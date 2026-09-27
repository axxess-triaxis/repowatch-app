"""Webhook verification and routing. Pure functions, no AWS or network calls."""

from __future__ import annotations

import hashlib
import hmac

from .github_app import ISSUE_TITLE

RUN_COMMAND = "/repowatch run"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def verify_signature(secret: bytes, body: bytes, signature_header: str | None) -> bool:
    """Check GitHub's X-Hub-Signature-256 header (HMAC-SHA256 of the raw body)."""
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _job(payload: dict, trigger: str) -> dict | None:
    installation = payload.get("installation") or {}
    account = installation.get("account") or {}
    owner = account.get("login") or (payload.get("organization") or {}).get("login") \
        or (payload.get("repository") or {}).get("owner", {}).get("login")
    if not installation.get("id") or not owner:
        return None
    return {"type": "audit", "installation_id": installation["id"], "owner": owner, "trigger": trigger}


def route(event: str, payload: dict) -> dict | None:
    """Map a webhook delivery to an audit job, or None when nothing should run."""
    action = payload.get("action")

    if event == "installation" and action == "created":
        return _job(payload, "new installation")

    if event == "installation_repositories" and action == "added":
        return _job(payload, "repositories added")

    if event == "issue_comment" and action == "created":
        comment = payload.get("comment") or {}
        issue = payload.get("issue") or {}
        sender = payload.get("sender") or {}
        if (
            comment.get("body", "").strip().lower() == RUN_COMMAND
            and issue.get("title") == ISSUE_TITLE
            and "pull_request" not in issue
            and comment.get("author_association") in TRUSTED_ASSOCIATIONS
            and sender.get("type") != "Bot"
        ):
            job = _job(payload, f"requested by @{sender.get('login')}")
            if job:
                job["reply_to"] = {
                    "repo": (payload.get("repository") or {}).get("full_name"),
                    "issue": issue.get("number"),
                }
            return job

    # ping, marketplace_purchase (free plan: nothing to provision), and every
    # other event are acknowledged without running anything.
    return None
