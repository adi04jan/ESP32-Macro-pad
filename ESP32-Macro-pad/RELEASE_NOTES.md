# Macropad v2.1.0

A polish + reliability release: Macropad Studio now updates itself, finishes the
Settings experience, and the firmware gains brightness/debounce controls plus
safer booting.

## Flagship: auto-update

- **Macropad Studio now updates itself** from GitHub Releases. New versions are
  detected on launch, downloaded in the background, and installed on restart
  (topbar "Update ready · Restart" chip + Settings → About → Check for updates).

## Studio

- **Finished Settings:** light/dark **theme** switch, working floating-widget
  controls — **Stay on top**, **Snap to edges**, **Auto-hide when idle** —
  **Export all profiles** to one file, guarded **Factory reset**, and
  **Launch at startup**.
- **LED brightness** slider on the Device tab (per-profile, pushed live).
- **AI reliability:** a **Cancel** button for in-flight generations and clearer
  timeout handling.
- **Serial reliability:** clear warnings when a device operation times out or the
  connection drops mid-transfer.

## Firmware (v2.1.0 — reflash to use)

- **Configurable LED brightness** — `setbrightness <0-255>` CLI + per-profile
  `brightness`, applied on load.
- **Per-key debounce** — optional `debounce` field per key in a profile.
- **Safe-boot** — a corrupt profile is rewritten from default and retried instead
  of soft-bricking the device.
- **Watchdog** — reboots the device if the main loop ever stalls
  (set `ENABLE_WATCHDOG 0` in `config.h` to disable).
- **Schema-version migration hook** so future profile-format changes stay
  backward compatible.

## Install

1. Download **`Macropad Studio-2.1.0-setup.exe`** below (existing installs will
   auto-update from here on).
2. To use the new firmware features, reflash the device with the v2.1.0 firmware
   (Arduino IDE — see [docs/firmware.md](ESP32-Macro-pad/docs/firmware.md)).

## Notes

- Builds are unsigned, so Windows SmartScreen may warn on first install.

**Developer:** Aditya Biswas — [GitHub](https://github.com/adi04jan) ·
[LinkedIn](https://www.linkedin.com/in/aditya-biswas-6409b78b/)

**Full changelog:** https://github.com/adi04jan/ESP32-Macro-pad/commits/v2.1.0
