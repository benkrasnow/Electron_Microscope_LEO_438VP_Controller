#include "eo.h"
#include "config.h"
#include "settings.h"
#include "log.h"
#include <IntervalTimer.h>

Eo eo;

// Register numbers inside a chip
enum { R_CONTROL = 0x0B, R_ROUTING = 0x0C, R_OPTIONS = 0x0D, R_DAC0 = 0x10, R_1A = 0x1A, R_1B = 0x1B };
#define DAC(n) (R_DAC0 + (n))

// ------------------------------------------------------------------ frame layer
// Frame: bit31 0 | bit30 read | bits29-18 register (chip<<5 | reg) | bits17-2 value | bits1-0 11.
// NRZ, MSB first, idle high, no start/stop bits. Bit-banged with the cycle counter
// (600 MHz CPU: 162.8 cycles per bit), interrupts masked for the ~9 us of a frame.

static volatile uint32_t lastEndCyc = 0;
static uint32_t bitCycQ8 = 41667;         // cycles per bit * 256
static uint32_t gapCyc = 8400;
static uint32_t replyCyc = 24000;
static uint8_t txInv = 0, rxInv = 1;

static inline uint32_t frameWord(int chip, int reg, uint16_t v, bool read) {
  uint32_t n = ((uint32_t)chip << 5) | (reg & 31);
  return (read ? (1u << 30) : 0) | ((n & 0xFFF) << 18) | ((uint32_t)v << 2) | 3u;
}

static inline uint32_t irqSave() { uint32_t pm; __asm__ volatile("mrs %0, primask" : "=r"(pm)); __disable_irq(); return pm; }
static inline void irqRestore(uint32_t pm) { if (!(pm & 1)) __enable_irq(); }

FASTRUN static void shiftOut(uint32_t w) {
  uint32_t t0 = ARM_DWT_CYCCNT;
  for (int i = 0; i < 32; i++) {
    digitalWriteFast(PIN_EO_F3, ((w >> (31 - i)) & 1) ^ txInv);
    uint32_t te = t0 + (((uint32_t)(i + 1) * bitCycQ8) >> 8);
    while ((int32_t)(ARM_DWT_CYCCNT - te) < 0) ;
  }
  digitalWriteFast(PIN_EO_F3, 1 ^ txInv);
}

// One start bit (0) then 16 bits MSB first, sampled mid-bit. -1 on timeout.
FASTRUN static int shiftIn16() {
  uint32_t t0 = ARM_DWT_CYCCNT;
  while ((digitalReadFast(PIN_EO_F4) ^ rxInv) & 1) {
    if (ARM_DWT_CYCCNT - t0 > replyCyc) return -1;
  }
  uint32_t te = ARM_DWT_CYCCNT;
  uint32_t v = 0;
  for (int i = 0; i < 16; i++) {
    uint32_t ts = te + (((uint32_t)(2 * i + 3) * bitCycQ8) >> 9);   // (i + 1.5) bit times
    while ((int32_t)(ARM_DWT_CYCCNT - ts) < 0) ;
    v = (v << 1) | ((digitalReadFast(PIN_EO_F4) ^ rxInv) & 1);
  }
  return (int)v;
}

// Callable from the main loop and from the line interrupt; frames never interleave.
FASTRUN static int frameTx(uint32_t w, bool read) {
  for (;;) {
    while (ARM_DWT_CYCCNT - lastEndCyc < gapCyc) ;
    uint32_t pm = irqSave();
    if (ARM_DWT_CYCCNT - lastEndCyc < gapCyc) { irqRestore(pm); continue; }
    shiftOut(w);
    int r = read ? shiftIn16() : 0;
    lastEndCyc = ARM_DWT_CYCCNT;
    irqRestore(pm);
    return r;
  }
}

// ------------------------------------------------------------------ queue
struct QEnt { uint32_t word; uint32_t delayUs; uint8_t kind; };
enum { K_WRITE, K_READ, K_RESTART, K_PAUSE };
#define QSIZE 512
static QEnt q[QSIZE];
static int qh = 0, qn = 0;
static uint32_t qLastUs = 0, qDelay = 0;
static int c3optSent = -1;

