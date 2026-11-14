# EHT link (UART A): IP board ⇄ EHT supply ("EHT set")

Physical: fiber, 9600 8N1, normal polarity. Teensy ch1 (pin 0) = **IP board → EHT**, ch2 (pin 9) = **EHT → IP board**.
Commands are ASCII ending in **CR only**. Replies start with `=` and end in CR LF.
Sources: captures `20261112_172619_eht_cold_boot.log` (power-on, LEO-32 start), `20261112_173118_eht_pump_beam_on_adjust.log` (pump-down, beam on, adjustments, shutdown) and `20261112_175857_eht_beamcurrent_ehtoff_vp.log` (emission vs probe current, EHT off/on, VP mode); GSP module `g100.440`.

## Reply format
`=SS` or `=SSdata`, where `SS` is a two-hex-digit status byte:
- `00`: OK
- `20`: OK, but a fault or inhibit is active (seen on every reply until the vacuum interlock released)
- `24`: command refused (seen for `.BFA0` while the vacuum interlock was active)

Each command gets its reply within 3–7 ms.

## Commands

| Command | Example | Meaning | Encoding |
|---|---|---|---|
| `?S` | `?S` → `=0040` | **Status poll**, every ~4.5 s | status byte + 2 hex digits (bits below) |
| `?H` | `?H` → `=20M08` | Hardware ID | `M08` on this unit |
| `.R` | `.R` | Reset / clear a latched trip | |
| `.O` | `.O0C07` | **Supply on/off bits** (4 hex digits) | see table below |
| `.E` | `.E1F2` | **Accelerating voltage** | 3 hex digits ≈ kV × 100 − 2 (5 kV = `1F2` = 498, 7 kV = `2BA` = 698, 4 kV = `18E` = 398); about 10 V per count, 12-bit |
| `.F` | `.F994` | **Filament current** | 3 hex digits = mA − 16 (2.468 A = `994` = 2452, 2.480 A = `99F`, 2.450 A = `982`); 1 mA per count |
| `.C` | `.CDDC` | **SE collector bias** | 3 hex digits = 2048 + 5 × volts (300 V = `DDC` = 3548, 100 V ≈ `9F4` = 2548, 0 V = `800`) |
| `.1` `.2` `.3` | `.174E` | **Photomultiplier (PM) voltage**, detector channels 1–3 | 3 hex digits; set to `190` (400) for all three at start-up; the **brightness** slider moved channel 1 between `3CA` and `EB0` |
| `.B` | `.BFA0` / `.B000` | **Emission current setpoint** | 3 hex digits = µA × 10 (400 µA = `FA0`, 375 µA = `EA6`, 350 µA = `DAC`); sent before EHT on, `000` before EHT off / shutdown |
| `.T` | `.T1` | Filament type | 1 on this system |
| `.A` | `.A1` | Anode type | 1 |

The **contrast** slider produced no EHT traffic; contrast is probably the scintillator amplifier gain, set elsewhere (the GSP code has `_convert_contrast_to_SCA_vals` / `_set_SC_amplifier`). Brightness → PM voltage matches `_convert_brightness_to_PM_val` / `_set_PM_level`.

### `?S` status bits (second byte of the reply)

| Value | Seen when | Interpretation |
|---|---|---|
| `58` | vacuum not ready (start-up, pumping) | 0x40 + 0x10 + 0x08 |
| `59` | right after `.R` while still inhibited | + 0x01 (reset acknowledged) |
| `48` | first poll after the vacuum interlock released (17:34:53) | 0x10 cleared |
| `41` | after `.R` with the interlock released | spurious-reset flag (0x08) cleared, 0x01 = reset acknowledged |
| `40` | normal: idle, beam on, during all adjustments | 0x40 = unit present / OK |

