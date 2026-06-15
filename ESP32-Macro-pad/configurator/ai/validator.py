"""
Code-based validation of AI output.

Replaces the old "ask a second LLM to validate" approach with deterministic,
schema-driven checks: parse leniently, repair programmatically, validate against
the canonical schema, and partition into valid / still-broken. The still-broken
set (with concrete error messages) is what the generator feeds back to the model
for a single targeted repair pass.
"""

from __future__ import annotations

import json
import re

from .. import schema

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_lenient(text):
    """Parse an array/object out of a possibly-noisy LLM response.

    Strips markdown fences and, failing a direct parse, extracts the first
    balanced [...] or {...} span. Returns the parsed value or None.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        return text  # already-parsed (e.g. provider returned structured JSON)

    cleaned = text.strip()
    cleaned = _FENCE_RE.sub("", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    span = _first_json_span(cleaned)
    if span is not None:
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            return None
    return None


def _first_json_span(text):
    """Return the substring of the first balanced [..] or {..}, or None."""
    start = None
    opener = None
    for i, ch in enumerate(text):
        if ch in "[{":
            start = i
            opener = ch
            break
    if start is None:
        return None
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _as_list(parsed):
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def partition_shortcuts(items):
    """Repair then split into (valid, invalid_with_errors).

    invalid_with_errors is a list of (repaired_item, [error strings]).
    """
    valid, invalid = [], []
    for item in _as_list(items):
        repaired = schema.repair_shortcuts([item])
        if not repaired:
            invalid.append((item, ["no recoverable actions"]))
            continue
        candidate = repaired[0]
        ok, errors = schema.validate_shortcuts([candidate])
        if ok:
            valid.append(candidate)
        else:
            invalid.append((candidate, errors))
    return valid, invalid


def process_shortcuts(raw_text):
    """Parse + repair + validate a raw shortcuts response.

    Returns (valid_shortcuts, invalid_with_errors). Never raises on bad input.
    """
    parsed = parse_json_lenient(raw_text)
    if parsed is None:
        return [], [(raw_text, ["response was not parseable JSON"])]
    return partition_shortcuts(parsed)


def process_actions(raw_text):
    """Parse + repair + validate a raw single-macro (action array) response.

    Returns (valid_actions_or_None). The whole macro is kept only if it has at
    least one valid action after repair and passes schema validation.
    """
    parsed = parse_json_lenient(raw_text)
    if parsed is None:
        return None
    actions = parsed if isinstance(parsed, list) else parsed.get("actions")
    repaired = schema.repair_actions(actions or [])
    if repaired and schema.is_valid_actions(repaired):
        return repaired
    return None
