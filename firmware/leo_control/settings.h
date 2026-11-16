// Runtime settings: every tunable number lives here, is readable/writable over USB
// ("get"/"set"/"list") and is stored in program flash (LittleFS file /settings.txt).
//
// Flags: FL_OP  = operating value (kV, focus, ...) changed by operator commands;
//        FL_ST  = internal persisted state (beam state, filament-off time), not for users;
//        FL_INT = integer-valued.
// Defaults come from the interface specs in specifications/ (captures of the original system).
#pragma once
#include <Arduino.h>

#define FL_OP  1
#define FL_ST  2
#define FL_INT 4

// X(id, name, default, min, max, unit, flags, description)
#define SETTINGS_TABLE(X) \
/* ---- EHT / gun supply link ---- */ \
X(EHT_POLL_S,        "eht.poll_s",        4.5,   0.5,  30,     "s",  0,      "status (?S) poll period") \
X(EHT_TIMEOUT_MS,    "eht.timeout_ms",    300,   50,   5000,   "ms", FL_INT, "reply timeout") \
X(EHT_GAP_MS,        "eht.gap_ms",        17,    0,    1000,   "ms", FL_INT, "gap after a reply before the next command") \
X(EHT_RETRIES,       "eht.retries",       1,     0,    5,      "",   FL_INT, "resends after a timeout") \
X(EHT_TX_INV,        "eht.tx_inv",        0,     0,    1,      "",   FL_INT, "invert transmit data (0: pin high = light on = idle)") \
X(EHT_RX_INV,        "eht.rx_inv",        1,     0,    1,      "",   FL_INT, "invert receive data (1: HFBR-2521Z pulls low with light on)") \
X(EHT_RAMP_MS,       "eht.ramp_ms",       466,   100,  5000,   "ms", FL_INT, "filament / >20 kV ramp step interval") \
X(EHT_FIL_START_MA,  "eht.fil_start_ma",  44,    16,   500,    "mA", FL_INT, "first filament step at beam on") \
X(EHT_FIL_FAST_STEP, "eht.fil_fast_step", 147,   1,    500,    "mA", FL_INT, "fast warm-up step") \
X(EHT_FIL_FAST_TO,   "eht.fil_fast_to",   1812,  16,   4000,   "mA", FL_INT, "end of fast warm-up") \
X(EHT_FIL_PAUSE_MS,  "eht.fil_pause_ms",  1350,  0,    10000,  "ms", FL_INT, "pause between fast and slow warm-up") \
X(EHT_FIL_SLOW_STEP, "eht.fil_slow_step", 39,    1,    500,    "mA", FL_INT, "slow approach step (also the max single adjust step with the beam on)") \
X(EHT_FIL_DOWN_START,"eht.fil_down_start",2320,  16,   4000,   "mA", FL_INT, "ramp-down starts at min(current, this)") \
X(EHT_FIL_DOWN_STEP, "eht.fil_down_step", 147,   1,    500,    "mA", FL_INT, "ramp-down step") \
X(EHT_FIL_OFF_MA,    "eht.fil_off_ma",    110,   16,   1000,   "mA", FL_INT, "ramp-down ends here, then supplies off") \
X(EHT_FIL_COOL_S,    "eht.fil_cool_s",    30,    0,    900,    "s",  0,      "filament cool-down wait before any pressure change") \
X(EHT_FIL_MAX_MA,    "eht.fil_max_ma",    2800,  16,   4111,   "mA", FL_INT, "upper limit for the filament setpoint") \
X(EHT_KV_START,      "eht.kv_start",      0.1,   0.03, 1,      "kV", 0,      "first EHT value at beam on") \
X(EHT_KV_RAMP_ABOVE, "eht.kv_ramp_above", 20,    1,    30,     "kV", 0,      "kV changes above this are ramped") \
X(EHT_KV_RAMP_STEP,  "eht.kv_ramp_step",  1.0,   0.1,  5,      "kV", 0,      "ramp step above eht.kv_ramp_above") \
X(EHT_KV_MIN,        "eht.kv_min",        0.5,   0.1,  30,     "kV", 0,      "lowest allowed kV setpoint") \
X(EHT_KV_MAX,        "eht.kv_max",        30,    1,    30,     "kV", 0,      "highest allowed kV setpoint") \
X(EHT_EMIS_MAX_UA,   "eht.emis_max_ua",   400,   0,    409.5,  "uA", 0,      "highest allowed emission setpoint") \
X(EHT_ON_DELAY_MS,   "eht.on_delay_ms",   1000,  0,    10000,  "ms", FL_INT, "beam on: emission set -> EHT on") \
X(EHT_FILON_DELAY_MS,"eht.filon_delay_ms",470,   0,    10000,  "ms", FL_INT, "beam on: EHT on -> filament supply on") \
X(EHT_OFF_DELAY_MS,  "eht.off_delay_ms",  700,   0,    10000,  "ms", FL_INT, "beam off: detectors off (0301) -> EHT off (0201)") \
X(EHT_O_BASE,        "eht.o_base",        1,     0,    65535,  "",   FL_INT, ".O bit always set (0x0001)") \
X(EHT_O_DETECT,      "eht.o_detect",      1030,  0,    65535,  "",   FL_INT, ".O detector/collector supply bits (0x0406)") \
X(EHT_O_SCINT,       "eht.o_scint",       2048,  0,    65535,  "",   FL_INT, ".O scintillator HV bit (0x0800)") \
X(EHT_O_EHT,         "eht.o_eht",         256,   0,    65535,  "",   FL_INT, ".O accelerating voltage bit (0x0100)") \
X(EHT_O_FIL,         "eht.o_fil",         512,   0,    65535,  "",   FL_INT, ".O filament supply bit (0x0200)") \
X(EHT_SCINT_OFF_VP,  "eht.scint_off_vp",  1,     0,    1,      "",   FL_INT, "1: scintillator HV off while the chamber is in VP") \
X(EHT_FILTYPE,       "eht.filtype",       1,     0,    15,     "",   FL_INT, ".T filament type") \
X(EHT_ANODE,         "eht.anode",         1,     0,    15,     "",   FL_INT, ".A anode type") \
/* ---- operating values (persisted, changed by commands) ---- */ \
X(OP_KV,             "op.kv",             5,     0.1,  30,     "kV", FL_OP,  "accelerating voltage setpoint") \
X(OP_FIL_MA,         "op.fil_ma",         2468,  16,   4111,   "mA", FL_OP|FL_INT, "filament current setpoint") \
X(OP_EMIS_UA,        "op.emis_ua",        400,   0,    409.5,  "uA", FL_OP,  "emission current setpoint") \
X(OP_COLL_V,         "op.coll_v",         300,   -409, 409,    "V",  FL_OP,  "SE collector bias") \
X(OP_PM1,            "op.pm1",            1912,  0,    4095,   "",   FL_OP|FL_INT, "PM HV channel 1 (brightness)") \
X(OP_PM2,            "op.pm2",            400,   0,    4095,   "",   FL_OP|FL_INT, "PM HV channel 2") \
X(OP_PM3,            "op.pm3",            400,   0,    4095,   "",   FL_OP|FL_INT, "PM HV channel 3") \
X(OP_VP_PA,          "op.vp_pa",          20,    1,    400,    "Pa", FL_OP,  "VP chamber pressure target") \
X(OP_MAG,            "op.mag",            100,   1,    1e6,    "x",  FL_OP,  "magnification") \
X(OP_ROT,            "op.rot",            0,     -360, 360,    "deg",FL_OP,  "scan rotation") \
X(OP_WD,             "op.wd",             15,    2,    150,    "mm", FL_OP,  "working distance as LEO-32 displayed it: sets the objective (eo.model 1) and the scan geometry") \
X(OP_TILT,           "op.tilt",           0,     -89,  89,     "deg",FL_OP,  "tilt correction angle (0 = off)") \
X(OP_SPEED,          "op.speed",          5,     0,    15,     "",   FL_OP|FL_INT, "internal scan speed 0-15") \
X(OP_SCAN,           "op.scan",           0,     0,    3,      "",   FL_OP|FL_INT, "scan mode 0 external (OBI), 1 raster, 2 line, 3 spot") \
X(OP_OBJ_C,          "op.obj_c",          790,   0,    4095,   "",   FL_OP,  "objective coarse (chip 1 DAC0)") \
X(OP_OBJ_F,          "op.obj_f",          2234,  0,    4095,   "",   FL_OP,  "objective fine / focus (chip 1 DAC1)") \
X(OP_STIG_X,         "op.stig_x",         2048,  0,    4095,   "",   FL_OP|FL_INT, "stigmator X (chip 0 DAC6)") \
X(OP_STIG_Y,         "op.stig_y",         2048,  0,    4095,   "",   FL_OP|FL_INT, "stigmator Y (chip 0 DAC7)") \
X(OP_COND0,          "op.cond0",          45,    0,    4095,   "",   FL_OP,  "condenser chip 0 DAC0") \
X(OP_COND1,          "op.cond1",          182,   0,    4095,   "",   FL_OP,  "condenser chip 0 DAC1") \
X(OP_COND2,          "op.cond2",          23,    0,    4095,   "",   FL_OP,  "condenser chip 0 DAC2") \
X(OP_COND3,          "op.cond3",          218,   0,    4095,   "",   FL_OP,  "condenser chip 0 DAC3") \
X(OP_PROBE_PA,       "op.probe_pa",        300,   1,    100000, "pA",  FL_OP , "probe current (Optibeam: sets the condensers through the column model or the eo.pc* table)") \
X(OP_OBEAM,          "op.obeam",          0,     0,    2,      "",   FL_OP|FL_INT, "Optibeam mode 0 Normal (resolution) / 1 Depth / 2 Auto resolution (picks the probe current)") \
X(OP_APERTURE,       "op.aperture",       50,    5,    1000,   "um", FL_OP,  "final aperture diameter entered by the operator (LEO-32 offered 30 and 50 um)") \
X(OP_SHIFT_X,        "op.shift_x",        0,     -2047,2047,   "",   FL_OP,  "beam shift X (image axes, DAC counts)") \
X(OP_SHIFT_Y,        "op.shift_y",        0,     -2047,2047,   "",   FL_OP,  "beam shift Y") \
X(OP_SPOT_X,         "op.spot_x",         32768, 0,    65535,  "",   FL_OP|FL_INT, "spot mode X position") \
X(OP_SPOT_Y,         "op.spot_y",         32768, 0,    65535,  "",   FL_OP|FL_INT, "spot mode Y position") \
X(OP_LINE_Y,         "op.line_y",         32768, 0,    65535,  "",   FL_OP|FL_INT, "line scan Y position") \
X(OP_WOB_PCT,        "op.wob_pct",        0,     0,    100,    "%",  FL_OP,  "focus wobble amplitude (0 = off)") \
X(OP_WOB_FAST,       "op.wob_fast",       1,     0,    1,      "",   FL_OP|FL_INT, "focus wobble rate 1 fast, 0 slow") \
X(OP_DYNF,           "op.dynf",           0,     -4000,4000,   "",   FL_OP,  "dynamic focus: objective fine change over the frame height (internal raster)") \
/* ---- persisted internal state ---- */ \
X(ST_BEAM,           "state.beam",        0,     0,    3,      "",   FL_ST|FL_INT, "0 off, 1 on, 2 in transition (filament current unknown), 3 EHT off with the filament lit") \
X(ST_FIL_OFF_T,      "state.fil_off_t",   0,     0,    4e9,    "s",  FL_ST|FL_INT, "RTC time the filament supply went off") \
/* ---- stage / vacuum link ---- */ \
X(STG_POLL_MS,       "stg.poll_ms",       1200,  100,  10000,  "ms", FL_INT, "idle poll period for .VT and .SD") \
X(STG_POLL_MOVE_MS,  "stg.poll_move_ms",  150,   50,   2000,   "ms", FL_INT, ".SD poll period while an axis moves") \
X(STG_SP_MS,         "stg.sp_ms",         300,   50,   5000,   "ms", FL_INT, ".SP repeat period while a stage event persists") \
X(STG_TIMEOUT_MS,    "stg.timeout_ms",    1000,  100,  5000,   "ms", FL_INT, "reply timeout") \
X(STG_GAP_MS,        "stg.gap_ms",        10,    0,    1000,   "ms", FL_INT, "gap after a reply") \
X(STG_RETRIES,       "stg.retries",       1,     0,    5,      "",   FL_INT, "resends after a timeout") \
X(STG_TX_INV,        "stg.tx_inv",        0,     0,    1,      "",   FL_INT, "invert transmit data") \
X(STG_RX_INV,        "stg.rx_inv",        1,     0,    1,      "",   FL_INT, "invert receive data") \
X(VAC_PEN_A,         "vac.pen_a",         60,    1,    1000,   "",   0,      "Penning: P_Torr = 1/(a * raw^exp)") \
X(VAC_PEN_EXP,       "vac.pen_exp",       0.9,   0.1,  3,      "",   0,      "Penning exponent") \
X(VAC_TA,            "vac.ta",            302,   0,    100000, "raw",FL_INT, ".TA scintillator threshold") \
X(VAC_TB1,           "vac.tb1",           302,   0,    100000, "raw",FL_INT, ".TB accelerating-voltage threshold") \
X(VAC_TB2,           "vac.tb2",           50,    0,    100000, "raw",FL_INT, ".TB hysteresis level") \
X(VAC_TC,            "vac.tc",            302,   0,    100000, "raw",FL_INT, ".TC PM threshold") \
X(VAC_TD1,           "vac.td1",           8210,  0,    100000, "raw",FL_INT, ".TD ion pump threshold (not fitted)") \
X(VAC_TD2,           "vac.td2",           50,    0,    100000, "raw",FL_INT, ".TD hysteresis level") \
X(VAC_TE1,           "vac.te1",           302,   0,    100000, "raw",FL_INT, ".TE filament threshold") \
X(VAC_TE2,           "vac.te2",           50,    0,    100000, "raw",FL_INT, ".TE hysteresis level") \
X(VAC_TH,            "vac.th",            50,    0,    100000, "raw",FL_INT, ".TH EDX threshold") \
X(STG_CPU_X,         "stg.cpu_x",         8148.74, 1,  1e6,    "/mm",0,      "X counts per mm") \
X(STG_CPU_Y,         "stg.cpu_y",         8148.74, 1,  1e6,    "/mm",0,      "Y counts per mm") \
X(STG_CPU_Z,         "stg.cpu_z",         64538.2, 1,  1e6,    "/mm",0,      "Z counts per mm") \
X(STG_CPU_T,         "stg.cpu_t",         11264, 1,    1e6,    "/deg",0,     "T counts per degree") \
X(STG_CPU_R,         "stg.cpu_r",         8448,  1,    1e6,    "/deg",0,     "R counts per degree") \
X(STG_ZERO_X,        "stg.zero_x",        7981171, 0,  16777215,"",  FL_INT, "X count at UI zero") \
X(STG_ZERO_Y,        "stg.zero_y",        7879312, 0,  16777215,"",  FL_INT, "Y count at UI zero") \
X(STG_ZERO_Z,        "stg.zero_z",        7259189, 0,  16777215,"",  FL_INT, "Z count at UI zero") \
X(STG_ZERO_T,        "stg.zero_t",        8388608, 0,  16777215,"",  FL_INT, "T count at UI zero") \
X(STG_ZERO_R,        "stg.zero_r",        8388608, 0,  16777215,"",  FL_INT, "R count at UI zero") \
X(STG_LO_X,          "stg.lo_x",          7981171, 0,  16777215,"",  FL_INT, ".SQ user lower limit X (pumped)") \
X(STG_LO_Y,          "stg.lo_y",          7879312, 0,  16777215,"",  FL_INT, ".SQ user lower limit Y") \
X(STG_LO_Z,          "stg.lo_z",          7259189, 0,  16777215,"",  FL_INT, ".SQ user lower limit Z") \
X(STG_LO_T,          "stg.lo_t",          7374848, 0,  16777215,"",  FL_INT, ".SQ user lower limit T") \
X(STG_LO_R,          "stg.lo_r",          5178369, 0,  16777215,"",  FL_INT, ".SQ user lower limit R") \
X(STG_HI_X,          "stg.hi_x",          8796045, 0,  16777215,"",  FL_INT, ".SJ user upper limit X (pumped)") \
X(STG_HI_Y,          "stg.hi_y",          8897904, 0,  16777215,"",  FL_INT, ".SJ user upper limit Y") \
X(STG_HI_Z,          "stg.hi_z",          9518027, 0,  16777215,"",  FL_INT, ".SJ user upper limit Z") \
X(STG_HI_T,          "stg.hi_t",          9402368, 0,  16777215,"",  FL_INT, ".SJ user upper limit T") \
X(STG_HI_R,          "stg.hi_r",          14471166,0,  16777215,"",  FL_INT, ".SJ user upper limit R") \
X(STG_AIR_LO_X,      "stg.air_lo_x",      8266377, 0,  16777215,"",  FL_INT, "X lower limit at air (35 mm)") \
X(STG_AIR_LO_Y,      "stg.air_lo_y",      8164518, 0,  16777215,"",  FL_INT, "Y lower limit at air") \
X(STG_AIR_HI_X,      "stg.air_hi_x",      8510839, 0,  16777215,"",  FL_INT, "X upper limit at air (65 mm)") \
X(STG_AIR_HI_Y,      "stg.air_hi_y",      8408980, 0,  16777215,"",  FL_INT, "Y upper limit at air") \
X(STG_HWLO_X,        "stg.hwlo_x",        7981171, 0,  16777215,"",  FL_INT, ".SO hardware lower limit X (homing)") \
X(STG_HWLO_Y,        "stg.hwlo_y",        7879312, 0,  16777215,"",  FL_INT, ".SO hardware lower limit Y") \
X(STG_HWLO_Z,        "stg.hwlo_z",        7259189, 0,  16777215,"",  FL_INT, ".SO hardware lower limit Z") \
X(STG_HWLO_T,        "stg.hwlo_t",        7374848, 0,  16777215,"",  FL_INT, ".SO hardware lower limit T") \
X(STG_HWLO_R,        "stg.hwlo_r",        5178369, 0,  16777215,"",  FL_INT, ".SO hardware lower limit R") \
X(STG_SPD_X,         "stg.spd_x",         1500,  1,    100000, "",   FL_INT, ".SB speed X at start-up") \
X(STG_SPD_Y,         "stg.spd_y",         1500,  1,    100000, "",   FL_INT, ".SB speed Y at start-up") \
X(STG_SPD_Z,         "stg.spd_z",         3000,  1,    100000, "",   FL_INT, ".SB speed Z at start-up") \
X(STG_SPD_T,         "stg.spd_t",         2000,  1,    100000, "",   FL_INT, ".SB speed T at start-up") \
X(STG_SPD_R,         "stg.spd_r",         3000,  1,    100000, "",   FL_INT, ".SB speed R at start-up") \
X(STG_HSPD_X,        "stg.hspd_x",        1500,  1,    100000, "",   FL_INT, ".SB speed X while homing") \
X(STG_HSPD_Y,        "stg.hspd_y",        1500,  1,    100000, "",   FL_INT, ".SB speed Y while homing") \
X(STG_HSPD_Z,        "stg.hspd_z",        3000,  1,    100000, "",   FL_INT, ".SB speed Z while homing") \
X(STG_HSPD_T,        "stg.hspd_t",        2000,  1,    100000, "",   FL_INT, ".SB speed T while homing") \
X(STG_HSPD_R,        "stg.hspd_r",        4000,  1,    100000, "",   FL_INT, ".SB speed R while homing") \
X(STG_PSPD_X,        "stg.pspd_x",        1500,  1,    100000, "",   FL_INT, ".SB speed X after homing") \
X(STG_PSPD_Y,        "stg.pspd_y",        1500,  1,    100000, "",   FL_INT, ".SB speed Y after homing") \
X(STG_PSPD_Z,        "stg.pspd_z",        2100,  1,    100000, "",   FL_INT, ".SB speed Z after homing") \
X(STG_PSPD_T,        "stg.pspd_t",        1300,  1,    100000, "",   FL_INT, ".SB speed T after homing") \
X(STG_PSPD_R,        "stg.pspd_r",        4000,  1,    100000, "",   FL_INT, ".SB speed R after homing") \
X(STG_RAMP_A,        "stg.ramp_a",        100,   0,    100000, "",   FL_INT, ".SC ramp value a (all axes)") \
X(STG_RAMP_B,        "stg.ramp_b",        200,   0,    100000, "",   FL_INT, ".SC ramp value b") \
X(STG_RAMP_C,        "stg.ramp_c",        30,    0,    100000, "",   FL_INT, ".SC ramp value c") \
X(STG_SV_X,          "stg.sv_x",          3926,  1,    1e8,    "",   FL_INT, ".SV step size X (1/32 nm per count)") \
X(STG_SV_Y,          "stg.sv_y",          3926,  1,    1e8,    "",   FL_INT, ".SV step size Y") \
X(STG_SV_Z,          "stg.sv_z",          495,   1,    1e8,    "",   FL_INT, ".SV step size Z") \
X(STG_SV_T,          "stg.sv_t",          2840910,1,   1e8,    "",   FL_INT, ".SV step size T (1/32 n-deg)") \
X(STG_SV_R,          "stg.sv_r",          3787880,1,   1e8,    "",   FL_INT, ".SV step size R") \
X(STG_HOME_X,        "stg.home_x",        7985269, 0,  16777215,"",  FL_INT, ".SA X position set after homing") \
X(STG_HOME_Y,        "stg.home_y",        7883410, 0,  16777215,"",  FL_INT, ".SA Y") \
X(STG_HOME_Z,        "stg.home_z",        7292522, 0,  16777215,"",  FL_INT, ".SA Z") \
X(STG_HOME_T,        "stg.home_t",        8377344, 0,  16777215,"",  FL_INT, ".SA T") \
X(STG_HOME_R,        "stg.home_r",        8388608, 0,  16777215,"",  FL_INT, ".SA R") \
X(STG_PARK_X,        "stg.park_x",        8388608, 0,  16777215,"",  FL_INT, "position after homing X (50 mm)") \
X(STG_PARK_Y,        "stg.park_y",        8286749, 0,  16777215,"",  FL_INT, "position after homing Y (50 mm)") \
X(STG_PARK_Z,        "stg.park_z",        7323727, 0,  16777215,"",  FL_INT, "position after homing Z (1 mm)") \
X(STG_PARK_T,        "stg.park_t",        8388608, 0,  16777215,"",  FL_INT, "position after homing T") \
X(STG_PARK_R,        "stg.park_r",        8388608, 0,  16777215,"",  FL_INT, "position after homing R") \
X(STG_VENT_Z,        "stg.vent_z",        7291458, 0,  16777215,"",  FL_INT, "Z count to drive to before venting (0.5 mm)") \
X(STG_VENT_Z_EN,     "stg.vent_z_en",     1,     0,    1,      "",   FL_INT, "1: lower Z before venting when the stage is homed") \
X(STG_REQ_HOME,      "stg.req_home",      1,     0,    1,      "",   FL_INT, "1: refuse go-to moves until all axes are initialised") \
X(STG_MOVE_TO_S,     "stg.move_to_s",     120,   5,    1000,   "s",  0,      "timeout for a move or one homing axis") \
X(STG_JOY_GAIN,      "stg.joy_gain",      1.0,   0.01, 100,    "",   0,      "joystick sensitivity: multiplies the .SW pixel size") \
X(STG_JOY_FIELD_M,   "stg.joy_field_m",   1.1458e-4, 1e-6, 1,  "m",  0,      "field of view at 1x divided by screen pixels (.SW = field*gain/mag)") \
X(STG_JOY_HYST,      "stg.joy_hyst",      0.05,  0,    1,      "",   0,      "resend .SW when it changes by more than this fraction") \
/* ---- VP controller link ---- */ \
X(VP_POLL_S,         "vp.poll_s",         4,     0.5,  60,     "s",  0,      "GP poll period (must stay well below vp.wd_s)") \
X(VP_TIMEOUT_MS,     "vp.timeout_ms",     2000,  100,  10000,  "ms", FL_INT, "reply timeout") \
X(VP_GAP_MS,         "vp.gap_ms",         25,    0,    1000,   "ms", FL_INT, "gap after a reply") \
X(VP_RETRIES,        "vp.retries",        1,     0,    5,      "",   FL_INT, "resends after a timeout") \
X(VP_TX_INV,         "vp.tx_inv",         0,     0,    1,      "",   FL_INT, "invert transmit data (VP board fiber polarity unconfirmed)") \
X(VP_RX_INV,         "vp.rx_inv",         1,     0,    1,      "",   FL_INT, "invert receive data") \
X(VP_REQUIRED,       "vp.required",       1,     0,    1,      "",   FL_INT, "1: beam on needs a live VP link in state 3 or 9") \
X(VP_WD_S,           "vp.wd_s",           360,   10,   3600,   "s",  FL_INT, "ST 1: controller comms watchdog") \
X(VP_T_MCPUP,        "vp.t_mcpup",        10,    1,    3600,   "s",  FL_INT, "ST 2: MCP-up timeout") \
X(VP_T_MCPDN,        "vp.t_mcpdn",        90,    1,    3600,   "s",  FL_INT, "ST 3: MCP-down timeout") \
X(VP_T_TARGET,       "vp.t_target",       240,   1,    3600,   "s",  FL_INT, "ST 4: target timeout") \
X(VP_T_GUN,          "vp.t_gun",          5,     1,    3600,   "s",  FL_INT, "ST 5: gun-enable timeout") \
X(VP_MC_DOWN,        "vp.mc_down",        900,   0,    4095,   "",   FL_INT, "MC down threshold (gauge counts)") \
X(VP_MC_UP_FRAC,     "vp.mc_up_frac",     0.8,   0.1,  1,      "",   0,      "MC up = frac * gauge counts at the target") \
X(VP_MC_UP_MIN,      "vp.mc_up_min",      100,   0,    4095,   "",   FL_INT, "MC up used for low targets") \
X(VP_MC_LOWP,        "vp.mc_lowp",        10,    0,    100,    "Pa", 0,      "targets at or below this use vp.mc_up_min") \
X(VP_HP_GAIN,        "vp.hp_gain",        1.094, 0.1,  10,     "",   0,      "HP setpoint gain (LEO.INI)") \
X(VP_HP_OFF,         "vp.hp_off",         190,   -4095,4095,   "",   0,      "HP setpoint offset") \
X(VP_HP_HIK,         "vp.hp_hik",         0.015, 0,    1,      "",   0,      "extra HP gain per hp_hip above hp_hip") \
X(VP_HP_HIP,         "vp.hp_hip",         250,   1,    2000,   "Pa", 0,      "HP high-pressure correction knee") \
X(VP_BAND_LO,        "vp.band_lo",        0.0175,0,    0.5,    "",   0,      "HP a = raw * (1 - band_lo)") \
X(VP_BAND_HI,        "vp.band_hi",        0.0155,0,    0.5,    "",   0,      "HP b = raw * (1 + band_hi)") \
X(VP_V_GAIN,         "vp.v_gain",         0.005005, 0, 1,      "V",  0,      "Pirani volts per count") \
X(VP_V_OFF,          "vp.v_off",          -0.01706, -1, 1,     "V",  0,      "Pirani volts offset") \
X(VP_PIR_P0,         "vp.pir_p0",         0,     0,    1e5,    "Pa", 0,      "Pirani table point 0 pressure") \
X(VP_PIR_P1,         "vp.pir_p1",         1,     0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P2,         "vp.pir_p2",         10,    0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P3,         "vp.pir_p3",         20,    0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P4,         "vp.pir_p4",         50,    0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P5,         "vp.pir_p5",         100,   0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P6,         "vp.pir_p6",         1000,  0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_P7,         "vp.pir_p7",         2240,  0,    1e5,    "Pa", 0,      "") \
X(VP_PIR_V0,         "vp.pir_v0",         2.000, 0,    12,     "V",  0,      "Pirani table point 0 voltage") \
X(VP_PIR_V1,         "vp.pir_v1",         2.99,  0,    12,     "V",  0,      "") \
X(VP_PIR_V2,         "vp.pir_v2",         4.49,  0,    12,     "V",  0,      "") \
X(VP_PIR_V3,         "vp.pir_v3",         5.104, 0,    12,     "V",  0,      "") \
X(VP_PIR_V4,         "vp.pir_v4",         5.737, 0,    12,     "V",  0,      "") \
X(VP_PIR_V5,         "vp.pir_v5",         6.345, 0,    12,     "V",  0,      "") \
X(VP_PIR_V6,         "vp.pir_v6",         8.84,  0,    12,     "V",  0,      "") \
X(VP_PIR_V7,         "vp.pir_v7",         9.40,  0,    12,     "V",  0,      "") \
X(VP_PUMP_DELAY_MS,  "vp.pump_delay_ms",  1500,  0,    60000,  "ms", FL_INT, "TO 3 this long after .VL P") \
X(VP_ENTER_TO_S,     "vp.enter_to_s",     600,   10,   7200,   "s",  0,      "give up waiting for AT_HP after this") \
X(VP_EXIT_TO_S,      "vp.exit_to_s",      240,   10,   7200,   "s",  0,      "give up waiting for GUN_ENABLE_OK after this") \
/* ---- EO board link and optics ---- */ \
X(EO_TX_INV,         "eo.tx_inv",         0,     0,    1,      "",   FL_INT, "invert F1/F2/F3 outputs") \
X(EO_RX_INV,         "eo.rx_inv",         1,     0,    1,      "",   FL_INT, "invert F4 input") \
X(EO_BAUD,           "eo.baud",           3686400, 1e6, 6e6,   "bit/s",0,    "F3/F4 bit rate") \
X(EO_GAP_US,         "eo.gap_us",         14,    6,    1000,   "us", 0,      "minimum idle between frames") \
X(EO_REPLY_US,       "eo.reply_us",       40,    5,    1000,   "us", 0,      "wait for an F4 reply start bit") \
X(EO_LENS_US,        "eo.lens_us",        940,   0,    100000, "us", 0,      "spacing of lens read-modify-write frames") \
X(EO_HB_S,           "eo.hb_s",           2,     0,    60,     "s",  0,      "link check read period (0 = off)") \
X(EO_RMW,            "eo.rmw",            1,     0,    1,      "",   FL_INT, "1: read control/routing before lens writes, like the original") \
X(EO_REPEAT,         "eo.repeat",         4,     1,    8,      "",   FL_INT, "repeats of coil-weight and shift writes") \
X(EO_SPD_REPEAT,     "eo.spd_repeat",     3,     1,    8,      "",   FL_INT, "repeats of the scan-speed block") \
X(EO_RANGE_WAIT_MS,  "eo.range_wait_ms",  45,    0,    1000,   "ms", FL_INT, "range relay settling before new weights") \
X(EO_WMAX,           "eo.wmax",           32000, 1000, 32767,  "",   FL_INT, "largest coil-weight offset before switching to a less sensitive range") \
X(EO_KV_REF,         "eo.kv_ref",         20,    0.5,  30,     "kV", 0,      "kV at which the range calibration was taken") \
X(EO_WD_REF,         "eo.wd_ref",         15,    1,    60,     "mm", 0,      "WD at which the range calibration was taken") \
X(EO_WD_EXP,         "eo.wd_exp",         -0.645,-3,   3,      "",   0,      "scan size ~ (WD/wd_ref)^exp") \
X(EO_WD_ROT,         "eo.wd_rot",         1.6,   -20,  20,     "deg/mm",0,   "lens rotation per mm of WD (sign to verify)") \
X(EO_GA,             "eo.ga",             1.04,  0.1,  10,     "",   0,      "coil A gain") \
X(EO_GB,             "eo.gb",             1.0,   0.1,  10,     "",   0,      "coil B gain") \
X(EO_K0,             "eo.k0",             44520,  1,   1e10,   "",   0,      "range 0 scale (weight x mag at kv_ref, wd_ref)") \
X(EO_K1,             "eo.k1",             347200, 1,   1e10,   "",   0,      "range 1 scale") \
X(EO_K2,             "eo.k2",             2846600,1,   1e10,   "",   0,      "range 2 scale") \
X(EO_K3,             "eo.k3",             23909000,1,  1e10,   "",   0,      "range 3 scale") \
X(EO_K4,             "eo.k4",             172190000,1, 1e10,   "",   0,      "range 4 scale") \
X(EO_D0,             "eo.d0",             -6.868,-90,  90,     "deg",0,      "range 0 angle trim") \
X(EO_D1,             "eo.d1",             -6.648,-90,  90,     "deg",0,      "range 1 angle trim") \
X(EO_D2,             "eo.d2",             -6.481,-90,  90,     "deg",0,      "range 2 angle trim") \
X(EO_D3,             "eo.d3",             -6.435,-90,  90,     "deg",0,      "range 3 angle trim") \
X(EO_D4,             "eo.d4",             -6.606,-90,  90,     "deg",0,      "range 4 angle trim") \
X(EO_KY0,            "eo.ky0",            0.9767,0.5,  2,      "",   0,      "range 0 Y/X gain") \
X(EO_KY1,            "eo.ky1",            0.9767,0.5,  2,      "",   0,      "range 1 Y/X gain") \
X(EO_KY2,            "eo.ky2",            0.9768,0.5,  2,      "",   0,      "range 2 Y/X gain") \
X(EO_KY3,            "eo.ky3",            0.9768,0.5,  2,      "",   0,      "range 3 Y/X gain") \
X(EO_KY4,            "eo.ky4",            0.9767,0.5,  2,      "",   0,      "range 4 Y/X gain") \
X(EO_E0,             "eo.e0",             -0.037,-10,  10,     "deg",0,      "range 0 X-Y orthogonality trim") \
X(EO_E1,             "eo.e1",             -0.255,-10,  10,     "deg",0,      "range 1 orthogonality trim") \
X(EO_E2,             "eo.e2",             -0.422,-10,  10,     "deg",0,      "range 2 orthogonality trim") \
X(EO_E3,             "eo.e3",             -0.469,-10,  10,     "deg",0,      "range 3 orthogonality trim") \
X(EO_E4,             "eo.e4",             -0.292,-10,  10,     "deg",0,      "range 4 orthogonality trim") \
X(EO_CX0,            "eo.cx0",            2088,  0,    4095,   "",   FL_INT, "range 0 X centring (chip 2 DAC2)") \
X(EO_CX1,            "eo.cx1",            2088,  0,    4095,   "",   FL_INT, "range 1 X centring") \
X(EO_CX2,            "eo.cx2",            2141,  0,    4095,   "",   FL_INT, "range 2 X centring") \
X(EO_CX3,            "eo.cx3",            2158,  0,    4095,   "",   FL_INT, "range 3 X centring") \
X(EO_CX4,            "eo.cx4",            2238,  0,    4095,   "",   FL_INT, "range 4 X centring") \
X(EO_CY0,            "eo.cy0",            1978,  0,    4095,   "",   FL_INT, "range 0 Y centring (chip 3 DAC0)") \
X(EO_CY1,            "eo.cy1",            1958,  0,    4095,   "",   FL_INT, "range 1 Y centring") \
X(EO_CY2,            "eo.cy2",            1931,  0,    4095,   "",   FL_INT, "range 2 Y centring") \
X(EO_CY3,            "eo.cy3",            2088,  0,    4095,   "",   FL_INT, "range 3 Y centring") \
X(EO_CY4,            "eo.cy4",            2301,  0,    4095,   "",   FL_INT, "range 4 Y centring") \
X(EO_MAG_MIN,        "eo.mag_min",        10,    1,    1e6,    "x",  0,      "lowest magnification accepted") \
X(EO_MAG_MAX,        "eo.mag_max",        500000,1,    1e7,    "x",  0,      "highest magnification accepted") \
X(EO_KV_OBJ,         "eo.kv_obj",         1,     0,    1,      "",   FL_INT, "1: scale objective coarse with sqrt(relativistic kV) on kV changes") \
X(EO_KV_COND,        "eo.kv_cond",         0,     0,    1,      "",    FL_INT, "1: scale the condenser DACs with sqrt(kV) (only with eo.optibeam = 0)") \
X(EO_OPTIBEAM,       "eo.optibeam",        1,     0,    1,      "",    FL_INT, "1: condenser follows op.probe_pa through the eo.pc* table; 0: op.cond* set directly") \
X(EO_MODEL,         "eo.model",           1,     0,    1,      "",     FL_INT, "1: lenses from the column model (op.wd / op.probe_pa / op.obeam / op.aperture); 0: eo.pc* table and op.obj_* directly") \
X(EO_CAL1,          "eo.cal1",            0.93565, 0.3,  3,      "",     0     , "C1 calibration LEO-32 effectively used (fit; Data.vac 1.0597)") \
X(EO_CAL2,          "eo.cal2",            0.9042, 0.3,  3,      "",     0     , "C2 calibration (fit to the Depth-mode C2 ceiling; Data.vac 1.05973)") \
X(EO_CAL3,          "eo.cal3",            0.991194, 0.3,  3,      "",     0     , "objective calibration (Data.vac)") \
X(EO_REM1,          "eo.rem1",            0.0101, -1,   1,      "A",    0     , "C1 remanence (Data.vac)") \
X(EO_REM2,          "eo.rem2",            0.0101094, -1,   1,      "A",    0     , "C2 remanence (Data.vac)") \
X(EO_REM3,          "eo.rem3",            0.0107648, -1,   1,      "A",    0     , "objective remanence (Data.vac)") \
X(EO_XTALK,         "eo.xtalk",           0.0422491, -1,   1,      "",     0     , "C1 / C2 crosstalk (Data.vac)") \
X(EO_WD_A,          "eo.wd_a",            1.21696, 0.5,  2,      "",     0     , "model WD = (op.wd - eo.wd_b) / eo.wd_a (LEO-32 display scale; fit)") \
X(EO_WD_B,          "eo.wd_b",            1.876, -20,  20,     "mm",   0     , "display WD offset (fit)") \
X(EO_KN,            "eo.kn",              0.95935, 0.01, 100,    "",     0     , "Normal mode probe-size constant (fit)") \
X(EO_AN,            "eo.an",              0.91561, 0.1,  10,     "",     0     , "Normal mode optimum-angle scale (fit)") \
X(EO_KD,            "eo.kd",              12.78728, 0.01, 1000,   "",     0     , "Depth mode constant (fit)") \
X(EO_KD0,           "eo.kd0",             1.46246, 0.1,  10,     "",     0     , "gun source-size factor (fit)") \
X(EO_THR,           "eo.thr",             0.95,  0.1,  0.999,  "",     0     , "fraction of the aperture-limited angle above which C2 goes to its limit") \
X(EO_AR2,           "eo.ar2",             50,    1,    100000, "pA",   0     , "Auto resolution probe current at 2 kV (LEO-32 UI 2026-11-15)") \
X(EO_AR5,           "eo.ar5",             70,    1,    100000, "pA",   0     , "Auto resolution probe current at 5 kV") \
X(EO_AR10,          "eo.ar10",            90,    1,    100000, "pA",   0     , "Auto resolution probe current at 10 kV") \
X(EO_AR20,          "eo.ar20",            150,   1,    100000, "pA",   0     , "Auto resolution probe current at 20 kV (log-log interpolated; extrapolated above)") \
X(EO_GUN,           "eo.gun",             0,     0,    1,      "",     FL_INT, "gun table for the column model: 0 LaB6 data as LEO-32 used it (matches the old system); 1 tungsten (the real filament; performance test)") \
X(EO_PA_MIN,        "eo.pa_min",          1,     0.1,  100000, "pA",   0     , "lowest probe current accepted with eo.model 1") \
X(EO_PA_MAX,        "eo.pa_max",          100000, 1,    1e6,    "pA",   0     , "highest probe current accepted with eo.model 1") \
X(EO_PC_KVREF,       "eo.pc_kvref",        5,     0.5,  30,     "kV",  0     , "kV at which the eo.pc* table was taken (captures: 5 kV)") \
X(EO_PC_KVEXP,       "eo.pc_kvexp",        0,     -2,   2,      "",    0     , "condenser = table * (rel. kV / rel. kV_ref)^exp; 0 = no kV dependence") \
X(EO_PC1_PA,         "eo.pc1_pa",          50,    0,    100000, "pA",  0     , "Optibeam table point 1: probe current (0 = unused)") \
X(EO_PC1_D0,         "eo.pc1_d0",          1111,  0,    4095,   "",    0     , "point 1: condenser chip 0 DAC0") \
X(EO_PC1_D1,         "eo.pc1_d1",          137,   0,    4095,   "",    0     , "point 1: condenser chip 0 DAC1") \
X(EO_PC1_D2,         "eo.pc1_d2",          317,   0,    4095,   "",    0     , "point 1: condenser chip 0 DAC2") \
X(EO_PC1_D3,         "eo.pc1_d3",          33,    0,    4095,   "",    0     , "point 1: condenser chip 0 DAC3") \
X(EO_PC2_PA,         "eo.pc2_pa",          300,   0,    100000, "pA",  0     , "Optibeam table point 2: probe current (0 = unused)") \
X(EO_PC2_D0,         "eo.pc2_d0",          1035,  0,    4095,   "",    0     , "point 2: condenser chip 0 DAC0") \
X(EO_PC2_D1,         "eo.pc2_d1",          88,    0,    4095,   "",    0     , "point 2: condenser chip 0 DAC1") \
X(EO_PC2_D2,         "eo.pc2_d2",          254,   0,    4095,   "",    0     , "point 2: condenser chip 0 DAC2") \
X(EO_PC2_D3,         "eo.pc2_d3",          204,   0,    4095,   "",    0     , "point 2: condenser chip 0 DAC3") \
X(EO_PC3_PA,         "eo.pc3_pa",          500,   0,    100000, "pA",  0     , "Optibeam table point 3: probe current (0 = unused)") \
X(EO_PC3_D0,         "eo.pc3_d0",          938,   0,    4095,   "",    0     , "point 3: condenser chip 0 DAC0") \
X(EO_PC3_D1,         "eo.pc3_d1",          21,    0,    4095,   "",    0     , "point 3: condenser chip 0 DAC1") \
X(EO_PC3_D2,         "eo.pc3_d2",          252,   0,    4095,   "",    0     , "point 3: condenser chip 0 DAC2") \
X(EO_PC3_D3,         "eo.pc3_d3",          140,   0,    4095,   "",    0     , "point 3: condenser chip 0 DAC3") \
X(EO_PC4_PA,         "eo.pc4_pa",          1000,  0,    100000, "pA",  0     , "Optibeam table point 4: probe current (0 = unused)") \
X(EO_PC4_D0,         "eo.pc4_d0",          827,   0,    4095,   "",    0     , "point 4: condenser chip 0 DAC0") \
X(EO_PC4_D1,         "eo.pc4_d1",          155,   0,    4095,   "",    0     , "point 4: condenser chip 0 DAC1") \
X(EO_PC4_D2,         "eo.pc4_d2",          250,   0,    4095,   "",    0     , "point 4: condenser chip 0 DAC2") \
X(EO_PC4_D3,         "eo.pc4_d3",          4,     0,    4095,   "",    0     , "point 4: condenser chip 0 DAC3") \
X(EO_PC5_PA,         "eo.pc5_pa",          0,     0,    100000, "pA",  0     , "Optibeam table point 5: probe current (0 = unused)") \
X(EO_PC5_D0,         "eo.pc5_d0",          0,     0,    4095,   "",    0     , "point 5: condenser chip 0 DAC0") \
X(EO_PC5_D1,         "eo.pc5_d1",          0,     0,    4095,   "",    0     , "point 5: condenser chip 0 DAC1") \
X(EO_PC5_D2,         "eo.pc5_d2",          0,     0,    4095,   "",    0     , "point 5: condenser chip 0 DAC2") \
X(EO_PC5_D3,         "eo.pc5_d3",          0,     0,    4095,   "",    0     , "point 5: condenser chip 0 DAC3") \
X(EO_PC6_PA,         "eo.pc6_pa",          0,     0,    100000, "pA",  0     , "Optibeam table point 6: probe current (0 = unused)") \
X(EO_PC6_D0,         "eo.pc6_d0",          0,     0,    4095,   "",    0     , "point 6: condenser chip 0 DAC0") \
X(EO_PC6_D1,         "eo.pc6_d1",          0,     0,    4095,   "",    0     , "point 6: condenser chip 0 DAC1") \
X(EO_PC6_D2,         "eo.pc6_d2",          0,     0,    4095,   "",    0     , "point 6: condenser chip 0 DAC2") \
X(EO_PC6_D3,         "eo.pc6_d3",          0,     0,    4095,   "",    0     , "point 6: condenser chip 0 DAC3") \
X(EO_C3DAC2,         "eo.c3dac2",         3006,  0,    4095,   "",   FL_INT, "chip 3 DAC2 constant") \
X(EO_C3DAC3,         "eo.c3dac3",         565,   0,    4095,   "",   FL_INT, "chip 3 DAC3 constant") \
X(EO_XSTART,         "eo.xstart",         110,   0,    4095,   "",   FL_INT, "chip 2 DAC1 X start offset, full frame") \
X(EO_XSTART_SPOT,    "eo.xstart_spot",    41,    0,    4095,   "",   FL_INT, "chip 2 DAC1 in spot mode") \
X(EO_WOB_K,          "eo.wob_k",          50000, 0,    1e8,    "",   0,      "wobble amplitude = k * pct / mag counts") \
X(EO_WOB_MAX,        "eo.wob_max",        766,   0,    2047,   "",   FL_INT, "wobble amplitude clamp") \
X(EO_SLOPE0,         "eo.slope0",         27066, 0,    65535,  "",   FL_INT, "X ramp slope (chip 2 DAC4) speed 0") \
X(EO_SLOPE1,         "eo.slope1",         13500, 0,    65535,  "",   FL_INT, "speed 1") \
X(EO_SLOPE2,         "eo.slope2",         6717,  0,    65535,  "",   FL_INT, "speed 2") \
X(EO_SLOPE3,         "eo.slope3",         3350,  0,    65535,  "",   FL_INT, "speed 3") \
X(EO_SLOPE4,         "eo.slope4",         1680,  0,    65535,  "",   FL_INT, "speed 4") \
X(EO_SLOPE5,         "eo.slope5",         837,   0,    65535,  "",   FL_INT, "speed 5") \
X(EO_SLOPE6,         "eo.slope6",         30998, 0,    65535,  "",   FL_INT, "speed 6") \
X(EO_SLOPE7,         "eo.slope7",         15499, 0,    65535,  "",   FL_INT, "speed 7") \
X(EO_SLOPE8,         "eo.slope8",         7749,  0,    65535,  "",   FL_INT, "speed 8") \
X(EO_SLOPE9,         "eo.slope9",         3899,  0,    65535,  "",   FL_INT, "speed 9") \
X(EO_LINE0,          "eo.line0_us",       124,   10,   1e7,    "us", 0,      "line period at speed 0") \
X(EO_LINE1,          "eo.line1_us",       207,   10,   1e7,    "us", 0,      "speed 1") \
X(EO_LINE2,          "eo.line2_us",       372,   10,   1e7,    "us", 0,      "speed 2") \
X(EO_LINE3,          "eo.line3_us",       703,   10,   1e7,    "us", 0,      "speed 3") \
X(EO_LINE4,          "eo.line4_us",       1405,  10,   1e7,    "us", 0,      "speed 4") \
X(EO_LINE5,          "eo.line5_us",       2811,  10,   1e7,    "us", 0,      "speed 5") \
X(EO_LINE6,          "eo.line6_us",       5608,  10,   1e7,    "us", 0,      "speed 6") \
X(EO_LINE7,          "eo.line7_us",       11220, 10,   1e7,    "us", 0,      "speed 7") \
X(EO_LINE8,          "eo.line8_us",       22430, 10,   1e7,    "us", 0,      "speed 8") \
X(EO_LINE9,          "eo.line9_us",       44870, 10,   1e7,    "us", 0,      "speed 9") \
X(EO_STEP_LINE_US,   "eo.step_line_us",   44870, 10,   1e7,    "us", 0,      "stepped speeds 10-15: line = (r0A+1) * this") \
X(SCAN_Y0,           "scan.y0",           511,   0,    65535,  "",   FL_INT, "Y value of the first line") \
X(SCAN_YSTEP,        "scan.ystep",        84,    1,    65535,  "",   FL_INT, "Y increment per line") \
X(SCAN_LINES,        "scan.lines",        768,   1,    4096,   "",   FL_INT, "lines per frame") \
X(SCAN_FLYBACK_MS,   "scan.flyback_ms",   360,   0,    10000,  "ms", 0,      "frame flyback (F1 high, Y parked)") \
X(SCAN_PARK_Y,       "scan.park_y",       511,   0,    65535,  "",   FL_INT, "Y value during flyback") \
X(SCAN_F2_US,        "scan.f2_us",        550,   1,    100000, "us", 0,      "line gate high time") \
X(SCAN_F2_FRAC,      "scan.f2_frac",      0.25,  0.01, 0.9,    "",   0,      "line gate high time cap as a fraction of the line") \
X(SCAN_YW_US,        "scan.yw_us",        27,    0,    1000,   "us", 0,      "Y write delay after the line gate rises") \
X(SCAN_DF_US,        "scan.df_us",        22,    0,    1000,   "us", 0,      "dynamic-focus write delay after the Y write") \
X(SCAN_TRIM_PPM,     "scan.trim_ppm",     0,     -5000,5000,   "ppm",0,      "line period trim against the EO board clock") \
X(SCAN_LPOL,         "scan.sync_lpol",    1,     0,    1,      "",   FL_INT, "OBI LINE_SYNC level while the line gate is high") \
X(SCAN_FPOL,         "scan.sync_fpol",    1,     0,    1,      "",   FL_INT, "OBI FRAME_SYNC level while the frame gate is high (flyback)") \
X(SCAN_EXT_GATES,    "scan.ext_gates",    1,     0,    1,      "",   FL_INT, "1: hold F1/F2 high in external scan") \
X(SCAN_ISR_PRIO,     "scan.isr_prio",     32,    0,    255,    "",   FL_INT, "line timer interrupt priority") \
/* ---- display, buttons, USB, system ---- */ \
X(UI_BL,             "ui.backlight",      100,   0,    128,    "",   FL_INT, "backlight PWM duty") \
X(UI_REFRESH_MS,     "ui.refresh_ms",     125,   30,   2000,   "ms", FL_INT, "screen redraw period") \
X(UI_SPI_MHZ,        "ui.spi_mhz",        16,    1,    30,     "MHz",0,      "display SPI clock after init") \
X(UI_CLKEXT,         "ui.clkext",         0,     0,    1,      "",   FL_INT, "1: FT813 external crystal") \
X(UI_ROTATE,         "ui.rotate",         0,     0,    1,      "",   FL_INT, "1: rotate the screen 180 degrees") \
X(UI_PUNIT,          "ui.punit",          0,     0,    2,      "",   FL_INT, "high-vacuum pressure unit 0 Torr, 1 mbar, 2 Pa") \
X(UI_CONFIRM,        "ui.confirm",        1,     0,    1,      "",   FL_INT, "1: confirm vent and VP changes on the touch screen") \
X(BTN_DEB_MS,        "btn.deb_ms",        30,    1,    500,    "ms", FL_INT, "button debounce") \
X(BTN1_ACT,          "btn.1",             1,     0,    6,      "",   FL_INT, "button 1 action: 0 none 1 safe 2 beam on 3 beam off 4 stage stop 5 EHT off 6 abort") \
X(BTN2_ACT,          "btn.2",             4,     0,    6,      "",   FL_INT, "button 2 action") \
X(BTN3_ACT,          "btn.3",             0,     0,    6,      "",   FL_INT, "button 3 action") \
X(USB_TEL_MS,        "usb.tel_ms",        250,   0,    60000,  "ms", FL_INT, "status telemetry period (0 = off)") \
X(SYS_VACLOSS_ABRUPT,"sys.vacloss_abrupt",1,     0,    1,      "",   FL_INT, "1: vacuum loss with the beam on cuts supplies at once; 0: ramp down") \
X(SYS_PUMP_WARN_MIN, "sys.pump_warn_min", 40,    1,    600,    "min",0,      "warn if pump-down has not reached ready after this") \
X(SYS_VENT_EXIT_VP,  "sys.vent_exit_vp",  1,     0,    1,      "",   FL_INT, "1: leave VP (TO 10) before venting") \
X(SYS_SAVE_DELAY_MS, "sys.save_delay_ms", 3000,  0,    600000, "ms", FL_INT, "write settings to flash this long after the last change") \
X(DBG_RAW,           "dbg.raw",           0,     0,    1,      "",   FL_INT, "1: allow raw link commands (bypass interlocks)")

enum SettingId {
#define X(id, ...) id,
  SETTINGS_TABLE(X)
#undef X
  S_COUNT
};

struct SettingMeta {
  const char* name;
  double def, mn, mx;
  const char* unit;
  uint8_t flags;
  const char* desc;
};

extern double S[S_COUNT];
extern const SettingMeta SMETA[S_COUNT];

inline float  sf(SettingId i) { return (float)S[i]; }
inline double sd(SettingId i) { return S[i]; }
inline long   si(SettingId i) { return lround(S[i]); }

void settingsBegin();                      // mount flash, load file
int  settingFind(const char* name);        // -1 if unknown
// Set with range check; returns nullptr or an error text. Calls settingChanged().
const char* settingSet(int id, double v);
void settingDefault(int id);
void settingsTouch();                      // mark dirty (deferred save)
void settingsService(bool linksIdle);      // performs the deferred save
bool settingsSaveNow();
bool settingsDirty();
void settingFormat(int id, char* buf, size_t n);   // value as text

// Implemented in leo_control.ino: lets modules react to a changed setting.
void settingChanged(int id);
