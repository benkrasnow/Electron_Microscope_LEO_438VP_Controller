#include "eht.h"
#include "config.h"
#include "settings.h"
#include "log.h"


Eht eht;

enum { T_CMD = 0, T_STATUS, T_ID };

static int clamp12(long v) { return v < 0 ? 0 : (v > 0xFFF ? 0xFFF : (int)v); }

void Eht::begin() {
  link.begin(&EHT_PORT, "eht", FRAME_EQ, "\r", onReplyThunk, this);
  applyLinkSettings();
  // Filament cool-down across a reboot: use the RTC if it has been set.
  filOffMs_ = millis();
  unsigned long now = rtc_get();
  if (now > 1600000000UL && S[ST_FIL_OFF_T] > 0 && now >= (unsigned long)S[ST_FIL_OFF_T]) {
    unsigned long el = now - (unsigned long)S[ST_FIL_OFF_T];
    unsigned long cap = 3600;
    filOffMs_ = millis() - min(el, cap) * 1000UL;
  }
  kvSettled_ = sf(OP_KV);
}

void Eht::applyLinkSettings() {
  link.setInvert(si(EHT_TX_INV), si(EHT_RX_INV));
  link.setTiming(si(EHT_TIMEOUT_MS), si(EHT_GAP_MS), si(EHT_RETRIES));
}

const char* Eht::beamName() const {
  switch (beam_) {
    case BEAM_OFF:      return filCold() ? "off" : "cooling";
    case BEAM_STARTING: return "starting";
    case BEAM_ON:       return "on";
    case BEAM_EHT_OFF:  return "eht_off";
    default:            return "stopping";
  }
}

bool Eht::filCold() const {
  return beam_ == BEAM_OFF && (millis() - filOffMs_) >= (uint32_t)(sf(EHT_FIL_COOL_S) * 1000.0f);
}

float Eht::coolRemainingS() const {
  if (beam_ != BEAM_OFF) return sf(EHT_FIL_COOL_S);
  float r = sf(EHT_FIL_COOL_S) - (millis() - filOffMs_) / 1000.0f;
  return r > 0 ? r : 0;
}

bool Eht::ready() const {
  return link.online && startupDone_ && sbValid_ && (sb_ & 0x5E) == 0x40;
}

int Eht::idleWord() const {
  int w = si(EHT_O_BASE) | si(EHT_O_DETECT);
  bool scint = !inhibited() && !(chamberVp_ && si(EHT_SCINT_OFF_VP));
  if (scint) w |= si(EHT_O_SCINT);
  return w;
}

void Eht::cmd(const char* s, uint8_t tag) { link.push(s, tag); }

void Eht::cmdO(int w) {
  char b[12]; snprintf(b, sizeof b, ".O%04X", w & 0xFFFF); cmd(b); wordSent_ = w;
}
void Eht::cmdE(float kv) {
  char b[12]; snprintf(b, sizeof b, ".E%03X", clamp12(lroundf(kv * 100.0f) - 2)); cmd(b); kvCur_ = kv;
}
void Eht::cmdF(int mA) {
  char b[12]; snprintf(b, sizeof b, ".F%03X", clamp12(mA - 16)); cmd(b); filCur_ = mA;
}
void Eht::cmdB(float uA) {
  int c = clamp12(lroundf(uA * 10.0f));
  char b[12]; snprintf(b, sizeof b, ".B%03X", c); cmd(b); emisSent_ = c;
}
void Eht::cmdC(float v) {
  int c = clamp12(2048 + lroundf(v * 5.0f));
  char b[12]; snprintf(b, sizeof b, ".C%03X", c); cmd(b); collSent_ = c;
}
void Eht::cmdPM(int ch, int v) {
  char b[12]; snprintf(b, sizeof b, ".%d%03X", ch, clamp12(v)); cmd(b); pmSent_[ch - 1] = clamp12(v);
}

void Eht::setBeam(BeamState b) {
  if (b == beam_) return;
  beam_ = b;
  int st = (b == BEAM_ON) ? 1 : (b == BEAM_EHT_OFF) ? 3 : (b == BEAM_OFF) ? 0 : 2;
  if (si(ST_BEAM) != st) settingSet(ST_BEAM, st);
}

void Eht::markFilOff() {
  filOffMs_ = millis();
  unsigned long t = rtc_get();
  if (t > 1600000000UL) settingSet(ST_FIL_OFF_T, t);
}

