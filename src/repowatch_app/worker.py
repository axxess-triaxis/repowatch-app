"""Run one installation's audit and publish it as the report issue."""

from __future__ import annotations

import json
import logging

from repowatch import github_client
from repowatch.report import run_audit

from . import github_app
from .render import render

log = logging.getLogger(__name__)


def pick_report_repo(repos: list[dict]) -> str | None:
    """Where the report issue goes.

    The org's `.github` repository if the installation can reach it, otherwise
    the only repository when exactly one is granted. With several repositories
    and no `.github`, there is no unambiguous place to post, so nothing is posted.
    """
    for r in repos:
        if r.get("name") == ".github":
            return r["full_name"]
    if len(repos) == 1:
        return repos[0]["full_name"]
    return None


def audit_installation(job: dict, client_id: str, private_key: str) -> dict:
    """Audit the repositories granted to one installation. Returns a summary for logs."""
    app_token = github_app.app_jwt(client_id, private_key)
    token = github_app.installation_token(app_token, job["installation_id"])
    owner = job["owner"]

    repos = github_app.installation_repos(token)
    active = [r["name"] for r in repos if not r.get("archived") and not r.get("fork")]
    target = pick_report_repo(repos)
    summary = {"installation_id": job["installation_id"], "owner": owner,
               "repos_granted": len(repos), "repos_audited": len(active), "report_repo": target}

    if not active:
        # run_audit treats an empty list as "the whole org"; never widen scope.
        log.info("nothing to audit: %s", json.dumps(summary))
        return summary

    github_client.use_token(token)
    try:
        report = run_audit(owner, active)
    finally:
        github_client.use_token(None)

    if target is None:
        log.warning("no report repository (grant the App access to the .github repository): %s",
                    json.dumps(summary))
        return summary

    number, created = github_app.upsert_report_issue(token, target, render(report, job["trigger"]))
    summary.update(issue=number, created=created)

    reply = job.get("reply_to")
    if reply and reply.get("repo") and reply.get("issue") and reply["repo"] != target:
        # Only reachable if the comment was on a report issue in another repo.
        github_app.comment(token, reply["repo"], reply["issue"],
                           f"RepoWatch re-ran the audit. The report is in {target}#{number}.")
    elif reply and not created:
        github_app.comment(token, target, number, "RepoWatch re-ran the audit and updated this report.")

    log.info("audit published: %s", json.dumps(summary))
    return summary
