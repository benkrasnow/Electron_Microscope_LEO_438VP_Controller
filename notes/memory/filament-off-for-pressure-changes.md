---
name: filament-off-for-pressure-changes
description: LEO 438VP replacement controller must cool the filament (zero current, not just EHT off) before any chamber pressure change
metadata:
  type: project
---

The replacement SEM control system must shut the filament off completely (full shutdown with ramp-down, not "EHT off", which leaves the filament lit) and let it cool before any chamber pressure change: VP transitions, return to HV, or vent. This is recorded in capture_tools/REPLACEMENT_REQUIREMENTS.md.

**Why:** the user says an unintended blast of air hitting a hot filament shortens its life. Beam-off during pressure changes is acceptable because they are quick and infrequent.

**How to apply:** when designing the replacement controller's state machine, interlock VP-controller commands on filament current = 0 plus a cool-down delay. Related: [[project-folder-layout]].
