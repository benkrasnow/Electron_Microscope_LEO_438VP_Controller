# LEO 438VP Electron Optics Model (from LEO-32 / GSP firmware)

| | |
|---|---|
| Subject | How accelerating voltage (kV), working distance (WD), probe current and focus determine the lens currents; the column model LEO-32 uses (Optibeam) |
| Source | Decompilation of the GSP module `TIGA/g200.440`. Source files `gcondens`, `gfocus`, `geht`, `goptctrl`, `gcolmod`, `gscncoil` and `gscnxfrm`. The machine data file `C:\LEO\Data.vac`, decoded with the field table of LEO's own `view.exe`. The factory calibration `LEO-32\435vpcal\LEO 438V.clb` |
| Revision | 0.6, 2026-11-15 (0.1–0.5 same day): fitted to the 2026-11-15 EO captures (§6.7) and implemented in the firmware (§13) |
| Tools | `analysis/fdec.py` (symbolic decompiler for the TI 340x0 C compiler's software floating point); `analysis/gspemu.py` + `analysis/optics/emu_driver.py` (TMS34020 emulator that runs LEO-32's own column code); raw outputs in `analysis/optics/` |

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
| Final (objective) aperture | −0.16 | `gcolmod`, `goptctrl` |
| Conjugate-focus plane | −0.164 | `Data.vac` "Conjugate Position" |
| Objective (C3) principal planes | functions of excitation, §5.1 (≈ −0.008) | `gfocus` |
| Specimen | +WD; allowed 0.001–0.12 m | `_gsp_set_working_dist` |

Apertures (`Data.vac`): 30 µm (in use), 50 µm, 750 µm on the strip (§7).

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

### 5.5 Aberrations (static function at 0x36ac0, called with the objective record) **[D]**
```
P(k²)  = 15.0471/k² + 0.00261369 + 0.000332747·k²
Q(k²)  = 0.628001/k² − 0.000147105 + 5.75723e-6·k²
Cs     = P(k²)³ · (1 + m)⁴          (m)     → `_read_C3_aberrations` word 0
Cc     = Q(k²)  · (1 + m)²          (m)     → word 1
```
- m is the objective's magnification. The (1+m) powers are the textbook conversion from infinite-conjugate to the actual imaging condition.
- Examples: k² ≈ 86 (short WD) gives Cs ≈ 8.8 mm, Cc ≈ 7.7 mm. k² ≈ 19 (long WD) gives Cs ≈ 0.5 m. That growth follows the expected ~f³ scaling.

### 5.6 Lens current → DAC (all three lenses) **[D][C]**
`_gsp_set_C3_current` and `_gsp_set_condenser_lens_current` use the same 20-bit encoding over a 3 A full scale:
```
code   = round(I / 3.0 A × 1 048 575)          (0x497ffff0 = 1048575.0, 0x40400000 = 3.0)
coarse = (code − 2048) >> 8                    12-bit coarse DAC (0.732 mA per count)
fine   = (code − 2048) & 0xFF                  condensers: chip 0 DAC1 / DAC3 (captured 4 … 204, all < 256)
fine   = 2048 + ((code − 2048) & 0xFF)          objective: chip 1 DAC1 (captured 2095 … 2262, all within 2048 … 2303)
I      = ((coarse << 8) + low byte + 2048) / 1 048 575 × 3 A
```
- Register map, confirmed in `_gsp_set_condenser_lens_current`: C1 = chip 0 DAC0 (coarse) / DAC1 (fine); C2 = DAC2 / DAC3; objective = chip 1 DAC0 / DAC1.
- Captured objective coarse 382 / 550 / 790 at 5 / 10 / 20 kV = **0.286 / 0.409 / 0.585 A**. The ratios match √Vr (1.43 vs 1.42), confirming the excitation law.
- The absolute values correspond to a longer WD than the 10 mm assumed in revision 0.1. The WD of those captures was not recorded (measurement M2 in §11).

### 5.7 Image rotation by the objective (tail of `_gsp_calc_focus_lens_current`) **[D][C]**
```
θ_C3 = −9° × k        wrapped to 0 … 360°       (−9 = Data.vac "Focus Rotation")
```
This is the Larmor rotation, which is proportional to `N·I/√Vr = k`. It feeds `_gsp_set_C3_rotation` → `_calc_E3_dependents` → the scan coil matrix (§8). So every focus or WD change rotates the scan to keep the image still.
Check: the 10 → 15 mm WD change in the captures rotated the scan by about 8°. A Δk of 0.6–0.9 predicts 5–8°.

## 6. Optibeam: probe current and probe size (`goptctrl`) **[D]**

