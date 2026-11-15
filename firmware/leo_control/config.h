// LEO 438VP control box firmware: board pins and build constants.
// Pin map follows hardware/leo_control_box (schematic rev 0.1).
#pragma once
#include <Arduino.h>

#define FW_NAME     "leo_control"
#define FW_VERSION  "0.1.0"
#define PROTO_VER   1

// Fiber UARTs (HFBR-1521Z TX through an NX3008 low-side switch: pin high = light on;
// HFBR-2521Z RX open collector: light on = pin LOW, so the receive side is normally inverted).
#define EHT_PORT    Serial1     // RX 0, TX 1
#define STG_PORT    Serial2     // RX 7, TX 8
#define VP_PORT     Serial3     // RX 15, TX 14

// EO board fibers
#define PIN_EO_F3   2           // register frames out (bit-banged, 3.6864 Mbit/s)
#define PIN_EO_F4   3           // read replies in
#define PIN_EO_F1   4           // frame gate out
#define PIN_EO_F2   5           // line gate out

// Isolated sync outputs to the OBI (ISO6720 side 1)
#define PIN_SYNC_LINE  6
#define PIN_SYNC_FRAME 9

// Display (FT813 EVE on SPI)
#define PIN_LCD_CS  10
#define PIN_LCD_PD  21
#define PIN_LCD_INT 22

// Front-panel buttons (active low) and status LED
#define PIN_BTN1    16
#define PIN_BTN2    17
#define PIN_BTN3    20
#define PIN_LED     23

// Qwiic I2C is on 18/19 (Wire); not used by this firmware yet.
