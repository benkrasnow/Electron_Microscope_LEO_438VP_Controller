# Control box settings

All 364 runtime settings, generated from `leo_control/settings.h` by `tools/gen_settings_doc.py`. Read and change them over USB with `get`, `set`, `list`, `default` (see PROTOCOL.md); they are kept in flash.


## EHT / gun supply link

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `eht.poll_s` | 4.5 | 0.5 | 30 | s | status (?S) poll period |
| `eht.timeout_ms` | 300 | 50 | 5000 | ms | reply timeout |
| `eht.gap_ms` | 17 | 0 | 1000 | ms | gap after a reply before the next command |
| `eht.retries` | 1 | 0 | 5 |  | resends after a timeout |
| `eht.tx_inv` | 0 | 0 | 1 |  | invert transmit data (0: pin high = light on = idle) |
| `eht.rx_inv` | 1 | 0 | 1 |  | invert receive data (1: HFBR-2521Z pulls low with light on) |
| `eht.ramp_ms` | 466 | 100 | 5000 | ms | filament / >20 kV ramp step interval |
| `eht.fil_start_ma` | 44 | 16 | 500 | mA | first filament step at beam on |
| `eht.fil_fast_step` | 147 | 1 | 500 | mA | fast warm-up step |
| `eht.fil_fast_to` | 1812 | 16 | 4000 | mA | end of fast warm-up |
| `eht.fil_pause_ms` | 1350 | 0 | 10000 | ms | pause between fast and slow warm-up |
| `eht.fil_slow_step` | 39 | 1 | 500 | mA | slow approach step (also the max single adjust step with the beam on) |
| `eht.fil_down_start` | 2320 | 16 | 4000 | mA | ramp-down starts at min(current, this) |
| `eht.fil_down_step` | 147 | 1 | 500 | mA | ramp-down step |
| `eht.fil_off_ma` | 110 | 16 | 1000 | mA | ramp-down ends here, then supplies off |
| `eht.fil_cool_s` | 30 | 0 | 900 | s | filament cool-down wait before any pressure change |
| `eht.fil_max_ma` | 2800 | 16 | 4111 | mA | upper limit for the filament setpoint |
| `eht.kv_start` | 0.1 | 0.03 | 1 | kV | first EHT value at beam on |
| `eht.kv_ramp_above` | 20 | 1 | 30 | kV | kV changes above this are ramped |
| `eht.kv_ramp_step` | 1.0 | 0.1 | 5 | kV | ramp step above eht.kv_ramp_above |
| `eht.kv_min` | 0.5 | 0.1 | 30 | kV | lowest allowed kV setpoint |
| `eht.kv_max` | 30 | 1 | 30 | kV | highest allowed kV setpoint |
| `eht.emis_max_ua` | 400 | 0 | 409.5 | uA | highest allowed emission setpoint |
| `eht.on_delay_ms` | 1000 | 0 | 10000 | ms | beam on: emission set -> EHT on |
| `eht.filon_delay_ms` | 470 | 0 | 10000 | ms | beam on: EHT on -> filament supply on |
| `eht.off_delay_ms` | 700 | 0 | 10000 | ms | beam off: detectors off (0301) -> EHT off (0201) |
| `eht.o_base` | 1 | 0 | 65535 |  | .O bit always set (0x0001) |
| `eht.o_detect` | 1030 | 0 | 65535 |  | .O detector/collector supply bits (0x0406) |
| `eht.o_scint` | 2048 | 0 | 65535 |  | .O scintillator HV bit (0x0800) |
| `eht.o_eht` | 256 | 0 | 65535 |  | .O accelerating voltage bit (0x0100) |
| `eht.o_fil` | 512 | 0 | 65535 |  | .O filament supply bit (0x0200) |
| `eht.scint_off_vp` | 1 | 0 | 1 |  | 1: scintillator HV off while the chamber is in VP |
| `eht.filtype` | 1 | 0 | 15 |  | .T filament type |
| `eht.anode` | 1 | 0 | 15 |  | .A anode type |

