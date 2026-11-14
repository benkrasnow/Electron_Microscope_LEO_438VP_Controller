"""Place every footprint from the schematic netlist on leo_control_box.kicad_pcb and assign pad nets.

Run with KiCad's own Python (it has the pcbnew module), from the project folder:
    "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist --format kicadsexpr -o leo_control_box.net leo_control_box.kicad_sch
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/build_pcb.py place
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/build_pcb.py route     (Freerouting, then zone fill)
'place' removes all footprints except the locked template mounting holes, all tracks and zones, then rebuilds.
Board: 160 x 100 mm template outline, (55, 45) to (215, 145). Fiber connectors on the top edge, Teensy and
USB-C on the right edge, display / buttons / isolated OBI sync headers on the bottom edge, Qwiic on the left.
"""
import os, re, subprocess, sys
import pcbnew

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HERE, "leo_control_box.kicad_pcb")
NET = os.path.join(HERE, "leo_control_box.net")
LIB = os.path.join(HERE, "leo_control_box.pretty")
FREEROUTING = os.path.join(HERE, "tools", "freerouting", "freerouting-1.9.0.jar")
X0, Y0, X1, Y1 = 55.0, 45.0, 215.0, 145.0


def mm(v):
    return pcbnew.FromMM(v)


def tracks(board):
    try:
        return list(board.GetTracks())
    except TypeError:                                   # empty track list comes back as a bare SwigPyObject
        return []