static void qPush(uint32_t word, uint32_t delayUs, uint8_t kind) {
  if (qn >= QSIZE) return;                  // overflow: drop (cannot happen with sane use)
  q[(qh + qn) % QSIZE] = { word, delayUs, kind };
  qn++;
}

// ------------------------------------------------------------------ internal raster
static IntervalTimer tLine, tGate;
static volatile uint8_t rMode = 0;          // 0 off, 1 raster, 2 line
static volatile uint32_t rLine = 0, rLines = 768, rFly = 128, rY0 = 511, rYStep = 84, rPark = 511, rLineY = 32768;
static volatile uint32_t rYwCyc = 16200, rDfCyc = 13200;
static volatile float rGateUs = 550;
static volatile bool rRestart = false, rFreeze = false, rFrozenNow = false;
static volatile float rDynK = 0;
static volatile int32_t rFocus = 2048;
static volatile uint32_t rFrames = 0;
static volatile uint8_t lpol = 1, fpol = 1;

static inline void setF1(bool hi) { digitalWriteFast(PIN_EO_F1, hi ^ txInv); digitalWriteFast(PIN_SYNC_FRAME, hi == (bool)fpol); }
static inline void setF2(bool hi) { digitalWriteFast(PIN_EO_F2, hi ^ txInv); digitalWriteFast(PIN_SYNC_LINE, hi == (bool)lpol); }
static inline void syncIdle() { digitalWriteFast(PIN_SYNC_LINE, !lpol); digitalWriteFast(PIN_SYNC_FRAME, !fpol); }

static void gateIsr() {
  setF2(false);
  tGate.end();
}

FASTRUN static void lineIsr() {
  uint32_t t0 = ARM_DWT_CYCCNT;
  uint32_t y;
  bool active = false;
  if (rMode == 1) {
    if (rRestart) { rLine = 0; rRestart = false; rFrozenNow = false; }
    if (rLine == 0 && rFreeze) rFrozenNow = true;     // freeze takes effect at the frame end
    active = !rFrozenNow && rLine < rLines;
    y = active ? rY0 + rLine * rYStep : rPark;
    if (!rFrozenNow && ++rLine >= rLines + rFly) { rLine = 0; rFrames++; }
    setF1(!active);
    setF2(true);
    tGate.begin(gateIsr, rGateUs);
  } else {
    y = rLineY;
  }
  while (ARM_DWT_CYCCNT - t0 < rYwCyc) ;
  frameTx(frameWord(3, DAC(4), (uint16_t)min(y, 65535u), false), false);
  if (active && rDynK != 0.0f) {
    uint32_t t1 = ARM_DWT_CYCCNT;
    while (ARM_DWT_CYCCNT - t1 < rDfCyc) ;
    float mid = rY0 + 0.5f * rLines * rYStep;
    int32_t f = rFocus + (int32_t)lroundf(rDynK * ((float)y - mid));
    frameTx(frameWord(1, DAC(1), (uint16_t)constrain(f, 0, 4095), false), false);
  }
}

// ------------------------------------------------------------------ public API

void Eo::applyPins() {
  txInv = si(EO_TX_INV); rxInv = si(EO_RX_INV);
  bitCycQ8 = (uint32_t)((double)F_CPU_ACTUAL * 256.0 / sd(EO_BAUD));
  gapCyc = (uint32_t)(sf(EO_GAP_US) * (F_CPU_ACTUAL / 1e6f));
  replyCyc = (uint32_t)(sf(EO_REPLY_US) * (F_CPU_ACTUAL / 1e6f));
  lpol = si(SCAN_LPOL); fpol = si(SCAN_FPOL);
  digitalWriteFast(PIN_EO_F3, 1 ^ txInv);
  if (!rMode) {
    bool g = (si(OP_SCAN) == SCAN_EXT) ? si(SCAN_EXT_GATES) : true;
    digitalWriteFast(PIN_EO_F1, g ^ txInv);
    digitalWriteFast(PIN_EO_F2, g ^ txInv);
    syncIdle();
  }
}

static double relKv(double kv) { return kv * (1.0 + 0.978e-3 * kv); }

