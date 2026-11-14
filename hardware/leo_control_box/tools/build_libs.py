"""Build the project-local KiCad symbol and footprint libraries for the LEO 438VP control box.

Custom parts (written here): Teensy 4.0 symbol + footprint, HFBR-1521Z / HFBR-2521Z symbols.
Stock parts are copied from the KiCad 10 installation so the project is self-contained.
Re-run after editing: python tools/build_libs.py   (from the project folder)
"""
import os, re, shutil, subprocess, uuid

KICAD = "C:/Program Files/KiCad/10.0/share/kicad"
KICAD_CLI = "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "leo_control_box"
SYM_OUT = os.path.join(HERE, LIB + ".kicad_sym")
FP_DIR = os.path.join(HERE, LIB + ".pretty")


def u():
    return str(uuid.uuid4())


# ---------------------------------------------------------------- s-expression helpers
def extract_block(text, start):
    """Return the balanced (...) block starting at index start."""
    depth, i, instr = 0, start, False
    while i < len(text):
        c = text[i]
        if instr:
            if c == '\\':
                i += 1
            elif c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError("unbalanced")


PROP = re.compile(r'\(property "[^"]+".*?\n\t\t\)', re.S)


def flat_symbol(lib, name):
    """Symbol block with KiCad 'extends' resolved: the parent's graphics and pins under the child's
    name and properties, so the library copy matches what the schematic embeds."""
    text = open(os.path.join(KICAD, "symbols", lib + ".kicad_sym"), encoding="utf-8").read()
    blk = extract_block(text, text.index('(symbol "%s"' % name))
    m = re.search(r'\(extends "([^"]+)"\)', blk[:400])
    if not m:
        return blk
    parent = flat_symbol(lib, m.group(1))
    pname = m.group(1)
    body = PROP.sub("", parent[parent.index("\n"):]).replace('(symbol "%s_' % pname, '(symbol "%s_' % name)
    head = parent[:parent.index("\n")].replace('"%s"' % pname, '"%s"' % name, 1)
    return head + "\n\t\t" + "\n\t\t".join(PROP.findall(blk)) + body


def stock_symbol(lib, name, footprint):
    blk = flat_symbol(lib, name)
    return re.sub(r'\(property "Footprint" "[^"]*"', '(property "Footprint" "%s:%s"' % (LIB, footprint), blk, count=1)


# ---------------------------------------------------------------- custom symbols
def pin(num, name, etype, x, y, angle, length=2.54, hidden=False):
    return ('\t\t\t(pin %s line (at %.2f %.2f %d) (length %.2f)%s\n'
            '\t\t\t\t(name "%s" (effects (font (size 1.27 1.27))))\n'
            '\t\t\t\t(number "%s" (effects (font (size 1.27 1.27))))\n\t\t\t)\n'
            % (etype, x, y, angle, length, " hide" if hidden else "", name, num))


def prop(key, val, x, y, hide=False):
    return ('\t\t(property "%s" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))%s))\n'
            % (key, val, x, y, " (hide yes)" if hide else ""))


def symbol(name, ref, value, fp, ds, desc, body, pins, ref_y, val_y):
    s = '\t(symbol "%s" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n' % name
    s += prop("Reference", ref, 0, ref_y)
    s += prop("Value", value, 0, val_y)
    s += prop("Footprint", "%s:%s" % (LIB, fp), 0, val_y - 2.54, True)
    s += prop("Datasheet", ds, 0, val_y - 5.08, True)
    s += prop("Description", desc, 0, val_y - 7.62, True)
    s += '\t\t(symbol "%s_0_1"\n%s\t\t)\n' % (name, body)
    s += '\t\t(symbol "%s_1_1"\n%s\t\t)\n' % (name, "".join(pins))
    s += '\t\t(embedded_fonts no)\n\t)\n'
    return s


def rect(x1, y1, x2, y2):
    return ('\t\t\t(rectangle (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.254) (type default)) '
            '(fill (type background)))\n' % (x1, y1, x2, y2))


# Teensy 4.0: footprint pads numbered DIP-style. Pads 1-14 = left row from the USB end
# (GND, 0..12); pads 15-28 = right row from the far end (13..23, 3V3, GND, VIN).
TEENSY_LEFT = ["GND", "0/RX1", "1/TX1", "2", "3", "4", "5", "6", "7/RX2", "8/TX2", "9",
               "10/CS", "11/MOSI", "12/MISO"]
TEENSY_RIGHT = ["13/SCK/LED", "14/TX3/A0", "15/RX3/A1", "16/RX4/SCL1/A2", "17/TX4/SDA1/A3",
                "18/SDA/A4", "19/SCL/A5", "20/TX5/A6", "21/RX5/A7", "22/A8", "23/A9",
                "3V3", "GND", "VIN"]


