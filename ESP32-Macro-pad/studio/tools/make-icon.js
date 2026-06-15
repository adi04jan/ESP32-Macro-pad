/* Packs the icon PNGs (produced by gen-icon.ps1) into a multi-resolution
 * assets/icon.ico for electron-builder and the runtime window icon.
 *   node tools/make-icon.js */
"use strict";
const fs = require("fs");
const path = require("path");
const _ptm = require("png-to-ico");
const pngToIco = _ptm.default || _ptm;

const A = path.join(__dirname, "..", "assets");
const sizes = [256, 128, 64, 48, 32, 16];
const pngs = sizes.map((s) => path.join(A, `icon-${s}.png`)).filter(fs.existsSync);

pngToIco(pngs)
  .then((buf) => {
    fs.writeFileSync(path.join(A, "icon.ico"), buf);
    // tidy the intermediate per-size PNGs; keep icon.png, tray.png, icon.ico.
    for (const s of sizes) {
      const f = path.join(A, `icon-${s}.png`);
      if (fs.existsSync(f)) fs.unlinkSync(f);
    }
    console.log(`wrote assets/icon.ico (${buf.length} bytes) from ${pngs.length} sizes`);
  })
  .catch((err) => { console.error(err); process.exit(1); });
