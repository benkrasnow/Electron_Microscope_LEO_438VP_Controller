# LEO 438VP Variable-Pressure (VP) Controller: Serial Interface Specification

| | |
|---|---|
| Subsystem | VP control board ("Orsay" / "Interface HP"): chamber isolation valve, VP rotary-pumping valve, proportional gas-admit valve, chamber Pirani gauge, chamber pressure regulation |
| Host in the original system | Win98 PC, COM2, program `hpapp.exe` ("hpapp32", 1998), settings in `C:\WINDOWS\LEO.INI` section `[HPAPP]` |
| Revision | 1.0, 2026-11-12 |
| Basis | Live captures of both directions on COM2, plus disassembly of `hpapp.exe` |

Confidence markers used below: **[C]** confirmed by capture, **[F]** taken from the original software but not seen on the wire, **[I]** inferred and needing verification.

---

## 1. Overview

The VP controller switches the chamber between two modes:
- **LP** ("low pressure"): normal high vacuum. The chamber is pumped by the turbo through the open chamber-isolation valve.
- **HP** ("high pressure"): VP mode, 1 to a few hundred Pa. The chamber is isolated from the turbo, which keeps pumping the gun and column. The chamber is pumped by the rotary through the VP valve, and gas is admitted through a proportional valve to regulate at a setpoint.

The controller runs its own state machine, valve sequencing, timeouts and pressure regulation. The host:
- configures timeouts and the target;
- requests state changes with `TO n`;
- polls status every 4 s.

It is a separate system from the stage/vacuum controller. That controller does the high-vacuum pumping and venting and owns the Penning gauge; it does not know about VP mode.

The SE / VPSE detector switchbox relays switch with the VP state. The relay drive is believed to come from this controller **[I]**.

## 2. Physical and link layer

| Parameter | Value |
|---|---|
| Interface | RS-232, PC COM2 (DB9, PC is DTE: pin 3 TXD, pin 2 RXD, pin 5 GND) **[C]** |
| Levels | standard RS-232 (idle = negative voltage) **[C]** |
| Format | 9600 baud, 8N1 (`COM2:9600,n,8,1`) **[C]** |
| Flow control | none observed; only TXD/RXD were used **[I]** |
| Command terminator | CR LF **[C]** |
| Reply | see §3: payload, then the prompt `HP>` + CR, then CR LF **[C]** |
| Character set | ASCII, decimal numbers, comma-separated fields |

### 2.1 Timing **[C]**

| Item | Measured / configured | Recommended for a new host |
|---|---|---|
| Reply latency (end of command → first byte) | 2–5 ms | Reply timeout 2000 ms (hpapp `Comms Timeout=2000`) |
| Prompt to trailing CR LF | ~19 ms | Frame on `HP>`, then discard the CR LF |
| Status poll (`GP`) interval | 4.014 s (`MonitorInterval=4`) | 2–4 s |
| Poll interval after comms loss | 20.1 s (hpapp behaviour) | keep 4 s |
| Comms watchdog in the controller | `ST 1,n` seconds (300 in INI, 360 on this machine) | **always poll faster than the watchdog**, see §6.6 |

### 2.2 Power-up output **[C]**
When the controller is powered on it sends `Interface HP OK` `HP>`, followed by `100` (probably firmware version 1.00). It may also emit a few garbage bytes while its UART settles. A host should discard everything before the first `HP>`.

## 3. Message format **[C]**

**Command:** `<CMD>[ <arg>[,<arg>…]]<CR><LF>`. The command is two uppercase letters; there is a space before the first argument and commas between arguments.

**Reply:**
- accepted, no data: `HP>` `<CR>` … `<CR><LF>`
- accepted with data (`GP`): `<data>HP>` `<CR>` … `<CR><LF>`
- **rejected:** `255` instead of the normal reply (seen for `TO 11` in an invalid state)

## 4. Command reference

### 4.1 `GP`: get status (poll) **[C]**

```
GP
1034,9,9,0,2,0HP>
```

