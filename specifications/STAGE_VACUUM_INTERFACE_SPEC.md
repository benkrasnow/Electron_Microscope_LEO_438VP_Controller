# LEO 438VP Stage / Vacuum Controller: Serial Interface Specification

| | |
|---|---|
| Subsystem | Combined stage and vacuum communications CPU ("STGVAC"): 5-axis motorised stage, high-vacuum pumping, venting, vacuum interlocks |
| Host in the original system | ISA image-processor board, TMS34020 GSP, 16550 UART B at GSP address 0x60380000 (modules `g600.440` vacuum, `g500.rlm` stage) |
| Revision | 1.0, 2026-11-12 |
| Basis | Live captures of the original system (`capture_tools/captures/`), plus disassembly of the GSP modules |

Confidence markers used below: **[C]** confirmed by capture, **[F]** taken from the original firmware or software but not seen on the wire, **[I]** inferred and needing verification.

---

## 1. Overview

The stage/vacuum controller is a slave. The host sends one ASCII command and waits for one ASCII reply before sending the next. The controller never transmits unsolicited data, apart from a power-up artefact (§2.4). Instead it flags pending events in the status code of every reply, and the host then fetches the detail.

The controller does all the real-time work itself:
- pump-down and vent sequencing (rotary, turbo, valves);
- Penning gauge reading;
- the hardware vacuum-interlock relays that inhibit the EHT supply, PM and scintillator;
- stage motor control, homing, limit switches;
- the joystick.

The host only:
- configures the controller at start-up;
- requests pump/vent;
- polls status;
- commands absolute stage moves.

On the 438VP the vacuum system is a two-stage rotary pump plus a turbomolecular pump. There is no ion pump. The VP option adds a separate VP controller (see `VP_CONTROLLER_INTERFACE_SPEC.md`) that handles the chamber-isolation and gas valves; this controller is unaware of VP mode.

## 2. Physical and link layer

| Parameter | Value |
|---|---|
| Medium | Fiber-optic link from the image-processor board (transceiver type to be confirmed on the hardware) **[C]** |
| Electrical level at the transceiver | TTL UART, idle high (normal polarity) **[C]** |
| Format | 9600 baud, 8 data bits, no parity, 1 stop bit (8N1) **[C]** |
| Flow control | None **[C]** |
| Character set | 7-bit ASCII |
| Command terminator | CR LF (`0x0D 0x0A`) **[C]** |
| Reply terminator | CR LF **[C]** |
| Separator | single space between fields |
| Numbers | decimal in commands and stage replies; two-digit uppercase hex in status codes and register replies |

### 2.1 Transaction timing **[C]**

| Item | Measured | Recommended for a new host |
|---|---|---|
| Reply latency (end of command → first reply byte) | min 4.6 ms, median 51 ms, 95th percentile 262 ms, max 610 ms | Reply timeout ≥ 1.0 s |
| Mid-reply pause | the controller can pause ~60 ms inside one reply line | Frame on CR LF, not on inter-character gaps |
| Minimum host gap between commands | ≥ 30 ms seen | Wait for the reply, then ≥ 10 ms |
| Commands outstanding | 1 | Never pipeline |

### 2.2 Polling cadence used by the original host **[C]**

| Condition | `.VT` (vacuum) | `.SD` (stage) |
|---|---|---|
| Idle | every ~1.2 s | every ~1.2 s |
| Any stage axis moving | every ~1.2 s | every ~150 ms |
| A reply returned `=20` | `.VS` sent within 50 ms | |
| A reply returned `=40` | | `.SP` sent within ~50 ms, repeated 3–4×/s while the condition persists |

Only `.VT` and `.SD` repeat during idle; there is no other periodic housekeeping.

### 2.3 Error handling
There is no checksum. A new host should:
- treat a missing reply (no CR LF within 1 s) as a comms fault;
- retry once, then flag the link as failed;
- resume normal polling when replies return. After a controller power cycle the stage reports all axes uninitialised (`U`), which must be detected and handled (§6.5).

### 2.4 Power-down / power-up artefacts
When the host board powers down, a single `0xFF` byte appears on its transmit line. A host should ignore any received bytes that are not part of a `=...CR LF` line. **[C]**

