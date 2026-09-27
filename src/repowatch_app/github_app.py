"""GitHub App authentication, plus the few write calls the App makes.

The audit itself is read-only and runs through RepoWatch's own client
(`repowatch.github_client.use_token`). This module only mints tokens and
maintains the single report issue.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt

API = "https://api.github.com"
ISSUE_TITLE = "RepoWatch audit"


class GitHubError(RuntimeError):
    pass


def app_jwt(client_id: str, private_key_pem: str, now: float | None = None) -> str:
    """JWT that authenticates as the App itself.

    Per GitHub: RS256, `iat` 60 seconds in the past to allow for clock drift,
    `exp` at most 10 minutes ahead, `iss` set to the App's client ID.
    """
    issued = int(now if now is not None else time.time()) - 60
    claims = {"iat": issued, "exp": issued + 600, "iss": client_id}
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def call(method: str, path: str, token: str, body: dict | None = None) -> object:
    url = path if path.startswith("https://") else f"{API}/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repowatch-app",
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise GitHubError(f"{method} {path} failed (HTTP {e.code}): {detail}") from None
    return json.loads(raw) if raw.strip() else None


def _pages(path: str, token: str, key: str | None = None, limit: int = 1000) -> list:
    """Page-number pagination for the App endpoints (100 per page)."""
    items: list = []
    page = 1
    while len(items) < limit:
        sep = "&" if "?" in path else "?"
        data = call("GET", f"{path}{sep}per_page=100&page={page}", token)
        batch = data.get(key, []) if key else data
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items[:limit]


def installation_token(app_token: str, installation_id: int) -> str:
    data = call("POST", f"app/installations/{installation_id}/access_tokens", app_token, {})
    return data["token"]


def list_installations(app_token: str) -> list[dict]:
    return _pages("app/installations", app_token)


def installation_repos(installation_token_: str) -> list[dict]:
    return _pages("installation/repositories", installation_token_, key="repositories")


def find_report_issue(token: str, repo_full_name: str) -> dict | None:
    """The App's open report issue in this repo, if there is one."""
    for issue in _pages(f"repos/{repo_full_name}/issues?state=open", token, limit=500):
        if (
            issue.get("title") == ISSUE_TITLE
            and "pull_request" not in issue
            and issue.get("user", {}).get("type") == "Bot"
        ):
            return issue
    return None


def upsert_report_issue(token: str, repo_full_name: str, body: str) -> tuple[int, bool]:
    """Update the open report issue, or open one. Returns (number, created)."""
    existing = find_report_issue(token, repo_full_name)
    if existing:
        call("PATCH", f"repos/{repo_full_name}/issues/{existing['number']}", token, {"body": body})
        return existing["number"], False
    created = call(
        "POST", f"repos/{repo_full_name}/issues", token, {"title": ISSUE_TITLE, "body": body}
    )
    return created["number"], True


def comment(token: str, repo_full_name: str, issue_number: int, body: str) -> None:
    call("POST", f"repos/{repo_full_name}/issues/{issue_number}/comments", token, {"body": body})