| Field | Name | Meaning |
|---|---|---|
| 1 | gauge | Chamber Pirani gauge, raw ADC counts (§5.1) |
| 2 | state | Current state number (§4.2) |
| 3 | requested | Target state the controller is working towards. Equals field 2 when settled |
| 4 | V8 | Chamber isolation valve: 0 closed, 1 closing, 2 open, 3 opening |
| 5 | V14 | VP (rotary pumping) valve: 0 closed, 2 open |
| 6 | error | Error code, 0 = none (no other value seen) |

Typical values: at air `~2015,2,2,2,0,0`; high vacuum `~399,3,3,2,0,0`; VP at 20 Pa `~1030,9,9,0,2,0`.

### 4.2 `TO n`: go to state **[C]**

| n | State | Who enters it | Meaning |
|---|---|---|---|
| 0 | POWER_UP | controller (power-on, watchdog, `RE 1`) | Safe state: V8 open, V14 closed |
| 1 | AT_AIR_HP | host | At air, VP mode selected |
| 2 | AT_AIR_LP | host | At air, normal mode. Send after a vent completes |
| 3 | PUMPING_LP | host | **Normal high-vacuum operation**. Send after `.VL P`, and to leave GUN_ENABLE_OK |
| 4 | GUN_ENABLE_OK | controller | Return from VP complete; the gun may be enabled |
| 5 | READY_TO_PUMP | host **[F]** | HP-mode pumping (not used in LP operation) |
| 6 | READY_TO_VENT | host **[F]** | HP-mode venting |
| 7 | WAIT_ABOVE_MCP | host | **Enter VP**: close V8, admit gas until gauge > MC up threshold |
| 8 | GOING_TO_HP | controller | Regulating towards the `HP` setpoint, not yet in band |
| 9 | AT_HP | controller | **In VP, regulated** within band of the setpoint |
| 10 | WAIT_LESS_MCP | host | **Leave VP**: pump the chamber on the rotary (V14) until gauge < MC down threshold |
| 11 | GUN_ENABLE_DELAY | controller | V14 closed, V8 opening, settling delay (~8 s) |

Valve-state names in the software are 12 Closed, 13 Closing, 14 Opened, 15 Opening and 16–19 Fault1–4. Error texts include CIV_Closing / CIV_Opening time_out, Rotary_Closing / Rotary_Opening time_out, MCP time_out, Target time_out, Com time_out, Reset, Reversing pending, Reversed_failed and Reversed_ok **[F]**. The numeric values these take in the error field have not been seen.

### 4.3 `HP a,b,c`: chamber pressure target **[C]**

`c` is the setpoint in controller units (§5.2). `a` and `b` move with the target; they are probably the lower and upper edges of the regulation band **[I]**. The command `HP 0,10000,c` (wide band) also works.

Values sent by LEO-32:

| Target | `HP a,b,c` | `MC up,down` |
|---|---|---|
| 10 Pa | `873,908,1165` (or `883,917,1175` stored) | `100,900` |
| 20 Pa | `1005,1040,1309` | `818,900` |
| 50 Pa | `1133,1164,1446` | `919,900` |
| 100 Pa | `1252,1287,1579` | `1016,900` |
| 200 Pa | `1391,1435,1738` | `1132,900` |
| 301 Pa | `1478,1527,1839` | `1202,900` |

May be sent at any time. Changing it while in VP sends the controller from 9 back to 8 until it is within band.

### 4.4 `MC up,down`: crossover thresholds **[C]**

Both values are in gauge counts (field 1 of `GP`):
- `up`: on the way into VP (state 7), the controller waits for gauge > `up` before moving to 8. LEO-32 sends `100` for targets ≤ 10 Pa, otherwise `0.8 × gauge_counts(target)`.
- `down`: on the way out (state 10), the controller waits for gauge < `down` before closing V14 and opening V8. LEO-32 always sends `900` (≈ 4.5 V ≈ 10 Pa).

### 4.5 `ST k,n`: timeouts **[C]**