// Optibeam: probe current -> condenser DACs, interpolated in log(probe current) through the
// eo.pc* table (captured with LEO-32 at eo.pc_kvref), clamped to the table's range, optionally
// scaled with relativistic kV. Each DAC is interpolated on its own.
static int pcTable(double pa[6], double d[6][4]) {
  int n = 0;
  for (int i = 0; i < 6; i++) {
    double p = sd((SettingId)(EO_PC1_PA + i * 5));
    if (p <= 0) continue;
    int k = n++;
    while (k > 0 && pa[k - 1] > p) { pa[k] = pa[k - 1]; for (int j = 0; j < 4; j++) d[k][j] = d[k - 1][j]; k--; }
    pa[k] = p;
    for (int j = 0; j < 4; j++) d[k][j] = sd((SettingId)(EO_PC1_PA + i * 5 + 1 + j));
  }
  return n;
}

bool Eo::probeRange(double& lo, double& hi) {
  double pa[6], d[6][4];
  int n = pcTable(pa, d);
  if (!n) return false;
  lo = pa[0]; hi = pa[n - 1];
  return true;
}

void Eo::updateOptibeam() {
  if (!si(EO_OPTIBEAM)) return;
  double pa[6], d[6][4];
  int n = pcTable(pa, d);
  if (!n) return;
  double p = constrain(sd(OP_PROBE_PA), pa[0], pa[n - 1]);
  int k = 0;
  while (k < n - 2 && p > pa[k + 1]) k++;
  double t = n == 1 || pa[k + 1] == pa[k] ? 0 : (log(p) - log(pa[k])) / (log(pa[k + 1]) - log(pa[k]));
  double kv = kvUsed_ > 0 ? kvUsed_ : sd(OP_KV);
  double scale = pow(relKv(kv) / relKv(sd(EO_PC_KVREF)), sd(EO_PC_KVEXP));
  for (int j = 0; j < 4; j++) {
    double v = n == 1 ? d[0][j] : d[k][j] + t * (d[k + 1][j] - d[k][j]);
    v = constrain(round(v * scale), 0.0, 4095.0);
    if (v != sd((SettingId)(OP_COND0 + j))) settingSet(OP_COND0 + j, v);
  }
}

void Eo::begin() {
  pinMode(PIN_EO_F3, OUTPUT);
  pinMode(PIN_EO_F1, OUTPUT);
  pinMode(PIN_EO_F2, OUTPUT);
  pinMode(PIN_EO_F4, INPUT);
  pinMode(PIN_SYNC_LINE, OUTPUT);
  pinMode(PIN_SYNC_FRAME, OUTPUT);
  applyPins();
  tLine.priority(si(SCAN_ISR_PRIO));
  tGate.priority(si(SCAN_ISR_PRIO));
  updateOptibeam();
  restoreAll();
}

void Eo::write(int chip, int reg, uint16_t v, uint32_t delayAfterUs) {
  if (chip == 3 && reg == R_OPTIONS) c3optSent = v;
  qPush(frameWord(chip, reg, v, false), delayAfterUs, K_WRITE);
}

int Eo::readNow(int chip, int reg) { return frameTx(frameWord(chip, reg, 0, true), true); }

int Eo::queued() const { return qn; }
uint32_t Eo::frames() const { return rFrames; }

const char* Eo::modeName() const {
  static const char* n[] = { "external", "raster", "line", "spot" };
  int m = si(OP_SCAN);
  return m >= 0 && m <= 3 ? n[m] : "?";
}

void Eo::restartFrame() { qPush(0, 0, K_RESTART); }

void Eo::freeze(bool on) {
  frozen_ = on;
  if (on) {               // pair A 3070, pair B 2047 then 1024
    write(0, DAC(4), 3070); write(1, DAC(3), 3070);
    write(0, DAC(5), 2047); write(1, DAC(2), 2047, 1700);
    write(0, DAC(5), 1024); write(1, DAC(2), 1024);
    rFreeze = true;
  } else {                // pair A 2047, pair B 1024 then 2047, restart
    write(0, DAC(4), 2047); write(1, DAC(3), 2047);
    write(0, DAC(5), 1024); write(1, DAC(2), 1024, 2500);
    write(0, DAC(5), 2047); write(1, DAC(2), 2047);
    rFreeze = false;
    restartFrame();
  }
}

