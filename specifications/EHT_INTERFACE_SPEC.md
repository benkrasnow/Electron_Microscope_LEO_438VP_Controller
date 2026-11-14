# LEO 438VP EHT / Gun Supply ("EHT set"): Serial Interface Specification

| | |
|---|---|
| Subsystem | EHT set, unit ID `M08`: accelerating voltage, thermionic tungsten filament, emission-current regulation, SE collector bias, photomultiplier (PM) high voltage, detector/scintillator supplies |
| Host in the original system | ISA image-processor board, TMS34020 GSP, 16550 UART A at GSP address 0x60300000 (module `g100.440`) |
| Revision | 1.0, 2026-11-12 |
| Basis | Live captures (cold boot, pump-down, beam on/off, adjustments, EHT off, VP, kV sweep, comms loss), plus disassembly of `g100.440` and LEO-32 |

Confidence markers used below: **[C]** confirmed by capture, **[F]** taken from the original firmware or software but not seen on the wire, **[I]** inferred and needing verification.

---

## 1. Overview

The EHT set is a slave. The host sends one ASCII command and the set replies within a few milliseconds.

The set holds whatever was last commanded. It does **not** ramp anything by itself, and does not remember settings across its own power cycle. The host is responsible for:
- the ordering of supplies;
- the filament warm-up and cool-down ramps;
- the voltage ramp above 20 kV;
- re-sending all settings after a reset.

The set reports faults (vacuum inhibit, spurious reset, filament blown, trip) in a status byte that the host polls every 4.5 s.

The vacuum interlock is a **hardware** line from the stage/vacuum controller's relay. The set refuses to energise while it is active, regardless of what the host sends.

## 2. Physical and link layer

| Parameter | Value |
|---|---|
| Medium | Fiber-optic link from the image-processor board (transceiver type to be confirmed) **[C]** |
| Electrical level at the transceiver | TTL UART, idle high (normal polarity) **[C]** |
| Format | 9600 baud, 8N1 **[C]** (divisor 12 at 1.8432 MHz in the firmware **[F]**) |
| Flow control | none **[C]** |
| Command terminator | **CR only** (`0x0D`) **[C]** |
| Reply terminator | CR LF **[C]** |
| Character set | ASCII; numeric arguments are **fixed-width uppercase hex** with no separator |

### 2.1 Timing **[C]**

| Item | Measured | Recommended for a new host |
|---|---|---|
| Reply latency (end of command → first reply byte) | ~1 ms (whole reply within 3–7 ms of the command) | Reply timeout 100–500 ms |
| Host command spacing | 16.7 or 33 ms (one or two 60 Hz ticks of the original firmware) | ≥ 10 ms after the reply |
| Status poll (`?S`) | every 4.51 s | 1–4.5 s |
| Ramp step interval (filament, kV > 20 kV) | 0.466 s | keep (see §6) |
| No reply | the original host waited ~4.5 s, flagged comms fail, and kept polling (poll period became 9.0 s) | timeout, retry once, then fault |

## 3. Message format

**Command:** `<P><L>[<hex>]<CR>`, where `<P>` is `.` (set) or `?` (query), `<L>` is a letter or digit, and `<hex>` is a fixed-width hex argument.

**Reply:** `=<RR>[<data>]<CR><LF>`

| `RR` | Meaning | |
|---|---|---|
| `00` | Accepted, no fault | **[C]** |
| `20` | Accepted, but a fault/inhibit condition is active (seen on every reply until the vacuum interlock released) | **[C]** |
| `24` | **Refused**: `.BFA0` while the vacuum interlock was active | **[C]** |
| others | The reply-level errors LEO-32 knows are 474 invalid parameter, 475 range error, 476 internal fault, 477 comms timeout, 478 unknown command. The exact code mapping is unconfirmed | **[F]** |

A host should treat any `RR` other than `00` / `20` as "command not applied".

## 4. Command reference

| Command | Arg width | Function | Encoding | Range / typical | |
|---|---|---|---|---|---|
| `?S` | – | **Status poll** | reply `=RRbb`, where bb = status bits (§5) | `=0040` normal | **[C]** |
| `?H` | – | Hardware ID | reply `=RRM08` | `M08` on this unit | **[C]** |
| `.R` | – | **Reset**: clears the latched fault flags (spurious reset, trip) and acknowledges (status bit 0x01) | | | **[C]** |
| `.O` | 4 hex | **Supply on/off word** | bit map §4.1 | `0C07`, `0F07`, `0001` | **[C]** |
| `.E` | 3 hex | **Accelerating voltage** | `round(kV × 100) − 2` | 1 kV `062` · 5 kV `1F2` · 10 kV `3E6` · 20 kV `7CE` · 30 kV `BB6`; ~10 V/count | **[C]** linear 1–30 kV |
| `.F` | 3 hex | **Filament current** | `mA − 16` (1 mA/count) | 2.468 A = `994`; ramp from `01C` | **[C]** |
| `.B` | 3 hex | **Emission current setpoint** | `µA × 10` | 400 µA `FA0` · 375 µA `EA6` · 350 µA `DAC` · off `000` | **[C]** |
| `.C` | 3 hex | **SE collector bias** | `2048 + 5 × V` (signed, 0.2 V/count) | +300 V `DDC` · +100 V `9F4` · 0 V `800` | **[C]** |
| `.1` `.2` `.3` | 3 hex | **PM high voltage**, detector channels 1–3 | 12-bit, scale unconfirmed | default `190`; brightness moves `.1` between `3CA` and `EB0` | **[C]** encoding **[I]** scale |
| `.T` | 1 hex | Filament type | | `1` (tungsten) | **[C]** |
| `.A` | 1 hex | Anode type | | `1` | **[C]** |

