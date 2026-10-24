"""Server-only configuration. No settings object is serialized to the browser."""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _integer(name: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


@dataclass(frozen=True)
class Settings:
    ai_enabled: bool = True
    ai_daily_call_limit: int = 20
    ai_max_output_tokens: int = 2500

    @classmethod
    def from_env(cls):
        enabled = os.environ.get("SEOPILOT_AI_ENABLED", "true").lower()
        if enabled not in {"true", "false"}:
            raise ValueError("SEOPILOT_AI_ENABLED must be true or false")
        return cls(
            ai_enabled=enabled == "true",
            ai_daily_call_limit=_integer("SEOPILOT_AI_DAILY_CALL_LIMIT", 20, 0, 100),
            ai_max_output_tokens=_integer("OPENAI_MAX_OUTPUT_TOKENS", 2500, 512, 2500),
        )


def proxy_token(path: Path) -> str:
    """One shared local secret; Next reads this file only on its server."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        token = path.read_text(encoding="ascii").strip()
    else:
        token = secrets.token_hex(32)
        with os.fdopen(fd, "w", encoding="ascii") as output:
            output.write(token)
    if len(token) != 64 or any(char not in "0123456789abcdef" for char in token):
        raise ValueError("Invalid local proxy token file")
    return token
