"""
AI provider clients + the macro generator + a background queue.

Local-first: Ollama is the default and is given the JSON schema as a native
`format` constraint. Gemini and OpenAI are optional fallbacks that rely on the
prompt + the deterministic code validator (no provider lock-in on structured
output). Whatever the provider returns, `MacroGenerator` only ever emits
schema-valid macros.
"""

from __future__ import annotations

import queue
import threading

from .. import schema
from . import prompts, validator

REQUEST_TIMEOUT_S = 120


def _requests():
    import requests  # lazy: keeps the module importable without the dep
    return requests


# ---------------------------------------------------------------------------
# Provider clients
# ---------------------------------------------------------------------------
class AIClient:
    """Interface: complete(system, user, json_schema=None) -> str."""

    def complete(self, system, user, json_schema=None):  # pragma: no cover
        raise NotImplementedError


class OllamaClient(AIClient):
    def __init__(self, endpoint="http://localhost:11434", model="llama3", **_):
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    def complete(self, system, user, json_schema=None):
        requests = _requests()
        body = {
            "model": self.model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
        }
        if json_schema is not None:
            body["format"] = json_schema
        try:
            r = requests.post(f"{self.endpoint}/api/generate", json=body,
                              timeout=REQUEST_TIMEOUT_S)
            r.raise_for_status()
        except Exception:
            # Some Ollama versions reject a full schema as `format`; retry with
            # the generic JSON mode before giving up.
            if json_schema is not None:
                body["format"] = "json"
                r = requests.post(f"{self.endpoint}/api/generate", json=body,
                                  timeout=REQUEST_TIMEOUT_S)
                r.raise_for_status()
            else:
                raise
        return r.json().get("response", "")


class OpenAIClient(AIClient):
    def __init__(self, endpoint="https://api.openai.com/v1", key="",
                 model="gpt-4o-mini", **_):
        self.endpoint = (endpoint or "https://api.openai.com/v1").rstrip("/")
        self.key = key
        self.model = model

    def complete(self, system, user, json_schema=None):
        requests = _requests()
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
        r = requests.post(
            f"{self.endpoint}/chat/completions", json=body,
            headers={"Authorization": f"Bearer {self.key}"},
            timeout=REQUEST_TIMEOUT_S)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class GeminiClient(AIClient):
    def __init__(self, key="", model="gemini-1.5-flash", **_):
        self.key = key
        self.model = model

    def complete(self, system, user, json_schema=None):
        requests = _requests()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.key}")
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        r = requests.post(url, json=body, timeout=REQUEST_TIMEOUT_S)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def make_client(settings):
    """Build a client from an AppSettings-like object."""
    provider = settings.get("ai_provider", "Ollama (Local)")
    kwargs = {
        "endpoint": settings.get("ai_endpoint", "http://localhost:11434"),
        "key": settings.get("ai_key", ""),
        "model": settings.get("ai_model", "llama3"),
    }
    if "OpenAI" in provider:
        return OpenAIClient(**kwargs)
    if "Gemini" in provider:
        return GeminiClient(**kwargs)
    return OllamaClient(**kwargs)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
class MacroGenerator:
    def __init__(self, client, log=None, max_repair=1):
        self.client = client
        self.log = log or (lambda msg: None)
        self.max_repair = max_repair

    def _complete(self, system, user, json_schema):
        try:
            return self.client.complete(system, user, json_schema)
        except Exception as e:  # noqa: BLE001 - report API/network failures
            self.log(f"AI request failed: {e}\n")
            return None

    def generate_shortcuts(self, context, existing=None, count=4, key_nums=None):
        """Return a list of schema-valid shortcuts for `context` (may be empty)."""
        system = prompts.system_prompt_shortcuts()
        user = prompts.user_prompt_shortcuts(context, existing, count, key_nums)
        raw = self._complete(system, user, schema.shortcuts_schema())
        if raw is None:
            return []

        valid, invalid = validator.process_shortcuts(raw)

        if invalid and self.max_repair > 0:
            bad = [item for item, _ in invalid]
            errors = sorted({e for _, errs in invalid for e in errs})
            self.log(f"Repairing {len(bad)} invalid shortcut(s)...\n")
            repair_user = prompts.repair_user_prompt(bad, errors)
            raw2 = self._complete(system, repair_user, schema.shortcuts_schema())
            if raw2 is not None:
                fixed, _ = validator.process_shortcuts(raw2)
                valid.extend(fixed)

        return self._dedupe(valid)

    def generate_actions(self, description):
        """Return a schema-valid action list for a free-text instruction (or [])."""
        system = prompts.system_prompt_actions()
        user = prompts.user_prompt_actions(description)
        raw = self._complete(system, user, schema.actions_schema())
        if raw is None:
            return []
        actions = validator.process_actions(raw)
        if actions is None and self.max_repair > 0:
            self.log("Macro failed validation; requesting one repair...\n")
            raw2 = self._complete(
                system, prompts.repair_user_prompt(raw if isinstance(raw, str) else [],
                                                   ["macro did not validate"]),
                schema.actions_schema())
            actions = validator.process_actions(raw2) if raw2 is not None else None
        return actions or []

    @staticmethod
    def _dedupe(shortcuts):
        seen = set()
        out = []
        for s in shortcuts:
            key = s.get("description", "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(s)
        return out


# ---------------------------------------------------------------------------
# Background queue for the GUI
# ---------------------------------------------------------------------------
class AIQueueManager:
    """Runs generator calls off the UI thread; delivers results via callback."""

    def __init__(self, generator, marshal=None):
        self.generator = generator
        # marshal(fn, *args): run fn on the UI thread (e.g. Tk's .after). If
        # None, the callback is invoked directly on the worker thread.
        self.marshal = marshal or (lambda fn, *a: fn(*a))
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, method, *args, on_done=None, **kwargs):
        """Queue generator.<method>(*args, **kwargs); call on_done(result) after."""
        self._q.put((method, args, kwargs, on_done))

    def _run(self):
        while not self._stop.is_set():
            try:
                method, args, kwargs, on_done = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                result = getattr(self.generator, method)(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                result = []
                self.generator.log(f"AI task error: {e}\n")
            if on_done:
                self.marshal(on_done, result)

    def stop(self):
        self._stop.set()
