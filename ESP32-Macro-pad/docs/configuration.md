# Configuration

All macros and settings are plain JSON. The **canonical action schema** lives in
[`configurator/schema.py`](../configurator/schema.py) and is mirrored, byte-for-
behaviour, in [`studio/services/schema.js`](../studio/services/schema.js) and the
firmware's `executeAction`. Anything that produces or consumes macros (the Studio
editor, the AI pipeline, the on-disk profiles) validates against it, so a macro
that validates here is guaranteed to run on the device.

`SCHEMA_VERSION = 1`.

## Files

| File | Tracked? | Purpose |
|------|----------|---------|
| [`data/profile1.json`](../data/profile1.json) … `profile3.json` | yes | Example/seed profiles. |
| [`macropad_default_templates.json`](../macropad_default_templates.json) | yes | Default per-context macro templates shipped with Studio (`extraResources`). |
| `macropad_templates.json` | yes | The user's edited context templates. |
| `macropad_settings.example.json` | yes | Sanitized template for the settings file below. |
| `macropad_settings.json` | **no (gitignored)** | Local user settings: active COM port, AI provider endpoint and **API key**. Never commit it. |
| `macropad_usage.json` | no (gitignored) | Runtime key-usage stats. |

> **Secrets:** `macropad_settings.json` can contain an AI provider API key, and
> `device_backups/` profile dumps can contain password-typing macros. Both are
> git-ignored by design. Copy `macropad_settings.example.json` →
> `macropad_settings.json` and fill in your own values.

## Profile format

```jsonc
{
  "profile_name": "Git Power Workflow",
  "idle_animation": "rainbow",        // see idle animations below
  "default_delay": 20,                 // ms between actions
  "keys": [
    {
      "id": 1,                         // logical key number 1–12
      "name": "git status",
      "led_color": [0, 120, 255],      // resting RGB for this key
      "actions": [
        { "type": "text", "value": "git status" },
        { "type": "key",  "value": "ENTER" }
      ]
    }
    // … up to 12 keys
  ]
}
```

## Action types

Every action is an object with a `"type"` and type-specific fields. There are
16 types:

| Type | Fields | Notes |
|------|--------|-------|
| `comment` | `value?` | No-op; documents the sequence. |
| `delay` | `ms` | Pause (≥0 ms). |
| `key` | `value` | A single named key or printable character. |
| `keycombo` | `keys[]` | Chord of modifiers + keys pressed together. |
| `text` | `value` | Type a string (≤4096 chars). |
| `multiline` | `value` | Like `text`, preserves newlines. |
| `hold` | `key` | Press and hold a key/modifier. |
| `release` | — | Release everything held. |
| `repeat` | `count`, `actions[]` | Run nested actions `count` times (1–50, nesting depth ≤4). |
| `media` | `value` | Media key (see below). |
| `mouse_move` | `x`, `y`, `wheel?` | Relative move; each axis −127…127. |
| `mouse_click` | `button` | `LEFT` / `RIGHT` / `MIDDLE`. |
| `led` | `color` | Set this key's LED to an `[r,g,b]` colour. |
| `led_anim` | `value`, `color?` | `flash` or `breathe` animation. |
| `profile` | `value` | Switch to profile 1–3. |
| `telephony` | `value` | `MIC_MUTE` / `ANSWER` / `DECLINE`. |

### Enums

- **Keys:** `A`–`Z`, `0`–`9`, `F1`–`F12`, and named keys: `ENTER`, `ESC`,
  `BACKSPACE`, `TAB`, `SPACE`, `MINUS`, `EQUAL`, `LEFT_BRACE`, `RIGHT_BRACE`,
  `BACKSLASH`, `SEMICOLON`, `QUOTE`, `TILDE`, `COMMA`, `DOT`, `SLASH`,
  `CAPS_LOCK`, `INSERT`, `HOME`, `PAGEUP`, `DELETE`, `END`, `PAGEDOWN`, and the
  four arrows (`UP_ARROW`, `DOWN_ARROW`, `LEFT_ARROW`, `RIGHT_ARROW`). A key may
  also be any single printable character.
- **Modifiers** (combo/hold only): `LEFT_CTRL`, `LEFT_SHIFT`, `LEFT_ALT`,
  `LEFT_GUI`, and their `RIGHT_*` variants.
- **Media:** `PLAY_PAUSE`, `STOP`, `NEXT`, `PREVIOUS`, `MUTE`, `VOLUME_UP`,
  `VOLUME_DOWN`.
- **Idle animations:** `none`, `breathe`, `rainbow`, `flash`, `wave`, `comet`,
  `twinkle`, `ripple`.

Common aliases (`CTRL`→`LEFT_CTRL`, `CMD`/`WIN`→`LEFT_GUI`, `ESCAPE`→`ESC`,
`UP`→`UP_ARROW`, …) are normalized automatically — see `ALIASES` in
[`schema.py`](../configurator/schema.py).

## Validation & repair

The schema module exposes (Python and JS ports both):

- `validate_actions(actions)` / `validate_shortcuts(items)` → `(ok, errors)`.
- `repair_actions(actions)` → best-effort normalization that applies aliases,
  clamps numbers to firmware limits, and **drops the unrecoverable** rather than
  emitting anything the device can't run.

AI-generated macros are parsed → repaired → validated before they're ever
written to a profile or sent to the device.
