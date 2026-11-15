#include "usb.h"
#include "config.h"
#include "settings.h"
#include "log.h"
#include "eht.h"
#include "stgvac.h"
#include "vp.h"
#include "eo.h"
#include "machine.h"
#include <math.h>

extern bool btnState(int i);

static char line[256];
static int lineN = 0;
static bool connected = false;
static uint32_t telMs = 250, lastTel = 0, lastCmd = 0, drops = 0;
static int listCursor = -1;          // streaming "list"
static char listPrefix[24];
static long listId = -1;
static int listCount = 0;

bool usbConnected() { return connected; }
uint32_t usbLastCmdMs() { return lastCmd; }

// ------------------------------------------------------------------ output

static bool out(const char* s) {
  if (!connected) return false;
  size_t n = strlen(s);
  if ((size_t)Serial.availableForWrite() < n + 1) { drops++; return false; }
  Serial.write(s, n);
  Serial.write('\n');
  return true;
}

// Tiny JSON writer into a fixed buffer.
struct J {
  char* b; size_t n; size_t len = 0; bool first = true;
  J(char* buf, size_t sz) : b(buf), n(sz) { b[0] = 0; }
  void raw(const char* s) { size_t l = strlen(s); if (len + l < n) { memcpy(b + len, s, l + 1); len += l; } }
  void fmt(const char* f, ...) __attribute__((format(printf, 2, 3))) {
    va_list ap; va_start(ap, f);
    int w = vsnprintf(b + len, n - len, f, ap);
    va_end(ap);
    if (w > 0) len = min(len + (size_t)w, n - 1);
  }
  void sep() { if (!first) raw(","); first = false; }
  void open(const char* k = nullptr) { sep(); if (k) fmt("\"%s\":", k); raw("{"); first = true; }
  void openArr(const char* k) { sep(); fmt("\"%s\":[", k); first = true; }
  void close() { raw("}"); first = false; }
  void closeArr() { raw("]"); first = false; }
  void key(const char* k) { sep(); fmt("\"%s\":", k); }
  void str(const char* k, const char* v) {
    key(k); raw("\"");
    for (const char* p = v; *p && len < n - 8; p++) {
      if (*p == '"' || *p == '\\') { char e[3] = { '\\', *p, 0 }; raw(e); }
      else if ((uint8_t)*p < 0x20) fmt("\\u%04x", (uint8_t)*p);
      else { char c[2] = { *p, 0 }; raw(c); }
    }
    raw("\"");
  }
  void num(const char* k, double v, int prec = 6) {
    key(k);
    if (isnan(v) || isinf(v)) raw("null"); else fmt("%.*g", prec, v);
  }
  void i(const char* k, long v) { key(k); fmt("%ld", v); }
  void bo(const char* k, bool v) { key(k); raw(v ? "true" : "false"); }
  void ai(long v) { sep(); fmt("%ld", v); }
  void ad(double v, int prec = 7) { sep(); fmt("%.*g", prec, v); }
};

static const char* ridStr(long id) {
  static char b[24];
  if (id < 0) return "";
  snprintf(b, sizeof b, "\"r\":%ld,", id);
  return b;
}

static void reply(long id, bool ok, const char* err = nullptr) {
  char b[200]; J j(b, sizeof b); j.open();
  if (id >= 0) j.i("r", id);
  j.bo("ok", ok);
  if (err) j.str("err", err);
  j.close();
  out(b);
}

void usbLogHook(const LogEntry& e) {
  if (!connected) return;
  char b[240]; J j(b, sizeof b); j.open();
  j.str("t", "ev"); j.i("ms", e.ms); j.i("rtc", e.rtc);
  j.str("lvl", logLevelName(e.lvl)); j.str("src", e.src); j.str("msg", e.msg);
  j.close();
  out(b);
}

void usbTraceHook(const char* link, char dir, const char* text) {
  if (!connected) return;
  char b[200]; J j(b, sizeof b); j.open();
  char d[2] = { dir, 0 };
  j.str("t", "tr"); j.i("ms", millis()); j.str("l", link); j.str("d", d); j.str("s", text);
  j.close();
  out(b);
}