// ---------------------------------------------------------------- operator actions

void Eht::beamOn() {
  if (beam_ == BEAM_OFF) { startSeq(SQ_ON); logf(LV_INFO, "eht", "beam on: %.2f kV, filament %d mA", sf(OP_KV), (int)si(OP_FIL_MA)); }
  else if (beam_ == BEAM_EHT_OFF) { startSeq(SQ_RESUME); logf(LV_INFO, "eht", "EHT on (filament already lit)"); }
}

void Eht::beamOff() {
  if (beam_ == BEAM_OFF) return;
  startSeq(SQ_OFF);                  // starts once already-queued commands have gone out
  logf(LV_INFO, "eht", "beam off: ramping filament down");
}

void Eht::ehtOff() {
  if (beam_ != BEAM_ON) return;
  startSeq(SQ_EHTOFF);
  logf(LV_INFO, "eht", "EHT off, filament stays lit");
}

void Eht::abruptOff(const char* why) {
  bool wasOn = beam_ != BEAM_OFF;
  link.clearQueue();
  seq_ = SQ_NONE;
  int base = si(EHT_O_BASE);
  cmdO(base);
  cmdB(0);
  cmdF(si(EHT_FIL_OFF_MA));
  filCur_ = 0;
  shutdownAllOff_ = true;
  if (wasOn) markFilOff();
  setBeam(BEAM_OFF);
  activity_[0] = 0;
  logf(wasOn ? LV_FAULT : LV_WARN, "eht", "supplies cut: %s", why);
}

void Eht::resetFaults() {
  cmd(".R");
  cmd("?S", T_STATUS);
}

// ---------------------------------------------------------------- link replies

void Eht::onReplyThunk(void* ctx, uint8_t tag, bool ok, const char* c, const char* r) {
  ((Eht*)ctx)->onReply(tag, ok, c, r);
}

void Eht::onReply(uint8_t tag, bool ok, const char* cmdText, const char* reply) {
  if (tag == TAG_UNSOLICITED) return;
  if (!ok) {
    if (wasOnline_) logf(LV_WARN, "eht", "no reply to %s: link down", cmdText);
    wasOnline_ = false;
    if (seq_ != SQ_NONE && seq_ != SQ_STARTUP) { seqLost_ = seq_; seq_ = SQ_NONE; link.clearQueue(); }
    if (seq_ == SQ_STARTUP) { seq_ = SQ_NONE; startupRetryMs_ = millis() + (uint32_t)(sf(EHT_POLL_S) * 1000); }
    return;
  }
  if (!wasOnline_) {
    wasOnline_ = true;
    logf(LV_INFO, "eht", "link up");
    if (startupDone_) link.push("?S", T_STATUS, true);   // re-check for a reset of the set
  }
  if (reply[0] != '=' || strlen(reply) < 3) return;
  char hx[3] = { reply[1], reply[2], 0 };
  int rr = strtol(hx, nullptr, 16);
  if (tag == T_STATUS && strlen(reply) >= 5) {
    char hb[3] = { reply[3], reply[4], 0 };
    handleStatus(strtol(hb, nullptr, 16));
  } else if (tag == T_ID) {
    strlcpy(hwid_, reply + 3, sizeof hwid_);
  } else if (rr != 0x00 && rr != 0x20) {
    logf(LV_WARN, "eht", "%s refused (=%02X)", cmdText, rr);
    if (seq_ == SQ_ON || seq_ == SQ_RESUME) abruptOff("command refused during beam on");
  }
}

