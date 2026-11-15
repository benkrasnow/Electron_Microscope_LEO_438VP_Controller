# EO optics capture test plan (LEO-32 lens settings)

| | |
|---|---|
| Purpose | Record what LEO-32 sends to the EO board for every combination of kV, WD, probe current, Optibeam mode, aperture entry and magnification. The new control box then reproduces (or improves on) the old behaviour. |
| Not needed | Faraday cup / measured probe current, probe size, physical aperture changes |
| Settles | The displayed-WD ↔ GSP-WD transform; which GSP routine each UI Optibeam mode uses; the C1/C2 law (spec `ELECTRON_OPTICS_MODEL.md` §6.5–6.6); kV and low-kV behaviour; whether magnification or hysteresis matter |
| Capture | CH3 (IP → EO) decoded by `cold_boot_loop.py` with the single-frame trigger (`high_limit_us = 2750`) |
| Time | Tier 1 ≈ 45 min, all tiers ≈ 1 h 45 min of stepping, plus kV settling |

## 1. How a session runs

1. You reconnect the probes as before (CH1–CH3 = IP → EO fibers, CH4 = EO → IP) and tell me.
2. I save your scope set-up, then start the capture loop for one block at a time, named after the block (e.g. `opt_A20`).
   - The loop prints **`ARMED shot NN`** in a terminal tab I open for you, and beeps.
   - After each trigger it needs about 15 s to download and re-arm.
3. You make **one** UI change per step. Wait for the next `ARMED` (or about 20 s) before the next change. A change made while the loop is downloading is lost: that is how the 5 kV step of the earlier EHT test was missed.
4. Say in chat when a block starts and ends, and anything unexpected (an extra click, a warning, a value the UI would not accept). I match shots to steps by order and by content.
5. At the end I stop the loop with the `STOP` file and restore your scope set-up.

Each step needs only the values written in the **Record** column of its block. Steps marked ★ are anchor points: also **save the conditions** there (LEO-32 "save state / conditions" to a file named after the step, e.g. `A20-6.MLC`). The `.MLC` files store LEO-32's own C1/C2/C3 currents and WD to 7 digits, which cross-checks my decoding. Copy the new `.MLC` files off the old PC afterwards (they are under `LEO-32\user\<your user>\`).

## 2. Standard state (return here before every block)

| Setting | Value |
|---|---|
| Vacuum | High vacuum (VP only in block H) |
| Beam | On, imaging any specimen. Focus is irrelevant: WD is typed in. |
| Scan | **Speed 5**, full frame. Reduced area, split scan, dynamic focus, tilt correction and wobble **off** (they trigger the loop on every line). |
| Magnification | **1000×** (block F changes it) |
| Optibeam | **On**, Depth **off**, Auto resolution **off** (= "Normal" below) |
| kV | **20 kV**, standard anode / no low-kV spacer |
| Aperture entry | The aperture the UI shows now. Note it at the start; this plan calls it the *home aperture*. |
| Probe current | **200 pA** |
| WD | **20 mm** (typed) |
| Don't touch | Focus knob (except step A-F), stigmators, beam shift, brightness/contrast (they are on other links, but keep the log clean) |

**Record once at the start:**
- the home aperture;
- the list of apertures the aperture dialog offers (diameters);
- the Optibeam panel, as a screenshot;
- the highest probe current the UI accepts at 20 kV (type 100 nA and note what it clamps to);
- the lowest it accepts (type 0.1 pA).

## 3. Blocks

### P. Pilot (5 min, Tier 1): does the old system recompute lenses with the beam off?
If it does, every block except E and H can be done beam-off (no filament wear, no specimen needed).

| Step | Action | Record |
|---|---|---|
| P-1 | Beam on, standard state. Probe current 200 → 300 pA | — |
| P-2 | Probe current 300 → 200 pA | — |
| P-3 | Beam **off** (EHT off, filament off as usual). Probe current 200 → 300 pA | any message |
| P-4 | Beam off. Type WD 20 → 25 mm | displayed WD |
| P-5 | Beam off. Type WD 25 → 20 mm, probe 300 → 200 pA | — |

I tell you right away whether P-3/P-4 produced lens writes and whether the objective value still matches 20 kV. If not, the rest is done beam-on.

### A. WD entry → objective (Tier 1 at 20 kV; Tier 2 at the other kV)
Settles the displayed-WD transform (displayed WD ≈ 1.19 × internal WD + 1.9 mm in the saved files). Normal mode, 200 pA, home aperture. Type each WD; **record the WD the UI displays afterwards** (it may round or differ).