## Operating values (changed by commands, persisted)

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `op.kv` | 5 | 0.1 | 30 | kV | accelerating voltage setpoint |
| `op.fil_ma` | 2468 | 16 | 4111 | mA | filament current setpoint |
| `op.emis_ua` | 400 | 0 | 409.5 | uA | emission current setpoint |
| `op.coll_v` | 300 | -409 | 409 | V | SE collector bias |
| `op.pm1` | 1912 | 0 | 4095 |  | PM HV channel 1 (brightness) |
| `op.pm2` | 400 | 0 | 4095 |  | PM HV channel 2 |
| `op.pm3` | 400 | 0 | 4095 |  | PM HV channel 3 |
| `op.vp_pa` | 20 | 1 | 400 | Pa | VP chamber pressure target |
| `op.mag` | 100 | 1 | 1e6 | x | magnification |
| `op.rot` | 0 | -360 | 360 | deg | scan rotation |
| `op.wd` | 15 | 2 | 150 | mm | working distance as LEO-32 displayed it: sets the objective (eo.model 1) and the scan geometry |
| `op.tilt` | 0 | -89 | 89 | deg | tilt correction angle (0 = off) |
| `op.speed` | 5 | 0 | 15 |  | internal scan speed 0-15 |
| `op.scan` | 0 | 0 | 3 |  | scan mode 0 external (OBI), 1 raster, 2 line, 3 spot |
| `op.obj_c` | 790 | 0 | 4095 |  | objective coarse (chip 1 DAC0) |
| `op.obj_f` | 2234 | 0 | 4095 |  | objective fine / focus (chip 1 DAC1) |
| `op.stig_x` | 2048 | 0 | 4095 |  | stigmator X (chip 0 DAC6) |
| `op.stig_y` | 2048 | 0 | 4095 |  | stigmator Y (chip 0 DAC7) |
| `op.cond0` | 45 | 0 | 4095 |  | condenser chip 0 DAC0 |
| `op.cond1` | 182 | 0 | 4095 |  | condenser chip 0 DAC1 |
| `op.cond2` | 23 | 0 | 4095 |  | condenser chip 0 DAC2 |
| `op.cond3` | 218 | 0 | 4095 |  | condenser chip 0 DAC3 |
| `op.probe_pa` | 300 | 1 | 100000 | pA | probe current (Optibeam: sets the condensers through the column model or the eo.pc* table) |
| `op.obeam` | 0 | 0 | 2 |  | Optibeam mode 0 Normal (resolution) / 1 Depth / 2 Auto resolution (picks the probe current) |
| `op.aperture` | 50 | 5 | 1000 | um | final aperture diameter entered by the operator (LEO-32 offered 30 and 50 um) |
| `op.shift_x` | 0 | -2047 | 2047 |  | beam shift X (image axes, DAC counts) |
| `op.shift_y` | 0 | -2047 | 2047 |  | beam shift Y |
| `op.spot_x` | 32768 | 0 | 65535 |  | spot mode X position |
| `op.spot_y` | 32768 | 0 | 65535 |  | spot mode Y position |
| `op.line_y` | 32768 | 0 | 65535 |  | line scan Y position |
| `op.wob_pct` | 0 | 0 | 100 | % | focus wobble amplitude (0 = off) |
| `op.wob_fast` | 1 | 0 | 1 |  | focus wobble rate 1 fast, 0 slow |
| `op.dynf` | 0 | -4000 | 4000 |  | dynamic focus: objective fine change over the frame height (internal raster) |

## Internal persisted state (read only)

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `state.beam` | 0 | 0 | 3 |  | 0 off, 1 on, 2 in transition (filament current unknown), 3 EHT off with the filament lit |
| `state.fil_off_t` | 0 | 0 | 4e9 | s | RTC time the filament supply went off |

## Stage

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `stg.poll_ms` | 1200 | 100 | 10000 | ms | idle poll period for .VT and .SD |
| `stg.poll_move_ms` | 150 | 50 | 2000 | ms | .SD poll period while an axis moves |
| `stg.sp_ms` | 300 | 50 | 5000 | ms | .SP repeat period while a stage event persists |
| `stg.timeout_ms` | 1000 | 100 | 5000 | ms | reply timeout |
| `stg.gap_ms` | 10 | 0 | 1000 | ms | gap after a reply |
| `stg.retries` | 1 | 0 | 5 |  | resends after a timeout |
| `stg.tx_inv` | 0 | 0 | 1 |  | invert transmit data |
| `stg.rx_inv` | 1 | 0 | 1 |  | invert receive data |

## Vacuum

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `vac.pen_a` | 60 | 1 | 1000 |  | Penning: P_Torr = 1/(a * raw^exp) |
| `vac.pen_exp` | 0.9 | 0.1 | 3 |  | Penning exponent |
| `vac.ta` | 302 | 0 | 100000 | raw | .TA scintillator threshold |
| `vac.tb1` | 302 | 0 | 100000 | raw | .TB accelerating-voltage threshold |
| `vac.tb2` | 50 | 0 | 100000 | raw | .TB hysteresis level |
| `vac.tc` | 302 | 0 | 100000 | raw | .TC PM threshold |
| `vac.td1` | 8210 | 0 | 100000 | raw | .TD ion pump threshold (not fitted) |
| `vac.td2` | 50 | 0 | 100000 | raw | .TD hysteresis level |
| `vac.te1` | 302 | 0 | 100000 | raw | .TE filament threshold |
| `vac.te2` | 50 | 0 | 100000 | raw | .TE hysteresis level |
| `vac.th` | 50 | 0 | 100000 | raw | .TH EDX threshold |