### 6.1 Gun model (`_update_electron_source_data`)
There are four tables of 15 rows: (tungsten, LaB6) × (standard anode 0.5–40 kV, low-kV anode 0.1–3 kV). Each row is (V, brightness B, source diameter d₀, energy spread ΔE). Values are interpolated linearly in V; there is `log`/`exp` scaling in one term. The block `[ΔE, d₀, B, V, √Vr, …]` (`_read_electron_source_data`) holds the values at the present kV.

This machine uses table 0 (tungsten, standard anode):

| V (kV) | 0.5 | 1 | 2 | 3 | 5 | 7.5 | 10 | 15 | 20 | 25 | 30 | 40 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B (A/m²/sr) | 1.62e6 | 6.15e6 | 2.27e7 | 4.81e7 | 1.22e8 | 2.53e8 | 4.22e8 | 8.59e8 | 1.42e9 | 2.08e9 | 2.84e9 | 4.62e9 |
| d₀ (µm) | 129.8 | 135.6 | 121.8 | 106.7 | 83.9 | 65.4 | 53.1 | 37.9 | 28.9 | 23.0 | 18.9 | 13.5 |
| ΔE (eV) | 0.38 | 0.53 | 0.74 | 0.89 | 1.11 | 1.30 | 1.44 | 1.64 | 1.77 | 1.87 | 1.94 | 2.04 |

(Rows 1.5, 2.5 and 4 kV are also in the table; all four tables are in `analysis/optics/`.)

### 6.2 Probe size (`_gsp_optibeam_status`, auto-resolution mode)
```
K_I = 0.53 · sqrt(I_p / B)                       ("current" term = α·d product)
K_λ = 1.30364e-9 / √Vr                           (diffraction; 1.063·λ)
d   = sqrt( d_I² + d_λ² + d_c² + d_s² ),   d_I = K_I/α,  d_λ = K_λ/α,
      d_c = 1.181·Cc·(ΔE/V)·α,  d_s = 0.278·Cs·α³ (the 0.278·Cs term appears in the resolution optimiser)
```
Depth of field is shown as 3.826e-5 / M or 2.292e-4 / M (two display criteria).

### 6.3 Setting a probe current **[D]**
`_gsp_set_probe_current(I)`:
1. Clamps I between `I_min = 1e-12 A` and `I_max`.
2. Stores I.
3. Calls the routine for the active mode through `_gsp_notify_optibeam`.

Each mode computes the convergence angle α and the required source-image size d at the specimen, then solves the condensers:

| Mode (routine) | α | d |
|---|---|---|
| **Auto-resolution** (0x5e000) | `α_opt = ((K_I² + K_λ²) / (3·(0.278·Cs)²))^(1/8)`: minimises the probe size (∂d/∂α = 0 with the spherical term) | `K_I / α_opt` |
| **Conjugate / fixed aperture angle** (0x5fd40) | the final aperture seen from the C2 crossover, which is held at the **conjugate plane z = −0.164 m** (`Data.vac`, `_gsp_set_conjugate_focus`): `α = D/(2·|−0.16 − (−0.164)|) / M_C3`. Also tries the other apertures (loops over the aperture table, thresholds 0.667 / 1.2) | `0.53·sqrt(I/B) / α` |
| Depth / other (0x5ef50, 0x5df00) | variants (larger WD, depth of field) | |
| VP (HPSEM, `_set_lenses_for_HPSEM`) | own settings | |

**Condenser solver** (static 0x4afb0, also 0x4bb40). Given the required total demagnification `M = d / d₀` and a target plane `z_t` for the C2 crossover:
```
u1 = zH1 + 0.534,   v2 = z_t − zH2'
z1 = (M·u1·zH2 + zH1'·v2) / (M·u1 + v2)          (C1 crossover position giving M1·M2 = M)
v1 = z1 − zH1',  u2 = zH2 − z1
f1 = u1·v1/(u1 + v1),   f2 = u2·v2/(u2 + v2)     → _gsp_set_condenser_focal_length(f1, f2)
```
`_set_focal_length_on_lens` turns f into k (§3 inverse), and `_calc_condenser_lens_current` into currents with the crosstalk matrix (§4). The objective is then re-solved for the WD (`_gsp_set_working_dist`), because its object (the C2 crossover) may have moved.

Probe-current range (0x567b0): `I_max = B·(α_g·d₀/0.53)²` with the gun acceptance α_g = 1.6779 mrad. The extreme condenser settings are the minimum focal lengths C1 4.9707 mm and C2 3.6796 mm. Lens record layout: `[zH, zH', f, k, I, z_crossover, M, N, –]` (`_update_C1/C2_crossover_and_mag`).