## 3. Message format

**Command:** `.<G><C>[ <arg1> <arg2> …]<CR><LF>`
- `<G>` is the group letter: `V` vacuum, `S` stage, `T` thresholds, `C` configuration, `Q` 4Q-BSD/SCM.
- `<C>` is the command letter.

**Reply:** `=<SS>[ <field> …]<CR><LF>`, where `<SS>` is the two-hex-digit status code.

### 3.1 Reply status code `<SS>`

| Code | Meaning | Host action | |
|---|---|---|---|
| `00` | OK, nothing pending | none | **[C]** |
| `20` | OK, **vacuum event pending** (state change, inhibit change, error) | send `.VS` and process it | **[C]** |
| `40` | OK, **stage event pending** (limit switch, homing event, touch) | send `.SP` and process it | **[C]** |
| other | not seen; assume error | log, retry once | **[I]** |

The status code is reported on the reply to *any* command, not only polls. The command itself was still accepted when `=20` or `=40` is returned (for example `.CF N` → `=20`).

---

## 4. Vacuum commands

### 4.1 `.VT`: vacuum status poll **[C]**

```
.VT
=00 NCP 0 N N N <state> <gauge> N N
```

| Field | Meaning |
|---|---|
| `NCP 0 N N N` | Constant on this system. Probably column-pumping / airlock / option flags (`NCP` = no column pumping) **[I]** |
| `<state>` | Vacuum state machine (table below) |
| `<gauge>` | Penning gauge raw value (decimal). 0 when the gauge is off |
| `N N` | Constant on this system **[I]** |

Vacuum states:

| State | Meaning | Gauge field |
|---|---|---|
| `NSP` | Not pumped: at air / vented | stale or ~372 |
| `WTUS` | Waiting for turbo speed (pump-down started) | 0 |
| `WP` | Waiting for Penning gauge to strike | 0 |
| `SP` | System pumped, Penning reading, not yet ready | live reading |
| `SPVR` | System pumped, **vacuum ready**: EHT and detectors may be enabled | live reading |
| `SPE` | System pumped, **Penning gauge error** | garbage (e.g. 879384) |
| `WVT` | Waiting for vent (vent in progress) | last reading |

Pressure conversion for the Penning gauge (confirmed against eight operator readings to within 0.7 %) **[C]**:

```
P_Torr = 1 / (60 × raw^0.9)        (raw 0 is treated as 1)
raw    = (1 / (60 × P_Torr))^(1/0.9)
P_Pa   = P_Torr × 133.32
```

| raw | Torr | raw | Torr |
|---|---|---|---|
| 50 | 4.9e-4 | 302 | 9.8e-5 |
| 100 | 2.6e-4 | 663 | 4.8e-5 |
| 257 | 1.13e-4 | 1759 | 2.0e-5 |

A second conversion ("mode 1": constants 0.2666, 500, 1e-8, exponent 0.185) exists in the firmware for another gauge reading. It is not used on this system. **[F]**

### 4.2 `.VS`: vacuum event / fault detail **[C]**

```
.VS
=00 b0 b1 b2 b3 b4 b5 b6 b7          (8 hex bytes)
```

The host sends `.VS` whenever any reply carries `=20`, and once at start-up.

| Byte | Content | Values seen |
|---|---|---|
| b0 | **Interlock / inhibit bits** | `0F` vented or pumping, `07` after the first release, `00` ready |
| b1 | EDX errors | `02` at power-up until `.CF N` is sent, then `00` |
| b2 | System errors | `01` = Penning gauge failure |
| b3 | Gun errors | `00` |
| b4 | Column errors | `00` |
| b5 | WDX errors | `00` |
| b6 | Airlock errors | `00` |
| b7 | unused | `00` |

b0 inhibit bits. A set bit means the inhibit is **active**. Each bit corresponds to a hardware relay that the controller drives directly to the subsystem.