## Stage

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `stg.cpu_x` | 8148.74 | 1 | 1e6 | /mm | X counts per mm |
| `stg.cpu_y` | 8148.74 | 1 | 1e6 | /mm | Y counts per mm |
| `stg.cpu_z` | 64538.2 | 1 | 1e6 | /mm | Z counts per mm |
| `stg.cpu_t` | 11264 | 1 | 1e6 | /deg | T counts per degree |
| `stg.cpu_r` | 8448 | 1 | 1e6 | /deg | R counts per degree |
| `stg.zero_x` | 7981171 | 0 | 16777215 |  | X count at UI zero |
| `stg.zero_y` | 7879312 | 0 | 16777215 |  | Y count at UI zero |
| `stg.zero_z` | 7259189 | 0 | 16777215 |  | Z count at UI zero |
| `stg.zero_t` | 8388608 | 0 | 16777215 |  | T count at UI zero |
| `stg.zero_r` | 8388608 | 0 | 16777215 |  | R count at UI zero |
| `stg.lo_x` | 7981171 | 0 | 16777215 |  | .SQ user lower limit X (pumped) |
| `stg.lo_y` | 7879312 | 0 | 16777215 |  | .SQ user lower limit Y |
| `stg.lo_z` | 7259189 | 0 | 16777215 |  | .SQ user lower limit Z |
| `stg.lo_t` | 7374848 | 0 | 16777215 |  | .SQ user lower limit T |
| `stg.lo_r` | 5178369 | 0 | 16777215 |  | .SQ user lower limit R |
| `stg.hi_x` | 8796045 | 0 | 16777215 |  | .SJ user upper limit X (pumped) |
| `stg.hi_y` | 8897904 | 0 | 16777215 |  | .SJ user upper limit Y |
| `stg.hi_z` | 9518027 | 0 | 16777215 |  | .SJ user upper limit Z |
| `stg.hi_t` | 9402368 | 0 | 16777215 |  | .SJ user upper limit T |
| `stg.hi_r` | 14471166 | 0 | 16777215 |  | .SJ user upper limit R |
| `stg.air_lo_x` | 8266377 | 0 | 16777215 |  | X lower limit at air (35 mm) |
| `stg.air_lo_y` | 8164518 | 0 | 16777215 |  | Y lower limit at air |
| `stg.air_hi_x` | 8510839 | 0 | 16777215 |  | X upper limit at air (65 mm) |
| `stg.air_hi_y` | 8408980 | 0 | 16777215 |  | Y upper limit at air |
| `stg.hwlo_x` | 7981171 | 0 | 16777215 |  | .SO hardware lower limit X (homing) |
| `stg.hwlo_y` | 7879312 | 0 | 16777215 |  | .SO hardware lower limit Y |
| `stg.hwlo_z` | 7259189 | 0 | 16777215 |  | .SO hardware lower limit Z |
| `stg.hwlo_t` | 7374848 | 0 | 16777215 |  | .SO hardware lower limit T |
| `stg.hwlo_r` | 5178369 | 0 | 16777215 |  | .SO hardware lower limit R |
| `stg.spd_x` | 1500 | 1 | 100000 |  | .SB speed X at start-up |
| `stg.spd_y` | 1500 | 1 | 100000 |  | .SB speed Y at start-up |
| `stg.spd_z` | 3000 | 1 | 100000 |  | .SB speed Z at start-up |
| `stg.spd_t` | 2000 | 1 | 100000 |  | .SB speed T at start-up |
| `stg.spd_r` | 3000 | 1 | 100000 |  | .SB speed R at start-up |
| `stg.hspd_x` | 1500 | 1 | 100000 |  | .SB speed X while homing |
| `stg.hspd_y` | 1500 | 1 | 100000 |  | .SB speed Y while homing |
| `stg.hspd_z` | 3000 | 1 | 100000 |  | .SB speed Z while homing |
| `stg.hspd_t` | 2000 | 1 | 100000 |  | .SB speed T while homing |
| `stg.hspd_r` | 4000 | 1 | 100000 |  | .SB speed R while homing |
| `stg.pspd_x` | 1500 | 1 | 100000 |  | .SB speed X after homing |
| `stg.pspd_y` | 1500 | 1 | 100000 |  | .SB speed Y after homing |
| `stg.pspd_z` | 2100 | 1 | 100000 |  | .SB speed Z after homing |
| `stg.pspd_t` | 1300 | 1 | 100000 |  | .SB speed T after homing |
| `stg.pspd_r` | 4000 | 1 | 100000 |  | .SB speed R after homing |
| `stg.ramp_a` | 100 | 0 | 100000 |  | .SC ramp value a (all axes) |
| `stg.ramp_b` | 200 | 0 | 100000 |  | .SC ramp value b |
| `stg.ramp_c` | 30 | 0 | 100000 |  | .SC ramp value c |
| `stg.sv_x` | 3926 | 1 | 1e8 |  | .SV step size X (1/32 nm per count) |
| `stg.sv_y` | 3926 | 1 | 1e8 |  | .SV step size Y |
| `stg.sv_z` | 495 | 1 | 1e8 |  | .SV step size Z |
| `stg.sv_t` | 2840910 | 1 | 1e8 |  | .SV step size T (1/32 n-deg) |
| `stg.sv_r` | 3787880 | 1 | 1e8 |  | .SV step size R |
| `stg.home_x` | 7985269 | 0 | 16777215 |  | .SA X position set after homing |
| `stg.home_y` | 7883410 | 0 | 16777215 |  | .SA Y |
| `stg.home_z` | 7292522 | 0 | 16777215 |  | .SA Z |
| `stg.home_t` | 8377344 | 0 | 16777215 |  | .SA T |
| `stg.home_r` | 8388608 | 0 | 16777215 |  | .SA R |
| `stg.park_x` | 8388608 | 0 | 16777215 |  | position after homing X (50 mm) |
| `stg.park_y` | 8286749 | 0 | 16777215 |  | position after homing Y (50 mm) |
| `stg.park_z` | 7323727 | 0 | 16777215 |  | position after homing Z (1 mm) |
| `stg.park_t` | 8388608 | 0 | 16777215 |  | position after homing T |
| `stg.park_r` | 8388608 | 0 | 16777215 |  | position after homing R |
| `stg.vent_z` | 7291458 | 0 | 16777215 |  | Z count to drive to before venting (0.5 mm) |
| `stg.vent_z_en` | 1 | 0 | 1 |  | 1: lower Z before venting when the stage is homed |
| `stg.req_home` | 1 | 0 | 1 |  | 1: refuse go-to moves until all axes are initialised |
| `stg.move_to_s` | 120 | 5 | 1000 | s | timeout for a move or one homing axis |
| `stg.joy_gain` | 1.0 | 0.01 | 100 |  | joystick sensitivity: multiplies the .SW pixel size |
| `stg.joy_field_m` | 1.1458e-4 | 1e-6 | 1 | m | field of view at 1x divided by screen pixels (.SW = field*gain/mag) |
| `stg.joy_hyst` | 0.05 | 0 | 1 |  | resend .SW when it changes by more than this fraction |

