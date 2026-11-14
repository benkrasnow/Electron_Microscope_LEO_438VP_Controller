// LEO 438VP serial-link logger for Teensy 3.2 (Teensyduino, USB Type: Serial)
//
// Listens (receive only) on up to four serial lines and streams every received
// byte to the USB serial port with a microsecond timestamp. Intended for tapping
// the 9600 8N1 links of the LEO 438VP: EHT (UART A), Stage/Vac (UART B) and the
// VP "Orsay" controller on PC COM2.
//
//   ch1 = Serial1  RX pin 0   (TX pin 1  is released after begin)
//   ch2 = Serial2  RX pin 9   (TX pin 10 is released after begin)
//   ch3 = Serial3  RX pin 7   (TX pin 8  is released after begin)
//   ch4 = software UART, RX pin 2 (8N1 only; decoded from pin-change interrupts)
//
// Output (one line per received byte):
//   <ch> <t_us> <HH>          e.g.  "1 18233021 2E"
// where t_us is microseconds since boot (or since the last Z command), 64-bit.
// The timestamp is taken when the byte has been received, i.e. at about the end
// of its stop bit, plus a few microseconds of loop latency.
// Lines starting with '#' are status / replies and never contain capture data.
//
// Commands (send over USB, end with newline):
//   ?            help
//   S            show configuration and counters
//   B <ch> <baud>          set baud rate            (default 9600)
//   F <ch> <fmt>           8N1 8E1 8O1 7E1 7O1 8N2  (default 8N1; ch4: 8N1 only)
//   I <ch> <0|1>           invert RX polarity       (default 0)
//   E <ch> <0|1>           enable channel           (default 1)
//   P            probe idle level / activity on each RX pin (for polarity)
//   X            self-test: inject the bytes "Hi\r\n" into the ch4 decoder
//   R <pin>      diagnostic: move ch4 to another pin (default 2)
//   Z            zero the timestamp clock

#include <Arduino.h>

static const uint32_t DEFAULT_BAUD = 9600;
static const uint8_t LED = 13;

struct Chan {
  HardwareSerial *port;
  uint8_t rxPin;
  uint8_t txPin;
  uint32_t baud;
  uint32_t fmt;      // SERIAL_xxx without the RXINV flag
  bool invert;
  bool enabled;
  uint32_t bytes;    // bytes received since boot
  uint8_t rxmem[2048];
};

static Chan chans[3] = {
  {&Serial1, 0, 1, DEFAULT_BAUD, SERIAL_8N1, false, true, 0, {0}},
  {&Serial2, 9, 10, DEFAULT_BAUD, SERIAL_8N1, false, true, 0, {0}},
  {&Serial3, 7, 8, DEFAULT_BAUD, SERIAL_8N1, false, true, 0, {0}},
};

// ---------------------------------------------------------------- 64-bit clock
static uint32_t lastMicros = 0;
static uint64_t microsHigh = 0;
static uint64_t epoch = 0;

static uint64_t now64() {
  uint32_t m = micros();
  if (m < lastMicros) microsHigh += (1ULL << 32);
  lastMicros = m;
  return (microsHigh | m) - epoch;
}

// ---------------------------------------------------------------- output ring
// Data is staged here and drained to USB only as fast as the host accepts it,
// so a slow host never stalls reception.
static const uint32_t RING = 24576;
static char ring[RING];
static uint32_t rHead = 0, rTail = 0;
static uint32_t dropped = 0;        // bytes not logged because the ring was full
static uint32_t unlogged = 0;       // bytes received while no host was connected

static uint32_t ringFree() { return (rTail + RING - rHead - 1) % RING; }

static bool ringPut(const char *s, uint32_t n) {
  if (ringFree() < n) return false;
  for (uint32_t i = 0; i < n; i++) {
    ring[rHead] = s[i];
    rHead = (rHead + 1) % RING;
  }
  return true;
}

static void drainRing() {
  while (rTail != rHead) {
    int room = Serial.availableForWrite();
    if (room <= 0) return;
    uint32_t chunk = (rHead > rTail) ? (rHead - rTail) : (RING - rTail);
    if (chunk > (uint32_t)room) chunk = room;
    Serial.write(&ring[rTail], chunk);
    rTail = (rTail + chunk) % RING;
  }
}

