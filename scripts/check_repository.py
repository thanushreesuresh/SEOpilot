"""Check publishable paths, obvious API-key accidents and local Markdown links."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
).decode("utf-8").split("\0")
failures = []
for name in set(filter(None, paths)):
    path = ROOT / name
    if not path.is_file():
        continue
    if (path.name.startswith(".env") and not path.name.endswith(".example")) or path.suffix in {".db", ".sqlite", ".pem", ".key"}:
        failures.append(f"Unexpected private/local file: {name}")
    if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".mjs", ".md", ".json", ".toml", ".example"}:
        continue
    content = path.read_text(encoding="utf-8-sig")
    if re.search(r"\bsk-[A-Za-z0-9_-]{24,}\b", content):
        failures.append(f"Possible API credential in {name}; value withheld")
    if path.suffix == ".md":
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", content):
            target = target.strip("<>").split("#", 1)[0]
            if not target or ":" in target or target.startswith("/"):
                continue
            if not (path.parent / unquote(target)).exists():
                failures.append(f"Missing Markdown target in {name}: {target}")
if failures:
    raise SystemExit("\n".join(failures))
print("Publishable-file, credential-pattern and Markdown-link checks passed.")
