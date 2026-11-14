# LEO 438VP Control System: Summary Datasheet

*A readable overview of every control link and subsystem on the LEO 438VP SEM, written as the starting point for replacing the Win98 PC and its ISA image-processor (IP) board. Each section points to the detailed interface specification. Revision 1.0, 2026-11-13.*

---

## 1. System at a glance

```
                         ┌──────────────────────────────────────────────┐
                         │  Win98 PC  (LEO-32 UI, hpapp32 for VP)       │
                         │                                              │
                         │  ┌────────────────────────────────────────┐  │
                         │  │ ISA image-processor (IP) board         │  │
                         │  │  TMS34020 GSP  ── UART A ──────────────┼──┼──fiber──► EHT / gun supply
                         │  │   (system control,  UART B ────────────┼──┼──fiber──► Stage / vacuum controller
                         │  │    display)                            │  │
                         │  │  ADSP-21xx DSP ── remote register bus ─┼──┼──4 fibers─► EO board (scan + lenses)
                         │  │  frame store, video ADC  ◄─────────────┼──┼──coax──── detector video (SE / VPSE)
                         │  └────────────────────────────────────────┘  │
                         │  COM2 (RS-232) ────────────────────────────────┼──────────► VP controller
                         └──────────────────────────────────────────────┘

 Hardware interlocks (not via the PC):
   Stage/vacuum controller relays ──► EHT inhibit, PM HV, scintillator HV
   VP state ──► SE / VPSE detector switchbox relays
```

| Subsystem | Link | Format | Role of the host | Detailed spec |
|---|---|---|---|---|
| Stage / vacuum (STGVAC) | fiber, UART B | 9600 8N1 ASCII, `.XX args` CR LF | configure, poll, request pump / vent, command stage moves | `STAGE_VACUUM_INTERFACE_SPEC.md` |
| EHT / gun supply (M08) | fiber, UART A | 9600 8N1 ASCII, `.X hex` CR | sequence and ramp everything; poll faults | `EHT_INTERFACE_SPEC.md` |
| VP controller | RS-232 COM2 | 9600 8N1 ASCII, `XX a,b` CR LF | request state changes, set target, poll; keep its watchdog fed | `VP_CONTROLLER_INTERFACE_SPEC.md` |
| EO board (scan + lenses) | 4 fibers | 3.6864 Mbit/s 32-bit register frames + 2 gate lines | compute and write every DAC; write Y every line | `SCAN_GENERATOR_INTERFACE_SPEC.md` |
| Detector video | analog coax | analog | digitise into the frame store; contrast = amplifier gain | (to be characterised) |

**Design principle shared by all subsystems:** every remote unit is a slave that holds its last setting. **All sequencing, ramps, calibration and safety ordering live in the host.** A replacement host must reproduce them.

---

## 2. Stage / vacuum controller

**What it is.** A separate CPU that owns the rotary + turbo pumping, the Penning gauge, the vent valve, the vacuum-interlock relays, and a 5-axis motorised stage with its own joystick.

**Logical architecture**

```
 host ── .VL P / .VL V ──► [vacuum state machine] ── valves, pumps
      ── .VT poll ◄────── state + Penning raw      ──► interlock relays (EHT, PM, scintillator)
      ── .SF / .SE / .SK ► [stage motion: 5 axes] ◄── joystick (local)
      ── .SD poll ◄────── positions, moving, homed
 replies carry an event flag: =20 vacuum event (.VS), =40 stage event (.SP)
```