static int fmtU64(char *buf, uint64_t v) {
  char tmp[21];
  int n = 0;
  do { tmp[n++] = '0' + (v % 10); v /= 10; } while (v);
  for (int i = 0; i < n; i++) buf[i] = tmp[n - 1 - i];
  return n;
}

// Small line builder (snprintf does not link for Teensy 3.x with the gcc 15 toolchain).
struct Line {
  char b[192];
  int n = 0;
  Line &s(const char *t) {
    while (*t && n < (int)sizeof(b) - 1) b[n++] = *t++;
    return *this;
  }
  Line &u(uint64_t v) {
    char t[21];
    int k = fmtU64(t, v);
    for (int i = 0; i < k && n < (int)sizeof(b) - 1; i++) b[n++] = t[i];
    return *this;
  }
  const char *str() { b[n] = 0; return b; }
};

// Status lines go through the same ring so they stay in order with the data.
static void msg(const char *s) {
  ringPut(s, strlen(s));
}

static uint32_t ledOffAt = 0;

// One data line: "<ch> <t_us> <HH>\n"
static void emitByte(int ch, uint64_t t, uint8_t b) {
  static const char hex[] = "0123456789ABCDEF";
  char line[32];
  int n = 0;
  line[n++] = '0' + ch;
  line[n++] = ' ';
  n += fmtU64(line + n, t);
  line[n++] = ' ';
  line[n++] = hex[b >> 4];
  line[n++] = hex[b & 15];
  line[n++] = '\n';
  if (!ringPut(line, n)) dropped++;
  digitalWriteFast(LED, HIGH);
  ledOffAt = millis() + 20;
}

// ---------------------------------------------------------------- ch4: software UART
// The Teensy 3.2 has only three UARTs. ch4 decodes a fourth line in software:
// a pin-change interrupt records every edge with the CPU cycle counter, and the
// main loop rebuilds each 8N1 byte by reading the line level at the centre of
// each bit from that edge history.
static uint8_t softPin = 2;                   // movable with the R command (diagnostic)
static volatile uint8_t *softPdir = nullptr;   // bit-band input byte for softPin (Teensy 3.x)
static uint8_t softMask = 1;

struct SoftChan {
  uint32_t baud = DEFAULT_BAUD;
  bool invert = false;
  bool enabled = true;
  uint32_t bytes = 0;
  uint32_t framing = 0;     // stop bit not at mark level
  uint32_t overflow = 0;    // edge buffer full
};
static SoftChan soft;

static const uint32_t EDGES = 1024;   // power of two
static volatile uint32_t edgeT[EDGES];
static volatile uint8_t edgeL[EDGES];
static volatile uint32_t eHead = 0;
static volatile uint32_t eTail = 0;
static bool inFrame = false;
static uint32_t frameStart = 0;

static void softIsr() {
  uint32_t t = ARM_DWT_CYCCNT;
  uint8_t l = (*softPdir & softMask) ? 1 : 0;
  uint32_t h = eHead;
  if (h - eTail >= EDGES) { soft.overflow++; return; }
  edgeT[h & (EDGES - 1)] = t;
  edgeL[h & (EDGES - 1)] = l;
  eHead = h + 1;
}

static uint8_t markLevel() { return soft.invert ? LOW : HIGH; }

static void softPush(uint32_t t, uint8_t level) {   // used by the self-test only
  uint32_t h = eHead;
  edgeT[h & (EDGES - 1)] = t;
  edgeL[h & (EDGES - 1)] = level;
  eHead = h + 1;
}

static void applySoft() {
  detachInterrupt(digitalPinToInterrupt(softPin));
  pinMode(softPin, INPUT_PULLUP);
  softPdir = portInputRegister(softPin);
  softMask = digitalPinToBitMask(softPin);
  noInterrupts();
  eTail = eHead;
  inFrame = false;
  interrupts();
  if (soft.enabled) attachInterrupt(digitalPinToInterrupt(softPin), softIsr, CHANGE);
}

