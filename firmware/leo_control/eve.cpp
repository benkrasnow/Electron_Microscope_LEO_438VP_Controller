#include "eve.h"
#include "config.h"
#include <SPI.h>

// FT81x memory map / registers
#define RAM_DL          0x300000
#define REG_ID          0x302000
#define REG_CPURESET    0x302020
#define REG_HCYCLE      0x30202C
#define REG_HOFFSET     0x302030
#define REG_HSIZE       0x302034
#define REG_HSYNC0      0x302038
#define REG_HSYNC1      0x30203C
#define REG_VCYCLE      0x302040
#define REG_VOFFSET     0x302044
#define REG_VSIZE       0x302048
#define REG_VSYNC0      0x30204C
#define REG_VSYNC1      0x302050
#define REG_DLSWAP      0x302054
#define REG_SWIZZLE     0x302064
#define REG_CSPREAD     0x302068
#define REG_PCLK_POL    0x30206C
#define REG_PCLK        0x302070
#define REG_DITHER      0x302060
#define REG_GPIO_DIR    0x302090
#define REG_GPIO        0x302094
#define REG_PWM_HZ      0x3020D0
#define REG_PWM_DUTY    0x3020D4
#define REG_CMD_READ    0x3020F8
#define REG_CMD_WRITE   0x3020FC
#define REG_CMD_DL      0x302100
#define REG_TOUCH_TAG   0x30212C
#define REG_CMDB_SPACE  0x302574
#define REG_CMDB_WRITE  0x302578

void Eve::wr8(uint32_t a, uint8_t v) {
  SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
  digitalWriteFast(PIN_LCD_CS, LOW);
  SPI.transfer(0x80 | ((a >> 16) & 0x3F)); SPI.transfer(a >> 8); SPI.transfer(a);
  SPI.transfer(v);
  digitalWriteFast(PIN_LCD_CS, HIGH);
  SPI.endTransaction();
}
void Eve::wr16(uint32_t a, uint16_t v) {
  SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
  digitalWriteFast(PIN_LCD_CS, LOW);
  SPI.transfer(0x80 | ((a >> 16) & 0x3F)); SPI.transfer(a >> 8); SPI.transfer(a);
  SPI.transfer(v); SPI.transfer(v >> 8);
  digitalWriteFast(PIN_LCD_CS, HIGH);
  SPI.endTransaction();
}
void Eve::wr32(uint32_t a, uint32_t v) {
  SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
  digitalWriteFast(PIN_LCD_CS, LOW);
  SPI.transfer(0x80 | ((a >> 16) & 0x3F)); SPI.transfer(a >> 8); SPI.transfer(a);
  for (int i = 0; i < 4; i++) SPI.transfer(v >> (8 * i));
  digitalWriteFast(PIN_LCD_CS, HIGH);
  SPI.endTransaction();
}
uint32_t Eve::rd32(uint32_t a) {
  SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
  digitalWriteFast(PIN_LCD_CS, LOW);
  SPI.transfer((a >> 16) & 0x3F); SPI.transfer(a >> 8); SPI.transfer(a);
  SPI.transfer(0);                                   // dummy
  uint32_t v = 0;
  for (int i = 0; i < 4; i++) v |= (uint32_t)SPI.transfer(0) << (8 * i);
  digitalWriteFast(PIN_LCD_CS, HIGH);
  SPI.endTransaction();
  return v;
}
uint16_t Eve::rd16(uint32_t a) { return rd32(a) & 0xFFFF; }
uint8_t Eve::rd8(uint32_t a) { return rd32(a) & 0xFF; }

void Eve::host(uint8_t c, uint8_t arg) {
  SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
  digitalWriteFast(PIN_LCD_CS, LOW);
  SPI.transfer(c); SPI.transfer(arg); SPI.transfer(0);
  digitalWriteFast(PIN_LCD_CS, HIGH);
  SPI.endTransaction();
}

bool Eve::begin(uint32_t spiHz, bool clkExt, bool rotate, uint32_t waitMs) {
  ok_ = false;
  pinMode(PIN_LCD_CS, OUTPUT);
  digitalWriteFast(PIN_LCD_CS, HIGH);
  pinMode(PIN_LCD_PD, OUTPUT);
  pinMode(PIN_LCD_INT, INPUT_PULLUP);
  SPI.begin();
  hz_ = 8000000;                                     // below 11 MHz until the clock is up
  digitalWriteFast(PIN_LCD_PD, LOW);  delay(20);
  digitalWriteFast(PIN_LCD_PD, HIGH); delay(20);
  if (clkExt) host(0x44);                            // CLKEXT
  host(0x00);                                        // ACTIVE
  uint32_t t0 = millis();
  while (rd8(REG_ID) != 0x7C) { if (millis() - t0 > waitMs) return false; delay(5); }
  t0 = millis();
  while (rd8(REG_CPURESET) & 0x03) { if (millis() - t0 > waitMs) return false; delay(5); }

  // Newhaven 4.3" 800x480 timing
  wr8(REG_PCLK, 0);
  wr16(REG_HCYCLE, 928); wr16(REG_HOFFSET, 88); wr16(REG_HSYNC0, 0); wr16(REG_HSYNC1, 48);
  wr16(REG_VCYCLE, 525); wr16(REG_VOFFSET, 32); wr16(REG_VSYNC0, 0); wr16(REG_VSYNC1, 3);
  wr8(REG_SWIZZLE, 0); wr8(REG_PCLK_POL, 1); wr8(REG_CSPREAD, 0); wr8(REG_DITHER, 1);
  wr16(REG_HSIZE, 800); wr16(REG_VSIZE, 480);
  wr32(RAM_DL + 0, ev::CLEAR_COLOR(0));
  wr32(RAM_DL + 4, ev::CLEAR());
  wr32(RAM_DL + 8, ev::DL_DISPLAY());
  wr8(REG_DLSWAP, 2);
  wr8(REG_GPIO_DIR, 0x80 | rd8(REG_GPIO_DIR));       // DISP on
  wr8(REG_GPIO, 0x80 | rd8(REG_GPIO));
  wr8(REG_PCLK, 2);
  wr16(REG_PWM_HZ, 250);
  hz_ = spiHz;
  ok_ = true;
  if (rotate) { n_ = 0; put(0xFFFFFF36u); put(1); frameEnd(); }   // CMD_SETROTATE 1 (180 deg, touch follows)
  return true;
}

