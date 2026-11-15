"""Compare the GSP emulator with operating points LEO-32 saved in its conditions files (*.MLC).

Each Optibeam-on .MLC records kV, displayed WD, probe current, aperture index and the C1/C2/C3
currents LEO-32 had set (read back from the EO board DACs, so they are commanded currents).
  python mlc_compare.py <LEO-32 user dir> [--csv out.csv]
Two comparisons per point:
  at saved WD  : Optibeam at the WD LEO-32 displayed
  at C3 WD     : Optibeam at the GSP WD that reproduces the saved C3 (removes the WD-display question)
"""
import os, re, sys, csv
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emu_driver import Column

APERTURES = {0: 30e-6, 1: 50e-6, 2: 750e-6}        # Data.vac Aperture 1..3 diameters


def read_mlc(root):
    pts = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.lower().endswith('.mlc'): continue
            b = open(os.path.join(dp, f), 'rb').read(); d = {}
            for m in re.finditer(rb'([AD]P_[A-Z0-9_]+)%(-?[0-9][-+0-9.eE]*)', b):
                d.setdefault(m.group(1).decode(), []).append(float(m.group(2)))
            # Optibeam on, a probe current, real (not placeholder 0.1 A) lens currents, aperture strip in use
            if d.get('DP_OPTIBEAM', [0])[-1] != 1 or 'AP_IPROBE' not in d or d['AP_C1'][0] < 0.1: continue
            if d.get('DP_FIXED_APERTURE', [0])[0] != 0: continue
            key = (d['AP_MANUALKV'][0], d['AP_WD'][0], d['AP_IPROBE'][0], int(d['DP_APERTURE'][0]))
            pts[key] = dict(file=f, kv=key[0] / 1000, wd=key[1], ip=key[2], ap=key[3],
                            c1=d['AP_C1'][0], c2=d['AP_C2'][0], c3=d['AP_C3'][0])
    return [pts[k] for k in sorted(pts)]


def optibeam(p, wd):
    c = Column(); c.set_kv(p['kv']); c.set_aperture(APERTURES[p['ap']]); c.optibeam(0)
    c.set_wd(wd); c.set_probe(p['ip']); c.set_wd(wd)
    return c, [c.rec(l)['I'] for l in ('C1', 'C2', 'C3')]


def wd_for_c3(p):
    lo, hi = 0.002, 0.15
    for _ in range(25):
        mid = (lo + hi) / 2
        if optibeam(p, mid)[1][2] > p['c3']: lo = mid
        else: hi = mid
    return mid


if __name__ == '__main__':
    pts = read_mlc(sys.argv[1])
    out = []
    print(f'{"file":22s} {"kV":>5s} {"pA":>5s} ap {"WD":>5s} {"WDgsp":>5s} | saved C1 C2 C3     | emu@WD C1 C2 C3    | emu@WDgsp C1 C2')
    for p in pts:
        _, e = optibeam(p, p['wd'])
        w = wd_for_c3(p); _, g = optibeam(p, w)
        out.append({**p, 'wd_gsp': w, 'emu_c1': e[0], 'emu_c2': e[1], 'emu_c3': e[2], 'emu_gsp_c1': g[0], 'emu_gsp_c2': g[1]})
        print(f'{p["file"][:22]:22s} {p["kv"]:5.2f} {p["ip"]*1e12:5.0f} {p["ap"]:2d} {p["wd"]*1e3:5.1f} {w*1e3:5.1f} | '
              f'{p["c1"]:.3f} {p["c2"]:.3f} {p["c3"]:.3f} | {e[0]:.3f} {e[1]:.3f} {e[2]:.3f} | {g[0]:.3f} {g[1]:.3f}')
    if '--csv' in sys.argv:
        with open(sys.argv[sys.argv.index('--csv') + 1], 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
