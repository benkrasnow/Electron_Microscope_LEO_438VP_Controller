# Stage/Vacuum link (UART B) – protocol notes

System: LEO 438VP with two-stage rotary pump + turbomolecular pump, Variable Pressure option (valve isolates turbo from chamber in VP while the turbo keeps pumping the gun; separate gas-admit valve in addition to the vent valve). No ion pump.

Physical: 9600 8N1, normal polarity, ASCII, every message ends CR LF.
Teensy ch1 (pin 0) = IP board → STGVAC controller; ch2 (pin 9) = STGVAC → IP board.
The IP board sends a command; the controller answers with a line starting `=` and a two-digit hex status.
The controller sometimes pauses about 60 ms mid-reply; this is normal.

Sources: captures in `captures/`, plus the GSP modules `g600.440` (vacuum) and `g500.rlm` (stage). Function names below are the GSP functions that build each command.

## Reply status code (first token)

| Code | Meaning | Evidence |
|---|---|---|
| `=00` | OK | every normal reply; `_vacuum_fault_routine` checks for `00` |
| `=20` | OK + vacuum event pending. The IP board answers with `.VS` | every `=20` was followed by `.VS` within 50 ms |

## Vacuum commands (all strings in g600.440)

| Cmd | GSP function | Seen | Notes |
|---|---|---|---|
| `.VT` | `_read_vacuum_status`, `_ProcStgVacCmds` | ✓ | status poll, ~1.2 s |
| `.VS` | `_vacuum_fault_routine` | ✓ | fault/inhibit detail, see below |
| `.VL` | `_system_pumping_tiga` | ✓ | `.VL P` pump, `.VL V` vent |
| `.VO` | `_operate_isolation_valve_tiga` | | |
| `.VP` | `_column_isolation_tiga` | | |
| `.VB` | `_column_pumping_tiga` | | |
| `.VI` | `_operate_wdx_gate_valve_tiga` | | |
| `.VV`, `.VU` | `_get/_save_system_config_data`, `_read_vacuum_software` | | `.VV 66` = `_check_vac_board` |
| `.VX`, `.VW` | `_read_comms_software`, `_touch_alarm_off` (`65`), `_calibrate_scm` (`61`) | | register-style read/write |
| `.VY` | `_get_comms_psu` | | |
| `.CA`–`.CG` | configure airlock, viewing window, front panel, tilt-0, column pumping, EDX, WDX | | sent at start-up |
| `.TA`–`.TE`, `.TH` | thresholds: scintillator, acc. voltage, PM, ion pump, filament; EDX | | sent at start-up; values from `_calculate_threshold` |
| `.QA`–`.QE` | 4Q-BSD control/visible/gain, SCM range, take SCM reading | | |

## Stage commands (all strings in g500.rlm)

| Cmd | GSP function | Seen |
|---|---|---|
| `.SD` | `_read_stage_status` | ✓ poll |
| `.SF` | `_move_to_a_position` (go-to) | |
| `.SH` | `_move_a_short_distance` | |
| `.SI` | `_move_stage_at_speed` (joystick) | |
| `.SK` | `_send_abort_move_tiga_request` | |
| `.SA` | `_set_stage_position` | |
| `.SE` | `_send_axes_reset` | |
| `.SB` / `.SC` | `_set_cruising_speed` / `_set_ramp_rate` | |
| `.SV` | `_set_axis_stepsizes` | |
| `.SW` | `_write_joystick_pixelsize` | |
| `.SL` | `_set_stage_config` | |
| `.SO` | `_set_stage_lower_limits` | |
| `.SJ` / `.SQ` | `_set_usr_upr_limits` / `_set_usr_low_limits` | ✓ |
| `.SR` | `_disable_touch_alarm` | |
| `.SS` | `_check_stage_psu` | |
| `.SM` / `.SN` | `_write_axis_register` / `_read_axis_register`, `_read_axis_software` | |
| `.SY` | `_read_hw_fw_ver_numbers` | |
| `.SZ` | `_general_stage_cmd` | |
| `.SP` | `_stage_fault_routine` (stage counterpart of `.VS`) | |

