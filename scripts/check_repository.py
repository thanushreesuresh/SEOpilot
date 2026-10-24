"""Check working/staged files and optional Git history; never print secret values."""

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".md", ".json", ".toml", ".example", ".yml", ".yaml", ".txt", ".ps1", ".sh"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def private_path(name: str) -> bool:
    path = Path(name)
    return ((path.name.startswith(".env") and not path.name.endswith(".example"))
            or path.suffix in {".db", ".sqlite", ".pem", ".key"}
            or path.name == "proxy-token" or ".data" in path.parts)


def content_failures(name: str, content: str) -> list[str]:
    failures = []
    if re.search(r"\bsk-[A-Za-z0-9_-]{24,}\b", content):
        failures.append(f"Possible API credential in {name}; value withheld")
    if Path(name).name.startswith(".env"):
        for match in re.finditer(r"(?m)^\s*(?:export\s+)?OPENAI_API_KEY\s*=([^\r\n]*)", content):
            value = match[1].split("#", 1)[0].strip().strip("\"'")
            if value:
                failures.append(f"Nonempty API key in example {name}; value withheld")
    return failures


def scan_blob(name: str, content: bytes, failures: list[str]):
    if private_path(name):
        failures.append(f"Unexpected private/local file: {name}")
    if Path(name).suffix.lower() in TEXT_SUFFIXES or Path(name).name.startswith(".env"):
        failures.extend(content_failures(name, content.decode("utf-8-sig", errors="replace")))


def check(history: bool = False) -> list[str]:
    failures: list[str] = []
    paths = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    for name in set(filter(None, paths)):
        path = ROOT / name
        if not path.is_file():
            continue
        scan_blob(name, path.read_bytes(), failures)
        if path.suffix == ".md":
            for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8-sig")):
                target = target.strip("<>").split("#", 1)[0]
                if target and ":" not in target and not target.startswith("/") and not (path.parent / unquote(target)).exists():
                    failures.append(f"Missing Markdown target in {name}: {target}")
    # Cleaning the working file cannot hide a credential already staged for commit.
    for entry in filter(None, git("ls-files", "--stage", "-z").decode().split("\0")):
        metadata, name = entry.split("\t", 1)
        scan_blob(name, git("cat-file", "blob", metadata.split()[1]), failures)
    if history:
        for entry in git("rev-list", "--objects", "--all").decode().splitlines():
            oid, separator, name = entry.partition(" ")
            if (separator and (private_path(name) or Path(name).suffix.lower() in TEXT_SUFFIXES)
                    and git("cat-file", "-t", oid).strip() == b"blob"):
                scan_blob(name, git("cat-file", "blob", oid), failures)
    for name in ("backend/.env", "frontend/.env", ".env", "backend/.env.bak", "backend/.data/proxy-token"):
        result = subprocess.run(["git", "check-ignore", "--no-index", "-q", name], check=False, cwd=ROOT, capture_output=True)
        if result.returncode:
            failures.append(f"Private path is not ignored: {name}")
    return sorted(set(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also inspect all reachable history")
    failures = check(parser.parse_args().history)
    if failures:
        raise SystemExit("\n".join(failures))
    print("Working/staged credential, private-path, ignore-rule and Markdown-link checks passed.")
