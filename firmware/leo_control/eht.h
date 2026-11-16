// EHT / gun supply (unit M08): start-up, status polling, fault handling,
// beam on/off sequences with the filament and >20 kV ramps (EHT_INTERFACE_SPEC.md).
// Interlocks against vacuum and VP state are checked by the Machine before calling in.
#pragma once
#include "link.h"

enum BeamState : uint8_t { BEAM_OFF, BEAM_STARTING, BEAM_ON, BEAM_EHT_OFF, BEAM_STOPPING };

class Eht {
public:
  void begin();
  void service();
  void applyLinkSettings();

  void beamOn();                 // OFF -> ramped start; EHT_OFF -> resume (filament already hot)
  void beamOff();                // full shutdown, filament ramped to zero
  void ehtOff();                 // EHT off, filament stays lit
  void abruptOff(const char* why);   // all supplies off at once (faults, vacuum loss)
  void resetFaults();            // .R
  void setChamberVp(bool vp) { chamberVp_ = vp; }

  BeamState beam() const { return beam_; }
  const char* beamName() const;
  bool busy() const { return seq_ != SQ_NONE; }
  const char* activity() const { return activity_; }
  bool filCold() const;              // filament off and cooled for eht.fil_cool_s
  float coolRemainingS() const;
  bool ready() const;                // link up, started, status OK (no inhibit / fault)
  bool inhibited() const { return sbValid_ && (sb_ & 0x10); }
  uint8_t status() const { return sb_; }
  bool statusValid() const { return sbValid_; }
  float kvApplied() const { return kvCur_; }
  int filApplied() const { return filCur_; }
  // What the supply is being told now (the link has no read-back): kV only while the EHT output is on,
  // emission as last sent (0 unless the beam is on).
  float kvOut() const;
  float emisApplied() const { return emisSent_ < 0 ? 0 : emisSent_ / 10.0f; }
  float kvSettled() const { return kvSettled_; }
  int word() const { return wordSent_; }
  const char* hwid() const { return hwid_; }

  Link link;

private:
  enum Seq : uint8_t { SQ_NONE, SQ_STARTUP, SQ_ON, SQ_RESUME, SQ_EHTOFF, SQ_OFF, SQ_KV, SQ_FIL };
  static void onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* cmd, const char* reply);
  void onReply(uint8_t tag, bool ok, const char* cmd, const char* reply);
  void handleStatus(uint8_t bb);
  void runSeq();
  void reconcile();
  void startSeq(Seq s) { seq_ = s; step_ = 0; nextMs_ = millis(); }
  void wait(uint32_t ms) { nextMs_ = millis() + ms; }
  int idleWord() const;
  void cmdO(int w);
  void cmdE(float kv);
  void cmdF(int mA);
  void cmdB(float uA);
  void cmdC(float v);
  void cmdPM(int ch, int v);
  void cmd(const char* s, uint8_t tag = 0);
  void setBeam(BeamState b);
  void markFilOff();
  float nextKvStep(float cur, float tgt) const;

  BeamState beam_ = BEAM_OFF;
  Seq seq_ = SQ_NONE, seqLost_ = SQ_NONE;
  uint8_t step_ = 0;
  uint32_t nextMs_ = 0, lastPollMs_ = 0, startupRetryMs_ = 0, filOffMs_ = 0, lastResetMs_ = 0;
  bool startupDone_ = false, needRestore_ = false, shutdownAllOff_ = false;
  bool chamberVp_ = false, wasOnline_ = false;
  uint8_t sb_ = 0;
  bool sbValid_ = false;
  float kvCur_ = 0, kvSettled_ = 0;
  int filCur_ = 0;
  int wordSent_ = -1, emisSent_ = -1, collSent_ = -1, pmSent_[3] = {-1, -1, -1};
  int typeSent_ = -1, anodeSent_ = -1;
  char hwid_[8] = "";
  char activity_[48] = "";
};

extern Eht eht;