int Eo::c2opt() const {
  int m = si(OP_SCAN), s = si(OP_SPEED), r = range_ < 0 ? 0 : range_;
  if (m == SCAN_SPOT || s >= 10) return r;
  return r | 8 | (s >= 6 ? 0x10 : 0);
}

int Eo::c3opt() const {
  int r = range_ < 0 ? 0 : range_;
  return (si(OP_SCAN) == SCAN_EXT ? 0xF0 : 0xF8) | r;
}


void Eo::computeWeights(int& rng, uint16_t w[4], uint16_t& shA, uint16_t& shB) const {
  double mag = max(sd(OP_MAG), 1e-3);
  double kv = kvUsed_ > 0 ? kvUsed_ : sd(OP_KV);
  double kvs = sqrt(relKv(kv) / relKv(sd(EO_KV_REF)));
  double wd = sd(OP_WD);
  double wds = pow(wd / sd(EO_WD_REF), sd(EO_WD_EXP));
  double rot = sd(OP_ROT) + sd(EO_WD_ROT) * (wd - sd(EO_WD_REF));
  double T = cos(sd(OP_TILT) * M_PI / 180.0);
  double gA = sd(EO_GA), gB = sd(EO_GB), wmax = sd(EO_WMAX);
  double off[4] = {0, 0, 0, 0}, phi = 0, eps = 0;
  rng = -1;
  for (int r = 4; r >= 0; r--) {
    double s = sd((SettingId)(EO_K0 + r)) * kvs * wds / mag;
    phi = (45.0 + sd((SettingId)(EO_D0 + r)) + rot) * M_PI / 180.0;
    eps = sd((SettingId)(EO_E0 + r)) * M_PI / 180.0;
    double ky = sd((SettingId)(EO_KY0 + r));
    off[0] = s * gA * cos(phi);
    off[1] = -s * gB * sin(phi);
    off[2] = T * ky * s * gA * sin(phi + eps);
    off[3] = T * ky * s * gB * cos(phi + eps);
    double m = 0;
    for (int i = 0; i < 4; i++) m = max(m, fabs(off[i]));
    if (m <= wmax) { rng = r; break; }
  }
  if (rng < 0) rng = 0;                     // below the lowest magnification: clamp
  for (int i = 0; i < 4; i++) w[i] = (uint16_t)constrain(lround(32768.0 + off[i]), 0L, 65535L);
  // Beam shift in image axes, rotated with the scan (UI +X is opposite to scan +X).
  double g = 0.5 * (gA + gB);
  double sx = sd(OP_SHIFT_X), sy = sd(OP_SHIFT_Y);
  double a = -sx * cos(phi) + sy * sin(phi + eps);
  double b =  sx * sin(phi) + sy * cos(phi + eps);
  shA = (uint16_t)constrain(lround(2047.0 + a * gA / g), 0L, 4095L);
  shB = (uint16_t)constrain(lround(2047.0 + b * gB / g), 0L, 4095L);
}

void Eo::applyOptics(bool force) {
  int rng; uint16_t w[4], a, b;
  computeWeights(rng, w, a, b);
  int rep = si(EO_REPEAT);
  bool ext = si(OP_SCAN) == SCAN_EXT;
  if (rng != range_ || force) {
    // Never switch range relays with the coils driven: park, switch, settle, then weights.
    for (int k = 0; k < rep; k++) { write(2, DAC(6), 32767); write(2, DAC(5), 32767); write(3, DAC(6), 32767); write(3, DAC(5), 32767); }
    qPush(0, 1000, K_PAUSE);
    range_ = rng;
    write(2, R_OPTIONS, c2opt());
    write(3, R_OPTIONS, c3opt(), si(EO_RANGE_WAIT_MS) * 1000UL);
    for (int k = 0; k < rep; k++) { write(2, DAC(6), w[0]); write(2, DAC(5), w[1]); write(3, DAC(6), w[2]); write(3, DAC(5), w[3]); }
    write(2, DAC(2), ext ? 2048 : si((SettingId)(EO_CX0 + rng)));
    write(3, DAC(0), ext ? 2048 : si((SettingId)(EO_CY0 + rng)));
    for (int k = 0; k < rep; k++) write(2, DAC(3), a);
    write(3, DAC(1), b);
    restartFrame();
  } else {
    if (memcmp(w, w_, sizeof w) != 0)
      for (int k = 0; k < rep; k++) { write(2, DAC(6), w[0]); write(2, DAC(5), w[1]); write(3, DAC(6), w[2]); write(3, DAC(5), w[3]); }
    if (a != shA_ || b != shB_) {
      for (int k = 0; k < rep; k++) write(2, DAC(3), a);
      write(3, DAC(1), b);
    }
  }
  memcpy(w_, w, sizeof w);
  shA_ = a; shB_ = b;
}

