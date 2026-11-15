#include "machine.h"
#include "settings.h"
#include "log.h"
#include "eht.h"
#include "stgvac.h"
#include "vp.h"
#include "eo.h"

Machine machine;

void Machine::begin() {}

const char* Machine::opName() const {
  static const char* n[] = { "none", "pump", "vent", "vp_enter", "vp_exit", "vp_target" };
  return n[op_];
}

const char* Machine::summary() const {
  static char b[48];
  const char* vac;
  if (!stg.link.online) vac = "NO STAGE/VAC LINK";
  else if (vp.chamberVp()) vac = vp.atHp() ? "VP READY" : "VP CHANGING";
  else switch (stg.vac()) {
    case VS_SPVR: vac = "VACUUM READY"; break;
    case VS_NSP:  vac = "VENTED"; break;
    case VS_WVT:  vac = "VENTING"; break;
    case VS_SPE:  vac = "GAUGE ERROR"; break;
    case VS_UNKNOWN: vac = "VACUUM ?"; break;
    default:      vac = "PUMPING"; break;
  }
  const char* beam;
  switch (eht.beam()) {
    case BEAM_ON: beam = "BEAM ON"; break;
    case BEAM_STARTING: beam = "BEAM STARTING"; break;
    case BEAM_STOPPING: beam = "BEAM STOPPING"; break;
    case BEAM_EHT_OFF: beam = "EHT OFF, FIL. LIT"; break;
    default: beam = eht.filCold() ? "BEAM OFF" : "FILAMENT COOLING"; break;
  }
  snprintf(b, sizeof b, "%s  -  %s", vac, beam);
  return b;
}

// ------------------------------------------------------------------ checks + actions

const char* Machine::pump(bool dry) {
  if (op_ != MO_NONE) return "another sequence is running";
  if (!stg.link.online || !stg.configured()) return "stage/vacuum link down";
  if (stg.vac() != VS_NSP) return "chamber is not vented";
  if (dry) return nullptr;
  op_ = MO_PUMP; step_ = 0; pumpWarned_ = false;
  return nullptr;
}

const char* Machine::vent(bool dry) {
  if (op_ != MO_NONE && op_ != MO_PUMP) return "another sequence is running";
  if (!stg.link.online || !stg.configured()) return "stage/vacuum link down";
  if (stg.vac() == VS_NSP) return "already vented";
  if (stg.vac() == VS_WVT) return "already venting";
  if (dry) return nullptr;
  op_ = MO_VENT; step_ = 0;
  logf(LV_INFO, "sys", "vent: beam off, filament cool, Z down, then vent");
  return nullptr;
}

const char* Machine::beamOn(bool dry) {
  if (op_ != MO_NONE && op_ != MO_PUMP) return "a pressure change is running";
  if (op_ == MO_PUMP && !stg.vacReady()) return "still pumping";
  BeamState b = eht.beam();
  if (b == BEAM_ON || b == BEAM_STARTING) return "beam is already on";
  if (b == BEAM_STOPPING) return "beam is still ramping down";
  if (!stg.vacReady()) return "vacuum not ready";
  if (!eht.link.online) return "EHT link down";
  if (!eht.ready()) return eht.inhibited() ? "EHT inhibited by the vacuum system" : "EHT not ready (fault or starting)";
  if (si(VP_REQUIRED)) {
    if (!vp.ready()) return "VP controller link down";
    if (vp.state() != 3 && vp.state() != 9) return "VP controller not settled (state 3 or 9 needed)";
  } else if (vp.online() && vp.state() != 3 && vp.state() != 9) {
    return "VP controller not settled";
  }
  if (dry) return nullptr;
  if (op_ == MO_PUMP) finish("pumped");
  eht.beamOn();
  return nullptr;
}

const char* Machine::beamOff(bool dry) {
  BeamState b = eht.beam();
  if (b == BEAM_OFF) return dry ? "beam is already off" : nullptr;
  if (b == BEAM_STOPPING) return dry ? "beam is already stopping" : nullptr;
  if (dry) return nullptr;
  eht.beamOff();
  return nullptr;
}

const char* Machine::ehtOff(bool dry) {
  if (eht.beam() != BEAM_ON) return "beam is not on";
  if (dry) return nullptr;
  eht.ehtOff();
  return nullptr;
}

const char* Machine::vpEnter(float pa, bool dry) {
  if (op_ != MO_NONE) return "another sequence is running";
  if (!stg.vacReady()) return "vacuum not ready";
  if (!vp.ready()) return "VP controller link down";
  if (vp.state() != 3 && vp.state() != 4) return "VP controller not in high-vacuum mode";
  if (!(pa >= SMETA[OP_VP_PA].mn && pa <= SMETA[OP_VP_PA].mx)) return "pressure out of range";
  if (dry) return nullptr;
  settingSet(OP_VP_PA, pa);
  pa_ = pa;
  op_ = MO_VP_ENTER; step_ = 0;
  logf(LV_INFO, "sys", "enter VP at %.0f Pa: beam off and filament cool first", pa);
  return nullptr;
}