static void softPoll(bool host) {
  if (!soft.enabled) return;
  const uint32_t cpb = F_CPU / soft.baud;   // CPU cycles per bit
  const uint8_t mark = markLevel();
  for (;;) {
    if (!inFrame) {
      // Skip edges back to mark; the next edge to space is a start bit.
      while (eTail != eHead && edgeL[eTail & (EDGES - 1)] == mark) eTail++;
      if (eTail == eHead) return;
      frameStart = edgeT[eTail & (EDGES - 1)];
      eTail++;
      inFrame = true;
    }
    // Wait until the whole frame (start + 8 data + stop) has gone by.
    if ((uint32_t)(ARM_DWT_CYCCNT - frameStart) < 10 * cpb) return;

    uint8_t level = !mark;          // the line is at space after the start edge
    uint32_t idx = eTail;
    uint8_t value = 0;
    for (int bit = 0; bit < 9; bit++) {   // 8 data bits, then the stop bit
      uint32_t centre = frameStart + cpb + cpb / 2 + bit * cpb;
      while (idx != eHead && (int32_t)(edgeT[idx & (EDGES - 1)] - centre) <= 0) {
        level = edgeL[idx & (EDGES - 1)];
        idx++;
      }
      uint8_t one = (level == mark);
      if (bit < 8) value |= one << bit;
      else if (!one) soft.framing++;
    }
    eTail = idx;
    inFrame = false;
    soft.bytes++;

    // Timestamp at the end of the stop bit, on the same clock as the UART channels.
    uint32_t ageCycles = ARM_DWT_CYCCNT - (frameStart + 10 * cpb);
    uint64_t t = now64() - ageCycles / (F_CPU / 1000000);
    if (host) emitByte(4, t, value);
    else unlogged++;
  }
}

// Self-test: synthesise the edges of "Hi\r\n" as if they had just arrived on pin 2.
static void softSelfTest() {
  const uint8_t text[] = {'H', 'i', '\r', '\n'};
  const uint32_t cpb = F_CPU / soft.baud;
  const uint8_t mark = markLevel();
  noInterrupts();
  uint32_t t = ARM_DWT_CYCCNT - (sizeof(text) * 10 + 2) * cpb;
  uint8_t level = mark;
  for (uint8_t c : text) {
    for (int bit = 0; bit < 10; bit++) {   // start, 8 data, stop
      uint8_t one = bit == 0 ? 0 : bit == 9 ? 1 : (c >> (bit - 1)) & 1;
      uint8_t l = one ? mark : !mark;
      if (l != level) { softPush(t, l); level = l; }
      t += cpb;
    }
  }
  interrupts();
  msg("# TEST injected \"Hi\\r\\n\" (48 69 0D 0A) into ch4\n");
}

// ---------------------------------------------------------------- UART setup
static const char *fmtName(uint32_t f) {
  switch (f) {
    case SERIAL_8N1: return "8N1";
    case SERIAL_8E1: return "8E1";
    case SERIAL_8O1: return "8O1";
    case SERIAL_7E1: return "7E1";
    case SERIAL_7O1: return "7O1";
    case SERIAL_8N2: return "8N2";
  }
  return "?";
}

static bool parseFmt(const char *s, uint32_t *out) {
  if (!strcasecmp(s, "8N1")) { *out = SERIAL_8N1; return true; }
  if (!strcasecmp(s, "8E1")) { *out = SERIAL_8E1; return true; }
  if (!strcasecmp(s, "8O1")) { *out = SERIAL_8O1; return true; }
  if (!strcasecmp(s, "7E1")) { *out = SERIAL_7E1; return true; }
  if (!strcasecmp(s, "7O1")) { *out = SERIAL_7O1; return true; }
  if (!strcasecmp(s, "8N2")) { *out = SERIAL_8N2; return true; }
  return false;
}

// Serial1/Serial2 have an 8-byte RX FIFO that the core sets to interrupt only
// every 4 bytes (or on line idle). Drop the watermark to 1 so each byte is
// delivered, and therefore timestamped, as soon as it arrives.
static void rxWatermarkOne(int i) {
#if defined(__MK20DX256__)
  if (i == 0) { UART0_C2 &= ~UART_C2_RE; UART0_RWFIFO = 1; UART0_C2 |= UART_C2_RE; }
  if (i == 1) { UART1_C2 &= ~UART_C2_RE; UART1_RWFIFO = 1; UART1_C2 |= UART_C2_RE; }
#endif
}