### Stage limit encoding (`.SJ` / `.SQ`)
Values are 24-bit offset binary, zero = 2^23 = 8388608 counts, axis order X Y Z T R:

| Axis | `.SJ` (upper) | `.SQ` (lower) | as ± counts |
|---|---|---|---|
| X | 8796045 | 7981171 | ±407437 |
| Y | 8897904 | 7879312 | ±509296 |
| Z | 9518027 | 7259189 | ±1129419 |
| T | 9402368 | 7374848 | ±1013760 |
| R | 14471166 | 5178369 | +6082558 / −3210239 |

The IP board re-sends `.SJ` + `.SQ` after every change in vacuum state.

## `.VT` reply: `=00 NCP 0 N N N <state> <value> N N`

States seen: `WVT` waiting for vent · `NSP` at air · `WTUS` waiting for turbo speed · `WP` waiting for Penning · `SP` pumped, value = gauge reading · `SPE` Penning error · `SPVR` pumped and vacuum ready.

### Gauge value → pressure (decoded, confirmed)
`_decode_vac_status` runs `atol` on the value and calls `_calculate_pressure(value, mode)`. The system vacuum uses mode 0:

    P_Torr = 1 / (60 × value^0.9)          (value 0 is treated as 1)

The GSP stores `P_Torr × 1.3333 / 1000` (bar); the PC converts to the chosen units. All 8 operator readings (9.75e-5 to 1.34e-4 Torr) agree within 0.7%. Inverse: `value = (1 / (60 P))^(1/0.9)`, e.g. 1e-4 Torr → 294, 2e-5 Torr → 1759.
Mode 1 is a second formula (constants 0.2666, 500, 1e-8, exponent 0.185), used for another reading that hasn't appeared in captures yet.

## `.VS` reply: `=00 b0 b1 b2 b3 b4 b5 b6 b7` (hex)

`_vacuum_fault_routine` checks for status `00`, then passes each byte to a handler:

| Byte | Handler | Seen |
|---|---|---|
| b0 | `_check_inhibits` | 0F → 07 → 00 |
| b1 | `_check_edx_errors` | 00 |
| b2 | `_check_system_errors` | 01 during the Penning gauge failure |
| b3 | `_check_gun_errors` | 00 |
| b4 | `_check_column_errors` | 00 |
| b5 | `_check_wdx_errors` | 00 |
| b6 | `_check_airlock_errors` | 00 |

### Inhibit bits (b0)
`_check_inhibits` copies bits 0–3 into four flags of `VACUUM_STATUS` (offsets 0x1C, 0x1F, 0x1D, 0x1E). The UI string table (`s400eng.dll`) names four vacuum inhibits in this order: **Vac EHT set inhibit, Vac Acc Volt inhibit, Vac PM inhibit, Vac Scint. inhibit**. Assuming the flags follow that order (0x1C…0x1F):

| Bit | Inhibit (probable) | Released at |
|---|---|---|
| 0 | EHT set (gun high-voltage supply) | ready, 13:50:44, ~9.9e-5 Torr |
| 1 | Scintillator HV | ready |
| 2 | Accelerating voltage | ready |
| 3 | **PM (photomultiplier) HV** | **13:39:25, ~1.17e-4 Torr: the audible click** |

**Update (vent/pump capture 20261112_161149): both audible clicks are inhibit releases.** The operator heard a click at 16:16:54 (bit 3 released 16:16:55.6, raw 258) and at 16:17:28 (bits 0–2 released at ready, 16:17:26.6). Bit 3 releases at raw 256–258 in every pump-down (≈1.14e-4 Torr).

**Correction after the cold-boot capture:** the IP board programs all four interlock thresholds to raw 302 (≈9.8e-5 Torr, see below). The bit-3 release at raw 257 (≈1.13e-4 Torr) therefore doesn't match any configured threshold, and the earlier "PM interlock" explanation of the 13:39 click is doubtful. The click coincides exactly with bit 3 of the inhibit byte clearing, but what the controller keys that bit on (a timer, its own internal level, or the second "50" parameter) is still unknown. The bit-to-name order above is also still an assumption.

