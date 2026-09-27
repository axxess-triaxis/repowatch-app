"""AWS Lambda entry points.

- `webhook_handler`: behind API Gateway (HTTP API). Verifies the signature,
  turns the delivery into a job, and queues it. It answers GitHub within its
  10-second webhook timeout; audits take minutes, so they never run here.
- `worker_handler`: consumes the queue. A `scheduled` job (from EventBridge
  Scheduler) fans out one `audit` job per installation; an `audit` job runs
  one installation's audit.

The webhook secret and the App private key are separate Secrets Manager
secrets, each readable only by the function that needs it. They are read at
runtime, cached for the life of the container, and never logged.
"""

from __future__ import annotations

import base64
import json
import logging
import os

import boto3

from . import github_app
from .webhook import route, verify_signature
from .worker import audit_installation

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger(__name__)

_secrets: dict[str, str] = {}
_sqs = None


def _secret(env_var: str) -> str:
    """Secret value named by an environment variable, cached per container."""
    if env_var not in _secrets:
        value = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ[env_var])
        _secrets[env_var] = value["SecretString"].strip()
    return _secrets[env_var]


def _queue():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs")
    return _sqs


def _enqueue(job: dict) -> None:
    _queue().send_message(QueueUrl=os.environ["QUEUE_URL"], MessageBody=json.dumps(job))


def _response(status: int, message: str) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": message})}


def webhook_handler(event: dict, context) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    raw = event.get("body") or ""
    body = base64.b64decode(raw) if event.get("isBase64Encoded") else raw.encode("utf-8")

    secret = _secret("WEBHOOK_SECRET_ARN").encode("utf-8")
    if not verify_signature(secret, body, headers.get("x-hub-signature-256")):
        log.warning("rejected webhook with a bad signature, delivery %s", headers.get("x-github-delivery"))
        return _response(401, "invalid signature")

    name = headers.get("x-github-event", "")
    try:
        payload = json.loads(body)
    except ValueError:
        return _response(400, "invalid JSON")

    job = route(name, payload)
    if job is None:
        return _response(200, f"{name} acknowledged")
    _enqueue(job)
    log.info("queued audit for installation %s (%s)", job["installation_id"], name)
    return _response(202, "audit queued")


def worker_handler(event: dict, context) -> dict:
    failures = []
    for record in event.get("Records", []):
        try:
            job = json.loads(record["body"])
            if job.get("type") == "scheduled":
                app_token = github_app.app_jwt(os.environ["GITHUB_APP_CLIENT_ID"],
                                               _secret("PRIVATE_KEY_SECRET_ARN"))
                for inst in github_app.list_installations(app_token):
                    _enqueue({"type": "audit", "installation_id": inst["id"],
                              "owner": inst["account"]["login"], "trigger": "weekly schedule"})
            elif job.get("type") == "audit":
                audit_installation(job, os.environ["GITHUB_APP_CLIENT_ID"], _secret("PRIVATE_KEY_SECRET_ARN"))
            else:
                log.warning("unknown job type %r", job.get("type"))
        except Exception:  # noqa: BLE001 -- report per-message failure, SQS retries then DLQ
            log.exception("job failed, message %s", record.get("messageId"))
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
