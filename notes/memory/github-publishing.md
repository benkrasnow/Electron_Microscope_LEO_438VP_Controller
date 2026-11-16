---
name: github-publishing
description: Complete_438VP_control is pushed to public GitHub repo benkrasnow/Electron_Microscope_LEO_438VP_Controller; capture data and decompiled LEO-32 text stay local
metadata:
  node_type: memory
  type: project
  originSessionId: 71aedc35-0b75-4cc5-9e18-af273a365c71
  modified: 2026-11-16T04:56:22.818Z
---

On 2026-11-15 the user asked to publish the project to https://github.com/benkrasnow/Electron_Microscope_LEO_438VP_Controller (public, remote `origin`, branch `main`).

The user chose:
- Push: KiCad files, firmware, web UI, specs, reports, analysis scripts and our own derived results, and notes/memory.
- Keep local only (in `.gitignore`):
  - all scope captures except `scope_captures/scan_fiber_timing.png`;
  - `capture_tools/captures/` (serial sniff logs);
  - decompiled / disassembled dumps of LEO-32 binaries (`analysis/syms/`, `analysis/optics/part*/scan*/g200_optics_dec/obeam_*/view_fields.txt`, `analysis/*_tables.txt`, `*_exports.txt`, `eo_calls.txt`, `ext_html.txt`, `*.pkl`).

History was rewritten to drop these. The pre-rewrite bundle is `Desktop/Complete_438VP_control_backup_2026-11-15.bundle`.

**Why:** the repo is public. Raw capture data is bulky, and decompiled proprietary code shouldn't be published.

**How to apply:**
- Never commit new capture data or decompiled LEO-32 listings. Put new outputs of that kind under ignored paths, or ask.
- Commits are still made locally after each change. Push only when the user asks (until they say otherwise).
- When unsure whether a file belongs on GitHub, ask.

Related: [[project-folder-layout]].
