# Private GitHub App setup

SEOPilot v2 is a local, single-operator tool for websites you own. Private repository source is parsed locally and never included in OpenAI requests. Publishing a branch or draft PR can trigger repository CI or previews and consume GitHub Actions usage separately from OpenAI usage.

1. In GitHub developer settings, create a **private GitHub App** for your account. Disable webhooks; local polling needs no tunnel or callback server.
2. Request repository permissions **Metadata: read**, **Contents: write**, **Pull requests: write**, and **Actions: read**. Leave all other repository, organization and account permissions disabled. Install on **selected repositories**.
3. Generate the RSA private key and keep its PEM file outside the checkout or in ignored `backend/.data/`. Restrict Windows file permissions to your local account. Never paste it into the browser, chat, a PR, or a committed file.
4. Set `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` (absolute path recommended), and comma-separated `GITHUB_APP_OWNERS` in ignored `backend/.env`. Restart the backend. The example contains no credentials. Repository-scoped installation tokens expire and live in memory only.
5. Connect a project in the dashboard. Choose an installed repository, enter the exact production origin, base branch and optional application subdirectory, and confirm this repository supplies that website. SEOPilot rechecks installation access and the owner allowlist before operations.

Disconnecting deletes cached patches and stops local work. Existing GitHub branches and PRs remain for manual review. Remove the App installation in GitHub to revoke external access completely. The user-managed private key is not automatically deleted.

The selected pilot is [thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio). Its production origin and App installation must be confirmed locally before pilot publication.

Sources: [GitHub App comparison](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps), [token scoping and expiry](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app). PyJWT/cryptography signs App JWTs; HTTPX uses verified TLS without ambient proxies.
