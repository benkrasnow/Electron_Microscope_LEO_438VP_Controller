#include "link.h"

void Link::begin(HardwareSerialIMXRT* port, const char* name, Framing f, const char* term,
                 LinkReplyFn fn, void* ctx) {
  port_ = port; name_ = name; framing_ = f; term_ = term; fn_ = fn; ctx_ = ctx;
  port_->addMemoryForRead(rxMem_, sizeof rxMem_);
}

void Link::setInvert(bool txInv, bool rxInv) {
  uint16_t fmt = SERIAL_8N1;
  if (rxInv) fmt |= SERIAL_8N1_RXINV;
  if (txInv) fmt |= SERIAL_8N1_TXINV;
  port_->end();
  port_->begin(9600, fmt);
  rxn_ = 0;
  inReply_ = false;
}

bool Link::push(const char* cmd, uint8_t tag, bool front) {
  if (qn_ >= QLEN) return false;
  int slot;
  if (front) { qh_ = (qh_ - 1 + QLEN) % QLEN; slot = qh_; }
  else slot = (qh_ + qn_) % QLEN;
  strlcpy(q_[slot].text, cmd, sizeof q_[slot].text);
  q_[slot].tag = tag;
  qn_++;
  return true;
}

void Link::clearQueue() { qn_ = 0; }

void Link::sendNow() {
  port_->write(cur_.text);
  port_->write(term_);
  sentMs_ = millis();
  rxn_ = 0;
  inReply_ = false;
  if (trace) usbTraceHook(name_, '>', cur_.text);
}

void Link::finish(bool ok, const char* reply) {
  inflight_ = false;
  doneMs_ = millis();
  if (ok) {
    online = true; okCount++; consecFail = 0; lastOkMs = doneMs_;
  } else {
    failCount++; consecFail++; online = false;
  }
  if (fn_) fn_(ctx_, cur_.tag, ok, cur_.text, reply);
}

void Link::service() {
  // Receive and frame
  while (port_->available()) {
    int c = port_->read();
    if (c < 0) break;
    if (framing_ == FRAME_EQ) {
      if (!inReply_) {
        if (c != '=') continue;                  // power-up 0xFF, stray CR LF, noise
        inReply_ = true;
        rxn_ = 0;
      }
      if (c == '\n') {
        while (rxn_ && (rx_[rxn_ - 1] == '\r' || rx_[rxn_ - 1] == ' ')) rxn_--;
        rx_[rxn_] = 0;
        inReply_ = false;
        if (trace) usbTraceHook(name_, '<', rx_);
        if (inflight_) finish(true, rx_);
        else if (fn_) fn_(ctx_, TAG_UNSOLICITED, true, "", rx_);
        rxn_ = 0;
      } else if (rxn_ < (int)sizeof(rx_) - 1) {
        rx_[rxn_++] = (char)c;
      }
    } else {                                     // FRAME_VP
      if (c == '\r' || c == '\n') {
        // A CR/LF ends an unsolicited line (power-up banner); inside a reply it is ignored.
        if (inflight_ && rxn_ == 3 && memcmp(rx_, "255", 3) == 0) {   // refusal without a prompt
          rx_[3] = 0;
          if (trace) usbTraceHook(name_, '<', rx_);
          finish(true, rx_);
          rxn_ = 0;
        } else if (!inflight_ && rxn_) {
          rx_[rxn_] = 0;
          if (trace) usbTraceHook(name_, '<', rx_);
          if (fn_) fn_(ctx_, TAG_UNSOLICITED, true, "", rx_);
          rxn_ = 0;
        }
        continue;
      }
      if (c < 0x20 || c > 0x7E) continue;        // UART settling garbage
      if (rxn_ < (int)sizeof(rx_) - 1) rx_[rxn_++] = (char)c;
      if (rxn_ >= 3 && memcmp(rx_ + rxn_ - 3, "HP>", 3) == 0) {
        rx_[rxn_ - 3] = 0;
        if (trace) usbTraceHook(name_, '<', rx_);
        if (inflight_) finish(true, rx_);
        else if (fn_) fn_(ctx_, TAG_UNSOLICITED, true, "", rx_);
        rxn_ = 0;
      }
    }
  }

  uint32_t now = millis();
  if (inflight_) {
    if (now - sentMs_ >= timeoutMs_) {
      if (trace) usbTraceHook(name_, '!', "timeout");
      if (triesLeft_ > 0) { triesLeft_--; sendNow(); }
      else finish(false, "");
    }
    return;
  }
  if (qn_ > 0 && now - doneMs_ >= gapMs_) {
    cur_ = q_[qh_];
    qh_ = (qh_ + 1) % QLEN;
    qn_--;
    inflight_ = true;
    triesLeft_ = retries_;
    sendNow();
  }
}
