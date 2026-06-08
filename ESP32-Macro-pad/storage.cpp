#include "storage.h"
#include "config.h"
#include <LittleFS.h>

bool fsBegin() {
  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS mount failed/format");
    return false;
  }
  if (!LittleFS.exists("/backups")) LittleFS.mkdir("/backups");
  return true;
}

String readFileStr(const char *path) {
  File f = LittleFS.open(path, "r");
  if (!f) return String();
  String s;
  s.reserve(f.size() + 1);
  while (f.available()) s += (char)f.read();
  f.close();
  return s;
}

bool writeFileStr(const char *path, const String &content) {
  File f = LittleFS.open(path, "w");
  if (!f) return false;
  size_t w = f.print(content);
  f.close();
  return w == content.length();
}

// Keep only the most recent MAX_BACKUPS_PER_FILE backups for a given base name.
static void pruneBackups(const String &baseName) {
  File dir = LittleFS.open("/backups");
  if (!dir) return;
  // Collect matching backup names.
  String names[16];
  int n = 0;
  File f = dir.openNextFile();
  while (f && n < 16) {
    String nm = String(f.name());
    if (nm.startsWith(baseName + "-")) names[n++] = nm;
    f = dir.openNextFile();
  }
  dir.close();
  // Names embed millis(); lexical sort approximates chronological for same width.
  for (int i = 0; i < n - 1; i++)
    for (int j = i + 1; j < n; j++)
      if (names[j] < names[i]) { String t = names[i]; names[i] = names[j]; names[j] = t; }
  for (int i = 0; i < n - MAX_BACKUPS_PER_FILE; i++)
    LittleFS.remove((String("/backups/") + names[i]).c_str());
}

bool atomicWrite(const char *targetPath, const uint8_t *data, size_t len) {
  String tmp = String(targetPath) + ".tmp";
  File f = LittleFS.open(tmp.c_str(), "w");
  if (!f) return false;
  size_t w = f.write(data, len);
  f.close();
  if (w != len) {
    LittleFS.remove(tmp.c_str());
    return false;
  }

  // Back up the existing file before replacing it.
  if (LittleFS.exists(targetPath)) {
    String base = String(targetPath + 1);  // strip leading '/'
    base.replace("/", "_");
    String bk = String("/backups/") + base + "-" + String(millis()) + ".bak";
    File oldF = LittleFS.open(targetPath, "r");
    File bkF = LittleFS.open(bk.c_str(), "w");
    if (oldF && bkF) {
      while (oldF.available()) bkF.write(oldF.read());
    }
    if (oldF) oldF.close();
    if (bkF) bkF.close();
    pruneBackups(base);
  }

  LittleFS.remove(targetPath);
  return LittleFS.rename(tmp.c_str(), targetPath);
}