void jsonStatus(char* buf, size_t n) {
  J j(buf, n);
  j.open();
  j.str("t", "st"); j.i("up", millis()); j.i("rtc", rtc_get());
  j.open("sys");
    j.str("op", machine.opName()); j.str("act", machine.activity()); j.str("sum", machine.summary());
    j.bo("dirty", settingsDirty()); j.i("drops", drops);
  j.close();
  j.open("vac");
    j.bo("link", stg.link.online); j.bo("cfg", stg.configured()); j.str("st", stg.vacName()); j.str("txt", stg.vacText());
    j.i("raw", stg.gauge()); j.num("torr", stg.torr(), 3); j.i("inh", stg.inhibits()); j.bo("ready", stg.vacReady());
    j.str("ver", stg.version());
  j.close();
  j.open("vp");
    j.bo("link", vp.online()); j.bo("hs", vp.ready()); j.i("st", vp.state()); j.str("name", vp.stateName());
    j.i("req", vp.requested()); j.i("gauge", vp.gauge()); j.num("pa", vp.pa(), 4); j.num("tgt", sf(OP_VP_PA), 4);
    j.i("v8", vp.v8()); j.i("v14", vp.v14()); j.i("err", vp.error());
  j.close();
  j.open("eht");
    j.bo("link", eht.link.online); j.bo("ready", eht.ready()); j.str("beam", eht.beamName());
    j.i("sb", eht.statusValid() ? eht.status() : -1); j.i("word", eht.word());
    j.num("kv", eht.kvApplied(), 4); j.num("kvset", sf(OP_KV), 4);
    j.i("fil", eht.filApplied()); j.i("filset", si(OP_FIL_MA)); j.num("emis", sf(OP_EMIS_UA), 4);
    j.num("coll", sf(OP_COLL_V), 4); j.i("pm1", si(OP_PM1)); j.num("cool", eht.coolRemainingS(), 3);
    j.bo("cold", eht.filCold()); j.str("act", eht.activity()); j.str("id", eht.hwid());
  j.close();
  j.open("stg");
    j.bo("valid", stg.sdValid()); j.bo("homed", stg.homed()); j.bo("mv", stg.moving()); j.bo("lim", stg.limitActive());
    j.bo("homing", stg.homing());
    j.openArr("pos");
    for (int a = 0; a < 5; a++) { if (stg.sdValid()) j.ad(StgVac::toUnits(a, stg.axis(a).pos), 7); else { j.sep(); j.raw("null"); } }
    j.closeArr();
    j.openArr("c"); for (int a = 0; a < 5; a++) j.ai(stg.axis(a).pos); j.closeArr();
  j.close();
  j.open("eo");
    j.bo("link", eo.linkOk()); j.str("mode", eo.modeName()); j.num("mag", sf(OP_MAG)); j.i("range", eo.range());
    j.i("speed", si(OP_SPEED)); j.num("rot", sf(OP_ROT)); j.num("wd", sf(OP_WD)); j.num("tilt", sf(OP_TILT));
    j.num("objc", sf(OP_OBJ_C)); j.num("focus", sf(OP_OBJ_F)); j.i("stigx", si(OP_STIG_X)); j.i("stigy", si(OP_STIG_Y));
    { double lo = 0, hi = 0; Eo::probeRange(lo, hi);
      j.num("probe", sf(OP_PROBE_PA)); j.num("pcmin", lo); j.num("pcmax", hi); j.bo("obeam", si(EO_OPTIBEAM)); }
    j.num("wob", sf(OP_WOB_PCT)); j.bo("frz", eo.frozen()); j.i("frames", eo.frames()); j.i("q", eo.queued());
    j.num("line_us", eo.linePeriodUs());
  j.close();
  j.openArr("btn"); for (int i = 0; i < 3; i++) j.ai(btnState(i)); j.closeArr();
  j.close();
}

static void settingJson(char* b, size_t n, int id, long rid) {
  const SettingMeta& m = SMETA[id];
  J j(b, n); j.open();
  if (rid >= 0) { j.i("r", rid); j.bo("ok", true); } else j.str("t", "set");
  char v[32]; settingFormat(id, v, sizeof v);
  j.str("name", m.name); j.key("value"); j.raw(v);
  j.num("def", m.def, 10); j.num("min", m.mn, 10); j.num("max", m.mx, 10);
  j.str("unit", m.unit); j.i("flags", m.flags); j.str("desc", m.desc);
  j.close();
}

// ------------------------------------------------------------------ commands

