"""Unit/integration tests must never consume a developer's real API key."""

import os

# Set before test modules import app.py: don't load backend/.env during pytest.
# Individual SDK contract tests explicitly install harmless fake credentials.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["OPENAI_API_KEY"] = ""
for name in ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_APP_OWNERS"):
    os.environ[name] = ""
