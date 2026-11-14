"""Annotated timing diagram showing how the CH3 scan-fiber frame format was worked out from the scope captures.

usage: python plot_scan_timing.py  (reads ../scope_captures/*.npz, writes ../scope_captures/scan_fiber_timing.png)
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CAP = '../scope_captures/'
T = 1 / 3.6864e6
THR = 1.8
fast = np.load(CAP + 'fast1_250M_8ms.npz')
long = np.load(CAP + 'long1_25M_400ms_trigch4.npz')

C2, C3, C4, GRID, ADDR, DATA, NOTE = '#1f8fb3', '#c0392b', '#5a9e1b', '#999999', '#e8a33d', '#6a5acd', '#333333'


def frames(t, v):
    """Frame start indices: first falling edge after >= 20 bit-times idle high."""
    b = v > THR; dt = t[1] - t[0]; idle = int(20 * T / dt)
    out = []; last = -1
    for s in np.flatnonzero(np.diff(b.astype(np.int8)) == -1) + 1:
        if s < last or (s >= idle and not b[s - idle:s].all()):
            continue
        out.append(s); last = s + int(31 * T / dt)
    return out


def bits_at(t, v, s):
    dt = t[1] - t[0]
    return ''.join('1' if v[int(s + (k + 0.5) * T / dt)] > THR else '0' for k in range(32))


fig = plt.figure(figsize=(16, 21))
gs = fig.add_gridspec(5, 1, height_ratios=[1.0, 1.5, 1.0, 1.0, 1.0], hspace=0.42, top=0.965, bottom=0.075)
fig.suptitle('LEO 438VP scan-generator fiber (CH3, IP board → EO board): how the frame format was derived',
             fontsize=16, fontweight='bold', y=0.995)

# ---- A: overview, line timing ------------------------------------------------------------
ax = fig.add_subplot(gs[0])
t = fast['t'] * 1e3
ax.plot(t, fast['ch2'] / 4 + 1.3, color=C2, lw=1)
ax.plot(t, fast['ch3'] / 4, color=C3, lw=0.8)
ax.set_yticks([0.45, 1.85]); ax.set_yticklabels(['CH3\nframes', 'CH2\nline pulse'])
ax.set_xlabel('time (ms)'); ax.set_xlim(t[0], t[-1]); ax.set_ylim(-0.3, 2.6)
ax.set_title('A.  Overview (250 MS/s, 8 ms): one CH3 frame per CH2 line pulse', loc='left', fontweight='bold')
e2 = np.flatnonzero(np.diff((fast['ch2'] > 3).astype(np.int8)) == 1)
r = t[e2]
ax.annotate('', xy=(r[1], 2.35), xytext=(r[0], 2.35), arrowprops=dict(arrowstyle='<->', color=NOTE))
ax.text((r[0] + r[1]) / 2, 2.42, f'line period {r[1] - r[0]:.3f} ms (356 Hz)', ha='center', fontsize=10)
ax.text(r[0] + 0.05, 1.0, 'CH2 high 0.55 ms', fontsize=9, color=C2)
fs = frames(fast['t'], fast['ch3'])
for s in fs:
    ax.annotate('frame', xy=(t[s], -0.05), xytext=(t[s] + 0.15, -0.25), fontsize=9, color=C3,
                arrowprops=dict(arrowstyle='->', color=C3))
ax.text(t[-1] - 0.05, 2.42, f'CH3 burst starts {(t[fs[0]] - r[0]) * 1e3:.0f} µs after each CH2 rising edge',
        ha='right', fontsize=10, color=C3)

# ---- B: one frame, bit by bit ------------------------------------------------------------------
ax = fig.add_subplot(gs[1])
s = fs[0]; dt = fast['t'][1] - fast['t'][0]
t0 = fast['t'][s]
i0, i1 = s - int(2 * T / dt), s + int(36 * T / dt)
tu = (fast['t'][i0:i1] - t0) / T                           # time in bit periods
ax.plot(tu, fast['ch3'][i0:i1], color=C3, lw=1.6)
b = bits_at(fast['t'], fast['ch3'], s)
for k in range(33):
    ax.axvline(k, color=GRID, lw=0.6, ls=':')
for k, c in enumerate(b):
    ax.text(k + 0.5, 4.3, c, ha='center', fontsize=12, fontweight='bold', color=ADDR if k < 16 else DATA)
    ax.plot(k + 0.5, fast['ch3'][int(s + (k + 0.5) * T / dt)], 'o', ms=4, color='k')
ax.axhline(THR, color=GRID, lw=0.8); ax.text(-1.9, THR + 0.1, 'threshold 1.8 V', fontsize=8, color=GRID)
A = int(b[:16], 2); D = int(b[16:], 2)
ax.add_patch(plt.Rectangle((0, 4.75), 16, 0.45, color=ADDR, alpha=0.35))
ax.add_patch(plt.Rectangle((16, 4.75), 16, 0.45, color=DATA, alpha=0.35))
ax.text(8, 4.97, f'ADDRESS word = 0x{A:04X}', ha='center', va='center', fontsize=12, fontweight='bold')
ax.text(24, 4.97, f'DATA word = 0x{D:04X}', ha='center', va='center', fontsize=12, fontweight='bold')
n = (A & 0x3FFF) >> 2
val = int(b[14:30], 2)
fields = [(0, 1, 'b31\n= 0'), (1, 2, 'b30\nread'), (2, 9, f'chip = {n >> 5}\n(b29–b23)'),
          (9, 14, f'register = 0x{n & 31:02X}\n(b22–b18)'),
          (14, 30, f'16-bit value (b17–b2) = {val} (0x{val:04X})'), (30, 32, 'b1–0\n= 11')]
for a, z, txt in fields:
    ax.annotate('', xy=(a, -0.75), xytext=(z, -0.75), arrowprops=dict(arrowstyle='<->', color=NOTE, lw=0.8))
    ax.text((a + z) / 2, -1.45, txt, ha='center', fontsize=9)
ax.set_xlim(-2, 36); ax.set_ylim(-2.1, 5.5)
ax.set_xlabel('time in bit periods (1 bit = 0.27127 µs = 1 / 3.6864 MHz), measured from the first falling edge')
ax.set_ylabel('CH3 (V)')
ax.set_title('B.  One frame (first frame in A): sample each bit at its centre (black dots), MSB first', loc='left',
             fontweight='bold')
ax.text(33, 2.6, 'idle high\nafter 32 bits\n(no stop bit)', fontsize=9, color=NOTE)
ax.text(-1.9, 2.6, 'idle\nhigh', fontsize=9, color=NOTE)

# ---- C: bit-rate determination -----------------------------------------------------------------
ax = fig.add_subplot(gs[2])
tl = long['t']; bl = long['ch3'] > THR
e = np.flatnonzero(np.diff(bl.astype(np.int8)))
iv = np.diff(tl[e]) * 1e6
iv = iv[iv < 3.0]
ax.hist(iv, bins=np.arange(0, 3.0, 0.01), color=C3)
for k in range(1, 11):
    ax.axvline(k * T * 1e6, color=NOTE, lw=0.8, ls='--')
    ax.text(k * T * 1e6, ax.get_ylim()[1] * 0.92, f'{k}T', ha='center', fontsize=9, color=NOTE)
ax.set_xlim(0, 3.0); ax.set_yscale('log')
ax.set_xlabel('time between consecutive CH3 edges (µs), all frames in the 400 ms capture')
ax.set_ylabel('count')
ax.set_title('C.  Bit rate: every edge interval is a whole multiple of T = 0.27127 µs (best fit over all edges) '
             '→ 3.6864 Mbit/s', loc='left', fontweight='bold')
ax.text(2.95, ax.get_ylim()[1] * 0.25, 'spread around each multiple is receiver\npulse-width distortion and 40 ns sampling',
        ha='right', fontsize=9)

# ---- D: read request and CH4 reply --------------------------------------------------------------
ax = fig.add_subplot(gs[3])
w0, w1 = 0.03994, 0.04010
m = (tl >= w0) & (tl <= w1)
tm = (tl[m] - w0) * 1e6
ax.plot(tm, long['ch3'][m] / 4 + 1.3, color=C3, lw=1)
ax.plot(tm, long['ch4'][m] / 4, color=C4, lw=1.2)
ax.set_yticks([0.45, 1.75]); ax.set_yticklabels(['CH4\nEO → IP', 'CH3\nIP → EO'])
fl = frames(tl, long['ch3'])
labels = {0x412F: 'READ\n0x412F', 0x012C: 'write\n0x012C'}
for s in fl:
    if w0 <= tl[s] <= w1:
        a = int(bits_at(tl, long['ch3'], s)[:16], 2)
        x = (tl[s] - w0) * 1e6
        ax.axvline(x, color=C3, lw=0.6, ls=':')
        ax.text(x + 0.3, 2.5, labels.get(a, f'0x{a:04X}'), fontsize=9, va='top', color=C3,
                fontweight='bold' if a & 0x4000 else 'normal')
e4 = np.flatnonzero(np.diff((long['ch4'] > THR).astype(np.int8)))
x4 = (tl[e4] - w0) * 1e6
ax.annotate('', xy=(x4[0], -0.15), xytext=(x4[1], -0.15), arrowprops=dict(arrowstyle='<->', color=C4))
ax.text((x4[0] + x4[1]) / 2, -0.32, f'CH4 reply: low for {x4[1] - x4[0]:.1f} µs '
        f'(≈{(x4[1] - x4[0]) * 1e-6 / T:.0f} bits)', ha='center', fontsize=9, color=C4)
ax.set_ylim(-0.5, 2.6); ax.set_xlim(0, (w1 - w0) * 1e6)
ax.set_xlabel(f'time (µs) from {w0 * 1e3:.2f} ms in the 400 ms capture')
ax.set_title('D.  The only CH4 activity: a reply ~5 µs after the one frame with address bit 14 set '
             '→ bit 14 = read', loc='left', fontweight='bold')

# ---- E: per-line value ---------------------------------------------------------------------------
ax = fig.add_subplot(gs[4])
xs, ys, oth = [], [], []
for s in fl:
    bb = bits_at(tl, long['ch3'], s)
    a, d = int(bb[:16], 2), int(bb[16:], 2)
    if (a & 0x3FFF) >> 2 == 0x74:
        xs.append(tl[s] * 1e3); ys.append(int(bb[14:30], 2))
    else:
        oth.append(tl[s] * 1e3)
ax.plot(xs, ys, 'o-', ms=3, color=DATA, lw=0.8)
ax.plot(oth, [0] * len(oth), '|', color=ADDR, ms=14)
ax.text(oth[0] + 15, 18000, f'{len(oth)} set-up writes\n(all chips: routing, options,\ncontrol, DACs, ramp parameters)',
        fontsize=9, color='#a0661a')
ax.set_xlabel('time (ms)'); ax.set_ylabel('chip 3 reg 0x14 (16-bit value)')
ax.set_title('E.  Between set-up bursts every frame writes the same register (chip 3, reg 0x14), once per line, '
             f'+{int(np.median(np.diff(ys)))} each line → slow-scan (Y) ramp', loc='left', fontweight='bold')
ax.set_xlim(0, tl[-1] * 1e3)

prov = ('Derived from the scope alone: bit rate (C), idle-high NRZ, MSB first, 32-bit frames (B), one frame per line (A), '
        'the read/reply pairing (D),\nthe 16-bit value field (midscale parking = 32767; Y steps 84/line x 780 lines = 2.5 s frame, E). '
        'Taken from the drive-image analysis: register\nnumbering chip = n >> 5, reg = n & 31 and the names (0x0B control, '
        '0x0C routing, 0x0D options, 0x10-0x19 DACs) from the EO register map in the ADSP-21xx / GSP code.\n'
        'Confirmed by control tests: chip 2 = X (line) ramp, chip 3 = Y (frame) ramp; reg 0x14 of chip 3 = Y position.')
fig.text(0.01, 0.002, prov, fontsize=10, va='bottom', family='monospace',
         bbox=dict(boxstyle='round', facecolor='#f4f4f4', edgecolor='#bbbbbb'))
fig.savefig(CAP + 'scan_fiber_timing.png', dpi=110)
print('wrote', CAP + 'scan_fiber_timing.png')
