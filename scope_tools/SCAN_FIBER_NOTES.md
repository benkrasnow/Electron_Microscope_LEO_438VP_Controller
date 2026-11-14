# Scan-generator fiber links: working notes

## Setup

- **Scope:** Tektronix MSO24 at 192.168.0.42 (VXI-11, `pyvisa-py`), 10x probes on the TTL side of the four fiber transceivers. The scan generator is the EO (electron-optics) board.
- **Channels:** CH1, CH2, CH3 = IP board → EO board; CH4 = EO board → IP board. There is no image data on any fiber; video is a separate analog coax.
- **Tools:**

| Script | Purpose |
|---|---|
| `scope_info.py` | Read-only connection check |
| `scope_setup.py` | Save / restore the user's setup, or arm a fast single shot |
| `arm_burst.py` | Arm the register-burst trigger (below) |
| `wait_grab_decode.sh <tag>` | Wait for the trigger, download, decode |
| `scope_grab.py` | Screenshot plus waveforms to `.npz` |
| `decode_scan_fiber.py` | Frame decoder (CH3 writes, CH4 replies) |
| `summarize_burst.py` | Distinct register writes in one capture |
| `plot_scan_timing.py` | Annotated timing diagram, `scope_captures/scan_fiber_timing.png` |

- **Burst trigger:** a pulse-width trigger on CH3, positive pulse 10–100 µs. Inside a frame the longest high is ≤ 16 bits (4.3 µs). Between per-line frames the line idles for a whole line period (≥ 1.4 ms at speeds 4–6). Back-to-back register writes leave about 14 µs gaps, so only multi-register updates fire it. The window is 400 ms at 25 MS/s with the trigger at 25 %.

## Signals

| Ch | Direction | Signal |
|---|---|---|
| CH1 | IP → EO | **Frame flyback**: high ~360 ms at the end of each frame. A short 2.76 ms pulse when a frame is restarted (magnification change, software start) |
| CH2 | IP → EO | **Line pulse**: 550 µs high per line. Period = line time (speed 4 1.405 ms, speed 5 2.811 ms, speed 6 5.608 ms) |
| CH3 | IP → EO | **Register frames**, 3.6864 Mbit/s NRZ, idle high, MSB first. One frame per line, ~27 µs after the CH2 rising edge. Set-up bursts have ~23 µs frame spacing |
| CH4 | EO → IP | Read replies only: one short word ~5 µs after a read request |

## Frame format (CH3), confirmed

32 bits:

| Bits | Field |
|---|---|
| b31 | 0 |
| b30 | **read request** |
| b29–b18 | register `n` (12 bits): `chip = n >> 5` (0–4), `reg = n & 31` |
| b17–b2 | **16-bit value** |
| b1–b0 | `11` |

- Bipolar DACs are offset binary: **32768 = zero**. Parking writes 32767.
- Register names come from the static EO map: 0x00–0x0A ramp parameters, 0x0B control (bit 15 = run: chip 2 control is written 0, then 0x8402), 0x0C routing, 0x0D options, 0x10–0x19 DAC0–DAC9.
- **CH4 reply:** starts with a 0 bit, then the value, then idle high. Seen: control reads = 0, routing reads = 4 or 5.

## Chip roles

| Chip | Role | Evidence |
|---|---|---|
| 0, 1 | Lens / focus-related DACs (and freeze levels) | Touched by WD and freeze, with read-modify-write via CH4 |
| 2 | **X (line) ramp generator** | All speed settings |
| 3 | **Y (frame) ramp**: reg 0x14 (DAC4) = Y position, written once per line | Steps +84 per line over 0–65535 → 780 lines; 780 × 2.81 ms + 0.36 s flyback = 2.55 s ≈ the speed-5 cycle. Parked at 511 during flyback / freeze |
| 4 | Barely used (DAC4 = 0 or 1 with speed) | |

## Control tests (2026-11-12, idle at air, mag 86×, WD 10 mm, speed 5)

### Scan speed
Chip 2 is stopped, reprogrammed and restarted; the block is sent three times with a small DAC1 trim.

| Speed | chip 2 r0A | Line period | per (r0A + 1) | chip 2 DAC4 (slope) | chip 2 options |
|---|---|---|---|---|---|
| 4 | 15 | 1.405 ms | 87.8 µs | ~1680 | 9 |
| 5 | 31 | 2.811 ms | 87.8 µs | ~840 | 9 |
| 6 | 63 | 5.608 ms | 87.6 µs | (range bit set) | 25 (bit 0x10) |

- Fit: r07 = 1024 (pixels?) + r09 = 272 (flyback?) = 1296 clocks of 14.7456 MHz = 87.9 µs. So line time ≈ (r0A + 1) × 1296 / 14.7456 MHz.
- Unchanged by speed: chip 2 r01 = 232, r07 = 1024, r09 = 272, DAC0 = 4095; chip 3 DAC2 = 3006, DAC3 = 565.

### Magnification
1. Park the four amplitude DACs at 32767.
2. Set the range bits (options low 3 bits on chips 2 and 3).
3. Wait ~40 ms for the relay.
4. Write the new amplitudes plus chip 2 DAC2 and chip 3 DAC0 (offsets).
5. Restart the frame.

| Mag | Range (chip 2 / chip 3 options) | X → A | X → B | Y → A | Y → B | Relay |
|---|---|---|---|---|---|---|
| 86× | 1 (9 / 249) | +3801 | −3655 | +3719 | +3552 | off |
| 1,000× | 3 (11 / 251) | +22282 | −21892 | +22020 | +21029 | on (clicks 86↔1,000) |
| 10,000× | 4 (12 / 252) | +16056 | −15749 | +15855 | +15141 | on |

DAC mapping: X ramp → chip 2 DAC6 = coil A, chip 2 DAC5 = coil B. Y ramp → chip 3 DAC6 = coil A, chip 3 DAC5 = coil B. Each range step ≈ 8× less deflection.

### Scan rotation (86×)

| Rotation | X → A | X → B | Y → A | Y → B |
|---|---|---|---|---|
| 0° (enable box) | +3801 | −3655 | +3719 | +3552 (unchanged from rotation off) |
| 45° | +73 | −5080 | +5284 | −106 |
| 90° | −3668 | −3501 | +3756 | −3700 |

The scan coils sit at 45° to the image axes, and the software applies a standard rotation matrix to the four weights. Coil A runs about 4 % hotter than coil B (calibration).

### Working distance 10 → 15 mm (rotation 45°)
- Read-modify-write on chips 0 and 1: read control and routing over CH4, then write chip 0 DAC0–3 and chip 1 DAC0–1.
- Amplitudes recomputed five times. Magnitude −23 % (keeps the field width), plus about 8° of rotation (lens-rotation compensation): X → (+569, −3933), Y → (+4090, +405).