| Command | Timeout | Default |
|---|---|---|
| `ST 1,n` | **Comms watchdog**, seconds without a command → falls back to POWER_UP | 300 (INI) / 360 seen |
| `ST 2,10` | MCP-up timeout (state 7), s | 10 |
| `ST 3,90` | MCP-down timeout (state 10), s | 90 |
| `ST 4,240` | Target timeout (state 8), s | 240 |
| `ST 5,5` | Gun-enable timeout, s | 5 |

### 4.6 `RE n`: reset

| Command | Action | |
|---|---|---|
| `RE 0` | Reset / clear errors. First command at host start-up; also used to abort ("reverse") a VP transition | **[C]** |
| `RE 1` | Reset the controller to POWER_UP. The host then waits up to 5 s for state 0 | **[F]** |

### 4.7 Other
`GM` is used by hpapp's reverse/abort routine (probably "get mode"). Its reply is not known **[F]**.

## 5. Encodings

### 5.1 Gauge counts → pressure **[C]**

```
V = counts × 0.005005 − 0.01706          (gauge output voltage, 2–10 V)
```

Then convert V → Pa with the Pirani calibration used by hpapp (interpolate):

| Pa | 0 | 1 | 10 | 20 | 50 | 100 | 1000 | 2240 |
|---|---|---|---|---|---|---|---|---|
| V | 2.000 | 2.99 | 4.49 | 5.104 | 5.737 | 6.345 | ≈8.84 | 9.40 |
| counts | 403 | 601 | 900 | 1023 | 1150 | 1271 | ≈1770 | 1882 |

At high vacuum the gauge reads ~399 (2.0 V), which displays as 0 Pa: this gauge only covers the VP range. At air it reads ~2015 (over range). Decoded values matched the operator display over 10–225 Pa.

### 5.2 Target pressure → `HP` setpoint **[C]**

```
V_target = Pirani(target Pa)                       (table above)
raw      = (V_target + 0.01706) / 0.005005
c        = raw × 1.094 + 190                        (gain/offset from LEO.INI)
if target > 250 Pa:  c = c × (1 + 0.015 × (target − 250) / 250)
```

Checks: 20 Pa → 1309, 50 Pa → 1447, 100 Pa → 1580, 200 Pa → 1738, 301 Pa → 1839.6 (all within one count of what was sent).

### 5.3 `MC up`
`up = 0.8 × raw(target)` (for example 20 Pa: 0.8 × 1023 = 818), or 100 for targets ≤ 10 Pa.

## 6. Typical usage

### 6.1 Host start-up handshake **[C]**

```
RE 0                    → HP>        (retry once if rejected)
GP                      → state must be 0 (POWER_UP); if not, RE 1 and wait ≤ 5 s for state 0
ST 1,360                → HP>
ST 2,10                 → HP>
ST 3,90                 → HP>
ST 4,240                → HP>
ST 5,5                  → HP>
GP
TO 2   (stage/vac reports NSP, at air)   or   TO 3 (pumped: SP / SPVR)
HP a,b,c                → stored target
MC up,900
```
Then poll `GP` every 4 s.

### 6.2 Normal vent and pump (LP mode) **[C]**

The VP controller plays no active part; it is only kept informed.
- **Vent:** the host sends `.VL V` to the stage/vacuum controller. When that reports `NSP` (~17 s), send `TO 2`.
- **Pump:** the host sends `.VL P` to the stage/vacuum controller, then `TO 3` ~1.5 s later. The chamber gauge falls from ~2018 to ~436 in ~75 s of rough pumping.

### 6.3 Enter VP **[C]**

Preconditions: state 3, stage/vacuum `SPVR`, **beam off and filament cooled** (see the EHT spec).

1. `MC <up>,900` and `HP a,b,c` for the target.
2. `TO 7`. The controller closes V8 (`…,7,1,0,0` closing → `…,8,0,0,0`), admits gas past `MC up`, then opens V14 and regulates.
3. Poll `GP` until state 9 (AT_HP). Typical time to 9 at 20 Pa is ~10 s. At 50–200 Pa it may stay in 8 for minutes while creeping towards the setpoint.
4. On the EHT link, turn the scintillator off (`.O` bit 0x0800, see the EHT spec). The SE/VPSE relays switch.
5. The beam may now be turned on.

