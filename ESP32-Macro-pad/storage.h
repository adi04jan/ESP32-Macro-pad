/* LittleFS helpers: read, atomic write with backup + pruning. */
#pragma once
#include <Arduino.h>

bool   fsBegin();
String readFileStr(const char *path);
bool   writeFileStr(const char *path, const String &content);
// Write to a temp file, back up the old version (pruned), then atomically rename.
bool   atomicWrite(const char *targetPath, const uint8_t *data, size_t len);
