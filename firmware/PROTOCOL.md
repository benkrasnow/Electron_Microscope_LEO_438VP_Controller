# LEO 438VP control box: USB protocol (version 1)

The Teensy 4.0 enumerates as a USB CDC serial port (`USB type: Serial`). Baud rate settings are ignored. It is meant for a Chromium page using Web Serial (`navigator.serial`), and it can also be driven from any terminal.

- **PC → box:** one command per line (ASCII, LF or CR), with words separated by spaces.
- **Box → PC:** one JSON object per line (LF).

The box sends only while the port is open, which means DTR is asserted. Web Serial asserts DTR on `open()`.

The box never waits for the PC. If the USB buffer is full, it drops output and counts the loss (`sys.drops` in the status). Unplugging the cable, closing the page or stalling the PC therefore has no effect on control or safety. On every (re)connection the box sends a `hello` line and restarts telemetry, so the page can simply reconnect.

## 1. Requests and replies

```
[#<id> ]<command> [args...]
```

The optional `#<id>` (an integer) is echoed back as `"r"` in the reply, so a page can match replies to requests. Every command gets exactly one reply:

```json
{"r":12,"ok":true}
{"r":13,"ok":false,"err":"vacuum not ready"}
```

Some replies carry data (`get`, `eo r`, `time`, `status`, `hello`). `list` streams `{"t":"set",...}` lines first and then the reply.

An `"ok":true` reply means the request was accepted, not that it has finished. Long operations (pump, vent, beam on, VP) continue on the box; follow them in the telemetry (`sys.op`, `sys.act`, `eht.beam`, ...). Every refusal names the interlock that blocked it.

## 2. Asynchronous lines

| `t` | When | Content |
|---|---|---|
| `hello` | on connection | `fw`, `ver`, `proto` |
| `st` | every `usb.tel_ms` (default 250 ms; `tel <ms>` changes it for this connection) | full status, §4 |
| `ev` | every log event | `ms`, `rtc`, `lvl` (`debug` / `info` / `warn` / `fault`), `src`, `msg` |
| `tr` | link traffic while tracing (`trace`) | `ms`, `l` (`eht` / `stg` / `vp`), `d` (`>` sent, `<` received, `!` timeout), `s` (text) |
| `set` | `list` output | one setting, as for `get` |

## 3. Commands

### Session, settings
| Command | Action |
|---|---|
| `hello` | firmware name and version, protocol version, number of settings, uptime |
| `status` | one status object (§4) as the reply |
| `tel <ms>` | telemetry period for this connection (0 = off) |
| `get <name>` | `{"value","def","min","max","unit","flags","desc"}` |
| `set <name> <value>` | change a setting at once. It is saved to flash `sys.save_delay_ms` (3 s) after the last change, while no link is mid-reply. `state.*` is read only. `op.*` values pass the same limits as the dedicated commands below |
| `list [prefix]` | stream every setting (or those starting with `prefix`, e.g. `list eht.`) |
| `default <name>` / `default all` | restore the default. `all` skips `op.*` and `state.*` |
| `save` | write settings to flash now |

Flags in setting metadata: 1 = operating value (`op.*`), 2 = internal state, 4 = integer. The full list with defaults is in [SETTINGS.md](SETTINGS.md).