### 6.4 Cross-check against the probe-current captures (5 kV) **[C]** partly
`analysis/optics/column_model.py` runs the decoded chain from the captured DACs: DAC → current → excitation (with crosstalk) → focal length → crossover positions.

| Requested | C1 / C2 current | f1 / f2 (mm) | C2 crossover z (mm) | M1·M2 |
|---|---|---|---|---|
| 50 pA | 0.820 / 0.238 A | 5.67 / 23.6 | −180.1 | 6.30e-3 |
| 300 pA | 0.764 / 0.193 A | 6.14 / 33.7 | −164.8 | 1.06e-2 |
| 500 pA | 0.693 / 0.191 A | 6.91 / 35.1 | −162.5 | 1.27e-2 |
| 1000 pA | 0.612 / 0.189 A | 8.18 / 36.7 | −159.5 | 1.63e-2 |

- The C2 crossover is **not** held at the conjugate plane, so these captures were taken in **auto-resolution** mode. In that mode α grows with current, and the crossover moves towards the aperture.
- In that mode, with Cs ≈ 0.52 m (the objective state of the 5 kV capture, coarse 382 → 0.286 A, k² ≈ 19), the required demagnification grows by **2.73×** from 50 to 1000 pA. The decoded DAC chain gives **2.59×**. That's consistent within the unknown WD and objective magnification.
- An exact absolute check needs the WD of those captures (M2) or a measured probe current (M3).
- Rev 0.2's single-law check (68 pA at the 50 pA setting) assumed the conjugate-mode angle and is superseded by this mode identification.

### 6.5 Running LEO-32's own code: the GSP emulator **[D][C]**
`analysis/gspemu.py` is a TMS34020 interpreter for `g200.440`:
- bit-addressed memory with `.text`, `.data` and `.cinit` loaded;
- the FS$/FD$ software-float library and the C maths calls (`sqrt`, `sin`, `cos`, `log`, `exp`, `pow`) done in Python;
- the PC/DSP hooks stubbed. Every EO register write (`_DSP_set_EO_register`) is recorded.

`analysis/optics/emu_driver.py` initialises it the way LEO-32 does:
1. Fills the EO register ID tables.
2. Runs `_gsp_init_EO_board`, `_initialise_lens_data` and `_initialise_focus_lens_data`.
3. Applies this machine's `Data.vac` values: C1–C3 cal/rem, crosstalk, conjugate focus −0.164 m.

It then drives the user controls through the same entry points the PC calls (`_update_EHT`, `_gsp_set_working_dist`, `_gsp_set_optibeam_mode`, `_gsp_set_conjugate_mode`, `_gsp_set_probe_current`). The result is the DAC words LEO-32 would send.

Comparison with the 5 kV probe-current captures (`python optics/emu_driver.py`; coarse DACs C1 / C2 / objective):

| Requested | Captured | Mode 0, 30 µm (Data.vac) | Mode 0, 70 µm | Conjugate, 30 µm |
|---|---|---|---|---|
| 50 pA | 1111 / 317 / 380 | 1305 / 317 / 382 | 1301 / 407 / 379 | 1308 / 248 / 386 |
| 300 pA | 1035 / 254 / 382 | 1307 / 271 / 384 | 1010 / 348 / 381 | 1308 / 248 / 386 |
| 500 pA | 938 / 252 / 382 | 1307 / 264 / 385 | 921 / 341 / 381 | 1308 / 248 / 386 |
| 1000 pA | 827 / 250 / 383 | 1101 / 269 / 385 | 819 / 333 / 382 | 1308 / 248 / 386 |

What this establishes:
- **Objective:** reproduced to 1–3 counts at every current, with WD = 36.55 mm (the WD that reproduces the captured code). The C3 chain (§5) is therefore exact, including the dependence on the C2 crossover.
- **Gun data at 5 kV** (`GUN_NOW` 0x172b20): ΔE 1.11 eV, d₀ 83.9 µm, B 1.22e8, √Vr 70.88, so the tungsten / standard-anode table is selected and interpolated as in §6.1. The `log`/`exp` brightness term in `_update_electron_source_data` applies only above or below the table's kV range, not at 5 kV.
- **C2:** close in mode 0 with the 30 µm aperture (exact at 50 pA, +10…19 counts elsewhere).
- **C1 does not reproduce in any single state tried.**
  - With the 30 µm aperture from `Data.vac`, the solver asks for more demagnification than C1 can give and clamps at its minimum focal length (code ≈ 1307).
  - A 70 µm aperture fits C1 within 1–3 % at 300–1000 pA, but moves C2 by ~90 counts.
  - Brightness scaling (B × 0.05 … 0.5), aperture (10–200 µm), WD (5–45 mm), the conjugate flag and auto-resolution sub-modes 0–2 were all swept; none fits C1 and C2 together. Optibeam modes 1–3 are far off.
  - Since d = 0.53·√(I/B)/α, B and the aperture-defined α trade against each other, so the captured C1 slope (−208 counts from 300 to 1000 pA) points at a different α law rather than a different brightness.