## VP controller

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `vp.poll_s` | 4 | 0.5 | 60 | s | GP poll period (must stay well below vp.wd_s) |
| `vp.timeout_ms` | 2000 | 100 | 10000 | ms | reply timeout |
| `vp.gap_ms` | 25 | 0 | 1000 | ms | gap after a reply |
| `vp.retries` | 1 | 0 | 5 |  | resends after a timeout |
| `vp.tx_inv` | 0 | 0 | 1 |  | invert transmit data (VP board fiber polarity unconfirmed) |
| `vp.rx_inv` | 1 | 0 | 1 |  | invert receive data |
| `vp.required` | 1 | 0 | 1 |  | 1: beam on needs a live VP link in state 3 or 9 |
| `vp.wd_s` | 360 | 10 | 3600 | s | ST 1: controller comms watchdog |
| `vp.t_mcpup` | 10 | 1 | 3600 | s | ST 2: MCP-up timeout |
| `vp.t_mcpdn` | 90 | 1 | 3600 | s | ST 3: MCP-down timeout |
| `vp.t_target` | 240 | 1 | 3600 | s | ST 4: target timeout |
| `vp.t_gun` | 5 | 1 | 3600 | s | ST 5: gun-enable timeout |
| `vp.mc_down` | 900 | 0 | 4095 |  | MC down threshold (gauge counts) |
| `vp.mc_up_frac` | 0.8 | 0.1 | 1 |  | MC up = frac * gauge counts at the target |
| `vp.mc_up_min` | 100 | 0 | 4095 |  | MC up used for low targets |
| `vp.mc_lowp` | 10 | 0 | 100 | Pa | targets at or below this use vp.mc_up_min |
| `vp.hp_gain` | 1.094 | 0.1 | 10 |  | HP setpoint gain (LEO.INI) |
| `vp.hp_off` | 190 | -4095 | 4095 |  | HP setpoint offset |
| `vp.hp_hik` | 0.015 | 0 | 1 |  | extra HP gain per hp_hip above hp_hip |
| `vp.hp_hip` | 250 | 1 | 2000 | Pa | HP high-pressure correction knee |
| `vp.band_lo` | 0.0175 | 0 | 0.5 |  | HP a = raw * (1 - band_lo) |
| `vp.band_hi` | 0.0155 | 0 | 0.5 |  | HP b = raw * (1 + band_hi) |
| `vp.v_gain` | 0.005005 | 0 | 1 | V | Pirani volts per count |
| `vp.v_off` | -0.01706 | -1 | 1 | V | Pirani volts offset |
| `vp.pir_p0` | 0 | 0 | 1e5 | Pa | Pirani table point 0 pressure |
| `vp.pir_p1` | 1 | 0 | 1e5 | Pa |  |
| `vp.pir_p2` | 10 | 0 | 1e5 | Pa |  |
| `vp.pir_p3` | 20 | 0 | 1e5 | Pa |  |
| `vp.pir_p4` | 50 | 0 | 1e5 | Pa |  |
| `vp.pir_p5` | 100 | 0 | 1e5 | Pa |  |
| `vp.pir_p6` | 1000 | 0 | 1e5 | Pa |  |
| `vp.pir_p7` | 2240 | 0 | 1e5 | Pa |  |
| `vp.pir_v0` | 2.000 | 0 | 12 | V | Pirani table point 0 voltage |
| `vp.pir_v1` | 2.99 | 0 | 12 | V |  |
| `vp.pir_v2` | 4.49 | 0 | 12 | V |  |
| `vp.pir_v3` | 5.104 | 0 | 12 | V |  |
| `vp.pir_v4` | 5.737 | 0 | 12 | V |  |
| `vp.pir_v5` | 6.345 | 0 | 12 | V |  |
| `vp.pir_v6` | 8.84 | 0 | 12 | V |  |
| `vp.pir_v7` | 9.40 | 0 | 12 | V |  |
| `vp.pump_delay_ms` | 1500 | 0 | 60000 | ms | TO 3 this long after .VL P |
| `vp.enter_to_s` | 600 | 10 | 7200 | s | give up waiting for AT_HP after this |
| `vp.exit_to_s` | 240 | 10 | 7200 | s | give up waiting for GUN_ENABLE_OK after this |

