# VP ("Orsay") controller link: PC COM2 ⇄ VP control board

Physical: RS-232, 9600 8N1 (`COM2:9600,n,8,1` in hpapp32). ASCII commands from the PC, each ending in CR LF.
Program on the PC: `hpapp.exe` ("hpapp32", 1998). Settings live in `C:\WINDOWS\LEO.INI` `[HPAPP]`: `Port=2`, `MonitorInterval=4`, `OrsayBoardTimeout=300`, `Comms Timeout=2000`, `Setting gain=1.094`, `Setting offset=190.`, `Debug=YES`.
Capture wiring: ch3 = PC TXD (DB9 pin 3) and ch4 = PC RXD (DB9 pin 2), each through a series resistor and clamp diodes, both **inverted** (`I 3 1`, `I 4 1`).

Sources: `hpapp.exe` disassembly (string table at 0x444C40, state table at 0x4434E4) and capture `20261112_145539_vp_pumpdown_and_vp_mode.log`.

## Commands (PC → VP controller)

| Command | Meaning | Evidence |
|---|---|---|
| `GP` | **Get status poll**, every 4.014 s. Reply `<gauge>,<state>,<requested>,<V8>,<V14>,<error>` (see below) | capture; `MonitorInterval=4` |
| `TO n` | **Go to state n** (table below). Rejected → "GotoState rejected: <state>" | `TO %d` at 0x444D8C, names at 0x4434E4 |
| `RE 0` | Reset / clear errors. First command at hpapp start (retried once); also used by the "reverse" (abort VP) routine | strings "RE 0 Rejected!", "Second RE 0 Rejected!", "Reverse failed/OK" |
| `RE 1` | Reset the controller to POWER_UP. Sent at start-up if the state is not POWER_UP; hpapp then waits up to 5 s for state 0 | "Current State != Power On!" |
| `ST 1,n` | Comms watchdog timeout, n = `OrsayBoardTimeout` (300 s) | "Comms timeout command rejected!" |
| `ST 2,10` | "MCP up" timeout, 10 s | "MCP up command rejected!" |
| `ST 3,90` | "MCP down" timeout, 90 s | "MCP down command rejected!" |
| `ST 4,240` | Target timeout, 240 s | "Target timeout command rejected!" |
| `ST 5,5` | Gun-enable timeout, 5 s | "Gun enable timeout command rejected!" |
| `HP a,b,c` | Set chamber pressure target; c = setpoint in controller counts (see below). Default path sends `HP 0,10000,c` | `HP %d,%d,%d` |
| `MC x,900` | MCP crossover setting; x = 100 for targets ≤ 10 Pa, otherwise 0.8 × raw gauge counts of the target. Exact meaning of the pair is unknown (x exceeds 900 for targets ≥ 50 Pa) | `MC 100,900`, `MC %d,900` |
| `GM` | Used by the reverse/abort routine (probably "get mode") | |

Start-up sequence (when hpapp starts): `RE 0` → (`RE 1` + wait for POWER_UP if needed) → `ST 1,300` → `ST 2,10` → `ST 3,90` → `ST 4,240` → `ST 5,5` → `TO 2` (at air) or `TO 3` (pumped).

## States (`TO n`)

| n | State | Sent by hpapp for SEM message |
|---|---|---|
| 0 | POWER_UP | — |
| 1 | AT_AIR_HP | HP_REQUIRED_1, HP_PUMPING_OFF_HP |
| 2 | AT_AIR_LP | LP_REQUIRED_1, HP_PUMPING_OFF_LP, start-up at air |
| 3 | PUMPING_LP | HP_PUMPING_ON, HP_PUMPING_ON_LP, start-up when pumped |
| 4 | GUN_ENABLE_OK | — |
| 5 | READY_TO_PUMP | HP_PUMP |
| 6 | READY_TO_VENT | HP_VENT_N |
| 7 | WAIT_ABOVE_MCP | HP_REQUIRED_2, HP_REQUIRED_3 (pumped → VP) |
| 8 | GOING_TO_HP | HP_REQUIRED_4, HP_PUMPING_ON_HP |
| 9 | AT_HP | — (reached by the controller) |
| 10 | WAIT_LESS_MCP | LP_REQUIRED_2, _4, _5 (VP → high vacuum) |
| 11 | GUN_ENABLE_DELAY | LP_REQUIRED_3 |

