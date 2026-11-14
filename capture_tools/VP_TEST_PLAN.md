# VP test plan: next capture

Goal: see both directions of the VP controller link together with the stage/vacuum link, find out why the VP controls are greyed out, and find out what the VP controller does (valves, gauge, state, errors) when it is asked to go to VP.

## 0. Wiring (4 channels)

| Teensy pin | Channel | Signal | Setting |
|---|---|---|---|
| 0 | ch1 | IP board → STGVAC (fiber tap) | normal |
| 9 | ch2 | STGVAC → IP board (fiber tap) | normal |
| 7 | ch3 | COM2 **TXD**, DB9 pin 3 (PC → VP controller) | `I 3 1` |
| **2** | **ch4** | COM2 **RXD**, DB9 pin 2 (VP controller → PC) | `I 4 1` |
| GND | | DB9 pin 5 + fiber tap ground | |

Use the same series resistor + clamp diodes on pin 2 as on pin 7. ch4 is a software UART (firmware v2): any digital pin works, and pin 2 is the default.

Start every capture with:

    python capture_serial.py COM17 --tag <name> --label1 "IP->STGVAC" --label2 "STGVAC->IP" --label3 "PC->VP" --label4 "VP->PC" --cmd "I 3 1" --cmd "I 4 1" --note "<what you will do>"

**Check within 10 s:** `GP` on PC->VP every 4 s, and a reply line on VP->PC right after each one. If VP->PC shows garbage, try `--cmd "I 4 0"`. One-time loopback check of ch4: `E 3 0`, `R 7`, `I 4 1` should decode the `GP` polls on ch4; then `R 2`, `E 3 1`.

## Safety
- EHT and filament **off** for every manual hpapp command (steps 4–5).
- Before any manual `TO`, note how to get back: the LEO-32 **Pump** button sends `.VL P` and `TO 3` (the normal path).
- Stop a step at once if the chamber goes to air while hpapp still reads ~0 Pa, or if the state does not change within its timeout (MCP up 10 s, target 240 s, MCP down 90 s).

## 1. hpapp start-up handshake (5 min)
With the system pumped and idle, close hpapp32 and let LEO-32 restart it (or restart LEO-32). Expect `RE 0`, maybe `RE 1`, `ST 1,300`, `ST 2,10`, `ST 3,90`, `ST 4,240`, `ST 5,5`, `TO 3`, and the controller's reply to each. Note any "rejected" message in the hpapp window.

## 2. Baseline at high vacuum (2 min)
No action. Gives the `GP` reply format with known values (0 Pa, PUMPING_LP, Error 0, V8 open, V14 closed, as shown in hpapp).

## 3. Why are the VP controls greyed out? (no capture needed, notes/screenshots)
- LEO-32 Administrator: vacuum/VP configuration, detector configuration (VP detector), and **licences** (VP is a licensed option held on the DESkey dongle).
- Current user privilege.
- Recent `LEO-32\LOG\leolog.leo` lines with "VP Control", "HPApp", "Comms".
- hpapp32 menus: is "Comms Disabled" shown; is there a log file (`Debug=YES` in LEO.INI; hpapp offers "Open Logfile", default `hpapp.log`)?
- `C:\WINDOWS\LEO.INI` `[HPAPP]` section, in case it changed since the drive image.

## 4. If the UI allows VP: normal VP cycle (10–15 min, one capture)
1. Set the VP target to **20 Pa** in the LEO-32 VP panel. Expect `HP 0,10000,≈1309` and `MC 818,900` (see VP_PROTOCOL.md).
2. **Go To VP.** Expect `TO 7` → `TO 8`, states 7 → 8 → 9, V8 closing, the gauge counts rising. Note audible clicks and the hpapp pressure readout every ~30 s.
3. Wait at AT_HP for 1 min.
4. **Go To HV.** Expect `TO 10` → `TO 11` → `TO 3`.

## 5. If the UI stays greyed: manual sequence from the hpapp command dialog (one capture, beam off)
Send one command at a time, waiting for the reply on VP->PC each time:
1. `RE 0`
2. `MC 818,900`
3. `HP 0,10000,1309` (20 Pa)
4. `TO 7`. Watch the hpapp pressure. **If it stays at 0 Pa while the chamber pressure clearly rises (Penning drops out, hissing), the chamber gauge or its wiring is the prime suspect.** Let the 10 s MCP timeout expire and record the error.
5. Recover: `RE 0`, then use the LEO-32 Pump button (or `TO 10`, wait, `TO 11`, `TO 3`).

## 6. Optional: VP reset/reverse
If hpapp has a "VP Reset" item, run it once during a capture (expect `RE 0`, `GM`).

## What to write down during the session
Clock time for each click or command; the hpapp status line (pressure, state, error, V8, V14) before and after each step; audible valve clicks; any LEO-32 or hpapp message box text.