static long toks(char* s, char** t, int max) {
  int n = 0;
  for (char* p = strtok(s, " \t"); p && n < max; p = strtok(nullptr, " \t")) t[n++] = p;
  return n;
}

static bool num(const char* s, double& v) {
  char* e; v = strtod(s, &e);
  return e != s && *e == 0 && isfinite(v);
}

static const char* setOp(SettingId id, double v) {
  // Operator limits that are tighter than the setting's own range
  switch (id) {
    case OP_KV: if (v < sd(EHT_KV_MIN) || v > sd(EHT_KV_MAX)) return "kV outside eht.kv_min..eht.kv_max"; break;
    case OP_FIL_MA: if (v > sd(EHT_FIL_MAX_MA)) return "above eht.fil_max_ma"; break;
    case OP_EMIS_UA: if (v > sd(EHT_EMIS_MAX_UA)) return "above eht.emis_max_ua"; break;
    case OP_MAG: if (v < sd(EO_MAG_MIN) || v > sd(EO_MAG_MAX)) return "magnification outside eo.mag_min..eo.mag_max"; break;
    case OP_VP_PA: return machine.vpTarget(v);
    case OP_PROBE_PA: {
      double lo, hi;
      if (si(EO_OPTIBEAM) && Eo::probeRange(lo, hi) && (v < lo || v > hi)) return "probe current outside the calibrated range (eo.pc* table)";
      break;
    }
    default: break;
  }
  return settingSet(id, v);
}

static void cmdStage(long id, char** t, int n) {
  if (n < 2) { reply(id, false, "stage goto|move|stop|home"); return; }
  if (!strcmp(t[1], "stop")) { stg.stop(); reply(id, true); return; }
  if (!strcmp(t[1], "home")) { const char* e = stg.home(); reply(id, !e, e); return; }
  bool rel = !strcmp(t[1], "move");
  if (!rel && strcmp(t[1], "goto")) { reply(id, false, "unknown stage command"); return; }
  if (!stg.sdValid()) { reply(id, false, "no stage position yet"); return; }
  long c[5];
  for (int a = 0; a < 5; a++) {
    c[a] = stg.axis(a).pos;
    if (2 + a >= n || !strcmp(t[2 + a], "-") || !strcmp(t[2 + a], "*")) continue;
    double v;
    if (!num(t[2 + a], v)) { reply(id, false, "bad number"); return; }
    if (rel) c[a] = stg.axis(a).pos + lround(v * sd((SettingId)(STG_CPU_X + a)));
    else c[a] = StgVac::toCounts(a, v);
  }
  const char* e = stg.gotoCounts(c);
  reply(id, !e || !strcmp(e, "clamped to limits"), e);
}

