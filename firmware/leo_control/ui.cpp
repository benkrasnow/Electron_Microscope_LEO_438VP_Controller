#include "ui.h"
#include "eve.h"
#include "settings.h"
#include "log.h"
#include "eht.h"
#include "stgvac.h"
#include "vp.h"
#include "eo.h"
#include "machine.h"
#include "usb.h"
#include <math.h>

using namespace ev;

static Eve lcd;
static uint32_t lastDraw = 0, lastTouch = 0, lastRetry = 0, msgUntil = 0;
static char msg[96] = "";
static bool msgWarn = false;
static uint8_t pressed = 0, lastTag = 0;
enum Confirm : uint8_t { CF_NONE, CF_VENT, CF_VP_ENTER, CF_VP_EXIT };
static Confirm confirm = CF_NONE;

// Colours
static const uint32_t C_BG = 0x0E1216, C_PANEL = 0x1C232C, C_HEAD = 0x14325A, C_TEXT = 0xE6EAF0,
  C_LABEL = 0x8C98A8, C_OK = 0x34C46A, C_WARN = 0xE8A824, C_BAD = 0xE5484D, C_BTN = 0x2C6FD6,
  C_BTN_OFF = 0x39424D, C_STOP = 0xC62828, C_DIM = 0x6B7480;

enum { TG_PUMP = 1, TG_VENT, TG_BEAM_ON, TG_BEAM_OFF, TG_VP, TG_STOP, TG_CONFIRM = 10, TG_CANCEL = 11 };

void uiMessage(const char* m, bool warn) {
  strlcpy(msg, m, sizeof msg);
  msgWarn = warn;
  msgUntil = millis() + 5000;
}

void uiApplySettings() { lcd.setBacklight(si(UI_BL)); lcd.setSpeed((uint32_t)(sd(UI_SPI_MHZ) * 1e6)); }

static bool tryDisplay(uint32_t waitMs, bool report) {
  if (lcd.begin((uint32_t)(sd(UI_SPI_MHZ) * 1e6), si(UI_CLKEXT), si(UI_ROTATE), waitMs)) {
    lcd.setBacklight(si(UI_BL));
    logf(LV_INFO, "ui", "display found");
    return true;
  }
  if (report) logf(LV_WARN, "ui", "no display (FT813 not answering): running without it");
  return false;
}

void uiBegin() { tryDisplay(500, true); }

// ------------------------------------------------------------------ drawing helpers

static void row(int x, int y, int w, const char* label, const char* value, uint32_t vc = C_TEXT, int font = 27) {
  lcd.dl(COLOR(C_LABEL)); lcd.text(x + 12, y, 26, OPT_CENTERY, label);
  lcd.dl(COLOR(vc));      lcd.text(x + w - 12, y, font, OPT_CENTERY | OPT_RIGHTX, value);
}

static void panel(int x, int y, int w, int h, const char* title) {
  lcd.dl(COLOR(C_PANEL)); lcd.rect(x, y, x + w, y + h, 8);
  lcd.dl(COLOR(C_LABEL)); lcd.text(x + 12, y + 16, 28, OPT_CENTERY, title);
}

static void fmtPressureHv(char* b, size_t n, double torr) {
  if (isnan(torr)) { strlcpy(b, "--", n); return; }
  switch (si(UI_PUNIT)) {
    case 1: snprintf(b, n, "%.1e mbar", torr * 1.33322); break;
    case 2: snprintf(b, n, "%.1e Pa", torr * 133.322); break;
    default: snprintf(b, n, "%.1e Torr", torr); break;
  }
}

static void dot(int x, int y, bool ok, const char* name) {
  lcd.dl(COLOR(ok ? C_OK : C_BAD)); lcd.point(x, y, 6);
  lcd.dl(COLOR(C_TEXT)); lcd.text(x + 11, y, 26, OPT_CENTERY, name);
}