On this system only channel 1 (`.1`) is used. The SE / VPSE switchbox relays route the active PM to channel 1. Image **contrast** does not use this link; it is the scintillator amplifier gain on the image-processor side.

Present in the firmware for field-emission-gun models and not used on this tungsten system **[F]**: extractor, suppressor and gun-lens voltages, field-emission filament calibration, lens/beam wobble. Their command letters were not captured.

### 4.1 `.O` supply word

| Bit | Function | Evidence |
|---|---|---|
| 0x0001 | Always set (logic / standby supply?) | never cleared **[C]** |
| 0x0002, 0x0004 | Detector / collector supplies (on in all non-shutdown states) | switch together with 0x0400 **[C]**, names **[I]** |
| 0x0100 | **EHT (accelerating voltage) on** | **[C]** |
| 0x0200 | **Filament supply on** | **[C]** |
| 0x0400 | Detector supply (PM?) | switches with 0x0002/0x0004 **[C]**, name **[I]** |
| 0x0800 | **Scintillator HV** | firmware forces it off in VP mode **[F]**. LEO-32 also sends it off (`0407`) while the vacuum interlock is active **[C]** |

Words used by LEO-32 **[C]**:

| Word | State |
|---|---|
| `0407` | idle while vacuum not ready (scintillator off) |
| `0C07` | idle, vacuum ready, beam off |
| `0D07` | EHT on, filament off (beam-on step 1) |
| `0F07` | EHT and filament on: **beam on** |
| `0301` | shutdown / EHT-off step 1 (detector supplies off) |
| `0201` | EHT off, filament still on ("EHT off") |
| `0001` | all off (after shutdown) |
| `0B07` (derived) | beam on in VP (0x0800 cleared): **[I]**, not yet seen |

## 5. Status byte (`?S` → `=RRbb`)

The firmware masks `bb` with 0x5F.

| Bit | Meaning | Latched? | LEO-32 message | |
|---|---|---|---|---|
| 0x40 | Unit present / OK | – | – | **[C]** |
| 0x10 | **Inhibited by vacuum system** (hardware interlock line active) | follows the line | 435 "EHT - Inhibited by Vac System" | **[C]** |
| 0x08 | **Spurious reset**: the set has restarted (set at every power-up) | until `.R` (only clears once the interlock is released) | 436 "EHT - Spurious Reset" | **[C]** |
| 0x04 | **Filament blown** | until `.R` | 433 "EHT - Filament Blown" | **[F]** (field order) |
| 0x02 | **EHT tripped** (arc / over-current) | until `.R` | 434 "EHT - Set Tripped" | **[F]** (field order) |
| 0x01 | Reset acknowledged (set for one poll after `.R`) | one poll | – | **[C]** |
| 0x20, 0x80 | masked off | | | |

Values seen:

| `bb` | Meaning |
|---|---|
| `58` | vacuum not ready (power-up) |
| `59` | after `.R` while still inhibited |
| `48` | interlock just released |
| `41` | after `.R` with the interlock released |
| `40` | normal |

## 6. Typical usage

All sequences below are what LEO-32 sends; a replacement should reproduce them.

### 6.1 Host start-up (vacuum not yet ready) **[C]**

```
.R            =20
?H            =20M08
?S            =2059
.O0C07        =20
.A1   .T1     =20
.CDDC         =20          collector +300 V
.O0C07  .1190  .CDDC
.O0407                     scintillator off while inhibited
.1778                      PM channel 1 to the stored brightness
.BFA0         =24          refused while inhibited (the original host retries ×10)
```
Then loop every 4.5 s: `?S` → (if bb ≠ 40) `.R` → `?S`.

### 6.2 Vacuum ready (interlock releases) **[C]**

```
?S            =2048        0x10 cleared
.R
?S            =0041
.O0C07  .T1  .A1  .B000  .CDDC  .1190  .2190  .3190     re-send everything
```
Then plain `?S` polling (`=0040`). Note: in the original system the host does this restore whenever the status returns to 0x40 after any fault.

### 6.3 Beam on **[C]**, about 15 s