### Machine actions (interlocked)
| Command | Action |
|---|---|
| `pump` | pump down. Needs: vented (`NSP`). Sends `.VL P`, then VP `TO 3` after `vp.pump_delay_ms` |
| `vent` | vent. Takes the beam off (filament ramp), waits `eht.fil_cool_s`, leaves VP if needed, lowers Z to `stg.vent_z` when the stage is homed, then `.VL V`, and VP `TO 2` at `NSP` |
| `beam on` | needs: vacuum ready (`SPVR`, inhibits clear), EHT status OK, VP state 3 or 9 (unless `vp.required = 0`), no pressure change running. From off it runs the ramped start (~15 s); from `eht_off` it resumes |
| `beam off` | full shutdown with filament ramp-down, then the cool-down timer starts |
| `eht off` | EHT off, filament stays lit (`.B000 .O0301 .O0201`) |
| `safe` | abort any sequence, stop the stage, beam off (ramped). Same as the red STOP button |
| `abort` | abort the running machine sequence only (no beam change) |
| `vp enter [Pa]` | enter VP at the given target (default `op.vp_pa`). Takes the beam off and cools the filament first |
| `vp exit` | return to high vacuum (`TO 10`, then `TO 3` automatically at state 4). Beam off and filament cool first |
| `vp target <Pa>` | new VP target. In VP: beam off and cool first, then `MC`/`HP`. Otherwise it is stored for the next entry |
| `vp reset` | `RE 0` |
| `eht reset` | `.R` and a status read |

### Setpoints
Each one sets an `op.*` setting. The subsystem modules follow the settings: the EHT ramps when needed, and the EO board gets the new values.

| Command | Setting | Notes |
|---|---|---|
| `kv <kV>` | `op.kv` | limited to `eht.kv_min`..`eht.kv_max`. With the beam on, changes above 20 kV ramp 1 kV / 0.466 s; after the ramp the objective, condenser and coil weights follow √(relativistic kV) |
| `fil <mA>` | `op.fil_ma` | beam on: ramped in steps of `eht.fil_slow_step` |
| `emis <µA>` | `op.emis_ua` | |
| `coll <V>` | `op.coll_v` | SE collector bias |
| `bright <n>` / `pm <ch> <n>` | `op.pm1..3` | PM HV (brightness = channel 1) |
| `mag <x>` | `op.mag` | coil weights and range relays (park → range → 45 ms → weights); also sets the joystick pixel size `.SW` |
| `rot <deg>`, `wd <mm>`, `tilt <deg>` | `op.rot`, `op.wd`, `op.tilt` | scan rotation, WD for the scan geometry, tilt correction (Y × cos tilt) |
| `focus <fine> [coarse]` | `op.obj_f`, `op.obj_c` | objective DACs (read-modify-write like the original) |
| `stig <x> <y>` | `op.stig_x/y` | |
| `shift <x> <y>` | `op.shift_x/y` | beam shift in image axes, ±2047 counts, rotated with the scan |
| `cond <d0> <d1> <d2> <d3>` | `op.cond0..3` | condenser DACs (no Optibeam model yet) |
| `scan ext\|raster\|line\|spot` | `op.scan` | `ext` = OBI drives the external scan input |
| `speed <0-15>` | `op.speed` | internal scan speed |
| `spot <x> <y>`, `line <y>` | `op.spot_*`, `op.line_y` | 16-bit positions |
| `wobble <%> [fast\|slow]` | `op.wob_pct`, `op.wob_fast` | 0 = off |
| `dynfocus <counts>` | `op.dynf` | objective-fine change over the frame height (internal raster) |
| `freeze on\|off` | | pair A / B levels, raster stops at the frame end |

### Stage
| Command | Action |
|---|---|
| `stage goto x y z t r` | absolute, in mm (X Y Z) and degrees (T R). `-` keeps an axis. Clamped to the active user limits (X/Y 35–65 mm at air) |
| `stage move dx dy dz dt dr` | relative, same units |
| `stage stop` | `.SK` |
| `stage home` | initialise Z, T, Y, X in turn, set positions, limits, speeds, then go to the start position |

Moves need an initialised stage (`stg.req_home`). The joystick on the stage controller works locally; its sensitivity is `stg.joy_gain`.

