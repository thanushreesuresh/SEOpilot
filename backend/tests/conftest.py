"""Unit/integration tests must never consume a developer's real API key."""

import os

# Set before test modules import app.py: don't load backend/.env during pytest.
# Individual SDK contract tests explicitly install harmless fake credentials.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["OPENAI_API_KEY"] = ""
# Unit contracts exercise injected fake providers even when the developer/CI has
# the runtime kill switch off. Credentials remain blank and dotenv stays disabled.
os.environ["SEOPILOT_AI_ENABLED"] = "true"
os.environ["SEOPILOT_LOCAL_UNLIMITED_AUDITS"] = "false"
for name in ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_APP_OWNERS"):
    os.environ[name] = ""
