// EO board (SCAN_GENERATOR_INTERFACE_SPEC.md): F3 register frames and F4 replies,
// boot restore, scan modes (external/OBI, internal raster, line, spot), magnification /
// rotation / tilt / shift coil weights with range switching, lenses, stigmators,
// focus wobble, dynamic focus, kV compensation. Follows the op.* settings: commands
// change those settings and this module sends whatever changed.
#pragma once
#include <Arduino.h>

enum ScanMode : uint8_t { SCAN_EXT = 0, SCAN_RASTER = 1, SCAN_LINE = 2, SCAN_SPOT = 3 };

class Eo {
public:
  void begin();
  void service(float kvSettled);
  void applyPins();                      // idle levels after a polarity change
  void restoreAll();                     // boot burst with the current state, then full set-up
  void calibrationChanged() { calDirty_ = true; }

  // Raw access (also used by the USB "eo" command)
  void write(int chip, int reg, uint16_t v, uint32_t delayAfterUs = 0);
  int  readNow(int chip, int reg);       // -1 if no reply; blocks ~20 us
  void freeze(bool on);
  void restartFrame();

  bool linkOk() const { return linkOk_; }
  int  range() const { return range_; }
  const uint16_t* weights() const { return w_; }
  int  queued() const;
  uint32_t frames() const;
  bool frozen() const { return frozen_; }
  float linePeriodUs() const { return lineUs_; }
  const char* modeName() const;

private:
  void computeWeights(int& rng, uint16_t w[4], uint16_t& shA, uint16_t& shB) const;
  void applyOptics(bool force);
  void applyLenses(bool obj, bool cond);
  void applyStig();
  void applyScan();
  void applyWobble();
  void speedBlock(int speed);
  void startTimer(bool on);
  int  c2opt() const;
  int  c3opt() const;

  int range_ = -1;
  uint16_t w_[4] = {32768, 32768, 32768, 32768};
  uint16_t shA_ = 2047, shB_ = 2047;
  bool linkOk_ = false, calDirty_ = true, frozen_ = false, started_ = false;
  uint32_t lastHb_ = 0, hbFails_ = 0;
  float lineUs_ = 0, kvUsed_ = 0;
  // applied copies of the op.* values
  float aMag_ = -1, aRot_ = 1e9, aWd_ = -1, aTilt_ = 1e9, aSx_ = 1e9, aSy_ = 1e9;
  float aObjC_ = -1, aObjF_ = -1, aCond_[4] = {-1, -1, -1, -1}, aWob_ = -1, aDynf_ = 1e9;
  int aStigX_ = -1, aStigY_ = -1, aScan_ = -1, aSpeed_ = -1, aSpotX_ = -1, aSpotY_ = -1, aLineY_ = -1, aWobFast_ = -1;
};

extern Eo eo;