| Block | kV | WD values to type (mm), in this order |
|---|---|---|
| A20 | 20 | 5, 8, 10, 12, 15, 20★, 25, 30, 40, 50, 60, 80, 100, then 20 again |
| A10 | 10 | 5, 10, 20★, 40, 80 |
| A5 | 5 | 5, 10, 20, 40, 45, 80 (45 mm ≈ the earlier 5 kV captures) |
| A30 | 30 | 5, 10, 20, 40 |
| A-F | 20 | From WD 20 mm: 5 clicks of **focus** one way, then 10 clicks the other way. Record the displayed WD after each group of clicks. Checks that focusing and typing use the same WD scale. |

Record per step: **displayed WD**.

### B. Probe-current sweeps, Normal mode (Tier 1: B20-20; Tier 2: the rest)
Settles the C1/C2 law for the mode you normally use. Type each current; **record the probe current the UI displays afterwards** (it clamps at the limits).

Currents (pA), in this order: **10, 30, 100, 200★, 500, 1000, 2000, 5000, max**, then **200 again** (hysteresis check).

| Block | kV | WD (mm) | Tier |
|---|---|---|---|
| B20-20 | 20 | 20 | 1 |
| B20-10 | 20 | 10 | 2 |
| B20-40 | 20 | 40 | 2 |
| B10-20 | 10 | 20 | 2 |
| B5-20 | 5 | 20 | 2 |
| B5-45 | 5 | 45 | 2 (repeats the earlier 50 / 300 / 500 / 1000 pA captures; add those four values) |

Record per step: **displayed probe current**, and any "limit" message.

### C. Optibeam modes (Tier 1 at 20 kV; Tier 2 at 5 kV)
Settles which internal routine each UI mode uses. The earlier test showed Depth swapping the condensers (C1 1035 → 205, C2 254 → 1116) and Auto resolution changing them slightly.

| Block | kV / WD | Mode | Currents (pA) |
|---|---|---|---|
| C20-D | 20 / 20 | **Depth on** | switch the mode on at 200 pA, then 10, 100, 1000, max, then 200, then Depth off |
| C20-R | 20 / 20 | **Auto resolution on** | same sequence |
| C20-DW | 20 | Depth on, 200 pA | WD 10, 20, 40 mm (Depth depends on WD more than Normal does) |
| C20-RW | 20 | Auto resolution on, 200 pA | WD 10, 20, 40 mm |
| C5-D, C5-R | 5 / 20 | as C20-D / C20-R | 10, 100, 1000 |

If the UI allows Depth and Auto resolution together, add one step with both on (20 kV, 200 pA).
Record per step: **displayed probe current, displayed WD, mode indicators**.

### D. Aperture entry (Tier 1: D20; Tier 2: the rest)
Software entry only: leave the physical aperture alone. Settles how much the entered diameter matters to the calculation (§6.5: it scales the convergence angle).

| Block | Condition | Steps |
|---|---|---|
| D20 | 20 kV, WD 20, Normal, 200 pA | enter each aperture the dialog offers, in turn, then the home aperture again |
| D20-1n | same, 1000 pA | each aperture, then home |
| D20-D | Depth on, 200 pA | each aperture, then home |
| D20-R | Auto resolution on, 200 pA | each aperture, then home |

Record per step: **aperture entered**, displayed probe current (it may clamp).

### E. kV sweep, standard anode (Tier 1)
Beam on (kV recompute follows the EHT readback). Normal, WD 20 mm, 200 pA, home aperture. **Wait about 30 s after each change** (the lenses follow the kV ramp over a few seconds, and the scan-range relay clicks near 20 and 10 kV). Go up and down to see hysteresis.

kV order: **20★, 25, 30, 25, 20, 15, 10★, 7.5, 5★, 4, 3, 2, 1**, then back to **5, 10, 20**.

Record per step: **kV readback shown**, displayed WD, displayed probe current, any relay click.

### E-L. Low kV with the low-kV anode / spacer (Tier 2, your call)
Only if you use the low-kV spacer and the swap is routine for you. LEO-32 has separate gun tables for the low-kV anode (0.1–3 kV), selected by the anode setting. If fitting the spacer is a hassle, do only the software part: with the beam off and P-3 positive, change the anode setting and step the kV setpoint.

| Step | Action | Record |
|---|---|---|
| EL-1 | Set the anode / spacer setting to low-kV (as you normally do), 3 kV, Normal, WD 10 mm, 50 pA | the anode setting name |
| EL-2…6 | kV 2, 1.5, 1, 0.5, 0.3 | kV readback, displayed probe current |
| EL-7 | At 1 kV: probe current 10, 50, 200, max | displayed probe current |
| EL-8 | At 1 kV: WD 5, 10, 20 | displayed WD |
| EL-9 | Anode back to standard | — |

