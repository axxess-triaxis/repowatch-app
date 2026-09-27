# GitHub Marketplace listing: draft copy

**Name:** RepoWatch, or whatever name the App was registered under.

**Very short description (no more than 80 characters):**
Weekly governance audits for AI-assisted teams, posted as one GitHub issue.

**Primary category:** Security. **Secondary category:** Code review.

**Introductory description:**
AI coding agents make it cheap to ship a lot, fast. RepoWatch makes it cheap to notice when that has quietly turned into risk. It audits the repositories you grant it and keeps one "RepoWatch audit" issue up to date.

**Detailed description:**
- **Dependabot:** open alerts by severity, with "turned off" and "no access" kept separate from a real clean result.
- **Pull requests:** PRs open more than 10 days, and merges that still carry conflict markers.
- **Tests:** recent commits with no Playwright or Vitest run behind them.
- **PII:** possible personal data in code, always masked and marked for human review.
- **Sprawl:** near-duplicate repository names.

It runs on install, weekly, and whenever someone comments `/repowatch run`. It is read-only apart from its own report issue, and your code is never stored.

**Pricing:** Free.

**Links:**
- Privacy policy: `docs/privacy.md` (publish it with GitHub Pages and use that URL)
- Support: https://github.com/axxess-triaxis/repowatch-app/issues
- Documentation: https://github.com/axxess-triaxis/repowatch-app#readme

**Still needed before submitting:**
- A logo, at least 200x200 PNG.
- A feature card.
- 1 to 5 screenshots, taken from a real report issue made during setup step 5.