- **Probe table** (`_gsp_import_probe_table`): it copies 25 floats into 0x174fa0. The defaults are five rows of increasing values (50…200, 5…160, 1…50, 1…20, 1…5). Mode 0 never reads them while setting a probe current.

The likeliest explanation is PC-side state the emulator does not set yet. Candidates:
- the aperture actually in the beam (M7);
- the PC's Optibeam start-up sequence (`_cp_set_aperture_data`, `_cp_set_current_aperture`, `_cp_FE_optibeam_update`, condition tables);
- a manual condenser adjustment during the captures.

M3/M4 captures with the LEO-32 Optibeam screen recorded (M8) would settle it. Until then:
- The control box uses the captured table for C1/C2 (`eo.pc*`).
- The emulator is the reference for the objective and for kV/WD scaling.

### 6.6 PC start-up state, condition table and saved operating points **[D][C]**

**How the PC talks to the GSP.**
- Every `_cp_*` entry (144 of them) only queues a message (`_PutQueue`, message ID plus arguments). The EO process later runs the matching `_gsp_*` routine.
- The emulator calls the `_gsp_*` routines directly, so nothing is lost.
- `_set_column_profile` (message 143) is an empty stub. `_initialise_lens_data` (0x2f0a0) and `_initialise_focus_lens_data` (0x3e010) take no arguments: they rebuild the lens records from the DAC words.

**Condition table** (`_gsp_import_condition_table`, message 113). It is a bilinear table over probe current (pA, 7 points at 0x175300) × kV (6 points at 0x1753e0), with 5 layers (0x1754a0, 35 floats per layer).
- Layer 0 is a correction of the probe current (`sub_4ac10`): the current used by the optics, `_coarse_lens_dac+1288`, becomes `layer0(I, kV)·1e-12` instead of the requested I.
- Layers 1–4 feed `_compensate_stig_setting`.
- The table is empty in `.cinit`. In that case the requested current is used unchanged, which the emulator confirms.
- No table file was found on the old PC's disk (Data.vac, user state files, `LEO\*.dat`). So, as far as can be told, LEO-32 ran with the identity table.

**Probe table** (`_gsp_import_probe_table`): 25 floats at 0x174fa0. Mode 0 never reads it while setting a probe current (§6.5).

**Saved operating points.** LEO-32's conditions files (`user\*\*.MLC`, macro text such as `AP_C1%7.717073e-001`) record, for each saved state:
- kV, the displayed WD, the probe current, the aperture index and the Optibeam mode;
- the C1/C2/C3 currents.

The currents are what `_gsp_get_C1C2_setting` / `_gsp_get_C3_setting` return: the DAC words read back from the EO board and converted with the same 3 A / 20-bit law. They are therefore the commanded currents. The emulator's readback path reproduces its own commanded currents to 1e-5.

