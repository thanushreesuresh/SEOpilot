"""Bounded JSON-LD syntax observations from fetched HTML, without remote processing.

This projection is not a JSON-LD processor, Schema.org validator, or search-feature
eligibility check. Source values and decoder exception bodies are never returned.
"""

import json
import re

from bs4 import BeautifulSoup

MAX_BLOCKS = 10
MAX_BLOCK_BYTES = 16 * 1024
MAX_TOTAL_BYTES = 64 * 1024
MAX_DEPTH = 32
MAX_TYPES = 20
MAX_TYPE_LENGTH = 120
MAX_OBSERVATIONS = 50

_TYPE_LABEL = re.compile(r"[\w:/.#-]+\Z")
_MESSAGES = {
    "json_ld_invalid_json": "A JSON-LD block cannot be parsed as JSON.",
    "json_ld_duplicate_key": "A JSON-LD object repeats a key; JSON-LD object keys must be unique.",
    "json_ld_non_finite_number": "A JSON-LD block uses a numeric constant that JSON does not support.",
    "json_ld_invalid_root": "A JSON-LD block needs an object or an array of objects at its root.",
    "json_ld_invalid_graph": "A JSON-LD @graph value contains a non-object entry.",
    "json_ld_missing_context": (
        "Review JSON-LD context: a root object has no @context. Fully qualified IRIs may be intentional."
    ),
    "json_ld_nonstandard_context": (
        "Review the declared JSON-LD context: it is outside directly recognized Schema.org forms. "
        "Other vocabularies and custom contexts can be valid."
    ),
    "json_ld_inspection_limited": "JSON-LD inspection reached a bound; review the omitted data separately.",
}