| Item | Summary |
|---|---|
| Link | Fiber, 9600 8N1, commands `.<group><cmd> args` CR LF, replies `=SS fields` CR LF, one command outstanding, reply ≤ 0.6 s |
| Vacuum states | `NSP` at air → `WTUS` turbo spin-up → `WP` → `SP` → **`SPVR` vacuum ready** (`WVT` venting, `SPE` gauge error) |
| Pressure | Penning raw → `P_Torr = 1 / (60 · raw^0.9)`; ready at raw ≈ 302 (9.8e-5 Torr) |
| Stage | 24-bit offset-binary counts per axis X Y Z T R (8148.74 /mm X, Y; 64538 /mm Z; 11264 /° T; 8448 /° R). Absolute go-to `.SF`, home `.SE`, stop `.SK` |
| Start-up | ~13 configuration groups (versions, options N, thresholds, axis map, speeds, limits), then poll `.VT` and `.SD` every ~1.2 s (150 ms while moving) |
| Host rules | filament off before vent; Z down before vent; re-send user limits on every vacuum change (X / Y 35–65 mm at air); service `=20` / `=40` promptly |

---

## 3. EHT / gun supply

**What it is.** The high-voltage set (unit `M08`): accelerating voltage 1–30 kV, tungsten filament, emission regulation, SE collector bias, PM high voltage, scintillator supply. It does **nothing on its own**: no ramps, no memory over its own reset.

**Logical architecture**

```
 host ── .O supply word ──► on/off: EHT 0x0100, filament 0x0200, scintillator 0x0800, detector bits
      ── .E kV, .F filament, .B emission, .C collector, .1-.3 PM HV ──► setpoint DACs
      ── ?S every 4.5 s ◄── status: OK 0x40, vacuum inhibit 0x10, reset 0x08, blown 0x04, trip 0x02
 hardware vacuum-inhibit line from the stage/vacuum controller overrides everything
```

| Item | Summary |
|---|---|
| Link | Fiber, 9600 8N1, `.L hex` / `?L` CR, replies `=RR[data]` CR LF in ~1 ms |
| Encodings | `.E` = kV × 100 − 2 · `.F` = mA − 16 · `.B` = µA × 10 · `.C` = 2048 + 5 × V · `.1` = PM HV (brightness) |
| Beam on (~15 s) | `.O0C07 .BFA0` → `.O0D07 .E008 .E<kV>` → `.O0F07` → filament ramp +147 mA / 0.466 s to 1.8 A, then +39 mA / 0.466 s to setpoint |
| kV above 20 kV | ramp 1 kV per 0.466 s |
| Shutdown (~9 s) | `.B000 .O0301 .O0201`, filament down −147 mA / 0.466 s, `.O0001` |
| Faults | anything other than 0x40 / 0x50: save settings, `.R`, beam stays off; re-send everything after any reset |
| Host rules | ramp filament and kV; **filament off and cooled before any pressure change**; scintillator (0x0800) off in VP and while vacuum-inhibited |

**Detector controls.** Brightness = PM high voltage (`.1`). Contrast = video amplifier gain on the IP board. Neither touches the EO board.

---

## 4. Variable-pressure (VP) controller

**What it is.** A separate board that isolates the chamber from the turbo and regulates chamber gas pressure (1 to a few hundred Pa) with its own state machine, valve sequencing and Pirani gauge. It has a **comms watchdog**: silence for `ST 1` seconds drops it to its safe POWER_UP state.

**Logical architecture**

```
 host ── TO n (go to state) ──► [VP state machine] ── V8 chamber isolation, V14 VP rotary valve, gas valve
      ── HP a,b,c / MC up,down ► setpoint / crossover thresholds
      ── GP poll every 4 s ◄── gauge, state, target, V8, V14, error
 VP state ──► SE / VPSE switchbox relays (believed driven from here)
```

| Item | Summary |
|---|---|
| Link | RS-232 COM2, 9600 8N1, `XX a,b` CR LF, reply `[data]HP>` CR … CR LF, 2–5 ms |
| Key states | 2 at air (LP) · 3 pumped high vacuum · **7 enter VP** → 8 regulating → **9 at pressure** · **10 leave VP** → 11 → 4 gun enable OK → host sends 3 · 0 power-up / watchdog |
| Pressure | gauge counts → V = counts × 0.005005 − 0.017 → Pirani table (403 = 0 Pa, 900 = 10 Pa, 1271 = 100 Pa) |
| Host rules | keep polling faster than the watchdog and re-handshake on an unexpected state 0; `TO 2` at air, `TO 3` after pump; set `HP` and `MC` before `TO 7`; **filament off and cooled before `TO 7`, `HP` changes in VP and `TO 10`**; scintillator off in VP |

