# Glasgow revC3 pin plan for full LEO 438VP control (OBI + all subsystem links)

Verified 2026-11-13 from source: Glasgow `software/glasgow/hardware/platform/rev_c.py` (GlasgowEmbedded/glasgow, main) and OBI `software/obi/applet/open_beam_interface/__init__.py` and `software/configs/*.toml` (nanographs/Open-Beam-Interface, main).

## What OBI uses

| OBI signal | iCE40 ball | Glasgow connector |
|---|---|---|
| power_good (in) | K1 | LVDS pin 3 |
| x_latch, y_latch, a_enable, a_latch, d_clock, a_clock | H3, H1, G3, H2, F3, G1 | LVDS |
| data[14] (bidirectional) | B2 C4 B1 C3 C2 C1 D3 D1 F4 G2 E3 F1 E2 F2 | LVDS |
| scan_enable / blank pins (runtime config, `[beam.*.pinout]`) | Port A or B, user choice | Zeiss example config: `scan_enable = "A0"` only |

- Glasgow LVDS connector (44 pins) = balls K1 J1 K2 H1 J2 H2 H3 G1 G3 G2 F3 F1 F4 F2 E3 E1 E2 D1 D2 C1 D3 C2 C3 B1 C4 B2, wired directly to the FPGA (bank 3, VIO_AUX 1.8-3.3 V, no level shifters).
- **Every OBI analog-board signal is on the LVDS connector.** Unused LVDS balls: J1, K2, J2, E1, D2 (3.3 V, unbuffered, routed to the OBI breakout).
- Port A balls: A1 A2 B3 A3 B6 A4 B7 A5 (OE C7 C8 D7 A7 B8 A8 B9 A9). Port B balls: B11 C11 D10 D11 E10 E11 F11 F10 (OE F9 G11 G10 H11 H10 J11 J10 K11). **No overlap with the LVDS balls.** Each port pin has an SN74LVC1T45 translator and 33 Ω; VIO per port 1.8 V-5 V; drive 24 mA at 3.3 V, 32 mA at 5 V.
- **Port B: completely free. Port A: free except the one scan-enable pin (A0 in the example config), which the user will not need.** (The EO board's internal/external select is also available as a register bit, chip 3 options bit 3, plus its EXT SCAN EN hardware input.)

## Signals needed, including the internal-scan backup

| Link | Out | In |
|---|---|---|
| EHT fiber | TX | RX |
| Stage / vacuum fiber | TX | RX |
| EO F3 register frames | TX | |
| EO F4 replies | | RX |
| EO F1 frame gate, F2 line gate (internal digital scan backup) | 2 TX | |
| VP RS-232 (via MAX3232) | TX | RX |
| **Total** | **7** | **4** |

## Proposed assignment

| Pin | Dir | Signal | Port VIO |
|---|---|---|---|
| B0 | out | EHT TX fiber driver | **Port B = 5 V** (HFBR-2521Z receivers are 5 V parts; driver inputs) |
| B1 | in | EHT RX fiber | |
| B2 | out | Stage/vacuum TX fiber driver | |
| B3 | in | Stage/vacuum RX fiber | |
| B4 | out | EO F3 (register frames, 3.6864 Mbit/s) | |
| B5 | in | EO F4 (read replies) | |
| B6 | out | EO F1 frame gate | |
| B7 | out | EO F2 line gate | |
| A0 | out | (existing OBI scan_enable; free if not used) | **Port A = 3.3 V** |
| A1 | out | VP TXD -> MAX3232 | |
| A2 | in | VP RXD <- MAX3232 | |
| A3 | open-drain | **I²C SCL** (knobs / levers / PMT gain DAC) | |
| A4 | open-drain | **I²C SDA** | |
| A5 | in | I²C interrupt (`INT`, active low, from the knob modules) | |
| A6-A7 | | spare: interlock inputs, status LEDs | |

Fiber transmitters (HFBR-1521Z) need an LED driver per channel (not a direct Glasgow pin); receivers (HFBR-2521Z) need 5 V supply and, if open-collector, pull-ups.

Notes: revD Glasgow (pre-launch) replaces the LVDS connector; stay on revC3 with the OBI. On revC, balls A6 / B5 are shared with Port A IO4 / IO6 and are tristated by the platform file (no action needed).

## I²C bus (Port A, 3.3 V)

- Open-drain emulation: the gateware drives the pin low by enabling the SN74LVC1T45 output with 0 and releases it by tristating (as Glasgow's own `i2c-initiator` applet does). External pull-ups to Port A VIO (2.2-4.7 kΩ); the on-board pull resistors are too weak for more than a short bus.
- 100 kHz is ample (knobs polled at 50-100 Hz plus occasional DAC writes); 400 kHz possible on a short bus.
- Use the INT line so the host only reads when a knob has moved.
- Candidate devices (all 3.3 V, address-selectable):
  - **Knobs (focus coarse / fine, stig X / Y, magnification, brightness / contrast):** I²C rotary-encoder modules with push button and interrupt output (e.g. DuPPa I2C Encoder V2.1, or an Adafruit seesaw encoder board); several on one bus.
  - **Levers / joystick-style analog controls:** ADS1115 (4-channel 16-bit ADC).
  - **PMT amplifier gain:** MCP4725 / DAC7571 (12-bit), or MCP4728 (4 channels: gain plus offset and spares), or an I²C digital potentiometer if the amplifier uses a resistor for gain.
- Gateware: an I²C initiator block on the control pipe as its own channel (transactions: write bytes / read n bytes / wait for INT). Knob handling (acceleration, mapping to focus steps scaled by magnification) lives in the host daemon.