void Eht::handleStatus(uint8_t bb) {
  bb &= 0x5F;
  uint8_t prev = sbValid_ ? sb_ : 0x40;
  sb_ = bb;
  sbValid_ = true;

  if (bb & 0x0E) {                                    // latched faults
    uint8_t fresh = bb & ~prev;
    if (fresh & 0x04) logf(LV_FAULT, "eht", "filament blown");
    if (fresh & 0x02) logf(LV_FAULT, "eht", "EHT set tripped");
    if (fresh & 0x08) logf(beam_ != BEAM_OFF ? LV_FAULT : LV_INFO, "eht",
                           beam_ != BEAM_OFF ? "EHT set restarted: settings lost" : "EHT set reset flag");
    if (beam_ != BEAM_OFF) abruptOff("EHT fault");
    // .R then ?S, as LEO-32 does; at most once per poll period (the reset flag
    // stays set while the vacuum inhibit is active).
    if (millis() - lastResetMs_ >= (uint32_t)(sf(EHT_POLL_S) * 1000)) {
      lastResetMs_ = millis();
      cmd(".R");
      cmd("?S", T_STATUS);
    }
    needRestore_ = true;
    return;
  }
  if (bb & 0x10) {                                    // vacuum inhibit (hardware line)
    if (!(prev & 0x10)) logf(LV_INFO, "eht", "inhibited by the vacuum system");
    if (beam_ != BEAM_OFF) abruptOff("vacuum inhibit");
    return;
  }
  if (prev & 0x10) { logf(LV_INFO, "eht", "vacuum inhibit released"); needRestore_ = true; }
  if (seqLost_ != SQ_NONE) {                          // link came back after a loss mid-sequence
    Seq s = seqLost_;
    seqLost_ = SQ_NONE;
    if (s == SQ_EHTOFF) startSeq(SQ_EHTOFF);
    else if (s == SQ_ON || s == SQ_RESUME || s == SQ_OFF) {
      logf(LV_WARN, "eht", "link lost during a beam sequence: ramping down");
      beam_ = BEAM_ON;                                 // so beamOff() runs from the last sent values
      beamOff();
    }
  }
}

// ---------------------------------------------------------------- sequences

float Eht::nextKvStep(float cur, float tgt) const {
  float above = sf(EHT_KV_RAMP_ABOVE), step = sf(EHT_KV_RAMP_STEP);
  if (tgt > cur) {
    if (tgt <= above) return tgt;
    if (cur < above) return above;
    return min(cur + step, tgt);
  } else {
    if (cur <= above) return tgt;
    float n = cur - step;
    return n > max(tgt, above) ? n : max(tgt, above);
  }
}