void Eo::applyLenses(bool obj, bool cond) {
  uint32_t d = si(EO_LENS_US);
  if (obj) {
    if (si(EO_RMW)) { qPush(frameWord(1, R_CONTROL, 0, true), d, K_READ); qPush(frameWord(1, R_ROUTING, 0, true), d, K_READ); }
    write(1, DAC(0), (uint16_t)constrain(lround(sd(OP_OBJ_C)), 0L, 4095L), d);
    if (sf(OP_WOB_PCT) <= 0) write(1, DAC(1), (uint16_t)constrain(lround(sd(OP_OBJ_F)), 0L, 4095L), d);
  }
  if (cond) {
    if (si(EO_RMW)) { qPush(frameWord(0, R_CONTROL, 0, true), d, K_READ); qPush(frameWord(0, R_ROUTING, 0, true), d, K_READ); }
    for (int i = 0; i < 4; i++) write(0, DAC(i), (uint16_t)constrain(lround(sd((SettingId)(OP_COND0 + i))), 0L, 4095L), d);
  }
  rFocus = lround(sd(OP_OBJ_F));
}

void Eo::applyStig() {
  write(0, DAC(6), si(OP_STIG_X));          // always both together
  write(0, DAC(7), si(OP_STIG_Y));
}

void Eo::applyWobble() {
  uint32_t d = si(EO_LENS_US);
  int F = constrain(lround(sd(OP_OBJ_F)), 0L, 4095L);
  float pct = sf(OP_WOB_PCT);
  if (pct <= 0) {
    write(1, R_CONTROL, 0, d);
    write(1, DAC(1), F, d);
    return;
  }
  int A = (int)min((double)si(EO_WOB_MAX), sd(EO_WOB_K) * pct / max(sd(OP_MAG), 1.0));
  if (A < 1) A = 1;
  bool fast = si(OP_WOB_FAST);
  int step = fast ? A : max(A / 2, 1), ticks = fast ? 2 : 4;
  write(1, R_CONTROL, 0, d);
  write(1, 0x00, (uint16_t)max(F - A, 0), d);
  write(1, 0x01, step, d);
  write(1, 0x02, step, d);
  for (int r = 3; r <= 6; r++) write(1, r, 0, d);
  write(1, 0x07, 1, d);
  write(1, 0x08, ticks, d);
  write(1, 0x09, ticks, d);
  write(1, 0x0A, 1, d);
  write(1, R_ROUTING, 1, d);
  write(1, R_CONTROL, 0x8063, d);
}

void Eo::speedBlock(int s) {
  int rep = si(EO_SPD_REPEAT);
  bool stepped = s >= 10;
  int r0a = stepped ? (1 << (s - 9)) - 1 : (1 << s) - 1;
  for (int k = 0; k < rep; k++) {
    write(2, R_CONTROL, 0);
    write(2, R_OPTIONS, c2opt());
    write(2, R_ROUTING, stepped ? 4 : 8);
    if (!stepped) write(2, DAC(4), si((SettingId)(EO_SLOPE0 + s)));
    write(2, 0x0A, r0a);
    write(2, R_CONTROL, stepped ? 0x8422 : 0x8402);
    write(2, 0x09, (!stepped && s <= 2) ? 288 : 272);
    write(2, 0x01, (!stepped && s <= 2) ? 220 : 232);
    write(2, 0x07, 1024);
    write(3, 0x0A, 0);
    write(4, DAC(4), s >= 6 ? 1 : 0);
  }
  lineUs_ = stepped ? (r0a + 1) * sf(EO_STEP_LINE_US) : sf((SettingId)(EO_LINE0 + s));
  lineUs_ *= 1.0f + sf(SCAN_TRIM_PPM) * 1e-6f;
}

