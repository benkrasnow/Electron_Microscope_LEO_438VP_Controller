// Event log: a small ring buffer shown on the display and streamed over USB.
#pragma once
#include <Arduino.h>

enum LogLevel : uint8_t { LV_DEBUG, LV_INFO, LV_WARN, LV_FAULT };

struct LogEntry {
  uint32_t ms;       // millis() when logged
  uint32_t rtc;      // RTC seconds (0 if the clock was never set)
  LogLevel lvl;
  char src[6];
  char msg[88];
};

#define LOG_DEPTH 32

void logf(LogLevel lvl, const char* src, const char* fmt, ...) __attribute__((format(printf, 3, 4)));
int  logCount();                         // entries currently held (<= LOG_DEPTH)
const LogEntry* logGet(int age);         // 0 = newest
uint32_t logSeq();                       // increments on every entry
const char* logLevelName(LogLevel l);

// Implemented by the USB module: forwards each new entry to the host.
void usbLogHook(const LogEntry& e);
