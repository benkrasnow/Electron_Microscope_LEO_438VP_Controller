---
name: replacement-plan-obi-glasgow
description: User plans to replace the Win98 PC + IP board with the Open Beam Interface (Glasgow revC3) driving all LEO 438VP links; no OBI Python UI
metadata:
  type: project
---

Plan (stated 2026-11-13): use the Open Beam Interface (https://github.com/nanographs/Open-Beam-Interface, Glasgow Interface Explorer revC3, iCE40HX8K) to control the whole LEO 438VP. The user already uses OBI on this microscope for high-resolution imaging (OBI scans via the EO board's external scan input). Spare Glasgow pins should drive the fiber links (EHT, stage/vacuum, EO F1-F4) and the VP RS-232 port.

- Fiber parts in the user's build: Avago HFBR-1521Z transmitter (660 nm, 5 MBd) and HFBR-2521Z receiver (5 MBd), used for all links (the original used different parts for slow and fast links).
- The user does NOT want to use OBI's Python UI (unreliable, hard to install).
- The old Win98 PC is becoming unreliable; running two computers is cumbersome.

Verified 2026-11-13: OBI analog board uses only the Glasgow LVDS connector; Port B fully free, Port A free except OBI scan_enable (A0); the user also wants internal digital scan (F1/F2) as a backup. Pin plan: design/GLASGOW_PIN_PLAN.md.

Decision 2026-11-13: use a separate microcontroller control box (Teensy 4.1 / RP2350 class) for EHT, stage/vacuum, VP and EO fibers, enforcing safety and machine state independently of the PC; OBI/Glasgow stays for imaging. EO internal scan kept as a backup, optionally synced to OBI via F2 into a spare OBI pin (needs OBI gateware support, not stock).

Update 2026-11-14: the control box (Teensy 4.0, hardware/leo_control_box) does NOT handle the PMT signal or its gain (separate hardware does), and has no knob/lever inputs; only a spare I2C Qwiic port remains.

**Why:** shapes every design decision for the replacement controller.

**How to apply:** design gateware/hardware additions inside the OBI/Glasgow environment and a separate, simpler host UI; keep the safety rules in [[filament-off-for-pressure-changes]]. Related: [[scan-fiber-status]].
