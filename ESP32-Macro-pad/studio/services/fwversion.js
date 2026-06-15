/* Pure firmware-version helpers: parse the device's `status` line and compare
 * semver strings. No I/O — unit-tested in tests/fwversion.test.js. */
"use strict";

function parseStatusVersion(text) {
  if (!text) return null;
  const m = String(text).match(/ver:\s*([0-9]+(?:\.[0-9]+){1,2})/i);
  return m ? m[1] : null;
}

function _parts(v) { return String(v).split(".").map((n) => parseInt(n, 10) || 0); }

// -1 if a<b, 0 if equal, 1 if a>b (incomplete versions < 3 parts considered less).
function cmpSemver(a, b) {
  const pa = _parts(a), pb = _parts(b);
  // If one version has fewer than 3 parts, it's incomplete and less.
  if (pa.length < 3 && pb.length === 3) return -1;
  if (pa.length === 3 && pb.length < 3) return 1;
  // Compare parts.
  for (let i = 0; i < 3; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d > 0 ? 1 : -1;
  }
  return 0;
}

function isOutdated(deviceVer, bundledVer) {
  if (!deviceVer || !bundledVer) return false;
  return cmpSemver(deviceVer, bundledVer) < 0;
}

module.exports = { parseStatusVersion, cmpSemver, isOutdated };
