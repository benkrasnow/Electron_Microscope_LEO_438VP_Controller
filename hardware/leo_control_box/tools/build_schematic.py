"""Generate leo_control_box.kicad_sch from a netlist description.

Every pin connection is made with a net label or a power symbol placed exactly on the pin end, so the
drawing is a set of tidy functional blocks rather than a wire diagram. Unused pins get no-connect flags.
Re-run after editing: python tools/build_schematic.py   (from the project folder). This OVERWRITES the
schematic, so make hand edits only once the generated version is final.
"""
import os, re, subprocess, uuid
from _pins import pins as lib_pins, K as STOCK_SYM_DIR

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = "leo_control_box"
SCH = os.path.join(HERE, PROJ + ".kicad_sch")
ROOT = "e63e39d7-6ac0-4ffd-8aa3-1841a4541b55"          # root sheet uuid from the template
POWER = {"+5V", "+3V3", "GND"}
FP = PROJ + ":"
KICAD_CLI = "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"


def u():
    return str(uuid.uuid4())


def block(text, start):
    depth, i, s = 0, start, False
    while True:
        c = text[i]
        if s:
            if c == "\\": i += 1
            elif c == '"': s = False
        elif c == '"': s = True
        elif c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: return text[start:i + 1]
        i += 1


# ------------------------------------------------------------------ symbol definitions
_src = {}


def lib_text(lib):
    if lib not in _src:
        p = os.path.join(HERE, PROJ + ".kicad_sym") if lib == PROJ else os.path.join(STOCK_SYM_DIR, lib + ".kicad_sym")
        _src[lib] = open(p, encoding="utf-8").read()
    return _src[lib]


def raw_def(lib, name):
    t = lib_text(lib)
    return block(t, t.index('(symbol "%s"' % name))


def flat_def(lib, name):
    """Definition with 'extends' resolved: the parent's graphics and pins under the child's name and properties."""
    d = raw_def(lib, name)
    m = re.search(r'\(extends "([^"]+)"\)', d[:400])
    if not m:
        return d, name
    parent = m.group(1)
    pd, pname = flat_def(lib, parent)
    child_props = re.findall(r'\(property "[^"]+".*?\n\t\t\)', d, re.S)
    body = pd[pd.index("\n"):]
    body = re.sub(r'\(property "[^"]+".*?\n\t\t\)', "", body, flags=re.S)
    body = body.replace('(symbol "%s_' % pname, '(symbol "%s_' % name)
    head = pd[:pd.index("\n")].replace('"%s"' % pname, '"%s"' % name, 1)
    return head + "\n\t\t" + "\n\t\t".join(child_props) + body, parent


LIBSYMS, PINS = {}, {}


