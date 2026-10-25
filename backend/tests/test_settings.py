import importlib.util
import os
from pathlib import Path

import pytest

from seopilot.settings import Settings, proxy_token


def test_offline_suite_cannot_inherit_a_live_api_key():
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    assert not key_present
    assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1"


def test_safe_defaults_and_invalid_config(monkeypatch):
    for name in ("SEOPILOT_AI_ENABLED", "SEOPILOT_AI_DAILY_CALL_LIMIT", "OPENAI_MAX_OUTPUT_TOKENS",
                 "SEOPILOT_LOCAL_UNLIMITED_AUDITS"):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env() == Settings()
    for name, value in [("OPENAI_MAX_OUTPUT_TOKENS", "2501"), ("SEOPILOT_AI_DAILY_CALL_LIMIT", "-1"),
                        ("SEOPILOT_AI_DAILY_CALL_LIMIT", "unlimited"), ("SEOPILOT_AI_ENABLED", "yes"),
                        ("SEOPILOT_LOCAL_UNLIMITED_AUDITS", "yes")]:
        with monkeypatch.context() as context:
            context.setenv(name, value)
            with pytest.raises(ValueError, match=name):
                Settings.from_env()


def test_unlimited_local_audits_are_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("SEOPILOT_LOCAL_UNLIMITED_AUDITS", "true")
    assert Settings.from_env().local_unlimited_audits is True
    monkeypatch.setenv("SEOPILOT_LOCAL_UNLIMITED_AUDITS", "false")
    assert Settings.from_env().local_unlimited_audits is False


def test_proxy_token_persists_and_bad_file_fails_closed(tmp_path):
    path = tmp_path / "private" / "proxy-token"
    token = proxy_token(path)
    assert len(token) == 64 and proxy_token(path) == token
    path.write_text("broken", encoding="ascii")
    with pytest.raises(ValueError, match="Invalid local proxy"):
        proxy_token(path)


def test_repository_guard_detects_credentials_without_echoing_them():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_repository.py"
    spec = importlib.util.spec_from_file_location("repository_guard", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    secret = "sk-" + "DO_NOT_PUBLISH_THIS_TEST_VALUE" * 2
    errors = module.content_failures("backend/.env.example", f"OPENAI_API_KEY={secret}")
    assert len(errors) == 2 and all(secret not in error for error in errors)
    assert not module.content_failures("backend/.env.example", "OPENAI_API_KEY=\nOPENAI_MODEL=gpt-6-luna\n")
    assert module.private_path("backend/.env") and module.private_path("backend/.data/proxy-token")
