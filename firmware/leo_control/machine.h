// Machine: the cross-subsystem sequences and the safety rules.
//  - every operator action is checked here first (the same checks grey out the touch buttons);
//  - pump, vent and VP changes run as step sequences that first take the beam off and wait
//    for the filament to cool (filament off and cold before any pressure change);
//  - monitors: vacuum loss with the beam on, gas reaching the column during VP,
//    keeping the VP controller's LP state in line with the vacuum state.
#pragma once
#include <Arduino.h>

enum MachOp : uint8_t { MO_NONE, MO_PUMP, MO_VENT, MO_VP_ENTER, MO_VP_EXIT, MO_VP_TARGET };

class Machine {
public:
  void begin();
  void service();

  // Each returns nullptr when accepted (or, with dry=true, when it would be), else the reason.
  const char* pump(bool dry = false);
  const char* vent(bool dry = false);
  const char* beamOn(bool dry = false);
  const char* beamOff(bool dry = false);
  const char* ehtOff(bool dry = false);
  const char* vpEnter(float pa, bool dry = false);
  const char* vpExit(bool dry = false);
  const char* vpTarget(float pa);
  void safe(const char* why);      // abort sequences, stop the stage, beam off (ramped)
  void abort();                    // abort the running sequence only

  MachOp op() const { return op_; }
  const char* opName() const;
  const char* activity() const { return act_; }
  const char* summary() const;     // one-line machine state for the display

private:
  bool coolStep();                 // true once the beam is off and the filament cold
  void finish(const char* msg);
  void fail(const char* msg);
  void monitors();

  MachOp op_ = MO_NONE;
  uint8_t step_ = 0;
  uint32_t t0_ = 0, seq0_ = 0;
  float pa_ = 0;
  bool pumpWarned_ = false, gasAbortDone_ = false;
  uint8_t lastVac_ = 0;
  char act_[64] = "";
};

extern Machine machine;
