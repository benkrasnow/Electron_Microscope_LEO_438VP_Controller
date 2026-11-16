"""Run every settled step of the 2026-11-15 capture table through the firmware's column model ("optics" USB
command, nothing applied) and compare with optics_model.py and with the captured DACs.
  python check_teensy.py [COM18] [eo.gun: 0 LaB6 as LEO-32, 1 tungsten]
"""
import sys, os, json, time
import numpy as np
import serial
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fit_capture import load
import optics_model as om

MODE = {'N': 0, 'D': 1, 'R': 2}
port = sys.argv[1] if len(sys.argv) > 1 else 'COM18'
GUN = int(sys.argv[2]) if len(sys.argv) > 2 else 0          # eo.gun to test (restored to 0 afterwards)
s = serial.Serial(port, 115200, timeout=2)
s.dtr = True; time.sleep(0.5); s.reset_input_buffer()


def ask(cmd, rid):
    s.write(f'#{rid} {cmd}\n'.encode())
    t0 = time.time()
    while time.time() - t0 < 3:
        ln = s.readline().decode(errors='replace').strip()
        if ln.startswith('{') and f'"r":{rid}' in ln: return json.loads(ln)
    raise TimeoutError(cmd)


ask(f'set eo.gun {GUN}', 999)
rows = load(); m = om.Column(gun=GUN)
dt, dc = [], []
for k, r in enumerate(rows):
    mode = MODE[r['mode']]
    pa = r['pa'] if r['mode'] != 'R' else 100
    j = ask(f"optics {r['kv']} {r['wd'] * 1e3} {pa} {mode} {r['ap'] * 1e6}", 1000 + k)
    t = j['dac']
    p = m.compute(r['kv'], r['wd'], pa, r['mode'], r['ap'])
    py = [*p['c1'], *p['c2'], *p['obj']]
    dt.append([a - b for a, b in zip(t, py)])
    dc.append([t[0] - r['c1'], t[2] - r['c2'], t[4] - r['ob']])
ask('set eo.gun 0', 998)
dt, dc = np.array(dt), np.array(dc)
print(f'{len(rows)} steps')
print('firmware - python (all six DAC words): max |diff| per word', np.abs(dt).max(axis=0))
for i, n in enumerate(('C1', 'C2', 'obj')):
    print(f'firmware - capture {n}: mean {dc[:, i].mean():+.1f} rms {np.sqrt((dc[:, i] ** 2).mean()):.1f} max {np.abs(dc[:, i]).max():.0f}')
