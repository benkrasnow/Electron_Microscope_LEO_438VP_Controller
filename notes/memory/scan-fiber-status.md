---
name: scan-fiber-status
description: LEO 438VP EO/scan fiber link fully decoded (spec rev 1.1, 2026-11-13); summary datasheet exists; next phase is designing the replacement IP board
metadata:
  type: project
---

As of 2026-11-13 the EO board fiber link is decoded, including beam-on tests (probe current, kV: weights and objective scale with sqrt(relativistic kV), angles unchanged; Optibeam depth / auto-resolution modes; split scan; line averaging = chip 3 r0A = N-1). Detail: specifications/SCAN_GENERATOR_INTERFACE_SPEC.md rev 1.1 and scope_tools/SCAN_FIBER_NOTES.md. Summary of all four subsystems: specifications/LEO438VP_SYSTEM_DATASHEET.md.

Facts from the user: EBBU beam blanker not fitted; gun shift/tilt and aperture are manual; capture is limited to 1024x768 (a main reason to replace the hardware); the user never uses averaging modes.

Open before / during the replacement IP board design: detector video characteristics (coax level, bandwidth), F1/F2 meaning (believed acquisition gates), HRRU remote-bus target, fiber transceiver part numbers, C1/C2 pairing and A/B coil pins, external-scan path test.

**Why:** the user's next step is detailed instructions for designing a replacement image-processing board.

**How to apply:**
- Scope: Tektronix MSO24 at 192.168.0.42 via pyvisa-py VXI-11. CH1-CH3 = IP->EO fibers, CH4 = EO->IP. Save the user's setup first, restore after.
- Use scope_tools/cold_boot_loop.py (auto re-arm; trigger high limit 2750 us catches single writes at speed 5 full frame only; 100 us for bursts). Stop it with a STOP file, not kill (stale VXI-11 link otherwise).

Related: [[project-folder-layout]], [[filament-off-for-pressure-changes]].
