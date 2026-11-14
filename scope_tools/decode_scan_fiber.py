"""Decode the scan-generator fiber frames (IP board -> EO board, scope CH3) from a scope_grab .npz.

Working model (2026-11-12, first captures):
  - NRZ, idle high, 3.6864 Mbit/s (0.27127 us/bit), MSB first, no start/stop bits.
  - Each frame is 32 bits: b31 = 0, b30 = read request, b29-b18 = register n (12 bits),
    b17-b2 = 16-bit value, b1-b0 = 11 (trailer). Printed as A (bits 31-16) and D (bits 15-0) too.
  - n >> 5 = chip (0-4, the five ramp-controller chips), n & 31 = register within the chip.
  - A read request is answered on CH4. Bipolar DACs use offset binary (32768 = zero).
  - Frames start on the first falling edge after >= 20 bit-times of idle.
usage: python decode_scan_fiber.py capture.npz [channel] [t_min_ms] [t_max_ms]
"""
import sys
import numpy as np

T = 1 / 3.6864e6
f = np.load(sys.argv[1]); ch = sys.argv[2] if len(sys.argv) > 2 else 'ch3'
tmin = float(sys.argv[3]) / 1e3 if len(sys.argv) > 3 else -1
tmax = float(sys.argv[4]) / 1e3 if len(sys.argv) > 4 else 1e9
t = f['t']; v = f[ch]; dt = t[1] - t[0]
THRESH = 1.8   # volts at the scope (10x probes, TTL receivers)
b = v > THRESH
idle = int(20 * T / dt)
falls = np.flatnonzero(np.diff(b.astype(np.int8)) == -1) + 1
REG = {0x0B: 'control', 0x0C: 'routing', 0x0D: 'options'}
last_end = -1; prev_t = None
for s in falls:
    if s < last_end or (s >= idle and not b[s - idle:s].all()):
        continue
    idx = [int(s + (k + 0.5) * T / dt) for k in range(32)]
    if idx[-1] >= len(b):
        break
    bits = ''.join('1' if b[i] else '0' for i in idx)
    last_end = s + int(31 * T / dt)
    if not (tmin <= t[s] <= tmax):
        continue
    a = int(bits[:16], 2); d = int(bits[16:], 2)
    n = (a & 0x3FFF) >> 2; chip, reg = n >> 5, n & 31
    val = int(bits[14:30], 2); trailer = bits[30:]
    name = REG.get(reg, f'DAC{reg - 0x10}' if 0x10 <= reg <= 0x19 else f'r{reg:02X}')
    gap = '' if prev_t is None else f'+{(t[s] - prev_t) * 1e6:8.1f}us'
    prev_t = t[s]
    print(f'{t[s] * 1e3:10.4f} ms {gap:>12}  A={a:04X} D={d:04X}  {"READ " if a & 0x4000 else "write"} '
          f'n={n:02X} chip{chip} {name:8s} V={val:5d} (0x{val:04X}){"" if trailer == "11" else " trailer=" + trailer}')