def teensy_symbol():
    pins = []
    for i, n in enumerate(TEENSY_LEFT):           # left side of the symbol
        et = "power_in" if n == "GND" else "bidirectional"
        pins.append(pin(i + 1, n, et, -17.78, 16.51 - i * 2.54, 0, 5.08))
    for i, n in enumerate(TEENSY_RIGHT):          # right side, top = VIN
        et = {"3V3": "power_out", "GND": "power_in", "VIN": "power_in"}.get(n, "bidirectional")
        pad = 15 + i
        pins.append(pin(pad, n, et, 17.78, 16.51 - (13 - i) * 2.54, 180, 5.08))
    body = rect(-12.7, 19.05, 12.7, -19.05)
    return symbol("Teensy_4.0", "U", "Teensy_4.0", "Teensy_4.0",
                  "https://www.pjrc.com/store/teensy40.html",
                  "PJRC Teensy 4.0 (i.MX RT1062, 3.3 V I/O, NOT 5 V tolerant), edge pins only. "
                  "Cut the VUSB-VIN pad link to power from VIN.",
                  body, pins, 20.32, -20.32)


def hfbr_tx_symbol():
    pins = [pin(1, "ANODE", "passive", -7.62, 1.27, 0),
            pin(2, "CATHODE", "passive", -7.62, -1.27, 0),
            pin(3, "NC", "no_connect", 7.62, 1.27, 180, hidden=True),
            pin(4, "NC", "no_connect", 7.62, -1.27, 180, hidden=True),
            pin(5, "MNT", "passive", 7.62, -3.81, 180),
            pin(6, "MNT", "passive", 7.62, -6.35, 180)]
    body = rect(-5.08, 3.81, 5.08, -7.62)
    return symbol("HFBR-1521Z", "U", "HFBR-1521Z", "AGILENT_HFBR-152x",
                  "https://docs.broadcom.com/docs/AV02-3283EN",
                  "Versatile Link fiber transmitter, 660 nm, 5 MBd (LED; needs a current driver). "
                  "Pads 5/6 = mounting posts. VERIFY pinout against the datasheet before layout.",
                  body, pins, 6.35, -10.16)


def hfbr_rx_symbol():
    pins = [pin(3, "VCC", "power_in", -7.62, 1.27, 0),
            pin(2, "GND", "power_in", -7.62, -1.27, 0),
            pin(1, "VO", "open_collector", 7.62, 1.27, 180),
            pin(4, "RL", "passive", 7.62, -1.27, 180),
            pin(5, "MNT", "passive", 7.62, -3.81, 180),
            pin(6, "MNT", "passive", 7.62, -6.35, 180)]
    body = rect(-5.08, 3.81, 5.08, -7.62)
    return symbol("HFBR-2521Z", "U", "HFBR-2521Z", "AGILENT_HFBR-252x",
                  "https://docs.broadcom.com/docs/AV02-3283EN",
                  "Versatile Link fiber receiver, 5 MBd, 5 V supply, open-collector output with "
                  "internal load resistor on RL. Pads 5/6 = mounting posts. VERIFY pinout before layout.",
                  body, pins, 6.35, -10.16)


# ---------------------------------------------------------------- Teensy 4.0 footprint
def teensy_footprint():
    pitch, row = 2.54, 15.24
    L = []
    L.append('(footprint "Teensy_4.0"\n\t(version 20260206)\n\t(generator "build_libs.py")\n\t(layer "F.Cu")\n'
             '\t(descr "PJRC Teensy 4.0, 2x14 edge pins, 0.1 in pitch, rows 0.6 in apart; board 35.56 x 17.78 mm; '
             'USB end at the top (pad 1 = GND)")\n\t(tags "Teensy 4.0 PJRC")\n')
    L.append('\t(property "Reference" "REF**" (at 7.62 -3.5 0) (layer "F.SilkS") (uuid "%s") '
             '(effects (font (size 1 1) (thickness 0.15))))\n' % u())
    L.append('\t(property "Value" "Teensy_4.0" (at 7.62 36.5 0) (layer "F.Fab") (uuid "%s") '
             '(effects (font (size 1 1) (thickness 0.15))))\n' % u())
    L.append('\t(attr through_hole)\n')
    # board outline (fab), courtyard, silk
    x1, y1, x2, y2 = -1.27, -1.27, row + 1.27, 13 * pitch + 1.27
    for layer, w, pad in (("F.Fab", 0.1, 0), ("F.SilkS", 0.12, 0.11), ("F.CrtYd", 0.05, 0.5)):
        L.append('\t(fp_rect (start %.2f %.2f) (end %.2f %.2f) (stroke (width %.2f) (type solid)) (fill no) '
                 '(layer "%s") (uuid "%s"))\n' % (x1 - pad, y1 - pad - (1.6 if layer != "F.SilkS" else 0),
                                                   x2 + pad, y2 + pad, w, layer, u()))
    # USB connector outline (overhangs the top edge)
    L.append('\t(fp_rect (start 3.81 -2.87) (end 11.43 3.5) (stroke (width 0.1) (type dash)) (fill no) '
             '(layer "F.Fab") (uuid "%s"))\n' % u())
    L.append('\t(fp_text user "USB" (at 7.62 0.5 0) (layer "F.Fab") (uuid "%s") '
             '(effects (font (size 1 1) (thickness 0.15))))\n' % u())
    L.append('\t(fp_text user "${REFERENCE}" (at 7.62 17 0) (layer "F.Fab") (uuid "%s") '
             '(effects (font (size 1 1) (thickness 0.15))))\n' % u())
    for i in range(14):
        shape = "rect" if i == 0 else "circle"
        L.append('\t(pad "%d" thru_hole %s (at 0 %.2f) (size 1.6 1.6) (drill 1) (layers "*.Cu" "*.Mask") '
                 '(uuid "%s"))\n' % (i + 1, shape, i * pitch, u()))
    for i in range(14):
        L.append('\t(pad "%d" thru_hole circle (at %.2f %.2f) (size 1.6 1.6) (drill 1) (layers "*.Cu" "*.Mask") '
                 '(uuid "%s"))\n' % (15 + i, row, (13 - i) * pitch, u()))
    L.append('\t(embedded_fonts no)\n)\n')
    return "".join(L)


