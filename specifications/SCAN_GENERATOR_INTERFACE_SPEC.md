# LEO 438VP Scan Generator / Electron-Optics (EO) Board: Fiber Interface Specification

| | |
|---|---|
| Subsystem | Scan generator / electron-optics ("EO") board: X and Y scan, scan-coil amplitude / range / rotation / shift, objective and condenser lens DACs, stigmators, focus wobble, frame and line gating |
| Host in the original system | ISA image-processor (IP) board. Its ADSP-21xx DSP drives a "remote register bus" (DM 0x3400 + n, busy flag at DM 0x37FF; target 0x40 = EO, 0x20 = HRRU) that is serialised onto the fibers |
| Revision | **1.1**, 2026-11-13 (1.0 same day: beam-off tests; 0.9 2026-11-12) |
| Basis | MSO24 captures of all four fibers while operating every LEO-32 scan and lens control, beam off and beam on under vacuum (probe current, EHT, Optibeam modes), including a cold boot; photos of the EO board; the static EO register map from the drive image. Test log: `scope_tools/SCAN_FIBER_NOTES.md` |

Confidence markers: **[C]** confirmed by capture, **[F]** from the original firmware / software (static analysis), **[I]** inferred, needs verification.

---

## 1. Overview

The EO board holds **five register-mapped chips** (chip 0–4) **[F][C]**. Chips 0–3 are the same ramp-generator part, each with:
- ramp parameters r00–r0A (start, steps, counts, clock divider);
- control (r0B, bit 15 = run), routing (r0C) and options (r0D);
- ten DACs (DAC0–DAC9 = r10–r19), plus r1A / r1B.

| Chip | Role **[C]** |
|---|---|
| 0 | Condenser lenses (DAC0–3, set by Optibeam), stigmator X / Y (DAC6 / DAC7), freeze/acquisition control levels (DAC4 / DAC5) |
| 1 | Objective lens coarse / fine (DAC0 / DAC1); its ramp generator makes the **focus wobble**; freeze/acquisition levels (DAC2 / DAC3) |
| 2 | **X scan**: line ramp generator, X coil weights (DAC5 / DAC6), coil-A beam shift (DAC3), X start offset (DAC1), centring offset (DAC2) |
| 3 | **Y scan**: Y position (DAC4, written by the host every line), Y coil weights (DAC5 / DAC6), coil-B beam shift (DAC1), centring offset (DAC0) |
| 4 | Mode latch: configured once at boot; DAC4 = 1 for slow scan (speeds ≥ 6), spot mode and stepped X, 0 otherwise |

The host programs the chips over one fiber and receives read replies on another. Two more fibers carry gating signals from the IP board. The X ramp runs in hardware; the **Y position is written by the host once per line**. Magnification, rotation, shift, tilt correction and WD compensation are all done in the host by computing DAC values. Dynamic focus is also done in the host (one extra objective write per line). Focus wobble runs in hardware (chip 1 ramp). **[C]**

The fibers carry **no image data**; the detector video goes to the IP board on a separate analog coax. **[C]**

### 1.1 Board hardware ("CONDENSED EO CONTROL", from photos) **[C]** parts, **[I]** assignments

| Part | Qty | Function | Register mapping |
|---|---|---|---|
| 84-pin PLCC ASIC "6428 207" | 5 | register-mapped ramp / control chips | chips 0–4 |
| AD7846JN 16-bit DAC (reference inputs usable as multiplier) | 6 | 16-bit outputs | X slope / X position (2.DAC4), Y position (3.DAC4), four coil weights (2.DAC5/6, 3.DAC5/6). The weights are most likely **multiplying DACs with the X / Y ramp on their reference inputs** (coil drive = ramp × weight) |
| AD664KN-UNI quad 12-bit DAC | 5 (20 ch) | lens and offset outputs | condenser (0.DAC0–3), objective (1.DAC0/1), stigmators (0.DAC6/7), shift, centring, X start, pairs A / B, constants |
| PMI DAC8408 quad 8-bit multiplying DAC | 2 (8 ch) | 8-bit outputs | 1.DAC4–7 (boot value 128 = 8-bit mid-scale): probably electronic **gun alignment** for the "GUN ALIGN PWR" connector; unused (gun alignment is manual here) |
| Relays (right side; Omron G6E on the "SCAN DRIVE" daughterboard) | ~5 | scan-coil range switching, internal / external scan | ranges 0–2 (audible), external-scan routing |
| DG411 / DG211 analog switches, LF353 / OP15 op-amps, PALCE22V10, 74HC04 / 74HCT20 | | ramp / external-scan selection, fiber decode glue | |
| Toroid + power transistor stages (TR9, TR11, TR23) | 3 | lens current drivers | C1, C2, C3 cables |

