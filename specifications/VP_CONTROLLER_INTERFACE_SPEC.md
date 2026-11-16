# LEO 438VP Variable-Pressure (VP) Controller: Serial Interface Specification

| | |
|---|---|
| Subsystem | VP control board ("Orsay" / "Interface HP"): chamber isolation valve, VP rotary-pumping valve, proportional gas-admit valve, chamber Pirani gauge, chamber pressure regulation |
| Host in the original system | Win98 PC, COM2, program `hpapp.exe` ("hpapp32", 1998), settings in `C:\WINDOWS\LEO.INI` section `[HPAPP]` |
| Revision | 1.3, 2026-11-15: who starts hpapp32, the two hpapp links (§7.1); 1.2: why LEO-32's "Go To VP" button is disabled (§7.1); lens note in §7 (1.0 2026-11-12) |
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

- **Lenses in VP.** On this machine VP is switched from hpapp32 and LEO-32's own VP button is disabled, so LEO-32's column model never knew the chamber was in VP. Its VP lens routine (`_set_lenses_for_HPSEM` in `g200.440`) was never used, and the high-vacuum lens settings applied in VP too. The control box does the same (`ELECTRON_OPTICS_MODEL.md` §6.7).

### 7.1 How LEO-32 enables "Go To VP" **[F]**
From `leoserv.exe`, `m600.dll` (vacuum DLL) and `m007.dll`, static analysis only:
1. **Configuration.** `leoserv.exe` starts `\HPAPP.EXE` from the LEO-32 folder only if the machine type is 4 (LEO 435VP) or 10 (LEO 438); otherwise it never starts it. `m600.dll` connects to hpapp only if `DP_COLUMN_TYPE` (state 0x8c) = 3 (LEO 435VP/438VP). It finds hpapp32's window by the title "Untitled - hpapp32" (`FindWindow`) and registers `LEO_HPAPP_MESSAGE`. `Data.vac` has machine type 10 (MASTER byte, file offset 0x507) and column type 3 (EO byte, file offset 0x0ed) in the current file and in every copy and backup on the disk, so the configuration is correct.
2. **State machine.** `m600.dll` keeps its own VP state, A–Z, A1, A2 (A Initialise, B At Air LP … F Vac Ready LP, I–O HP states, X / Y LP error, Z HP error), driven by the messages from hpapp32. From that state it sets `DP_VP_OK` (state 0x141):
   - **1** ("Go To VP" allowed) in **B At Air LP**, **E Pumping LP** (unless `DP_VACSTATUS` is 4 or 5) and **F Vac Ready LP**;
   - **2** in the HP states I, K, M, N, O;
   - **0** otherwise, including **A Initialise** (nothing heard from hpapp) and the error states **X, Y, Z**.
3. **Errors.** If hpapp does not answer within `OrsayBoardTimeout` (LEO.INI `[HPAPP]`, clamped to 10–300 s; 300 here), `m600.dll` reports a timeout and sets `DP_HP_STATUS` (0x108) to 13. Other paths report "HPAPP start error. SEM set to LP mode only.", "HPAPP has closed …" and "HPAPP hung up …".
4. **Who starts hpapp32.** Only `leoserv.exe`. At start-up it reads the machine type through `Srv32.dll` (`SRV_Get_Machine_Type`) and, for 4 or 10, calls `CreateProcessA` on `<LEO-32 folder>\HPAPP.EXE` (code at 0x49fae8 → 0x530260). It doesn't wait for hpapp32 to come up (no `WaitForInputIdle`). On failure it posts "*** HPAPP failed to start". Windows doesn't start it: there are no Startup-folder, `Run=` / `Load=` or registry Run entries for it. `m600.dll` doesn't launch it either; it only checks `GetModuleHandle("HPAPP.EXE")` and reports "HPAPP start error. SEM set to LP mode only." if hpapp32 isn't loaded.
5. **Two separate links.**
   - *hpapp32 → LEO-32*: hpapp32 finds LEO-32's server window by `FindWindow("LEO SRV-32")` and polls the VP board on COM2. It reads LEO parameters (`AP_CHAMBER_PRESSURE`, `AP_SYSTEM_VAC`, `DP_VACSTATUS`, `DP_DETECTOR_TYPE`), writes `AP_HP_TARGET`, `AP_COLLECTOR_BIAS`, `AP_BRIGHTNESS`, `AP_CONTRAST`, and runs `CMD_GOTO_VP` / `CMD_GOTO_HV`. The chamber pressure reaches LEO-32's display through this path; `m600.dll` exports `HP_SET_CHAMBER_PRESSURE` and `HP_STATE_EVENT` for it.
   - *m600.dll → hpapp32*: `m600.dll` calls `FindWindow("Untitled - hpapp32")` **once**, at initialisation (its only `FindWindow` call), and stores the handle. Its send routine silently does nothing if the handle is 0.
   - A working pressure display therefore doesn't show that the m600 link is up. If hpapp32's window didn't exist yet, or had another title, when `m600.dll` initialised, LEO-32 never talks to hpapp32 for the rest of the session, and its VP state stays A, which disables "Go To VP". Since `leoserv.exe` doesn't wait after `CreateProcessA`, this is a start-up race. Inference from static analysis.