## Captures

| File | Content |
|---|---|
| `20261112_131633_stgvac_running_idle.log` | 30 s idle polling |
| `20261112_131836_stgvac_vent_pump.log` | Pump click (`.VL P`), turbo spin-up, Penning error (vent not included) |
| `20261112_132627_stgvac_pumpdown_to_ready.log` | 26 min pump-down to ready, inhibit-bit release at the 13:39 click, operator pressure notes in the file |
| `20261112_140133_stage_init_goto.log` | stage initialise and six go-to moves |
| `20261112_140932_stgvac_cold_boot.log` | vent, shutdown, cold power-up start-up configuration |
| `20261112_153419_vp_manual_mc_hp_to7.log` | 4-channel: power-up, hpapp handshake, pump-down, manual VP (`MC`/`HP`/`TO 7`) |
| `20261112_155926_vp_return_to_hv.log` | 4-channel: VP → HV with `TO 10` / `TO 3` |
| `20261112_161149_vent_and_pump_4ch.log` | 4-channel: vent and pump from the UI, both clicks matched |

## Stage (capture 20261112_140133: initialise + six go-to moves)

### Position encoding (confirmed against the operator's go-to targets)
All positions are 24-bit offset-binary counts (2^23 = 8388608), axis order X Y Z T R.

| Axis | Scale | UI zero at | Range (from `.SQ`/`.SJ`) | Check |
|---|---|---|---|---|
| X | 8148.74 counts/mm | 7981171 (= lower limit) | 0 – 100 mm | X=5 → 8021915, X=55 → 8429352 |
| Y | 8148.74 counts/mm | 7879312 (= lower limit) | 0 – 125 mm | Y=55 → 8327492 |
| Z | 64538.2 counts/mm | 7259189 (= lower limit) | 0 – 35 mm | Z=5 → 7581880 |
| T | 11264 counts/° | 8388608 | −90° – +90° | T=5 → 8444928 |
| R | 8448 counts/° | 8388608 | −380° – +720° | R=5 → 8430848 |

Every target and every limit matches to the count.

### Stage commands decoded

| Command | Example | Meaning |
|---|---|---|
| `.SF x y z t r` | `.SF 8429352 8286749 7323727 8388608 8388608` | **Go to** absolute position, all five axes always sent |
| `.SK` | `.SK` | **Abort / stop** move (operator STOP) |
| `.SB x y z t r` | `.SB 1500 1500 3000 2000 4000` | Cruise speed per axis. Set before a move, restored afterwards (e.g. Y=100, R=2500, Z/T reduced for the first move after init) |
| `.SE x y z t r` | `.SE 0 0 1 0 0` | **Initialise (home) the flagged axes** |
| `.SA x y z t r` | `.SA 7985269 7883410 7292522 8377344 8388608` | Set current position registers (after homing; T gets a −1.0° offset, R set to 0°) |
| `.SO x y z t r` | same values as `.SQ` | Stage (hardware) lower limits |
| `.SP` | reply `=40 00 00 00 02 00 00` | Stage fault/event detail, read after a `=40` status |

### `.SD` reply flags (per axis: position, motion, init)
- Motion: `S` stopped, `M` moving
- Init: `U` uninitialised, `I` initialised
- The IP board polls `.SD` every ~150 ms while anything moves, and every ~1.2 s otherwise.

### Status `=40`
Stage event pending, e.g. a limit switch reached during homing. The IP board answers with `.SP`. During Z homing `.SP` returned byte 3 = `02`; it then read all zeros once the event cleared.

