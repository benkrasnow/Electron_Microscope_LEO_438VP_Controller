---
name: electron-optics-model
description: LEO 438VP lens/Optibeam physics decoded from g200.440; Data.vac holds per-machine lens calibration (user flagged Data.vac as important)
metadata:
  node_type: memory
  type: project
  originSessionId: 71aedc35-0b75-4cc5-9e18-af273a365c71
  modified: 2026-11-15T23:28:49.996Z
---

2026-11-15: LEO-32's column model was decoded from TIGA/g200.440 (source files gcondens, gfocus, geht, goptctrl, gcolmod) with analysis/fdec.py; written up in specifications/ELECTRON_OPTICS_MODEL.md. Lens law k = N(I+rem)/(cal*sqrt(Vr)), f(k^2) per lens, C1/C2 crosstalk, WD solver, gun table, probe-size terms. Objective law cross-checked against captured DACs (~1.6 mA per coarse count).

C:\LEO\Data.vac (in the drive image) is LEO-32's packed non-volatile machine data: it holds the C1/C2/C3 cal/rem and crosstalk (matching 435vpcal\LEO 438V.clb) and aperture diameters. The user pointed to it ("has been important in the past").

Later the same day, a TMS34020 emulator was added (analysis/gspemu.py + optics/emu_driver.py) that runs LEO-32's own GSP code. LEO-32's user/*/*.MLC conditions files hold real operating points (kV, displayed WD, probe current, aperture, C1/C2/C3 currents), compared by optics/mlc_compare.py.
- Results so far: the objective matches given the GSP WD; displayed WD ≈ 1.19·GSP WD + 1.9 mm, a PC-side transform. C2 is close.
- C1 is still too high and depends on state that isn't saved.
- Next step is PC-side (leom.exe / m200.dll) or measurements M2/M8. Spec rev 0.5, §6.5–6.6.

Status as of 2026-11-15: the firmware drives the lenses from a fitted column model (optics.cpp, commit 026b048; spec rev 0.6 §6.7/§13), checked against 124 captured states. What made the fit work:
- displayed WD is rescaled by the PC (internal = (WD − 1.876 mm)/1.217);
- LEO-32 used the LaB6 gun table and effective condenser cals of about 0.936 / 0.904;
- the UI modes map as Normal = GSP mode 0, Depth = mode 1, Auto = a separate flag;
- with the beam off LEO-32 computed a 100 V column from the EHT readback, so beam-off EO captures are not usable kV data.

**Why:** the control box firmware currently uses a 4-point probe-current table; the decoded model is the basis for replacing it with real kV/WD/probe/focus physics.

**How to apply:** start from the spec's §8 (implementation) and §9 (open items: DAC coarse/fine scaling, condition-layer tables). Related: [[scan-fiber-status]], [[replacement-plan-obi-glasgow]].