**Connectors.** Left: fiber inputs, EXT SCAN EN (with optocoupler OPT1), scan out, SCAN IN (external X / Y, ±10 V), FRAME, X / Y scan power, GUN ALIGN PWR. Right (bottom to top): **C1, C2, C3, Stig**. Best estimate: **C1 / C2 = the two condenser lenses** (chip 0 DAC0/1 and DAC2/3, pairing not yet determined), **C3 = objective (final lens)** (chip 1 DAC0/1), **Stig** = stigmator octupole (chip 0 DAC6/7). Confirm with a current probe while focusing / changing probe current.

**External scan path [I].** There is no ADC on the board and no extra traffic in external mode; the software only flips the select bit and neutralises the centring offsets, and leaves the coil weights in place. The external ±10 V X / Y signals are therefore most likely switched (DG411 / relay) in place of the internal ramps **ahead of the multiplying coil-weight DACs**, so magnification, rotation, tilt and kV scaling still apply to them. Test: ±10 V triangle on X in external mode, check that the field scales with magnification and rotates with scan rotation.

**Coil notation.** "A" and "B" are the two physical deflection channels driven by the board (A = DAC6, B = DAC5 of chips 2 / 3). The image axes are at ~45° to them. Which connector pins carry A and B is still to be traced.

## 2. Physical layer

| Fiber | Direction | Content | |
|---|---|---|---|
| F1 (scope CH1) | IP → EO | **Frame gate**: high during frame flyback / not acquiring | **[C]** (meaning **[I]**) |
| F2 (scope CH2) | IP → EO | **Line gate**: 550 µs high at the start of each line | **[C]** (meaning **[I]**) |
| F3 (scope CH3) | IP → EO | **Register frames** (§3) | **[C]** |
| F4 (scope CH4) | EO → IP | **Read replies** (§3.1) | **[C]** |

- TTL at the transceivers, **idle high** (light on = high), measured at the receiver outputs with 10x probes. F2's low level reads ~2.0 V (receiver / probe property); use a ~3 V threshold for F2. **[C]**
- Transceiver part numbers and wavelength: to be recorded from the board.

### 2.1 F1 / F2 gating **[C]**

| Signal | Behaviour |
|---|---|
| F2 line gate | High 550 µs per line, period = line time (§5.1). Present during flyback and freeze. Held **high** (no pulses) in line-scan mode, spot mode and while the scan is stopped |
| F1 frame gate | High ~360 ms at the end of each frame (speed 5). Pulse of 2.76 ms (full frame) or 1.52 ms (reduced area) when the host restarts a frame. Held high in line-scan mode |
| Register timing | The per-line Y write starts ~27 µs after the F2 rising edge |

The scan keeps running at the right rhythm with F1 and F2 both held high (line scan), so they are **not** the ramp timing source. They behave like frame-valid / line-valid gates for acquisition. **[I]**

## 3. Register frame format (F3) **[C]**

NRZ, **3.6864 Mbit/s** (bit time 0.27127 µs = 4 / 14.7456 MHz), MSB first, no start / stop bits, idle high.

```
 bit: 31 | 30 | 29 ............ 18 | 17 ................ 2 | 1  0
      0  | R  |  register n (12)   |   value (16 bits)     | 1  1
```