static void applyChan(int i) {
  Chan &c = chans[i];
  c.port->end();
  if (!c.enabled) {
    pinMode(c.rxPin, INPUT);
    return;
  }
  uint32_t f = c.fmt | (c.invert ? (SERIAL_8N1_RXINV - SERIAL_8N1) : 0);
  c.port->begin(c.baud, f);
  c.port->addMemoryForRead(c.rxmem, sizeof(c.rxmem));
  rxWatermarkOne(i);
  // Receive only: release the TX pin so the logger can never drive the tapped line.
  pinMode(c.txPin, INPUT);
}

// ---------------------------------------------------------------- reporting
static void printConfig() {
  for (int i = 0; i < 3; i++) {
    Chan &c = chans[i];
    Line l;
    l.s("# CFG ch").u(i + 1).s(" rx_pin=").u(c.rxPin).s(" en=").u(c.enabled).s(" baud=").u(c.baud)
        .s(" fmt=").s(fmtName(c.fmt)).s(" invert=").u(c.invert).s(" bytes=").u(c.bytes).s("\n");
    msg(l.str());
  }
  Line s;
  s.s("# CFG ch4 rx_pin=").u(softPin).s(" en=").u(soft.enabled).s(" baud=").u(soft.baud)
      .s(" fmt=8N1 invert=").u(soft.invert).s(" bytes=").u(soft.bytes).s(" soft=1 framing=")
      .u(soft.framing).s(" edge_overflow=").u(soft.overflow).s("\n");
  msg(s.str());
  Line l;
  l.s("# CNT dropped=").u(dropped).s(" unlogged=").u(unlogged).s("\n");
  msg(l.str());
}

static void printHeader() {
  msg("# LEO438VP serial logger v2 (Teensy 3.2, 3 UART + 1 software channel)\n");
  msg("# format: <ch> <t_us> <hex byte>\n");
  Line l;
  l.s("# T0 t_us=").u(now64()).s("\n");
  msg(l.str());
  printConfig();
}

static void printHelp() {
  msg("# commands: ? | S | B <ch> <baud> | F <ch> <8N1|8E1|8O1|7E1|7O1|8N2> |\n");
  msg("#           I <ch> <0|1> (invert) | E <ch> <0|1> (enable) | P (probe) | X (ch4 self-test) | Z (zero clock)\n");
}

// Sample each RX pin as a plain GPIO for 200 ms. An idle UART line sits at the
// "mark" level (high); a mostly-low pin means the signal is inverted.
static void probe() {
  const uint8_t pins[4] = {chans[0].rxPin, chans[1].rxPin, chans[2].rxPin, softPin};
  for (int i = 0; i < 3; i++) chans[i].port->end();
  detachInterrupt(digitalPinToInterrupt(softPin));
  for (int i = 0; i < 4; i++) pinMode(pins[i], INPUT_PULLUP);
  delayMicroseconds(200);
  uint32_t high[4] = {0, 0, 0, 0}, edges[4] = {0, 0, 0, 0}, samples = 0;
  int last[4];
  for (int i = 0; i < 4; i++) last[i] = digitalRead(pins[i]);
  uint32_t start = millis();
  while (millis() - start < 200) {
    for (int i = 0; i < 4; i++) {
      int v = digitalRead(pins[i]);
      high[i] += v;
      if (v != last[i]) { edges[i]++; last[i] = v; }
    }
    samples++;
    delayMicroseconds(10);
  }
  for (int i = 0; i < 4; i++) {
    uint32_t pct = samples ? (high[i] * 1000UL / samples) : 0;
    const char *hint = edges[i] == 0
        ? (pct > 500 ? "idle high: normal polarity" : "idle low: inverted (I x 1) or unconnected")
        : (pct > 500 ? "active, mostly high: normal polarity" : "active, mostly low: try I x 1");
    Line l;
    l.s("# PROBE ch").u(i + 1).s(" pin=").u(pins[i]).s(" high=").u(pct / 10).s(".").u(pct % 10)
        .s("% edges=").u(edges[i]).s("  ").s(hint).s("\n");
    msg(l.str());
  }
  for (int i = 0; i < 3; i++) applyChan(i);
  applySoft();
}

// ---------------------------------------------------------------- commands
static char cmd[64];
static uint8_t cmdLen = 0;

