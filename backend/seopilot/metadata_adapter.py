"""Parse untrusted Next.js source with our fixed, non-executing TypeScript helper.

No target package, config, imports, or scripts are loaded. Source is sent only to a
local parser process whose environment excludes provider and GitHub credentials.
"""

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

HELPER = Path(__file__).resolve().parents[2] / "repository-tools" / "metadata.mjs"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_FILE_BYTES = 128 * 1024
PATH_PATTERN = re.compile(r"^(?:src/)?app/(?:[^/\\\x00-\x1f]+/)*(?:page|layout)\.tsx?$")


class MetadataAdapterError(ValueError):
    """The proposed source transformation is unsupported or unavailable."""


def _validate_input(files: dict[str, str], edits: list[dict]) -> bytes:
    if not isinstance(files, dict) or not 1 <= len(files) <= 500:
        raise MetadataAdapterError("Provide a bounded App Router source inventory.")
    for path, source in files.items():
        if (not isinstance(path, str) or len(path) > 500 or not PATH_PATTERN.fullmatch(path)
                or any(part in {".", "..", ""} for part in path.split("/"))):
            raise MetadataAdapterError("Only safe App Router page and layout source paths are accepted.")
        try:
            source_size = len(source.encode("utf-8")) if isinstance(source, str) else MAX_FILE_BYTES + 1
        except UnicodeError:
            raise MetadataAdapterError("Source must be valid UTF-8 text.") from None
        if source_size > MAX_FILE_BYTES:
            raise MetadataAdapterError("Source file exceeds the bounded limit.")
    if not isinstance(edits, list) or not 1 <= len(edits) <= 3:
        raise MetadataAdapterError("Select between one and three pages.")
    try:
        encoded = json.dumps({"files": files, "edits": edits}, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as from_error:
        raise MetadataAdapterError("Invalid metadata edit input.") from from_error
    if len(encoded) > MAX_INPUT_BYTES:
        raise MetadataAdapterError("Source inventory exceeds the bounded limit.")
    return encoded


def _safe_environment() -> dict[str, str]:
    # NODE_OPTIONS/NODE_PATH and target app variables could load code or expose secrets.
    return {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "TEMP", "TMP", "LANG") if name in os.environ}


async def generate_metadata_patch(files: dict[str, str], edits: list[dict]) -> dict[str, Any]:
    """Return verified page edits, or fail as a whole without exposing source in errors.

    ``files`` is the complete bounded app/page/layout inventory at one commit,
    relative to the application directory. Edits contain URL, route and at least
    one title/description. Returned ``before``/``after`` remain private artifacts.
    """
    data = _validate_input(files, edits)
    node = shutil.which("node")
    if not node or not HELPER.is_file():
        raise MetadataAdapterError("Install Node.js and run npm ci in repository-tools to enable safe patches.")
    try:
        process = await asyncio.create_subprocess_exec(
            node, str(HELPER), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, cwd=str(HELPER.parent), env=_safe_environment(),
        )
    except OSError as from_error:
        raise MetadataAdapterError("The trusted metadata helper could not be started.") from from_error
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(data), timeout=15)
    except (TimeoutError, asyncio.CancelledError) as error:
        process.kill()
        await process.wait()
        if isinstance(error, asyncio.CancelledError):
            raise
        raise MetadataAdapterError("The trusted metadata helper exceeded its time limit.") from None
    if len(stdout) > MAX_OUTPUT_BYTES:
        raise MetadataAdapterError("Metadata helper output exceeded its bounded limit.")
    try:
        result = json.loads(stdout)
    except (ValueError, UnicodeError) as from_error:
        raise MetadataAdapterError("The trusted metadata helper is unavailable; run npm ci in repository-tools.") from from_error
    if not isinstance(result, dict) or result.get("ok") is not True or process.returncode:
        message = result.get("error") if isinstance(result, dict) else None
        # The helper exposes only fixed refusal messages, never parser/source diagnostics.
        if not isinstance(message, str) or len(message) > 200:
            message = "The trusted metadata helper could not process this source."
        raise MetadataAdapterError(message)
    changes = result.get("changes")
    mappings = result.get("mappings")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 3 or not isinstance(mappings, list):
        raise MetadataAdapterError("The trusted metadata helper returned an invalid result.")
    for change in changes:
        if (not isinstance(change, dict) or change.get("path") not in files
                or change.get("before") != files[change["path"]] or not isinstance(change.get("after"), str)
                or len(change["after"].encode("utf-8")) > MAX_FILE_BYTES + 2048):
            raise MetadataAdapterError("The trusted metadata helper returned an invalid source change.")
    return {"changes": changes, "mappings": mappings}
