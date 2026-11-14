"""Summarise a scope_grab .npz: levels, edge counts, pulse widths and burst structure per channel."""
import sys
import numpy as np

d = np.load(sys.argv[1])
t = d['t']; dt = t[1] - t[0]
print('record', len(t), 'pts, dt', dt, 's, span', t[-1] - t[0], 's')
for ch in ('ch1', 'ch2', 'ch3', 'ch4'):
    if ch not in d: continue
    v = d[ch]
    lo, hi = np.percentile(v, 2), np.percentile(v, 98)
    thr = (lo + hi) / 2
    b = v > thr
    e = np.flatnonzero(np.diff(b.astype(np.int8)))
    print(f'\n{ch}: min {v.min():.2f} max {v.max():.2f} p2 {lo:.2f} p98 {hi:.2f} thr {thr:.2f}  high {b.mean()*100:.1f}%  edges {len(e)}')
    if len(e) < 2: continue
    rises = e[~b[e]]; falls = e[b[e]]
    hw = []; lw = []
    for r in rises:
        f = falls[falls > r]
        if len(f): hw.append((f[0] - r) * dt)
    for f in falls:
        r = rises[rises > f]
        if len(r): lw.append((r[0] - f) * dt)
    for name, w in (('high', hw), ('low', lw)):
        if w:
            w = np.array(w)
            u, c = np.unique(np.round(w / dt).astype(int), return_counts=True)
            top = sorted(zip(c, u), reverse=True)[:8]
            print(f'  {name} widths: min {w.min()*1e6:.1f} us med {np.median(w)*1e6:.1f} us max {w.max()*1e3:.3f} ms; common(samples:count) {[(int(x), int(n)) for n, x in top]}')
    gaps = np.diff(e) * dt
    big = np.flatnonzero(gaps > 20 * np.median(gaps))
    print(f'  first edge {t[e[0]]*1e3:.3f} ms, last {t[e[-1]]*1e3:.3f} ms; long gaps (>20x median): {len(big)}', [round(gaps[i]*1e3, 3) for i in big[:10]])