### Freeze / unfreeze
- **Freeze:** the frame finishes and Y is parked at 511 while line pulses continue. Block sent twice: chip 1 DAC8 = 0, chip 1 r1B = 0, chip 2 DAC3 = chip 3 DAC1 = 2047, the amplitudes unchanged, and:

| Register pair | Frozen | Running |
|---|---|---|
| chip 0 DAC4, chip 1 DAC3 | 3070 | 2047 |
| chip 1 DAC2, chip 0 DAC5 | 1024 | 2047 |

- **Unfreeze:** the same block with the running values, then the flyback ends and the Y ramp restarts.

## Open
- Meaning of chip 0 / chip 1 DACs (lens, stigmator, beam shift, blanking?), chip 2 DAC0 / DAC1 / DAC4 roles, the options bits beyond the range field, chip 4.
- Spot mode, line scan, reduced area, focus and stigmator controls, beam shift: not yet tested.

## Captures (`scope_captures/`)
2026-11-13: `coldboot_01..03`, `idlecheck`, `ctl_01..09`, `ctl_dfoff_check`, `ctl2_01..04`, `ctl3_01..16`, `ctl4_01..02`, `spd_01..35`, `kv_01..02`, each with a `<prefix>_log.txt` of wall-clock trigger times. 2026-11-12:
`survey1_40ms`, `fast1_250M_8ms`, `long1_25M_400ms_trigch4` (software start), `survey2_speed5_4s`, `base_speed5_flyback`, `t1_speed5to4`, `t2_speed4to6`, `t3_speed6to5`, `t4_mag86to1000`, `t5_mag1000to10000`, `t6_mag10000to86`, `t7_rot_enable0`, `t8_rot90`, `t9_rot45`, `t10_wd10to15`, `t11_freeze`, `t12_freeze2`, `t13_unfreeze`. Each has `.npz`, `.png` (scope screen) and `_ch3.txt` (decoded).

## Session 2026-11-13

Loop tool: `cold_boot_loop.py <prefix> [shots] [minutes] [high_limit_us]`. With `high_limit_us = 2750` (speed 5 only) the trigger fires on any single frame between two per-line Y writes. 90 s idle check: no false triggers.

### Cold boot (`coldboot_01..03`)
- **Windows start ("waiting for LEO")**, shot 01: fixed 59-write reset burst (all control/routing 0, chip 4 configured r01=r02=1, r08=r09=255, control 0x8403; bipolar DACs 32768, 12-bit DACs 2048 or 0, chip 1 DAC4-7 = 128), then ramp setup (chip2 r00=1023 r02=62 r08=1024; chip3 r00=385 r01=504 r02=84 r08=768 r09=128), one CH4 read of chip 2 control, speed 5. Coil weights stay at 32768: timed raster with zero deflection.
- **LEO-32 UI start**, shot 02: same reset burst and setup (chip3 r00 = 511), frame restart.
- **Login**, shot 03: unfreeze block (running values), then 86x coil weights, then repeated lens read-modify-write (chip 0 DAC0-3, chip 1 DAC0-1) each followed by a coil-weight rewrite, every ~10-40 ms; still changing at the end of the window, done within ~17 s.

### Focus (Optibeam: focus = WD), `ctl_01`
- One fine click at 86x: **chip 1 DAC1 2230 -> 2234** (chip 1 DAC0 = 62 unchanged), read-modify-write via CH4 read of chip 1 control and routing. Chip 0 DAC0-3 not touched.
- Then all four coil weights rewritten (X->A 36085, X->B 30277, Y->B 35881, Y->A 35300): amplitude/rotation tracks WD.
- The same chip 1 + coil-weight block repeats with identical values every ~110 ms for the whole 400 ms window.
- Working model: **chip 1 DAC0 / DAC1 = objective coarse / fine**. Chip 0 DAC0-3 (changed by a WD *entry* and at login, not by focus) are probably condenser / Optibeam settings.

### Stigmator X+ (one click), `ctl_02`
- Just two writes, ~1.6 ms apart, sent once: **chip 0 DAC6 = 2231**, then **chip 0 DAC7 = 2047**. No read-modify-write, no coil-weight update. Only the single-frame trigger catches this.
- Working model: chip 0 DAC6 / DAC7 = stigmator X / Y, 12-bit centred on ~2048 (the reset value).

### Stigmator Y+ (one click), `ctl_03`
- Same pair, sent once: chip 0 DAC6 = 2231 (X unchanged), **chip 0 DAC7 2047 -> 1536**. Confirms DAC6 = stig X, DAC7 = stig Y, both always sent together.
- Step size / sign still open: Y+ moved DAC7 by -511, which is large for one click (polarity inverted? first click jumps from a default?).

### Stigmator Y+ again, `ctl_04`
- chip 0 DAC7 **1536 -> 1024**: a fixed **-512 counts per click at 86x**, Y polarity inverted (UI + = lower code). X stays 2231.
- 512 of 4096 per click is coarse, consistent with the user's note that every control's step scales with magnification (expect much smaller steps at high mag).

### Beam shift X+ (one click), `ctl_05`
- Sends the same block as freeze/unfreeze/login (chip1 DAC8, chip0 DAC4, chip1 DAC3, chip1 r1B, chip1 DAC2, chip0 DAC5 at running values), with **chip 2 DAC3 2047 -> 2036** (x4) and **chip 3 DAC1 2047 -> 2055**, then the four coil weights unchanged.
- So chip 2 DAC3 / chip 3 DAC1 are the shift offsets (2047 = zero shift), and that block is the general "beam position state" message, not freeze-specific. Both change for an X shift, probably because the shift goes through the same rotation as the scan (coils at 45 deg); Y+ shift should separate them.

### Beam shift Y+ (one click), `ctl_06`
- Same block: **chip 2 DAC3 2036 -> 2043 (+7)**, **chip 3 DAC1 2055 -> 2064 (+9)**.
- Step vectors in (chip2 DAC3, chip3 DAC1): X+ = (-11, +8), Y+ = (+7, +9); 92 deg apart, ~12 counts each at 86x.
- Compare the scan weights at the same moment (offsets from 32768): X scan (A, B) = (+3317, -2491) -> -37 deg; Y scan (A, B) = (+2532, +3113) -> +51 deg. Shift Y+ is at +52 deg, shift X+ at 144 deg = -36 deg reversed.
- So **chip 2 DAC3 = coil-A shift, chip 3 DAC1 = coil-B shift** (12-bit, 2047 = 0), and the software rotates shift by the same angle as the scan. UI X+ shift is opposite to scan +X; Y+ shift is along scan +Y.

### Dynamic focus on, angle 0 deg, `ctl_07`
- Only the four coil weights re-sent, values unchanged. No new per-line writes (still only chip 3 DAC4 each line). At 0 deg there is nothing to correct; needs a non-zero angle.