def parse_netlist():
    t = open(NET, encoding="utf-8").read()
    comps = {}
    for blk in re.split(r"\(comp\s", t.split("(libparts")[0])[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        fp = re.search(r'\(footprint "([^"]*)"\)', blk)
        val = re.search(r'\(value "([^"]*)"\)', blk)
        stamp = re.search(r'\(tstamps\s+"([0-9a-f-]{36})"', blk)     # symbol uuid (first unit); sheetpath has "/"
        props = dict(re.findall(r'\(property\s+\(name "([^"]+)"\)\s+\(value "([^"]*)"\)', blk))
        dnp = bool(re.search(r'\(property\s+\(name "dnp"\)\s*\)', blk))
        comps[ref] = (fp.group(1) if fp else "", val.group(1) if val else "", stamp.group(1), props, dnp)
    nets = {}
    for blk in t.split("(net\n")[1:] if "(net\n" in t else re.split(r"\(net \(code", t)[1:]:
        name = re.search(r'\(name "([^"]+)"', blk).group(1)
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"', blk):
            nets[(ref, pin)] = name
    return comps, nets


# ---------------------------------------------------------------- placement: ref -> (x, y, rotation)
P = {}
# fiber connectors along the top edge (nose at the board edge), driver parts under each
FY = Y0 + 16.2
chans = [("U4", "TX", "Q1", "R10", "R20", "C20", "EHT TX"), ("U9", "RX", "C40", "R30", "EHT RX"),
         ("U5", "TX", "Q2", "R11", "R21", "C21", "STG TX"), ("U10", "RX", "C41", "R31", "STG RX"),
         ("U12", "TX", "Q6", "R15", "R25", "C25", "VP TX"), ("U14", "RX", "C43", "R33", "VP RX"),
         ("U6", "TX", "Q3", "R12", "R22", "C22", "EO F1"), ("U7", "TX", "Q4", "R13", "R23", "C23", "EO F2"),
         ("U8", "TX", "Q5", "R14", "R24", "C24", "EO F3"), ("U11", "RX", "C42", "R32", "EO F4")]
LABELS = []
for i, ch in enumerate(chans):
    x = 66 + 13.5 * i
    P[ch[0]] = (x, FY, 0)
    LABELS.append((ch[-1], x + 2.8, FY + 19.5))
    if ch[1] == "TX":
        _, _, q, rpu, rled, cpk, _ = ch
        P[rled] = (x + 1.0, FY + 6.0, 90)
        P[cpk] = (x + 4.6, FY + 6.0, 90)
        P[q] = (x + 2.6, FY + 11.0, 0)
        P[rpu] = (x + 2.6, FY + 15.5, 0)
    else:
        _, _, c, r, _ = ch
        P[c] = (x + 6.0, FY + 6.0, 90)
        P[r] = (x + 1.0, FY + 6.0, 90)
P["U2"] = (106, 91, 0); P["C30"] = (106, 98, 0)
P["U3"] = (167, 91, 0); P["C31"] = (160, 91, 90)

# Teensy: USB end on the right edge (rotation 270 puts pins 0-12 on the upper row, facing the fibers)
P["U1"] = (211.6, 97.0, 270)
P["TP1"] = (174.5, 118.0, 0)                        # wire to the Teensy's VBAT pad
P["BT1"] = (150.0, 122.0, 0)                        # CR2032, tabs at x and x + 20.5

# power: USB-C on the right edge below the Teensy
P["J10"] = (212.2, 126.0, 90)
P["R65"] = (203.0, 122.0, 90); P["R66"] = (203.0, 129.5, 90)
P["F1"] = (196.0, 134.0, 0); P["C1"] = (196.0, 138.5, 0); P["C2"] = (190.0, 138.5, 0)
P["R1"] = (183.0, 134.0, 0); P["D1"] = (183.0, 138.5, 180)
P["R2"] = (176.0, 134.0, 0); P["D2"] = (176.0, 138.5, 180)

# display header on the bottom edge, its passives above it
P["J9"] = (118.0, 140.0, 90)
for k, ref in enumerate(("R60", "R61", "R62", "R63", "R64", "C62", "C63")):
    P[ref] = (114.0 + 4.6 * k, 128.0, 90)

# pushbutton header on the bottom edge
P["J11"] = (90.0, 140.5, 90)
for k in range(3):
    P["R%d" % (70 + k)] = (84.0 + 7 * k, 124.0, 90)
    P["C%d" % (72 + k)] = (87.4 + 7 * k, 124.0, 90)
    P["R%d" % (73 + k)] = (84.0 + 7 * k, 130.0, 90)

# isolated OBI sync in the bottom-left corner (side 2 of U13 faces J6)
P["U13"] = (70.0, 125.0, 270); P["C70"] = (64.0, 120.5, 0)
P["C71"] = (64.0, 133.0, 90); P["R50"] = (69.0, 133.5, 90); P["R51"] = (73.0, 133.5, 90)
P["J6"] = (64.5, 140.5, 90)

# Qwiic sockets on the left edge, I2C pull-ups beside them
P["J3"] = (58.3, 98.0, 270); P["J4"] = (58.3, 110.0, 270)
P["R40"] = (66.0, 101.0, 90); P["R41"] = (70.0, 101.0, 90)


HOLES = [("MH1", 58.57, 50.55), ("MH2", 58.57, 139.45), ("MH3", 212.24, 50.55), ("MH4", 212.24, 139.45)]   # M2.5, template corners
STOCK_FP = "C:/Program Files/KiCad/10.0/share/kicad/footprints"


def ensure_holes(board):
    have = {fp.GetReference() for fp in board.GetFootprints()}
    for ref, x, y in HOLES:
        if ref in have:
            continue
        fp = pcbnew.FootprintLoad(STOCK_FP + "/MountingHole.pretty", "MountingHole_2.7mm_M2.5_DIN965")
        fp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.7mm_M2.5_DIN965"))
        fp.SetReference(ref)
        fp.Reference().SetVisible(False)
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.SetBoardOnly(True)
        fp.SetLocked(True)
        board.Add(fp)


def place():
    comps, nets = parse_netlist()
    board = pcbnew.LoadBoard(PCB)
    # take every list before removing anything (KiCad 10's SWIG lists break after a Remove)
    all_fps = list(board.GetFootprints())
    old_fps = [fp for fp in all_fps if not fp.IsLocked() and not fp.GetReference().startswith("MH")]
    for fp in all_fps:
        if fp.IsLocked():
            fp.SetBoardOnly(True)                       # template mounting holes: not in the schematic
    old_tracks = tracks(board)
    old_zones = list(board.Zones())
    old_text = [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS]
    for item in old_fps + old_tracks + old_zones + old_text:
        board.Remove(item)
    ensure_holes(board)
    netinfo = {}

    def net(name):
        if name not in netinfo:
            n = board.FindNet(name)
            if n is None:
                n = pcbnew.NETINFO_ITEM(board, name)
                board.Add(n)
            netinfo[name] = n
        return netinfo[name]

    missing = []
    for ref, (fpid, val, tstamp, props, dnp) in sorted(comps.items()):
        if not fpid:
            continue                                    # off-board BOM items
        if ref not in P:
            missing.append(ref)
            continue
        lib, name = fpid.split(":")
        fp = pcbnew.FootprintLoad(LIB, name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(val)
        fp.SetPath(pcbnew.KIID_PATH("/" + tstamp))
        for k in ("Manufacturer", "MPN", "DigiKey_PN", "Unit_Price_USD", "BOM_Note"):
            if k in props:
                fp.SetField(k, props[k])
                fp.GetField(k).SetVisible(False)
                fp.GetField(k).SetLayer(pcbnew.F_Fab)
        fp.SetDNP(dnp)
        if ref == "U1":
            fp.Reference().SetPosition(pcbnew.VECTOR2I(mm(x - 18), mm(y + 8.5)))   # keep it off the board edge
        x, y, rot = P[ref]
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        for pad in fp.Pads():
            n = nets.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(net(n))
    if missing:
        raise SystemExit("no placement for: " + ", ".join(missing))

    for txt, x, y in LABELS + [("OBI SYNC", 66, 136.5), ("BUTTONS", 93, 136.5), ("DISPLAY", 129, 133.5),
                               ("QWIIC", 61, 92), ("5V USB-C", 205, 117), ("CUT VUSB-VIN", 196, 92),
                               ("LEO 438VP control box rev 0.1", 105, 108)]:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        t.SetTextThickness(mm(0.15))
        board.Add(t)
    board.Save(PCB)
    print("placed", len(comps) - sum(1 for c in comps.values() if not c[0]), "footprints")


def add_zones(board):
    gnd = board.FindNet("GND")
    iso = board.FindNet("/SYNC_GND")
    # isolated corner: SYNC_GND only, board GND kept out (split runs under U13's middle)
    corner = [(X0 + 0.5, 125.0), (77.0, 125.0), (77.0, Y1 - 0.5), (X0 + 0.5, Y1 - 0.5)]
    main = [(X0 + 0.5, Y0 + 0.5), (X1 - 0.5, Y0 + 0.5), (X1 - 0.5, Y1 - 0.5), (78.0, Y1 - 0.5), (78.0, 124.0), (X0 + 0.5, 124.0)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        for pts, n in ((main, gnd), (corner, iso)):
            z = pcbnew.ZONE(board)
            z.SetLayer(layer)
            z.SetNet(n)
            z.SetLocalClearance(mm(0.3))
            z.SetMinThickness(mm(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            ol = z.Outline()
            ol.NewOutline()
            for x, y in pts:
                ol.Append(mm(x), mm(y))
            board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def route():
    board = pcbnew.LoadBoard(PCB)
    dsn = os.path.join(HERE, "leo_control_box.dsn")
    ses = os.path.join(HERE, "leo_control_box.ses")
    for item in list(board.Zones()) + tracks(board):
        board.Remove(item)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise SystemExit("DSN export failed")
    if os.path.exists(ses):
        os.remove(ses)
    subprocess.run(["java", "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "100"], check=True, timeout=1800)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("SES import failed")
    add_zones(board)
    board.Save(PCB)
    print("routed:", len(tracks(board)), "track/via items")


if __name__ == "__main__":
    {"place": place, "route": route}[sys.argv[1]]()