### F. Magnification (Tier 2)
Checks whether magnification feeds the lens calculation (`DP_MAGTRACK` was on in your saved files). 20 kV, WD 20, Normal, 200 pA.

Mag order: **50×, 200×, 1000×, 5000×, 20 000×, 100 000×, 1000×**. Record the displayed mag. (The coil weights change at every step; I am looking for condenser/objective writes.)

### G. Repeatability (Tier 1, spread through the session)
Return to the standard state (20 kV, WD 20, 200 pA, Normal, home aperture, 1000×) **after blocks A20, B20-20, C20, D20 and E**, one step each (G-1…G-5), and save conditions there (★). Your saved files show two states with the same settings and different C1 (0.904 vs 0.762 A). This shows whether the old system really depends on history.

### H. VP mode (Tier 2, optional)
At the standard state, switch to VP by your normal procedure (the old system handles the filament). Once at pressure and imaging: probe current 10, 200, 1000 pA, then WD 10 and 40 mm, then back to HV. Record **chamber pressure**, displayed probe current and WD. Settles `_set_lenses_for_HPSEM`.

## 4. Summary of what to write down

| When | What |
|---|---|
| Start | home aperture, aperture list, Optibeam panel screenshot, min / max probe current at 20 kV |
| Every step | the step ID if you deviate from the order; the value in the block's Record column |
| ★ steps | save conditions as `<step>.MLC` |
| Anything odd | clicks, warnings, clamped values, image going dark: tell me in chat at the time |

## 5. Priorities if time is short

1. **Tier 1:** P, A20, B20-20, C20-D, C20-R, D20, E, G. This settles the WD transform, the Normal-mode C1/C2 law, the mode mapping and kV scaling at the conditions you use most.
2. **Tier 2:** the other WDs and kVs in A and B, C5, the rest of D, E-L, F, H.

## 6. What I do with the data

- Decode each shot into condenser DAC0–3 (C1 / C2 coarse + fine) and objective DAC0 / DAC1, then convert to currents (§5.6).
- Fit the displayed-WD transform (block A).
- Run the emulator on every step and fix the remaining C1 mismatch: mode mapping (block C), aperture scaling (D), history (G).
- Write the result back into the spec and into the control-box firmware as either the emulated LEO-32 law or a measured lookup table, whichever reproduces the captures better.

## 7. Session log, 2026-11-15

All blocks ran in Normal / Depth / Auto resolution at 50 µm unless noted. The per-step table (settings + final lens DACs + currents, 140 rows) is `analysis/optics/eo_capture_2026-11-15.csv`, built by `analysis/optics/eo_capture_table.py` from the `scope_captures/opt_*` shots.

| Block | Shots | Done |
|---|---|---|
| Pilot `opt_P` | 6 | Beam off: lenses are recomputed from the **EHT readback** (0 V → clamped to 100 V), not the setpoint, so beam-off data is a 100 V state; beam on needed. A kV setpoint change with the beam off sends nothing. |
| `opt_A20` | 14 | WD 5–100 mm at 20 kV, 200 pA |
| `opt_B20` | 34 | Probe 10 pA–100 nA (Normal, Depth), Auto resolution (WD, aperture), aperture 30 / 50 µm in Normal and Depth |
| `opt_E`, `opt_E2` | 32 + 48 | kV 30 → 1 → 30 with a WD "nudge" (20.0 ↔ 20.1 mm) after the readback settled; Auto resolution at 10 / 5 / 2 kV; magnification 50×–100 000×; 5 kV probe, WD and Depth sweeps |
| `opt_EL` | 2 | 3 kV reference only |

Observations made during the session:
- Displayed WD: internal (GSP) WD = (WD − 1.9 mm) / 1.19 reproduces the objective within 2–8 coarse counts from 5 to 100 mm (20 kV), and at 100 V.
- The first lens update after a kV change is within 3 counts of the settled (nudged) value; no kV hysteresis; returning to a state reproduces it within a few counts (no visible history effect).
- Auto resolution sets the probe current itself (150 / 90 / 70 / 50 pA at 20 / 10 / 5 / 2 kV, independent of WD and aperture), then computes the lenses as Normal mode does at that current.
- Depth mode pins C2 near a ceiling (coarse ≈ 2260 at 20 kV, ≈ 1115 at 5 kV, about 0.853× the emulator's limit) and moves only C1; Normal mode lands on the Depth solution at low current or short WD.
- Magnification sends no lens writes (scan-coil weights and range relay only).
- The aperture entry has a large effect on the condensers (20 kV, 200 pA: C1 1011 → 1944 coarse for 50 → 30 µm).
- Skipped: VP (LEO-32 does not know about VP when it is switched from hpapp32, so its lens settings in VP were the high-vacuum ones) and the low-kV spacer (the UI only allows selecting it with the beam off).
