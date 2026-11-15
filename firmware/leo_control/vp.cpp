#include "vp.h"
#include "config.h"
#include "settings.h"
#include "log.h"

Vp vp;

enum { T_GEN = 0, T_GP, T_HSGP };

void Vp::begin() {
  link.begin(&VP_PORT, "vp", FRAME_VP, "\r\n", onReplyThunk, this);
  applyLinkSettings();
}

void Vp::applyLinkSettings() {
  link.setInvert(si(VP_TX_INV), si(VP_RX_INV));
  link.setTiming(si(VP_TIMEOUT_MS), si(VP_GAP_MS), si(VP_RETRIES));
}

const char* Vp::stateName() const {
  static const char* n[] = { "POWER_UP", "AT_AIR_HP", "AT_AIR_LP", "PUMPING_LP", "GUN_ENABLE_OK",
                             "READY_TO_PUMP", "READY_TO_VENT", "WAIT_ABOVE_MCP", "GOING_TO_HP",
                             "AT_HP", "WAIT_LESS_MCP", "GUN_ENABLE_DELAY" };
  if (!link.online || st_ < 0) return "no link";
  if (st_ > 11) return "unknown";
  return n[st_];
}

// Pirani gauge: counts -> volts -> Pa through the calibration table (vp.pir_*).
float Vp::paFromCounts(int c) {
  float v = c * sf(VP_V_GAIN) + sf(VP_V_OFF);
  if (v <= sf(VP_PIR_V0)) return sf(VP_PIR_P0);
  for (int i = 1; i < 8; i++) {
    float v0 = sf((SettingId)(VP_PIR_V0 + i - 1)), v1 = sf((SettingId)(VP_PIR_V0 + i));
    if (v <= v1) {
      float p0 = sf((SettingId)(VP_PIR_P0 + i - 1)), p1 = sf((SettingId)(VP_PIR_P0 + i));
      return p0 + (p1 - p0) * (v - v0) / (v1 - v0);
    }
  }
  return sf(VP_PIR_P7);
}

float Vp::countsFromPa(float pa) {
  float v = sf(VP_PIR_V7);
  if (pa <= sf(VP_PIR_P0)) v = sf(VP_PIR_V0);
  else for (int i = 1; i < 8; i++) {
    float p0 = sf((SettingId)(VP_PIR_P0 + i - 1)), p1 = sf((SettingId)(VP_PIR_P0 + i));
    if (pa <= p1) {
      float v0 = sf((SettingId)(VP_PIR_V0 + i - 1)), v1 = sf((SettingId)(VP_PIR_V0 + i));
      v = v0 + (v1 - v0) * (pa - p0) / (p1 - p0);
      break;
    }
  }
  return (v - sf(VP_V_OFF)) / sf(VP_V_GAIN);
}

void Vp::sendTarget(float pa) {
  float raw = countsFromPa(pa);
  float c = raw * sf(VP_HP_GAIN) + sf(VP_HP_OFF);
  if (pa > sf(VP_HP_HIP)) c *= 1.0f + sf(VP_HP_HIK) * (pa - sf(VP_HP_HIP)) / sf(VP_HP_HIP);
  long a = lroundf(raw * (1.0f - sf(VP_BAND_LO))), b = lroundf(raw * (1.0f + sf(VP_BAND_HI)));
  long up = pa <= sf(VP_MC_LOWP) ? si(VP_MC_UP_MIN) : lroundf(sf(VP_MC_UP_FRAC) * raw);
  char buf[40];
  snprintf(buf, sizeof buf, "MC %ld,%ld", up, si(VP_MC_DOWN));
  link.push(buf, T_GEN);
  snprintf(buf, sizeof buf, "HP %ld,%ld,%ld", a, b, lroundf(c));
  link.push(buf, T_GEN);
}

void Vp::informAir()    { if (st_ != 2) link.push("TO 2", T_GEN); }
void Vp::informPumped() { if (st_ != 3) link.push("TO 3", T_GEN); }
void Vp::reset()        { link.push("RE 0", T_GEN); }

void Vp::enter(float pa) {
  sendTarget(pa);                  // always set HP and MC before TO 7
  link.push("TO 7", T_GEN);
  link.push("GP", T_GP);
  logf(LV_INFO, "vp", "enter VP at %.0f Pa", pa);
}

void Vp::exit() {
  exiting_ = true;
  link.push("TO 10", T_GEN);
  link.push("GP", T_GP);
  logf(LV_INFO, "vp", "return to high vacuum");
}