### EO board, raw access and diagnostics
| Command | Action |
|---|---|
| `eo restore` | resend the full EO state (boot burst with current values) |
| `eo r <chip> <reg>` | read a register over F4 → `{"value":n}` (−1 = no reply) |
| `eo w <chip> <reg> <value>` | write a register (needs `dbg.raw 1`) |
| `raw eht\|stg\|vp <text>` | send a raw command line. Needs `dbg.raw 1`, **bypasses the interlocks**, and switches tracing on for that link so the reply shows up |
| `trace eht\|stg\|vp\|all\|off` | echo link traffic as `tr` lines |
| `log [n]` | resend the last n events |
| `time [unix]` | read or set the RTC (the page should set it from the PC clock on connection) |
| `reboot` | restart the Teensy (the beam is adopted after the restart, see README) |
| `bootloader` | enter the Teensy loader for flashing |
| `help` | list of commands |

## 4. Status object (`t: "st"`)

```json
{"t":"st","up":123456,"rtc":1794000000,
 "sys":{"op":"none","act":"","sum":"VACUUM READY  -  BEAM ON","dirty":false,"drops":0},
 "vac":{"link":true,"cfg":true,"st":"SPVR","txt":"Vacuum ready","raw":302,"torr":9.8e-05,"inh":0,"ready":true,"ver":"V01.01 /V02.00 "},
 "vp":{"link":true,"hs":true,"st":3,"name":"PUMPING_LP","req":3,"gauge":399,"pa":0,"tgt":20,"v8":2,"v14":0,"err":0},
 "eht":{"link":true,"ready":true,"beam":"on","sb":64,"word":3847,"kv":5,"kvset":5,"fil":2468,"filset":2468,
        "emis":400,"coll":300,"pm1":1912,"cool":30,"cold":false,"act":"","id":"M08"},
 "stg":{"valid":true,"homed":true,"mv":false,"lim":false,"homing":false,
        "pos":[50,50,1,0,0],"c":[8388608,8286749,7323727,8388608,8388608]},
 "eo":{"link":true,"mode":"external","mag":100,"range":1,"speed":5,"rot":0,"wd":15,"tilt":0,
       "objc":790,"focus":2234,"stigx":2048,"stigy":2048,"wob":0,"frz":false,"frames":0,"q":0,"line_us":2811},
 "btn":[0,0,0]}
```

| Field | Meaning |
|---|---|
| `sys.op` | running machine sequence: `none`, `pump`, `vent`, `vp_enter`, `vp_exit`, `vp_target` |
| `sys.act` | what that sequence is doing ("Filament cooling 12 s", ...) |
| `vac.st` | the controller's own state code: `NSP` `WTUS` `WP` `SP` `SPVR` `SPE` `WVT` |
| `vac.inh` | `.VS` b0 inhibit bits (0 = all released). 255 = unknown |
| `vac.torr` | Penning pressure, `null` when the gauge is off |
| `vp.st` | VP controller state 0–11 (spec §4.2); −1 = not yet read |
| `eht.beam` | `off` (filament cold), `cooling`, `starting`, `on`, `eht_off` (filament lit), `stopping` |
| `eht.sb` | last `?S` status byte (0x40 OK, 0x10 vacuum inhibit, 0x08 reset, 0x04 filament blown, 0x02 trip); −1 = none yet |
| `eht.word` | last `.O` supply word sent |
| `eht.kv`, `eht.fil` | values actually sent (they lag the setpoints during ramps) |
| `stg.pos` | X Y Z in mm, T R in degrees (UI coordinates); `stg.c` = raw counts |
| `eo.link` | EO read-back check OK (chip 3 options returns the last value written) |

## 5. Example session

```
> hello
< {"ok":true,"fw":"leo_control","ver":"0.1.0","proto":1,"settings":307,"up":5120}
> #1 time 1794067200
< {"r":1,"ok":true}
> #2 beam on
< {"r":2,"ok":false,"err":"vacuum not ready"}
> #3 pump
< {"r":3,"ok":true}
< {"t":"ev","ms":9001,"rtc":1794067203,"lvl":"info","src":"vac","msg":"pump down requested"}
  ... telemetry until vac.ready ...
> #4 beam on
< {"r":4,"ok":true}
> #5 set stg.joy_gain 0.5
< {"r":5,"ok":true}
```