void Eht::runSeq() {
  if (seq_ == SQ_NONE || !link.idle() || (int32_t)(millis() - nextMs_) < 0) return;
  const int base = si(EHT_O_BASE), oE = si(EHT_O_EHT), oF = si(EHT_O_FIL);
  const uint32_t ramp = si(EHT_RAMP_MS);
  const int filT = si(OP_FIL_MA);
  const float kvT = sf(OP_KV);

  switch (seq_) {
  case SQ_STARTUP:
    if (step_ == 0) {                 // ?S before .R, so a reset of the set is still visible
      cmd("?S", T_STATUS); cmd("?H", T_ID);
      step_ = 1;
    } else {
      if (!link.online) { seq_ = SQ_NONE; startupRetryMs_ = millis() + (uint32_t)(sf(EHT_POLL_S) * 1000); return; }
      int pers = si(ST_BEAM);
      bool setReset = sb_ & 0x08, inh = sb_ & 0x10;
      if ((pers == 1 || pers == 3) && !setReset && !inh) {
        kvCur_ = kvSettled_ = kvT; filCur_ = filT;
        beam_ = pers == 1 ? BEAM_ON : BEAM_EHT_OFF;
        int w = pers == 1 ? (idleWord() | oE | oF) : (base | oF);
        cmdO(w);
        cmd(".R");
        if (pers == 1) { cmdE(kvT); cmdB(sf(OP_EMIS_UA)); }
        cmdF(filT);
        logf(LV_INFO, "eht", "adopted running beam after restart (%s)", pers == 1 ? "beam on" : "EHT off, filament lit");
      } else {
        if (pers != 0) {
          logf(LV_WARN, "eht", "beam state after restart unknown or lost: supplies off");
          cmdB(0); cmdO(base); cmdF(si(EHT_FIL_OFF_MA));
          markFilOff();
          beam_ = BEAM_ON;           // force the persisted state update below
          setBeam(BEAM_OFF);
        }
        filCur_ = 0;
        if (sb_ & 0x0E) cmd(".R");
        cmdO(idleWord());
        cmdB(0);
      }
      needRestore_ = true;           // send .T .A .C .1-.3 through reconcile
      startupDone_ = true;
      seq_ = SQ_NONE;
    }
    break;

  case SQ_ON:
    switch (step_) {
    case 0:
      setBeam(BEAM_STARTING);
      shutdownAllOff_ = false;
      cmdO(idleWord());
      cmdB(sf(OP_EMIS_UA));
      snprintf(activity_, sizeof activity_, "EHT on");
      wait(si(EHT_ON_DELAY_MS)); step_ = 1; break;
    case 1:
      cmdO(idleWord() | oE);
      cmdE(sf(EHT_KV_START));
      cmdE(min(kvT, sf(EHT_KV_RAMP_ABOVE)));
      wait(si(EHT_FILON_DELAY_MS)); step_ = 2; break;
    case 2:
      if (kvCur_ < kvT - 0.001f) {
        cmdE(nextKvStep(kvCur_, kvT));
        snprintf(activity_, sizeof activity_, "EHT ramp %.1f kV", kvCur_);
        wait(ramp); break;
      }
      kvSettled_ = kvCur_;
      // Low filament current first, then the supply bit: the set may still hold an old .F value.
      cmdF(si(EHT_FIL_START_MA));
      cmdO(idleWord() | oE | oF);
      wait(ramp); step_ = 3; break;
    case 3: {
      int fastEnd = min((int)si(EHT_FIL_FAST_TO), filT);
      if (filCur_ < fastEnd) {
        cmdF(min(filCur_ + (int)si(EHT_FIL_FAST_STEP), fastEnd));
        snprintf(activity_, sizeof activity_, "Filament %.2f A", filCur_ / 1000.0f);
        wait(ramp); break;
      }
      wait(filCur_ < filT ? si(EHT_FIL_PAUSE_MS) : 0); step_ = 4; break;
    }
    case 4:
      if (filCur_ < filT) {
        cmdF(min(filCur_ + (int)si(EHT_FIL_SLOW_STEP), filT));
        snprintf(activity_, sizeof activity_, "Filament %.2f A", filCur_ / 1000.0f);
        wait(ramp); break;
      }
      setBeam(BEAM_ON);
      activity_[0] = 0;
      seq_ = SQ_NONE;
      logf(LV_INFO, "eht", "beam on");
      break;
    }
    break;

  case SQ_RESUME:
    if (step_ == 0) {
      setBeam(BEAM_STARTING);
      int w = idleWord() | oE | oF;
      cmdO(w); cmdB(sf(OP_EMIS_UA)); cmdO(w);
      cmdE(sf(EHT_KV_START));
      cmdE(min(kvT, sf(EHT_KV_RAMP_ABOVE)));
      wait(ramp); step_ = 1;
    } else if (kvCur_ < kvT - 0.001f) {
      cmdE(nextKvStep(kvCur_, kvT));
      snprintf(activity_, sizeof activity_, "EHT ramp %.1f kV", kvCur_);
      wait(ramp);
    } else {
      kvSettled_ = kvCur_;
      setBeam(BEAM_ON);
      activity_[0] = 0;
      seq_ = SQ_NONE;            // a filament difference is settled by reconcile (SQ_FIL)
    }
    break;

  case SQ_EHTOFF:
    if (step_ == 0) {
      cmdB(0);
      cmdO(base | oE | oF);
      wait(si(EHT_OFF_DELAY_MS)); step_ = 1;
    } else {
      cmdO(base | oF);
      setBeam(BEAM_EHT_OFF);
      seq_ = SQ_NONE;
    }
    break;

  case SQ_OFF:
    switch (step_) {
    case 0:
      setBeam(BEAM_STOPPING);
      snprintf(activity_, sizeof activity_, "Beam off");
      cmdB(0);
      // Detectors off first, keeping only the EHT / filament bits that are already on.
      if (wordSent_ >= 0 && (wordSent_ & oE)) { cmdO(base | (wordSent_ & (oE | oF))); wait(si(EHT_OFF_DELAY_MS)); }
      step_ = 1; break;
    case 1:
      if (wordSent_ >= 0 && !(wordSent_ & oF)) {      // filament never switched on
        cmdO(base); filCur_ = 0; step_ = 3; break;
      }
      cmdO(base | oF);
      if (filCur_ > si(EHT_FIL_DOWN_START)) cmdF(si(EHT_FIL_DOWN_START));
      wait(ramp); step_ = 2; break;
    case 2:
      if (filCur_ > si(EHT_FIL_OFF_MA)) {
        cmdF(max(filCur_ - (int)si(EHT_FIL_DOWN_STEP), (int)si(EHT_FIL_OFF_MA)));
        snprintf(activity_, sizeof activity_, "Filament %.2f A", filCur_ / 1000.0f);
        wait(ramp); break;
      }
      cmdO(base);
      filCur_ = 0;
      step_ = 3; break;
    case 3:
      shutdownAllOff_ = true;
      markFilOff();
      setBeam(BEAM_OFF);
      activity_[0] = 0;
      seq_ = SQ_NONE;
      logf(LV_INFO, "eht", "beam off, filament cooling %d s", (int)si(EHT_FIL_COOL_S));
      break;
    }
    break;

  case SQ_KV:
    if (fabsf(kvCur_ - kvT) > 0.001f) {
      cmdE(nextKvStep(kvCur_, kvT));
      snprintf(activity_, sizeof activity_, "EHT %.1f kV", kvCur_);
      wait(ramp);
    } else { kvSettled_ = kvCur_; activity_[0] = 0; seq_ = SQ_NONE; }
    break;

  case SQ_FIL: {
    int d = filT - filCur_, st = si(EHT_FIL_SLOW_STEP);
    if (d == 0) { activity_[0] = 0; seq_ = SQ_NONE; break; }
    cmdF(filCur_ + (d > st ? st : (d < -st ? -st : d)));
    wait(ramp);
    break;
  }
  default: seq_ = SQ_NONE;
  }
}

