// LEO 438VP control box: Teensy 4.0 firmware.
// Owns machine state and safety for the EHT, stage/vacuum, VP and EO links; the PC talks to it
// over USB serial (firmware/PROTOCOL.md) and the touch display shows the state.
// Build: Teensyduino, board Teensy 4.0, USB type Serial, CPU 600 MHz.
#include "config.h"
#include "settings.h"
#include "log.h"
#include "eht.h"
#include "stgvac.h"
#include "vp.h"
#include "eo.h"
#include "machine.h"
#include "usb.h"
#include "ui.h"

// ------------------------------------------------------------------ buttons (active low)
static const uint8_t BTN_PIN[3] = { PIN_BTN1, PIN_BTN2, PIN_BTN3 };
static bool btnStable[3] = { false, false, false }, btnRaw[3] = { false, false, false };
static uint32_t btnChange[3] = { 0, 0, 0 };

bool btnState(int i) { return btnStable[i]; }

static void buttonAction(int i) {
  int a = si((SettingId)(BTN1_ACT + i));
  const char* err = nullptr;
  switch (a) {
    case 1: machine.safe("button"); uiMessage("STOP button: beam off, stage stopped", true); break;
    case 2: err = machine.beamOn(); break;
    case 3: err = machine.beamOff(); break;
    case 4: stg.stop(); uiMessage("Stage stopped", false); break;
    case 5: err = machine.ehtOff(); break;
    case 6: machine.abort(); break;
    default: break;
  }
  if (err) uiMessage(err, true);
  logf(LV_INFO, "btn", "button %d pressed (action %d)", i + 1, a);
}

static void buttonsService() {
  uint32_t now = millis();
  for (int i = 0; i < 3; i++) {
    bool r = !digitalReadFast(BTN_PIN[i]);
    if (r != btnRaw[i]) { btnRaw[i] = r; btnChange[i] = now; }
    if (r != btnStable[i] && now - btnChange[i] >= (uint32_t)si(BTN_DEB_MS)) {
      btnStable[i] = r;
      if (r) buttonAction(i);
    }
  }
}

// ------------------------------------------------------------------ settings hook

void settingChanged(int id) {
  switch (id) {
    case EHT_TX_INV: case EHT_RX_INV: case EHT_TIMEOUT_MS: case EHT_GAP_MS: case EHT_RETRIES:
      eht.applyLinkSettings(); break;
    case STG_TX_INV: case STG_RX_INV: case STG_TIMEOUT_MS: case STG_GAP_MS: case STG_RETRIES:
      stg.applyLinkSettings(); break;
    case VP_TX_INV: case VP_RX_INV: case VP_TIMEOUT_MS: case VP_GAP_MS: case VP_RETRIES:
      vp.applyLinkSettings(); break;
    case EO_TX_INV: case EO_RX_INV: case EO_BAUD: case EO_GAP_US: case EO_REPLY_US: case SCAN_LPOL: case SCAN_FPOL:
      eo.applyPins(); break;
    case UI_BL: case UI_SPI_MHZ:
      uiApplySettings(); break;
    default:
      if ((id >= EO_KV_REF && id <= EO_CY4) || id == EO_WMAX) eo.calibrationChanged();
      break;
  }
}

// ------------------------------------------------------------------ main

static uint32_t lastLed = 0;

void setup() {
  pinMode(PIN_LED, OUTPUT);
  // External 10k pull-ups and RC on the board; the internal pull-up keeps a bare Teensy quiet.
  // A button already held at power-up does not act until it is released and pressed again.
  for (int i = 0; i < 3; i++) pinMode(BTN_PIN[i], INPUT_PULLUP);
  delay(2);
  for (int i = 0; i < 3; i++) btnStable[i] = btnRaw[i] = !digitalReadFast(BTN_PIN[i]);
  usbBegin();
  settingsBegin();
  logf(LV_INFO, "sys", "%s %s start", FW_NAME, FW_VERSION);
  if (CrashReport) logf(LV_WARN, "sys", "restarted after a crash (details: CrashReport over USB)");
  eo.begin();             // EO first: lenses and scan come back immediately after a reset
  eht.begin();
  stg.begin();
  vp.begin();
  machine.begin();
  uiBegin();
}

void loop() {
  usbService();
  eht.service();
  stg.service();
  vp.service();
  machine.service();
  eo.service(eht.kvSettled());
  buttonsService();
  uiService();
  bool linksIdle = !eht.link.inflight() && !stg.link.inflight() && !vp.link.inflight() && eo.queued() == 0;
  settingsService(linksIdle);

  // Status LED: slow blink normally, fast while any link is down or a fault is recent.
  uint32_t now = millis();
  bool trouble = !eht.link.online || !stg.link.online || !vp.online();
  if (logCount() && logGet(0)->lvl == LV_FAULT && now - logGet(0)->ms < 30000) trouble = true;
  if (now - lastLed >= (trouble ? 125u : 500u)) { lastLed = now; digitalToggleFast(PIN_LED); }
}
