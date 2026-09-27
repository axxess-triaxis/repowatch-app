"""RepoWatch GitHub App infrastructure.

GitHub -> API Gateway (HTTP API) -> webhook Lambda -> SQS -> worker Lambda
EventBridge Scheduler (weekly) -> SQS -> worker Lambda (fans out per installation)

Secrets: two Secrets Manager secrets. The webhook secret is generated here and
read only by the webhook function; the App private key (PEM) is put by the
operator after deploy and read only by the worker. Neither is in code,
templates, or logs.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_lambda as lambda_,
    aws_lambda_event_sources as event_sources,
    aws_logs as logs,
    aws_scheduler as scheduler,
    aws_scheduler_targets as targets,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_sqs as sqs,
)
from constructs import Construct

BUILD_DIR = Path(__file__).resolve().parent.parent / "build" / "lambda"
WORKER_TIMEOUT = Duration.minutes(15)


class RepoWatchAppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, client_id: str,
                 alert_email: str | None = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not (BUILD_DIR / "repowatch_app").is_dir():
            raise RuntimeError("build/lambda is missing: run `python scripts/build_lambda.py` first")
        code = lambda_.Code.from_asset(str(BUILD_DIR))

        webhook_secret = secretsmanager.Secret(
            self, "WebhookSecret",
            description="RepoWatch GitHub App - webhook secret (generated; copy into the App settings)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True, password_length=48),
            removal_policy=RemovalPolicy.RETAIN,
        )
        private_key = secretsmanager.Secret(
            self, "PrivateKey",
            description="RepoWatch GitHub App - private key PEM (set after deploy)",
            secret_string_value=SecretValue.unsafe_plain_text("SET-AFTER-DEPLOY"),
            removal_policy=RemovalPolicy.RETAIN,
        )

        dlq = sqs.Queue(
            self, "JobsDlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
        )
        jobs = sqs.Queue(
            self, "Jobs",
            # AWS guidance: at least 6x the consuming function's timeout.
            visibility_timeout=Duration.minutes(90),
            retention_period=Duration.days(2),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )

        common = dict(
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            code=code,
            environment={"QUEUE_URL": jobs.queue_url},
        )

        webhook_fn = lambda_.Function(
            self, "WebhookFn",
            handler="repowatch_app.handlers.webhook_handler",
            timeout=Duration.seconds(10),
            memory_size=256,
            log_group=logs.LogGroup(self, "WebhookLogs", retention=logs.RetentionDays.ONE_MONTH,
                                    removal_policy=RemovalPolicy.DESTROY),
            **common,
        )
        worker_fn = lambda_.Function(
            self, "WorkerFn",
            handler="repowatch_app.handlers.worker_handler",
            timeout=WORKER_TIMEOUT,
            memory_size=1024,
            reserved_concurrent_executions=2,
            log_group=logs.LogGroup(self, "WorkerLogs", retention=logs.RetentionDays.ONE_MONTH,
                                    removal_policy=RemovalPolicy.DESTROY),
            **common,
        )
        webhook_fn.add_environment("WEBHOOK_SECRET_ARN", webhook_secret.secret_arn)
        worker_fn.add_environment("PRIVATE_KEY_SECRET_ARN", private_key.secret_arn)
        worker_fn.add_environment("GITHUB_APP_CLIENT_ID", client_id)

        # Each function can read only the secret it needs.
        webhook_secret.grant_read(webhook_fn)
        private_key.grant_read(worker_fn)
        jobs.grant_send_messages(webhook_fn)
        jobs.grant_send_messages(worker_fn)  # scheduled job fans out per installation
        worker_fn.add_event_source(event_sources.SqsEventSource(
            jobs, batch_size=1, report_batch_item_failures=True))

        api = apigw.HttpApi(self, "WebhookApi", description="RepoWatch GitHub App webhook")
        api.add_routes(
            path="/webhook",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("WebhookIntegration", webhook_fn),
        )
        default_stage = api.default_stage.node.default_child
        default_stage.add_property_override("DefaultRouteSettings.ThrottlingRateLimit", 20)
        default_stage.add_property_override("DefaultRouteSettings.ThrottlingBurstLimit", 40)

        scheduler.Schedule(
            self, "WeeklyAudit",
            description="Weekly RepoWatch audit of every installation",
            # Mondays 03:30 UTC (09:00 IST).
            schedule=scheduler.ScheduleExpression.cron(minute="30", hour="3", week_day="MON"),
            target=targets.SqsSendMessage(
                jobs, input=scheduler.ScheduleTargetInput.from_object({"type": "scheduled"})),
        )

        alarms = [
            cloudwatch.Alarm(
                self, "WorkerErrors",
                metric=worker_fn.metric_errors(period=Duration.hours(1)),
                threshold=1, evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description="A RepoWatch audit job failed",
            ),
            cloudwatch.Alarm(
                self, "DeadLetters",
                metric=dlq.metric_approximate_number_of_messages_visible(period=Duration.minutes(5)),
                threshold=1, evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description="RepoWatch jobs failed three times and reached the dead-letter queue",
            ),
            cloudwatch.Alarm(
                self, "WebhookErrors",
                metric=webhook_fn.metric_errors(period=Duration.minutes(15)),
                threshold=1, evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description="The RepoWatch webhook function raised errors",
            ),
        ]
        if alert_email:
            topic = sns.Topic(self, "Alerts", enforce_ssl=True)
            topic.add_subscription(subscriptions.EmailSubscription(alert_email))
            for alarm in alarms:
                alarm.add_alarm_action(cw_actions.SnsAction(topic))

        CfnOutput(self, "WebhookUrl", value=f"{api.api_endpoint}/webhook",
                  description="Paste into the GitHub App's Webhook URL")
        CfnOutput(self, "WebhookSecretName", value=webhook_secret.secret_name,
                  description="Generated webhook secret: copy its value into the GitHub App settings")
        CfnOutput(self, "PrivateKeySecretName", value=private_key.secret_name,
                  description="Put the App private key PEM here after deploy")
