# LEO 438VP Electron Optics Model (from LEO-32 / GSP firmware)

| | |
|---|---|
| Subject | How accelerating voltage (kV), working distance (WD), probe current and focus determine the lens currents; the column model LEO-32 uses (Optibeam) |
| Source | Decompilation of the GSP module `TIGA/g200.440`. Source files `gcondens`, `gfocus`, `geht`, `goptctrl` and `gcolmod`. The machine data file `C:\LEO\Data.vac` and the factory calibration `LEO-32\435vpcal\LEO 438V.clb` |
| Revision | 0.1, 2026-11-15 |
| Tools | `analysis/fdec.py` (symbolic decompiler for the TI 340x0 C compiler's software floating point); raw outputs in `analysis/optics/` |

Markers: **[D]** decoded from the code with constants; **[C]** cross-checked against scope captures; **[I]** inferred, needs confirmation.

---

## 1. The short version: how the controls interact

LEO-32 holds a **paraxial model of the whole column**:

```
gun crossover → C1 → C2 → (final aperture) → objective C3 → specimen
```

It does not keep tables of DAC values. Every operator control changes one input of the model. The model then gives each lens a focal length, and each focal length is converted to a coil current for the present kV.

| Operator control | What changes in the model | Which lens currents move |
|---|---|---|
| **kV** | Electron rigidity `√Vr`, and the gun data (brightness, source size, energy spread) | **All of them.** At a fixed focal length every lens current scales with `√Vr` (§3). Optibeam then re-picks C1/C2 so the requested probe current is still delivered with the new gun brightness, so the condensers do *not* simply follow √Vr. Scan coil weights also scale with √Vr (scan spec §5.3) |
| **Probe current** | Demagnification of the source by C1 and C2, which moves the C2 crossover. This changes how much of the beam passes the final aperture (§6) | **C1 and C2** (solved together through the crosstalk matrix, §4). The objective also changes slightly, because the C2 crossover is the objective's object |
| **WD** (typed in) | Target image plane of the objective | **Objective (C3)**, solved iteratively (§5.3) |
| **Focus** (knob) | Objective excitation `k` directly, in steps scaled to magnification (§5.4). The displayed WD is the image distance this produces | **Objective (C3)** only |
| Aperture selection | Aperture diameter in the probe model | C1/C2 for the same probe current (Optibeam on) |

So **focus and WD are the same thing**: focusing is solving for the objective excitation that images the C2 crossover onto the specimen, and the WD readout is that distance. **Probe current is set by the condensers.** **kV rescales everything** by `√Vr` and changes the gun.

## 2. Column geometry **[D]**

Coordinates along the optical axis are in metres, as used by the code. The objective sits near z = 0, with negative values towards the gun. The specimen plane is at **z = +WD**.

| Element | z (m) | Source |
|---|---|---|
| Gun crossover (object of C1) | −0.534 | constant in `gcondens`, `goptctrl` |
| C1 principal planes (object / image) | −0.36592 / −0.36737 | `.cinit` lens record 0 |
| C2 principal planes | −0.20683 / −0.20797 | `.cinit` lens record 1 |
| Final (objective) aperture | −0.16 (code); `Data.vac` holds −0.164 **[I]** | `gcolmod`, `goptctrl` |
| Objective (C3) principal planes | functions of excitation, §5.1 (≈ −0.008) | `gfocus` |
| Specimen | +WD; allowed 0.001–0.12 m | `_gsp_set_working_dist` |

Aperture size: 30 µm by default (`.cinit` aperture table, 5 positions). `Data.vac` holds measured diameters of 29.75 µm ×5 and 30.63 µm ×5 **[I]**.

## 3. Common lens law **[D]**

Every lens is a magnetic lens described by its **excitation** `k = N·I_eff / √Vr`:

```
√Vr   = sqrt( V · (1 + V / 1 021 955) )          V in volts (relativistic, = 0.978e-6 per volt)
k     = N · (I + rem) / (cal · √Vr)               N = turns, I = coil current (A)
I     = cal · k · √Vr / N − rem
f(k²) = a + b / (2c·k²) + (c/2)·k²                focal length (m), thick-lens fit
k²(f) = ( (f − a) − sqrt((f − a)² − b) ) / c     inverse, used to set a focal length
```

| Lens | N (turns) | a | b | c | f(k²) written out |
|---|---|---|---|---|---|
| C1 | 1000 | 0.00144945 | 9.19117e-6 | 1.02404e-5 | 0.00144945 + 0.44877/k² + 5.1202e-6·k² |
| C2 | 1000 | 0.00107975 | 5.24399e-6 | 8.09958e-6 | 0.00107975 + 0.32372/k² + 4.04979e-6·k² |
| C3 (objective) | 1030 | 0.00213392 | 1.76339e-5 | 1.4051e-5 | 0.00213392 + 0.627497/k² + 7.0255e-6·k² |

Per-machine calibration (`cal`, `rem`) comes from `Data.vac`. It matches the factory calibration file `LEO 438V.clb` of 2003-06-23:

| Lens | cal | rem (A) | compiled default |
|---|---|---|---|
| C1 | 1.0597 | 0.0101 | 0.958 / 0.0105 |
| C2 | 1.0597 | 0.0101 | 1.063 / 0.0318 |
| C3 | 0.9912 | 0.0108 | 0.939 / 0.0137 |
| Crosstalk C1↔C2 (XTLK 12, 21) | 0.042 each | | 0 |

Current limits used by the ramp / hysteresis routines: condensers 2.6 A, objective 2.1 A **[D]** (meaning as maxima **[I]**).

**Consequence for kV:** at a fixed focal length, `k` is fixed, so `I + rem ∝ √Vr`. Going from 20 to 25 kV multiplies every lens current by 1.1207 (scan spec §5.3 measured 1.1196 for the weights).

## 4. Condensers C1 / C2 **[D]**

- **Each crossover image** uses the thin-lens relation, measured from the principal planes (`_calculate_crossover`):
  ```
  u = z_H − z_object,   v = u·f / (u − f),   z_image = z_H' + v,   M = v / u
  ```
  C1 images the gun crossover (z = −0.534); C2 images the C1 crossover. Each lens stores its magnification (`_update_C1/C2_crossover_and_mag`).
- **Currents from the wanted excitations** `k1`, `k2`, with crosstalk (`_calc_condenser_lens_current`). The two-equation system is
  ```
  k1 = N1·(I1 + rem1)/(cal1·√Vr) + N2·xt12·I2/√Vr
  k2 = N2·(I2 + rem2)/(cal2·√Vr) + N1·xt21·I1/√Vr
  ```
  solved with Cramer's rule for I1 and I2.
- In Optibeam mode the probe-current routine picks the condenser focal lengths, and `_set_focal_length_on_lens(f1, f2)` turns them into excitations and currents.

## 5. Objective C3: WD and focus **[D]**

### 5.1 Excitation-dependent principal planes
```
z_H (object side) = 2.12386e-5 · k² − 0.00805914
z_H'(image side)  = −1.19731e-5 · k² − 0.00792216
```

### 5.2 Excitation range
`k` is limited to **2.88378 … 10.6798** (the focus step routine clamps to it). The working distance must stay between **1 mm and 120 mm**.

### 5.3 Typed WD → excitation (`_calc_excitation_for_WD`)
This is an iterative solution. With the C2 crossover as the object, it repeats the following until the image lands within 10 µm of z = WD:
1. compute the needed focal length from the thin-lens equation;
2. invert f(k²);
3. update the principal planes for the new k.

The objective current then follows from §3.

### 5.4 Focus knob (`_gsp_step_focus`)
- Each click changes the excitation: `k ← k + clicks·Δk`.
- The step comes from `_calc_excitation_step_size`. It is based on the image magnification and the column model, capped by a constant 0.088, and scaled by `k` and a sensitivity setting. Fine steps at high magnification, coarse at low.
- The new k is accepted only if the resulting image distance (the WD) stays within 1–120 mm.
- Afterwards the WD readout, the scan rotation (`_gsp_set_C3_rotation`) and the Optibeam state are updated.

### 5.5 Aberrations (`gfocus`, near `_gsp_read_C3_current`)
Two polynomials in k² define the objective's aberration coefficients:
```
P(k²) = 15.0471/k² + 0.00261369 + 0.000332747·k²
Q(k²) = 0.628001/k² − 0.000147105 + 5.75723e-6·k²
```
The stored values (`_read_C3_aberrations`: two numbers, used by Optibeam as Cs and Cc) are products of P³, Q and the excitation **[D]** for the forms, **[I]** for their exact meaning and units.

### 5.6 Cross-check with the captures **[C]**
- Model objective current at WD ≈ 10 mm: **0.623 / 0.888 / 1.26 A** at 5 / 10 / 20 kV.
- Captured objective coarse DAC (scan spec §5.3): **382 / 550 / 790**.
- Implied scale: **1.63 / 1.61 / 1.59 mA per coarse count**, constant to about 2 %. This confirms the √Vr law and the C3 calibration, and gives about **1.6 mA per objective coarse count**. The fine DAC adds a small trim on top (2230 → 2234 per focus click at 86×). The exact coarse/fine split is in `_gsp_set_C3_current` (to finish decoding).

## 6. Optibeam: probe current and probe size (`goptctrl`) **[D]** structure, **[I]** details

### 6.1 Gun model (`_update_electron_source_data`)
Gun data is a table versus voltage, interpolated linearly in kV. The brightness term is scaled with `log`/`exp` in the code. There are two tables, by filament type and mode, each with 15 voltage rows (500 V … 30 kV).

| V (kV) | Brightness β (A/m²/sr) | Source (crossover) diameter d₀ | Energy spread ΔE (eV) |
|---|---|---|---|
| 0.5 | 1.62e6 | 129.8 µm | 0.38 |
| 1 | 6.15e6 | 135.6 µm | 0.53 |
| 2 | 2.27e7 | 121.8 µm | 0.74 |
| 5 | 1.22e8 | 83.9 µm | 1.11 |
| 10 | 4.22e8 | 53.1 µm | 1.44 |
| … to 30 kV | | | |

The units shown are the natural ones for a tungsten hairpin. The column meanings come from how the code uses them **[I]**.

### 6.2 Probe size (`_gsp_optibeam_status`)
The final probe diameter is a quadrature sum:
```
d = sqrt( d_I² + d_d² + d_c² + d_s² )
d_I = d₀ · M_C1 · M_C2 · M_C3                 (demagnified source)
d_d = 1.30364e-9 / (√Vr · α)                  (diffraction; 1.0634 · λ·√Vr, with λ = 1.226e-9/√Vr m)
d_c = 1.181 · Cc · (ΔE / V) · α               (chromatic)
d_s = Cs-term · α³                            (spherical)
```
- α is the convergence semi-angle at the specimen, set by the final aperture (radius / distance to the C2 crossover image, at z = −0.16 m) and the objective magnification.
- Depth of field is shown as 3.826e-5 / M or 2.292e-4 / M (two display criteria).

### 6.3 Probe current
- Brightness-limited: `I_p ∝ β · (source image size × aperture angle)²`. In the code: `β · ((r · M · …) / 0.53)²` for the maximum current, with the same form evaluated for the present lens state.
- `_gsp_set_probe_current` clamps the request between the achievable minimum and maximum. These are recomputed for every kV / aperture change (`_update_optibeam_for_EHT_change`, `_gsp_set_current_aperture`).
- It then chooses C1/C2 (the crossover position) to deliver it. Correction tables ("condition layers", `_interpolate_condition_layer`, import/export via `_gsp_import_condition_table` / `_gsp_import_probe_table`) refine the analytic result **[I]**.
- Modes: auto-resolution, depth, HPSEM (VP: `_set_lenses_for_HPSEM`), conjugate focus.

### 6.4 Cross-check **[C]**
- In the probe-current captures at 5 kV, the C1 DAC fell monotonically with current: 1111 → 1035 → 938 → 827 for 50 → 1000 pA. A weaker C1 means less demagnification and more current through the aperture, as §6.3 predicts.
- The objective moved by a few counts, because the C2 crossover (its object) moved.
- At 20 / 21 / 25 kV with the same requested current, the C1 DAC stayed near 1393–1403, *not* ∝ √Vr. That's because brighter gun data at higher kV lets Optibeam use weaker condensers, which roughly cancels the √Vr scaling.

## 7. `Data.vac` (LEO-32 non-volatile machine data) **[D]** partly

`Data.vac` is a 1567-byte packed binary image of a structure. It's written by the vacuum DLL `m600.dll` on shutdown, read by `leoserv.exe`, and serialised by admin32 ("Data.Vac", with dongle serial). Known fields:

| Offset | Content |
|---|---|
| 0x9d / 0xa1 | C1 cal 1.0597 / rem 0.0101 |
| 0xa5 / 0xa9 | C2 cal 1.0597 / rem 0.0101 |
| 0xad / 0xb1 | C3 cal 0.9912 / rem 0.0108 |
| 0xb5–0xd9 | aperture diameters per position: 29.75 µm ×5, 30.63 µm ×5 **[I]** |
| 0xee / 0xf2 | crosstalk XTLK 12 / 21 = 0.0422 |
| 0xf6 | 3e-5 (default aperture, 30 µm) |
| 0x156 | −0.164 (final aperture z, m?) **[I]** |
| others | vacuum, stage, detector list (SE1, SE2, QBSD, RBSD, SCM, Cathodo, Trans, TV, AUX 1–9), unknown |

## 8. What this means for the control box

The firmware currently uses a 4-point probe-current table at 5 kV (`eo.pc*`). With this model it can do what LEO-32 did:
1. **kV:** compute `√Vr`, interpolate the gun table, and scale every lens current by `√Vr` at constant focal length. That replaces the empirical "objective coarse ∝ √kV" rule, which turns out to be exact.
2. **WD / focus:** keep the objective as excitation `k`. Focus clicks change `k` (step ∝ 1/magnification). WD is computed from the thin-lens image of the C2 crossover, and the WD readout feeds the scan geometry (rotation and size versus WD).
3. **Probe current:** choose C1/C2 focal lengths from the brightness-limited current through the aperture, then use the crosstalk-matrix currents.
4. **Current → DAC:** objective ≈ 1.6 mA per coarse count (§5.6). The condenser DAC scaling and the coarse/fine splitting are still to be decoded from `_gsp_set_condenser_lens_current` / `_gsp_set_C3_current`, or measured with a clamp meter on the lens supplies.

## 9. Open items

- Coarse/fine DAC scaling for all three lenses (decode `_gsp_set_C3_current`, `_gsp_set_condenser_lens_current`; or measure).
- The exact probe-current law and the condition-layer correction tables (`_interpolate_condition_layer`, 0x48d20–0x61920, unnamed statics). Where the imported probe / condition tables are stored on the PC.
- Units and meaning of the aberration polynomials P and Q; the WD dependence of the scan rotation (`_gsp_set_C3_rotation`, `_gsp_set_FCF_tilt_angle`).
- Whether the specimen-plane z reference is exactly +WD or offset (the WD solver compares with `arg1`).
- Remaining `Data.vac` fields.

## 10. Reproducing

```
cd analysis
python fdec.py "<drive>/TIGA/g200.440" _calc_excitation_for_WD _calc_condenser_lens_current _gsp_optibeam_status
python fdec.py "<drive>/TIGA/g200.440" 0x567b0          # unnamed static functions by address
```
Outputs used for this document: `analysis/optics/*.txt`. GSP doubles are stored with their two 32-bit words swapped. `.cinit` holds the compiled lens records, calibration defaults, gun table and aperture table.