static void btn(int tag, int x, int y, int w, int h, const char* label, bool enabled, uint32_t color = C_BTN) {
  lcd.dl(TAG(tag));
  lcd.fg(enabled ? color : C_BTN_OFF);
  lcd.dl(COLOR(enabled ? 0xFFFFFF : C_DIM));
  lcd.button(x, y, w, h, 28, enabled ? 0 : OPT_FLAT, label);
  lcd.dl(TAG(0));
}

static void draw() {
  char b[64], b2[64];
  lcd.frameStart(C_BG);
  lcd.dl(TAG(0));

  // Header
  lcd.dl(COLOR(C_HEAD)); lcd.rect(0, 0, 800, 44, 0);
  lcd.dl(COLOR(C_TEXT)); lcd.text(12, 22, 29, OPT_CENTERY, "LEO 438VP");
  lcd.dl(COLOR(0xFFFFFF)); lcd.text(420, 22, 28, OPT_CENTER, machine.summary());
  unsigned long t = rtc_get();
  if (t > 1600000000UL) { snprintf(b, sizeof b, "%02lu:%02lu", (t / 3600) % 24, (t / 60) % 60); lcd.dl(COLOR(C_LABEL)); lcd.text(788, 22, 27, OPT_CENTERY | OPT_RIGHTX, b); }

  // Activity / message line
  const char* act = machine.activity()[0] ? machine.activity() : eht.activity();
  uint32_t mc = C_TEXT;
  if (millis() < msgUntil) { act = msg; mc = msgWarn ? C_WARN : C_TEXT; }
  else if (!act[0] && logCount()) {
    const LogEntry* e = logGet(0);
    if (e->lvl >= LV_WARN && millis() - e->ms < 60000) { act = e->msg; mc = e->lvl == LV_FAULT ? C_BAD : C_WARN; }
  }
  lcd.dl(COLOR(mc)); lcd.text(400, 62, 28, OPT_CENTER, act);

  // Vacuum panel
  const int py = 82, ph = 290, pw = 256;
  int x = 8;
  panel(x, py, pw, ph, "VACUUM");
  bool ready = stg.vacReady();
  row(x, py + 52, pw, "State", stg.vacText(), ready ? C_OK : (stg.link.online ? C_WARN : C_BAD), 28);
  fmtPressureHv(b, sizeof b, stg.torr());
  row(x, py + 86, pw, "Column", b, C_TEXT, 28);
  snprintf(b, sizeof b, "%02X", stg.inhibits());
  row(x, py + 118, pw, "Inhibits", stg.link.online ? b : "--", stg.inhibits() == 0 ? C_OK : C_WARN);
  row(x, py + 156, pw, "VP ctrl", vp.stateName(), vp.online() ? C_TEXT : C_BAD);
  if (vp.chamberVp()) snprintf(b, sizeof b, "%.0f Pa", vp.pa()); else strlcpy(b, vp.online() ? "high vac." : "--", sizeof b);
  row(x, py + 190, pw, "Chamber", b, vp.atHp() ? C_OK : C_TEXT, 28);
  snprintf(b, sizeof b, "%.0f Pa", sf(OP_VP_PA));
  row(x, py + 222, pw, "VP target", b);
  row(x, py + 254, pw, "Mode", vp.chamberVp() ? "VP" : "High vacuum", C_TEXT);

  // Beam panel
  x = 272;
  panel(x, py, pw, ph, "BEAM");
  BeamState bs = eht.beam();
  uint32_t bc = bs == BEAM_ON ? C_OK : (bs == BEAM_OFF ? (eht.filCold() ? C_TEXT : C_WARN) : C_WARN);
  const char* bn = bs == BEAM_ON ? "ON" : bs == BEAM_STARTING ? "STARTING" : bs == BEAM_STOPPING ? "STOPPING" :
                   bs == BEAM_EHT_OFF ? "EHT OFF" : (eht.filCold() ? "OFF" : "COOLING");
  row(x, py + 52, pw, "Beam", bn, bc, 29);
  snprintf(b, sizeof b, "%.2f kV", bs == BEAM_OFF ? sf(OP_KV) : eht.kvApplied());
  row(x, py + 88, pw, bs == BEAM_OFF ? "EHT (set)" : "EHT", b, C_TEXT, 28);
  snprintf(b, sizeof b, "%.0f uA", sf(OP_EMIS_UA));
  row(x, py + 122, pw, "Emission", b);
  snprintf(b, sizeof b, "%.3f A", (bs == BEAM_OFF ? si(OP_FIL_MA) : eht.filApplied()) / 1000.0);
  row(x, py + 154, pw, bs == BEAM_OFF ? "Filament (set)" : "Filament", b);
  snprintf(b, sizeof b, "%.0f V", sf(OP_COLL_V));
  row(x, py + 186, pw, "Collector", b);
  if (eht.statusValid()) snprintf(b, sizeof b, "%02X%s", eht.status(), eht.inhibited() ? " inhib." : ""); else strlcpy(b, "--", sizeof b);
  row(x, py + 218, pw, "EHT status", b, eht.ready() ? C_OK : C_WARN);
  if (bs == BEAM_OFF && !eht.filCold()) { snprintf(b, sizeof b, "%.0f s", eht.coolRemainingS()); row(x, py + 254, pw, "Cooling", b, C_WARN); }

  // Stage / scan panel
  x = 536;
  panel(x, py, pw, ph, "STAGE / SCAN");
  static const char* an[5] = { "X", "Y", "Z", "T", "R" };
  for (int a = 0; a < 5; a++) {
    if (stg.sdValid()) snprintf(b, sizeof b, a < 3 ? "%.3f mm" : "%.2f deg", StgVac::toUnits(a, stg.axis(a).pos));
    else strlcpy(b, "--", sizeof b);
    row(x, py + 50 + a * 28, pw, an[a], b, stg.axis(a).moving ? C_WARN : C_TEXT);
  }
  const char* sst = stg.homing() ? stg.homeActivity() : (stg.homed() ? (stg.limitActive() ? "on limit" : "initialised") : "not initialised");
  row(x, py + 194, pw, "Stage", sst, stg.homed() && !stg.limitActive() ? C_OK : C_WARN);
  snprintf(b, sizeof b, "%s, speed %d", eo.modeName(), (int)si(OP_SPEED));
  row(x, py + 226, pw, "Scan", b);
  float mag = sf(OP_MAG);
  if (mag >= 1000) snprintf(b2, sizeof b2, "%.1fk x", mag / 1000); else snprintf(b2, sizeof b2, "%.0f x", mag);
  row(x, py + 258, pw, "Mag", b2, C_TEXT, 28);

  // Links
  int ly = 388;
  dot(20, ly, eht.link.online, "EHT");
  dot(90, ly, stg.link.online, "STG/VAC");
  dot(190, ly, vp.online(), "VP");
  dot(240, ly, eo.linkOk(), "EO");
  dot(290, ly, usbConnected(), "PC");
  if (logCount()) {
    const LogEntry* e = logGet(0);
    lcd.dl(COLOR(e->lvl == LV_FAULT ? C_BAD : e->lvl == LV_WARN ? C_WARN : C_LABEL));
    lcd.text(345, ly, 26, OPT_CENTERY, e->msg);
  }

  // Buttons
  const int by = 406, bh = 66, bw = 124;
  int bx = 8;
  btn(TG_PUMP, bx, by, bw, bh, "PUMP", !machine.pump(true)); bx += bw + 6;
  btn(TG_VENT, bx, by, bw, bh, "VENT", !machine.vent(true)); bx += bw + 6;
  btn(TG_BEAM_ON, bx, by, bw, bh, "BEAM ON", !machine.beamOn(true), 0x23944F); bx += bw + 6;
  btn(TG_BEAM_OFF, bx, by, bw, bh, "BEAM OFF", !machine.beamOff(true)); bx += bw + 6;
  bool inVp = vp.chamberVp();
  btn(TG_VP, bx, by, bw, bh, inVp ? "LEAVE VP" : "ENTER VP",
      inVp ? !machine.vpExit(true) : !machine.vpEnter(sf(OP_VP_PA), true)); bx += bw + 6;
  btn(TG_STOP, bx, by, 792 - bx, bh, "STOP", true, C_STOP);

  // Confirmation overlay
  if (confirm != CF_NONE) {
    lcd.dl(COLOR_A(200)); lcd.dl(COLOR(0x000000)); lcd.rect(0, 0, 800, 480, 0); lcd.dl(COLOR_A(255));
    lcd.dl(COLOR(C_PANEL)); lcd.rect(170, 130, 630, 350, 12);
    const char* q = confirm == CF_VENT ? "Vent the chamber?" : confirm == CF_VP_EXIT ? "Return to high vacuum?" : "Enter VP mode?";
    lcd.dl(COLOR(C_TEXT)); lcd.text(400, 175, 30, OPT_CENTER, q);
    if (confirm == CF_VP_ENTER) snprintf(b, sizeof b, "Target %.0f Pa. Beam goes off first.", sf(OP_VP_PA));
    else strlcpy(b, "The beam goes off and the filament cools first.", sizeof b);
    lcd.dl(COLOR(C_LABEL)); lcd.text(400, 220, 27, OPT_CENTER, b);
    btn(TG_CONFIRM, 200, 260, 190, 66, "CONFIRM", true, 0xD07A12);
    btn(TG_CANCEL, 410, 260, 190, 66, "CANCEL", true, C_BTN_OFF);
  }
  lcd.frameEnd();
}

