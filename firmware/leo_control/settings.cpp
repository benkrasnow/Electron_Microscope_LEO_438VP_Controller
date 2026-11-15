#include "settings.h"
#include "log.h"
#include <LittleFS.h>

double S[S_COUNT];

const SettingMeta SMETA[S_COUNT] = {
#define X(id, name, def, mn, mx, unit, flags, desc) { name, def, mn, mx, unit, flags, desc },
  SETTINGS_TABLE(X)
#undef X
};

static LittleFS_Program fs;
static bool fsOk = false;
static bool dirty = false;
static uint32_t lastChangeMs = 0;

static const char* FILE_MAIN = "/settings.txt";
static const char* FILE_TMP  = "/settings.tmp";

int settingFind(const char* name) {
  for (int i = 0; i < S_COUNT; i++)
    if (strcmp(SMETA[i].name, name) == 0) return i;
  return -1;
}

void settingFormat(int id, char* buf, size_t n) {
  if (SMETA[id].flags & FL_INT) snprintf(buf, n, "%ld", (long)lround(S[id]));
  else snprintf(buf, n, "%.7g", S[id]);
}

static bool loadFile(const char* path) {
  File f = fs.open(path, FILE_READ);
  if (!f) return false;
  char line[96];
  int n = 0, loaded = 0;
  while (f.available()) {
    int c = f.read();
    if (c == '\n' || n == (int)sizeof(line) - 1) {
      line[n] = 0;
      n = 0;
      char* eq = strchr(line, '=');
      if (!eq) continue;
      *eq = 0;
      int id = settingFind(line);
      if (id < 0) continue;                      // setting removed in this firmware
      double v = strtod(eq + 1, nullptr);
      if (v >= SMETA[id].mn && v <= SMETA[id].mx) { S[id] = v; loaded++; }
    } else if (c != '\r') {
      line[n++] = (char)c;
    }
  }
  f.close();
  logf(LV_INFO, "set", "loaded %d settings from %s", loaded, path);
  return true;
}

void settingsBegin() {
  for (int i = 0; i < S_COUNT; i++) S[i] = SMETA[i].def;
  fsOk = fs.begin(256 * 1024);
  if (!fsOk) {
    logf(LV_WARN, "set", "flash file system unavailable: defaults only, nothing will be saved");
    return;
  }
  if (!loadFile(FILE_MAIN) && !loadFile(FILE_TMP))
    logf(LV_INFO, "set", "no saved settings: using defaults");
}

bool settingsSaveNow() {
  if (!fsOk) return false;
  fs.remove(FILE_TMP);
  File f = fs.open(FILE_TMP, FILE_WRITE);
  if (!f) return false;
  char v[32];
  for (int i = 0; i < S_COUNT; i++) {
    if (S[i] == SMETA[i].def) continue;          // only store what differs from the default
    settingFormat(i, v, sizeof v);
    if (!(SMETA[i].flags & FL_INT)) snprintf(v, sizeof v, "%.10g", S[i]);
    f.print(SMETA[i].name); f.print('='); f.print(v); f.print('\n');
  }
  f.close();
  fs.remove(FILE_MAIN);
  fs.rename(FILE_TMP, FILE_MAIN);
  dirty = false;
  return true;
}

const char* settingSet(int id, double v) {
  if (id < 0 || id >= S_COUNT) return "unknown setting";
  const SettingMeta& m = SMETA[id];
  if (!(v >= m.mn && v <= m.mx)) return "out of range";
  if (m.flags & FL_INT) v = (double)lround(v);
  if (S[id] == v) return nullptr;
  S[id] = v;
  settingsTouch();
  settingChanged(id);
  return nullptr;
}

void settingDefault(int id) { settingSet(id, SMETA[id].def); }

void settingsTouch() { dirty = true; lastChangeMs = millis(); }
bool settingsDirty() { return dirty; }

// Flash writes stall the CPU; do them only while no link is waiting for a reply,
// so no UART reply byte can be lost (all remote units only ever answer).
void settingsService(bool linksIdle) {
  if (!dirty || !fsOk || !linksIdle) return;
  if (millis() - lastChangeMs < (uint32_t)si(SYS_SAVE_DELAY_MS)) return;
  if (!settingsSaveNow()) {
    logf(LV_WARN, "set", "settings save failed");
    dirty = false;
  }
}
