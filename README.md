# LEO 438VP control replacement: working files

Everything generated while reverse-engineering the LEO 438VP SEM's control system: the Win98 PC running LEO-32 plus the custom ISA image-processor board. The untouched drive image stays in `C:\Users\Ben\Desktop\LEO 438VP - claude`; the analysis tools read the original binaries from there.

## Layout

| Folder | Contents |
|---|---|
| **`specifications/`** | **Start here: `LEO438VP_SYSTEM_DATASHEET.md` (summary of every subsystem and its architecture).** Detailed interface specs: `STAGE_VACUUM_INTERFACE_SPEC.md`, `VP_CONTROLLER_INTERFACE_SPEC.md`, `EHT_INTERFACE_SPEC.md`, `SCAN_GENERATOR_INTERFACE_SPEC.md` |
| `hardware/leo_control_box/` | KiCad 10 project for the Teensy 4.0 control box (schematic rev 0.1, PCB rev 0.1). See its README |
| **`firmware/`** | **Teensy 4.0 control-box firmware (`leo_control/`), the USB protocol for the PC page (`PROTOCOL.md`) and every runtime setting (`SETTINGS.md`). See `firmware/README.md`** |
| `design/` | Design notes, e.g. the Glasgow pin plan |
| `scope_tools/` | Tektronix MSO24 control and scan-fiber decoding scripts (`arm_burst.py`, `wait_grab_decode.sh`, `decode_scan_fiber.py`, …) and `SCAN_FIBER_NOTES.md` (working notes and test log) |
| `scope_captures/` | Scope captures (`.npz` waveforms, `.png` screens, `_ch3.txt` decodes) and the annotated `scan_fiber_timing.png` |
| `capture_tools/` | Live serial capture: Teensy 3.2 logger firmware, `capture_serial.py`, `decode_serial_log.py`, the protocol write-ups, and every capture. See `capture_tools/README.md`. |
| `capture_tools/captures/` | Raw logs (`<date>_<time>_<tag>.log`), operator notes, decoded timelines and CSVs. |
| `capture_tools/teensy_blink_test/` | Blink sketch used to check the Teensy toolchain. |
| `report/` | The static-analysis report (`leo438vp_report.html`, also published as a claude.ai artifact) plus the section drafts and diagrams it was built from. |
| `analysis/` | Python tools for the original binaries, and their outputs (see below). |
| `notes/memory/` | Copy of Claude's project memory (decisions and requirements from the user). |

## Protocol and requirements documents

All in `capture_tools/`:

- `STGVAC_PROTOCOL.md`: stage / vacuum link (UART B, 9600 8N1): polls, pressure conversion, stage counts, thresholds and interlocks.
- `VP_PROTOCOL.md` and `VP_TEST_PLAN.md`: VP controller on PC COM2: hpapp32 commands, states, gauge and setpoint encodings, watchdog.
- `EHT_PROTOCOL.md`: EHT / gun supply link (UART A): commands and encodings, `.O` supply bits, status bits and fault map, ramp sequences, and the VP-mode scintillator behaviour.
- `REPLACEMENT_REQUIREMENTS.md`: rules the new controller must enforce, for example cooling the filament before any pressure change.

## Analysis tools (`analysis/`)

Run them with the original files as arguments, for example `python t34.py "<orig>/TIGA/g100.440" _eht_fault_monitor`.

| Tool | Purpose |
|---|---|
| `coff.py`, `t34.py`, `t340.py` | TI COFF parser and TMS34010/34020 disassembler with relocations and symbols (GSP modules such as `g100.440`) |
| `adsp.py` | Partial ADSP-21xx disassembler (scan-generator DSP code) |
| `ne.py`, `nedis.py`, `mzio.py` | 16-bit NE / MZ executable parsing and disassembly |
| `peinfo.py`, `xref32.py`, `strs.py` | PE32 inspection, string cross-references, string extraction |
| `argtrace.py`, `calls.py`, `cinit.py`, `ext.py`, `movi.py`, `rec.py`, `scanio.py`, `g900map.py` | Call/argument tracing, TIGA extension tables, scan I/O and EO register mapping |
| `syms/` | Symbol dumps of every GSP module |
| `*_tables.txt`, `*_exports.txt`, `eo_calls.txt` | Extracted TIGA extension tables, exports and EO register call lists |
| `patch8.py`, `patch9.py` | One-off report-editing scripts (historical) |

## Status (2026-11-13)

- Decoded and captured live: stage / vacuum, VP controller and EHT links (serial, Teensy logger).
- Scan-generator fiber link (rev 1.1 spec, incl. beam-on tests: probe current, EHT / kV scaling, Optibeam modes, averaging, board hardware): cold boot, all scan speeds 0-15, magnification sweep with every range, rotation, tilt correction, beam shift, focus / WD / Optibeam / aperture, stigmators, dynamic focus, focus wobble, reduced area / line / spot / external scan, freeze modes. See `specifications/SCAN_GENERATOR_INTERFACE_SPEC.md`.
- Next: design of the replacement IP board. Open items before that: detector video characteristics, F1 / F2 meaning, HRRU, transceiver part numbers (summary datasheet §8).

## How to resume scope captures

1. Scope on the "Ethernet 3" network at 192.168.0.42; probes CH1–CH3 on the IP→EO fibers, CH4 on EO→IP.
2. `cd scope_tools`, then `python scope_setup.py save`.
3. Easiest: run `python cold_boot_loop.py <prefix> [shots] [minutes] [high_limit_us]` in the background; it re-arms after every shot and writes `<prefix>_NN.npz`, `_ch3.txt` and `<prefix>_log.txt` (trigger wall-clock times). `high_limit_us = 2750` catches single writes but only works at scan speed 5 in full frame and not while dynamic focus is on; `100` (default) catches bursts at any speed. About 17 s dead time per shot. Stop it with `touch STOP` in `scope_tools/`.
   Alternative, one shot at a time: `python arm_burst.py`, then `./wait_grab_decode.sh <tag>`, change one control, then `python summarize_burst.py <tag>`.
4. Finish with `python scope_setup.py restore` (if it cannot connect right after the loop stops, retry after ~15 s).

## Version history (git)

This folder is a local git repository (no remote; nothing is uploaded anywhere). Claude commits after each meaningful change so any earlier version can be restored. Raw scope waveforms (`scope_captures/*.npz`, 6.8 GB) are excluded via `.gitignore`; their decoded `_ch3.txt`, screenshots and logs are tracked. Line-ending conversion is off (`core.autocrlf false`) so KiCad files are stored byte-for-byte.

Useful commands if you ever want them: `git log --oneline` (list versions), `git show <id> --stat` (what changed), `git checkout <id> -- <file>` (restore one file from an earlier version).