### Initialisation sequence observed
1. `.SB 1500 1500 3000 2000 4000`, `.SO` lower limits
2. `.SE 0 0 1 0 0`: **Z homes first** (moves negative, `=40` limit events, bounces, reverses), then the position register jumps to ≈ lower limit and the flags go `S I`
3. `.SE 0 0 0 1 0`: T homes
4. `.SE 0 1 0 0 0`: Y homes
5. `.SE 1 0 0 0 0`: X homes (R is never homed)
6. `.SA` sets positions (X 0.50 mm, Y 0.50 mm, Z 0.52 mm, T −1.0°, R 0°), then `.SQ` / `.SJ` user limits
7. `.SB` with reduced Z/T speed, then `.SF` to the default position: X 50, Y 50, Z 1 mm, T 0°, R 0°

### Operator moves matched
| Operator | `.SF` / command | Result |
|---|---|---|
| GO X=5 | `.SF 8021915 …` | moving |
| STOP | `.SK` | stopped at X 14.75 mm |
| GO X=55 | `.SB 1500 100 …`, `.SF 8429352 …` | X 55.000 |
| GO Y=55 | `.SF … 8327492 …` | Y 55.000 |
| GO Z=5 | `.SF … 7581880 …` | Z 5.000 |
| GO T=5 | `.SF … 8444928 …` | T 5.0° |
| GO R=5 | `.SB … 2500`, `.SF … 8430848` | R 5.0° |

## Vent, shutdown and cold start-up (capture 20261112_140932)

### Vent (14:09:54)
1. `.SF … Z=7291458 …`: **Z driven to 0.5 mm first** ("Z move on vent"), sent together with
2. `.VL V`: **vent**. State `SPVR` → `WVT` (waiting for vent, with `=20` → `.VS` showing all four inhibits back on, `0F`) → `NSP` (at air) after about 18 s.
3. At air the IP board sends tighter user limits: **X and Y restricted to 35–65 mm** (`.SJ 8510839 8408980 …`, `.SQ 8266377 8164518 …`). Z, T and R are unchanged.

### Shutdown (14:10:48)
`.SK` (abort any move), then a single `FF` byte from the IP board's UART as it powered down. The link was silent for 137 s.

### Start-up configuration (14:13:22, sent once at power-up)
The stage controller had also been power-cycled: every axis came back `0 S U` (uninitialised), and the gauge reading reset to 0.

| Order | Command → reply | Meaning |
|---|---|---|
| 1 | `.VS` → `=00 0F 02 00 …` | all inhibits on; b1 (EDX errors) = 02 until EDX is configured |
| 2 | `.VX 80`…`86` → `56 30 31 2E 30 31 20` | comms CPU firmware **"V01.01 "** (one ASCII byte per register) |
| 3 | `.VV 80`…`86` → `56 30 32 2E 30 30 20` | vacuum CPU firmware **"V02.00 "** |
| 4 | `.VV 66` → `FD` | `_check_vac_board` |
| 5 | `.VX 61` → `C8`, `.VW 61 CC`, `.VW 61 C8` | SCM calibration register read/write |
| 6 | `.VY` → `=00 OK OK` | comms PSU check |
| 7 | `.CF N` → `=20`, `.SS`, `.VS` → b1 cleared | EDX not fitted; stage PSU check |
| 8 | `.CG N` `.CA N` `.CB N` `.CE N` | no WDX, no airlock, no viewing window, no column pumping |
| 9 | `.VP C` | column isolation (C = closed?) |
| 10 | `.TH 50` | EDX threshold |
| 11 | `.QA 1 N` … `.QA 4 N` | 4Q-BSD quadrants off |
| 12 | `.TA 302` | scintillator threshold |
| 13 | `.TB 302 50` | acc. voltage threshold, second level 50 |
| 14 | `.TC 302` | PM threshold |
| 15 | `.TD 8210 50` | "ion pump" threshold (GSP name `_ion_pump_threshold`). This 438VP has **no ion pump** (two-stage rotary + turbo), so it is probably a default for models that have one, unused here or reused for the gun/turbo side in VP mode |
| 16 | `.TE 302 50` | filament threshold, second level 50 |
| 17 | `.SL X 0 Y 1 Z 2 T 3 R 4` | stage axis map |
| 18 | `.CD N` | tilt-0 configuration off |
| 19 | `.SP` → all 00 | stage fault check |
| 20 | `.SC 100 200 30` ×5 | ramp rates, three values per axis |
| 21 | `.SB 1500 1500 3000 2000 3000` | cruise speeds |
| 22 | `.SY` → `=00 H 0001 F 0001` | stage hardware / firmware version 1 / 1 |
| 23 | `.SV 3926 3926 495 2840910 3787880` | **step size per count**, in 1/32 nm (X Y Z) and 1/32 n° (T R) |
| 24 | `.SN a 80`…`86` for axes 0–4 → all `00` | axis firmware registers (blank) |
| 25 | `.QC H` | 4Q-BSD gain high |
| 26 | `.SJ` ×4 | user upper limits (full range) |

