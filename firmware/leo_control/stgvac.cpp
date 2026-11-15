#include "stgvac.h"
#include "config.h"
#include "settings.h"
#include "log.h"
#include <math.h>

StgVac stg;

enum { T_GEN = 0, T_VT, T_SD, T_VS, T_SP, T_VX, T_VV, T_SY, T_CFGEND };

static const char AXN[5] = { 'X', 'Y', 'Z', 'T', 'R' };

static long sAx(SettingId base, int i) { return si((SettingId)(base + i)); }

void StgVac::begin() {
  link.begin(&STG_PORT, "stg", FRAME_EQ, "\r\n", onReplyThunk, this);
  applyLinkSettings();
}

void StgVac::applyLinkSettings() {
  link.setInvert(si(STG_TX_INV), si(STG_RX_INV));
  link.setTiming(si(STG_TIMEOUT_MS), si(STG_GAP_MS), si(STG_RETRIES));
}

static const char* vacCode(VacState v) {
  static const char* n[] = { "?", "NSP", "WTUS", "WP", "SP", "SPVR", "SPE", "WVT", "other" };
  return n[v];
}

const char* StgVac::vacName() const { return vacCode(vac_); }

const char* StgVac::vacText() const {
  if (!link.online) return "No link";
  static const char* n[] = { "Unknown", "Vented", "Turbo spin-up", "Waiting for gauge", "Pumping",
                             "Vacuum ready", "Gauge error", "Venting", "Unknown" };
  return n[vac_];
}

double StgVac::torr() const {
  if (gauge_ <= 0 || vac_ == VS_SPE || vac_ == VS_WTUS || vac_ == VS_WP) return NAN;
  return 1.0 / (sd(VAC_PEN_A) * pow((double)gauge_, sd(VAC_PEN_EXP)));
}

bool StgVac::vacReady() const {
  return link.online && configured_ && vac_ == VS_SPVR && vsValid_ && vs_[0] == 0;
}

bool StgVac::moving() const {
  for (int i = 0; i < 5; i++) if (ax_[i].moving) return true;
  return false;
}

bool StgVac::homed() const {
  if (!sdValid_) return false;
  for (int i = 0; i < 5; i++) if (!ax_[i].init) return false;
  return true;
}

double StgVac::toUnits(int a, long c) {
  return (c - sAx(STG_ZERO_X, a)) / sd((SettingId)(STG_CPU_X + a));
}
long StgVac::toCounts(int a, double u) {
  return sAx(STG_ZERO_X, a) + lround(u * sd((SettingId)(STG_CPU_X + a)));
}

void StgVac::activeLimits(long lo[5], long hi[5]) const {
  for (int i = 0; i < 5; i++) { lo[i] = sAx(STG_LO_X, i); hi[i] = sAx(STG_HI_X, i); }
  if (airLimits_) {
    lo[0] = si(STG_AIR_LO_X); hi[0] = si(STG_AIR_HI_X);
    lo[1] = si(STG_AIR_LO_Y); hi[1] = si(STG_AIR_HI_Y);
  }
}