### Dynamic focus on, 30 deg, `ctl_08` (and `ctl_09`)
- **Done in software, per line.** First the IP reads chip 1 DAC0 and DAC1 (READ of DAC registers, not only control/routing), rewrites DAC0 = 62, then **writes chip 1 DAC1 (objective fine) once per line, 22 us after the chip 3 DAC4 Y write**.
- DAC1 is linear in Y: **DAC1 = 2087.3 + 0.004465 * Y** (fit over 127 lines) -> 2233.6 at Y = 32768, i.e. exactly the focus setting (2234) at frame centre, +-146 counts over the frame at 30 deg and 86x. Expect slope ~ tan(angle) x scan size.
- Side effect for capture: the 22 us gap fires both triggers (10-100 us and 10-2750 us) on every line while dynamic focus is on, so the loop must be stopped (it was, after shot 09).
- Dynamic focus off: free-run check `ctl_dfoff_check` shows only the per-line Y writes again (143 frames, all chip 3 DAC4). The off-transition writes themselves were not captured (loop was stopped).

### Tilt correction on, 0 deg (default), `ctl2_01`
- Only the four coil weights re-sent, unchanged (X->A 36085, X->B 30277, Y->B 35881, Y->A 35300). Same as dynamic focus at 0 deg.

### Tilt correction 30 deg, `ctl2_02`
- Only the coil weights change, and only the Y pair: Y->B 35881 -> 35464 (offset 3113 -> 2696), Y->A 35300 -> 34961 (2532 -> 2193). Both scale by **0.866 = cos 30 deg**. X->A / X->B unchanged.
- So tilt correction = Y scan amplitude x cos(tilt), applied in the rotated frame (before the coil mixing). Nothing else on the link.

### Reduced area on (centred, about half the screen), `ctl2_04`
- Beam-position block + coil weights re-sent (unchanged), then the **ramp set-up block sent twice**: the first pass has full-frame values, the second the reduced values. Then the speed block (chip 2 stop, options 9, DAC4 837, control 0x8402, r0A 31) is repeated with the new r01, plus one write of chip 4 DAC4 = 0. Then the beam-position + weights block is repeated about 5 more times.

| Register | Full frame | Reduced | Reading |
|---|---|---|---|
| chip 2 r08 | 1024 | **512** | X points per line |
| chip 2 r01 | 232 | **116** | halves with r08 (X ramp parameter) |
| chip 2 r00 | 1023 (0x03FF) | **16895 (0x41FF)** | bit 14 set + 511: start / park value plus a flag |
| chip 3 r08 | 768 | **384** | Y lines per frame |
| chip 3 r01 | 504 | **252** | halves with r08 |
| chip 3 r00 | 511 / 385 (0x1FF) | **16639 (0x40FF)** | bit 14 set + 255 |
| chip 2 r02 / chip 3 r02 | 62 / 84 | unchanged | step per point / step per line (Y step 84 matches DAC4 +84 per line) |
| chip 2 r07 / r09 | 1024 / 272 | unchanged | |

- **Line period 2.811 -> 1.736 ms**: per (r0A+1) = 32, 1296 -> 800 clocks of 14.7456 MHz. So line time ~ (r0A+1) x (X points + ~272-288 overhead clocks).
- **Y DAC4 now runs from ~16723 in +84 steps** (384 lines x 84 = 32256): Y covers the central half, 16384-49152. Y step per line is unchanged, so the Y pixel pitch is the same as full frame, and the same must hold for X (same slope DAC4 = 837, half the points).
- CH1 shows several 1.52 ms frame-restart pulses (full-frame restarts were 2.76 ms).

### Back to full frame, `ctl3_01`
- Mirror image of the reduced-area switch: one pass with the reduced counts but **r00 back to 1023 / 511 (bit 14 cleared)**, then the full counts (r08 1024 / 768, r01 232 / 504), speed block, chip 4 DAC4 = 0.
- **chip 2 DAC1 = X start offset**: ~110-113 in full frame, ~1087-1090 in reduced area (about a quarter of 4095, so the half-width line starts a quarter of the way across). It was 0 at boot. Y needs no start register because the IP writes Y (chip 3 DAC4) itself every line.
- Bit 14 of r00 is set only while reduced area is active.

### Line scan on, `ctl3_02`
- Normal full-frame ramp set-up and speed block first, then only three changes: **chip 3 r00 = 16219 (0x3F5B)**, **chip 3 r08 = 10**, **chip 3 r01 = 6**. chip 2 (X) is unchanged and keeps running at speed 5.
- The per-line Y write (chip 3 DAC4) steps down 16639 -> 16303 in -84 steps and then **stays at 16219 on every line**. So the line sits at Y = 16219 (about 25 % of the frame, probably where the line cursor is), and chip 3 r00 = the line's Y position.
- **CH1 and CH2 both go high and stay high** about 115 ms after the switch: no frame flyback edges, no line pulses. The per-line Y writes keep their 2.81 ms rhythm anyway. So CH1/CH2 are probably acquisition gates (frame / line valid for the frame store) rather than the timing source for the ramps, and line scan (a waveform display, not an image) doesn't use them.
- Line scan off (`ctl3_03`): ramp set-up with the line values, speed block, then chip 3 r00 = 511, r08 = 768, r01 = 504 restored; frame restarts on CH1 and line pulses on CH2 resume.

### Spot mode on (spot ~20 % from top and left), `ctl3_04`
- chip 2 stopped, **options 9 -> 1** (bit 3 cleared), **routing 8 -> 4**, r0A = 1, **control 0x8422** (run + bit 5, new; full scan uses 0x8402), DAC1 41, chip 4 DAC4 = 1, r0A = 15.
- Then **chip 2 DAC4 = 16895 (0x41FF)** and **chip 3 DAC4 = 16639 (0x40FF)**, and the per-line Y writes stop. CH1 ends low, CH2 high.
- Reading: with the X ramp held (control bit 5 / routing 4), chip 2 DAC4 is the X position directly, and chip 3 DAC4 the Y position: 16895 / 65536 = 26 % and 16639 / 65536 = 25 %, matching the spot location.
- **Correction to the reduced-area reading:** the same values 0x41FF / 0x40FF were the reduced-area r00 values. So bit 14 is not a flag: **r00 = ramp start position, 16-bit** (full frame X 1023, Y 511 = near the edge; reduced X 16895, Y 16639 = 25 %; line scan Y 16219 = the line position).
- Spot off (`ctl3_05`): full-frame ramp set-up (r00 1023 / 511, r08 1024 / 768) with chip 2 still stopped (options 1, routing 4, DAC1 41); ~100 ms later scanning is restored: options 9, routing 8, **DAC4 = 837 (back to slope)**, r0A 31, control 0x8402, DAC1 110, chip 4 DAC4 = 0. Y writes resume (Y parked at 595 while waiting for the frame).
- **chip 4 DAC4 = 1 in spot mode, 0 when scanning** (it was 0 or 1 with speed earlier): probably a blank/hold or scan-enable line, not a DAC level.

