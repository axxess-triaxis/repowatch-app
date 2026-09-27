"""Unit tests for the RepoWatch GitHub App. No network, no AWS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from repowatch_app import github_app, handlers, render, webhook, worker

SECRET = b"webhook-secret"


def sign(body: bytes, secret: bytes = SECRET) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


@pytest.fixture(scope="module")
def key_pair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return private_pem, key.public_key()


# --- signatures ---------------------------------------------------------------

def test_valid_signature_is_accepted():
    body = b'{"action":"created"}'
    assert webhook.verify_signature(SECRET, body, sign(body))


@pytest.mark.parametrize("header", [None, "", "sha1=abc", "sha256=" + "0" * 64])
def test_bad_or_missing_signature_is_rejected(header):
    assert not webhook.verify_signature(SECRET, b"{}", header)


def test_tampered_body_is_rejected():
    assert not webhook.verify_signature(SECRET, b'{"a":2}', sign(b'{"a":1}'))


def test_empty_secret_never_verifies():
    assert not webhook.verify_signature(b"", b"{}", sign(b"{}", b""))


# --- routing ------------------------------------------------------------------

INSTALLATION = {"id": 42, "account": {"login": "acme"}}


def test_new_installation_queues_an_audit():
    job = webhook.route("installation", {"action": "created", "installation": INSTALLATION})
    assert job == {"type": "audit", "installation_id": 42, "owner": "acme", "trigger": "new installation"}


def test_installation_deleted_does_nothing():
    assert webhook.route("installation", {"action": "deleted", "installation": INSTALLATION}) is None


def comment_payload(**overrides):
    payload = {
        "action": "created",
        "installation": INSTALLATION,
        "repository": {"full_name": "acme/.github", "owner": {"login": "acme"}},
        "issue": {"number": 5, "title": github_app.ISSUE_TITLE},
        "comment": {"body": "/repowatch run", "author_association": "MEMBER"},
        "sender": {"login": "dev", "type": "User"},
    }
    payload.update(overrides)
    return payload


def test_run_command_from_a_member_queues_an_audit_with_reply():
    job = webhook.route("issue_comment", comment_payload())
    assert job["trigger"] == "requested by @dev"
    assert job["reply_to"] == {"repo": "acme/.github", "issue": 5}


@pytest.mark.parametrize("override", [
    {"comment": {"body": "/repowatch run", "author_association": "NONE"}},
    {"comment": {"body": "please run it", "author_association": "OWNER"}},
    {"issue": {"number": 5, "title": "Some other issue"}},
    {"issue": {"number": 5, "title": github_app.ISSUE_TITLE, "pull_request": {}}},
    {"sender": {"login": "bot", "type": "Bot"}},
])
def test_run_command_is_ignored_unless_trusted_and_on_the_report_issue(override):
    assert webhook.route("issue_comment", comment_payload(**override)) is None


def test_marketplace_and_ping_are_acknowledged_only():
    assert webhook.route("marketplace_purchase", {"action": "purchased"}) is None
    assert webhook.route("ping", {"zen": "hi"}) is None


# --- App JWT -------------------------------------------------------------------

def test_app_jwt_claims(key_pair):
    private_pem, public_key = key_pair
    token = github_app.app_jwt("Iv1.client", private_pem, now=1_000_000)
    claims = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_exp": False})
    assert claims == {"iat": 999_940, "exp": 1_000_540, "iss": "Iv1.client"}
    assert claims["exp"] - 1_000_000 <= 600


# --- report repository and rendering -----------------------------------------

def test_report_repo_prefers_dot_github():
    repos = [{"name": "api", "full_name": "acme/api"}, {"name": ".github", "full_name": "acme/.github"}]
    assert worker.pick_report_repo(repos) == "acme/.github"


def test_report_repo_single_repo_and_ambiguous():
    assert worker.pick_report_repo([{"name": "api", "full_name": "acme/api"}]) == "acme/api"
    assert worker.pick_report_repo([{"name": "a", "full_name": "acme/a"},
                                    {"name": "b", "full_name": "acme/b"}]) is None


REPORT = {
    "org": "acme",
    "generated_at": "2026-09-27T05:00:00+00:00",
    "repos_scanned": 2,
    "sprawl": {"over_threshold": False, "near_duplicates": []},
    "repos": [
        {
            "repo": "web",
            "dependabot": {"findings": [
                {"severity": "critical", "package": "next", "summary": "RCE", "url": "https://x/1"},
                {"severity": "high", "package": "image-size", "summary": "DoS", "url": "https://x/2"},
            ], "access_denied": False, "dependabot_disabled": False, "error": None},
            "stale_prs": {"stale_prs": [{"number": 9, "title": "bump", "days_open": 15, "url": "https://x/pr"}], "error": None},
            "conflict_merges": {"findings": [], "error": None},
            "untested_deploys": {"findings": [{"sha": "abc"}], "error": None},
            "pii": {"findings": [
                {"path": "src/a.py", "kind": "aadhaar_in", "masked_excerpt": "22********08", "likely_benign": False},
                {"path": "tests/t.py", "kind": "email", "masked_excerpt": "re****om", "likely_benign": True},
            ], "error": None},
        },
        {
            "repo": "docs",
            "dependabot": {"findings": [], "access_denied": False, "dependabot_disabled": True, "error": None},
            "stale_prs": {"stale_prs": [], "error": None},
            "conflict_merges": {"findings": [], "error": None},
            "untested_deploys": {"findings": [], "error": None},
            "pii": {"findings": [], "error": None},
        },
    ],
}


def test_render_summary_and_details():
    body = render.render(REPORT, "new installation")
    assert "| `web` | **2 open** (1 critical, 1 high) | **1** | 0 | **1** | **1** to review |" in body
    assert "| `docs` | turned off |" in body
    assert "`22********08`" in body
    assert "re****om" not in body  # likely-benign PII is not listed
    assert "/repowatch run" in body


def test_render_truncates_to_issue_limit():
    huge = json.loads(json.dumps(REPORT))
    huge["repos"][0]["stale_prs"]["stale_prs"] = [
        {"number": i, "title": "x" * 200, "days_open": 11, "url": "u"} for i in range(1000)
    ]
    body = render.render(huge, "t")
    assert len(body) <= render.MAX_BODY + 100
    assert body.endswith("_Report truncated to fit GitHub's issue size limit._")


# --- Lambda handlers ------------------------------------------------------------

@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("QUEUE_URL", "https://sqs.test/q")
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.client")
    monkeypatch.setattr(handlers, "_secrets", {"WEBHOOK_SECRET_ARN": SECRET.decode(), "PRIVATE_KEY_SECRET_ARN": "pem"})
    sqs = MagicMock()
    monkeypatch.setattr(handlers, "_sqs", sqs)
    return sqs


def api_event(payload: dict, event: str, signature: str | None = None, b64: bool = False) -> dict:
    body = json.dumps(payload).encode()
    return {
        "headers": {"X-GitHub-Event": event, "X-Hub-Signature-256": signature or sign(body)},
        "body": base64.b64encode(body).decode() if b64 else body.decode(),
        "isBase64Encoded": b64,
    }


def test_webhook_rejects_bad_signature_with_401(aws):
    event = api_event({"action": "created", "installation": INSTALLATION}, "installation",
                      signature="sha256=" + "0" * 64)
    assert handlers.webhook_handler(event, None)["statusCode"] == 401
    aws.send_message.assert_not_called()


@pytest.mark.parametrize("b64", [False, True])
def test_webhook_queues_installation_audit(aws, b64):
    event = api_event({"action": "created", "installation": INSTALLATION}, "installation", b64=b64)
    assert handlers.webhook_handler(event, None)["statusCode"] == 202
    sent = json.loads(aws.send_message.call_args.kwargs["MessageBody"])
    assert sent["installation_id"] == 42 and sent["type"] == "audit"


def test_webhook_acknowledges_ping_without_queueing(aws):
    assert handlers.webhook_handler(api_event({"zen": "hi"}, "ping"), None)["statusCode"] == 200
    aws.send_message.assert_not_called()


def test_worker_scheduled_job_fans_out_per_installation(aws):
    installs = [{"id": 1, "account": {"login": "a"}}, {"id": 2, "account": {"login": "b"}}]
    with patch.object(github_app, "app_jwt", return_value="jwt"), \
         patch.object(github_app, "list_installations", return_value=installs):
        out = handlers.worker_handler({"Records": [{"messageId": "m1", "body": '{"type": "scheduled"}'}]}, None)
    assert out == {"batchItemFailures": []}
    owners = [json.loads(c.kwargs["MessageBody"])["owner"] for c in aws.send_message.call_args_list]
    assert owners == ["a", "b"]


def test_worker_reports_failed_messages_for_retry(aws):
    with patch.object(handlers, "audit_installation", side_effect=RuntimeError("boom")):
        out = handlers.worker_handler(
            {"Records": [{"messageId": "m9", "body": json.dumps({"type": "audit", "installation_id": 1,
                                                               "owner": "a", "trigger": "t"})}]}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "m9"}]}


# --- worker end to end (GitHub mocked) ------------------------------------------

def test_audit_installation_audits_only_active_granted_repos_and_posts_issue():
    repos = [
        {"name": "web", "full_name": "acme/web", "archived": False, "fork": False},
        {"name": "old", "full_name": "acme/old", "archived": True, "fork": False},
        {"name": ".github", "full_name": "acme/.github", "archived": False, "fork": False},
    ]
    with patch.object(github_app, "app_jwt", return_value="jwt"), \
         patch.object(github_app, "installation_token", return_value="ghs_x"), \
         patch.object(github_app, "installation_repos", return_value=repos), \
         patch.object(worker, "run_audit", return_value=REPORT) as run, \
         patch.object(github_app, "upsert_report_issue", return_value=(3, True)) as upsert, \
         patch.object(worker.github_client, "use_token") as use_token:
        summary = worker.audit_installation(
            {"installation_id": 42, "owner": "acme", "trigger": "t"}, "Iv1.client", "pem")

    run.assert_called_once_with("acme", ["web", ".github"])
    assert upsert.call_args.args[1] == "acme/.github"
    assert use_token.call_args_list[0].args == ("ghs_x",)
    assert use_token.call_args_list[-1].args == (None,)  # token cleared after the audit
    assert summary["issue"] == 3


def test_audit_installation_never_widens_to_whole_org_when_nothing_granted():
    with patch.object(github_app, "app_jwt", return_value="jwt"), \
         patch.object(github_app, "installation_token", return_value="ghs_x"), \
         patch.object(github_app, "installation_repos", return_value=[
             {"name": "old", "full_name": "acme/old", "archived": True, "fork": False}]), \
         patch.object(worker, "run_audit") as run:
        worker.audit_installation({"installation_id": 42, "owner": "acme", "trigger": "t"}, "c", "pem")
    run.assert_not_called()
