"""Fit optics_model.py parameters to the 2026-11-15 capture table (Nelder-Mead on coarse-DAC residuals).
  python fit_model.py [param ...]        (default: kN aN kD kd0)
"""
import sys, math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fit_capture import load
import optics_model as om

ROWS = load()


def residuals(p, rows=ROWS):
    c = om.Column(**p); out = []
    for r in rows:
        try:
            x = c.compute(r['kv'], r['wd'], r['pa'], r['mode'], r['ap'])
            out.append((x['c1'][0] - r['c1'], x['c2'][0] - r['c2'], x['obj'][0] - r['ob']))
        except (ValueError, ZeroDivisionError, OverflowError):
            out.append((2000, 2000, 2000))
    return np.array(out, float)


def cost(p):
    d = residuals(p)
    return float(np.sqrt((d ** 2).mean()))


def nelder_mead(f, x0, step, iters=300):
    n = len(x0); pts = [np.array(x0, float)]
    for i in range(n):
        x = np.array(x0, float); x[i] *= (1 + step); pts.append(x)
    vals = [f(x) for x in pts]
    for _ in range(iters):
        o = np.argsort(vals); pts = [pts[i] for i in o]; vals = [vals[i] for i in o]
        c = np.mean(pts[:-1], axis=0)
        xr = c + (c - pts[-1]); fr = f(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1]); fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]: pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c); fc = f(xc)
            if fc < vals[-1]: pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0] + 0.5 * (x - pts[0]) for x in pts]; vals = [f(x) for x in pts]
        if max(vals) - min(vals) < 0.05: break
    return pts[0], vals[0]


if __name__ == '__main__':
    names = sys.argv[1:] or ['kN', 'aN', 'kD', 'kd0']
    x0 = [om.P[n] for n in names]
    f = lambda x: cost(dict(zip(names, np.abs(x))))
    print('start', dict(zip(names, x0)), 'cost %.1f' % f(np.array(x0)))
    x, v = nelder_mead(f, x0, 0.3)
    best = dict(zip(names, np.abs(x)))
    print('best', {k: round(float(v_), 5) for k, v_ in best.items()}, 'cost %.1f' % v)
    d = residuals(best)
    for i, n in enumerate(('C1', 'C2', 'obj')):
        print(f'{n}: mean {d[:, i].mean():+.1f} rms {np.sqrt((d[:, i] ** 2).mean()):.1f} max {np.abs(d[:, i]).max():.0f}')
    for m in 'NDR':
        idx = [k for k, r in enumerate(ROWS) if r['mode'] == m]
        print(m, len(idx), 'rms C1 %.1f C2 %.1f' % tuple(np.sqrt((d[idx, :2] ** 2).mean(axis=0))))