| Field | Meaning |
|---|---|
| b31 | always 0; its falling edge starts the frame (resync on the first falling edge after ≥ 20 bit-times idle) |
| b30 (R) | 1 = **read request** (reply on F4), 0 = write |
| b29–b18 | register `n`: **chip = n >> 5**, **reg = n & 31** |
| b17–b2 | 16-bit value |
| b1–b0 | always `11` |

- Frame = 32 bits (8.68 µs). In bursts frames are ~22–23 µs apart, start to start. Lens read-modify-write sequences use ~0.94 ms spacing.
- Many writes are repeated (coil weights ×4, X shift ×4, slope trim ×4); the repeats are identical.
- Bipolar DACs (coil weights, Y position, X slope / position) are 16-bit offset binary: **32768 = zero**; "park" = 32767. Most other DACs are 12-bit (0–4095, 2047/2048 = centre).
- 16-bit word view used by `decode_scan_fiber.py`: `A` = bits 31–16, `D` = bits 15–0, `n = (A & 0x3FFF) >> 2`, `value = ((A & 3) << 14) | (D >> 2)`.

### 3.1 Read replies (F4) **[C]**
About 5 µs after a read request the EO board sends **one start bit (0), then the 16-bit register value MSB first**, then idle high, at the same bit rate. Verified: options reads returned 0x00FC and 0x00F4, exactly the last values written. Control reads return 0; routing reads 4 or 5. The host reads control and routing of chip 0 or 1 before every lens write (read-modify-write), chip 2 control before reprogramming the X ramp, chip 3 options before external-scan changes, and chip 1 DAC0 / DAC1 when dynamic focus starts.

## 4. Register map **[C]** unless marked

| Chip.reg | Name | Meaning / values |
|---|---|---|
| 0.DAC0–DAC3 | Condenser | Computed by Optibeam from aperture, WD, magnification (e.g. 45 / 182 / 23 / 218 at 50 µm, 49 / 128 / 21 / 251 at 30 µm) |
| 0.DAC4, 1.DAC3 | "Pair A" | 2047 running, **3070 frozen** (freeze on command / line end) |
| 0.DAC5, 1.DAC2 | "Pair B" | 2047 running, **1024 acquisition stopped**; unfreeze passes 1024 → 2047 |
| 0.DAC6 / DAC7 | Stigmator X / Y | 12-bit, centre ~2048. Step per click scales with magnification (Y 512 at 86×, X 67 at 10,000×). Y polarity inverted (UI + = lower code). Both always sent together |
| 0.DAC8 / DAC9 | — | 2048 at boot, never seen changing |
| 1.DAC0 / DAC1 | Objective coarse / fine | e.g. 62 / 2234. Focus (Optibeam: WD knob) changes DAC1 |
| 1.r00–r0A, routing, control | Wobble generator | §5.9 |
| 1.DAC4–DAC7 | — | 128 at boot, never seen changing |
| 1.DAC8, 1.r1B | — | Always 0 (sent in the beam-position block) |
| 2.r00 | X start position | 16-bit; 1023 full frame, 16895 reduced area |
| 2.r01, r09 | X line overhead | 232 / 272 (speeds 3–9), 220 / 288 (speeds 0–2); r01 halves in reduced area |
| 2.r02 | X step | 62 |
| 2.r07 | | 1024 |
| 2.r08 | X points per line | 1024 full, 512 reduced |
| 2.r0A | Line clock divider | §5.1 |
| 2.control | | 0 = stop, **0x8402** = run (analog ramp), **0x8422** = run with hold / stepped X (bit 5) |
| 2.routing | | **8** analog ramp, **4** stepped / held X |
| 2.options | | bits 2–0 = magnification range; bit 3 (8) = analog ramp enable; bit 4 (0x10) = slow-slope range |
| 2.DAC0 | | 4095 |
| 2.DAC1 | X start offset | ~110 full frame, ~1088 reduced area, 41 spot; small trims between repeats |
| 2.DAC2 | X centring offset | per magnification range (2088 / 2088 / 2141 / 2158 / 2238 for ranges 0–4); 2048 with external scan |
| 2.DAC3 | Beam shift, coil A | 12-bit, 2047 = 0 |
| 2.DAC4 | X slope / X position | Ramp slope while scanning (§5.1); **X position** in spot mode |
| 2.DAC5 / DAC6 | X → coil B / coil A | Coil weights (§5.3) |
| 3.r00 | Y start position | 511 full frame, 16639 reduced area, line position in line scan (e.g. 16219) |
| 3.r01 / r08 | Y lines | 504 / 768 full, 252 / 384 reduced, 6 / 10 line scan |
| 3.r02 | Y step per line | 84 |
| 3.r09 | | 128 |
| 3.r0A | Line repeat / frame restart | N − 1 for line averaging (0 normally); every write restarts the frame from r00 |
| 3.options | | bits 2–0 = range (base 248); bit 3 (8) = internal scan (cleared = external scan) |
| 3.DAC0 | Y centring offset | per range (1978 / 1958 / 1931 / 2088 / 2301); 2048 with external scan |
| 3.DAC1 | Beam shift, coil B | 12-bit, 2047 = 0 |
| 3.DAC2 / DAC3 | | 3006 / 565 |
| 3.DAC4 | **Y position** | Written once per line by the host; Y spot position in spot mode; parked at 511 |
| 3.DAC5 / DAC6 | Y → coil B / coil A | Coil weights (§5.3) |
| 4.DAC4 | Slow / hold mode | 1 for speeds 6–15 and spot mode, 0 for speeds 0–5. Possibly a video filter select **[I]** |
| 4.r01, r02 / r08, r09 / control | | 1 / 255 / 0x8403, set once at boot |