| Bit | Inhibit (name order from LEO-32 string table) | Released at | |
|---|---|---|---|
| 0 | EHT set (gun high voltage) | vacuum ready (`SPVR`, raw ≈ 302) | **[C]** timing, **[I]** name |
| 1 | Accelerating voltage | vacuum ready | **[C]** timing, **[I]** name |
| 2 | PM (photomultiplier) HV | vacuum ready | **[C]** timing, **[I]** name |
| 3 | Scintillator HV | raw 256–258 (≈1.14e-4 Torr), consistently in 4 pump-downs; this is the first audible relay click | **[C]** timing, **[I]** name |

The two audible clicks during pump-down are these relays releasing: bit 3 first, then bits 0–2 at vacuum ready. The bit-3 level does not match any programmed threshold (§4.6), so it is fixed inside the controller. Note that the order of the bit names is an assumption: the EHT supply sees the vacuum inhibit (its status bit 0x10) clear at the same moment as bits 0–2 do.

### 4.3 `.VL`: pump or vent **[C]**

| Command | Action | Typical result |
|---|---|---|
| `.VL P` | Start pump-down | `NSP` → `WTUS` → `WP` → `SP` → `SPVR`. 2–26 min depending on chamber condition |
| `.VL V` | Vent | `SPVR` → `WVT` (all inhibits set, b0 = `0F`) → `NSP` after ~17–18 s |

Reply: `=00`.

### 4.4 Identification and diagnostics **[C]**

| Command | Reply | Meaning |
|---|---|---|
| `.VX 80` … `.VX 86` | `=00 56`, `=00 30`, … | Comms-CPU firmware string, one ASCII byte per register: `V01.01 ` |
| `.VV 80` … `.VV 86` | `=00 56` … | Vacuum-CPU firmware string: `V02.00 ` |
| `.VV 66` | `=00 FD` | Vacuum board check (`_check_vac_board`) |
| `.VX 61` | `=00 C8` | SCM calibration register read |
| `.VW 61 <hh>` | `=00` | SCM calibration register write (start-up writes `CC` then `C8`) |
| `.VY` | `=00 OK OK` | Comms PSU check |

`.VX` / `.VV` read a register, and `.VW` / `.VU` write one. Register 65 is the touch-alarm-off control. **[F]**

### 4.5 Configuration commands (sent once at start-up) **[C]**

Each takes `Y` (fitted) or `N` (not fitted). Values shown are for this system.

| Command | Feature | This system |
|---|---|---|
| `.CA N` | Airlock | not fitted |
| `.CB N` | Viewing window | not fitted |
| `.CD N` | Tilt-0 | off |
| `.CE N` | Column pumping | not fitted |
| `.CF N` | EDX | not fitted (clears b1 = 02) |
| `.CG N` | WDX | not fitted |
| `.VP C` | Column isolation valve state | `C` (closed / not used) **[I]** |
| `.QA n N` (n = 1–4) | 4Q-BSD quadrant n enable | off |
| `.QC H` | 4Q-BSD gain | high |

Seen only in the firmware **[F]**: `.VO` (isolation valve), `.VB` (column pumping), `.VI` (WDX gate valve), `.QB` / `.QD` / `.QE` (BSD visibility, SCM range, take SCM reading). These options are not fitted here.

### 4.6 Threshold commands (sent once at start-up) **[C]**

All values are Penning raw counts (§4.1). Two-value forms give the release level and a second level that is probably the re-inhibit (hysteresis) level.

| Command | Purpose (firmware name) | Value | Pressure |
|---|---|---|---|
| `.TA 302` | Scintillator threshold | 302 | 9.8e-5 Torr |
| `.TB 302 50` | Accelerating-voltage threshold | 302 / 50 | 9.8e-5 / 4.9e-4 Torr |
| `.TC 302` | PM threshold | 302 | 9.8e-5 Torr |
| `.TD 8210 50` | "Ion pump" threshold (no ion pump fitted; default value) | 8210 / 50 | 5.0e-6 / 4.9e-4 Torr |
| `.TE 302 50` | Filament threshold | 302 / 50 | 9.8e-5 / 4.9e-4 Torr |
| `.TH 50` | EDX threshold | 50 | |