## EO board and optics

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `eo.tx_inv` | 0 | 0 | 1 |  | invert F1/F2/F3 outputs |
| `eo.rx_inv` | 1 | 0 | 1 |  | invert F4 input |
| `eo.baud` | 3686400 | 1e6 | 6e6 | bit/s | F3/F4 bit rate |
| `eo.gap_us` | 14 | 6 | 1000 | us | minimum idle between frames |
| `eo.reply_us` | 40 | 5 | 1000 | us | wait for an F4 reply start bit |
| `eo.lens_us` | 940 | 0 | 100000 | us | spacing of lens read-modify-write frames |
| `eo.hb_s` | 2 | 0 | 60 | s | link check read period (0 = off) |
| `eo.rmw` | 1 | 0 | 1 |  | 1: read control/routing before lens writes, like the original |
| `eo.repeat` | 4 | 1 | 8 |  | repeats of coil-weight and shift writes |
| `eo.spd_repeat` | 3 | 1 | 8 |  | repeats of the scan-speed block |
| `eo.range_wait_ms` | 45 | 0 | 1000 | ms | range relay settling before new weights |
| `eo.wmax` | 32000 | 1000 | 32767 |  | largest coil-weight offset before switching to a less sensitive range |
| `eo.kv_ref` | 20 | 0.5 | 30 | kV | kV at which the range calibration was taken |
| `eo.wd_ref` | 15 | 1 | 60 | mm | WD at which the range calibration was taken |
| `eo.wd_exp` | -0.645 | -3 | 3 |  | scan size ~ (WD/wd_ref)^exp |
| `eo.wd_rot` | 1.6 | -20 | 20 | deg/mm | lens rotation per mm of WD (sign to verify) |
| `eo.ga` | 1.04 | 0.1 | 10 |  | coil A gain |
| `eo.gb` | 1.0 | 0.1 | 10 |  | coil B gain |
| `eo.k0` | 44520 | 1 | 1e10 |  | range 0 scale (weight x mag at kv_ref, wd_ref) |
| `eo.k1` | 347200 | 1 | 1e10 |  | range 1 scale |
| `eo.k2` | 2846600 | 1 | 1e10 |  | range 2 scale |
| `eo.k3` | 23909000 | 1 | 1e10 |  | range 3 scale |
| `eo.k4` | 172190000 | 1 | 1e10 |  | range 4 scale |
| `eo.d0` | -6.868 | -90 | 90 | deg | range 0 angle trim |
| `eo.d1` | -6.648 | -90 | 90 | deg | range 1 angle trim |
| `eo.d2` | -6.481 | -90 | 90 | deg | range 2 angle trim |
| `eo.d3` | -6.435 | -90 | 90 | deg | range 3 angle trim |
| `eo.d4` | -6.606 | -90 | 90 | deg | range 4 angle trim |
| `eo.ky0` | 0.9767 | 0.5 | 2 |  | range 0 Y/X gain |
| `eo.ky1` | 0.9767 | 0.5 | 2 |  | range 1 Y/X gain |
| `eo.ky2` | 0.9768 | 0.5 | 2 |  | range 2 Y/X gain |
| `eo.ky3` | 0.9768 | 0.5 | 2 |  | range 3 Y/X gain |
| `eo.ky4` | 0.9767 | 0.5 | 2 |  | range 4 Y/X gain |
| `eo.e0` | -0.037 | -10 | 10 | deg | range 0 X-Y orthogonality trim |
| `eo.e1` | -0.255 | -10 | 10 | deg | range 1 orthogonality trim |
| `eo.e2` | -0.422 | -10 | 10 | deg | range 2 orthogonality trim |
| `eo.e3` | -0.469 | -10 | 10 | deg | range 3 orthogonality trim |
| `eo.e4` | -0.292 | -10 | 10 | deg | range 4 orthogonality trim |
| `eo.cx0` | 2088 | 0 | 4095 |  | range 0 X centring (chip 2 DAC2) |
| `eo.cx1` | 2088 | 0 | 4095 |  | range 1 X centring |
| `eo.cx2` | 2141 | 0 | 4095 |  | range 2 X centring |
| `eo.cx3` | 2158 | 0 | 4095 |  | range 3 X centring |
| `eo.cx4` | 2238 | 0 | 4095 |  | range 4 X centring |
| `eo.cy0` | 1978 | 0 | 4095 |  | range 0 Y centring (chip 3 DAC0) |
| `eo.cy1` | 1958 | 0 | 4095 |  | range 1 Y centring |
| `eo.cy2` | 1931 | 0 | 4095 |  | range 2 Y centring |
| `eo.cy3` | 2088 | 0 | 4095 |  | range 3 Y centring |
| `eo.cy4` | 2301 | 0 | 4095 |  | range 4 Y centring |
| `eo.mag_min` | 10 | 1 | 1e6 | x | lowest magnification accepted |
| `eo.mag_max` | 500000 | 1 | 1e7 | x | highest magnification accepted |
| `eo.kv_obj` | 1 | 0 | 1 |  | 1: scale objective coarse with sqrt(relativistic kV) on kV changes |
| `eo.kv_cond` | 0 | 0 | 1 |  | 1: scale the condenser DACs with sqrt(kV) (only with eo.optibeam = 0) |
| `eo.optibeam` | 1 | 0 | 1 |  | 1: condenser follows op.probe_pa through the eo.pc* table; 0: op.cond* set directly |
| `eo.model` | 1 | 0 | 1 |  | 1: lenses from the column model (op.wd / op.probe_pa / op.obeam / op.aperture); 0: eo.pc* table and op.obj_* directly |
| `eo.cal1` | 0.93565 | 0.3 | 3 |  | C1 calibration LEO-32 effectively used (fit; Data.vac 1.0597) |
| `eo.cal2` | 0.9042 | 0.3 | 3 |  | C2 calibration (fit to the Depth-mode C2 ceiling; Data.vac 1.05973) |
| `eo.cal3` | 0.991194 | 0.3 | 3 |  | objective calibration (Data.vac) |
| `eo.rem1` | 0.0101 | -1 | 1 | A | C1 remanence (Data.vac) |
| `eo.rem2` | 0.0101094 | -1 | 1 | A | C2 remanence (Data.vac) |
| `eo.rem3` | 0.0107648 | -1 | 1 | A | objective remanence (Data.vac) |
| `eo.xtalk` | 0.0422491 | -1 | 1 |  | C1 / C2 crosstalk (Data.vac) |
| `eo.wd_a` | 1.21696 | 0.5 | 2 |  | model WD = (op.wd - eo.wd_b) / eo.wd_a (LEO-32 display scale; fit) |
| `eo.wd_b` | 1.876 | -20 | 20 | mm | display WD offset (fit) |
| `eo.kn` | 0.95935 | 0.01 | 100 |  | Normal mode probe-size constant (fit) |
| `eo.an` | 0.91561 | 0.1 | 10 |  | Normal mode optimum-angle scale (fit) |
| `eo.kd` | 12.78728 | 0.01 | 1000 |  | Depth mode constant (fit) |
| `eo.kd0` | 1.46246 | 0.1 | 10 |  | gun source-size factor (fit) |
| `eo.thr` | 0.95 | 0.1 | 0.999 |  | fraction of the aperture-limited angle above which C2 goes to its limit |
| `eo.ar2` | 50 | 1 | 100000 | pA | Auto resolution probe current at 2 kV (LEO-32 UI 2026-11-15) |
| `eo.ar5` | 70 | 1 | 100000 | pA | Auto resolution probe current at 5 kV |
| `eo.ar10` | 90 | 1 | 100000 | pA | Auto resolution probe current at 10 kV |
| `eo.ar20` | 150 | 1 | 100000 | pA | Auto resolution probe current at 20 kV (log-log interpolated; extrapolated above) |
| `eo.pa_min` | 1 | 0.1 | 100000 | pA | lowest probe current accepted with eo.model 1 |
| `eo.pa_max` | 100000 | 1 | 1e6 | pA | highest probe current accepted with eo.model 1 |
| `eo.pc_kvref` | 5 | 0.5 | 30 | kV | kV at which the eo.pc* table was taken (captures: 5 kV) |
| `eo.pc_kvexp` | 0 | -2 | 2 |  | condenser = table * (rel. kV / rel. kV_ref)^exp; 0 = no kV dependence |
| `eo.pc1_pa` | 50 | 0 | 100000 | pA | Optibeam table point 1: probe current (0 = unused) |
| `eo.pc1_d0` | 1111 | 0 | 4095 |  | point 1: condenser chip 0 DAC0 |
| `eo.pc1_d1` | 137 | 0 | 4095 |  | point 1: condenser chip 0 DAC1 |
| `eo.pc1_d2` | 317 | 0 | 4095 |  | point 1: condenser chip 0 DAC2 |
| `eo.pc1_d3` | 33 | 0 | 4095 |  | point 1: condenser chip 0 DAC3 |
| `eo.pc2_pa` | 300 | 0 | 100000 | pA | Optibeam table point 2: probe current (0 = unused) |
| `eo.pc2_d0` | 1035 | 0 | 4095 |  | point 2: condenser chip 0 DAC0 |
| `eo.pc2_d1` | 88 | 0 | 4095 |  | point 2: condenser chip 0 DAC1 |
| `eo.pc2_d2` | 254 | 0 | 4095 |  | point 2: condenser chip 0 DAC2 |
| `eo.pc2_d3` | 204 | 0 | 4095 |  | point 2: condenser chip 0 DAC3 |
| `eo.pc3_pa` | 500 | 0 | 100000 | pA | Optibeam table point 3: probe current (0 = unused) |
| `eo.pc3_d0` | 938 | 0 | 4095 |  | point 3: condenser chip 0 DAC0 |
| `eo.pc3_d1` | 21 | 0 | 4095 |  | point 3: condenser chip 0 DAC1 |
| `eo.pc3_d2` | 252 | 0 | 4095 |  | point 3: condenser chip 0 DAC2 |
| `eo.pc3_d3` | 140 | 0 | 4095 |  | point 3: condenser chip 0 DAC3 |
| `eo.pc4_pa` | 1000 | 0 | 100000 | pA | Optibeam table point 4: probe current (0 = unused) |
| `eo.pc4_d0` | 827 | 0 | 4095 |  | point 4: condenser chip 0 DAC0 |
| `eo.pc4_d1` | 155 | 0 | 4095 |  | point 4: condenser chip 0 DAC1 |
| `eo.pc4_d2` | 250 | 0 | 4095 |  | point 4: condenser chip 0 DAC2 |
| `eo.pc4_d3` | 4 | 0 | 4095 |  | point 4: condenser chip 0 DAC3 |
| `eo.pc5_pa` | 0 | 0 | 100000 | pA | Optibeam table point 5: probe current (0 = unused) |
| `eo.pc5_d0` | 0 | 0 | 4095 |  | point 5: condenser chip 0 DAC0 |
| `eo.pc5_d1` | 0 | 0 | 4095 |  | point 5: condenser chip 0 DAC1 |
| `eo.pc5_d2` | 0 | 0 | 4095 |  | point 5: condenser chip 0 DAC2 |
| `eo.pc5_d3` | 0 | 0 | 4095 |  | point 5: condenser chip 0 DAC3 |
| `eo.pc6_pa` | 0 | 0 | 100000 | pA | Optibeam table point 6: probe current (0 = unused) |
| `eo.pc6_d0` | 0 | 0 | 4095 |  | point 6: condenser chip 0 DAC0 |
| `eo.pc6_d1` | 0 | 0 | 4095 |  | point 6: condenser chip 0 DAC1 |
| `eo.pc6_d2` | 0 | 0 | 4095 |  | point 6: condenser chip 0 DAC2 |
| `eo.pc6_d3` | 0 | 0 | 4095 |  | point 6: condenser chip 0 DAC3 |
| `eo.c3dac2` | 3006 | 0 | 4095 |  | chip 3 DAC2 constant |
| `eo.c3dac3` | 565 | 0 | 4095 |  | chip 3 DAC3 constant |
| `eo.xstart` | 110 | 0 | 4095 |  | chip 2 DAC1 X start offset, full frame |
| `eo.xstart_spot` | 41 | 0 | 4095 |  | chip 2 DAC1 in spot mode |
| `eo.wob_k` | 50000 | 0 | 1e8 |  | wobble amplitude = k * pct / mag counts |
| `eo.wob_max` | 766 | 0 | 2047 |  | wobble amplitude clamp |
| `eo.slope0` | 27066 | 0 | 65535 |  | X ramp slope (chip 2 DAC4) speed 0 |
| `eo.slope1` | 13500 | 0 | 65535 |  | speed 1 |
| `eo.slope2` | 6717 | 0 | 65535 |  | speed 2 |
| `eo.slope3` | 3350 | 0 | 65535 |  | speed 3 |
| `eo.slope4` | 1680 | 0 | 65535 |  | speed 4 |
| `eo.slope5` | 837 | 0 | 65535 |  | speed 5 |
| `eo.slope6` | 30998 | 0 | 65535 |  | speed 6 |
| `eo.slope7` | 15499 | 0 | 65535 |  | speed 7 |
| `eo.slope8` | 7749 | 0 | 65535 |  | speed 8 |
| `eo.slope9` | 3899 | 0 | 65535 |  | speed 9 |
| `eo.line0_us` | 124 | 10 | 1e7 | us | line period at speed 0 |
| `eo.line1_us` | 207 | 10 | 1e7 | us | speed 1 |
| `eo.line2_us` | 372 | 10 | 1e7 | us | speed 2 |
| `eo.line3_us` | 703 | 10 | 1e7 | us | speed 3 |
| `eo.line4_us` | 1405 | 10 | 1e7 | us | speed 4 |
| `eo.line5_us` | 2811 | 10 | 1e7 | us | speed 5 |
| `eo.line6_us` | 5608 | 10 | 1e7 | us | speed 6 |
| `eo.line7_us` | 11220 | 10 | 1e7 | us | speed 7 |
| `eo.line8_us` | 22430 | 10 | 1e7 | us | speed 8 |
| `eo.line9_us` | 44870 | 10 | 1e7 | us | speed 9 |
| `eo.step_line_us` | 44870 | 10 | 1e7 | us | stepped speeds 10-15: line = (r0A+1) * this |

