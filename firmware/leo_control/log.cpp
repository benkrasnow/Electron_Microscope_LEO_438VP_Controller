#include "log.h"
#include <stdarg.h>


static LogEntry ring[LOG_DEPTH];
static int head = 0, count = 0;
static uint32_t seq = 0;

void logf(LogLevel lvl, const char* src, const char* fmt, ...) {
  LogEntry& e = ring[head];
  e.ms = millis();
  e.rtc = rtc_get();
  e.lvl = lvl;
  strlcpy(e.src, src, sizeof e.src);
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(e.msg, sizeof e.msg, fmt, ap);
  va_end(ap);
  head = (head + 1) % LOG_DEPTH;
  if (count < LOG_DEPTH) count++;
  seq++;
  usbLogHook(e);
}

int logCount() { return count; }
uint32_t logSeq() { return seq; }

const LogEntry* logGet(int age) {
  if (age < 0 || age >= count) return nullptr;
  return &ring[(head - 1 - age + LOG_DEPTH) % LOG_DEPTH];
}

const char* logLevelName(LogLevel l) {
  switch (l) {
    case LV_DEBUG: return "debug";
    case LV_INFO:  return "info";
    case LV_WARN:  return "warn";
    default:       return "fault";
  }
}