## 5. Functions

### 5.1 Scan speed **[C]**
Each change: chip 2 control = 0, options, routing, DAC4 (slope), r0A, control (run), r09, r01, r07, chip 3 r0A = 0, chip 4 DAC4, then a small DAC4 trim. Typically sent three times.

| Speed | chip 2 r0A | Line period | DAC4 (slope) | options bit 4 | X mode | chip 4 DAC4 |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.124 ms | 27066 | 0 | analog | 0 |
| 1 | 1 | 0.207 ms | 13500 | 0 | analog | 0 |
| 2 | 3 | 0.372 ms | 6717 | 0 | analog | 0 |
| 3 | 7 | 0.703 ms | 3350 | 0 | analog | 0 |
| 4 | 15 | 1.405 ms | ~1680 | 0 | analog | 0 |
| 5 | 31 | 2.811 ms | 837 | 0 | analog | 0 |
| 6 | 63 | 5.608 ms | 30998 | 1 | analog | 1 |
| 7 | 127 | 11.22 ms | 15499 | 1 | analog | 1 |
| 8 | 255 | 22.43 ms | 7749 | 1 | analog | 1 |
| 9 | 511 | 44.87 ms | 3899 | 1 | analog | 1 |
| 10 | 1 | 89.73 ms | — | — | **stepped** | 1 |
| 15 | 63 | ~2.87 s | — | — | **stepped** | 1 |

- Analog speeds 0–9: **r0A = 2^speed − 1**; line time = (r0A + 1) × 87.9 µs (1296 clocks of 14.7456 MHz) for speeds 3–9, with extra overhead at speeds 0–2.
- **Slope × (r0A + 1) is constant per slope range**: ~27,000 (bit 4 clear), ~1,985,000 (bit 4 set; ~73× slower integrator).
- Stepped speeds 10–15: options = range only (bit 3 cleared), routing 4, control 0x8422; r0A = 2^(speed − 9) − 1; line time = (r0A + 1) × 44.87 ms, i.e. 1024 points of ~43.8 µs × (r0A + 1). The slope DAC is not used.

### 5.2 Frame / Y scan **[C]**
- The host writes chip 3 DAC4 = Y once per line, from r00 upward by r02 (84) per line: 780 lines × 2.81 ms + 0.36 s flyback ≈ 2.55 s per frame at speed 5.
- End of frame: Y parked at 511, F1 high ~360 ms, Y = 511 still written every line.
- The Y step does not change with magnification; amplitude is in the coil weights.