`analysis/optics/mlc_compare.py` extracts the 11 points that have Optibeam mode 0, an aperture-strip aperture and real currents (2007–2009 and Ben's own `Feb1` / `Working`) into `mlc_points.csv`, and runs the emulator on each:

| File | kV | pA | ap | WD shown | GSP WD for saved C3 | Saved C1 / C2 / C3 (A) | Emulator at GSP WD: C1 / C2 |
|---|---|---|---|---|---|---|---|
| Feb1 | 6 | 200 | 0 | 32.7 | 25.5 | 0.896 / 0.190 / 0.359 | 1.050 / 0.228 |
| Working | 11.38 | 50 | 0 | 11.1 | 7.6 | 1.238 / 0.323 / 0.727 | 1.451 / 0.375 |
| 05-06-09 particles | 15 | 400 | 0 | 19.4 | 14.6 | 1.177 / 0.319 / 0.695 | 1.416 / 0.374 |
| WPseal20mm | 15 | 600 | 1 | 19.8 | 14.9 | 0.761 / 0.432 / 0.688 | 1.012 / 0.450 |
| 8-5penny18mm | 20 | 1000 | 1 | 18.1 | 13.4 | 0.904 / 0.457 / 0.824 | 0.992 / 0.534 |
| Aug 12 2008 | 20 | 2000 | 1 | 18.5 | 13.8 | 0.722 / 0.480 / 0.818 | 0.908 / 0.519 |
| 9-4 18 Z | 20 | 1000 | 1 | 19.1 | 14.3 | 0.762 / 0.510 / 0.808 | 0.999 / 0.532 |
| 10-15-2008 | 20 | 400 | 1 | 19.2 | 14.5 | 0.772 / 0.586 / 0.805 | 1.123 / 0.557 |
| Microsample 9-11-08 | 20 | 1000 | 1 | 20.7 | 15.7 | 0.756 / 0.512 / 0.785 | 1.010 / 0.529 |
| 200X25Z41WD | 20 | 200 | 1 | 41.5 | 32.7 | 0.983 / 0.552 / 0.609 | 1.435 / 0.538 |
| 25X80mm plg | 20 | 200 | 1 | 80.3 | 64.2 | 0.976 / 0.555 / 0.482 | 1.701 / 0.500 |

Findings:
1. **Displayed WD ≠ GSP WD.**
   - At the displayed WD the emulated objective current is 9.5 % below the saved C3 at every kV (7.5 % at 80 mm). This persists with the saved C1/C2 forced in, and every Data.vac copy has the same C3 cal/rem.
   - Expressed as WD: displayed WD ≈ 1.19 × GSP WD + 1.9 mm (rms 0.6 mm).
   - The GSP's forward (WD → current) and inverse (current → WD) agree with each other, so the transformation is on the PC side (leom/leoserv), not in `g200.440`.
   - Consequence: the 5 kV DAC captures (objective 380–383, emulator WD 36.6 mm) were taken at a **displayed** WD of about 45 mm.
2. **C2 is close.** Within −0.06 … +0.05 A once the objective state is matched. C2 also carries most of the current dependence at 20 kV (0.586 → 0.480 A from 400 to 2000 pA).
3. **C1 is too high in every case** (by 0.09 … 0.7 A, worst at long WD). The emulator's C1 also varies more with current than LEO-32's.
4. **C1 also depends on state that isn't saved.** `8-5penny18mm` and `9-4 18 Z` have the same kV, current, aperture and nearly the same WD, but C1 is 0.904 vs 0.762 A (C2 0.457 vs 0.510). No saved field (gun, filament, anode, aperture, Optibeam mode) differs between them.
   - The gun-related GSP setters (`_gsp_set_emission_amp`, `_gsp_set_first/second_peak`) only feed emission control and auto-saturation, not the source data.
   - The remaining candidates are PC-side: a runtime condition table, or hysteresis / manual condenser changes before saving.

### 6.7 What the 2026-11-15 captures settled **[D][C]**
`scope_tools/EO_OPTICS_TEST_PLAN.md` captured about 130 settled lens states on the EO link (`analysis/optics/eo_capture_2026-11-15.csv`). With `analysis/optics/fit_capture.py` (the emulator on every step) they settle the LEO-32 side:

| Question | Answer |
|---|---|
| Beam off | LEO-32 computes the column from the EHT **readback**: with the beam off that is 0 V, clamped to 100 V. Every earlier capture with objective coarse ≈ 34–76 (the `ctl*` tests, the "trip" event `beam_05`) was such a 100 V state. This explains those odd values, not the C1 mismatch |
| UI Optibeam modes | Dispatcher `_gsp_notify_optibeam`: **Normal** = mode 0 (`sub_5e000`, optimum angle from Cs); **Depth** = mode 1 (`sub_5ef50`, C2 at its 3.6796 mm focal-length limit); **Auto resolution** = flag +12 (`sub_5df00` picks the probe current: 150 / 90 / 70 / 50 pA at 20 / 10 / 5 / 2 kV, independent of WD and aperture), then mode 0 |
| Displayed WD | internal WD = (displayed − 1.876 mm) / 1.217 (fit; rms 1.6 objective counts over 5–100 mm and 1–30 kV). A PC-side conversion: a different C3 calibration fits much worse |
| Condenser calibration | LEO-32 behaves as if C1 / C2 cal were ≈ 0.936 / 0.904, not `Data.vac`'s 1.0597 / 1.05973. The Depth-mode C2 ceiling fixes C2's value to 3 counts at 5 and 20 kV |
| Gun table | The **LaB6 / standard-anode** table (filament selector 0x172b00 = 1) reproduces the probe-current dependence; the tungsten table does not. Presumably the PC's filament index differs from the GSP's |
| Magnification | no lens writes |
| History | none: every state repeats to within a few counts after other changes; first update after a kV change = settled value within 3 counts |

With these inputs the emulator gives Depth exactly (C2 ±4, C1 ±30 counts). In Normal mode it still differs where the optimum angle is large (short WD, low current, 25–30 kV). The firmware model (§13) therefore re-implements the equations with four fitted constants instead of running LEO-32's exact code.

## 7. `Data.vac`: LEO-32 non-volatile machine data **[D]**

The field layout comes from LEO's own viewer, **`view.exe` ("LEO DATA.VAC File Viewer", 1997)**. Each label in it is preceded by the load of its field. `analysis/datavac.py` extracts the table and decodes any `Data.vac`; the full listing for this machine is `analysis/optics/datavac_decoded.txt`. It's a 1567-byte packed file:

| Section | File offset | Size | Content |
|---|---|---|---|
| NVRAM | 0x000 | 5 | version, write count, checksum |
| Stage | 0x005 | 12 | stage type, backlash, move Z on vent, rotate limit |
| Vacuum | 0x011 | 22 | airlock, window, column pumping, bakeout, partial vent |
| **EO** | 0x027 | 936 | column calibration (below) |
| Master | 0x3cf | 475 | detectors, passwords, machine type, licences |
| Modes / Display / Acquire | 0x5aa | 1 / 1 / 5 | |
| **EHT** | 0x5b1 | 110 | filament type, anode, voltage offset, kV calibrations |

EO fields for this machine (file offset):

| Field | Value | Use |
|---|---|---|
| Stig X / Y upper, lower (0x29–0x39) | −13.4 … −19 | stigmator limits |
| Mag Comp Amp[16] (0x3d) | 42.1, 41.3, 41.2, 41, 41.1, 40.9, 47.3 ×4, 100 ×6 | line amplitude compensation per scan rate (`_gsp_set_mag_comp_amp` → DSP fast/slow line amp) **[I]** |
| Mag Comp Off[16] (0x7d, int16) | 62, 75, 75, 72, 66, 70, 70, 68, 63, 65, 0 … | line offset compensation per scan rate **[I]** |
| **C1 Cal / Rem, C2 Cal / Rem, C3 Cal / Rem** (0x9d–0xb1) | 1.0597 / 0.0101, 1.0597 / 0.0101, 0.9912 / 0.0108 | lens law §3 |
| **Mag Cal X / Y 1–5** (0xb5, 0xc9) | 29.75 / 30.63 (all ranges) | per-range scan calibration in `_gsp_set_mag` |
| Dual Mag Offset X / Y | 0 / 0 | |
| **Focus Rotation** (0xe5) | −9 | image rotation versus objective excitation (C3 rotation) |
| **Scan Orthog** (0xe9) | 1.5 | orthogonality trim (degrees) |
| Column Type (0xed) | 3 | LEO 435VP / 438VP |
| **X Talk 12 / 21** (0xee / 0xf2) | 0.0422 / 0.0422 | C1↔C2 crosstalk |
| **Apertures 1–4**: diameter, X, Y, clean (0xf6) | 30 µm (0, 0); 50 µm (0, 3 mm); 750 µm (0, 7 mm); 4: unused | aperture strip |
| Current Aperture (0x138) | 1 | 30 µm in use |
| Beam Shift Cal X / Y | 0.0512 / 0.8235 | |
| Dual Mag Gain / Slope | 95.5 / 3.9 | |
| Microshift Mag / Lever | 0.1211 / 0.1786 | |
| **Conjugate Position** (0x156) | −0.164 m | conjugate-focus plane |
| **Mag Range Cal X / Y 1–5** (0x15a, 0x16e) | X 40, 40, 93, 110, 190; Y −70, −90, −117, 40, 253 | **per-range scan centring**: 2048 + these = the captured chip 2 DAC2 / chip 3 DAC0 values exactly (2088 / 2088 / 2141 / 2158 / 2238, 1978 / 1958 / 1931 / 2088 / 2301) **[C]** |
| Gun Shift / Tilt X / Y | 0 | electronic gun alignment, unused |
| Emission Centre X / Y | 512 / 384 | |
| User Cal Factor X / Y | 1000 / 1000 | |
| EHT: Filament 3 Amps / Voltage Offset | 3.23 / 17 | |
| EHT: Calibration @ 0.1 / 10 / 24 / 30 kV | 0 | (FE only) |

## 8. Scan geometry (`gscncoil`, `gscnxfrm`) **[D]**

- **Deflection needed for a magnification M** (`_calc_scan_deflection`):
  `defl = 0.088 m · √Vr / (M · L) · (1 + cal% / 100)`.
  0.088 m is the reference image width, and L is a column distance from the scan pivot at z = −0.005 m (taken from the objective and condenser data records). So the coil drive scales with √Vr and with 1/(distance to the specimen); that is the WD dependence of the scan size **[D]**, **[I]** for the exact record fields.
- **Range selection** (`_gsp_set_mag`): five ranges with hard-coded gain steps (a data constant, then ÷8.2, ÷8.4, ÷7.2), each scaled by the scan coil sensitivity × Mag Cal X/Y[range]. The most sensitive range that fits is used. This matches the capture analysis (steps 7.7 / 8.2 / 8.4 / 7.2).
- **Coil weights** (`_gsp_recalc_scan_transforms`, `_scale_and_set_transforms`):
  - The angles used are the scan rotation S (user), the objective rotation E (from the focus state, minus a reference), E' = E − orthogonality (Scan Orthog), and the tilt correction T.
  - Four coefficients are built from them, e.g. `cT·cS·cE + sS·sE`, `cT·sS·sE' + cS·cE'`, `cT·sS·cE − cS·sE`, `cT·cS·sE' − sS·cE'` (two variants depending on configuration).
  - Each weight = amplitude(range) × coefficient + offset, clipped to 0 … 65535, and sent to the DSP. `K1 = cos(E − S)` and `K2 = sin(E − S)` are used elsewhere.
- **Stage joystick pixel size** (`_update_stage_pixel_size`): 1.1458e-4 m / M, sent to the stage controller (message 12/27). This confirms the `.SW` scaling.

## 9. What this means for the control box

Items 1–3 are implemented (§13). The original plan, for reference:
1. **kV:** compute `√Vr`, interpolate the gun table, and scale all lens excitations to keep focal lengths (I + rem ∝ √Vr). The scan deflection also scales with √Vr.
2. **WD / focus:** hold the objective as excitation `k`, step it like `_gsp_step_focus`, and compute WD from the thin-lens image of the C2 crossover. Drive the DACs with the §5.6 encoding. Update the scan rotation (Focus Rotation) and the scan size (distance term) with WD.
3. **Probe current:** implement §6.3. Compute α (auto-resolution: α_opt from Cs; or conjugate mode) and d = K_I/α, solve f1/f2 with the condenser solver, convert to currents with the crosstalk matrix, then to DACs with §5.6. Re-solve the objective for the WD afterwards.
4. **Rotation:** θ_C3 = −9°·k on every objective change (§5.7).
5. **Scan:** replace the curve-fitted per-range calibration with §8: the range steps, Mag Cal, centring from Mag Range Cal, orthogonality, and the rotation chain.
6. **Calibration** values can be imported from `Data.vac` (`analysis/datavac.py`).

## 10. Open items (decoding)

- Resolved by §6.7: the UI mode mapping, the beam-off 100 V states, the displayed-WD conversion, the condenser calibration and the gun table.
- Why LEO-32 used the LaB6 gun table and the 0.90-ish condenser calibrations (PC-side; not needed to reproduce it).
- VP: LEO-32 never knew when the column was in VP (switched from hpapp32), so its VP lens settings were the high-vacuum ones; `_set_lenses_for_HPSEM` was never used on this machine.
- Low-kV anode tables: not captured (the UI selects the spacer only with the beam off).
- The condition-layer correction tables (`_interpolate_condition_layer`, imported from the PC with `_gsp_import_condition_table` / `_gsp_import_probe_table`) and where the PC keeps them (user state files `*.MLC`, `current.mll` contain Optibeam data).
- The exact length L in the scan deflection formula, and the reference angle subtracted from θ_C3 (`_calc_E3_dependents`).
- The constants for the probe-size display terms beyond §6.2.

## 11. Measurements that would settle the model

These use the old system while it still runs, with the scope / serial loggers already set up. Each one closes a specific gap:

| # | Measurement | Closes |
|---|---|---|
| M1 | Clamp meter (or shunt voltage) on the C1, C2 and objective supply leads at 3–4 known DAC settings, beam off | absolute 3 A / 20-bit encoding and offsets (§5.6) |
| M2 | At 10 kV, type WD = 5, 10, 20, 40 mm in LEO-32 and log the objective DACs (EO fiber) plus the displayed WD; repeat at 20 kV | WD ↔ objective current, the z reference of the specimen plane (§5.3) |
| M3 | Specimen current with a Faraday cup and picoammeter at 4–6 probe-current settings (10 pA … 2 nA), logging the condenser DACs and the displayed probe current; at 5 kV and 20 kV | the probe-current law near the aperture (§6.4) and the brightness scale |
| M4 | Probe-current sweep at 10, 20 and 30 kV, logging the condenser DACs only (no meter) | direct LEO-32 condenser table per kV, a fallback even if §6.4 stays open |
| M5 | Coil weights at three WDs with the same magnification (focus change only) | objective rotation and size versus WD (§8) |
| M6 | One image of a calibration grid at a known magnification, taken through the OBI (external scan), plus the same magnification on internal scan | absolute field width / reference 0.088 m, external-scan scaling |
| M7 | Which aperture is in the beam (strip position) and its diameter, from the column or the service records | aperture diameter in the probe-current law |
| M8 | The LEO-32 Optibeam status screen (probe size, current, depth of field) for M3's settings, as screenshots | check of the probe-size terms |

M2, M4 and M5 need only the existing EO fiber capture setup. M3 needs a Faraday cup on the stage and a picoammeter (or the EO board's specimen-current input, if fitted).

## 12. Reproducing

```
cd analysis
python fdec.py "<drive>/TIGA/g200.440" _calc_excitation_for_WD _gsp_optibeam_status 0x567b0
python datavac.py "<drive>/Program Files/LEO Electron Microscopy Ltd/LEO-32/view.exe" "<drive>/LEO/Data.vac"
python optics/column_model.py
python optics/emu_driver.py          # runs LEO-32's GSP code, compares with the 5 kV captures
python optics/mlc_compare.py "<drive>/Program Files/LEO Electron Microscopy Ltd/LEO-32/user" --csv optics/mlc_points.csv
python optics/fit_capture.py --wdmap 1.19,1.9 --cal 0.9042,0.9042,0.991194 --fil 1 -v   # emulator vs captures
python optics/fit_model.py                  # firmware model fit
python optics/check_teensy.py COM18         # firmware model on the Teensy vs Python and captures
```
GSP doubles are stored with their two 32-bit words swapped. `.cinit` holds the compiled lens records, calibration defaults, gun table and aperture table.

## 13. The firmware column model **[C]**

`firmware/leo_control/optics.cpp` (prototype and fit: `analysis/optics/optics_model.py`, `fit_model.py`) computes the six lens DAC words from the settled kV, the displayed WD (`op.wd`), the probe current, the Optibeam mode and the aperture:

1. `√Vr` (kV clamped to ≥ 100 V); gun B and d₀ interpolated from the LaB6 / standard-anode table; d₀ × `eo.kd0`.
2. Internal WD = (op.wd − `eo.wd_b`) / `eo.wd_a`, limited to 1–120 mm.
3. Three passes of:
   - objective: excitation imaging the C2 crossover onto the WD (§5.3), magnification m₃ = v/u;
   - **Normal:** K = `eo.kn`·0.53·√(I/B); α = `eo.an`·((K² + K_λ²)/(3(0.278 Cs)²))^(1/8) (§6.2); condenser magnification M = K/α/(d₀·m₃). The C2 crossover z_t is placed so that the aperture (radius r at z = −0.16) defines α: z_ap − z_t = r(z_H3 − z_ap)/(α·v₃ − r). Then the condenser solver (§6.3). If C2 would need f < 3.6796 mm (or the aperture cannot reach α), C2 goes to that limit and C1 alone sets M. f₁ is limited to 4.9707–77.0 mm;
   - **Depth:** C2 at 3.6796 mm; C1 by bisection so that d₀·M·α = `eo.kd`·0.53·√(I/B), with α = r/(z_ap − z₂)·u₃/v₃;
   - **Auto resolution:** the probe current from `eo.ar2/5/10/20` (log-log), then Normal.
4. Final objective solve, currents with the crosstalk matrix (§4) and `eo.cal1..3` / `eo.rem1..3`, DAC words (§5.6).

Fitted constants (2026-11-15 captures): `eo.cal1` 0.93565, `eo.cal2` 0.9042, `eo.wd_a` 1.21696, `eo.wd_b` 1.876 mm, `eo.kn` 0.95935, `eo.an` 0.91561, `eo.kd` 12.787, `eo.kd0` 1.4625. `eo.cal3`, the remanences and the crosstalk are `Data.vac`'s.

Agreement with the 124 settled captured states (coarse DAC counts; 1 count = 0.73 mA):

| | C1 rms / max | C2 rms / max | Objective rms / max |
|---|---|---|---|
| All | 42 / 154 | 62 / 198 | 1.6 / 8 |
| Normal (101) | 42 | 48–62 | 1.7 |
| Depth (13) | 17 | 9 | 0.4 |

The largest condenser differences sit at the edge between Normal and the C2 limit (100 pA or WD 8–10 mm at 20 kV), where LEO-32 blends more gradually. That is a few % of the lens current, a small change of probe current and none of focus.

The firmware result is identical to the Python model for all 124 steps: `analysis/optics/check_teensy.py` runs them through the box's `optics` command. One computation takes about 2 ms on the Teensy.

Operator controls (as LEO-32): `wd` (and `focus`, which the box converts to the WD giving that objective current), `probe`, `obeam normal|depth|auto` and `aperture 30|50`. The lenses are computed for the settled EHT **setpoint**, so with the beam off they are already right for the kV it will come on at. `eo.model 0` restores the previous behaviour (`eo.pc*` table and direct objective DACs).