---

## 5. Electron-optics (EO) board: scan generator and lenses

**What it is.** The board "CONDENSED EO CONTROL" in the column electronics. It generates the X / Y scan and drives the scan coils, the condenser and objective lenses and the stigmators. It contains five identical register-mapped ASICs (chips 0–4), six 16-bit DACs (AD7846), twenty 12-bit DACs (5 × AD664), eight 8-bit DACs (2 × DAC8408), range relays and lens current drivers. The host computes every value; the board only converts and ramps.

**Logical architecture**

```
                        F3: 32-bit register writes (3.6864 Mbit/s)        F4: read replies
 host ──────────────────────────────┬──────────────────────────────────────────────▲
                                    ▼                                              │
  chip 2  X ramp generator ── slope DAC ── X ramp ──┐                              │
          (r0A divider, points, start)              ├─[select: internal / EXT SCAN IN ±10 V]
  chip 3  Y position DAC (host writes every line) ──┘        │
                                                      ┌──────▼───────────────────────────┐
                                                      │ 4 multiplying coil-weight DACs   │
                                                      │ X→A X→B Y→A Y→B  (mag, rotation, │──► range relays ──► scan coils A, B
                                                      │ tilt, kV, per-range calibration) │
                                                      └──────────────────────────────────┘
  chip 2 / 3  shift + centring DACs ──────────────────────────────────────────────────────► added to coil drive
  chip 0  condenser DAC0-3 (two coarse/fine pairs) ──► lens drivers ──► C1, C2 (condensers)
  chip 1  objective DAC0/1 (+ wobble ramp generator) ──► lens driver ──► C3 (objective)
  chip 0  stigmator X / Y (DAC6 / DAC7) ──────────────────────────────────► Stig (octupole)
  chip 1  DAC4-7 (8-bit) ──► gun alignment (not used: manual on this microscope)
  chip 4  mode latch (slow scan / spot)
 F1, F2: frame and line gates from the host (acquisition timing)
```

| Item | Summary |
|---|---|
| Link | F3 register frames: NRZ, idle high, MSB first, `0 R n[12] value[16] 11`; chip = n >> 5, reg = n & 31; ~23 µs apart in bursts. F4: start bit + 16-bit reply. F1 frame gate, F2 line gate (550 µs per line) |
| Scan | X ramp in hardware; **host writes Y once per line**. Speed n: chip 2 r0A = 2^n − 1, line = (r0A + 1) × 87.9 µs (speed 5 = 2.81 ms). Speeds 10–15 step X point by point. 1024 points × 768 lines in the old system (the EO registers allow more) |
| Magnification | four coil weights (16-bit, 32768 = 0) + 5 ranges, each ~8× apart; weight × magnification is constant within a range; most sensitive range with \|weight\| < 32767; park → range → wait 40 ms → weights |
| Rotation / tilt / shift / kV | rotation matrix on the weights (coils at ~45° to the image); tilt = Y × cos(tilt); shift through the same rotation; weights and objective × √(relativistic kV) |
| Lenses | condenser (chip 0 DAC0–3) from the Optibeam calculation (kV, probe current, aperture, WD, depth / resolution mode); objective fine = focus; dynamic focus = one objective write per line linear in Y; wobble = chip 1's own ramp generator |
| Modes | reduced area, line scan, spot, split scan, line averaging (chip 3 r0A = N − 1), external scan (select bit + neutral offsets), freeze (control levels) |
| Start-up | fixed 59-write reset burst, ramp set-up, speed 5, weights at zero until a magnification is chosen |