### 5.3 Magnification **[C]**
Four bipolar coil weights (scan coils at 45° to the image axes) plus a range field in options bits 2–0 of chips 2 and 3:

| Weight | Register |
|---|---|
| X → coil A / B | chip 2 DAC6 / DAC5 |
| Y → coil A / B | chip 3 DAC6 / DAC5 |

Sweep at WD 15 mm (offsets from 32768, rotation 0):

| Mag | Range | chip 2 / 3 options | X→A | X→B | Y→A | Y→B | \|X\| × mag |
|---|---|---|---|---|---|---|---|
| 10× | 0 | 8 / 248 | +3642 | −2749 | +2790 | +3422 | 46k |
| 30× | 1 | 9 / 249 | +9395 | −7227 | +7251 | +8893 | 356k |
| 86× | 1 | | +3308 | −2489 | +2531 | +3104 | 356k |
| 200× | 2 | 10 / 250 | +11545 | −8900 | +8919 | +10939 | 2.92M |
| 500× | 2 | | +4647 | −3531 | +3569 | +4377 | 2.92M |
| 1,000× | 3 | 11 / 251 | +19364 | −14986 | +14982 | +18375 | 24.5M |
| 2,000× | 3 | | +9706 | −7469 | +7492 | +9189 | 24.5M |
| 5,000× | 3 | | +3910 | −2958 | +2998 | +3677 | 24.6M |
| 10,000× | 4 | 12 / 252 | +13956 | −10775 | +10788 | +13230 | 176M |
| 20,000× | 4 | | +7002 | −5363 | +5395 | +6616 | 176M |
| 50,000× | 4 | | +2829 | −2116 | +2160 | +2648 | 177M |

- **Within a range, weight magnitude × magnification is constant**; ranges differ by ~8× (7.7, 8.2, 8.4, 7.2: per-range calibration).
- **Range rule:** the most sensitive range whose weight magnitude stays below ~32767.
- A relay clicks entering range 1 (30×) and range 2 (200×); 2 → 3 → 4 switch silently.
- The UI offers 3× at WD 15 mm, but the weights are identical to 10×: below the true minimum the deflection is clamped.
- Centring offsets chip 2 DAC2 / chip 3 DAC0 are rewritten per range.

**Magnification-change sequence:**
1. Park all four weights at 32767.
2. ~1 ms later: chip 2 options, chip 3 options (range; relay).
3. **Wait ~40–46 ms.**
4. New weights (same order and repetition).
5. Chip 2 DAC2 and chip 3 DAC0 (centring offsets).
6. Restart the frame (F1 pulse, Y from the top).
7. Then Optibeam's lens update (chip 0 condenser, objective) and, if wobble is on, the wobble reprogram.

Within a range only step 4 is sent.

**EHT (kV) compensation [C]:** on every kV change (after the EHT has ramped) the host recomputes the condenser, the objective and the coil weights. Weight magnitudes and objective coarse scale as **√(V·(1 + 0.978×10⁻³·V))** (V in kV): 21 / 20 kV 1.0247 vs 1.0252 predicted, 25 / 20 kV 1.1196 vs 1.1207; objective coarse 382 / 550 / 790 / 810 / 887 at 5 / 10 / 20 / 21 / 25 kV. The range is re-chosen by the same rule, so a kV change can click the range relay (20 kV → range 0, 10 kV → range 1 at the magnification used). **The angles do not change with kV** (constant to 0.05° within a range); rotation is unaffected because the objective excitation scales with √V.

### 5.4 Rotation, tilt correction **[C]**

```
X → coil A = 32768 + M·gA·cos(θ + 45°)              X → coil B = 32768 − M·gB·sin(θ + 45°)
Y → coil A = 32768 + T·M·gA·sin(θ + 45°)            Y → coil B = 32768 + T·M·gB·cos(θ + 45°)
```

