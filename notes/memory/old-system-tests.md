---
name: old-system-tests
description: Checks to run on the old LEO-32 PC are listed in notes/OLD_SYSTEM_TESTS.md (Go To VP / hpapp32 start-order checks)
metadata:
  node_type: memory
  type: project
  originSessionId: 71aedc35-0b75-4cc5-9e18-af273a365c71
  modified: 2026-11-16T04:56:26.774Z
---

On 2026-11-15 the user asked that the three hpapp32 / "Go To VP" suggestions be kept as things to test. They are in `notes/OLD_SYSTEM_TESTS.md` in Complete_438VP_control:
1. hpapp32 title must be exactly "Untitled - hpapp32".
2. Read the VP Control panel Status (Initialise = no m600 link).
3. Start hpapp32 by hand before LEO-32 (rename trick, untested).

The background is in the VP spec §7.1.

**Why:** a working VP mode on the old system would let us capture VP-mode EO values and the detector switchbox drive.

**How to apply:** when the user is at the old PC or asks about VP, bring up this list. Add new old-system checks to the same file. Related: [[filament-off-for-pressure-changes]], [[performance-tests-after-bringup]].