After this the link settles into `.VT` / `.SD` polling. The stage stays uninitialised until the user runs stage initialise.

### Thresholds in pressure terms (`P = 1/(60·raw^0.9)`)
| Raw | Torr | Used by |
|---|---|---|
| 302 | 9.8e-5 | scintillator, acc. voltage, PM, filament (and "vacuum ready", which came at raw 302) |
| 50 | 4.9e-4 | second level of `.TB`, `.TE`, `.TD`: re-inhibit level (hysteresis). Supported by the VP return: the gauge read 1.38e-4 Torr and the state stayed `SPVR` |
| 8210 | 5.0e-6 | "ion pump" (not fitted on this system) |

### Step sizes check
`.SV / 32` = 122.69 nm (X, Y), 15.47 nm (Z), 88778 n° (T), 118371 n° (R). These match the counts/unit measured from the go-to test (122.72 nm, 15.49 nm, 88778 n°, 118371 n°). X/Y/Z are truncated to whole 1/32 nm.

## Joystick, delta moves, limit switch, abort (capture 20261112_170333)

- **Joystick is handled entirely by the stage controller.** Joystick moves on X, Y, Z, T, R (17:05:29–17:06:00) produced no commands from the IP board, only changing positions and `M`/`S` flags in the `.SD` replies.
- **Delta moves (ΔX/ΔY/ΔZ/ΔT/ΔR +5 in the UI) are sent as absolute `.SF` go-tos** with all five axes, each followed by `.SB` (speed restore; `R` uses 2500 for its move). `.SH` and `.SI` were never used.
- **Stage initialise** repeated the sequence documented above exactly (`.SB`, `.SO`, `.SE` for Z, T, Y, X in turn, `.SA`, `.SQ`, `.SJ`, `.SB 1500 1500 2100 1300 4000`, `.SF` to X50 Y50 Z1 T0 R0).
- **Lower limit switch (Z driven down with the joystick, 17:11:47):** status `=40`, and `.SP` returns `=40 00 00 00 02 00 00`. Z read −0.00 mm (the bottom of travel). The `.SP` reply has 6 bytes; byte 3 = Z and bit 0x02 = limit. This matches Z homing, so the bytes are probably [summary?] X Y Z T R. The condition persists while the axis sits on the switch: the reply stays `=40`, and the IP board polls `.SP` 3–4 times per second until it clears. LEO-32 showed a dialog. Other moves are still accepted: a go-to X=10 ran while Z was on the limit.
- **Abort:** `.SK` stopped the X move at 29.10 mm (operator STOP during go-to X=10).

### Coverage
Every command seen across all stage/vacuum captures: `.CA .CB .CD .CE .CF .CG .QA .QC .SA .SB .SC .SD .SE .SF .SJ .SK .SL .SN .SO .SP .SQ .SS .SV .SY .TA–.TE .TH .VL .VP .VS .VT .VV .VW .VX .VY`. Only `.VT` and `.SD` repeat during idle; there is no other periodic housekeeping.
Never seen, because the features are unused or not fitted on this system: `.SH .SI .SM .SR .SW .SZ .VO .VB .VI .VU .QB .QD .QE`. `.SR` is "disable touch alarm"; the old leolog shows "Stage Touching" errors, so the touch alarm is real, but its reply pattern has not been captured.