- **0x10 = vacuum interlock active** (hardware line from the vacuum controller's relay). It cleared at 17:34:53, matching the operator's click at 5:35 and LEO-32 "EHT vac ready = yes".
- **0x08 = spurious reset** (the EHT set has restarted since the last `.R`; set at every power-up), cleared by `.R` once the vacuum interlock is gone.
- 0x01 = reset acknowledged (clears on the next poll).

**Full bit map, from the GSP firmware (`g100.440`):** `_cp_eht_status` hands the PC `g_fault_status` (the `?S` byte masked with 0x5F) split into flags in this order: comms error, **0x04**, **0x02**, **0x08**, **0x01**, **0x10**. LEO-32 lists the matching parameters in the order `DP_FIL_BLOWN`, `DP_EHT_TRIPPED`, `DP_EHT_RESET`, `DP_EHT_VAC_READY`. 0x10 = vacuum is confirmed by capture, which anchors the order:

| Bit | Meaning | LEO-32 message | Confidence |
|---|---|---|---|
| 0x40 | unit present / OK | none | captured |
| 0x10 | inhibited by vacuum system | 435 "EHT - Inhibited by Vac System" | captured |
| 0x08 | spurious reset (set restarted) | 436 "EHT - Spurious Reset" | captured (power-up) + field order |
| 0x04 | **filament blown** | 433 "EHT - Filament Blown" | field order only |
| 0x02 | **EHT tripped** (arc / over-current) | 434 "EHT - Set Tripped" | field order only |
| 0x01 | reset acknowledged | none | captured |
| 0x20, 0x80 | masked off by the firmware; 0x20 appears in the reply-status byte while a fault is active | | |

Comms failure is a separate firmware flag (`g_comms_error` = 0x80 when the set stops answering), shown as "EHT Comms Fail". Reply-level errors (messages 474–478: invalid parameter, range error, internal fault, comms timeout, unknown command) are carried in the first status byte of each `=SS` reply; `=24` (refused while inhibited) is one of these, and the exact code-to-message mapping is unconfirmed.

**Firmware fault handling (`_eht_fault_monitor`)**, which the replacement should copy:
- `(status & 0x5F) == 0x40`: OK. If the previous poll was a fault, call `switch_supplies_back_on` + `restore_eht_settings` (this is the re-send of `.O`, `.T`, `.A`, `.B`, `.C`, `.1`–`.3` seen when the vacuum interlock released).
- `== 0x50` (vacuum inhibit only): remember the EHT setpoint and wait; it is restored when the inhibit clears.
- Anything else (blown, tripped, spurious reset): save beam current, collector and PM settings, send `.R`, reset ramp state, and keep polling. LEO-32 shows the message; the beam stays off until the operator turns it on again.
- While the interlock is active the IP board repeats `?S` → `.R` → `?S` every 4.5 s. After the release it sends only `?S`.

### `.O` supply bits
| Value | When |
|---|---|
| `0407` / `0C07` | start-up, idle (beam off) |
| `0D07` | beam on, step 1 (0x0100 set; then the EHT ramp starts) |
| `0F07` | beam on, step 2 (0x0200 set; then the filament ramp starts) |
| `0301` | shutdown step 1 (low byte 07 → 01) |
| `0001` | shutdown step 2: all off |

| `0201` | EHT off (filament stays on) |

**Confirmed (run 3):** 0x0100 = EHT on, 0x0200 = filament on. "EHT off" sends `.O0301` → `.O0201` and leaves the filament lit at its setpoint; "EHT on" then sends `.O0F07`, `.BFA0`, `.O0F07`, `.E008`, `.E1F2`, `.F994` (straight to the setpoint, no ramp).
Bits 0x0400/0x0800 and low-byte 0x02/0x04 always switch together (on with `.O0C07`, off with `.O0301`), so they could not be separated; probably detector / collector / scintillator supplies. Bit 0x0001 is never cleared.

## Sequences

**Start-up (LEO-32 start, before vacuum is ready):** `.R`, `?H` → `M08`, `?S`, `.O0C07`, `.A1`, `.T1`, `.CDDC` (collector 300 V), `.O0C07`, `.1190`, `.CDDC`, `.O0407`, … `.1778`, `.BFA0` ×10 (refused with `=24`) … then the `?S`/`.R` loop.

**On vacuum ready (17:34:53–58):** `?S` → `=2048`, `.R`, `?S` → `=0041`; then `.O0C07`, `.T1`, `.A1`, `.B000`, `.CDDC`, `.1190`, `.2190`, `.3190` (re-sends all settings), then plain `?S` polling (`=0040`).

**Beam on (17:37:49):**
1. `.O0C07`, `.BFA0`
2. `.O0D07` → `.E008` → `.E1F2`: EHT on, set to 5 kV
3. `.O0F07`: filament supply on
4. Filament ramp: `.F01C`, then +0x93 (147 mA) every 0.47 s up to `.F704` (1.81 A); pause 1.4 s; then +0x27 (39 mA) every 0.47 s up to `.F994` (2.468 A), with a final smaller step. About 14 s in total.

**Adjustments:** each UI change sends the new `.F`, `.E`, `.C` or `.1` value. The sliders send a stream of intermediate values (collector bias steps of 0x2D ≈ 9 V while dragging).

**Shutdown:** `.B000`, `.O0301`, `.O0201` (EHT off), then the filament ramps down: `.F900`, then −0x93 (147 mA) every 0.47 s to `.F05E`, then `.O0001`. About 8.5 s in total.

**Things that produce no EHT traffic:** probe current (condenser lenses; needs "Optibeam"), contrast, and the VP transition itself. With the chamber at the VP setpoint (hpapp `TO 7`) the status stayed `=0040` (no vacuum interlock), and beam on/shutdown used exactly the HV sequences. The only extra message was a lone `.O0001` about when `TO 3` brought the chamber back to HV (LEO-32 re-sending the idle state on a vacuum-status change).

## VP mode and the scintillator (firmware, not yet captured)

`g100.440` has `_cp_scint_toggle`, a TIGA call from the PC that sets `g_VP_mode`. While `g_VP_mode` = 1, `_set_new_state` clears **bit 0x0800** of the `.O` word on every supply-state update, so **0x0800 is almost certainly the scintillator HV**, forced off in VP. Run 3 never triggered this because the VP transition was driven from hpapp, not LEO-32's own (greyed-out) VP controls; the scintillator stayed on at 20 Pa. The replacement should drop 0x0800 whenever the chamber is above the HV threshold.

## Run 4 (`20261112_194728_eht_kv_detectors_commsfail.log`)

**kV scale is linear over the whole range:** 1 kV = `.E062` (98), 10 kV = `.E3E6` (998), 20 kV = `.E7CE` (1998), 30 kV = `.EBB6` (2998), so `.E` = kV × 100 − 2 holds from 1 to 30 kV.

**Above 20 kV the board ramps the voltage itself:** steps of 0x64 (1 kV) every 0.466 s (~2.1 kV/s), both up (20 → 30 kV) and down (30 → 20 kV). Below 20 kV, changes are sent as a single step (30 → 5 kV went 1 kV/step down to `.E7CE`, then straight to `.E1F2`). This matches the readback the operator saw.

**Comms failure (fiber pulled, beam off):** the IP board keeps polling `?S`. With no reply it waits ~4.5 s (timeout) before the next normal 4.5 s interval, so polls go out every 9.0 s. LEO-32 raised error 477 "EHT Set Comms timeout" once. There were no retries, no `.R`, and nothing re-sent after reconnecting: the first reply was `=0040` and polling simply resumed at 4.5 s. Not tested with the beam on.

**Detector select:** LEO-32 has no separate SE / VPSE selection on this system; the VP switchbox relays route one PM to the same EHT channel (`.1`), so no other PM channel is used.