// Start-up configuration, in the original order (spec §6.1). Returns false past the end.
bool StgVac::configCmd(int i, char* b, size_t n, uint8_t& tag) {
  tag = T_GEN;
  if (i == 0) { snprintf(b, n, ".VS"); tag = T_VS; return true; }
  if (i >= 1 && i <= 7)  { snprintf(b, n, ".VX %d", 80 + i - 1); tag = T_VX; return true; }
  if (i >= 8 && i <= 14) { snprintf(b, n, ".VV %d", 80 + i - 8); tag = T_VV; return true; }
  static const char* fixed[] = {
    ".VV 66", ".VX 61", ".VW 61 CC", ".VW 61 C8", ".VY", ".CF N", ".SS", ".VS",
    ".CG N", ".CA N", ".CB N", ".CE N", ".VP C", nullptr /*TH*/,
    ".QA 1 N", ".QA 2 N", ".QA 3 N", ".QA 4 N",
    nullptr /*TA*/, nullptr /*TB*/, nullptr /*TC*/, nullptr /*TD*/, nullptr /*TE*/,
    ".SL X 0 Y 1 Z 2 T 3 R 4", ".CD N", ".SP",
    nullptr /*SC*/, nullptr /*SB*/, ".SY", nullptr /*SV*/, ".QC H", ".VT"
  };
  int k = i - 15;
  if (k < 0 || k >= (int)(sizeof fixed / sizeof fixed[0])) return false;
  if (fixed[k]) {
    strlcpy(b, fixed[k], n);
    if (!strcmp(b, ".VS")) tag = T_VS;
    if (!strcmp(b, ".SP")) tag = T_SP;
    if (!strcmp(b, ".SY")) tag = T_SY;
    if (!strcmp(b, ".VT")) tag = T_CFGEND;
    return true;
  }
  switch (k) {
    case 13: snprintf(b, n, ".TH %ld", si(VAC_TH)); break;
    case 18: snprintf(b, n, ".TA %ld", si(VAC_TA)); break;
    case 19: snprintf(b, n, ".TB %ld %ld", si(VAC_TB1), si(VAC_TB2)); break;
    case 20: snprintf(b, n, ".TC %ld", si(VAC_TC)); break;
    case 21: snprintf(b, n, ".TD %ld %ld", si(VAC_TD1), si(VAC_TD2)); break;
    case 22: snprintf(b, n, ".TE %ld %ld", si(VAC_TE1), si(VAC_TE2)); break;
    case 26: {
      int p = snprintf(b, n, ".SC");
      for (int a = 0; a < 5; a++) p += snprintf(b + p, n - p, " %ld %ld %ld", si(STG_RAMP_A), si(STG_RAMP_B), si(STG_RAMP_C));
      break;
    }
    case 27: snprintf(b, n, ".SB %ld %ld %ld %ld %ld", sAx(STG_SPD_X, 0), sAx(STG_SPD_X, 1), sAx(STG_SPD_X, 2), sAx(STG_SPD_X, 3), sAx(STG_SPD_X, 4)); break;
    case 29: snprintf(b, n, ".SV %ld %ld %ld %ld %ld", sAx(STG_SV_X, 0), sAx(STG_SV_X, 1), sAx(STG_SV_X, 2), sAx(STG_SV_X, 3), sAx(STG_SV_X, 4)); break;
    default: return false;
  }
  return true;
}

void StgVac::sendLimits() {
  bool air = !(vac_ == VS_SP || vac_ == VS_SPVR);
  airLimits_ = air;
  limitsValid_ = true;
  long lo[5], hi[5];
  activeLimits(lo, hi);
  char b[80];
  snprintf(b, sizeof b, ".SQ %ld %ld %ld %ld %ld", lo[0], lo[1], lo[2], lo[3], lo[4]); link.push(b, T_GEN);
  snprintf(b, sizeof b, ".SJ %ld %ld %ld %ld %ld", hi[0], hi[1], hi[2], hi[3], hi[4]); link.push(b, T_GEN);
}

bool StgVac::pump() {
  if (!link.online) return false;
  link.push(".VL P", T_GEN, true);
  logf(LV_INFO, "vac", "pump down requested");
  return true;
}

bool StgVac::vent() {
  if (!link.online) return false;
  link.push(".VL V", T_GEN, true);
  logf(LV_INFO, "vac", "vent requested");
  return true;
}

const char* StgVac::gotoCounts(const long c[5]) {
  if (!link.online || !configured_) return "stage link down";
  if (si(STG_REQ_HOME) && !homed()) return "stage not initialised";
  long lo[5], hi[5], t[5];
  activeLimits(lo, hi);
  for (int i = 0; i < 5; i++) t[i] = constrain(c[i], lo[i], hi[i]);
  char b[80];
  snprintf(b, sizeof b, ".SF %ld %ld %ld %ld %ld", t[0], t[1], t[2], t[3], t[4]);
  link.push(b, T_GEN);
  for (int i = 0; i < 5; i++) if (t[i] != c[i]) return "clamped to limits";
  return nullptr;
}