| Step | Command(s) | Notes |
|---|---|---|
| 1 | `.O0C07`, `.BFA0` | emission setpoint 400 µA |
| 2 | ~1 s later: `.O0D07`, `.E008`, `.E1F2` | EHT on, start at 0.1 kV, then the target (5 kV). Above 20 kV, ramp as in §6.5 |
| 3 | 0.47 s later: `.O0F07` | filament supply on |
| 4 | `.F01C`, then **+0x93 (147 mA) every 0.466 s** to `.F704` (1.812 A) | fast warm-up |
| 5 | pause 0.9–1.8 s | |
| 6 | **+0x27 (39 mA) every 0.466 s** to the setpoint (`.F994` = 2.468 A), with a smaller final step | slow approach to saturation |

### 6.4 Adjustments while the beam is on **[C]**

| UI control | Command | Notes |
|---|---|---|
| Filament current | `.F<new>` | single step (2.468 ↔ 2.480 ↔ 2.450 A) |
| Accelerating voltage ≤ 20 kV | `.E<new>` | single step |
| Accelerating voltage > 20 kV | ramp, §6.5 | |
| Emission ("beam") current | `.B<new>` | e.g. 350 µA `.BDAC` |
| Collector bias | `.C<new>` | sliders send intermediate values (steps of 0x2D ≈ 9 V) |
| Brightness | `.1<new>` | PM voltage |
| Probe current, contrast | none | condenser lenses / scintillator amplifier on other links |

### 6.5 kV above 20 kV **[C]**
The host ramps in **1 kV steps (0x64) every 0.466 s** (~2.1 kV/s), both up and down across the 20–30 kV range. It may jump directly between any values ≤ 20 kV.

Example, 30 → 5 kV: `.EB52`, `.EAEE`, … `.E7CE` (20 kV) one step per 0.466 s, then `.E1F2`.

### 6.6 EHT off (filament stays lit) **[C]**

```
.B000   .O0301   (0.7 s)   .O0201
```
EHT on again: `.O0F07  .BFA0  .O0F07  .E008  .E1F2  .F994`. The filament is still hot, so there is no ramp.

### 6.7 Shutdown (beam off, filament cooled) **[C]**, about 9 s

```
.B000   .O0301   (0.7–0.9 s)   .O0201
.F900, then −0x93 every 0.466 s: .F86D .F7DA … .F0F2 .F05E
.O0001
```

### 6.8 Fault handling (original firmware behaviour, `_eht_fault_monitor`) **[F]** + **[C]**

| `bb & 0x5F` | Host action |
|---|---|
| `40` | OK. If the previous poll was a fault: switch the supplies back on and re-send all settings (`.O`, `.T`, `.A`, `.B`, `.C`, `.1`–`.3`) |
| `50` (vacuum inhibit only) | Remember the kV setpoint and wait. Restore when the inhibit clears |
| anything else (spurious reset, blown, trip) | Save beam current, collector and PM settings; send `.R`; reset ramp state; show the message; leave the beam off until the operator turns it on |

**Comms loss [C]:** with the fiber pulled, the original host kept sending `?S`. It flagged error 477 once, sent nothing else, and simply resumed polling when replies returned (`=0040`). The set kept its state (tested with the beam off only). A replacement should treat comms loss with the beam on as a fault: when the link returns, read `?S`, and if bit 0x08 is set, assume all settings are lost.

## 7. Interlocks and requirements for a replacement host

1. **Respect the hardware vacuum interlock** (bit 0x10). Do not send beam-on sequences while it is set; they are refused (`=24`).
2. **Ramp the filament** with the profile in §6.3 / §6.7. Never jump from 0 to the operating current.
3. **Ramp the kV above 20 kV** at ≤ 1 kV per 0.466 s.
4. **Filament off and cooled before any chamber pressure change** (vent, enter/leave VP, VP pressure change). "EHT off" is not enough, because it leaves the filament lit.
5. **Scintillator off in VP:** clear `.O` bit 0x0800 whenever the chamber is in VP (or the vacuum is not ready), and restore it in high vacuum.
6. **Re-send all settings after any reset** (status 0x08, or a fault clearing). The set does not keep them.
7. **Send `.B000` before switching the EHT off**, as LEO-32 does.

## 8. Open items

- Bits 0x04 / 0x02 (blown / tripped) are inferred from firmware field order; confirm on a real fault.
- Reply codes `RR` other than `00` / `20` / `24`.
- Individual meaning of `.O` bits 0x0002, 0x0004, 0x0400.
- PM voltage scale for `.1`–`.3`.
- Whether the set has its own comms watchdog when the beam is on.
- A VP-mode `.O` word (`0B07`?) has not been captured, because LEO-32's VP controls are disabled on this machine.
- Fiber transceiver part number and wavelength.

## 9. Source captures

`20261112_172619_eht_cold_boot.log`, `…173118_eht_pump_beam_on_adjust.log`, `…175857_eht_beamcurrent_ehtoff_vp.log`, `…194728_eht_kv_detectors_commsfail.log`. Working notes: `capture_tools/EHT_PROTOCOL.md`.
