---
name: performance-tests-after-bringup
description: List of performance improvements to test once the new system is brought up; first item is the tungsten gun table (eo.gun 1)
metadata:
  node_type: memory
  type: project
  originSessionId: 71aedc35-0b75-4cc5-9e18-af273a365c71
  modified: 2026-11-16T04:14:27.810Z
---

The user asked (2026-11-15) for a list of possible performance improvements, to be tested after bring-up of the new system. It lives in `notes/PERFORMANCE_TESTS.md` in the Complete_438VP_control repo. Item 1, the first to test, is `eo.gun 1`: the column model uses the tungsten gun table instead of the LaB6 data LEO-32 used. The default `eo.gun 0` matches the old system. Estimated gain: ~8 % smaller probe at equal current at 20 kV.

**Why:** the new system should first reproduce LEO-32, then improve on it in measured steps.

**How to apply:** when bring-up is done, or when the user asks what to improve, bring up this list starting with item 1. Add new improvement ideas to the same file rather than acting on them right away. Related: [[electron-optics-model]].