Example (20 Pa):

| t | Command | `GP` reply |
|---|---|---|
| 0.0 s | `TO 7` | |
| 1.7 s | | `400,3,7,1,0,0` (V8 closing) |
| 5.7 s | | `1059,7,8,0,0,0` (above MCP) |
| 9.7 s | | `1055,9,9,0,2,0` **AT_HP** |

### 6.4 Change pressure while in VP **[C]**
Beam off and filament cooled. Send new `MC` and `HP`. The state goes 9 → 8 → 9. Lowering the target (for example 225 → 20 Pa) took ~40 s.

### 6.5 Return to high vacuum **[C]**

1. Beam off and filament cooled.
2. `TO 10`. The controller pumps through V14 until gauge < 900 (~20 s), closes V14, and opens V8 (`…,10,11,3,0,0`). It goes to 11 (GUN_ENABLE_DELAY, ~8 s), then **4 (GUN_ENABLE_OK)**, ~34 s after `TO 10`.
3. Send **`TO 3`** to return to normal PUMPING_LP. (`TO 11` is rejected with `255`; it is not needed.)
4. Restore the scintillator (`.O` bit 0x0800) on the EHT link once the stage/vacuum controller reports `SPVR`. The Penning reading briefly rises to ~1.4e-4 Torr when V8 opens but stays `SPVR`.

### 6.6 Comms loss and watchdog **[C]**
- If no command arrives for `ST 1` seconds, the controller goes to **POWER_UP (state 0)** with the valves in the HV-safe positions (V8 open, V14 closed). It reports error 0, not a fault.
- The original hpapp never re-initialises after a comms loss, so the system stays "Power Up" until hpapp is restarted or `TO 3` is sent by hand. This is the known cause of "VP stuck at Power Up".
- **A replacement host must** poll faster than the watchdog. If any `GP` returns state 0 unexpectedly, re-run the handshake (§6.1) and send `TO 3` (pumped) or `TO 2` (at air) according to the stage/vacuum state, then re-send `HP` / `MC`.
- Recovery observed: comms restored → first reply `395,0,0,2,0,0` → `TO 3` → `398,3,3,2,0,0`.

## 7. Interlocks and requirements for a replacement host

1. **Filament off and cooled before `TO 7`, any `HP` change in VP, and `TO 10`.** A pressure transient on a hot filament shortens its life.
2. **Scintillator HV off in VP.** The original EHT firmware forces `.O` bit 0x0800 off in VP mode. Without this the SE image shows no signal at VP pressures.
3. **Always set `HP` and `MC` before `TO 7`.** A `TO 7` run with no valid stored target admitted gas until the Penning side saw it (`NSP` within 4.7 s): effectively a vent.
4. Watch the stage/vacuum Penning state during VP. It should stay `SPVR`, since the turbo side is isolated. A drop to `NSP` means gas is reaching the column: abort with `TO 10` (or `RE 0`).
5. Keep the LP/HP states consistent with the stage/vacuum controller: `TO 2` at air, `TO 3` when pumped.

## 8. Open items

- Meaning of `HP a,b` (band edges?) and the formula LEO-32 uses for them.
- Numeric error codes in field 6, and the `GM` reply.
- Whether RTS/DTR are needed (only TXD/RXD were tapped).
- Where the SE/VPSE switchbox relay drive comes from (believed to be this board).
- Settling 12–16 % high at 50–200 Pa is regulation behaviour to be tuned later (the `HP` gain/offset).
- The full Pirani table: only the calibration points above are documented; the complete table can be extracted from `hpapp.exe`.

## 9. Source captures

`20261112_145539_vp_pumpdown_and_vp_mode.log`, `…153419_vp_manual_mc_hp_to7.log`, `…155926_vp_return_to_hv.log`, `…161149_vent_and_pump_4ch.log`, `…162701_vp_watchdog_unplug_hv.log`, `…164437_vp_target_sweep.log`. Working notes: `capture_tools/VP_PROTOCOL.md`.