static void runCommand(char *s) {
  char op = toupper(s[0]);
  char *a = s + 1;
  long ch = strtol(a, &a, 10);
  while (*a == ' ') a++;
  bool chOk = ch >= 1 && ch <= 3;
  bool ch4 = ch == 4;
  switch (op) {
    case '?': case 'H': printHelp(); return;
    case 'S': printConfig(); return;
    case 'P': probe(); return;
    case 'X': softSelfTest(); return;
    case 'R':   // diagnostic: move ch4 to another pin, e.g. "R 7" with ch3 disabled (E 3 0)
      if (ch >= 0 && ch <= 33 && ch != 13) {
        detachInterrupt(digitalPinToInterrupt(softPin));
        softPin = ch;
        applySoft();
        printConfig();
        return;
      }
      break;
    case 'Z':
      epoch = 0;
      epoch = now64();
      msg("# T0 t_us=0 (clock zeroed)\n");
      return;
    case 'B': {
      long b = strtol(a, nullptr, 10);
      if (b < 300 || b > 1000000) break;
      if (chOk) { chans[ch - 1].baud = b; applyChan(ch - 1); printConfig(); return; }
      if (ch4 && b <= 115200) { soft.baud = b; applySoft(); printConfig(); return; }
      break;
    }
    case 'F':
      if (chOk && parseFmt(a, &chans[ch - 1].fmt)) { applyChan(ch - 1); printConfig(); return; }
      if (ch4 && !strcasecmp(a, "8N1")) { printConfig(); return; }
      break;
    case 'I':
      if (chOk) { chans[ch - 1].invert = atoi(a) != 0; applyChan(ch - 1); printConfig(); return; }
      if (ch4) { soft.invert = atoi(a) != 0; applySoft(); printConfig(); return; }
      break;
    case 'E':
      if (chOk) { chans[ch - 1].enabled = atoi(a) != 0; applyChan(ch - 1); printConfig(); return; }
      if (ch4) { soft.enabled = atoi(a) != 0; applySoft(); printConfig(); return; }
      break;
  }
  Line l;
  l.s("# ERR bad command: ").s(s).s("\n");
  msg(l.str());
}

static void pollCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r' || c == '\n') {
      cmd[cmdLen] = 0;
      if (cmdLen) runCommand(cmd);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmd) - 1) {
      cmd[cmdLen++] = c;
    }
  }
}

// ---------------------------------------------------------------- main
static bool hostWasConnected = false;
static uint32_t nextHeartbeat = 1000;

void setup() {
  pinMode(LED, OUTPUT);
  ARM_DEMCR |= ARM_DEMCR_TRCENA;            // enable the cycle counter used by ch4
  ARM_DWT_CTRL |= ARM_DWT_CTRL_CYCCNTENA;
  Serial.begin(115200);   // USB: rate is ignored, runs at full USB speed
  for (int i = 0; i < 3; i++) applyChan(i);
  applySoft();
}

void loop() {
  bool host = (bool)Serial;   // true while the host has the port open (DTR)
  if (host && !hostWasConnected) printHeader();
  hostWasConnected = host;

  for (int i = 0; i < 3; i++) {
    Chan &c = chans[i];
    if (!c.enabled) continue;
    while (c.port->available()) {
      uint8_t b = c.port->read();
      uint64_t t = now64();
      c.bytes++;
      if (host) emitByte(i + 1, t, b);
      else unlogged++;
    }
  }
  softPoll(host);

  if (host) {
    pollCommands();
    if ((int32_t)(millis() - nextHeartbeat) >= 0) {
      nextHeartbeat += 1000;
      if ((int32_t)(millis() - nextHeartbeat) >= 0) nextHeartbeat = millis() + 1000;  // after a long gap
      Line l;
      l.s("# HB t_us=").u(now64()).s(" n1=").u(chans[0].bytes).s(" n2=").u(chans[1].bytes)
          .s(" n3=").u(chans[2].bytes).s(" n4=").u(soft.bytes).s(" dropped=").u(dropped)
          .s(" framing4=").u(soft.framing).s("\n");
      msg(l.str());
    }
    drainRing();
  } else {
    rHead = rTail = 0;   // nobody listening: discard staged output
  }

  if ((int32_t)(millis() - ledOffAt) >= 0) digitalWriteFast(LED, LOW);
}