def use(lib_id):
    if lib_id in LIBSYMS:
        return
    lib, name = lib_id.split(":")
    d, pname = flat_def(lib, name)
    LIBSYMS[lib_id] = d.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)
    PINS[lib_id] = lib_pins(LIBSYMS[lib_id], name)
    props = {}
    for m in re.finditer(r'\(property "(Reference|Value)" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', d):
        props[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    PINS[lib_id + "#props"] = props


# ------------------------------------------------------------------ drawing primitives
ITEMS = []
PWR_N = [0]


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def label(net, x, y, pin_angle):
    ang = (pin_angle + 180) % 360
    just = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
    ITEMS.append('\t(label "%s" (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid "%s"))\n'
                 % (net, fmt(x), fmt(y), ang, just, u()))


def noconn(x, y):
    ITEMS.append('\t(no_connect (at %s %s) (uuid "%s"))\n' % (fmt(x), fmt(y), u()))


def text(s, x, y, size=2.54):
    ITEMS.append('\t(text "%s" (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s) (thickness 0.4) bold) (justify left bottom)) (uuid "%s"))\n'
                 % (s, fmt(x), fmt(y), size, size, u()))


def snap(v):
    return round(v / 2.54) * 2.54


# ------------------------------------------------------------------ purchasing (Digi-Key, checked 2026-11-13)
# (Manufacturer, MPN, Digi-Key PN, unit price at qty 1 in USD, note)
PARTS = {
    "R10k":   ("Yageo", "RC0805FR-0710KL", "311-10.0KCRCT-ND", 0.10, ""),
    "R1k":    ("Yageo", "RC0805FR-071KL", "311-1.00KCRCT-ND", 0.10, ""),
    "R2k2":   ("Yageo", "RC0805FR-072K2L", "311-2.20KCRCT-ND", 0.10, ""),
    "R56":    ("Yageo", "RC0805FR-0756RL", "311-56.0CRCT-ND", 0.10, ""),
    "C100n":  ("Samsung Electro-Mechanics", "CL21B104KBCNNNC", "1276-1003-1-ND", 0.10, "50 V X7R; used everywhere a 100 nF is needed"),
    "C47u":   ("Samsung Electro-Mechanics", "CL31A476MPHNNNE", "1276-3063-1-ND", 0.59, "10 V X5R 1206; low Digi-Key stock (123)"),
    "LED":    ("Lite-On", "LTST-C171GKT", "160-1423-1-ND", 0.15, "green, used for both indicators"),
    "FUSE":   ("Littelfuse", "1812L110/16DR", "F3485CT-ND", 0.74, "replaces obsolete Bourns MF-MSMF110-2"),
    "TB2":    ("Phoenix Contact", "1729128", "277-1247-ND", 0.95, "MKDS 1,5/2-5,08; replaces out-of-stock 1715721"),
    "DE9M":   ("NorComp", "182-009-113R531", "182-09ME-ND", 2.41, "0.318 in backset, board locks; VERIFY footprint against the NorComp drawing"),
    "HDR":    ("Sullins", "PRPC040SAAN-RC", "S1011EC-40-ND", 1.23, "1x40 breakaway strip, cut for J6"),
    "QWIIC":  ("JST", "SM04B-SRSS-TB(LF)(SN)", "455-SM04B-SRSS-TBCT-ND", 0.51, ""),
    "AHCT125": ("Texas Instruments", "SN74AHCT125DR", "296-4652-1-ND", 0.52, ""),
    "2N7002": ("onsemi", "2N7002LT1G", "2N7002LT1GOSCT-ND", 0.26, ""),
    "MAX3232": ("Texas Instruments", "MAX3232ECDR", "296-19851-1-ND", 1.24, ""),
    "TEENSY":  ("PJRC / SparkFun", "15583 (Teensy 4.0)", "1568-15583-ND", 25.66, "owner has stock; Digi-Key stock 0 on 2026-11-13"),
    "HFBR_TX": ("Broadcom", "HFBR-1521Z", "516-2043-ND", 19.14, "owner has stock; Digi-Key backordered (alt AFBR-1521CZ 516-3584-ND)"),
    "HFBR_RX": ("Broadcom", "HFBR-2521Z", "516-2062-ND", 20.46, "owner has stock"),
    "IDC20":   ("Sullins", "SBH11-PBPC-D10-ST-BK", "S9172-ND", 0.46, "2x10 shrouded box header for the display cable"),
    "LCD":     ("Newhaven Display", "NHD-4.3-800480FT-CSXP-CTP", "757-NHD-4.3-800480FT-CSXP-CTP-ND", 75.14,
                "OFF-BOARD: 4.3 in 800x480 IPS EVE (FT813) display, capacitive touch"),
    "CABLE20": ("Adafruit", "5294", "1528-5294-ND", 1.95, "OFF-BOARD: 2x10 IDC socket-to-socket ribbon cable, 1 ft"),
}


def part_key(lib_id, value, dnp):
    if dnp:
        return None
    name = lib_id.split(":")[1]
    by_name = {"74AHCT125": "AHCT125", "2N7002": "2N7002", "MAX3232": "MAX3232",
               "Teensy_4.0": "TEENSY", "HFBR-1521Z": "HFBR_TX", "HFBR-2521Z": "HFBR_RX",
               "LED": "LED", "Polyfuse": "FUSE", "Conn_01x02": "TB2", "DE9_Pins_MountingHoles": "DE9M",
               "Conn_01x03": "HDR", "Conn_01x04_MountingPin": "QWIIC", "Conn_02x10_Odd_Even": "IDC20"}
    if name in by_name:
        return by_name[name]
    if name == "MountingHole":                         # placeholder symbols for off-board items
        return {"Display NHD-4.3": "LCD", "Display cable": "CABLE20"}[value]
    if name == "R":
        return {"10k": "R10k", "1k": "R1k", "2.2k": "R2k2", "56": "R56"}[value]
    if name == "C":
        return {"100n": "C100n", "47u 10V": "C47u"}[value]
    return None


def instance(lib_id, ref, value, fp, x, y, unit=1, dnp=False, hide_ref=False, on_board=True):
    use(lib_id)
    props = PINS[lib_id + "#props"]
    rx, ry = props.get("Reference", (0, 5))
    vx, vy = props.get("Value", (0, -5))
    pins = [p for p in PINS[lib_id] if p[0] in (str(unit), "0")]
    s = ('\t(symbol (lib_id "%s") (at %s %s 0) (unit %d) (exclude_from_sim no) (in_bom %s) (on_board %s) (dnp %s) (uuid "%s")\n'
         % (lib_id, fmt(x), fmt(y), unit, "no" if ref.startswith("#") else "yes", "yes" if on_board else "no",
            "yes" if dnp else "no", u()))
    s += '\t\t(property "Reference" "%s" (at %s %s 0) (effects (font (size 1.27 1.27))%s))\n' % (ref, fmt(x + rx), fmt(y - ry), " (hide yes)" if hide_ref else "")
    s += '\t\t(property "Value" "%s" (at %s %s 0) (effects (font (size 1.27 1.27))))\n' % (value, fmt(x + vx), fmt(y - vy))
    s += '\t\t(property "Footprint" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n' % (fp, fmt(x), fmt(y))
    s += '\t\t(property "Datasheet" "" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n' % (fmt(x), fmt(y))
    if not ref.startswith("#"):
        key = part_key(lib_id, value, dnp)
        mfr, mpn, dkpn, price, note = PARTS[key] if key else ("", "", "", "", "DNP" if dnp else "")
        for k, v in (("Manufacturer", mfr), ("MPN", mpn), ("DigiKey_PN", dkpn),
                     ("Unit_Price_USD", ("%.2f" % price) if price != "" else ""), ("BOM_Note", note)):
            s += '\t\t(property "%s" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n' % (k, v, fmt(x), fmt(y))
    for p in pins:
        s += '\t\t(pin "%s" (uuid "%s"))\n' % (p[1], u())
    s += '\t\t(instances (project "%s" (path "/%s" (reference "%s") (unit %d))))\n\t)\n' % (PROJ, ROOT, ref, unit)
    ITEMS.append(s)
    return pins


def power(net, x, y):
    PWR_N[0] += 1
    x, y = round(x / 1.27) * 1.27, round(y / 1.27) * 1.27
    instance("power:" + net, "#PWR%03d" % PWR_N[0], net, "", x, y, hide_ref=True)


def place(lib_id, ref, value, fp, x, y, conns, unit=1, dnp=False):
    """Place a symbol and connect its pins: conns maps pin number -> net (None = leave open, flagged)."""
    x, y = snap(x), snap(y)
    pins = instance(lib_id, ref, value, fp, x, y, unit, dnp)
    for (_, num, name, etype, px, py, ang, hidden) in pins:
        ex, ey = x + px, y - py
        net = conns.get(num, "__NC__")
        if net == "":
            continue                      # joined pin-to-pin with a neighbouring symbol
        if net == "__NC__" or net is None:
            if not hidden and etype != "no_connect":
                noconn(ex, ey)
        elif net in POWER:
            power(net, ex, ey)
        else:
            label(net, ex, ey, ang)
    unknown = set(conns) - {p[1] for p in pins}
    if unknown:
        raise ValueError("%s unit %d: no pins %s" % (ref, unit, unknown))


# shorthand for passives
R_ = ("Device:R", FP + "R_0805_2012Metric")
C_ = ("Device:C", FP + "C_0805_2012Metric")
CB = ("Device:C", FP + "C_1206_3216Metric")
LED = ("Device:LED", FP + "LED_0805_2012Metric")


def two(kind, ref, value, x, y, top, bottom, dnp=False):
    place(kind[0], ref, value, kind[1], x, y, {"1": top, "2": bottom}, dnp=dnp)


# ------------------------------------------------------------------ the circuit
def build():
    T = PROJ + ":"
    text("LEO 438VP control box: Teensy 4.0 machine-state / safety controller", 20, 18, 3.5)

    # --- power ------------------------------------------------------------------------------------
    text("5 V input (from the SEM side; Teensy VUSB-VIN link cut)", 20, 32)
    place("Connector_Generic:Conn_01x02", "J1", "5V_IN", FP + "TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
          30, 45, {"1": "+5V_IN", "2": "GND"})
    place("Device:Polyfuse", "F1", "1.1A hold", FP + "Fuse_1812_4532Metric", 50, 45, {"1": "+5V_IN", "2": "+5V"})
    two(CB, "C1", "47u 10V", 65, 45, "+5V", "GND")
    two(C_, "C2", "100n", 75, 45, "+5V", "GND")
    for i, net in enumerate(("+5V", "GND")):                       # PWR_FLAGs for ERC
        x = snap(90 + 12 * i)
        instance("power:PWR_FLAG", "#FLG%02d" % (i + 1), "PWR_FLAG", "", x, snap(42), hide_ref=True)
        power(net, x, snap(42))
    two(R_, "R1", "1k", 115, 45, "+5V", "PWR_LED_A")
    place(LED[0], "D1", "green", LED[1], 125, 52, {"2": "PWR_LED_A", "1": "GND"})
    two(R_, "R2", "1k", 140, 45, "STATUS_LED", "STATUS_LED_A")
    place(LED[0], "D2", "status", LED[1], 150, 52, {"2": "STATUS_LED_A", "1": "GND"})

    # --- Teensy ----------------------------------------------------------------------------------
    text("Controller", 20, 75)
    tpins = {"0": "EHT_RX", "1": "EHT_TX", "2": "EO_F3", "3": "EO_F4", "4": "EO_F1", "5": "EO_F2",
             "6": "SYNC_LINE_T", "7": "STG_RX", "8": "STG_TX", "9": "SYNC_FRAME_T",
             "14": "VP_TX", "15": "VP_RX", "18": "SDA", "19": "SCL", "23": "STATUS_LED",
             "10": "LCD_CS", "11": "LCD_MOSI_T", "12": "LCD_MISO", "13": "LCD_SCK_T", "21": "LCD_PD", "22": "LCD_INT"}
    left = ["GND"] + [str(i) for i in range(13)]
    right = [str(i) for i in range(13, 24)] + ["3V3", "GND", "VIN"]
    conns = {}
    for pad, name in enumerate(left + right, start=1):
        if name == "GND": conns[str(pad)] = "GND"
        elif name == "3V3": conns[str(pad)] = "+3V3"
        elif name == "VIN": conns[str(pad)] = "+5V"
        else: conns[str(pad)] = tpins.get(name)
    place(T + "Teensy_4.0", "U1", "Teensy 4.0", FP + "Teensy_4.0", 60, 110, conns)
    text("Spare: 16/17 (UART4/I2C1), 20", 20, 140, 1.8)

    # --- fiber transmitters ----------------------------------------------------------------------
    text("Fiber transmitters (HFBR-1521Z)", 170, 32)
    text("Idle = high = LED on. 10k pull-ups hold the lines idle while the Teensy is in reset. Peaking caps DNP.", 170, 37, 1.8)
    tx = [("EHT_TX", "EHT"), ("STG_TX", "STG/VAC"), ("EO_F1", "EO F1 frame gate"), ("EO_F2", "EO F2 line gate"), ("EO_F3", "EO F3 registers")]
    gates = [("U2", 1), ("U2", 2), ("U2", 3), ("U2", 4), ("U3", 1)]
    gate_pins = {1: ("1", "2", "3"), 2: ("4", "5", "6"), 3: ("10", "9", "8"), 4: ("13", "12", "11")}
    for i, ((net, title), (gref, gu)) in enumerate(zip(tx, gates)):
        y = 55 + 26 * i
        text(title, 172, y - 10, 1.8)
        two(R_, "R%d" % (10 + i), "10k", 180, y, "+3V3", net)
        oe, a, yo = gate_pins[gu]
        gx = 200.66
        place(T + "74AHCT125", gref, "74AHCT125", FP + "SOIC-14_3.9x8.7mm_P1.27mm", gx, y, {oe: "GND", a: net, yo: ""}, unit=gu)
        # MOSFET gate pin sits exactly on the buffer output pin (gx + 7.62 = qx - 5.08)
        place(T + "2N7002", "Q%d" % (1 + i), "2N7002", FP + "SOT-23", gx + 12.7, y, {"1": "", "2": "GND", "3": net + "_K"})
        place(T + "HFBR-1521Z", "U%d" % (4 + i), "HFBR-1521Z", FP + "AGILENT_HFBR-152x", 255, y,
              {"1": net + "_A", "2": net + "_K", "5": "GND", "6": "GND"})
        two(R_, "R%d" % (20 + i), "56", 280, y, "+5V", net + "_A")
        two(C_, "C%d" % (20 + i), "peaking", 292, y, "+5V", net + "_A", dnp=True)
    # unused gates of U3: input low, output disabled
    for j, gu in enumerate((2, 3, 4)):
        oe, a, yo = gate_pins[gu]
        place(T + "74AHCT125", "U3", "74AHCT125", FP + "SOIC-14_3.9x8.7mm_P1.27mm", 200 + 25 * j, 190, {oe: "+5V", a: "GND", yo: None}, unit=gu)
    for k, ref in enumerate(("U2", "U3")):
        place(T + "74AHCT125", ref, "74AHCT125", FP + "SOIC-14_3.9x8.7mm_P1.27mm", 290 + 25 * k, 190, {"14": "+5V", "7": "GND"}, unit=5)
        two(C_, "C%d" % (30 + k), "100n", 300 + 25 * k, 190, "+5V", "GND")

    # --- fiber receivers -------------------------------------------------------------------------
    text("Fiber receivers (HFBR-2521Z)", 170, 215)
    text("Open-collector output pulled up to 3.3 V (Teensy is not 5 V tolerant); internal RL unused.", 170, 220, 1.8)
    rx = [("EHT_RX", "EHT"), ("STG_RX", "STG/VAC"), ("EO_F4", "EO F4 replies")]
    for i, (net, title) in enumerate(rx):
        y = 232 + 24 * i
        text(title, 172, y - 9, 1.8)
        two(C_, "C%d" % (40 + i), "100n", 205, y, "+5V", "GND")
        place(T + "HFBR-2521Z", "U%d" % (9 + i), "HFBR-2521Z", FP + "AGILENT_HFBR-252x", 230, y,
              {"3": "+5V", "2": "GND", "1": net, "4": None, "5": "GND", "6": "GND"})
        two(R_, "R%d" % (30 + i), "1k", 255, y, "+3V3", net)

    # --- VP RS-232 -------------------------------------------------------------------------------
    text("VP controller RS-232", 340, 32)
    text("DTE wiring, like the PC's COM2", 340, 37, 1.8)
    place(T + "MAX3232", "U12", "MAX3232", FP + "SOIC-16_3.9x9.9mm_P1.27mm", 370, 80,
          {"1": "VP_C1P", "3": "VP_C1N", "4": "VP_C2P", "5": "VP_C2N", "2": "VP_VSP", "6": "VP_VSN",
           "11": "VP_TX", "12": "VP_RX", "14": "VP_TXD_232", "13": "VP_RXD_232",
           "10": "GND", "9": None, "8": None, "7": None, "16": "+3V3", "15": "GND"})
    two(C_, "C50", "100n", 335, 50, "VP_C1P", "VP_C1N")
    two(C_, "C51", "100n", 345, 50, "VP_C2P", "VP_C2N")
    two(C_, "C52", "100n", 405, 55, "VP_VSP", "GND")
    two(C_, "C53", "100n", 415, 55, "GND", "VP_VSN")
    two(C_, "C54", "100n", 425, 55, "+3V3", "GND")
    place("Connector:DE9_Pins_MountingHoles", "J2", "VP DE-9 male",
          FP + "DSUB-9_Pins_Horizontal_P2.77x2.84mm_EdgePinOffset7.70mm_Housed_MountingHolesOffset9.12mm",
          440, 95, {"2": "VP_RXD_232", "3": "VP_TXD_232", "5": "GND", "SH": "GND"})

    # --- I2C -------------------------------------------------------------------------------------
    # Only a spare I2C expansion port remains (no DAC, ADC or knob on this board).
    text("I2C expansion (3.3 V, spare)", 330, 130)
    two(R_, "R40", "2.2k", 335, 145, "+3V3", "SDA")
    two(R_, "R41", "2.2k", 345, 145, "+3V3", "SCL")
    for k, ref in enumerate(("J3", "J4")):
        place("Connector_Generic_MountingPin:Conn_01x04_MountingPin", ref, "Qwiic", FP + "JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
              370 + 22 * k, 150, {"1": "GND", "2": "+3V3", "3": "SDA", "4": "SCL", "MP": "GND"})

    # --- OBI sync --------------------------------------------------------------------------------
    text("Sync to OBI (Glasgow port, 3.3 V)", 330, 300)
    two(R_, "R50", "56", 340, 315, "SYNC_LINE_T", "SYNC_LINE")
    two(R_, "R51", "56", 350, 315, "SYNC_FRAME_T", "SYNC_FRAME")
    place("Connector_Generic:Conn_01x03", "J6", "OBI sync", FP + "PinHeader_1x03_P2.54mm_Vertical", 385, 315,
          {"1": "SYNC_LINE", "2": "SYNC_FRAME", "3": "GND"})

    # --- touch display (Newhaven NHD-4.3-800480FT-CSXP-CTP, FT813 EVE) -----------------------------
    text("Touch display (NHD-4.3, FT813)", 20, 160)
    text("2x10 IDC ribbon, pin n = pin n. VDD 3.3 V 40 mA; backlight 240 mA from +5V.", 20, 165, 1.8)
    text("/PD pulled low: display stays off until firmware enables it.", 20, 169, 1.8)
    two(R_, "R60", "56", 45, 185, "LCD_SCK_T", "LCD_SCK")
    two(R_, "R61", "56", 55, 185, "LCD_MOSI_T", "LCD_MOSI")
    two(R_, "R62", "10k", 65, 185, "+3V3", "LCD_CS")
    two(R_, "R63", "10k", 75, 185, "+3V3", "LCD_INT")
    two(R_, "R64", "10k", 85, 185, "LCD_PD", "GND")
    idc = {"1": "+3V3", "2": "GND", "3": "LCD_SCK", "4": "LCD_MISO", "5": "LCD_MOSI", "6": "LCD_CS",
           "7": "LCD_INT", "8": "LCD_PD", "9": None, "10": None, "11": None, "12": None, "13": None,
           "14": None, "15": None, "16": None, "17": "+5V", "18": "+5V", "19": "GND", "20": "GND"}
    place("Connector_Generic:Conn_02x10_Odd_Even", "J9", "DISPLAY", FP + "IDC-Header_2x10_P2.54mm_Vertical", 125, 195, idc)
    two(C_, "C62", "100n", 155, 185, "+3V3", "GND")
    two(CB, "C63", "47u 10V", 165, 185, "+5V", "GND")
    instance("Mechanical:MountingHole", "X1", "Display NHD-4.3", "", 95, 215, on_board=False)
    instance("Mechanical:MountingHole", "X2", "Display cable", "", 115, 215, on_board=False)


def main():
    build()
    head = ('(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
            '\t(uuid "%s")\n\t(paper "A2")\n\t(title_block (title "LEO 438VP control box") (rev "0.1") '
            '(comment 1 "Generated by tools/build_schematic.py"))\n\t(lib_symbols\n' % ROOT)
    libs = "".join("\t\t" + d + "\n" for d in LIBSYMS.values())
    tail = '\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n'
    open(SCH, "w", encoding="utf-8").write(head + libs + "\t)\n" + "".join(ITEMS) + tail)
    print("wrote", SCH, len(ITEMS), "items")
    # let KiCad itself rewrite the file in its native format (KiCad 10)
    subprocess.run([KICAD_CLI, "sch", "upgrade", SCH], check=True, capture_output=True)


if __name__ == "__main__":
    main()
