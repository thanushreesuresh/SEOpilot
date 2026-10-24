# Private GitHub App setup

SEOPilot v2 is a local, single-operator tool for websites you own. Private repository source is parsed locally and never included in OpenAI requests. Publishing a branch or draft PR can trigger repository CI or previews and consume GitHub Actions usage separately from OpenAI usage.

1. Open [New GitHub App](https://github.com/settings/apps/new) while signed in as `thanushreesuresh`. Choose an available name such as `SEOPilot Thanushree` and use `https://github.com/thanushreesuresh/SEOpilot` as the homepage.
2. Leave callback/setup URLs blank. Leave OAuth authorization during installation and Device Flow disabled. Under Webhook, uncheck **Active**; local polling needs no tunnel or callback server. Choose **Only on this account**.
3. Set repository permissions **Metadata: Read-only**, **Contents: Read & write**, **Pull requests: Read & write**, and **Actions: Read-only**. Leave other repository, organization and account permissions disabled, then create the App.
4. Copy the numeric **App ID** from the App settings; this is different from the Client ID. Generate an RSA private key from **Credentials → Key pairs → New key** (some GitHub layouts show **Private keys → Generate a private key**). Keep the downloaded PEM outside this OneDrive checkout, for example `C:/Users/thanu/.seopilot/portfolio-app.pem`, with file permissions limited to your local account. Never paste its contents into chat, the dashboard, a PR, or source files.
5. Under **Install App**, install on your own account, choose **Only select repositories**, and select **thanushree-portfolio**. Registering the App alone does not install it or grant repository access.
6. Edit the existing ignored `backend/.env`, preserving your OpenAI setting. Add or update only these entries, replacing the App ID and path with your actual local values:

   ```dotenv
   GITHUB_APP_ID=YOUR_NUMERIC_APP_ID
   GITHUB_APP_PRIVATE_KEY_PATH=C:/Users/thanu/.seopilot/portfolio-app.pem
   GITHUB_APP_OWNERS=thanushreesuresh
   ```

   Use an absolute path to the PEM file, not its contents. Forward slashes avoid Windows backslash escaping in dotenv files. Do not replace the entire `.env` with the example. No client secret, personal access token or installation token belongs in these settings. Repository-scoped installation tokens expire and live in memory only.
7. Manually stop the existing backend in its terminal and restart it from the repository root with `.\.venv\Scripts\python.exe -m seopilot`. Restart the dashboard using the README commands to load the latest build. Preserve `backend/.data/` and its quota database.
8. Connect a project in the dashboard: select `thanushree-portfolio`, production origin `https://thanushree-portfolio-six.vercel.app`, and base branch `main`. Set the application subdirectory to the folder containing the site's Next.js app, or leave blank if it is at the repository root. Explicitly confirm this repository supplies that website. SEOPilot rechecks installation access and the owner allowlist before operations.

If no repositories appear, confirm the App was installed on the selected repository and the owner matches `GITHUB_APP_OWNERS`. If the App is shown as unconfigured, check the three settings and restart the backend. If authentication fails, check that the PEM matches this App and the computer clock is correct. Reinstall or approve updated permissions in GitHub when necessary. Report only the sanitized error message; never include the `.env`, PEM, tokens or raw authenticated request headers.

Disconnecting deletes cached patches and stops local work. Existing GitHub branches and PRs remain for manual review. Remove the App installation in GitHub to revoke external access completely. The user-managed private key is not automatically deleted.

Before publishing, review and install the [owner-managed validation workflow](../validation/README.md) in the website repository. SEOPilot will never write workflow files for you. GitHub status polling lasts ten minutes per explicit publication, verification or **Refresh status** action; it then pauses until you refresh again. Pending writes are reconciled before another write attempt.

The selected pilot is [thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio), serving the user-confirmed origin [thanushree-portfolio-six.vercel.app](https://thanushree-portfolio-six.vercel.app/). Its GitHub repository ID is `1348533178` and base branch is `main`; the App installation and explicit project mapping must still be configured locally before pilot publication.

Sources: [registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app), [private-key management](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps), [GitHub App comparison](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps), [token scoping and expiry](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app). PyJWT/cryptography signs App JWTs; HTTPX uses verified TLS without ambient proxies.
