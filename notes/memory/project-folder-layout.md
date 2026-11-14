---
name: project-folder-layout
description: Where LEO 438VP work lives — new files in Complete_438VP_control, original drive image untouched in "LEO 438VP - claude"
metadata:
  type: project
---

On 2026-11-12 the user split the project into two folders:
- `C:\Users\Ben\Desktop\LEO 438VP - claude`: the original Win98 drive image only. It must stay free of new files.
- `C:\Users\Ben\Desktop\Complete_438VP_control - claude`: everything generated. That covers capture_tools/ (Teensy firmware, capture/decode scripts, protocol docs, captures), report/, analysis/ (binary-analysis tools that take original files as arguments) and notes/memory/. Its README.md is the index.

**Why:** the user wants new work kept separate from the original files.

**How to apply:** write new files only in Complete_438VP_control, and read originals from the old folder. Next planned work is the scan-generator fiber link (the user is surveying it with an oscilloscope first). Related: [[filament-off-for-pressure-changes]].