// Bring the set in line with the wanted state when no sequence is running:
// re-sends after a restore, follows setpoint changes, scintillator on/off.
void Eht::reconcile() {
  if (seq_ != SQ_NONE || !startupDone_ || !link.online || link.queued() > 4) return;
  if (inhibited() && beam_ == BEAM_OFF && !needRestore_) {
    int w = shutdownAllOff_ ? si(EHT_O_BASE) : idleWord();
    if (w != wordSent_) cmdO(w);
    return;
  }
  if (needRestore_ && !inhibited()) {
    needRestore_ = false;
    shutdownAllOff_ = false;
    wordSent_ = emisSent_ = collSent_ = typeSent_ = anodeSent_ = -1;
    pmSent_[0] = pmSent_[1] = pmSent_[2] = -1;
  }
  int w;
  switch (beam_) {
    case BEAM_ON:      w = idleWord() | si(EHT_O_EHT) | si(EHT_O_FIL); break;
    case BEAM_EHT_OFF: w = si(EHT_O_BASE) | si(EHT_O_FIL); break;
    default:           w = shutdownAllOff_ ? si(EHT_O_BASE) : idleWord(); break;
  }
  if (w != wordSent_) cmdO(w);
  char b[8];
  if (typeSent_ != si(EHT_FILTYPE)) { typeSent_ = si(EHT_FILTYPE); snprintf(b, sizeof b, ".T%X", typeSent_); cmd(b); }
  if (anodeSent_ != si(EHT_ANODE)) { anodeSent_ = si(EHT_ANODE); snprintf(b, sizeof b, ".A%X", anodeSent_); cmd(b); }
  int wantB = beam_ == BEAM_ON ? clamp12(lroundf(sf(OP_EMIS_UA) * 10)) : 0;
  if (wantB != emisSent_) cmdB(wantB / 10.0f);
  if (collSent_ != clamp12(2048 + lroundf(sf(OP_COLL_V) * 5))) cmdC(sf(OP_COLL_V));
  for (int ch = 1; ch <= 3; ch++) {
    int v = clamp12(si((SettingId)(OP_PM1 + ch - 1)));
    if (pmSent_[ch - 1] != v) cmdPM(ch, v);
  }
  if (beam_ == BEAM_ON) {
    if (fabsf(kvCur_ - sf(OP_KV)) > 0.001f) startSeq(SQ_KV);
    else if (filCur_ != si(OP_FIL_MA)) startSeq(SQ_FIL);
  } else if (beam_ == BEAM_EHT_OFF && filCur_ != si(OP_FIL_MA)) {
    startSeq(SQ_FIL);
  } else if (beam_ == BEAM_OFF) {
    kvSettled_ = sf(OP_KV);
  }
}

void Eht::service() {
  link.service();
  uint32_t now = millis();
  if (!startupDone_ && seq_ == SQ_NONE && (int32_t)(now - startupRetryMs_) >= 0) startSeq(SQ_STARTUP);
  runSeq();
  reconcile();
  if (startupDone_ && !link.inflight() && link.queued() == 0 &&
      now - lastPollMs_ >= (uint32_t)(sf(EHT_POLL_S) * 1000)) {
    lastPollMs_ = now;
    cmd("?S", T_STATUS);
  }
}