void Vp::setTarget(float pa) {
  sendTarget(pa);
  link.push("GP", T_GP);
}

void Vp::onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* c, const char* r) {
  ((Vp*)ctx)->onReply(tag, ok, c, r);
}

void Vp::onReply(uint8_t tag, bool ok, const char* cmd, const char* r) {
  if (tag == TAG_UNSOLICITED) {
    if (strstr(r, "Interface HP")) {
      logf(LV_WARN, "vp", "VP controller restarted");
      hsDone_ = false; hsStep_ = 0;
    }
    return;
  }
  if (!ok) {
    if (wasOnline_) logf(LV_WARN, "vp", "no reply to %s: link down", cmd);
    wasOnline_ = false;
    gpValid_ = false;
    if (!hsDone_) { hsStep_ = 0; link.clearQueue(); hsRetryMs_ = millis() + (uint32_t)(sf(VP_POLL_S) * 1000); }
    return;
  }
  if (!wasOnline_) { wasOnline_ = true; logf(LV_INFO, "vp", "link up"); }
  if (!strcmp(r, "255")) {
    rejects_++;
    logf(LV_WARN, "vp", "%s refused (255)", cmd);
    return;
  }
  if (tag == T_GP || tag == T_HSGP) {
    int f[6];
    if (sscanf(r, "%d,%d,%d,%d,%d,%d", &f[0], &f[1], &f[2], &f[3], &f[4], &f[5]) != 6) return;
    int old = st_;
    gauge_ = f[0]; st_ = f[1]; req_ = f[2]; v8_ = f[3]; v14_ = f[4];
    if (f[5] != err_ && f[5]) logf(LV_FAULT, "vp", "VP controller error %d", f[5]);
    err_ = f[5];
    gpValid_ = true;
    if (old != st_ && old >= 0) logf(LV_INFO, "vp", "VP state %d -> %d (%s)", old, st_, stateName());
    if (hsDone_ && st_ == 0 && old != 0) {
      logf(LV_WARN, "vp", "VP controller back in POWER_UP (watchdog or reset): handshake again");
      hsDone_ = false; hsStep_ = 0;
    }
    if (hsDone_ && st_ == 4) { link.push("TO 3", T_GEN); exiting_ = false; }   // gun enable OK -> pumping LP
  }
}

// Start-up handshake (spec §6.1). A controller found in a working state is adopted
// without RE 0 / RE 1, which could reverse a VP transition or open V8 under gas.
void Vp::hsService() {
  if (hsDone_ || link.queued() || link.inflight()) return;
  if ((int32_t)(millis() - hsRetryMs_) < 0) return;
  char b[24];
  switch (hsStep_) {
    case 0:
      link.push("GP", T_HSGP);
      hsStep_ = 1;
      break;
    case 1:
      if (!gpValid_) { hsStep_ = 0; return; }
      if (st_ == 0 || err_) link.push("RE 0", T_GEN);
      snprintf(b, sizeof b, "ST 1,%ld", si(VP_WD_S)); link.push(b, T_GEN);
      snprintf(b, sizeof b, "ST 2,%ld", si(VP_T_MCPUP)); link.push(b, T_GEN);
      snprintf(b, sizeof b, "ST 3,%ld", si(VP_T_MCPDN)); link.push(b, T_GEN);
      snprintf(b, sizeof b, "ST 4,%ld", si(VP_T_TARGET)); link.push(b, T_GEN);
      snprintf(b, sizeof b, "ST 5,%ld", si(VP_T_GUN)); link.push(b, T_GEN);
      link.push("GP", T_HSGP);
      hsStep_ = 2;
      break;
    case 2:
      if (st_ >= 0 && st_ <= 3) {                      // not in a VP transition: align LP state
        if (vacHint_ == 0) return;                     // wait until the vacuum state is known
        link.push(vacHint_ == 2 ? "TO 3" : "TO 2", T_GEN);
        sendTarget(sf(OP_VP_PA));
      }
      link.push("GP", T_GP);
      hsDone_ = true;
      logf(LV_INFO, "vp", "handshake done, state %d", st_);
      break;
  }
}

void Vp::service() {
  link.service();
  hsService();
  uint32_t now = millis();
  // Poll (and so feed the controller's watchdog) also while the handshake waits for the vacuum state.
  if ((hsDone_ || hsStep_ == 2) && !link.inflight() && link.queued() == 0 &&
      now - lastPoll_ >= (uint32_t)(sf(VP_POLL_S) * 1000)) {
    lastPoll_ = now;
    link.push("GP", T_GP);
  }
}