# ---------------------------------------------------------------- stock footprints to copy
DSUB = "DSUB-9_Pins_Horizontal_P2.77x2.84mm_EdgePinOffset7.70mm_Housed_MountingHolesOffset9.12mm"
STOCK_FP = {
    "OptoDevice": ["AGILENT_HFBR-152x", "AGILENT_HFBR-252x"],
    "Package_SO": ["SOIC-16_3.9x9.9mm_P1.27mm", "SOIC-14_3.9x8.7mm_P1.27mm", "SOIC-8_3.9x4.9mm_P1.27mm"],
    "Package_TO_SOT_SMD": ["SOT-23"],
    "Connector_Dsub": [DSUB],
    "Connector_JST": ["JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal"],
    "Connector_IDC": ["IDC-Header_2x10_P2.54mm_Vertical"],
    "Connector_USB": ["USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal"],
    "Connector_PinHeader_2.54mm": ["PinHeader_1x04_P2.54mm_Vertical"],
    "Battery": ["Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles"],
    "TestPoint": ["TestPoint_THTPad_D1.5mm_Drill0.7mm"],
    "Resistor_SMD": ["R_0805_2012Metric"],
    "Capacitor_SMD": ["C_0805_2012Metric", "C_1206_3216Metric"],
    "LED_SMD": ["LED_0805_2012Metric"],
    "Fuse": ["Fuse_1812_4532Metric"],
}

# stock symbols copied into the project library: (library, name, project footprint)
STOCK_SYM = [
    ("Interface_UART", "MAX3232", "SOIC-16_3.9x9.9mm_P1.27mm"),
    ("74xx", "74AHCT125", "SOIC-14_3.9x8.7mm_P1.27mm"),
    ("Transistor_FET", "2N7002", "SOT-23"),
    ("Connector", "DE9_Pins_MountingHoles", DSUB),
    ("Connector", "USB_C_Receptacle_PowerOnly_6P", "USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal"),
    ("Isolator", "ISO6720FBD", "SOIC-8_3.9x4.9mm_P1.27mm"),
]


def main():
    os.makedirs(FP_DIR, exist_ok=True)
    for lib, names in STOCK_FP.items():
        for n in names:
            shutil.copy(os.path.join(KICAD, "footprints", lib + ".pretty", n + ".kicad_mod"),
                        os.path.join(FP_DIR, n + ".kicad_mod"))
    open(os.path.join(FP_DIR, "Teensy_4.0.kicad_mod"), "w", encoding="utf-8").write(teensy_footprint())

    out = '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "build_libs.py")\n\t(generator_version "10.0")\n'
    out += teensy_symbol() + hfbr_tx_symbol() + hfbr_rx_symbol()
    for lib, name, fp in STOCK_SYM:
        out += "\t" + stock_symbol(lib, name, fp) + "\n"
    out += ")\n"
    open(SYM_OUT, "w", encoding="utf-8").write(out)
    # let KiCad itself rewrite the library in its native format (KiCad 10)
    subprocess.run([KICAD_CLI, "sym", "upgrade", SYM_OUT], check=True, capture_output=True)
    print("wrote", SYM_OUT, "and", len(os.listdir(FP_DIR)), "footprints")


if __name__ == "__main__":
    main()