void StgVac::stop() {
  link.push(".SK", T_GEN, true);
  if (homeStep_) { homeStep_ = 0; homeAct_[0] = 0; logf(LV_WARN, "stg", "homing aborted"); }
}

const char* StgVac::home() {
  if (!link.online || !configured_) return "stage link down";
  if (homeStep_) return "already homing";
  homeStep_ = 1;
  logf(LV_INFO, "stg", "stage initialise started");
  return nullptr;
}

// Homing: Z, then T, Y, X (R is never homed), then set positions, limits, speeds, park.
void StgVac::homeService() {
  if (!homeStep_ || link.queued() > 2) return;
  char b[80];
  static const int order[4] = { 2, 3, 1, 0 };
  uint32_t now = millis();
  if (homeStep_ == 1) {
    snprintf(b, sizeof b, ".SB %ld %ld %ld %ld %ld", sAx(STG_HSPD_X, 0), sAx(STG_HSPD_X, 1), sAx(STG_HSPD_X, 2), sAx(STG_HSPD_X, 3), sAx(STG_HSPD_X, 4));
    link.push(b, T_GEN);
    snprintf(b, sizeof b, ".SO %ld %ld %ld %ld %ld", sAx(STG_HWLO_X, 0), sAx(STG_HWLO_X, 1), sAx(STG_HWLO_X, 2), sAx(STG_HWLO_X, 3), sAx(STG_HWLO_X, 4));
    link.push(b, T_GEN);
    homeStep_ = 2;
  }
  if (homeStep_ >= 2 && homeStep_ <= 5) {          // one axis per step
    int a = order[homeStep_ - 2];
    if (homeT0_ == 0) {
      int f[5] = {0, 0, 0, 0, 0};
      f[a] = 1;
      snprintf(b, sizeof b, ".SE %d %d %d %d %d", f[0], f[1], f[2], f[3], f[4]);
      link.push(b, T_GEN);
      homeT0_ = now;
      homeSeq_ = sdSeq_;
      snprintf(homeAct_, sizeof homeAct_, "Homing %c", AXN[a]);
      return;
    }
    // Wait at least 1 s and two fresh .SD replies, then for the axis to be stopped and initialised.
    if (now - homeT0_ > 1000 && sdSeq_ >= homeSeq_ + 2 && !ax_[a].moving && ax_[a].init) {
      homeT0_ = 0;
      homeStep_++;
    } else if (now - homeT0_ > (uint32_t)(sf(STG_MOVE_TO_S) * 1000)) {
      link.push(".SK", T_GEN, true);
      logf(LV_FAULT, "stg", "homing %c timed out", AXN[a]);
      homeStep_ = 0; homeT0_ = 0; homeAct_[0] = 0;
    }
    return;
  }
  if (homeStep_ == 6) {
    snprintf(b, sizeof b, ".SA %ld %ld %ld %ld %ld", sAx(STG_HOME_X, 0), sAx(STG_HOME_X, 1), sAx(STG_HOME_X, 2), sAx(STG_HOME_X, 3), sAx(STG_HOME_X, 4));
    link.push(b, T_GEN);
    sendLimits();
    snprintf(b, sizeof b, ".SB %ld %ld %ld %ld %ld", sAx(STG_PSPD_X, 0), sAx(STG_PSPD_X, 1), sAx(STG_PSPD_X, 2), sAx(STG_PSPD_X, 3), sAx(STG_PSPD_X, 4));
    link.push(b, T_GEN);
    snprintf(b, sizeof b, ".SF %ld %ld %ld %ld %ld", sAx(STG_PARK_X, 0), sAx(STG_PARK_X, 1), sAx(STG_PARK_X, 2), sAx(STG_PARK_X, 3), sAx(STG_PARK_X, 4));
    link.push(b, T_GEN);
    snprintf(homeAct_, sizeof homeAct_, "Moving to start position");
    homeStep_ = 0;
    wasHomed_ = true;
    logf(LV_INFO, "stg", "stage initialised");
  }
}

