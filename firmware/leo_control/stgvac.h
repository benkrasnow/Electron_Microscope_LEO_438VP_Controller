// Stage / vacuum controller (STAGE_VACUUM_INTERFACE_SPEC.md): start-up configuration,
// .VT/.SD polling, =20/=40 event service, pump/vent, user limits per vacuum state,
// stage moves and homing, joystick pixel size (.SW).
#pragma once
#include "link.h"

enum VacState : uint8_t { VS_UNKNOWN, VS_NSP, VS_WTUS, VS_WP, VS_SP, VS_SPVR, VS_SPE, VS_WVT, VS_OTHER };

struct AxisState { long pos; bool moving; bool init; };

class StgVac {
public:
  void begin();
  void service();
  void applyLinkSettings();

  // vacuum
  VacState vac() const { return vac_; }
  const char* vacName() const;          // controller's own code (NSP, SPVR, ...)
  const char* vacText() const;          // plain words for the display
  long gauge() const { return gauge_; }
  double torr() const;                  // Penning pressure, NAN when the gauge is off
  uint8_t inhibits() const { return vsValid_ ? vs_[0] : 0xFF; }
  const uint8_t* vsBytes() const { return vs_; }
  bool vacReady() const;                // SPVR and all inhibits released
  bool configured() const { return configured_; }
  bool pump();
  bool vent();
  const char* version() const { return ver_; }

  // stage
  const AxisState& axis(int i) const { return ax_[i]; }
  bool sdValid() const { return sdValid_; }
  uint32_t sdSeq() const { return sdSeq_; }     // increments with every .SD reply
  bool moving() const;
  bool homed() const;
  bool homing() const { return homeStep_ != 0; }
  const char* homeActivity() const { return homeAct_; }
  const uint8_t* spBytes() const { return sp_; }
  bool limitActive() const { return spEvent_; }
  // absolute go-to in counts; returns nullptr or an error text
  const char* gotoCounts(const long c[5]);
  void stop();
  const char* home();
  void activeLimits(long lo[5], long hi[5]) const;
  static double toUnits(int axis, long counts);
  static long toCounts(int axis, double units);
  void setMag(float mag) { mag_ = mag; }

  Link link;

private:
  static void onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* cmd, const char* reply);
  void onReply(uint8_t tag, bool ok, const char* cmd, const char* reply);
  bool configCmd(int i, char* b, size_t n, uint8_t& tag);
  void sendLimits();
  void parseVT(const char* r);
  void parseSD(const char* r);
  void parseHex(const char* r, uint8_t* out, int n);
  void homeService();

  bool configured_ = false, wasOnline_ = false;
  int cfgIdx_ = -1;                     // -1: not started
  VacState vac_ = VS_UNKNOWN;
  long gauge_ = 0;
  uint8_t vs_[8] = {0};
  bool vsValid_ = false, needVS_ = false, needSP_ = false, spEvent_ = false;
  uint8_t sp_[6] = {0};
  AxisState ax_[5] = {};
  bool sdValid_ = false, wasHomed_ = false;
  uint32_t sdSeq_ = 0;
  uint32_t lastVT_ = 0, lastSD_ = 0, lastSP_ = 0;
  char ver_[24] = "";
  char vx_[8] = "", vv_[8] = "";
  // homing
  uint8_t homeStep_ = 0;
  uint32_t homeT0_ = 0, homeSeq_ = 0;
  char homeAct_[32] = "";
  // joystick pixel size
  float mag_ = 0;
  long swSent_ = 0;
  bool airLimits_ = true, limitsValid_ = false;
};

extern StgVac stg;