- θ = scan rotation + WD lens-rotation compensation; M = range calibration × √kV(rel.) / magnification; gA ≈ 1.04 gB (per-coil calibration); T = cos(tilt).
- **Per-range calibration [C]:** each range has its own gain (range steps 7.7 / 8.2 / 8.4 / 7.2×), a small angle trim (~0.6° between ranges 0 and 1), X–Y orthogonality (89.3° vs 89.8°) and Y/X gain (0.957 vs 0.961).
- Verified at 86× (0°, 45°, 90°) and at 10,000× (0°, 90°): at 90° new X = −old Y, new Y = old X.
- **Tilt correction:** only the Y weights change, both × cos(tilt) (0.866 at 30°, measured 0.8660 / 0.8661). Off restores them exactly.

### 5.5 Beam shift **[C]**
- chip 2 DAC3 = coil-A shift, chip 3 DAC1 = coil-B shift (12-bit, 2047 = 0).
- Shift is rotated by the same angle as the scan: at 86× X+ = (−11, +8), Y+ = (+7, +9) counts per click. UI X+ is opposite to scan +X; Y+ is along scan +Y.
- Sent inside the **beam-position block**: chip 1 DAC8 = 0, pair A, chip 1 r1B = 0, pair B, chip 2 DAC3 ×4, chip 3 DAC1, then the four coil weights.

### 5.6 Focus, working distance, Optibeam, aperture **[C]**
- All lens writes are read-modify-write: read chip control + routing (F4), then write the DACs ~0.94 ms apart.
- **Focus** (with Optibeam on, the WD knob): chip 1 DAC1 (objective fine) changes (2230 → 2234 per fine click at 86×), then the four coil weights are recomputed (scan amplitude and rotation follow the objective). The lens + weights block repeats every ~110 ms for a short while after a change.
- **WD typed in / login:** chip 0 DAC0–3 and chip 1 DAC0–1 are rewritten (several intermediate steps), weights recomputed (e.g. 10 → 15 mm: −23 % magnitude, ~8° rotation).
- **Optibeam** is a host mode: off sends nothing; on recomputes and re-sends chip 0 DAC0–3 (condenser), the weights and the objective.
- **Aperture** change (Optibeam on): new condenser values, weights, then an objective correction (2234 → 2262 at 50 → 30 µm, 10,000×).
- **Probe current** (beam on, 20 kV): the same lens block. Condenser DAC0 falls monotonically with current (1111 / 1035 / 938 / 827 at 50 / 300 / 500 / 1000 pA); DAC0/1 and DAC2/3 behave as two coarse / fine pairs; the objective is refocused each time (fine 2095–2256) and the weights follow by tens of counts.
- **Depth mode** swaps condenser strength between the pairs (DAC0 ~1035 → 205, DAC2 ~254 → 1116); **auto resolution** is a smaller condenser change. Both are host-side Optibeam calculations.
- The Optibeam condenser values are a calibration function of kV, probe current, aperture, WD and magnification inside LEO-32; only sample points are known. A replacement needs its own lens calibration.

### 5.7 Dynamic focus **[C]**
- Enable (non-zero angle): read chip 1 DAC0 / DAC1, then **write chip 1 DAC1 once per line, ~22 µs after the Y write**.
- **DAC1 = focus + k·(Y − 32768)**; at 30°, 86×: DAC1 = 2087.3 + 0.004465·Y (centre = focus value, ±146 counts over the frame). Slope ∝ tan(angle) × scan size **[I]**.
- At 0°: only the weights are re-sent. Off: the per-line writes stop.