LP = low chamber pressure (normal high vacuum); HP = high chamber pressure (VP mode). MCP is a crossover pressure.
Valve states: 12 Closed, 13 Closing, 14 Opened, 15 Opening, 16–19 Fault1–4.
Error texts: CIV_Closing / CIV_Opening time_out (CIV = chamber isolation valve), Rotary_Closing / Rotary_Opening time_out, MCP time_out, Target time_out, Com time_out, Reset, Reversing pending, Reversed_failed, Reversed_ok.

Likely sequence pumped → VP: `TO 7`: close the chamber isolation valve (turbo keeps pumping the gun), admit gas until the chamber is above MCP (10 s timeout) → `TO 8`: regulate to the `HP` setpoint (240 s timeout) → state 9 AT_HP. Return: `TO 10`: pump the chamber on the rotary until below MCP (90 s timeout) → `TO 11`: gun-enable delay → `TO 3`.

## Chamber gauge and setpoints
hpapp converts Pa → volts with a built-in table for a Pirani-type gauge (0 Pa = 2.00 V, 1 Pa = 2.99 V, 10 Pa = 4.49 V, 100 Pa = 6.35 V, 1000 Pa ≈ 8.84 V, 2240 Pa = 9.40 V; clamped 2–10 V). Then:

    raw      = (V + 0.01706) / 0.005005
    setpoint = raw × gain + offset          (gain 1.094, offset 190 from LEO.INI)
    above 250 Pa the setpoint is multiplied by 1 + 0.015 × (P − 250 Pa)/250 Pa

| Target | Volts | `HP` setpoint | `MC` |
|---|---|---|---|
| 0 Pa | 2.000 | ≈630 | `MC 100,900` |
| 10 Pa | 4.490 | ≈1175 | `MC 100,900` |
| 20 Pa | 5.104 | ≈1309 | `MC 818,900` |
| 50 Pa | 5.737 | ≈1447 | `MC 919,900` |
| 100 Pa | 6.345 | ≈1580 | `MC 1016,900` |

"0 Pa" in the hpapp window at high vacuum is therefore normal: this gauge only reads the VP range.

## What happened on 12 Nov 2026 (capture 20261112_145539)

| Time | Event |
|---|---|
| 14:56:35 | `.VL P` on the stage/vacuum link; hpapp sends **`TO 3`** automatically 1.4 s later (HP_PUMPING_ON) |
| 15:01:06 | interlock bit 3 clears at gauge value 256: **the same click as on the previous pump-down** (257) |
| 15:04:50 | `SPVR`: vacuum ready |
| 15:08:38 | manual `TO 3`: no change, the controller was already in PUMPING_LP |
| 15:09:20 | manual **`TO 7`** (WAIT_ABOVE_MCP) |
| 15:09:24.7 | **4.7 s later** the stage/vacuum controller reports `NSP` (Penning off: chamber far above high vacuum), `=20`, `.VS` = `0F 02 …`; LEO-32 applies the vented X/Y limits |

Observations:
- No `HP` or `MC` was sent during this session, so the controller ran `TO 7` with whatever target and crossover values it had stored (or none).
- `TO 7` is the correct first step for a pumped → VP change, but normally LEO-32 drives it. VP controls were greyed out in the UI, so this run bypassed the SEM's own sequence.
- Without the controller's replies we can't tell whether it then reached MCP, whether the gauge ever read above 0 Pa, or whether it timed out. A gauge stuck at 0 Pa (2 V) would explain a full vent: the controller keeps admitting gas because it never sees the pressure rise.

## Controller replies (capture 20261112_153419, ch4 = COM2 RXD)

Every command is answered with the prompt `HP>` + CR, then CR LF. `GP` returns a status line before the prompt:

    <gauge>,<state>,<requested>,<V8>,<V14>,<error>HP>\r  \r\n
    e.g.  399,3,3,2,0,0      1047,9,9,0,2,0

