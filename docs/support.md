# RepoWatch GitHub App: Support

Open an issue at https://github.com/axxess-triaxis/repowatch-app/issues. Please don't paste tokens, private keys or unmasked personal data into an issue.

## Common questions

**No report issue appeared.**
Grant the App access to your org's `.github` repository. The App posts there. If you granted exactly one repository, it posts in that one instead. With several repositories and no `.github`, there is nowhere unambiguous to post, so nothing is posted.

**Dependabot shows "no access".**
The App was installed before it requested the Dependabot alerts permission, or the permission request is still pending. An org owner can accept updated permissions under **Settings → GitHub Apps → RepoWatch**.

**Dependabot shows "turned off".**
Dependabot alerts were never enabled for that repository. Enable them under the repository's **Settings → Code security**.

**Every commit shows as untested.**
RepoWatch only recognises check runs whose names contain `playwright` or `vitest`. Repositories that test with other tools show every commit as untested. This is a known limitation.

**How do I re-run the audit?**
Comment `/repowatch run` on the report issue. Only owners, members and collaborators can trigger it.
