# Performance improvements to test after bring-up

Ideas where the new system could do better than LEO-32. Work through them once the control box, OBI imaging and the web page run the microscope reliably with the LEO-32-compatible defaults. Each item names its switch, what to compare, and what is expected.

## 1. Tungsten gun table for the column model (`eo.gun 1`)

**Background.** LEO-32's lens model ran on its LaB6 gun data, although `Data.vac` configures a tungsten filament (probably an off-by-one filament index; `specifications/ELECTRON_OPTICS_MODEL.md` §6.7). The box reproduces that by default (`eo.gun 0`). `eo.gun 1` uses the tungsten table instead; the other fitted constants are unchanged.

**Expected (estimate, not measured).**
- Probe current for a given setting: about the same (brightness × source area agrees within 3 % at 20 kV, 12 % at 5 kV).
- Resolution mode: about 20 % larger convergence angle and stronger demagnification, so roughly 8 % smaller probe at the same current at 20 kV. Probably less at low kV, where chromatic aberration (not in the optimisation) dominates.
- Lens values: C1 / C2 move by hundreds of DAC counts (e.g. 20 kV, WD 20 mm, 200 pA: C1 1001 → 1607, C2 1034 → 734 coarse).

**Test.**
1. Resolution sample (e.g. gold on carbon or tin balls), 20 kV, WD ~10 mm, high magnification, Resolution mode, a few probe currents (50, 200, 1000 pA).
2. At each current, image with `eo.gun 0` and `eo.gun 1`, refocusing and restigmating each time, same dwell and PMT setting.
3. Compare edge sharpness (e.g. 25–75 % edge width) and noise. Optionally measure specimen / Faraday-cup current to see whether the current changes as predicted.
4. Repeat at 5 kV.

**Before testing.** Check the firmware against the Python model with both tables: `python analysis/optics/check_teensy.py COM18 1` (it sets `eo.gun` and restores it to 0). This hasn't been run on the Teensy yet: the port was in use when the switch was added on 2026-11-15.

**Decide.** Keep `eo.gun 1` only if images are measurably sharper at equal current. If so, refit the Normal-mode constants (`eo.kn`, `eo.an`, `eo.kd0`) for tungsten physics rather than for matching LEO-32.
