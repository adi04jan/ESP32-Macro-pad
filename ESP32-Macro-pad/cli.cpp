#include "cli.h"
#include "config.h"
#include "storage.h"
#include "profiles.h"
#include <ArduinoJson.h>
#include <LittleFS.h>

static String serialBuffer = "";
static bool serialRecording = false;
static String serialTargetFile = "";
static unsigned long uploadLastActivity = 0;

static void printPrompt() { Serial.print("macropad:$ "); }

static void cmdLs() {
  File root = LittleFS.open("/");
  File f = root.openNextFile();
  while (f) {
    Serial.printf("%s\t%u\n", f.name(), (unsigned)f.size());
    f = root.openNextFile();
  }
}

static void cmdSetkey(const String &arg) {
  int sp = arg.indexOf(' ');
  if (sp == -1) { Serial.println("setkey <id> <json-actions>"); return; }
  int keyId = arg.substring(0, sp).toInt();
  String jsonArr = arg.substring(sp + 1);

  JsonDocument tmp;
  if (deserializeJson(tmp, jsonArr)) { Serial.println("setkey JSON parse failed"); return; }
  if (!tmp.is<JsonArray>()) { Serial.println("setkey expects a JSON array"); return; }

  if (!profileDoc["keys"].is<JsonArray>()) profileDoc["keys"].to<JsonArray>();
  JsonArray keys = profileDoc["keys"].as<JsonArray>();
  for (size_t i = 0; i < keys.size(); i++) {
    if ((keys[i]["id"] | 0) == keyId) { keys.remove(i); break; }
  }
  JsonObject ko = keys.add<JsonObject>();
  ko["id"] = keyId;
  ko["actions"] = tmp.as<JsonArray>();   // deep-copied into profileDoc
  Serial.printf("Key %d updated in RAM\n", keyId);
}

static void cliHandleLine(const String &line) {
  String s = line; s.trim();
  if (s.length() == 0) { printPrompt(); return; }
  int sp = s.indexOf(' ');
  String cmd = (sp == -1) ? s : s.substring(0, sp);
  cmd.toLowerCase();
  String arg = (sp == -1) ? "" : s.substring(sp + 1);
  arg.trim();

  if (cmd == "help") {
    Serial.println("help ls cat <f> setprofile <n> setkey <id> <json> status fsinfo reboot");
  } else if (cmd == "fsinfo") {
    Serial.printf("FS_INFO:%u,%u\n", (unsigned)LittleFS.totalBytes(), (unsigned)LittleFS.usedBytes());
  } else if (cmd == "ls") {
    cmdLs();
  } else if (cmd == "cat") {
    if (arg.length() == 0) Serial.println("cat <file>");
    else Serial.println(readFileStr(arg.c_str()));
  } else if (cmd == "setprofile") {
    int id = arg.toInt();
    if (id < 1 || id > NUM_PROFILES) Serial.println("invalid");
    else { loadProfile(id); Serial.printf("profile %d\n", id); }
  } else if (cmd == "setkey") {
    cmdSetkey(arg);
  } else if (cmd == "status") {
    Serial.printf("Profile:%d loaded:%d idle:%d ver:%s\n",
                  currentProfile, profileLoaded, idleAnimation, FW_VERSION);
  } else if (cmd == "reboot") {
    Serial.println("rebooting"); delay(200); ESP.restart();
  } else {
    Serial.println("unknown");
  }
  printPrompt();
}

static void finishUpload() {
  // Validate JSON before committing it to flash.
  JsonDocument check;
  DeserializationError err = deserializeJson(check, serialBuffer);
  if (err) {
    Serial.printf("Upload rejected: invalid JSON (%s)\n", err.c_str());
  } else {
    bool ok = atomicWrite(serialTargetFile.c_str(),
                          (const uint8_t *)serialBuffer.c_str(), serialBuffer.length());
    Serial.printf("Wrote %s -> %s\n", serialTargetFile.c_str(), ok ? "OK" : "FAILED");
  }
  serialRecording = false;
  serialTargetFile = "";
  serialBuffer = "";
  printPrompt();
}

void cliBegin() {
  serialRecording = false;
  serialBuffer = "";
  printPrompt();
}

void handleSerialInput() {
  // Abort a stalled upload so a dropped connection can't wedge the device.
  if (serialRecording && millis() - uploadLastActivity > SERIAL_UPLOAD_TIMEOUT_MS) {
    Serial.println("Upload timed out; discarded.");
    serialRecording = false;
    serialBuffer = "";
    serialTargetFile = "";
    printPrompt();
  }

  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (!serialRecording) {
      if (line.startsWith("###BEGIN###")) {
        String target = line.substring(strlen("###BEGIN###"));
        target.trim();
        if (target.length() == 0) { Serial.println("Usage: ###BEGIN### filename.json"); continue; }
        serialRecording = true;
        serialBuffer = "";
        serialTargetFile = "/" + target;
        uploadLastActivity = millis();
        Serial.printf("Recording JSON to %s\n", serialTargetFile.c_str());
      } else if (line.length() > 0) {
        cliHandleLine(line);
      } else {
        printPrompt();
      }
    } else {
      uploadLastActivity = millis();
      if (line == "###END###") {
        finishUpload();
      } else if (serialBuffer.length() + line.length() + 1 > SERIAL_UPLOAD_MAX) {
        Serial.println("Upload too large; discarded.");
        serialRecording = false;
        serialBuffer = "";
        serialTargetFile = "";
        printPrompt();
      } else {
        serialBuffer += line;
        serialBuffer += "\n";
      }
    }
  }
}