void Eve::setBacklight(uint8_t duty) { if (ok_) wr8(REG_PWM_DUTY, duty > 128 ? 128 : duty); }

void Eve::recover() {                                // co-processor fault: reset it
  wr8(REG_CPURESET, 1);
  wr16(REG_CMD_READ, 0);
  wr16(REG_CMD_WRITE, 0);
  wr16(REG_CMD_DL, 0);
  wr8(REG_CPURESET, 0);
}

bool Eve::busy() {
  if (!ok_) return true;
  uint16_t rd = rd16(REG_CMD_READ);
  if (rd == 0xFFF) { recover(); return true; }
  return rd16(REG_CMDB_SPACE) != 4092;
}

void Eve::frameStart(uint32_t clearRgb) {
  n_ = 0;
  put(0xFFFFFF00u);                                  // CMD_DLSTART
  put(ev::CLEAR_COLOR(clearRgb));
  put(ev::CLEAR());
}

void Eve::text(int x, int y, int font, uint16_t opt, const char* s) {
  put(0xFFFFFF0Cu);
  put(((uint32_t)(y & 0xFFFF) << 16) | (x & 0xFFFF));
  put(((uint32_t)opt << 16) | font);
  // string, NUL-terminated, padded to 4 bytes
  size_t l = strlen(s);
  for (size_t i = 0; i <= l; i += 4) {
    uint32_t w = 0;
    for (int k = 0; k < 4; k++) { size_t j = i + k; w |= (uint32_t)(j < l ? (uint8_t)s[j] : 0) << (8 * k); }
    put(w);
  }
}

void Eve::button(int x, int y, int w, int h, int font, uint16_t opt, const char* s) {
  put(0xFFFFFF0Du);
  put(((uint32_t)(y & 0xFFFF) << 16) | (x & 0xFFFF));
  put(((uint32_t)(h & 0xFFFF) << 16) | (w & 0xFFFF));
  put(((uint32_t)opt << 16) | font);
  size_t l = strlen(s);
  for (size_t i = 0; i <= l; i += 4) {
    uint32_t v = 0;
    for (int k = 0; k < 4; k++) { size_t j = i + k; v |= (uint32_t)(j < l ? (uint8_t)s[j] : 0) << (8 * k); }
    put(v);
  }
}

void Eve::rect(int x0, int y0, int x1, int y1, int radius) {
  put(ev::LINE_WIDTH(radius * 16));
  put(ev::BEGIN(ev::RECTS));
  put(ev::VERTEX2F(x0 + radius, y0 + radius));
  put(ev::VERTEX2F(x1 - radius, y1 - radius));
  put(ev::END());
}

void Eve::point(int x, int y, int r) {
  put(ev::POINT_SIZE(r * 16));
  put(ev::BEGIN(ev::POINTS));
  put(ev::VERTEX2F(x, y));
  put(ev::END());
}

bool Eve::frameEnd() {
  put(ev::DL_DISPLAY());
  put(0xFFFFFF01u);                                  // CMD_SWAP
  // Stream into the command FIFO in chunks that fit the free space.
  int i = 0;
  uint32_t t0 = micros();
  while (i < n_) {
    uint16_t space = rd16(REG_CMDB_SPACE) & ~3;
    if (rd16(REG_CMD_READ) == 0xFFF) { recover(); return false; }
    if (space < 4) { if (micros() - t0 > 20000) return false; continue; }
    int words = min((int)space / 4, n_ - i);
    SPI.beginTransaction(SPISettings(hz_, MSBFIRST, SPI_MODE0));
    digitalWriteFast(PIN_LCD_CS, LOW);
    uint32_t a = REG_CMDB_WRITE;
    SPI.transfer(0x80 | ((a >> 16) & 0x3F)); SPI.transfer(a >> 8); SPI.transfer(a);
    for (int k = 0; k < words; k++) {
      uint32_t w = buf_[i + k];
      SPI.transfer(w); SPI.transfer(w >> 8); SPI.transfer(w >> 16); SPI.transfer(w >> 24);
    }
    digitalWriteFast(PIN_LCD_CS, HIGH);
    SPI.endTransaction();
    i += words;
  }
  return true;
}

uint8_t Eve::touchTag() { return ok_ ? rd8(REG_TOUCH_TAG) : 0; }