## Internal scan

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `scan.y0` | 511 | 0 | 65535 |  | Y value of the first line |
| `scan.ystep` | 84 | 1 | 65535 |  | Y increment per line |
| `scan.lines` | 768 | 1 | 4096 |  | lines per frame |
| `scan.flyback_ms` | 360 | 0 | 10000 | ms | frame flyback (F1 high, Y parked) |
| `scan.park_y` | 511 | 0 | 65535 |  | Y value during flyback |
| `scan.f2_us` | 550 | 1 | 100000 | us | line gate high time |
| `scan.f2_frac` | 0.25 | 0.01 | 0.9 |  | line gate high time cap as a fraction of the line |
| `scan.yw_us` | 27 | 0 | 1000 | us | Y write delay after the line gate rises |
| `scan.df_us` | 22 | 0 | 1000 | us | dynamic-focus write delay after the Y write |
| `scan.trim_ppm` | 0 | -5000 | 5000 | ppm | line period trim against the EO board clock |
| `scan.sync_lpol` | 1 | 0 | 1 |  | OBI LINE_SYNC level while the line gate is high |
| `scan.sync_fpol` | 1 | 0 | 1 |  | OBI FRAME_SYNC level while the frame gate is high (flyback) |
| `scan.ext_gates` | 1 | 0 | 1 |  | 1: hold F1/F2 high in external scan |
| `scan.isr_prio` | 32 | 0 | 255 |  | line timer interrupt priority |

