// One command/reply serial link to a slave unit (EHT, stage/vacuum, VP).
// Non-blocking: commands wait in a small queue, one is in flight at a time,
// replies are framed per link type, timeouts are retried, results go to a callback.
#pragma once
#include <Arduino.h>

enum Framing : uint8_t {
  FRAME_EQ,      // reply "=..." terminated by LF (EHT, stage/vacuum); junk before '=' ignored
  FRAME_VP       // reply "<payload>HP>" (then CR, CR LF which are skipped)
};

#define TAG_UNSOLICITED 0xFF

// tag: caller's id for the command; ok=false means no reply after all retries.
typedef void (*LinkReplyFn)(void* ctx, uint8_t tag, bool ok, const char* cmd, const char* reply);

class Link {
public:
  void begin(HardwareSerialIMXRT* port, const char* name, Framing f, const char* term,
             LinkReplyFn fn, void* ctx);
  void setInvert(bool txInv, bool rxInv);          // (re)starts the UART at 9600 8N1
  void setTiming(uint32_t timeoutMs, uint32_t gapMs, uint8_t retries) {
    timeoutMs_ = timeoutMs; gapMs_ = gapMs; retries_ = retries;
  }

  // Queue a command (without terminator). front=true jumps the queue.
  bool push(const char* cmd, uint8_t tag, bool front = false);
  void clearQueue();                               // drops queued commands, not the one in flight
  bool inflight() const { return inflight_; }
  bool idle() const { return !inflight_ && qn_ == 0; }
  int  queued() const { return qn_; }
  void service();                                  // call every loop

  const char* name() const { return name_; }
  bool online = false;          // last transaction got a reply
  uint32_t okCount = 0, failCount = 0, consecFail = 0;
  uint32_t lastOkMs = 0;
  bool trace = false;           // echo traffic to USB

private:
  struct Cmd { char text[80]; uint8_t tag; };
  enum { QLEN = 24 };
  void sendNow();
  void finish(bool ok, const char* reply);

  HardwareSerialIMXRT* port_ = nullptr;
  const char* name_ = "";
  Framing framing_ = FRAME_EQ;
  const char* term_ = "\r\n";
  LinkReplyFn fn_ = nullptr;
  void* ctx_ = nullptr;
  uint32_t timeoutMs_ = 500, gapMs_ = 10;
  uint8_t retries_ = 1;

  Cmd q_[QLEN];
  int qh_ = 0, qn_ = 0;
  Cmd cur_;
  bool inflight_ = false;
  uint8_t triesLeft_ = 0;
  uint32_t sentMs_ = 0, doneMs_ = 0;
  char rx_[96];
  uint8_t rxMem_[256];          // extra UART receive buffer (survives a slow loop pass)
  int rxn_ = 0;
  bool inReply_ = false;
};

// Implemented by the USB module: raw traffic echo when Link::trace is on.
void usbTraceHook(const char* link, char dir, const char* text);
