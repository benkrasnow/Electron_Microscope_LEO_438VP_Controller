// USB serial protocol to the PC (see firmware/PROTOCOL.md).
// Text command lines in, one JSON object per line out. Never blocks: output that does
// not fit the USB buffer is dropped (and counted), so a stalled or absent PC cannot stall control.
#pragma once
#include <Arduino.h>

void usbBegin();
void usbService();
bool usbConnected();
uint32_t usbLastCmdMs();
void jsonStatus(char* buf, size_t n);   // status object (also used by "status")
