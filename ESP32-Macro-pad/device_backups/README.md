# Device firmware backups

Full flash dumps of the connected macropad (read-only `esptool read_flash`).

| File | Chip | MAC | Flash | Date |
|------|------|-----|-------|------|
| `macropad_full_4MB_84f703f52c52_20260608.bin` | ESP32-S2FNR2 | 84:f7:03:f5:2c:52 | 4 MB | 2026-06-08 |

This is a complete image (offset `0x0`–`0x400000`): bootloader, partition table,
app, and the LittleFS data partition — i.e. it includes the profiles that were on
the device at backup time. SHA-256 is in the `.bin.sha256` sidecar.

## Restoring this exact image

The board uses **native USB (USB-OTG)**, so esptool's auto-reset can't follow the
port across the firmware↔bootloader switch. Put the board in download mode first
(it re-enumerates as VID:PID `303A:0002`), then write the full image:

```sh
ESPTOOL="$HOME/AppData/Local/Arduino15/packages/esp32/tools/esptool_py/5.0.dev1/esptool.exe"
# 1) Kick into bootloader (errors out but leaves the device in download mode):
"$ESPTOOL" --port <FIRMWARE_PORT> --chip esp32s2 --before default_reset flash-id
# 2) Find the new 303A:0002 port, then write the whole image and reboot:
"$ESPTOOL" --port <BOOTLOADER_PORT> --chip esp32s2 --baud 921600 \
    --before no_reset --after hard_reset write_flash 0x0 \
    macropad_full_4MB_84f703f52c52_20260608.bin
```

(If auto-reset won't enter download mode, hold BOOT/GPIO0 and tap RESET manually.)

> Note: restoring the full image also restores the *old* profiles/filesystem from
> backup time. To keep current profiles, reflash only the app instead of `0x0`.