### 5.8 Scan modes **[C]**
- **Reduced area (window):** ramp set-up sent twice (old values, then new): X r00 = 16895, r08 = 512, r01 = 116; Y r00 = 16639, r08 = 384, r01 = 252; chip 2 DAC1 = ~1088; then the speed block. Same pixel pitch as full frame, central half of each axis. Line period 2.811 → 1.736 ms at speed 5 (800 instead of 1296 clocks per divider unit).
- **Line scan:** chip 3 r00 = line Y position (e.g. 16219), r08 = 10, r01 = 6; the per-line Y write stays at the line position; X keeps scanning; F1 and F2 held high.
- **Spot:** chip 2 control 0 → options 1, routing 4, r0A 1, control 0x8422, DAC1 41, chip 4 DAC4 = 1, r0A 15, then **chip 2 DAC4 = X position, chip 3 DAC4 = Y position** (16-bit, e.g. 16895 / 16639 ≈ 25 %); per-line writes stop.
- **Return to full frame:** full ramp set-up (X r00 1023 / r08 1024 / r01 232; Y r00 511 / r08 768 / r01 504), speed block (options 9 or range | 8, routing 8, slope, r0A, control 0x8402), chip 2 DAC1 110, chip 4 DAC4 0.
- **External scan:** centring offsets → 2048; read then clear chip 3 options bit 3 (252 → 244). Off reverses it. Signal path: §1.1.
- **Split scan / dual magnification:** X r08 = 512, r01 = 116 with X r00 = 1023 (full-frame start), chip 2 DAC1 = 1116; Y unchanged (768 lines). Line period 1.736 ms at speed 5. The two halves of the display are built by the IP board.
- **Line averaging (N):** **chip 3 r0A = N − 1**: each Y position is scanned on N consecutive lines. Writing chip 3 r0A also **restarts the frame** (this is the "chip 3 r0A = 0" at the end of every speed / mode block).
- **Frame averaging / frame integration:** only a frame restart (chip 3 r0A = 0); the averaging is in the IP frame store.
- **Auto-stigmation (autofocus + autostig, several seconds):** small centred window (256 × 128 points, X r00 24831, Y r00 27391), speed-2 settings, range change, objective rewrite, then stigmator steps of ±1000–1500 counts; the rest of the algorithm was not captured. A replacement implements its own image-based autofocus / autostig.
- Capture is fixed at 1024 × 768 by the IP frame store and software, not by the EO board (16-bit start / step / count registers).

### 5.9 Focus wobble **[C]**
Chip 1's ramp generator swings the objective fine value around the focus value `F` (chip 1 DAC1) with amplitude `A`:

| chip 1 reg | Value |
|---|---|
| control | 0 (stop) first |
| r00 | **F − A** |
| r01 = r02 | step: **A** (fast) or **A/2** (slow) |
| r03–r06 | 0 |
| r07 | 1 |
| r08 = r09 | ticks per step: **2** (fast) or **4** (slow) |
| r0A | 1 |
| routing | 1 |
| control | **0x8063** (run) |

- Written ~0.94 ms apart. Slow has ~4× the period of fast.
- A scales with the amplitude setting and inversely with magnification: at 10,000× A = 5 counts per % (10 % → 50, 50 % → 250); at 86× A is clamped at 766 for every setting.
- The software also switches to the reduced-area window while wobbling.
- **Off:** chip 1 control = 0, chip 1 DAC1 = F, then full frame restored.
- Changing magnification while wobbling re-sends the wobble with the new A.

### 5.10 Freeze **[C]**
Sent as the beam-position block (pairs A and B, §4):

| Action | Pair A | Pair B | Effect |
|---|---|---|---|
| Freeze on command / on line end | 2047 → 3070 | 2047, then 1024 (~1.7 ms) | identical on the link; Y ramp continues to frame end, then parks at 511 |
| Freeze on frame end | unchanged | unchanged | nothing immediate; freeze at the end of the frame |
| Unfreeze | 2047 | 1024, then 2047 (~2–3 ms) | frame restart, Y ramp restarts |

These look like 3-level control signals rather than analog settings **[I]**. **No beam blanking was found** on this link: the beam keeps scanning to the end of the frame in every freeze mode.

### 5.11 Boot and start-up sequences **[C]**
1. **Windows start ("waiting for LEO")** and **LEO-32 UI start** send the same reset burst (59 writes, 23 µs apart):
   - routing 15 / options 32 / control 0 on chips 0 and 1;
   - chip 2 / chip 3 r07, r0A, control and routing 0 (chip 3 routing 4);
   - **chip 4**: r00 0, r01 1, r02 1, r07 0, r08 255, r09 255, r0A 0, control 0x8403;
   - all DACs to defaults: chip 0 DAC0–3 = 0, DAC4–9 = 2048; chip 1 DAC0–1 = 0, DAC2–3 = 2048, DAC4–7 = 128, DAC8–9 / r1A / r1B = 0; chip 2 DAC0 0, DAC1–3 2048, DAC5–6 32768; chip 3 DAC0–1 2048, DAC2 0, DAC3 2048, DAC4–6 32768, DAC7–8 0.

   Then the ramp set-up (chip 2 r08 1024, r02 62, r00 1023; chip 3 r08 768, r09 128, r02 84, r01 504, r00 385 or 511), a read of chip 2 control, and speed 5. **The coil weights stay at 32768**: a timed raster with zero deflection.
