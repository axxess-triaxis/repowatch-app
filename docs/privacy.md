# RepoWatch GitHub App: Privacy Policy

Effective 27 September 2026. Operated by Triaxis Ventures Private Limited.

## What the App reads

When it runs, the App reads the following from the repositories you grant it, using GitHub's API:

- repository metadata
- open pull requests
- recent commits and their check runs
- Dependabot alerts
- up to 80 text files per repository, for the PII pattern scan

## What the App stores

- **Your code:** not stored. Files are read into memory during an audit and discarded when it ends.
- **Audit results:** written only to the "RepoWatch audit" issue in your own repository. Possible PII is always shown masked, for example `22********08`. We keep no copy of reports.
- **Operational logs:** your installation ID and account name, repository counts, the report repository and issue number, and error messages. They are kept for 30 days in AWS CloudWatch, in the ap-south-1 (Mumbai) region, to operate and debug the service. Logs contain no code, no file contents and no unmasked PII.
- **Credentials:** GitHub installation tokens are short-lived and held only in memory during an audit.

## What the App does not do

- It doesn't sell or share your data.
- It doesn't use third-party analytics or advertising.
- It doesn't send your data anywhere except GitHub's own API.
- It doesn't write to your repositories, other than the report issue and its replies.

## Your control

- Change which repositories the App can reach, or uninstall it, at any time in your GitHub settings. Uninstalling stops all access immediately.
- The report issue is yours to edit, close or delete.
- To ask for your operational logs to be deleted before the 30 days are up, open an issue at https://github.com/axxess-triaxis/repowatch-app/issues without including sensitive details. We'll reply there.

## Changes

We'll update this page and its effective date if the policy changes.