Evidence for the hysteresis interpretation: after a VP return the gauge read 1.38e-4 Torr (raw ≈ 220, worse than 302) and the state stayed `SPVR`. **[C]**

---

## 5. Stage commands

### 5.1 Coordinate system **[C]**

All positions are **24-bit offset binary**: 8388608 (2^23) is the mechanical zero, and values are sent as unsigned decimal. Axis order is always **X Y Z T R**. All five axes are always sent.

| Axis | Counts per unit | Step (`.SV`/32) | UI zero (count) | Range |
|---|---|---|---|---|
| X | 8148.74 /mm | 122.69 nm | 7981171 | 0 – 100 mm |
| Y | 8148.74 /mm | 122.69 nm | 7879312 | 0 – 125 mm |
| Z | 64538.2 /mm | 15.47 nm | 7259189 | 0 – 35 mm |
| T (tilt) | 11264 /° | 88778 n° | 8388608 | −90° … +90° |
| R (rotation) | 8448 /° | 118371 n° | 8388608 | −380° … +720° |

Conversion: `count = zero + round(value × counts_per_unit)`. Check: X = 55 mm → 7981171 + 55 × 8148.74 = 8429352. All six go-to targets and every limit in the captures match to the count.

### 5.2 `.SD`: stage status poll **[C]**

```
.SD
=00 X <pos> <m> <i> Y <pos> <m> <i> Z <pos> <m> <i> T <pos> <m> <i> R <pos> <m> <i> 
```
(note the trailing space before CR LF)

| Field | Values |
|---|---|
| `<pos>` | current position in counts (decimal; may be 0 or negative before initialisation, e.g. `-635`) |
| `<m>` | `S` stopped, `M` moving |
| `<i>` | `U` uninitialised, `I` initialised |

Example: `=00 X 8388608 S I Y 8286749 S I Z 7758894 S I T 8478050 S I R 8560122 S I `

### 5.3 `.SP`: stage event detail **[C]**

```
.SP
=00 00 00 00 00 00 00          (6 hex bytes)
=40 00 00 00 02 00 00          Z on a limit switch
```

The bytes are probably [summary?] X Y Z T R **[I]**: byte 3 = Z, and bit 0x02 = limit switch. The reply keeps returning `=40` while the axis sits on the switch. Other axes still accept moves during that time.

### 5.4 Motion commands

| Command | Arguments | Action | |
|---|---|---|---|
| `.SF x y z t r` | absolute counts, all 5 axes | **Go to** position. Axes that should not move are sent at their current position | **[C]** |
| `.SK` | none | **Abort** all motion (operator STOP; also sent at host shutdown) | **[C]** |
| `.SE x y z t r` | 1 = home this axis, 0 = leave | **Initialise (home)** the flagged axes | **[C]** |
| `.SA x y z t r` | counts | **Set** the current position registers (used after homing) | **[C]** |
| `.SB x y z t r` | speed per axis (controller units) | Cruise speed. Default `1500 1500 3000 2000 3000`; changed before some moves and restored after | **[C]** |
| `.SC a b c` × 5 | three values per axis | Ramp rates. Default `100 200 30` for every axis | **[C]** |
| `.SH …` | | Move a short distance **[F]** (not used by LEO-32; delta moves use `.SF`) | |
| `.SI …` | | Move at speed **[F]** (not used; joystick is local) | |

All return `=00`. Completion is detected by polling `.SD` until every axis reports `S`.

### 5.5 Limits and configuration