static void command(char* s) {
  char* t[12];
  long id = -1;
  int n = toks(s, t, 12);
  if (n == 0) return;
  if (t[0][0] == '#') {
    id = atol(t[0] + 1);
    for (int i = 1; i < n; i++) t[i - 1] = t[i];
    n--;
    if (n == 0) { reply(id, false, "empty command"); return; }
  }
  for (char* p = t[0]; *p; p++) *p = tolower(*p);
  lastCmd = millis();
  const char* c = t[0];
  double v = 0, v2 = 0;
  const char* err = nullptr;

  if (!strcmp(c, "hello") || !strcmp(c, "ver")) {
    char b[200]; J j(b, sizeof b); j.open();
    if (id >= 0) j.i("r", id);
    j.bo("ok", true); j.str("fw", FW_NAME); j.str("ver", FW_VERSION); j.i("proto", PROTO_VER);
    j.i("settings", S_COUNT); j.i("up", millis());
    j.close(); out(b);
  }
  else if (!strcmp(c, "status")) {
    static char b[2048]; jsonStatus(b, sizeof b);
    if (id >= 0) { size_t l = strlen(b); snprintf(b + l - 1, sizeof b - l + 1, ",\"r\":%ld,\"ok\":true}", id); }
    out(b);
  }
  else if (!strcmp(c, "tel")) {
    if (n < 2 || !num(t[1], v) || v < 0) { reply(id, false, "tel <ms>"); return; }
    telMs = (uint32_t)v; reply(id, true);
  }
  else if (!strcmp(c, "get")) {
    int k = n >= 2 ? settingFind(t[1]) : -1;
    if (k < 0) { reply(id, false, "unknown setting"); return; }
    char b[400]; settingJson(b, sizeof b, k, id); out(b);
  }
  else if (!strcmp(c, "set")) {
    int k = n >= 2 ? settingFind(t[1]) : -1;
    if (k < 0) { reply(id, false, "unknown setting"); return; }
    if (SMETA[k].flags & FL_ST) { reply(id, false, "internal state, read only"); return; }
    if (n < 3 || !num(t[2], v)) { reply(id, false, "set <name> <value>"); return; }
    err = (SMETA[k].flags & FL_OP) ? setOp((SettingId)k, v) : settingSet(k, v);
    reply(id, !err, err);
  }
  else if (!strcmp(c, "list")) {
    strlcpy(listPrefix, n >= 2 ? t[1] : "", sizeof listPrefix);
    listCursor = 0; listId = id; listCount = 0;
  }
  else if (!strcmp(c, "default")) {
    if (n < 2) { reply(id, false, "default <name>|all"); return; }
    if (!strcmp(t[1], "all")) {
      for (int k = 0; k < S_COUNT; k++) if (!(SMETA[k].flags & (FL_ST | FL_OP))) settingDefault(k);
      reply(id, true);
    } else {
      int k = settingFind(t[1]);
      if (k < 0 || (SMETA[k].flags & FL_ST)) { reply(id, false, "unknown setting"); return; }
      settingDefault(k); reply(id, true);
    }
  }
  else if (!strcmp(c, "save")) { reply(id, settingsSaveNow(), nullptr); }
  // ---- machine actions
  else if (!strcmp(c, "pump")) { err = machine.pump(); reply(id, !err, err); }
  else if (!strcmp(c, "vent")) { err = machine.vent(); reply(id, !err, err); }
  else if (!strcmp(c, "beam")) {
    if (n >= 2 && !strcmp(t[1], "on")) err = machine.beamOn();
    else if (n >= 2 && !strcmp(t[1], "off")) err = machine.beamOff();
    else err = "beam on|off";
    reply(id, !err, err);
  }
  else if (!strcmp(c, "eht")) {
    if (n >= 2 && !strcmp(t[1], "off")) err = machine.ehtOff();
    else if (n >= 2 && !strcmp(t[1], "reset")) eht.resetFaults();
    else err = "eht off|reset";
    reply(id, !err, err);
  }
  else if (!strcmp(c, "safe")) { machine.safe("USB command"); reply(id, true); }
  else if (!strcmp(c, "abort")) { machine.abort(); reply(id, true); }
  else if (!strcmp(c, "vp")) {
    if (n >= 2 && !strcmp(t[1], "enter")) err = machine.vpEnter(n >= 3 && num(t[2], v) ? v : sf(OP_VP_PA));
    else if (n >= 2 && !strcmp(t[1], "exit")) err = machine.vpExit();
    else if (n >= 3 && !strcmp(t[1], "target") && num(t[2], v)) err = machine.vpTarget(v);
    else if (n >= 2 && !strcmp(t[1], "reset")) vp.reset();
    else err = "vp enter [Pa]|exit|target <Pa>|reset";
    reply(id, !err, err);
  }
  // ---- setpoints (each maps to an op.* setting; the subsystems follow it)
  else if (!strcmp(c, "kv") || !strcmp(c, "fil") || !strcmp(c, "emis") || !strcmp(c, "coll") ||
           !strcmp(c, "bright") || !strcmp(c, "mag") || !strcmp(c, "rot") || !strcmp(c, "wd") ||
           !strcmp(c, "tilt") || !strcmp(c, "speed") || !strcmp(c, "dynfocus") || !strcmp(c, "line") || !strcmp(c, "probe")) {
    static const struct { const char* n; SettingId id; } m[] = {
      {"kv", OP_KV}, {"fil", OP_FIL_MA}, {"emis", OP_EMIS_UA}, {"coll", OP_COLL_V}, {"bright", OP_PM1},
      {"mag", OP_MAG}, {"rot", OP_ROT}, {"wd", OP_WD}, {"tilt", OP_TILT}, {"speed", OP_SPEED},
      {"dynfocus", OP_DYNF}, {"line", OP_LINE_Y}, {"probe", OP_PROBE_PA} };
    SettingId k = OP_KV;
    for (auto& e : m) if (!strcmp(c, e.n)) k = e.id;
    if (n < 2 || !num(t[1], v)) { reply(id, false, "value expected"); return; }
    err = setOp(k, v);
    reply(id, !err, err);
  }
  else if (!strcmp(c, "pm")) {
    if (n < 3 || !num(t[1], v) || !num(t[2], v2) || v < 1 || v > 3) { reply(id, false, "pm <1-3> <value>"); return; }
    err = setOp((SettingId)(OP_PM1 + (int)v - 1), v2); reply(id, !err, err);
  }
  else if (!strcmp(c, "focus")) {
    if (n < 2 || !num(t[1], v)) { reply(id, false, "focus <fine> [coarse]"); return; }
    err = setOp(OP_OBJ_F, v);
    if (!err && n >= 3 && num(t[2], v2)) err = setOp(OP_OBJ_C, v2);
    reply(id, !err, err);
  }
  else if (!strcmp(c, "stig") || !strcmp(c, "shift") || !strcmp(c, "spot")) {
    SettingId a = !strcmp(c, "stig") ? OP_STIG_X : !strcmp(c, "shift") ? OP_SHIFT_X : OP_SPOT_X;
    if (n < 3 || !num(t[1], v) || !num(t[2], v2)) { reply(id, false, "two values expected"); return; }
    err = setOp(a, v);
    if (!err) err = setOp((SettingId)(a + 1), v2);
    reply(id, !err, err);
  }
  else if (!strcmp(c, "cond")) {
    if (si(EO_OPTIBEAM)) { reply(id, false, "Optibeam is on: set the probe current (eo.optibeam 0 for direct condenser values)"); return; }
    if (n < 5) { reply(id, false, "cond <d0> <d1> <d2> <d3>"); return; }
    for (int i = 0; i < 4 && !err; i++) { if (!num(t[1 + i], v)) err = "bad number"; else err = setOp((SettingId)(OP_COND0 + i), v); }
    reply(id, !err, err);
  }
  else if (!strcmp(c, "scan")) {
    static const char* modes[] = { "ext", "raster", "line", "spot" };
    int m = -1;
    for (int i = 0; i < 4; i++) if (n >= 2 && !strcmp(t[1], modes[i])) m = i;
    if (m < 0) { reply(id, false, "scan ext|raster|line|spot"); return; }
    err = setOp(OP_SCAN, m); reply(id, !err, err);
  }
  else if (!strcmp(c, "wobble")) {
    if (n < 2 || !num(t[1], v)) { reply(id, false, "wobble <percent> [fast|slow]"); return; }
    if (n >= 3) setOp(OP_WOB_FAST, strcmp(t[2], "slow") ? 1 : 0);
    err = setOp(OP_WOB_PCT, v); reply(id, !err, err);
  }
  else if (!strcmp(c, "freeze")) { eo.freeze(n >= 2 && !strcmp(t[1], "on")); reply(id, true); }
  else if (!strcmp(c, "stage")) cmdStage(id, t, n);
  else if (!strcmp(c, "eo")) {
    if (n >= 2 && !strcmp(t[1], "restore")) { eo.restoreAll(); reply(id, true); return; }
    double ch, rg;
    if (n >= 4 && !strcmp(t[1], "r") && num(t[2], ch) && num(t[3], rg)) {
      int r = eo.readNow((int)ch, (int)rg);
      char b[80]; snprintf(b, sizeof b, "{%s\"ok\":%s,\"value\":%d}", id >= 0 ? ridStr(id) : "", r >= 0 ? "true" : "false", r);
      out(b); return;
    }
    if (n >= 5 && !strcmp(t[1], "w") && num(t[2], ch) && num(t[3], rg) && num(t[4], v)) {
      if (!si(DBG_RAW)) { reply(id, false, "raw writes need dbg.raw = 1"); return; }
      eo.write((int)ch, (int)rg, (uint16_t)v); reply(id, true); return;
    }
    reply(id, false, "eo restore | eo r <chip> <reg> | eo w <chip> <reg> <value>");
  }
  else if (!strcmp(c, "raw")) {
    if (!si(DBG_RAW)) { reply(id, false, "raw commands need dbg.raw = 1 (they bypass the interlocks)"); return; }
    if (n < 3) { reply(id, false, "raw eht|stg|vp <text>"); return; }
    char txt[80] = "";
    for (int i = 2; i < n; i++) { if (i > 2) strlcat(txt, " ", sizeof txt); strlcat(txt, t[i], sizeof txt); }
    Link* l = !strcmp(t[1], "eht") ? &eht.link : !strcmp(t[1], "stg") ? &stg.link : !strcmp(t[1], "vp") ? &vp.link : nullptr;
    if (!l) { reply(id, false, "raw eht|stg|vp <text>"); return; }
    l->trace = true;                                  // the reply shows up as a trace line
    l->push(txt, 0);
    reply(id, true);
  }
  else if (!strcmp(c, "trace")) {
    const char* w = n >= 2 ? t[1] : "all";
    bool off = !strcmp(w, "off");
    if (off || !strcmp(w, "all")) { eht.link.trace = stg.link.trace = vp.link.trace = !off; }
    else if (!strcmp(w, "eht")) eht.link.trace = true;
    else if (!strcmp(w, "stg")) stg.link.trace = true;
    else if (!strcmp(w, "vp")) vp.link.trace = true;
    else { reply(id, false, "trace eht|stg|vp|all|off"); return; }
    reply(id, true);
  }
  else if (!strcmp(c, "log")) {
    int k = n >= 2 ? atoi(t[1]) : LOG_DEPTH;
    for (int a = min(k, logCount()) - 1; a >= 0; a--) usbLogHook(*logGet(a));
    reply(id, true);
  }
  else if (!strcmp(c, "time")) {
    if (n >= 2 && num(t[1], v) && v > 1.6e9) { rtc_set((unsigned long)v); reply(id, true); }
    else { char b[64]; snprintf(b, sizeof b, "{%s\"ok\":true,\"rtc\":%lu}", id >= 0 ? ridStr(id) : "", rtc_get()); out(b); }
  }
  else if (!strcmp(c, "reboot")) { reply(id, true); Serial.flush(); delay(20); SCB_AIRCR = 0x05FA0004; }
  else if (!strcmp(c, "bootloader")) { reply(id, true); Serial.flush(); delay(20); _reboot_Teensyduino_(); }
  else if (!strcmp(c, "help")) {
    out("{\"t\":\"help\",\"cmds\":\"hello status tel get set list default save pump vent beam eht safe abort vp kv fil emis coll bright pm "
        "mag rot wd tilt speed probe scan spot line focus stig shift cond wobble dynfocus freeze stage eo raw trace log time reboot bootloader\"}");
    reply(id, true);
  }
  else reply(id, false, "unknown command");
}

