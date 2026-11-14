import re, os
K = os.path.join("C:/", "Program Files", "KiCad", "10.0", "share", "kicad", "symbols")
PIN = re.compile(r'\(pin (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [\d.]+\)(\s*\(hide yes\)|\s*hide)?\s*\(name "([^"]*)".*?\(number "([^"]*)"', re.S)
def pins(text, name):
    out = []
    for sub in re.finditer(r'\(symbol "(%s_\d+_\d+)"' % re.escape(name), text):
        seg = text[sub.start():sub.start() + 30000]
        nxt = seg.find('(symbol "', 10)
        seg = seg[:nxt if nxt > 0 else None]
        for p in PIN.finditer(seg):
            out.append((sub.group(1).rsplit('_', 2)[1], p.group(7), p.group(6), p.group(1), float(p.group(2)), float(p.group(3)), int(p.group(4)), bool(p.group(5))))
    return out
if __name__ == "__main__":
    t = open('leo_control_box.kicad_sym', encoding='utf-8').read()
    for n in ['MAX232', '74LS125', 'MCP4728', 'ADS1015IDGS', 'Q_NMOS_GSD', 'DE9_Pins_MountingHoles']:
        print('==', n)
        for r in pins(t, n): print('  ', r)
    for lib, n in [('Device', 'R'), ('Device', 'C'), ('Device', 'LED'), ('Device', 'Polyfuse'), ('Connector_Generic', 'Conn_01x03'), ('Connector_Generic_MountingPin', 'Conn_01x04_MountingPin'), ('power', '+5V'), ('power', 'GND'), ('power', 'PWR_FLAG')]:
        tx = open(os.path.join(K, lib + '.kicad_sym'), encoding='utf-8').read()
        i = tx.find('(symbol "%s"' % n)
        print('==', lib, n, 'EXTENDS' if '(extends' in tx[i:i + 300] else '', pins(tx, n)[:6])