### Focus wobble on ("slow", 100 % amplitude), `ctl3_06`
- **Chip 1 is programmed as a ramp/waveform generator**, one write every ~0.94 ms (too slow to trigger; caught in the pre-trigger): control = 0 (stop), **r00 = 1468, r01 = 383, r02 = 383, r03-r06 = 0, r07 = 1, r08 = 4, r09 = 4, r0A = 1, routing = 1, control = 0x8063** (run + 0x63).
- Then the beam-position block twice, and the image switches to **reduced area** (same values as the reduced-area test: r00 16895 / 16639, r08 512 / 384, r01 116 / 252, chip 2 DAC1 1087-1090), speed block, chip 4 DAC4 = 0.
- After that nothing more on CH3 except the per-line Y writes: **the wobble runs in hardware on chip 1**, which drives the objective (chip 1 DAC0/1 are the objective coarse / fine). The loop did not re-trigger while wobbling.
- So chips 0-3 are all the same ramp-generator part: 2 = X, 3 = Y, 1 = objective (static DACs + wobble ramp), 0 = other lenses / stigmators.
- Wobble off (`ctl3_07`): **chip 1 control = 0** (stop the wobble ramp), ~0.94 ms later **chip 1 DAC1 = 2234** (objective fine back to the focus value), then the full-frame restore (same as leaving reduced area: r00 1023 / 511, r08 1024 / 768, r01 232 / 504, chip 2 DAC1 110). The UI shows the automatic window (reduced-area) scan during wobble; the link confirms it is entered at wobble-on and left at wobble-off.

### Wobble slow vs fast (100 %), `ctl3_08` (on, slow), `ctl3_09` (fast)
| chip 1 reg | slow | fast |
|---|---|---|
| r00 | 1468 | 1468 |
| r01 = r02 | 383 | **766** |
| r08 = r09 | 4 | **2** |
| r03-r06, r07, r0A, routing, control | 0, 1, 1, 1, 0x8063 | same |
- r01 x r08 = 1532 in both. Model: r01 / r02 = step size (up / down), r08 / r09 = clock ticks per step, r00 = limit (amplitude). Then period ~ (r00 / r01) x r08: slow 15.3, fast 3.8 units -> fast is ~4x faster at the same amplitude. Needs the 50 % amplitude test (expect r00 to change) to confirm.
- Wobble fast at **50 %** (`ctl3_10`): chip 1 fully rewritten with **exactly the same values as 100 %** (r00 1468, r01/r02 766, r08/r09 2). Nothing else on CH3. So amplitude is not in these registers at 86x, or 1468 is a clamp that both 50 % and 100 % hit at low mag. Open: test 10 % and a high magnification.
- Wobble fast at **10 %** (`ctl3_11`): again identical chip 1 values (r00 1468, r01/r02 766, r08/r09 2), nothing else on CH3 in the whole 400 ms window (40 ms pre-trigger included). **Amplitude 100 / 50 / 10 % produces no difference on this link at 86x.** Either the setting is not used at this magnification, or the amplitude reaches the column by another path. Open.

### 10,000x + wobble fast 100 %, `ctl3_12`
- Magnification change as before: weights parked at 32767, chip 2 / chip 3 options **12 / 252 (range 4)**, ~46 ms, new weights (46722 / 22018 / 45998 / 43530), offsets chip 2 DAC2 = 2238, chip 3 DAC0 = 2301. (Range 4 = 10,000x, matching yesterday.)
- Wobble then reprogrammed: **r00 1468 -> 2184, r01 = r02 766 -> 50**, r08 = r09 = 2, rest unchanged.
- So the wobble registers depend on magnification (86x -> 10,000x: r00 x1.49, step r01 /15) but not on the amplitude %, at least at 86x. Next: 50 % at 10,000x.
- 10,000x, fast, **50 %** (`ctl3_13`): **r00 = 1984, r01 = r02 = 250**, r08 = r09 = 2.
- **Wobble model (fits every capture so far, focus = chip 1 DAC1 = 2234):** r00 = focus - A, where A = wobble amplitude in objective-fine counts. The ramp runs from r00 up to focus + A and back in steps of r01 (up) / r02 (down), r08 / r09 clock ticks per step.
  - 86x: A = 766 (r00 1468) for 100 / 50 / 10 %; fast step = A (2 steps per sweep, 2 ticks), slow step = A/2 (4 steps, 4 ticks) -> slow is 4x the period.
  - 10,000x fast: 100 % -> A = 50 (r00 2184); 50 % -> A = 250 (r00 1984). The amplitude goes *up* at 50 %, which is unexplained (clamp, UI inversion, or the 100 % value captured before the setting applied). Check with 10 %.
- 10,000x, fast, **10 %** (`ctl3_14`): r00 = 2184, r01 = r02 = 50 -> **A = 50**, identical to the "100 %" shot `ctl3_12`.
- Resolution: `ctl3_12` was the magnification change re-sending the wobble with the *previous* setting (10 %, set at 86x just before); the switch to 100 % was not captured separately. So at 10,000x **A = 5 counts per % (10 % -> 50, 50 % -> 250; 100 % -> ~500 expected)**. At 86x A = 766 for every % = a clamp (the scaled amplitude would exceed it).
- Wobble summary: r00 = focus - A, r01 = r02 = step (fast: A, slow: A/2), r08 = r09 = ticks per step (fast 2, slow 4), r07 = 1, r0A = 1, routing 1, control 0x8063. A scales with % and inversely with magnification, capped at 766.

### Wobble off at 10,000x (`ctl3_15`): chip 1 control = 0, chip 1 DAC1 = 2234, then beam-position block and full-frame restore (as at 86x).

### Optibeam on (10,000x), `ctl3_16`
- Read chip 0 control + routing (CH4), then **chip 0 DAC0 = 45, DAC1 = 182** (~1 ms apart), read again, **DAC2 = 23, DAC3 = 218**; coil weights re-sent; read chip 1 control + routing, chip 1 DAC1 = 2234, DAC0 = 62 (objective unchanged).
- So **chip 0 DAC0-3 are what Optibeam computes** (condenser lens pair, coarse/fine each?). Compare login values: DAC0 43, DAC1 199-241, DAC2 24, DAC3 61-70.
- Optibeam **off** was not captured: the loop was on the burst-only trigger and the lens writes are ~1 ms apart. Loop restarted as `ctl4` with the single-frame trigger.
- With the single-frame trigger (`ctl4`): **Optibeam off sends nothing** on CH3. Optibeam on (`ctl4_01`) re-sends the identical lens set (chip 0 DAC0-3 = 45 / 182 / 23 / 218, coil weights, objective 2234 / 62). So Optibeam is a software mode: off just stops the condenser being recomputed; on recomputes and re-sends it (same result here because nothing else changed).