const char* Machine::vpExit(bool dry) {
  if (op_ != MO_NONE && op_ != MO_VP_ENTER && op_ != MO_VP_TARGET) return "another sequence is running";
  if (!vp.ready()) return "VP controller link down";
  if (!vp.chamberVp() && op_ == MO_NONE) return "not in VP";
  if (dry) return nullptr;
  op_ = MO_VP_EXIT; step_ = 0;
  logf(LV_INFO, "sys", "leave VP: beam off and filament cool first");
  return nullptr;
}

const char* Machine::vpTarget(float pa) {
  if (!(pa >= SMETA[OP_VP_PA].mn && pa <= SMETA[OP_VP_PA].mx)) return "pressure out of range";
  if (vp.chamberVp()) {
    if (op_ != MO_NONE) return "another sequence is running";
    if (vp.state() != 8 && vp.state() != 9) return "VP transition in progress";
    settingSet(OP_VP_PA, pa);
    pa_ = pa;
    op_ = MO_VP_TARGET; step_ = 0;
    logf(LV_INFO, "sys", "VP target %.0f Pa: beam off and filament cool first", pa);
  } else {
    settingSet(OP_VP_PA, pa);                  // used at the next VP entry
  }
  return nullptr;
}

void Machine::abort() {
  if (op_ == MO_NONE) return;
  logf(LV_WARN, "sys", "%s sequence aborted", opName());
  op_ = MO_NONE;
  act_[0] = 0;
}

void Machine::safe(const char* why) {
  logf(LV_WARN, "sys", "safe state: %s", why);
  abort();
  stg.stop();
  BeamState b = eht.beam();
  if (b != BEAM_OFF && b != BEAM_STOPPING) eht.beamOff();
}

// ------------------------------------------------------------------ sequences

void Machine::finish(const char* msg) {
  logf(LV_INFO, "sys", "%s done: %s", opName(), msg);
  op_ = MO_NONE;
  act_[0] = 0;
}

void Machine::fail(const char* msg) {
  logf(LV_FAULT, "sys", "%s failed: %s", opName(), msg);
  op_ = MO_NONE;
  act_[0] = 0;
}

bool Machine::coolStep() {
  BeamState b = eht.beam();
  if (b != BEAM_OFF) {
    if (b != BEAM_STOPPING) eht.beamOff();
    snprintf(act_, sizeof act_, "Beam off: %s", eht.activity()[0] ? eht.activity() : "ramping");
    return false;
  }
  if (!eht.filCold()) {
    snprintf(act_, sizeof act_, "Filament cooling %.0f s", eht.coolRemainingS());
    return false;
  }
  return true;
}

