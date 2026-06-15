# Bundled firmware

`macropad.merged.bin` is the full-flash image the Studio app flashes to a board.

## Export it (per firmware version)

Arduino IDE: **Sketch → Export Compiled Binary**, then take the
`*.ino.merged.bin` from the build output. Or with arduino-cli:

```sh
arduino-cli compile --fqbn esp32:esp32:lolin_s2_pico \
  --output-dir build_out ESP32-Macro-pad
cp build_out/ESP32-Macro-pad.ino.merged.bin firmware/macropad.merged.bin
```

Then update `manifest.json`'s `version` to match `config.h`'s `FW_VERSION`,
and commit both. Only commit an image you have flashed and verified.