class _UnsupportedJSON(ValueError):
    """Use fixed codes instead of returning source-bearing decoder errors."""


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _UnsupportedJSON("json_ld_duplicate_key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise _UnsupportedJSON("json_ld_non_finite_number")


def _exceeds_depth(source: str) -> bool:
    """Check container depth before decoding; quoted delimiters are only data."""
    depth = 0
    quoted = False
    escaped = False
    for character in source:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                return True
        elif character in "]}":
            depth -= 1
    return False


def _record(summary: dict, code: str, index: int, evidence: str) -> None:
    if any(item["code"] == code and item["block_index"] == index for item in summary["observations"]):
        return
    if len(summary["observations"]) >= MAX_OBSERVATIONS:
        summary["truncated"] = True
        return
    summary["observations"].append({
        "code": code, "message": _MESSAGES[code], "block_index": index, "evidence": evidence,
    })


def _limited(summary: dict, index: int, evidence: str) -> None:
    summary["truncated"] = True
    _record(summary, "json_ld_inspection_limited", index, evidence)


def _known_schema_context(context: object, *, mapping: bool = False) -> bool:
    """Recognize common local forms only; never fetch or expand a context."""
    if isinstance(context, str):
        return context in {"https://schema.org", "http://schema.org", "https://schema.org/", "http://schema.org/"} or (
            mapping and context.startswith(("https://schema.org/", "http://schema.org/"))
        )
    if isinstance(context, list):
        return any(_known_schema_context(value, mapping=mapping) for value in context)
    if isinstance(context, dict):
        return any(_known_schema_context(value, mapping=True) for value in context.values())
    return False


def _inspect_document(document: dict | list, summary: dict, index: int, types: set[str]) -> None:
    roots = [document] if isinstance(document, dict) else document
    for root in roots:
        if "@context" not in root:
            _record(summary, "json_ld_missing_context", index, "A root object does not declare @context.")

    stack = list(reversed(roots))
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(reversed(node))
            continue
        if not isinstance(node, dict):
            continue
        if "@context" in node and not _known_schema_context(node["@context"]):
            _record(summary, "json_ld_nonstandard_context", index,
                    "No directly recognized Schema.org context form was found in a declared @context.")

        if "@graph" in node:
            graph = node["@graph"]
            if not isinstance(graph, (dict, list)) or (
                isinstance(graph, list) and any(not isinstance(entry, dict) for entry in graph)
            ):
                _record(summary, "json_ld_invalid_graph", index,
                        "A @graph value is neither an object nor an array containing only objects.")

        # Value objects carry literal datatypes, rather than declared node types.
        if "@value" not in node:
            declared = node.get("@type", [])
            declared = [declared] if isinstance(declared, str) else declared
            if isinstance(declared, list):
                for value in declared:
                    if not isinstance(value, str):
                        continue
                    if len(value) > MAX_TYPE_LENGTH or not _TYPE_LABEL.fullmatch(value):
                        _limited(summary, index, "A declared type label was omitted from the bounded summary.")
                    elif value not in types:
                        if len(types) < MAX_TYPES:
                            types.add(value)
                        else:
                            _limited(summary, index, f"Declared type summary is limited to {MAX_TYPES} distinct labels.")

        # Context mappings and @json literal bodies can contain arbitrary JSON;
        # neither is a data-node subtree for this deliberately shallow inspector.
        stack.extend(value for key, value in reversed(node.items())
                     if key not in {"@context", "@value", "@type"} and isinstance(value, (dict, list)))


def inspect_jsonld(soup: BeautifulSoup) -> dict:
    """Return only block count, declared types, fixed observations and limit state.

    Block indexes are one-based among JSON-LD scripts. ``blocks`` counts all
    matching scripts, including those omitted by limits. Bounds exclude a block
    in full rather than parsing a clipped prefix and inventing a syntax error.
    """
    summary = {"blocks": 0, "types": [], "observations": [], "truncated": False}
    types: set[str] = set()
    total_bytes = 0
    for script in soup.find_all("script"):
        media_type = str(script.get("type", "")).split(";", 1)[0].strip().casefold()
        if media_type != "application/ld+json":
            continue
        summary["blocks"] += 1
        index = summary["blocks"]
        if index > MAX_BLOCKS:
            if index == MAX_BLOCKS + 1:
                _limited(summary, index, f"Only the first {MAX_BLOCKS} JSON-LD blocks were inspected.")
            continue

        source = str(script.string if script.string is not None else script.get_text())
        if len(source) > MAX_BLOCK_BYTES:
            _limited(summary, index, f"This block exceeds the {MAX_BLOCK_BYTES}-byte inspection limit.")
            continue
        size = len(source.encode("utf-8", errors="surrogatepass"))
        if size > MAX_BLOCK_BYTES:
            _limited(summary, index, f"This block exceeds the {MAX_BLOCK_BYTES}-byte inspection limit.")
            continue
        if total_bytes + size > MAX_TOTAL_BYTES:
            _limited(summary, index, f"This block exceeds the remaining {MAX_TOTAL_BYTES}-byte total inspection budget.")
            continue
        total_bytes += size
        if _exceeds_depth(source):
            _limited(summary, index, f"This block exceeds the {MAX_DEPTH}-level JSON nesting limit.")
            continue

        try:
            # Numeric values do not appear in this projection. Avoid Python's
            # integer digit limit and float overflow for valid JSON numbers.
            document = json.loads(source, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                                  parse_int=lambda _value: 0, parse_float=lambda _value: 0)
        except json.JSONDecodeError as error:
            _record(summary, "json_ld_invalid_json", index,
                    f"JSON decoding failed at line {error.lineno}, column {error.colno}.")
            continue
        except _UnsupportedJSON as error:
            code = str(error)
            evidence = ("At least one object repeats a JSON key." if code == "json_ld_duplicate_key" else
                        "A NaN or Infinity constant was found outside a JSON string.")
            _record(summary, code, index, evidence)
            continue
        except RecursionError:
            _limited(summary, index, "JSON decoding exceeded the supported nesting bound.")
            continue

        if not isinstance(document, (dict, list)) or (
            isinstance(document, list) and any(not isinstance(entry, dict) for entry in document)
        ):
            _record(summary, "json_ld_invalid_root", index,
                    "The parsed root is neither an object nor an array containing only objects.")
            continue
        _inspect_document(document, summary, index, types)

    summary["types"] = sorted(types)
    return summary