void StgVac::parseHex(const char* r, uint8_t* out, int n) {
  const char* p = r + 3;                              // past "=SS"
  for (int i = 0; i < n; i++) {
    while (*p == ' ') p++;
    if (!*p) { out[i] = 0; continue; }
    out[i] = (uint8_t)strtol(p, (char**)&p, 16);
  }
}

void StgVac::parseVT(const char* r) {
  // "=00 NCP 0 N N N <state> <gauge> N N"
  char buf[96];
  strlcpy(buf, r, sizeof buf);
  char* tok[12];
  int nt = 0;
  for (char* t = strtok(buf, " "); t && nt < 12; t = strtok(nullptr, " ")) tok[nt++] = t;
  if (nt < 8) return;
  VacState s = VS_OTHER;
  const char* st = tok[6];
  if (!strcmp(st, "NSP")) s = VS_NSP;
  else if (!strcmp(st, "WTUS")) s = VS_WTUS;
  else if (!strcmp(st, "WP")) s = VS_WP;
  else if (!strcmp(st, "SP")) s = VS_SP;
  else if (!strcmp(st, "SPVR")) s = VS_SPVR;
  else if (!strcmp(st, "SPE")) s = VS_SPE;
  else if (!strcmp(st, "WVT")) s = VS_WVT;
  gauge_ = atol(tok[7]);
  if (s != vac_) {
    VacState old = vac_;
    vac_ = s;
    logf(s == VS_SPE ? LV_WARN : LV_INFO, "vac", "vacuum %s -> %s", vacCode(old), vacName());
    bool air = !(s == VS_SP || s == VS_SPVR);
    if (configured_ && s != VS_SPE && (!limitsValid_ || air != airLimits_)) sendLimits();
  }
}

void StgVac::parseSD(const char* r) {
  // "=00 X <pos> <m> <i> Y ... R <pos> <m> <i>"
  char buf[128];
  strlcpy(buf, r, sizeof buf);
  char* tok[24];
  int nt = 0;
  for (char* t = strtok(buf, " "); t && nt < 24; t = strtok(nullptr, " ")) tok[nt++] = t;
  if (nt < 21) return;
  bool lost = false;
  for (int a = 0; a < 5; a++) {
    int k = 1 + a * 4;
    if (tok[k][0] != AXN[a]) return;
    bool init = tok[k + 3][0] == 'I';
    if (ax_[a].init && !init && sdValid_) lost = true;
    ax_[a].pos = atol(tok[k + 1]);
    ax_[a].moving = tok[k + 2][0] == 'M';
    ax_[a].init = init;
  }
  sdValid_ = true;
  sdSeq_++;
  if (lost) logf(LV_WARN, "stg", "stage controller lost its position: initialise again");
}

void StgVac::onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* c, const char* r) {
  ((StgVac*)ctx)->onReply(tag, ok, c, r);
}