// ------------------------------------------------------------------ service

void usbBegin() {
  Serial.begin(115200);              // USB: the rate is ignored
  telMs = si(USB_TEL_MS);
}

void usbService() {
  bool c = (bool)Serial;             // USB configured and the port opened (DTR)
  if (c && !connected) {
    connected = true;
    lineN = 0; listCursor = -1;
    telMs = si(USB_TEL_MS);
    char b[160];
    snprintf(b, sizeof b, "{\"t\":\"hello\",\"fw\":\"%s\",\"ver\":\"%s\",\"proto\":%d}", FW_NAME, FW_VERSION, PROTO_VER);
    out(b);
  } else if (!c && connected) {
    connected = false;
    eht.link.trace = stg.link.trace = vp.link.trace = false;
  }
  // Input: read whatever is there (also while disconnected, to keep the buffer empty).
  int budget = 512;
  while (Serial.available() && budget-- > 0) {
    int ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (lineN) { line[lineN] = 0; if (connected) command(line); lineN = 0; }
    } else if (lineN < (int)sizeof(line) - 1) {
      line[lineN++] = (char)ch;
    }
  }
  if (!connected) return;
  // Streaming "list"
  if (listCursor >= 0) {
    char b[420];
    while (listCursor < S_COUNT) {
      int k = listCursor;
      if (strncmp(SMETA[k].name, listPrefix, strlen(listPrefix)) != 0) { listCursor++; continue; }
      if (Serial.availableForWrite() < 480) return;     // continue next loop
      settingJson(b, sizeof b, k, -1);
      out(b);
      listCount++;
      listCursor++;
    }
    char e[80];
    snprintf(e, sizeof e, "{%s\"ok\":true,\"count\":%d}", listId >= 0 ? ridStr(listId) : "", listCount);
    if (out(e)) listCursor = -1;
    return;
  }
  uint32_t now = millis();
  if (telMs && now - lastTel >= telMs) {
    lastTel = now;
    static char b[2048];
    jsonStatus(b, sizeof b);
    out(b);
  }
}