---

## 6. Cross-subsystem sequences

| Operation | Order |
|---|---|
| **Pump down** | STGVAC `.VL P` → VP `TO 3` (~1.5 s later) → wait for `SPVR` → re-send stage limits → EHT inhibit clears (`?S` = 0x48 → `.R` → restore settings) |
| **Beam on** | require `SPVR` and EHT status 0x40 → EHT beam-on sequence (§3) → EO: lenses and weights for the new kV |
| **Change kV** | EHT `.E` (ramped above 20 kV) → after it settles, EO: recompute condenser, objective (√kV), weights (√kV), range |
| **Vent** | beam off, **filament ramped to zero** → stage Z to 0.5 mm → STGVAC `.VL V` → at `NSP`: VP `TO 2`, at-air stage limits |
| **Enter VP** | beam off, filament cooled → VP `MC`, `HP`, `TO 7` → state 9 → EHT scintillator off (0x0800) → beam on |
| **Leave VP** | beam off, filament cooled → VP `TO 10` → state 4 → `TO 3` → scintillator back on |
| **Host start** | each link independently: STGVAC configuration, EHT reset / restore, VP handshake + watchdog polling, EO reset burst |

---

## 7. What a replacement IP board / host must provide

| Function | Requirement |
|---|---|
| Two fiber UARTs | 9600 8N1 to the EHT set and the stage / vacuum controller (TTL idle high at the transceivers) |
| One RS-232 port | VP controller (or a UART + level shifter) |
| EO fiber link | 3.6864 Mbit/s serial transmitter for F3 (14.7456 MHz / 4), receiver for F4, F1 / F2 gate outputs, deterministic per-line Y writes ~27 µs after each F2 edge (a microcontroller timer / DMA or an FPGA) |
| Video acquisition | analog video input from the detector coax with programmable gain (contrast) and offset, digitised in sync with the X ramp (pixel clock derived from the line timing); frame store / streaming to the PC |
| Optics model | coil-weight calculation (magnification, range table, rotation, tilt, shift, kV, WD lens rotation); lens calibration to replace Optibeam |
| Safety logic | filament-off before any pressure change; scintillator off in VP; kV and filament ramps; fault handling and re-send after resets; VP watchdog polling |

---

## 8. Confidence and open items

The detailed specs mark every statement **[C]** confirmed by capture, **[F]** from the original firmware / software, or **[I]** inferred.

Open items that affect a replacement:
- **Detector video:** signal level, bandwidth, impedance and the IP-side amplifier / ADC (not yet measured).
- **F1 / F2:** confirmed timing, inferred meaning (acquisition gates).
- **HRRU** (second target on the IP board's remote register bus) and any hardware knob panel: not yet investigated.
- Fiber transceiver part numbers and wavelengths; IP board connector pinouts.
- EO: C1 / C2 pair assignment, A / B coil pins, the external-scan path test, the meaning of a few constant registers.
- EHT: fault bits 0x04 / 0x02, PM HV scale. VP: `HP a,b` formula, error codes.

## 9. Document map

| File | Content |
|---|---|
| `specifications/STAGE_VACUUM_INTERFACE_SPEC.md` | stage / vacuum controller, full command set |
| `specifications/EHT_INTERFACE_SPEC.md` | EHT / gun supply, full command set and sequences |
| `specifications/VP_CONTROLLER_INTERFACE_SPEC.md` | VP controller, full command set and sequences |
| `specifications/SCAN_GENERATOR_INTERFACE_SPEC.md` | EO board, frame format, register map, every function |
| `capture_tools/REPLACEMENT_REQUIREMENTS.md` | safety rules for the new controller |
| `scope_tools/SCAN_FIBER_NOTES.md`, `capture_tools/*_PROTOCOL.md` | test logs behind the specs |
| `report/leo438vp_report.html` | static analysis of the original software |
