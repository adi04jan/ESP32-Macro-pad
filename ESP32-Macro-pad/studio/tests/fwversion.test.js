"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { parseStatusVersion, cmpSemver, isOutdated } = require("../services/fwversion");

test("parseStatusVersion pulls ver: from a status line", () => {
  assert.equal(parseStatusVersion("Profile:1 loaded:1 idle:2 mode:rainbow ver:2.0.0"), "2.0.0");
});
test("parseStatusVersion handles multiline + CRLF", () => {
  assert.equal(parseStatusVersion("noise\r\nProfile:1 loaded:1 idle:0 mode:none ver:2.1.0\r\n"), "2.1.0");
});
test("parseStatusVersion returns null when absent", () => {
  assert.equal(parseStatusVersion("no version here"), null);
});
test("cmpSemver orders versions", () => {
  assert.equal(cmpSemver("2.0.0", "2.1.0"), -1);
  assert.equal(cmpSemver("2.1.0", "2.1.0"), 0);
  assert.equal(cmpSemver("2.2.0", "2.1.0"), 1);
  assert.equal(cmpSemver("2.1.0", "2.1"), 1);
});
test("isOutdated true only when device < bundled", () => {
  assert.equal(isOutdated("2.0.0", "2.1.0"), true);
  assert.equal(isOutdated("2.1.0", "2.1.0"), false);
  assert.equal(isOutdated("2.2.0", "2.1.0"), false);
  assert.equal(isOutdated(null, "2.1.0"), false);
});