void Eo::startTimer(bool on) {
  if (!on) {
    tLine.end(); tGate.end();
    rMode = 0;
    bool g = (si(OP_SCAN) == SCAN_EXT) ? si(SCAN_EXT_GATES) : true;
    digitalWriteFast(PIN_EO_F1, g ^ txInv);
    digitalWriteFast(PIN_EO_F2, g ^ txInv);
    syncIdle();
    return;
  }
  int m = si(OP_SCAN);
  float cyc = F_CPU_ACTUAL / 1e6f;
  rY0 = si(SCAN_Y0); rYStep = si(SCAN_YSTEP); rLines = si(SCAN_LINES); rPark = si(SCAN_PARK_Y);
  rLineY = si(OP_LINE_Y);
  rFly = (uint32_t)ceilf(sf(SCAN_FLYBACK_MS) * 1000.0f / lineUs_);
  rYwCyc = (uint32_t)(sf(SCAN_YW_US) * cyc);
  rDfCyc = (uint32_t)(sf(SCAN_DF_US) * cyc);
  rGateUs = min(sf(SCAN_F2_US), sf(SCAN_F2_FRAC) * lineUs_);
  float span = (float)rLines * rYStep;
  rDynK = span > 0 ? sf(OP_DYNF) / span : 0;
  rFocus = lround(sd(OP_OBJ_F));
  rRestart = true;
  if (m == SCAN_LINE) {                     // gates held high, Y written each line
    digitalWriteFast(PIN_EO_F1, 1 ^ txInv);
    digitalWriteFast(PIN_EO_F2, 1 ^ txInv);
    syncIdle();
    rMode = 2;
  } else {
    rMode = 1;
  }
  tLine.begin(lineIsr, lineUs_);
}

void Eo::applyScan() {
  int m = si(OP_SCAN), s = si(OP_SPEED);
  int r = range_ < 0 ? 0 : range_;
  bool ext = m == SCAN_EXT;
  startTimer(false);
  if (m == SCAN_SPOT) {
    write(2, R_CONTROL, 0);
    write(2, R_OPTIONS, c2opt());
    write(2, R_ROUTING, 4);
    write(2, 0x0A, 1);
    write(2, R_CONTROL, 0x8422);
    write(2, DAC(1), si(EO_XSTART_SPOT));
    write(4, DAC(4), 1);
    write(2, 0x0A, 15);
    write(2, DAC(4), si(OP_SPOT_X));
    write(3, DAC(4), si(OP_SPOT_Y));
  } else {
    // Ramp set-up (full frame), or the line-scan Y window.
    write(2, 0x00, 1023); write(2, 0x08, 1024); write(2, 0x02, 62);
    if (m == SCAN_LINE) { write(3, 0x00, si(OP_LINE_Y)); write(3, 0x08, 10); write(3, 0x01, 6); }
    else { write(3, 0x00, si(SCAN_Y0)); write(3, 0x08, si(SCAN_LINES)); write(3, 0x01, 504); }
    write(3, 0x02, si(SCAN_YSTEP)); write(3, 0x09, 128);
    speedBlock(s);
    write(2, DAC(1), si(EO_XSTART));
  }
  write(2, DAC(2), ext ? 2048 : si((SettingId)(EO_CX0 + r)));
  write(3, DAC(0), ext ? 2048 : si((SettingId)(EO_CY0 + r)));
  write(3, R_OPTIONS, c3opt());
  if (m == SCAN_RASTER || m == SCAN_LINE) {
    if (lineUs_ <= 0) speedBlock(s);
    startTimer(true);
  }
}