### Aperture 50 um -> 30 um (Optibeam on, 10,000x), `ctl4_02`
- Condenser recomputed via read-modify-write: **chip 0 DAC0 45 -> 49, DAC1 182 -> 128, DAC2 23 -> 21, DAC3 218 -> 251**.
- Then coil weights (small change), objective re-sent (2234 / 62), then **objective fine 2234 -> 2262** and two more coil-weight updates (amplitude/rotation follow the focus).
- Confirms chip 0 DAC0-3 = Optibeam condenser outputs, which depend on aperture, WD and magnification.

### Scan speed table (10,000x, range 4), `spd_01..07` plus speeds 4/5 from 2026-11-12
Every change: chip 2 control 0, options, routing 8, DAC4 (slope), r0A, control 0x8402, r09, r01, r07 = 1024, chip 3 r0A = 0, chip 4 DAC4; then a small DAC4 trim.

| Speed | chip 2 r0A | Line period (CH2) | DAC4 slope | options bit 0x10 | r09 / r01 | chip 4 DAC4 |
|---|---|---|---|---|---|---|
| 1 | 1 | 0.207 ms | 13500 | 0 | 288 / 220 | 0 |
| 2 | 3 | 0.372 ms | 6717 | 0 | 288 / 220 | 0 |
| 3 | 7 | 0.703 ms | 3350 | 0 | 272 / 232 | 0 |
| 4 | 15 | 1.405 ms | ~1680 (86x) | 0 | 272 / 232 | 0 |
| 5 | 31 | 2.811 ms | 837 | 0 | 272 / 232 | 0 |
| 6 | 63 | 5.608 ms | 30998 | 1 | 272 / 232 | 1 |
| 7 | 127 | 11.217 ms | 15499 | 1 | 272 / 232 | 1 |
| 8 | 255 | 22.433 ms | 7749 | 1 | 272 / 232 | 1 |
| 9 | 511 | 44.866 ms | 3899 | 1 | 272 / 232 | 1 |

- **r0A = 2^speed - 1** (speeds 1-9). Line period = (r0A + 1) x 87.9 us for speeds 3-9 (1296 clocks of 14.7456 MHz per unit); speeds 1-2 have extra overhead (r09 288 / r01 220 there).
- **Slope DAC4 x (r0A + 1) is constant within a range**: ~27,000 with options bit 0x10 clear (speeds 1-5), ~1,985,000 with it set (speeds 6-9): bit 0x10 switches the X ramp integrator to a ~73x slower range.
- **chip 4 DAC4 = 1 for speeds 6-9 (and spot mode), 0 for speeds 1-5**: probably a video bandwidth / filter select for slow scans.
- Options low bits = magnification range (12 = range 4 here), so options = range | 8 | (0x10 for slow speeds).

| Speed | chip 2 r0A | Line period | DAC4 | options | control / routing | chip 4 DAC4 |
|---|---|---|---|---|---|---|
| 0 (`spd_08`) | 0 | 0.124 ms | 27066 -> 27590 | 12 | 0x8402 / 8, r09 288, r01 220 | 0 |
| 10 (`spd_09`) | 1 | 89.73 ms | not written | **4** | **0x8422 / 4** (hold bit, as spot mode) | 1 |
| 15 (`spd_10`) | 63 | ~2.87 s (est., 1 line not seen) | not written | 4 | 0x8422 / 4 | 1 |
| 5 (`spd_11`) | 31 | 2.804 ms | 862 -> 837 | 12 | 0x8402 / 8 | 0 |

- **Speeds 10-15 use a different X mode**: options bit 3 (8) cleared, routing 4 and control bit 0x20, the same as spot mode, and the slope DAC is not used. Line period = (r0A + 1) x 44.87 ms, i.e. r0A = 2^(speed - 9) - 1, and 44.87 ms / 1024 points = 43.8 us per point step: X is stepped point by point (staircase) by the chip instead of the analogue integrator ramp. With r0A = 1 at speed 10 the unit equals one speed-9 line.
- So routing 8 + options bit 3 = analogue ramp; routing 4 = stepped / held X (spot mode is the same mode with no stepping).

### Magnification sweep (speed 5, WD 15 mm), `spd_12..`
- **10,000x -> 3x** (`spd_12`, UI minimum at WD 15): weights parked at 32767, **options 8 / 248 = range 0** (new), new weights offsets X->A +3642, X->B -2749, Y->B +3422, Y->A +2790, offsets chip 2 DAC2 = 2088, chip 3 DAC0 = 1978.
- Ranges seen so far: 0 (3x), 1 (86x), 3 (1,000x at WD 10), 4 (10,000x). Range 2 not yet seen.

- Sweep `spd_12..23` (WD 15 mm, rotation as set; offsets from 32768; relay clicked entering 30x and 200x):

| Mag | Range (opt 2/3) | X->A | X->B | Y->A | Y->B | |X| | |X| x mag | chip 2 DAC2 / chip 3 DAC0 |
|---|---|---|---|---|---|---|---|---|
| 3x | 0 (8/248) | +3642 | -2749 | +2790 | +3422 | 4563 | 14k | 2088 / 1978 |
| 10x | 0 (8/248) | +3642 | -2749 | +2790 | +3422 | 4563 | 46k | - |
| 30x | 1 (9/249) | +9395 | -7227 | +7251 | +8893 | 11853 | 356k | 2088 / 1958 |
| 86x | 1 (9/249) | +3308 | -2489 | +2531 | +3104 | 4140 | 356k | - |
| 200x | 2 (10/250) | +11545 | -8900 | +8919 | +10939 | 14577 | 2915k | 2141 / 1931 |
| 500x | 2 (10/250) | +4647 | -3531 | +3569 | +4377 | 5836 | 2918k | - |
| 1,000x | 3 (11/251) | +19364 | -14986 | +14982 | +18375 | 24486 | 24486k | 2158 / 2088 |
| 2,000x | 3 (11/251) | +9706 | -7469 | +7492 | +9189 | 12247 | 24494k | - |
| 5,000x | 3 (11/251) | +3910 | -2958 | +2998 | +3677 | 4903 | 24514k | - |
| 10,000x | 4 (12/252) | +13956 | -10775 | +10788 | +13230 | 17632 | 176315k | 2238 / 2301 |
| 20,000x | 4 (12/252) | +7002 | -5363 | +5395 | +6616 | 8820 | 176397k | - |
| 50,000x | 4 (12/252) | +2829 | -2116 | +2160 | +2648 | 3533 | 176640k | - |

