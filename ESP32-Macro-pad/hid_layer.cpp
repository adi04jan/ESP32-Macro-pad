#include "hid_layer.h"
#include "hid_maps.h"
#include "config.h"

USBHIDKeyboard Keyboard;
USBHIDMouse Mouse;
USBHIDConsumerControl Consumer;

// ---------------------------------------------------------------------------
// Telephony HID device (custom report descriptor with a known report ID).
// ---------------------------------------------------------------------------
#if ENABLE_TELEPHONY_HID
#include "USBHID.h"

// Telephony page collection reporting three momentary controls as input bits:
//   bit0 = Hook Switch (answer), bit1 = Phone Mute, bit2 = Drop (decline).
static const uint8_t telephony_report_desc[] = {
  0x05, 0x0B,                    // Usage Page (Telephony)
  0x09, 0x05,                    // Usage (Headset)
  0xA1, 0x01,                    // Collection (Application)
  0x85, TELEPHONY_REPORT_ID,     //   Report ID
  0x05, 0x0B,                    //   Usage Page (Telephony)
  0x09, 0x20,                    //   Usage (Hook Switch)
  0x09, 0x2F,                    //   Usage (Phone Mute)
  0x09, 0x26,                    //   Usage (Drop)
  0x15, 0x00,                    //   Logical Minimum (0)
  0x25, 0x01,                    //   Logical Maximum (1)
  0x75, 0x01,                    //   Report Size (1)
  0x95, 0x03,                    //   Report Count (3)
  0x81, 0x02,                    //   Input (Data,Var,Abs)
  0x75, 0x01,                    //   Report Size (1)
  0x95, 0x05,                    //   Report Count (5)  -> pad to a byte
  0x81, 0x03,                    //   Input (Const,Var,Abs)
  0xC0                           // End Collection
};

class TelephonyHID : public USBHIDDevice {
 public:
  TelephonyHID() {
    static bool registered = false;
    if (!registered) {
      registered = true;
      hid.addDevice(this, sizeof(telephony_report_desc));
    }
  }
  void begin() { hid.begin(); }
  uint16_t _onGetDescriptor(uint8_t *dst) override {
    memcpy(dst, telephony_report_desc, sizeof(telephony_report_desc));
    return sizeof(telephony_report_desc);
  }
  void sendBits(uint8_t bits) {
    hid.SendReport(TELEPHONY_REPORT_ID, &bits, 1);
  }
 private:
  USBHID hid;
};

static TelephonyHID telephony;
#endif  // ENABLE_TELEPHONY_HID

// ---------------------------------------------------------------------------
void hidBegin() {
  Keyboard.begin();
  Mouse.begin();
  Consumer.begin();
#if ENABLE_TELEPHONY_HID
  telephony.begin();
#endif
}

void hidPressKey(const String &name) {
  if (name.length() == 0) return;
  uint8_t hid = keyNameToHid(name);
  if (!hid) {
    if (name.length() == 1) Keyboard.print(name);   // printable char
    else Serial.printf("Unknown key '%s'\n", name.c_str());
    return;
  }
  Keyboard.pressRaw(hid);
  delay(12);
  Keyboard.releaseRaw(hid);
}

void hidSendKeyCombo(JsonArrayConst keys) {
  for (JsonVariantConst v : keys) {
    String k = v.as<const char *>() ? String(v.as<const char *>()) : String();
    uint8_t m = modifierNameToCode(k);
    if (m) Keyboard.press(m);
  }
  for (JsonVariantConst v : keys) {
    String k = v.as<const char *>() ? String(v.as<const char *>()) : String();
    if (modifierNameToCode(k)) continue;
    uint8_t hid = keyNameToHid(k);
    if (hid) Keyboard.pressRaw(hid);
    else if (k.length() == 1) Keyboard.print(k);
  }
  delay(15);
  Keyboard.releaseAll();
}

void hidHold(const String &name) {
  uint8_t m = modifierNameToCode(name);
  if (m) { Keyboard.press(m); return; }
  uint8_t hid = keyNameToHid(name);
  if (hid) Keyboard.pressRaw(hid);
}

void hidReleaseAll() { Keyboard.releaseAll(); }

void hidSendMedia(uint16_t usage) {
  if (!usage) return;
  Consumer.press(usage);
  delay(15);
  Consumer.release();
}

void hidMouseMove(int x, int y, int wheel) {
  // Clamp to the int8 range the HID report supports.
  auto clamp8 = [](int v) -> int8_t {
    if (v > 127) v = 127;
    if (v < -127) v = -127;
    return (int8_t)v;
  };
  Mouse.move(clamp8(x), clamp8(y), clamp8(wheel));
}

void hidMouseClick(uint8_t buttons) {
  if (buttons & 1) Mouse.click(MOUSE_LEFT);
  if (buttons & 2) Mouse.click(MOUSE_RIGHT);
  if (buttons & 4) Mouse.click(MOUSE_MIDDLE);
}

bool hidSendTelephony(const String &which) {
#if ENABLE_TELEPHONY_HID
  uint8_t bits = 0;
  if (which.equalsIgnoreCase("ANSWER")) bits = 0x01;       // Hook Switch
  else if (which.equalsIgnoreCase("MIC_MUTE")) bits = 0x02; // Phone Mute
  else if (which.equalsIgnoreCase("DECLINE")) bits = 0x04;  // Drop
  else return false;
  telephony.sendBits(bits);
  delay(10);
  telephony.sendBits(0x00);  // release
  return true;
#else
  Serial.println("Telephony HID disabled in firmware build.");
  return false;
#endif
}
