# Macropad v2.1.1

A reliability + recovery release on top of v2.1: the in-app **firmware flasher now
works hands-free**, a blank-window regression is fixed, and you can **restore
profiles from local backups**.

## New in 2.1.1

- ⚡ **In-app firmware flasher (now hands-free).** Flash or update the board from
  the Device tab — no BOOT button. It reboots the board via a 1200-baud touch,
  auto-detects the bootloader port the native-USB S2 re-enumerates to, and writes
  with the bundled `esptool`. Offers **recover** (unrecognized board),
  **update** (outdated firmware), and on-demand **re-flash**.
- ♻️ **Restore backups.** Device tab → **Restore**: load any local snapshot into
  the editor, or **Restore all** to write the latest backup of every profile —
  keys, idle **LED pattern**, and per-key colors — straight to the device.
- 🐛 **Fixed blank window** on launch (a sandboxed-preload regression in v2.1.0
  that left the app blank).

## From v2.1

- 🔄 Auto-update from GitHub Releases
- ⚙️ Finished Settings: theme, widget stay-on-top / snap / auto-hide, export-all,
  guarded factory reset, launch-at-startup
- 💡 LED-brightness slider, AI request Cancel, clearer serial error handling
- 🔧 Firmware: configurable brightness, per-key debounce, safe-boot + watchdog
  (firmware `FW_VERSION` 2.1.0, verified on hardware)

## Install

Download **`Macropad-Studio-2.1.1-setup.exe`** below (existing 2.1.0+ installs
auto-update from here). Flash firmware from the app's Device tab, or via the
Arduino IDE.

> Builds are unsigned, so Windows SmartScreen may warn on first install.

**Developer:** Aditya Biswas — [GitHub](https://github.com/adi04jan) ·
[LinkedIn](https://www.linkedin.com/in/aditya-biswas-6409b78b/)

**Full changelog:** https://github.com/adi04jan/ESP32-Macro-pad/commits/v2.1.1