- **Within a range, weight magnitude x magnification is constant** (range 1: 356k, range 2: 2.92M, range 3: 24.5M, range 4: 176M). Range-to-range sensitivity steps: 7.7x, 8.2x, 8.4x, 7.2x (~8x each, calibrated per range).
- **Range rule:** the software picks the most sensitive range whose weight magnitude stays under ~32767 (e.g. 10x in range 1 would need 35.6k -> range 0; 5,000x in range 4 would need 35.2k -> range 3).
- **3x is not real:** the 3x weights are identical to 10x. 10x is the true minimum at WD 15 mm; below that the software clamps the deflection and only the displayed number changes.
- Relay clicks only at the 0->1 (30x) and 1->2 (200x) boundaries in this sweep; ranges 2->3->4 switch silently. chip 2 DAC2 / chip 3 DAC0 (centring offsets) are recalibrated per range.

### External scan on / off (10,000x), `spd_24` / `spd_25`
- **On:** centring offsets chip 2 DAC2 and chip 3 DAC0 -> 2048 (neutral, instead of the range-4 calibration 2238 / 2301); read chip 3 options (CH4 reply 252); **chip 3 options 252 -> 244 (bit 3 cleared)**; then the beam-position block. Coil weights unchanged. CH1 ends low.
- **Off:** offsets back to 2238 / 2301; read chip 3 options (reply 244); options back to 252.
- So **chip 3 options bit 3 (8) = internal scan select** (cleared = external scan input; the same bit cleared on chip 2 selects stepped X at speeds 10-15).
- **CH4 read reply format confirmed:** one start bit (0) then the 16-bit register value MSB first, then idle high (3.6864 Mbit/s). Options read returned 0x00FC and 0x00F4, exactly the values last written.

### Freeze modes (10,000x), `spd_26..31`
Pair A = chip 0 DAC4 + chip 1 DAC3, pair B = chip 1 DAC2 + chip 0 DAC5 (both sent inside the beam-position block; chip 1 DAC8 = 0 and chip 1 r1B = 0 always).

| Shot | Action | Pair A | Pair B | Afterwards |
|---|---|---|---|---|
| 26 | freeze on command | 2047 -> **3070** | 2047, then **1024** 1.7 ms later | Y keeps ramping to the end of the frame, then parks at 511 |
| 27 | unfreeze | **2047** | 1024, then **2047** 3 ms later | frame restart pulse on CH1, Y ramp restarts |
| 28 | freeze on line end | 3070 | 2047 -> 1024 | identical to "command" on the link |
| 29 | unfreeze | 2047 | 1024 -> 2047 | as 27 |
| 30 | freeze on frame end | 2047 (no change) | 2047 (no change) | Y keeps ramping; CH2 ends high; the actual freeze presumably comes at frame end, outside the window |
| 31 | unfreeze | 2047 | 1024 -> 2047 | as 27 |

- The levels behave like 3-state control lines (1024 / 2047 / 3070), not analogue settings. Pair A = 3070 marks "frozen (immediate)", pair B = 1024 marks "acquisition stopped"; unfreeze always passes B through 1024 before 2047 (a reset pulse).
- **No beam blanking is visible**: in every mode the Y ramp carries on to the end of the frame, and then Y parks at 511 (top edge). The beam is never moved off-axis or blanked over this link. If the column has a beam blanker, it is driven by something else (no UI control; possibly a macro).
- "Command" and "line end" are identical on the link, so the line-end timing must be handled on the board or by the IP's timing, not by a different message.

### Rotation at 10,000x (range 4), `spd_32..35`
- 0 deg (and rotation off) weights: X (A, B) = (+13956, -10775), Y (A, B) = (+10788, +13230).
- 90 deg: X (A, B) = (-10737, -13179) = -Y(0 deg); Y (A, B) = (+13911, -10820) = X(0 deg). A clean 90 deg rotation of the same matrix, as at 86x: rotation is applied identically in every range.
- Stigmator X+ did not trigger the burst-only loop (single write), as expected. Loop restarted as `kv` with the single-frame trigger.

### Stigmator X at 10,000x, `kv_01` (X+) / `kv_02` (X-)
- X+: chip 0 DAC6 = 2564, DAC7 = 1024 (Y unchanged since the 86x test). X-: DAC6 = 2497. **X step = 67 counts at 10,000x, X+ = higher code** (normal polarity; Y is inverted). At 86x the Y step was 512: the stigmator step scales with magnification like the other controls.
- X before these clicks was not 2231 (the 86x value) + 67, so the stored stigmator value was also changed somewhere in between (magnification changes or Optibeam / aperture); not captured.

### EHT change 20 -> 10 kV (beam off, no vacuum)
- **Nothing on CH3.** The lens / scan compensation for kV is not sent while the beam is off; it presumably follows the EHT readback once the beam is on. Retest under vacuum with the beam running (and log the EHT link at the same time).

### Probe current (under vacuum, imaging, Optibeam on, speed 5), `beam_01..04`
Each change: read-modify-write of chip 0 DAC0-3 (condenser), the four coil weights, then chip 1 DAC1 / DAC0 (objective). Final values per shot:

| Probe current | chip 0 DAC0 / DAC1 | chip 0 DAC2 / DAC3 | chip 1 DAC0 / DAC1 (objective) | X->A / X->B / Y->B / Y->A |
|---|---|---|---|---|
| 500 pA | 938 / 21 | 252 / 140 | 382 / 2256 | 52051 / 25218 / 51259 / 40093 |
| 1000 pA | 827 / 155 | 250 / 4 | 383 / 2095 | 52054 / 25206 / 51261 / 40106 |
| 50 pA | 1111 / 137 | 317 / 33 | 380 / 2244 | 52037 / 25288 / 51248 / 40022 |
| 300 pA | 1035 / 88 | 254 / 204 | 382 / 2188 | 52052 / 25227 / 51259 / 40085 |

- chip 0 DAC0 falls monotonically with increasing probe current (1111 -> 1035 -> 938 -> 827 for 50 -> 300 -> 500 -> 1000 pA): a weaker first condenser for more current. DAC0/DAC1 and DAC2/DAC3 look like two coarse/fine pairs [I].
- The objective is re-focused for each current (fine 2095-2256, coarse ~381), and the weights follow by a few tens of counts.

### Unexpected event ("EHT tripped?"), `beam_05`
- Beam-position block, then large weight change (52051 -> 55095 etc.), condenser 48 / 23 / 22 / 214, **range change to 2 (options 10 / 250)** with new centring offsets 2141 / 1931, and **objective coarse 382 -> 34**, fine 2269.
- The big objective drop suggests the software recomputed all lenses for a much lower measured kV (EHT readback collapsed) [I]. To be checked against the EHT tests.

### EHT changes (under vacuum, imaging), `beam_06..10`
Each EHT change produces, ~20-40 ms after the first frame: beam-position block (x2), condenser read-modify-write (chip 0 DAC0-3), coil weights, objective (chip 1 DAC1 / DAC0, twice), then weights repeated 2-3 times. This is the same "lens recompute" block as probe current / aperture, triggered by the new kV.

