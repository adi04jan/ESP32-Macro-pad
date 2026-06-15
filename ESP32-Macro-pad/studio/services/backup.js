/* Local PC backups of device profiles.
 * Auto: a timestamped snapshot before every device write, pruned to the last N
 *       per profile. Manual: a full snapshot of all 3 profiles on demand.
 * Everything lands under device_backups/ (gitignored — may hold secrets). */
"use strict";

const fs = require("fs");
const path = require("path");

// Writable base dir (dev: project root; packaged: userData — set by main.js).
let BASE_DIR = path.resolve(__dirname, "..", "..");
let BACKUP_ROOT = path.join(BASE_DIR, "device_backups");
function configure(opts = {}) {
  if (opts.dataDir) { BASE_DIR = opts.dataDir; BACKUP_ROOT = path.join(BASE_DIR, "device_backups"); }
}
const AUTO_KEEP = 20;   // snapshots retained per profile

function stamp() { return new Date().toISOString().replace(/[:.]/g, "-"); }
function ensure(dir) { fs.mkdirSync(dir, { recursive: true }); }

// One snapshot of a single profile, taken before a device write. Pruned to AUTO_KEEP.
function autoBackup(slot, profileObj) {
  try {
    const dir = path.join(BACKUP_ROOT, "auto", `profile${slot}`);
    ensure(dir);
    fs.writeFileSync(path.join(dir, `${stamp()}.json`), JSON.stringify(profileObj, null, 2));
    const files = fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
    while (files.length > AUTO_KEEP) {
      const old = files.shift();
      try { fs.unlinkSync(path.join(dir, old)); } catch (_) {}
    }
    return { ok: true };
  } catch (e) { return { ok: false, error: e.message }; }
}

// All provided profiles into one timestamped folder. profiles = { "1": obj, ... }.
function manualBackupAll(profiles) {
  try {
    const dir = path.join(BACKUP_ROOT, "manual", stamp());
    ensure(dir);
    let count = 0;
    for (const slot of Object.keys(profiles)) {
      if (!profiles[slot]) continue;
      fs.writeFileSync(path.join(dir, `profile${slot}.json`), JSON.stringify(profiles[slot], null, 2));
      count++;
    }
    return { ok: true, path: dir, count };
  } catch (e) { return { ok: false, error: e.message }; }
}

module.exports = { configure, autoBackup, manualBackupAll };