2. **Login:** beam-position block (running values), the saved coil weights, then a series of lens read-modify-writes (chip 0 DAC0–3, chip 1 DAC0–1), each followed by a weight update, for several seconds.

## 6. Requirements for a replacement host

1. At power-up, send the reset burst (§5.11) and the ramp / speed set-up; keep the coil weights at 32768 until a magnification is chosen.
2. Generate F2 (line) and F1 (frame) gates as in §2.1 and write the Y position once per line ~27 µs after each F2 rising edge (except line-scan / spot / stepped modes as described).
3. Program the line rate with chip 2 stopped (control 0), then restart (0x8402, or 0x8422 for stepped / spot).
4. Magnification: park the weights → set the range → wait ≥ 40 ms → write the weights. Choose the most sensitive range that keeps |weight| < 32767. Never switch the relay ranges with the coils driven.
5. Compute the coil weights from the range calibration, magnification, rotation + lens rotation, tilt (cos on Y) and per-coil gains (§5.4); beam shift through the same rotation.
6. Use read-modify-write for lens DACs on chips 0 and 1 as the original does.
7. Dynamic focus: add one objective-fine write per line, linear in Y.
8. Focus wobble: program chip 1's ramp generator (§5.9); restore DAC1 on stop.
9. On every EHT change (after the ramp settles): rescale the objective and the coil weights by √(relativistic kV), recompute the condenser, re-pick the range. Keep the angles.
10. Provide a lens calibration (condenser / objective vs kV, probe current, aperture, WD) to replace Optibeam.
11. Interlock with the EHT / vacuum side as specified in `REPLACEMENT_REQUIREMENTS.md`.

## 7. Open items

- kV compensation: **resolved** (§5.3); it only happens with the beam on.
- Which chip-0 pair drives C1 and which C2; A / B coil pins; external-scan path (§1.1 tests).
- Wobble amplitude at 100 % / 10,000× (expected A ≈ 500); the dependence of A on WD.
- Exact meaning of r01 / r07 / r09 / r0A on chips 2 and 3, and of chip 4's registers.
- Meaning of pairs A / B (acquisition-control lines?) and of F1 / F2 (gates?): confirm with the IP-side frame store.
- Never-written registers: chip 0 DAC8 / DAC9, chip 1 DAC4–DAC7 (8-bit, probably gun alignment, §1.1), DAC9 (spare outputs or unfitted options). The electrostatic beam blanker (EBBU) is an option that is **not fitted** on this microscope (user, 2026-11-13), so no blanking control is expected.
- Dynamic-focus slope vs angle and magnification; stigmator step vs magnification table.
- Transceiver part numbers and wavelength.

## 8. Sources

- Test log with every capture: `scope_tools/SCAN_FIBER_NOTES.md`.
- Captures: `scope_captures/` (`coldboot_*`, `ctl_*`, `ctl2_*`, `ctl3_*`, `ctl4_*`, `spd_*`, `kv_*`, `beam_*`, `beam2_*`, `t1`–`t13`, surveys). Each has `.npz`, `_ch3.txt` (decoded) and, for the loop captures, a wall-clock `*_log.txt`.
- Timing diagram: `scope_captures/scan_fiber_timing.png`.
- Tools: `scope_tools/cold_boot_loop.py` (re-arming capture loop), `decode_scan_fiber.py`, `arm_burst.py`, `scope_setup.py`.
- Static EO register map: `report/` and `analysis/` (ADSP-21xx disassembly).
