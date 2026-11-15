// Minimal FT813 (EVE2) driver for the Newhaven NHD-4.3-800480FT-CSXP-CTP:
// register access, co-processor command stream through REG_CMDB_WRITE, touch tags.
#pragma once
#include <Arduino.h>

namespace ev {
// display-list words
inline uint32_t CLEAR_COLOR(uint32_t rgb) { return 0x02000000u | (rgb & 0xFFFFFF); }
inline uint32_t CLEAR() { return 0x26000007u; }
inline uint32_t COLOR(uint32_t rgb) { return 0x04000000u | (rgb & 0xFFFFFF); }
inline uint32_t COLOR_A(uint8_t a) { return 0x10000000u | a; }
inline uint32_t TAG(uint8_t t) { return 0x03000000u | t; }
inline uint32_t BEGIN(uint8_t p) { return 0x1F000000u | p; }
inline uint32_t END() { return 0x21000000u; }
inline uint32_t LINE_WIDTH(uint16_t w16) { return 0x0E000000u | (w16 & 0xFFF); }
inline uint32_t POINT_SIZE(uint16_t s16) { return 0x0D000000u | (s16 & 0x1FFF); }
inline uint32_t VERTEX2F(int x, int y) { return 0x40000000u | ((uint32_t)(x * 16) & 0x7FFF) << 15 | ((uint32_t)(y * 16) & 0x7FFF); }
inline uint32_t DL_DISPLAY() { return 0; }
enum { POINTS = 2, LINES = 3, RECTS = 9 };
enum { OPT_FLAT = 256, OPT_CENTERX = 512, OPT_CENTERY = 1024, OPT_CENTER = 1536, OPT_RIGHTX = 2048 };
}

class Eve {
public:
  bool begin(uint32_t spiHz, bool clkExt, bool rotate, uint32_t waitMs);
  bool ok() const { return ok_; }
  void setBacklight(uint8_t duty);
  void setSpeed(uint32_t hz) { hz_ = hz; }

  // Command stream for one frame
  void frameStart(uint32_t clearRgb);
  void dl(uint32_t w) { put(w); }
  void text(int x, int y, int font, uint16_t opt, const char* s);
  void button(int x, int y, int w, int h, int font, uint16_t opt, const char* s);
  void fg(uint32_t rgb) { put(0xFFFFFF0Au); put(rgb); }
  void bg(uint32_t rgb) { put(0xFFFFFF09u); put(rgb); }
  void rect(int x0, int y0, int x1, int y1, int radius);
  void point(int x, int y, int r);
  bool frameEnd();                 // DISPLAY + SWAP, sent to the chip; false if it was busy
  bool busy();                     // co-processor still working on the previous frame
  uint8_t touchTag();

private:
  void put(uint32_t w) { if (n_ < (int)(sizeof buf_ / 4)) buf_[n_++] = w; }
  void wr8(uint32_t a, uint8_t v);
  void wr16(uint32_t a, uint16_t v);
  void wr32(uint32_t a, uint32_t v);
  uint8_t rd8(uint32_t a);
  uint16_t rd16(uint32_t a);
  uint32_t rd32(uint32_t a);
  void host(uint8_t c, uint8_t arg = 0);
  void recover();

  bool ok_ = false;
  uint32_t hz_ = 8000000;
  uint32_t buf_[1600];
  int n_ = 0;
};
