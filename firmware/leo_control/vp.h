// VP controller (VP_CONTROLLER_INTERFACE_SPEC.md): handshake, GP polling that also feeds
// its comms watchdog, TO state requests, HP/MC target, watchdog-reset recovery.
#pragma once
#include "link.h"

class Vp {
public:
  void begin();
  void service();
  void applyLinkSettings();

  // 0 unknown, 1 at air, 2 pumped: set by the Machine from the stage/vacuum state;
  // needed to pick TO 2 / TO 3 after a controller reset.
  void setVacHint(uint8_t h) { vacHint_ = h; }

  void informAir();              // TO 2
  void informPumped();           // TO 3
  void enter(float pa);          // MC, HP, TO 7
  void exit();                   // TO 10 (then TO 3 automatically at state 4)
  void setTarget(float pa);      // MC, HP
  void reset();                  // RE 0

  bool online() const { return link.online && gpValid_; }
  bool ready() const { return online() && hsDone_; }
  int state() const { return st_; }
  int requested() const { return req_; }
  int v8() const { return v8_; }
  int v14() const { return v14_; }
  int error() const { return err_; }
  int gauge() const { return gauge_; }
  float pa() const { return paFromCounts(gauge_); }
  bool chamberVp() const { return online() && st_ >= 7 && st_ <= 11; }   // gas in the chamber / isolated
  bool inHv() const { return online() && (st_ == 3 || st_ == 4); }
  bool atHp() const { return online() && st_ == 9; }
  const char* stateName() const;
  uint32_t rejectCount() const { return rejects_; }

  static float paFromCounts(int c);
  static float countsFromPa(float pa);

  Link link;

private:
  static void onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* cmd, const char* reply);
  void onReply(uint8_t tag, bool ok, const char* cmd, const char* reply);
  void sendTarget(float pa);
  void hsService();

  bool gpValid_ = false, hsDone_ = false, wasOnline_ = false;
  uint8_t hsStep_ = 0;
  uint8_t vacHint_ = 0;
  int gauge_ = 0, st_ = -1, req_ = -1, v8_ = 0, v14_ = 0, err_ = 0;
  uint32_t lastPoll_ = 0, rejects_ = 0, hsRetryMs_ = 0;
  bool exiting_ = false;
};

extern Vp vp;