// ------------------------------------------------------------------ touch

static void act(uint8_t tag) {
  const char* err = nullptr;
  if (confirm != CF_NONE) {
    if (tag == TG_CONFIRM) {
      if (confirm == CF_VENT) err = machine.vent();
      else if (confirm == CF_VP_ENTER) err = machine.vpEnter(sf(OP_VP_PA));
      else err = machine.vpExit();
    }
    if (tag == TG_CONFIRM || tag == TG_CANCEL) confirm = CF_NONE;
    if (err) uiMessage(err, true);
    return;
  }
  switch (tag) {
    case TG_PUMP: err = machine.pump(); break;
    case TG_VENT:
      err = machine.vent(true);
      if (!err) { if (si(UI_CONFIRM)) confirm = CF_VENT; else err = machine.vent(); }
      break;
    case TG_BEAM_ON: err = machine.beamOn(); break;
    case TG_BEAM_OFF: err = machine.beamOff(true); if (!err) machine.beamOff(); break;
    case TG_VP:
      if (vp.chamberVp()) { err = machine.vpExit(true); if (!err) { if (si(UI_CONFIRM)) confirm = CF_VP_EXIT; else err = machine.vpExit(); } }
      else { err = machine.vpEnter(sf(OP_VP_PA), true); if (!err) { if (si(UI_CONFIRM)) confirm = CF_VP_ENTER; else err = machine.vpEnter(sf(OP_VP_PA)); } }
      break;
    default: break;
  }
  if (err) uiMessage(err, true);
}

void uiService() {
  uint32_t now = millis();
  if (!lcd.ok()) {
    // Look for a display plugged in later; short wait so the control loop is barely held up.
    if (now - lastRetry > 60000) { lastRetry = now; tryDisplay(60, false); }
    return;
  }
  if (now - lastTouch >= 20) {
    lastTouch = now;
    uint8_t tg = lcd.touchTag();
    if (tg != lastTag) {
      if (tg && !lastTag) {
        pressed = tg;
        if (tg == TG_STOP) { machine.safe("touch STOP"); confirm = CF_NONE; uiMessage("STOP: beam off, stage stopped", true); }
      } else if (!tg && pressed && pressed == lastTag && pressed != TG_STOP) {
        act(pressed);                // act on release over the same button
      }
      if (!tg) pressed = 0;
      lastTag = tg;
    }
  }
  if (now - lastDraw >= (uint32_t)si(UI_REFRESH_MS) && !lcd.busy()) {
    lastDraw = now;
    draw();
  }
}