void Machine::service() {
  monitors();
  uint32_t now = millis();
  switch (op_) {
  case MO_NONE: break;

  case MO_PUMP:
    if (step_ == 0) { stg.pump(); t0_ = now; step_ = 1; snprintf(act_, sizeof act_, "Pumping"); }
    else if (step_ == 1 && now - t0_ >= (uint32_t)si(VP_PUMP_DELAY_MS)) { if (vp.ready()) vp.informPumped(); step_ = 2; }
    else if (step_ == 2) {
      snprintf(act_, sizeof act_, "Pumping: %s", stg.vacText());
      if (stg.vacReady()) finish("vacuum ready");
      else if (!pumpWarned_ && now - t0_ > (uint32_t)(sf(SYS_PUMP_WARN_MIN) * 60000)) {
        pumpWarned_ = true;
        logf(LV_WARN, "vac", "pump-down not ready after %.0f min", sf(SYS_PUMP_WARN_MIN));
      }
    }
    break;

  case MO_VENT:
    switch (step_) {
    case 0: if (coolStep()) step_ = 1; break;
    case 1:
      if (vp.chamberVp() && si(SYS_VENT_EXIT_VP)) { vp.exit(); t0_ = now; step_ = 2; snprintf(act_, sizeof act_, "Leaving VP"); }
      else step_ = 3;
      break;
    case 2:
      if (vp.inHv() && vp.state() == 3) step_ = 3;
      else if (now - t0_ > (uint32_t)(sf(VP_EXIT_TO_S) * 1000)) fail("VP did not return to high vacuum");
      break;
    case 3:
      if (si(STG_VENT_Z_EN) && stg.homed()) {
        long c[5];
        for (int i = 0; i < 5; i++) c[i] = stg.axis(i).pos;
        c[2] = si(STG_VENT_Z);
        stg.gotoCounts(c);
        t0_ = now; seq0_ = stg.sdSeq(); step_ = 4;
        snprintf(act_, sizeof act_, "Lowering Z");
      } else step_ = 5;
      break;
    case 4:
      if (now - t0_ > 1000 && stg.sdSeq() >= seq0_ + 2 && !stg.moving()) step_ = 5;
      else if (now - t0_ > (uint32_t)(sf(STG_MOVE_TO_S) * 1000)) { stg.stop(); fail("Z move timed out"); }
      break;
    case 5:
      stg.vent(); t0_ = now; step_ = 6;
      snprintf(act_, sizeof act_, "Venting");
      break;
    case 6:
      if (stg.vac() == VS_NSP && now - t0_ > 2000) {
        if (vp.ready()) vp.informAir();
        finish("vented");
      } else if (now - t0_ > 300000) fail("no NSP within 5 min");
      break;
    }
    break;

  case MO_VP_ENTER:
    switch (step_) {
    case 0: if (coolStep()) step_ = 1; break;
    case 1:
      if (!stg.vacReady()) { fail("vacuum not ready"); break; }
      if (vp.state() == 4) { vp.informPumped(); break; }
      if (vp.state() != 3) break;
      vp.enter(pa_); t0_ = now; step_ = 2;
      break;
    case 2:
      snprintf(act_, sizeof act_, "VP %s, %.0f Pa", vp.stateName(), vp.pa());
      if (vp.error()) fail("VP controller reported an error");
      else if (vp.atHp() && now - t0_ > 3000) finish("at pressure");
      else if (now - t0_ > (uint32_t)(sf(VP_ENTER_TO_S) * 1000)) fail("target pressure not reached");
      break;
    }
    break;

  case MO_VP_EXIT:
    switch (step_) {
    case 0: if (coolStep()) step_ = 1; break;
    case 1: vp.exit(); t0_ = now; step_ = 2; break;
    case 2:
      snprintf(act_, sizeof act_, "VP %s, %.0f Pa", vp.stateName(), vp.pa());
      if (vp.state() == 3 && now - t0_ > 3000) finish("high vacuum");
      else if (now - t0_ > (uint32_t)(sf(VP_EXIT_TO_S) * 1000)) fail("did not reach GUN_ENABLE_OK");
      break;
    }
    break;

  case MO_VP_TARGET:
    switch (step_) {
    case 0: if (coolStep()) step_ = 1; break;
    case 1: vp.setTarget(pa_); t0_ = now; step_ = 2; break;
    case 2:
      snprintf(act_, sizeof act_, "VP %s, %.0f Pa", vp.stateName(), vp.pa());
      if (vp.atHp() && now - t0_ > 5000) finish("at pressure");
      else if (now - t0_ > (uint32_t)(sf(VP_ENTER_TO_S) * 1000)) fail("target pressure not reached");
      break;
    }
    break;
  }
}

void Machine::monitors() {
  VacState v = stg.vac();
  bool vacKnown = stg.link.online && stg.configured();
  vp.setVacHint(!vacKnown ? 0 : (v == VS_NSP || v == VS_WVT) ? 1 : (v == VS_UNKNOWN ? 0 : 2));
  eht.setChamberVp(vp.chamberVp());
  stg.setMag(sf(OP_MAG));

  // Vacuum lost with the beam on: the hardware interlock cuts the EHT; take the filament down too.
  BeamState b = eht.beam();
  if (vacKnown && b != BEAM_OFF && v != VS_SPVR) {
    if (si(SYS_VACLOSS_ABRUPT)) eht.abruptOff("vacuum no longer ready");
    else if (b != BEAM_STOPPING) { logf(LV_FAULT, "sys", "vacuum no longer ready: beam off"); eht.beamOff(); }
  }

  // Gas reaching the column during VP: the Penning side should stay pumped.
  if (vacKnown && vp.online() && vp.state() >= 7 && vp.state() <= 9 && v != VS_SP && v != VS_SPVR) {
    if (!gasAbortDone_) {
      gasAbortDone_ = true;
      logf(LV_FAULT, "vp", "Penning side lost vacuum during VP: returning to high vacuum");
      if (op_ != MO_NONE) { op_ = MO_NONE; act_[0] = 0; }
      vp.exit();
    }
  } else gasAbortDone_ = false;

  // Keep the VP controller's LP state in line when the vacuum state changes on its own.
  if (vacKnown && v != lastVac_ && vp.ready() && op_ == MO_NONE) {
    if (v == VS_NSP && vp.state() == 3) vp.informAir();
    if ((v == VS_WTUS || v == VS_WP || v == VS_SP || v == VS_SPVR) && vp.state() == 2) vp.informPumped();
  }
  if (vacKnown) lastVac_ = v;
}