void StgVac::onReply(uint8_t tag, bool ok, const char* cmd, const char* r) {
  if (tag == TAG_UNSOLICITED) return;
  if (!ok) {
    if (wasOnline_) logf(LV_WARN, "stg", "no reply to %s: link down", cmd);
    wasOnline_ = false;
    if (!configured_) { cfgIdx_ = -1; link.clearQueue(); }
    return;
  }
  if (!wasOnline_) { wasOnline_ = true; logf(LV_INFO, "stg", "link up"); needVS_ = true; }
  if (r[0] != '=' || strlen(r) < 3) return;
  char hx[3] = { r[1], r[2], 0 };
  int ss = strtol(hx, nullptr, 16);
  if (ss == 0x20) needVS_ = true;
  if (ss == 0x40) needSP_ = true;
  if (ss != 0x00 && ss != 0x20 && ss != 0x40) logf(LV_WARN, "stg", "%s -> unexpected status %s", cmd, r);

  switch (tag) {
    case T_VT: parseVT(r); break;
    case T_CFGEND:
      parseVT(r);
      configured_ = true;
      sendLimits();
      logf(LV_INFO, "stg", "configured (comms %s, vacuum %s)", vx_, vv_);
      snprintf(ver_, sizeof ver_, "%s/%s", vx_, vv_);
      break;
    case T_SD: parseSD(r); break;
    case T_VS: {
      uint8_t old0 = vs_[0];
      parseHex(r, vs_, 8);
      if (vsValid_ && old0 != vs_[0]) logf(LV_INFO, "vac", "inhibits %02X -> %02X", old0, vs_[0]);
      vsValid_ = true;
      if (vs_[2] & 0x01) logf(LV_WARN, "vac", "Penning gauge failure");
      // b1 = 02 (EDX) reappears after a controller power-up until .CF N: configure again.
      if (configured_ && (vs_[1] & 0x02)) {
        logf(LV_WARN, "stg", "controller restarted: configuring again");
        configured_ = false; cfgIdx_ = -1; limitsValid_ = false; swSent_ = 0;
      }
      break;
    }
    case T_SP: {
      parseHex(r, sp_, 6);
      bool any = false;
      for (int i = 0; i < 6; i++) if (sp_[i]) any = true;
      if (any && !spEvent_) {
        for (int a = 0; a < 5; a++)
          if (sp_[a + 1] & 0x02) logf(LV_WARN, "stg", "%c on a limit switch", AXN[a]);
      }
      spEvent_ = any;
      break;
    }
    case T_VX: case T_VV: {
      char* dst = tag == T_VX ? vx_ : vv_;
      int i = strlen(dst);
      if (i < 7) { char c = (char)strtol(r + 3, nullptr, 16); dst[i] = (c >= 0x20 && c < 0x7F) ? c : ' '; dst[i + 1] = 0; }
      break;
    }
    default: break;
  }
}

void StgVac::service() {
  link.service();
  if (link.inflight() || link.queued() > 0) { if (configured_) homeService(); return; }
  uint32_t now = millis();

  if (!configured_) {
    if (cfgIdx_ < 0) {
      if (now - lastVT_ < (uint32_t)si(STG_POLL_MS)) return;      // retry pace while offline
      lastVT_ = now;
      cfgIdx_ = 0; vx_[0] = vv_[0] = 0;
    }
    char b[80]; uint8_t tag;
    for (int k = 0; k < 6; k++) {
      if (!configCmd(cfgIdx_, b, sizeof b, tag)) { cfgIdx_ = -1; return; }
      link.push(b, tag);
      cfgIdx_++;
    }
    return;
  }

  homeService();
  if (link.queued() > 0) return;
  if (needVS_) { needVS_ = false; link.push(".VS", T_VS); return; }
  if (needSP_ && now - lastSP_ >= (uint32_t)si(STG_SP_MS)) { lastSP_ = now; needSP_ = false; link.push(".SP", T_SP); return; }
  if (now - lastVT_ >= (uint32_t)si(STG_POLL_MS)) { lastVT_ = now; link.push(".VT", T_VT); return; }
  uint32_t sdp = (moving() || homing()) ? si(STG_POLL_MOVE_MS) : si(STG_POLL_MS);
  if (now - lastSD_ >= sdp) { lastSD_ = now; link.push(".SD", T_SD); return; }
  // Joystick pixel size: the local joystick moves a constant number of screen pixels per second.
  if (mag_ > 0) {
    long nm = lround(sd(STG_JOY_FIELD_M) * sd(STG_JOY_GAIN) / mag_ / 1e-9);
    if (nm < 1) nm = 1;
    if (swSent_ == 0 || fabs((double)nm - swSent_) > sd(STG_JOY_HYST) * swSent_) {
      char b[24];
      snprintf(b, sizeof b, ".SW %ld", nm);
      link.push(b, T_GEN);
      swSent_ = nm;
    }
  }
}
