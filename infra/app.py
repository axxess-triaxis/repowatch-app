"""CDK entry point.

    cdk deploy -c client_id=<GitHub App client ID> [-c alert_email=you@example.com]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import aws_cdk as cdk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stack import RepoWatchAppStack  # noqa: E402

app = cdk.App()
client_id = app.node.try_get_context("client_id")
if not client_id:
    raise SystemExit("Pass the GitHub App client ID: cdk synth -c client_id=Iv23...")

RepoWatchAppStack(
    app, "RepoWatchApp",
    client_id=client_id,
    alert_email=app.node.try_get_context("alert_email"),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=app.node.try_get_context("region") or "ap-south-1",
    ),
    description="RepoWatch GitHub App - webhook, audit worker, weekly schedule",
)
cdk.Tags.of(app).add("Project", "RepoWatch")
app.synth()