| Field | Meaning | Values seen |
|---|---|---|
| gauge | chamber (Pirani) reading in raw counts, `V = counts × 0.005005 − 0.017` | ~2011–2025 at air (≈10 V, over range), ~399–400 at high vacuum (≈2.0 V = 0 Pa), 1044–1059 in VP (≈5.2 V ≈ 25 Pa) |
| state | current state (`TO` table) | 0, 2, 3, 7, 9 |
| requested | state last requested / being moved to | follows `TO`; the controller advances 7 → 8 → 9 itself |
| V8 | chamber isolation valve: 0 closed, 1 closing, 2 open | 2 in high vacuum, 1 → 0 after `TO 7` |
| V14 | VP (rotary) pumping valve: 0 closed, 2 open | 0 in high vacuum, 2 in VP |
| error | error code | 0 throughout |

Controller power-up banner: `Interface HP OK` `HP>`, then `100` (probably firmware 1.00).

### hpapp start-up handshake as observed (15:37:54, LEO-32 start, system at air)
`RE 0` → `GP` (state 0, POWER_UP, so no `RE 1`) → `ST 1,360` → `ST 2,10` → `ST 3,90` → `ST 4,240` → `ST 5,5` → `GP` → `TO 2` → `HP 883,917,1175` + `MC 100,900` (the stored 10 Pa target). Each command answered `HP>` within ~10 ms.
`ST 1` was **360** on this machine (the drive image's LEO.INI had `OrsayBoardTimeout=300`).

### Target slider in the LEO-32 UI
Each slider step sends `HP a,b,c` + `MC x,900` about every 0.5 s while dragging. The final values for 301 Pa were `HP 1478,1527,1839` and `MC 1202,900`, which matches the formula (c = 1839.6, MC = 0.8 × raw 1503 = 1202). The first two `HP` values move with the target (e.g. 883/917 at 10 Pa, 1478/1527 at 301 Pa), probably the lower/upper edges of a regulation band; manual `HP 0,10000,c` also worked.

### Successful manual VP transition (15:48–15:51)
| Time | PC → VP | Reply |
|---|---|---|
| 15:48:47 | `MC 818,900` | `HP>` |
| 15:49:56 | `HP 0,10000,1309` (20 Pa) | `HP>` |
| 15:50:43.1 | `TO 7` | `HP>` |
| 15:50:44.8 | | `400,3,7,1,0,0`: still PUMPING_LP, V8 closing |
| 15:50:48.8 | | `1059,7,8,0,0,0`: above MCP, V8 closed, moving to GOING_TO_HP |
| 15:50:52.8 | | `1055,9,9,0,2,0`: **AT_HP**, V14 open, regulating |
| → 15:52:41 | | gauge drifts 1055 → 1044 (≈25 → 23 Pa) towards the 20 Pa setpoint, error 0 |

The stage/vacuum link stayed at `SPVR 303` throughout: the Penning gauge on the turbo/gun side kept reading high vacuum, so the column stayed protected. In the earlier failed attempt (14:55 session) the Penning dropped to `NSP` within 4.7 s of `TO 7`, meaning gas reached the turbo side.

### Why the VP controls may have been greyed out (hypothesis from the code)
hpapp's start-up routine aborts if the controller is not at POWER_UP and does not return there within 5 s of `RE 1` ("Current State != Power On!"). It then skips the `ST`, `TO`, `HP` and `MC` setup, and LEO-32 falls back to "SEM set to LP mode only". This time the controller had just been power-cycled (state 0), the handshake completed, and the VP slider worked. Test: restart only LEO-32 (not the microscope) while pumped, and check whether `RE 1` brings the controller back to state 0 within 5 s.

## Return from VP to high vacuum (capture 20261112_155926)

| Time | PC → VP | Reply (gauge,state,req,V8,V14,err) | Meaning |
|---|---|---|---|
| 15:59:26 | | `1034,9,9,0,2,0` | AT_HP ≈ 22 Pa |
| 16:00:14.9 | `TO 10` | `HP>` | |
| 16:00:18.9 | | `1004,10,10,0,2,0` | WAIT_LESS_MCP: rotary pumping the chamber via V14 |
| 16:00:39.0 | | `901,10,11,0,0,0` | gauge reached the down threshold (900), V14 closed, next = 11 |
| 16:00:43.0 | | `447,11,11,2,0,0` | V8 (chamber isolation) open → turbo takes the chamber; GUN_ENABLE_DELAY |
| 16:00:51.0 | | `409,4,4,2,0,0` | **GUN_ENABLE_OK** (reached by the controller itself, ~8 s) |
| 16:03:22.4 | `TO 11` | **`255`** | rejected / invalid in this state (not needed) |
| 16:04:09.8 | `TO 3` | `398,3,3,2,0,0` | PUMPING_LP: normal high-vacuum state |

So the controller steps 10 → 11 → 4 by itself after a single `TO 10`. `TO 3` then returns it to the normal pumped state (hpapp sends `TO 3` for HP_PUMPING_ON / _LP). A reply of `255` instead of a status line means the command was refused.

**`MC` decoded:** `MC <up>,<down>` are gauge thresholds in raw counts. Going to VP, the controller waits until the gauge is above `<up>` (818 for a 20 Pa target, 100 for ≤ 10 Pa) before moving 7 → 8. Coming back, it waits until the gauge is below `<down>` = 900 (≈ 4.5 V ≈ 10 Pa) before closing V14 and opening V8.

Main Penning gauge (stage/vacuum link `.VT`) during the return: 1.2e-5 Torr while in VP (only the gun/column side on the turbo), a jump to **1.38e-4 Torr** when V8 opened at 16:00:40, then recovery to 6.6e-5 Torr by 16:05. The state stayed `SPVR` (vacuum ready) throughout even above 1e-4 Torr. This supports reading the second threshold level ("50" ≈ 4.9e-4 Torr) as a re-inhibit level (hysteresis).

## Complete working VP cycle (manual, hpapp "send command")
1. At high vacuum, state 3: `MC <up>,900`, `HP a,b,<setpoint>` (or let the LEO-32 target slider send them).
2. `TO 7` → 7 → 8 → 9 (AT_HP) in ~10 s.
3. Return: `TO 10` → 10 → 11 → 4 (GUN_ENABLE_OK) in ~35 s, then `TO 3`.

## Vent and pump from the LEO-32 UI with all four links (capture 20261112_161149)

| Time | Link | Event |
|---|---|---|
| 16:12:40.5 | STGVAC | `.VL V` (vent) → `WVT`, `=20` → `.VS 0F …` (all four inhibits on) |
| 16:12:57.9 | STGVAC | `NSP` (at air) after 17 s; IP board sends the vented X/Y limits (35–65 mm) |
| 16:12:58.2 | VP | **`TO 2`** (AT_AIR_LP), sent only once the stage/vac controller reports at air. The VP controller stayed in state 3 during the vent (gauge 397 → 1716) |
| 16:13:01.7 | VP | `1948,2,2,2,0,0`: AT_AIR_LP, V8 open, V14 closed |
| 16:15:13.9 | STGVAC | `.VL P` (pump) → `WTUS` |
| 16:15:15.7 | VP | **`TO 3`** (PUMPING_LP) 1.8 s later. No `TO 5` / `TO 6` are used in LP mode |
| 16:15:18 → 16:16:34 | VP | chamber gauge 2018 → 436 (rough pumping, ~75 s) |
| 16:16:43 / 16:16:53 | STGVAC | `WP` → `SP`, `.SJ` / `.SQ` re-sent (full range) |
| 16:16:55.6 | STGVAC | `=20` → `.VS 07`: inhibit bit 3 released at Penning raw 258 → **operator heard a click at 16:16:54** |
| 16:17:26.6 | STGVAC | `SPVR` (ready), `=20` → `.VS 00`: inhibit bits 0–2 released → **operator heard a click at 16:17:28** |

Notes:
- The stage was uninitialised in this run, so there was no Z-down move before the vent (the cold-boot capture, with the stage initialised, showed Z driven to 0.5 mm first).
- The VP controller is told about vent and pump only through `TO 2` / `TO 3`. It plays no active part in a normal high-vacuum vent/pump; the stage/vacuum controller does the pumping and venting.
- Bit 3 has now released at raw 256–258 in four separate pump-downs (≈1.14e-4 Torr), well before the 302 thresholds that `.TA`–`.TE` program. It is a fixed level, probably internal to the vacuum controller.
- Pump-down from air to ready took 2 min 13 s this time (turbo speed at 16:16:43, ready at 16:17:27), much faster than earlier runs because the chamber walls had been baked out by the previous cycles.

## Comms-loss / watchdog test (capture 20261112_162701)

Setup: high vacuum, ready, EHT off. COM2 cable unplugged at the VP board end ~16:27:30, reconnected 16:38:10. Taps on the PC side.

| Time | Observation |
|---|---|
| 16:27:04 | last normal reply `394,3,3,2,0,0` (PUMPING_LP) |
| 16:27:32 – 16:27:40 | three unanswered `GP` 4 s apart (hpapp log: "COM time out!" ×3) → LEO-32 dialog "VP Control Comms Error", VP status "VP mode error", leolog Error 555 "VP Control Comms Error: 6" |
| 16:28:00 → 16:38:03 | hpapp keeps sending only `GP`, now every **20.1 s**. No `RE`, `ST` or `TO`. Nothing changed on the stage/vacuum link |
| 16:38:23 | first reply after reconnecting: **`395,0,0,2,0,0`**: POWER_UP, V8 open, V14 closed, error 0 |
| after | polling back to every 4 s; the controller stays in POWER_UP and hpapp sends no handshake or `TO`, so the status stays "Power Up" |

(The `FF FF FF FF` groups on the VP→PC channel while unplugged are the PC's own `GP` transmissions coupling onto the floating RXD line, not controller output.)

Conclusions:
- After the `ST 1,360` watchdog expires (sometime between 16:33:30 and 16:38:10) the controller **falls back to POWER_UP**, with the valves in the high-vacuum-safe positions (chamber isolation valve open, VP valve closed). It does not report a separate error code.
- hpapp only runs its handshake (`RE 0`, `ST 1–5`, `TO 2/3`, `HP`/`MC`) when it starts. After a comms loss it never re-initialises the controller, so the system stays at POWER_UP until LEO-32/hpapp is restarted or `TO 3` is sent by hand. This is one plausible route to the "VP never works" history.
- **Requirement for a replacement:** poll every ~4 s, treat state 0 (POWER_UP) in any reply as "controller was reset", and re-run the full handshake. Use `TO 3` or `TO 2` according to the stage/vacuum state (`SPVR`/`SP` → 3, `NSP` → 2), then re-send `HP` / `MC`.
- To recover the current session by hand: hpapp send-command `TO 3` (the system is pumped), or restart LEO-32.

## Target sweep (capture 20261112_164437)

Targets were set with the LEO-32 slider (or text entry for 20 Pa); VP was entered with a manual `TO 7` and left with `TO 10` + `TO 3`. "Gauge → Pa" uses the hpapp table (`V = counts × 0.005005 − 0.01706`, then interpolate).

| Target | `HP` sent | `MC` sent | Settled gauge | → Pa (decoded) | Operator reading | State |
|---|---|---|---|---|---|---|
| 10 Pa | `873,908,1165` | `100,900` | 899–907 | 9.9–10.4 | 10 | 9 AT_HP |
| 50 Pa | `1133,1164,1446` | `919,900` | 1172–1175 | 57.5–58.5 | 57, drifting down slowly | 8 GOING_TO_HP |
| 100 Pa | `1252,1287,1579` | `1016,900` | 1297–1300 | 116–118 | 116 | 8 |
| 200 Pa | `1391,1435,1738` | `1132,900` | 1441–1443 | 225–227 | 225 | 8 |
| 20 Pa | `1005,1040,1309` | `818,900` | 1027–1036 | 20.4–21.5 | 20 exactly, "At VP" | 9 AT_HP |

- **The pressure decode now matches the operator's readings over 10–225 Pa.** The `HP` setpoints match the formula to within 1 count (50 Pa → 1447, 100 Pa → 1580, 200 Pa → 1738, 20 Pa → 1309).
- Raising the target sends the controller back from 9 to 8 (GOING_TO_HP). It reports 9 (AT_HP) only when the pressure is within its band of the setpoint. At 50–200 Pa it settled about 12–16 % high, stayed in state 8 and crept down slowly. Lowering the target (225 → 20 Pa) took about 40 s and ended in state 9.
- The first two `HP` values track the target (about 270–350 counts below the setpoint). They are probably the edges of the proportional valve's control band. To reproduce LEO-32 exactly, a replacement can use the table above or decode the rest of the hpapp routine.
- V8 reports **3 = opening** during the return (`503,10,11,3,0,0`). So the valve codes are 0 closed, 1 closing, 2 open, 3 opening.
- Return timing: `TO 10` → gauge below 900 in 20 s → V14 closed, V8 opening → 11 → 4 (GUN_ENABLE_OK) 34 s after `TO 10` → `TO 3`.
