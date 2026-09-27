# Register and deploy the RepoWatch GitHub App

These steps need an account owner. They create credentials and cloud resources, so nobody else should do them on your behalf.

## 1. Register the GitHub App

Go to GitHub, then **Developer settings → GitHub Apps → New GitHub App**. For a personal account like `axxess-triaxis`, that's **Settings → Developer settings**. For an organization, it's **Organization settings → Developer settings**.

| Field | Value |
|---|---|
| GitHub App name | `RepoWatch`. If it's taken, choose another, such as `RepoWatch Audit`. |
| Homepage URL | `https://github.com/axxess-triaxis/repowatch-app` |
| Webhook: Active | On |
| Webhook URL | `https://example.com/webhook` for now; you'll replace it in step 4 |
| Webhook secret | Leave empty for now; you'll set it in step 4 |
| Where can this GitHub App be installed? | **Any account** (required for the Marketplace) |

**Repository permissions:**

| Permission | Access |
|---|---|
| Checks | Read-only |
| Contents | Read-only |
| Dependabot alerts | Read-only |
| Issues | Read and write |
| Metadata | Read-only (set automatically) |
| Pull requests | Read-only |

Leave every other permission at **No access**.

**Subscribe to events:** Issue comment. The installation events are always delivered, so there's nothing to tick for them.

Create the App. On its settings page:

1. Under **Display information**, upload `docs/assets/repowatch-logo-512.png` as the logo and set **Badge background color** to `#0A0F1E`.
1. Note the **Client ID** (it starts with `Iv`).
2. Under **Private keys**, select **Generate a private key**. A `.pem` file downloads. Keep it out of any git folder.

## 2. Deploy to AWS

You need AWS credentials for the target account, plus Node.js and Python 3.13 or newer.

```bash
cd repowatch-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/build_lambda.py
npx aws-cdk@2.1142.0 bootstrap aws://<ACCOUNT_ID>/ap-south-1
npx aws-cdk@2.1142.0 diff -c client_id=<CLIENT_ID>
npx aws-cdk@2.1142.0 deploy -c client_id=<CLIENT_ID> -c alert_email=<ALERT_EMAIL>
```

- **Bootstrap** is needed once per account and region.
- **`alert_email`** is optional. AWS sends a confirmation email that you must accept before alarm emails arrive.

The deploy prints three outputs: `WebhookUrl`, `WebhookSecretName` and `PrivateKeySecretName`.

## 3. Store the private key

```bash
aws secretsmanager put-secret-value --region ap-south-1 --secret-id <PrivateKeySecretName> --secret-string file://path/to/your-app.private-key.pem
```

Then delete the downloaded `.pem`, or move it somewhere safe outside any repository. GitHub lets you generate a new key at any time, which is the rotation path: generate a new key, `put-secret-value` it, then delete the old key in GitHub.

## 4. Point the App at AWS

1. In the AWS console, open **Secrets Manager** in ap-south-1, then the secret named `WebhookSecretName`, then **Retrieve secret value**. Copy the value.
2. In the GitHub App settings:
   - Set **Webhook URL** to the `WebhookUrl` output.
   - Set **Webhook secret** to that value.
   - Save.
3. Still in the App settings, open **Advanced**. The latest `ping` delivery should now show **200** after you select **Redeliver**.

## 5. Try it

Install the App on `axxess-triaxis`, granting the `.github` repository and one or two others. If there's no `.github` repository, grant exactly one repository, and the report goes there. Within a few minutes a **RepoWatch audit** issue should appear.

Then check the following:

- A comment of `/repowatch run` on that issue updates the report and adds a reply.
- A request with a bad signature is rejected with **401**:

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -X POST <WebhookUrl> -H "X-GitHub-Event: ping" -H "X-Hub-Signature-256: sha256=0000" -d "{}"
  ```

- CloudWatch Logs for the worker (the log group whose name starts with `RepoWatchApp-WorkerLogs`) show `audit published: {...}`.

## 6. List it on GitHub Marketplace (free plan)

Requirements, per GitHub's docs:
- The App must be publicly installable (step 1 does this).
- A privacy policy URL and a support URL: publish `docs/privacy.md` and `docs/support.md` with GitHub Pages, or link to them on GitHub.
- A logo, feature card and screenshots. Take the screenshots from a real report issue made in step 5.
- A free pricing plan.
- The Marketplace Developer Agreement accepted.
- Two-factor authentication on your account.

Paid plans are not in scope; they need 100+ installations and a verified publisher.

Listing copy is drafted in [MARKETPLACE_LISTING.md](MARKETPLACE_LISTING.md).

## Costs

With a handful of installations, Lambda, SQS, API Gateway, Scheduler and CloudWatch usage stays at low single-digit US dollars a month. Secrets Manager is about USD 0.40 per secret per month. These are estimates, not measured.