void Eo::restoreAll() {
  qn = 0;
  // Reset burst (spec §5.11) with the current state in place of the zero defaults.
  for (int c = 0; c <= 1; c++) { write(c, R_ROUTING, 15); write(c, R_OPTIONS, 32); write(c, R_CONTROL, 0); }
  for (int c = 2; c <= 3; c++) { write(c, 0x07, 0); write(c, 0x0A, 0); write(c, R_CONTROL, 0); write(c, R_ROUTING, c == 3 ? 4 : 0); }
  write(4, 0x00, 0); write(4, 0x01, 1); write(4, 0x02, 1); write(4, 0x07, 0);
  write(4, 0x08, 255); write(4, 0x09, 255); write(4, 0x0A, 0); write(4, R_CONTROL, 0x8403);
  for (int i = 0; i < 4; i++) write(0, DAC(i), (uint16_t)constrain(lround(sd((SettingId)(OP_COND0 + i))), 0L, 4095L));
  write(0, DAC(4), 2047); write(0, DAC(5), 2047);                 // pairs A / B: running
  write(0, DAC(6), si(OP_STIG_X)); write(0, DAC(7), si(OP_STIG_Y));
  write(0, DAC(8), 2048); write(0, DAC(9), 2048);
  write(1, DAC(0), (uint16_t)constrain(lround(sd(OP_OBJ_C)), 0L, 4095L));
  write(1, DAC(1), (uint16_t)constrain(lround(sd(OP_OBJ_F)), 0L, 4095L));
  write(1, DAC(2), 2047); write(1, DAC(3), 2047);
  for (int i = 4; i <= 7; i++) write(1, DAC(i), 128);
  write(1, DAC(8), 0); write(1, DAC(9), 0); write(1, R_1A, 0); write(1, R_1B, 0);
  write(2, DAC(0), 4095); write(2, DAC(1), si(EO_XSTART)); write(2, DAC(2), 2048); write(2, DAC(3), 2047);
  write(2, DAC(5), 32768); write(2, DAC(6), 32768);
  write(3, DAC(0), 2048); write(3, DAC(1), 2047); write(3, DAC(2), si(EO_C3DAC2)); write(3, DAC(3), si(EO_C3DAC3));
  write(3, DAC(4), si(SCAN_PARK_Y)); write(3, DAC(5), 32768); write(3, DAC(6), 32768); write(3, DAC(7), 0); write(3, DAC(8), 0);
  range_ = -1;
  kvUsed_ = 0;
  applyScan();
  applyOptics(true);
  if (sf(OP_WOB_PCT) > 0) applyWobble();
  frozen_ = false; rFreeze = false;
  aMag_ = sf(OP_MAG); aRot_ = sf(OP_ROT); aWd_ = sf(OP_WD); aTilt_ = sf(OP_TILT);
  aSx_ = sf(OP_SHIFT_X); aSy_ = sf(OP_SHIFT_Y);
  aObjC_ = sf(OP_OBJ_C); aObjF_ = sf(OP_OBJ_F);
  for (int i = 0; i < 4; i++) aCond_[i] = sf((SettingId)(OP_COND0 + i));
  aStigX_ = si(OP_STIG_X); aStigY_ = si(OP_STIG_Y);
  aScan_ = si(OP_SCAN); aSpeed_ = si(OP_SPEED);
  aSpotX_ = si(OP_SPOT_X); aSpotY_ = si(OP_SPOT_Y); aLineY_ = si(OP_LINE_Y);
  aWob_ = sf(OP_WOB_PCT); aWobFast_ = si(OP_WOB_FAST); aDynf_ = sf(OP_DYNF);
  calDirty_ = false;
  started_ = true;
  logf(LV_INFO, "eo", "EO board restored (%d frames queued)", qn);
}