| Shot | UI action | Condenser DAC0-3 | Objective coarse / fine | Range | X->A offset | Notes |
|---|---|---|---|---|---|---|
| 06 | 10 kV | 1278 / 250 / 409 / 107 | 550 / 2240 | 2 | +27320 | still range 2 from the "trip" event |
| 07 | 20 kV | 1393 / 67 / 687 / 170 | 790 / 2146 | **0** (park, options 8 / 248, ~50 ms, new weights, offsets 2088 / 1978) | +5039 | relay click |
| 08 | 21 kV | 1403 / 119 / 714 / 52 | 810 / 2234 | 0 | +5139 | |
| 09 | 25 kV | 1397 / 68 / 823 / 7 | 887 / 2262 | 0 | +5613 | |
| 10 | 5 kV (two-step) | 1396 / 218 / 686 / 131 | 790 / 2151 | 0 | +5014 | **identical to the 20 kV state**: the first step (25 -> 20 kV) was caught; the 5 kV recompute came during the ~17 s download and was missed |

- **Objective coarse scales as sqrt(kV)** (relativistically corrected): 550 / 790 / 810 / 887 = 0.696 / 1 / 1.025 / 1.123 vs predicted 0.704 / 1 / 1.025 / 1.121.
- **Coil weights scale as sqrt(kV)** too: 20 -> 21 -> 25 kV gives 1 / 1.020 / 1.114 (predicted 1.025 / 1.121; the remaining difference is the WD / focus coupling).
- The software recomputes optics from the EHT setpoint / readback, not from anything on this link. The 10 kV state (shot 06) was inherited from the odd "trip" event (range 2 with large weights) and is not trusted.
- The 25 -> 5 kV change goes in two steps (via 20 kV, relay click in the EHT supply) [I].

### EHT repeat, 30 s between steps, `beam_11..13`
| Shot | kV | Condenser DAC0-3 | Objective coarse / fine | Range (options) | X->A / X->B offsets |
|---|---|---|---|---|---|
| 11 | 20 | 1390 / 203 / 688 / 115 | 790 / 2165 | 0 (8) | +5015 / -1899 |
| 12 | 10 | 1283 / 0 / 408 / 187 | 550 / 2263 | **1 (9)** | +27328 / -10685 |
| 13 | 5 | 1033 / 70 / 255 / 11 | 382 / 2219 | 1 | +19297 / -7551 |

- **Coil weights follow sqrt(relativistic kV) exactly, including across the range switch.** Expressed in range-1 counts (range 0 = 7.74x range 1): 20 kV = 5015 x 7.74 = 38,800 (> 32767, so range 0 is needed); 10 kV predicted 38,800 x 0.7037 = 27,300 (measured 27,328); 5 kV predicted 38,800 x 0.4964 = 19,260 (measured 19,297).
- **The relay clicks at 20 kV and 10 kV are the scan-coil range relay** (range 0 <-> 1), switched because the required deflection crosses the 32767 limit; they are not in the EHT supply.
- Objective coarse 382 / 550 / 790 / 810 / 887 for 5 / 10 / 20 / 21 / 25 kV = 0.484 / 0.696 / 1 / 1.025 / 1.123, against sqrt(kV) 0.496 / 0.704 / 1 / 1.025 / 1.121 (fine DAC takes up the difference).
- The earlier `beam_06` (10 kV) weights (+27320) match this 10 kV value, so that shot was valid after all; its range write was simply not in the window.
- The lens update follows the kV ramp over a couple of seconds (the user saw the image brighten / blur and recover).

### Optibeam modes and split scan (imaging, 20 kV), `beam_14..19`
Each Optibeam mode change sends the usual lens recompute block (condenser read-modify-write, coil weights, objective).

| Shot | Action | Condenser DAC0 / 1 / 2 / 3 | Objective coarse / fine |
|---|---|---|---|
| 13 (before) | 5 kV state | 1033 / 70 / 255 / 11 | 382 / 2219 |
| 14 | **Depth mode on** | **205** / 229 / **1116** / 137 | 378 / 2179 |
| 15 | Depth mode off | 1039 / 174 / 254 / 77 | 382 / 2223 |
| 16 | **Auto resolution on** | 1112 / 80 / 299 / 183 | 381 / 2115 |
| 17 | Auto resolution off | same values re-sent | same |

- Depth mode swaps the condenser strengths (DAC0 ~1035 -> 205, DAC2 ~254 -> 1116): a different crossover / convergence angle for more depth of field. Auto resolution is a smaller condenser change. All are host-side Optibeam calculations; only the four condenser DACs and the objective change.

- **Split scan on** (`beam_18`): beam-position block, then the ramp set-up with **X r08 = 512, r01 = 116** but **X r00 = 1023** (full-frame start) and **Y unchanged (768 lines, r00 511)**; speed block with chip 2 DAC1 = 1116. Line period 2.811 -> 1.736 ms (as reduced area), Y steps +84 per line over the full height. So the X line has half the points at the same pitch while Y covers the full frame [I: probably half the field width for each half of the split display].
- `beam_19` has no new writes: a false trigger, because the 1.736 ms line period is shorter than the 2.75 ms single-frame trigger limit. Loop stopped.

### Other checks (imaging), `beam2_*`
- Gun shift / tilt and the objective aperture are **fully manual** on this microscope: nothing on the link.
- **Brightness / contrast: no traffic on F3** (confirmed with the single-frame trigger). Detector gain/offset is handled elsewhere (PM voltage on the EHT link, or the IP board).
- "Dual magnification" = split scan with two magnifications; captured but not analysed (ignore `beam2_*` shots from that test).
- The never-written DACs (chip 0 DAC8/9, chip 1 DAC4-7/DAC9) are most likely outputs for options that are not fitted (with the EBBU beam blanker).

### Auto-stigmation (runs autofocus, then auto-stig; several seconds), `beam2_08` (first 400 ms only)
- Beam-position block, then a **small central window**: X r00 = 24831, r08 1024 -> **256**, r01 58; Y r00 = 27391, r08 768 -> **128**, r01 84 (about 24 % x 16 % of the field, centred), X start offset chip 2 DAC1 ~1580-1600.
- **Fast scan**: speed 2 settings (r0A 3, DAC4 6700 / 6750, r09 288, r01 54); Y written every ~0.17 ms; the Y sequence is interleaved (alternating jumps of ~10-21k between +84 steps), not a simple ramp [not analysed further].
- Magnification change to range 0 (weights parked, options 8 / 248, new weights 42688 / 28918 / 42260 / 36527, offsets 2088 / 1978), objective 382 / 2227.
- **Stigmator sweep**: chip 0 DAC6 / DAC7 = 2497 / 1024 -> 1065 / 1433 -> 3931 / 1433 -> 2497 / 0 within ~250 ms: large steps across the range, evaluated on the small fast window.
- Only the first 0.4 s of a multi-second algorithm was captured (17 s dead time per shot). Low value for a replacement, which would implement its own image-based autofocus / autostig.

