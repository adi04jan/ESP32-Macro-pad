"""
Template manager: per-context shortcut libraries (defaults + user/AI custom).

Improvements over the old TemplatesManager:
  * Deduplicates by description AND normalized actions (the old code only
    checked description, so two different macros with the same name collided,
    and identical macros with different names both slipped through).
  * Validates every shortcut against the canonical schema on load and on add,
    so the library can never serve the firmware a macro it can't run.
"""

from __future__ import annotations

import json
import os

from . import schema


def _normalize_actions(actions):
    """A stable, hashable signature of an action list for dedup."""
    return json.dumps(schema.repair_actions(actions), sort_keys=True)


class TemplatesManager:
    def __init__(self, custom_file="macropad_templates.json",
                 default_file="macropad_default_templates.json"):
        self.custom_file = custom_file
        self.default_file = default_file
        self.custom_templates = {}
        self.default_templates = {}
        self.load()

    def load(self):
        self.default_templates = self._load_file(self.default_file)
        self.custom_templates = self._load_file(self.custom_file)

    @staticmethod
    def _load_file(path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        # Keep only schema-valid shortcuts (repaired), per context.
        cleaned = {}
        for ctx, items in data.items():
            if not isinstance(items, list):
                continue
            good = []
            for s in items:
                if not isinstance(s, dict):
                    continue
                actions = schema.repair_actions(s.get("actions", []))
                if actions and schema.is_valid_actions(actions):
                    entry = {"description": s.get("description", "Macro"),
                             "actions": actions}
                    if "key_num" in s:
                        entry["key_num"] = s["key_num"]
                    good.append(entry)
            if good:
                cleaned[ctx.lower()] = good
        return cleaned

    def save(self):
        try:
            with open(self.custom_file, "w", encoding="utf-8") as f:
                json.dump(self.custom_templates, f, indent=4)
        except OSError as e:
            print(f"[templates] save failed: {e}")

    def get_context_shortcuts(self, context):
        """Custom first, then defaults; deduped by (description, actions).

        Falls back to a fuzzy substring match if there's no exact context hit.
        """
        ctx = context.lower()
        combined = []
        seen_desc = set()
        seen_sig = set()

        def add(items):
            for s in items:
                desc = s.get("description", "").lower()
                sig = _normalize_actions(s.get("actions", []))
                if desc in seen_desc or sig in seen_sig:
                    continue
                seen_desc.add(desc)
                seen_sig.add(sig)
                combined.append(s)

        add(self.custom_templates.get(ctx, []))
        add(self.default_templates.get(ctx, []))

        if not combined:
            for source in (self.custom_templates, self.default_templates):
                for key in source:
                    if key in ctx or ctx in key:
                        add(source[key])
                        break
        return combined

    def add_shortcuts(self, context, new_shortcuts):
        """Add schema-valid, non-duplicate shortcuts. Returns count added."""
        ctx = context.lower()
        bucket = self.custom_templates.setdefault(ctx, [])
        existing = self.get_context_shortcuts(ctx)
        seen_desc = {s.get("description", "").lower() for s in existing}
        seen_sig = {_normalize_actions(s.get("actions", [])) for s in existing}

        added = 0
        for s in new_shortcuts:
            actions = schema.repair_actions(s.get("actions", []))
            if not actions or not schema.is_valid_actions(actions):
                continue
            desc = s.get("description", "Macro")
            sig = _normalize_actions(actions)
            if desc.lower() in seen_desc or sig in seen_sig:
                continue
            entry = {"description": desc, "actions": actions}
            if "key_num" in s:
                entry["key_num"] = s["key_num"]
            bucket.append(entry)
            seen_desc.add(desc.lower())
            seen_sig.add(sig)
            added += 1

        if added:
            self.save()
        return added
