"""
Profile data model.

A profile mirrors the firmware's on-disk JSON (`/profileN.json`):

    {
      "schema_version": 1,
      "profile_name": "Profile1",
      "idle_animation": "none",
      "default_delay": 30,
      "keys": [
        {"id": 1, "name": "...", "led_color": [r,g,b], "actions": [ ... ]},
        ...
      ]
    }

The format is backward compatible: profiles written by the old firmware (no
`schema_version`) load unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import schema
from .config import NUM_KEYS


@dataclass
class KeyMacro:
    id: int
    name: str = ""
    led_color: list = field(default_factory=lambda: [0, 0, 0])
    actions: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        color = d.get("led_color", [0, 0, 0])
        if not (isinstance(color, list) and len(color) == 3):
            color = [0, 0, 0]
        actions = d.get("actions", [])
        if not isinstance(actions, list):
            actions = []
        return cls(
            id=int(d.get("id", 0)),
            name=str(d.get("name", "")),
            led_color=[int(c) for c in color],
            actions=actions,
        )

    def to_dict(self):
        out = {"id": self.id, "actions": self.actions}
        if self.name:
            out["name"] = self.name
        if any(self.led_color):
            out["led_color"] = self.led_color
        return out


@dataclass
class Profile:
    profile_name: str = "Profile1"
    idle_animation: str = "none"
    default_delay: int = 30
    keys: list = field(default_factory=list)            # list[KeyMacro]
    schema_version: int = schema.SCHEMA_VERSION

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            raise ValueError("profile must be a JSON object")
        keys = [KeyMacro.from_dict(k) for k in d.get("keys", [])
                if isinstance(k, dict)]
        anim = str(d.get("idle_animation", "none"))
        if anim not in schema.IDLE_ANIMATIONS:
            anim = "none"
        return cls(
            profile_name=str(d.get("profile_name", "Profile")),
            idle_animation=anim,
            default_delay=int(d.get("default_delay", 30) or 30),
            keys=keys,
            schema_version=int(d.get("schema_version", schema.SCHEMA_VERSION)),
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "profile_name": self.profile_name,
            "idle_animation": self.idle_animation,
            "default_delay": self.default_delay,
            "keys": [k.to_dict() for k in self.keys],
        }

    def key(self, key_id):
        """Return the KeyMacro with this id, creating an empty one if absent."""
        for k in self.keys:
            if k.id == key_id:
                return k
        km = KeyMacro(id=key_id)
        self.keys.append(km)
        return km

    def validate(self):
        """Return (ok, errors) — validates every key's actions against the schema."""
        errors = []
        if not 1 <= self.default_delay <= 10000:
            errors.append(f"default_delay {self.default_delay} out of range")
        for k in self.keys:
            if not 1 <= k.id <= NUM_KEYS:
                errors.append(f"key id {k.id} out of range 1..{NUM_KEYS}")
            ok, errs = schema.validate_actions(k.actions)
            if not ok:
                errors.extend(f"key {k.id}: {e}" for e in errs)
        return (not errors, errors)


def new_default_profile(index):
    """A blank profile matching the firmware's `ensureDefaultProfile`."""
    return Profile(profile_name=f"Profile{index}",
                   idle_animation="none", default_delay=30, keys=[])