| Command | Arguments | Meaning | |
|---|---|---|---|
| `.SO x y z t r` | counts | Hardware (stage) lower limits | **[C]** |
| `.SQ x y z t r` | counts | User **lower** limits | **[C]** |
| `.SJ x y z t r` | counts | User **upper** limits | **[C]** |
| `.SV x y z t r` | 1/32 nm (X Y Z), 1/32 n° (T R) | Step size per count: `3926 3926 495 2840910 3787880` | **[C]** |
| `.SL X 0 Y 1 Z 2 T 3 R 4` | | Axis-to-motor map | **[C]** |
| `.SS` | | Stage PSU check → `=00` | **[C]** |
| `.SY` | | Version → `=00 H 0001 F 0001 ` (hardware 1, firmware 1) | **[C]** |
| `.SN a r` | axis 0–4, register hex | Read axis register → `=00 hh` (regs 80–86 = firmware string, blank here) | **[C]** |
| `.SM a r v` | | Write axis register **[F]** | |
| `.SR` | | Disable touch alarm **[F]** (touch alarm exists: old logs show "Stage Touching") | |
| `.SW n` | integer nm | **Joystick pixel size**: specimen distance per displayed pixel, so the local joystick moves the image a constant number of screen pixels per second at any magnification. Sent as `.SW <ltoa(pixel_size / 1e-9)>` by `_write_joystick_pixelsize` when the value changes by more than 5 %. Pixel size comes from the EO module (`_update_stage_pixel_size`, g200.440) as 1.1458e-4 m (110 mm / 960 screen pixels) ÷ magnification **[I]** (e.g. ~1146 nm at 100×, ~11 nm at 10,000×). Not seen on the wire yet: confirm by logging the stage link while changing magnification | **[F]** |
| `.SZ` | | General stage command **[F]** | |

Limit values used by LEO-32 **[C]**:

| Axis | `.SQ` lower | `.SJ` upper (pumped) | `.SQ` / `.SJ` when vented |
|---|---|---|---|
| X | 7981171 | 8796045 | 8266377 / 8510839 (35–65 mm) |
| Y | 7879312 | 8897904 | 8164518 / 8408980 (35–65 mm) |
| Z | 7259189 | 9518027 | unchanged |
| T | 7374848 | 9402368 | unchanged |
| R | 5178369 | 14471166 | unchanged |

The host re-sends `.SQ` and `.SJ` after every change of vacuum state. When at air it restricts X and Y to 35–65 mm, presumably for door clearance.

---

## 6. Typical usage

### 6.1 Start-up configuration (host power-up) **[C]**

Send in this order and check each reply for `=00` (or `=20` / `=40`, then service the event):

| # | Command(s) | Purpose |
|---|---|---|
| 1 | `.VS` | Read initial inhibits (expect `0F 02 …`) |
| 2 | `.VX 80`…`86`, `.VV 80`…`86` | Firmware versions (`V01.01`, `V02.00`) |
| 3 | `.VV 66` | Vacuum board check |
| 4 | `.VX 61`, `.VW 61 CC`, `.VW 61 C8` | SCM calibration |
| 5 | `.VY` | PSU check |
| 6 | `.CF N`, `.SS`, `.VS` | EDX not fitted, stage PSU, re-read inhibits |
| 7 | `.CG N`, `.CA N`, `.CB N`, `.CE N`, `.VP C` | Remaining option configuration |
| 8 | `.TH 50`, `.QA 1 N` … `.QA 4 N` | EDX threshold, BSD quadrants off |
| 9 | `.TA 302`, `.TB 302 50`, `.TC 302`, `.TD 8210 50`, `.TE 302 50` | Interlock thresholds |
| 10 | `.SL X 0 Y 1 Z 2 T 3 R 4`, `.CD N`, `.SP` | Axis map, tilt-0 off, clear stage events |
| 11 | `.SC 100 200 30` (×5 axes in one line), `.SB 1500 1500 3000 2000 3000` | Ramp rates, speeds |
| 12 | `.SY`, `.SV 3926 3926 495 2840910 3787880`, `.SN a 80`–`86` | Version, step sizes, axis registers |
| 13 | `.QC H`, `.SJ …` | BSD gain, user upper limits |

Then start `.VT` / `.SD` polling. The stage remains uninitialised until §6.4 is run.

### 6.2 Pump-down **[C]**
1. Send `.VL P`. (If a VP controller is fitted, the host then sends it `TO 3`, see the VP spec.)
2. Poll `.VT`: `WTUS` → `WP` → `SP <gauge>` → `SPVR`.
3. Service `=20` events with `.VS`: b0 goes `0F` → `07` (raw ≈ 257) → `00` (ready).
4. On `SPVR`, re-send `.SQ` / `.SJ` with the full-range limits. The EHT supply's vacuum inhibit clears at the same time, and the beam may then be enabled.

