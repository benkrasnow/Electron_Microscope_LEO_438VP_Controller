"""Run the GSP emulator on every settled step of the 2026-11-15 capture table and report the DAC residuals.

  python fit_capture.py [--cal C1,C2,C3] [--rem C1,C2,C3] [--wdmap a,b] [--rows filter] [-v]
--wdmap a,b : GSP WD = (displayed WD - b) / a   (default 1,0 = displayed WD used as is)
Modes: N = Normal (GSP Optibeam mode 0), D = Depth (mode 1), R = Auto resolution (mode 0 at the current the UI chose).
"""
import csv, os, sys, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emu_driver import Column, CAL, DAC, GUN_NOW
K_CS = 0xec000                               # double 0.278 (spherical term in the Normal-mode optimum angle)
FILAMENT, ANODE = 0x172b00, 0x172be0          # gun table selectors used by _update_EHT (1 = LaB6 / low-kV anode)

MODE = {'N': 0, 'D': 1, 'R': 0}


def load(path=os.path.join(HERE, 'eo_capture_2026-11-15.csv')):
    rows = []
    for r in csv.DictReader(open(path)):
        if r['use'] != '1' or not r['c1c'] or not r['obc'] or r['kv'] in ('', 'None'): continue
        rows.append(dict(r, kv=float(r['kv']), wd=float(r['wd_mm']) * 1e-3, pa=float(r['probe_pa']),
                         ap=float(r['aperture_um']) * 1e-6, c1=int(r['c1c']), c2=int(r['c2c']), ob=int(r['obc'])))
    return rows


def emulate(r, cal=None, rem=None, wdmap=(1.0, 0.0), bscale=1.0, dscale=1.0, fil=0, anode=0, csk=1.0, aps=1.0):
    c = Column(cal=cal, rem=rem)
    wd = (r['wd'] - wdmap[1]) / wdmap[0]
    if csk != 1.0: c.g.wr_double(K_CS, 0.278 * csk)
    c.g.wr(FILAMENT, 16, fil); c.g.wr(ANODE, 16, anode)
    c.set_kv(r['kv'])
    if bscale != 1.0: c.g.sf(GUN_NOW + 64, c.g.gf(GUN_NOW + 64) * bscale)
    if dscale != 1.0: c.g.sf(GUN_NOW + 32, c.g.gf(GUN_NOW + 32) * dscale)
    c.set_aperture(r['ap'] * aps); c.optibeam(MODE[r['mode']])
    c.set_wd(wd); c.set_probe(r['pa'] * 1e-12); c.set_wd(wd)
    return c.lens_dacs()


def run(rows, **kw):
    out = []
    for r in rows:
        e = emulate(r, **kw)
        out.append((r, e, (e[0] - r['c1'], e[1] - r['c2'], e[2] - r['ob'])))
    return out


def summary(res):
    import statistics as st
    s = []
    for i, n in enumerate(('C1', 'C2', 'obj')):
        d = [x[2][i] for x in res]
        s.append(f'{n}: mean {st.mean(d):+7.1f} rms {st.pstdev(d) if len(d) > 1 else 0:6.1f} max|{max(map(abs, d)):5d}|')
    return '   '.join(s)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--cal'); ap.add_argument('--rem'); ap.add_argument('--wdmap', default='1,0')
    ap.add_argument('--rows', default=''); ap.add_argument('--bscale', type=float, default=1.0); ap.add_argument('--dscale', type=float, default=1.0); ap.add_argument('--fil', type=int, default=0); ap.add_argument('--anode', type=int, default=0); ap.add_argument('--csk', type=float, default=1.0); ap.add_argument('--aps', type=float, default=1.0); ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    f = lambda s: tuple(float(x) for x in s.split(',')) if s else None
    cal, rem, wdmap = f(a.cal), f(a.rem), f(a.wdmap)
    wdmap = (wdmap[0], wdmap[1] * 1e-3)
    rows = [r for r in load() if all(eval(cond, {}, r) for cond in a.rows.split(';') if cond)]
    res = run(rows, cal=cal, rem=rem, wdmap=wdmap, bscale=a.bscale, dscale=a.dscale, fil=a.fil, anode=a.anode, csk=a.csk, aps=a.aps)
    if a.v:
        for r, e, d in res:
            print(f"{r['block']:7s}{int(r['shot']):3d} {r['kv']:4.1f}kV WD{r['wd']*1e3:5.1f} {r['pa']:6.0f}pA {r['mode']} {r['ap']*1e6:2.0f}um"
                  f"  cap {r['c1']:4d}/{r['c2']:4d}/{r['ob']:4d}  emu {e[0]:4d}/{e[1]:4d}/{e[2]:4d}  d {d[0]:+5d}/{d[1]:+5d}/{d[2]:+4d}")
    print(len(res), 'rows ', summary(res))
