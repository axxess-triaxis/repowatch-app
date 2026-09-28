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
- Privacy policy: https://repowatch-app.vercel.app/privacy (the `repowatch-app` Vercel project serves `site/`, generated from `docs/privacy.md`)
- Support: https://repowatch-app.vercel.app/support, which points to https://github.com/axxess-triaxis/repowatch-app/issues
- Homepage: https://repowatch-app.vercel.app/

After editing `README.md`, `docs/privacy.md` or `docs/support.md`, run `python scripts/build_site.py` and commit `site/`. `tests/test_site.py` fails if the site is stale.
- Documentation: https://github.com/axxess-triaxis/repowatch-app#readme

**Brand assets** (in `docs/assets/`):
- **Logo:** `repowatch-logo-512.png` (512x512). `repowatch-logo-200.png` is the 200x200 minimum size.
- **Feature card and banner:** `repowatch-banner.png` (2000x1050).
- **Colours:**

  | Use | Hex |
  |---|---|
  | Background / badge | `#0A0F1E` |
  | Shield | `#111A33` |
  | Accent gold | `#F2B544` |
  | Cream | `#E9E4D2` |
  | Wordmark gold | `#9A6A0D` |
  | Light background | `#F4F1E9` |

**Still needed before submitting:**
- 1 to 5 screenshots, taken from a real report issue made during setup step 5.
- If GitHub's feature-card form asks for a background colour rather than an image, use `#0A0F1E` with the 512px logo.