### 6.3 Vent **[C]**
1. **Turn the beam off and ramp the filament to zero first** (see the EHT spec; a hot filament must not see a pressure change).
2. If the stage is initialised, drive Z to 0.5 mm: `.SF <x> <y> 7291458 <t> <r>`.
3. Send `.VL V`. The state goes `WVT` (b0 = `0F`) → `NSP` after ~17 s.
4. On `NSP`, send the at-air limits (X/Y 35–65 mm). If a VP controller is fitted, send it `TO 2`.

### 6.4 Stage initialise (home) **[C]**
1. `.SB 1500 1500 3000 2000 4000`, then `.SO <lower limits>`.
2. `.SE 0 0 1 0 0` (Z first, for safety). Poll `.SD` at 150 ms. Expect `=40` / `.SP` limit events during homing; wait until Z reports `S I`.
3. `.SE 0 0 0 1 0` (T), then `.SE 0 1 0 0 0` (Y), then `.SE 1 0 0 0 0` (X), waiting for each. R is never homed.
4. `.SA 7985269 7883410 7292522 8377344 8388608` (X 0.5, Y 0.5, Z 0.52 mm, T −1.0°, R 0°).
5. `.SQ …`, `.SJ …`, `.SB 1500 1500 2100 1300 4000`.
6. `.SF 8388608 8286749 7323727 8388608 8388608` (default position X 50, Y 50, Z 1 mm, T 0°, R 0°).

### 6.5 Move the stage **[C]**
- **Absolute go-to:** optionally `.SB` with the speeds for this move, then `.SF` with all five axes. Poll `.SD` every 150 ms until all axes show `S`, then restore `.SB`.
- **Relative move (Δ):** compute absolute counts and use `.SF`. The original host does not use `.SH`.
- **Stop:** `.SK`.
- **Joystick:** handled locally by the controller with no host command. Positions simply change in `.SD`.
- **Limit hit:** reply `=40`; `.SP` shows the axis byte with bit 0x02. Warn the operator and keep polling `.SP` until it clears. Moves away from the limit are still accepted.
- **Controller reset detection:** any axis reporting `U` after it had been `I` means the stage controller lost its position. Re-initialise before any move.

### 6.6 Host shutdown **[C]**
Send `.SK`. Nothing else is required; the controller keeps its vacuum state.

---

## 7. Interlocks and requirements for a replacement host

1. **Vacuum inhibits are hardware.** The controller drives relays to the EHT, PM and scintillator supplies. A replacement host must not try to bypass them, and should mirror b0 in its UI.
2. **Filament off before any pressure change** (vent, VP transition, return to HV): ramp the filament to zero and let it cool. A burst of air on a hot filament shortens its life.
3. **Z down before vent** when the stage is initialised (Z = 0.5 mm).
4. **Re-send user limits** on every vacuum-state change: full range when pumped, X/Y 35–65 mm at air.
5. **Service `=20` and `=40` promptly.** They are the only way the controller reports events.
6. The VP controller must be told `TO 2` after a vent reaches `NSP`, and `TO 3` about 1.5 s after `.VL P` (see the VP spec).

## 8. Open items

- Exact b0 bit-to-subsystem names (§4.2), and what triggers bit 3 at raw ≈ 257.
- Meaning of the constant `.VT` fields `NCP 0 N N N … N N`.
- `.SP` byte layout beyond "byte 3 = Z, bit 0x02 = limit"; touch-alarm reporting.
- Units of `.SB` / `.SC`.
- `.SW` (joystick pixel size): confirm format and scaling on the wire while changing magnification.
- `.VP C` meaning.
- Fiber transceiver part number and wavelength.

## 9. Source captures

`20261112_131633_stgvac_running_idle.log`, `…131836_stgvac_vent_pump.log`, `…132627_stgvac_pumpdown_to_ready.log`, `…140133_stage_init_goto.log`, `…140932_stgvac_cold_boot.log`, `…161149_vent_and_pump_4ch.log`, `…170333_stage_jog_step_limits.log`. Working notes: `capture_tools/STGVAC_PROTOCOL.md`.