void Eo::service(float kvSettled) {
  // Drain the frame queue, honouring each entry's delay.
  uint32_t now = micros();
  for (int n = 0; n < 32 && qn > 0 && now - qLastUs >= qDelay; n++) {
    QEnt e = q[qh];
    qh = (qh + 1) % QSIZE; qn--;
    if (e.kind == K_RESTART) rRestart = true;
    else if (e.kind != K_PAUSE) frameTx(e.word, e.kind == K_READ);
    qLastUs = micros(); qDelay = e.delayUs;
    now = qLastUs;
  }
  if (!started_) return;

  // Link check: chip 3 options reads back the last value written.
  if (sf(EO_HB_S) > 0 && qn == 0 && millis() - lastHb_ >= (uint32_t)(sf(EO_HB_S) * 1000)) {
    lastHb_ = millis();
    int v = readNow(3, R_OPTIONS);
    bool ok = v >= 0 && (c3optSent < 0 || v == c3optSent);
    if (ok != linkOk_) {
      if (ok) logf(LV_INFO, "eo", "EO link OK");
      else logf(LV_WARN, "eo", "EO link check failed (read %d, expected %d)", v, c3optSent);
    }
    if (!ok) hbFails_++;
    linkOk_ = ok;
  }

  if (qn > 64) return;                      // let a big burst drain first

  // kV compensation once the EHT has settled (spec §5.3): lenses and weights follow sqrt(rel. kV).
  bool optics = calDirty_, forceRange = calDirty_;
  if (kvSettled > 0 && fabsf(kvSettled - kvUsed_) > 0.005f) {
    if (kvUsed_ > 0) {
      double ratio = sqrt(relKv(kvSettled) / relKv(kvUsed_));
      if (si(EO_KV_OBJ)) settingSet(OP_OBJ_C, constrain(sd(OP_OBJ_C) * ratio, 0.0, 4095.0));
      if (si(EO_KV_COND) && !si(EO_OPTIBEAM))
        for (int i = 0; i < 4; i++) settingSet(OP_COND0 + i, constrain(sd((SettingId)(OP_COND0 + i)) * ratio, 0.0, 4095.0));
    }
    kvUsed_ = kvSettled;
    optics = true;
  }
  calDirty_ = false;
  updateOptibeam();

  if (si(OP_SCAN) != aScan_ || si(OP_SPEED) != aSpeed_) {
    aScan_ = si(OP_SCAN); aSpeed_ = si(OP_SPEED);
    aSpotX_ = si(OP_SPOT_X); aSpotY_ = si(OP_SPOT_Y); aLineY_ = si(OP_LINE_Y);
    applyScan();
    optics = true;
  }
  if (aScan_ == SCAN_SPOT && (si(OP_SPOT_X) != aSpotX_ || si(OP_SPOT_Y) != aSpotY_)) {
    aSpotX_ = si(OP_SPOT_X); aSpotY_ = si(OP_SPOT_Y);
    write(2, DAC(4), aSpotX_); write(3, DAC(4), aSpotY_);
  }
  if (aScan_ == SCAN_LINE && si(OP_LINE_Y) != aLineY_) {
    aLineY_ = si(OP_LINE_Y);
    write(3, 0x00, aLineY_);
    rLineY = aLineY_;
  }
  bool magChanged = sf(OP_MAG) != aMag_;
  if (magChanged || sf(OP_ROT) != aRot_ || sf(OP_WD) != aWd_ || sf(OP_TILT) != aTilt_ ||
      sf(OP_SHIFT_X) != aSx_ || sf(OP_SHIFT_Y) != aSy_) optics = true;
  if (optics) {
    aMag_ = sf(OP_MAG); aRot_ = sf(OP_ROT); aWd_ = sf(OP_WD); aTilt_ = sf(OP_TILT);
    aSx_ = sf(OP_SHIFT_X); aSy_ = sf(OP_SHIFT_Y);
    applyOptics(forceRange);
  }
  bool objC = sf(OP_OBJ_C) != aObjC_, objF = sf(OP_OBJ_F) != aObjF_;
  bool cond = false;
  for (int i = 0; i < 4; i++) if (sf((SettingId)(OP_COND0 + i)) != aCond_[i]) cond = true;
  if (objC || objF || cond) {
    aObjC_ = sf(OP_OBJ_C); aObjF_ = sf(OP_OBJ_F);
    for (int i = 0; i < 4; i++) aCond_[i] = sf((SettingId)(OP_COND0 + i));
    applyLenses(objC || objF, cond);
  }
  if (si(OP_STIG_X) != aStigX_ || si(OP_STIG_Y) != aStigY_) {
    aStigX_ = si(OP_STIG_X); aStigY_ = si(OP_STIG_Y);
    applyStig();
  }
  bool wobOn = sf(OP_WOB_PCT) > 0;
  if (sf(OP_WOB_PCT) != aWob_ || si(OP_WOB_FAST) != aWobFast_ || (wobOn && (magChanged || objF))) {
    aWob_ = sf(OP_WOB_PCT); aWobFast_ = si(OP_WOB_FAST);
    applyWobble();
  }
  if (sf(OP_DYNF) != aDynf_) {
    aDynf_ = sf(OP_DYNF);
    float span = (float)rLines * rYStep;
    rDynK = span > 0 ? aDynf_ / span : 0;
  }
}