### Frame averaging on (N = 3), `beam2_09`
- Only one register write: **chip 3 r0A = 0**, and the very next Y write restarts at the top (7987 -> 595 = r00 511 + 84). No change to speed, window, weights or lenses.
- So **writing chip 3 r0A = 0 restarts the frame** (it appears at the end of every speed / mode block, which is why those restart the frame).
- So frame averaging is done in the IP board's frame store; the EO board just keeps scanning. Image capture is fixed at 1024 x 768 in the old system.

### Frame averaging off / line averaging N = 2 / frame integration, `beam2_10..12`
- Frame averaging off (`beam2_10`): chip 3 r0A = 0 (frame restart) only.
- **Line averaging N = 2** (`beam2_11`): **chip 3 r0A = 1**, frame restart, then **every Y position is written twice on consecutive lines** (dY = 0, +84 alternating): each line is scanned N times. Beam-position block re-sent ~190 ms later.
- Frame integration (`beam2_12`): chip 3 r0A = 0 + frame restart (line averaging back to 1); the integration itself is in the frame store.
- So **chip 3 r0A = lines per Y step - 1** (line repeat count), and writing it restarts the frame. (chip 2 r0A, by contrast, is the X clock divider.)

## EO board hardware ("CONDENSED EO CONTROL"), from the user's photos 2026-11-13
Connectors: left = fiber inputs, EXT SCAN EN / scan out / SCAN IN / FRAME (analog), X/Y scan power, "GUN ALIGN PWR" (top left). Right, bottom to top: C1, C2, C3, Stig cables.

| Part | Qty (visible) | Function | Likely registers [I] |
|---|---|---|---|
| 84-pin PLCC ASIC "6428 207" (identical, date 9523) | **5** (IC23, IC38, C118 area, C150 area, IC77) | Register-mapped ramp / control chips | **chips 0-4** (four identical ramp generators + one more of the same part) |
| AD7846JN, 16-bit voltage-output DAC with reference inputs (multiplying) | **6** | 16-bit outputs | the six 16-bit values: X slope / X position (chip 2 DAC4), Y position (chip 3 DAC4), four coil weights (chip 2 DAC5/6, chip 3 DAC5/6). The weights are probably multiplying DACs with the X / Y ramps on their reference inputs (ramp x weight = coil drive) |
| AD664KN-UNI, quad 12-bit DAC | **5** (= 20 channels) | 12-bit lens / offset outputs | condenser (chip 0 DAC0-3 -> C1, C2), objective (chip 1 DAC0/1 -> C3?), stigmators (chip 0 DAC6/7 -> Stig), shift, centring, X start, pairs A / B, constants |
| PMI DAC8408FP, quad 8-bit multiplying DAC | **2** (= 8 channels) | 8-bit outputs | **chip 1 DAC4-7 (boot value 128 = 8-bit mid-scale)** -> plausibly electronic **gun alignment** (shift X/Y, tilt X/Y) for the "GUN ALIGN PWR" connector, unused because gun alignment is manual on this microscope |
| Relays (right side, several) | ~4 | Scan-coil range switching | ranges 0 / 1 / 2 (audible clicks) |
| Toroids + power transistors TR9 / TR11 / TR23 (right side) | 3 | Output stages / filters for the C1 / C2 / C3 or coil cables | |
| PALCE22V10 (IC33), line receivers, REF01-type references, LF353 op-amps, analog switches | | Fiber decode glue, references, analog | |

### Rotation / coefficients vs EHT (from `beam_06..13`)
| kV | Range | X angle (atan2(B, A)) | Y angle | Y - X | \|X\| (range-1 units) | Y/X magnitude |
|---|---|---|---|---|---|---|
| 5 | 1 | -21.37 deg | 68.40 | 89.77 | 20722 | 0.960 |
| 10 | 1 | -21.36 | 68.47 | 89.83 | 29343 | 0.961 |
| 20 | 0 | -20.74 | 68.54 | 89.28 | 41506 | 0.957 |
| 21 | 0 | -20.74 | 68.55 | 89.29 | 42532 | 0.957 |
| 25 | 0 | -20.78 | 68.58 | 89.36 | 46468 | 0.958 |
- **kV does not change the scan rotation.** Within a range the angle is constant to 0.05 deg from 5 to 10 kV and from 20 to 25 kV. The 0.6 deg step and the slightly different X-Y orthogonality (89.3 vs 89.8 deg) and Y/X gain (0.957 vs 0.961) come with the **range change**, i.e. per-range calibration of the coil channels, not kV.
- Physically consistent: the objective excitation is scaled by sqrt(kV), so NI / sqrt(V), and with it the magnetic-lens image rotation, stays constant; no rotation correction is needed for kV at fixed WD.
- Only the magnitudes scale, as sqrt(relativistic kV) (21 / 20 kV: 1.0247 measured vs 1.0252; 25 / 20: 1.1196 vs 1.1207; 10 / 20: 0.7070 vs 0.7037 and 5 / 20: 0.4993 vs 0.4964 after the range-0 / range-1 factor 7.74, which is itself a ~0.5 % estimate).

## Image-artifact check, speed 4 (`artifact_speed4_fast`, 25 MS/s 0.4 s; `artifact_speed4_long`, 1 MS/s 10 s)
- Register traffic normal: only the per-line Y write (+84), 24.8 +- 0.6 us after each F2 rise; no stray frames, no CH4 traffic.
- Frame period 1.259184 s (constant to 1 us), F1 flyback 0.18 s.
- **Line period is not constant:** F2 rising edges are 1405.30 us apart, except that **one line in every ~29.3 is longer by 1.08 us = exactly one pixel time at speed 4** (16 / 14.7456 MHz). Pattern: lines 2, 31, 60, 90, 119, ... (spacing 29, 29, 30, 29 ...).
- Same at speed 5 in earlier captures: one line in every 29 is longer by 2.16 us = one speed-5 pixel (`beam2_10`, `t1`). Not seen at speeds 2 or 7 (few lines / short captures).
- Interpretation [I]: the IP board's line timing slips one pixel against its reference every ~29 lines (~26 ppm clock mismatch, e.g. IP pixel clock vs the EO board's 14.7456 MHz). If the X ramp and the image sampling are not slipped together, image lines would be misregistered horizontally by up to one pixel in a ~29-line sawtooth.
- Mains-hum alternative (line rate 711.57 Hz at speed 4, not locked to mains): 60 Hz bands every 11.9 lines at speed 4, 5.9 at speed 5, 23.7 at speed 3; 50 Hz: 14.2 / 7.1 / 28.5.
- **Resolved (user, 2026-11-13): the image artifact was 60 Hz mains interference on the PMT signal line**, not the EO link. The one-pixel line stretch every ~29 lines is real but was not the cause.