## Display

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `ui.backlight` | 100 | 0 | 128 |  | backlight PWM duty |
| `ui.refresh_ms` | 125 | 30 | 2000 | ms | screen redraw period |
| `ui.spi_mhz` | 16 | 1 | 30 | MHz | display SPI clock after init |
| `ui.clkext` | 0 | 0 | 1 |  | 1: FT813 external crystal |
| `ui.rotate` | 0 | 0 | 1 |  | 1: rotate the screen 180 degrees |
| `ui.punit` | 0 | 0 | 2 |  | high-vacuum pressure unit 0 Torr, 1 mbar, 2 Pa |
| `ui.confirm` | 1 | 0 | 1 |  | 1: confirm vent and VP changes on the touch screen |

## Buttons

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `btn.deb_ms` | 30 | 1 | 500 | ms | button debounce |
| `btn.1` | 1 | 0 | 6 |  | button 1 action: 0 none 1 safe 2 beam on 3 beam off 4 stage stop 5 EHT off 6 abort |
| `btn.2` | 4 | 0 | 6 |  | button 2 action |
| `btn.3` | 0 | 0 | 6 |  | button 3 action |

## USB

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `usb.tel_ms` | 250 | 0 | 60000 | ms | status telemetry period (0 = off) |

## System

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `sys.vacloss_abrupt` | 1 | 0 | 1 |  | 1: vacuum loss with the beam on cuts supplies at once; 0: ramp down |
| `sys.pump_warn_min` | 40 | 1 | 600 | min | warn if pump-down has not reached ready after this |
| `sys.vent_exit_vp` | 1 | 0 | 1 |  | 1: leave VP (TO 10) before venting |
| `sys.save_delay_ms` | 3000 | 0 | 600000 | ms | write settings to flash this long after the last change |

## Debug

| Name | Default | Min | Max | Unit | Description |
|---|---|---|---|---|---|
| `dbg.raw` | 0 | 0 | 1 |  | 1: allow raw link commands (bypass interlocks) |
