"""Summarise a decoded burst file: line period before/after, and the distinct register writes (last value wins).

usage: python summarize_burst.py <capture_tag>    (reads ../scope_captures/<tag>.npz and <tag>_ch3.txt)
"""
import sys, re
import numpy as np

tag = sys.argv[1]
d = np.load(f'../scope_captures/{tag}.npz'); t = d['t']
r = t[np.flatnonzero(np.diff((d['ch2'] > 3).astype(np.int8)) == 1)] * 1e3
p = np.diff(r)
print(f'line period: start {np.median(p[r[:-1] < 80]):.3f} ms, end {np.median(p[r[:-1] > t[-1] * 1e3 - 80]):.3f} ms')
for ch in ('ch1', 'ch4'):
    e = np.flatnonzero(np.diff((d[ch] > 1.8).astype(np.int8)))
    if len(e): print(ch, 'edges at ms', np.round(t[e] * 1e3, 2)[:10])
seq, last, reps = [], {}, {}
for line in open(f'../scope_captures/{tag}_ch3.txt'):
    m = re.search(r'A=(\w{4}) D=(\w{4})\s+(\w+)\s+n=(\w+) (chip\d) (\S+)\s+V=\s*(\d+)', line)
    if not m or m.group(6) == 'DAC4' and m.group(5) == 'chip3': continue
    key = f'{m.group(5)} {m.group(6)}'
    reps.setdefault(key, []).append(int(m.group(7)))
    if key not in seq: seq.append(key)
for k in seq:
    v = reps[k]; u = []
    [u.append(x) for x in v if x not in u]
    print(f'  {k:28s} x{len(v):2d}  ' + ' -> '.join(f'{x}' + (f' ({x - 32768:+d})' if 'DAC' in k else '') for x in u))
