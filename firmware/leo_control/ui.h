// Touch display: status of every subsystem and the operator buttons
// (pump, vent, beam on, beam off, VP / HV, STOP). The box runs without a display.
#pragma once
#include <Arduino.h>

void uiBegin();
void uiService();
void uiApplySettings();      // backlight, after a settings change
void uiMessage(const char* msg, bool warn);   // short-lived message line