6. **History** (`LOG\*.leo`): VP errors from 2003 to 4 Jan 2025 (550 HPApp failed to start ×12, 552 closed unexpectedly ×8, 553 hung up ×6, 554 VP Control spurious reset ×45, 555 comms error ×11, 556 / 557 turbo isolation valve ×12, 570 unknown ×24). There are none after 4 Jan 2025.

So the button is grey whenever LEO-32's own VP state is not B / E / F. The most likely causes: LEO-32 never linked to hpapp32 (state A), because hpapp32's window wasn't up yet or didn't have the title "Untitled - hpapp32" when `m600.dll` looked for it (item 5); or it latched an error state (X / Y / Z). LEO-32's VP Control panel shows the state name under "Status"; that text identifies which. A fresh start, with LEO-32 launching hpapp32 itself and the chamber pumped (state F), should enable the button. Unconfirmed on the running system.

## 8. Open items

- Meaning of `HP a,b` (band edges?) and the formula LEO-32 uses for them.
- Numeric error codes in field 6, and the `GM` reply.
- Whether RTS/DTR are needed (only TXD/RXD were tapped).
- Where the SE/VPSE switchbox relay drive comes from (believed to be this board).
- Settling 12–16 % high at 50–200 Pa is regulation behaviour to be tuned later (the `HP` gain/offset).
- The full Pirani table: only the calibration points above are documented; the complete table can be extracted from `hpapp.exe`.

## 9. Source captures

`20261112_145539_vp_pumpdown_and_vp_mode.log`, `…153419_vp_manual_mc_hp_to7.log`, `…155926_vp_return_to_hv.log`, `…161149_vent_and_pump_4ch.log`, `…162701_vp_watchdog_unplug_hv.log`, `…164437_vp_target_sweep.log`. Working notes: `capture_tools/VP_PROTOCOL.md`.

## Fiber port on the VP control board (traced 2026-11-14 from photos)

The VP control board (PCB "98/46", S/N 98048, MC68HC705C8 firmware "875421 V01") has an unused Versatile Link fiber port next to its DE-9 (PL2): **TX1 = HFBR-1524**, **RX1 = HFBR-2524** (the 40 kBd, high-sensitivity grade). A 4-position DIP switch next to the 4 MHz oscillator chooses which port the processor's single SCI uses. Lever colours follow the resistor colour code:

| Switch | Lever | Connects |
|---|---|---|
| 1 | brown | SCI TX (pin 30, PD1/TDO) → ADM232 T1IN (pin 11) → PL2 |
| 2 | red | SCI TX → transistor LED driver (R19–R21) → TX1 |
| 3 | orange | ADM232 R1OUT (pin 12) → SCI RX (pin 29, PD0/RDI) |
| 4 | yellow | RX1 → SCI RX (trace on the top layer; inferred) |

- RS-232 (as installed): 1 and 3 ON. Fiber: 2 and 4 ON, 3 OFF (1 may stay ON). Never 3 and 4 together.
- Protocol is unchanged on the fiber (same SCI, 9600 8N1).
- Traced from the solder side: the switch pairs 1/2 and 3/4 are joined on the processor side; the ADM232 orientation is confirmed by its charge-pump capacitor and VCC connections. Not yet confirmed: the fiber idle polarity (check whether TX1 is lit at idle) and the RX1 trace.
