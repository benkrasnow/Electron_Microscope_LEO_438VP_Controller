"""Build the per-step table of the 2026-11-15 LEO-32 optics capture session (scope_tools/EO_OPTICS_TEST_PLAN.md).

Each row is one UI change: the settings in force after it and the last value written to each lens register
in that shot (condenser chip 0 DAC0-3, objective chip 1 DAC0/1). Currents use §5.6 of the optics spec:
condensers I = ((coarse<<8) + fine + 2048) / 1048575 * 3 A, objective fine already carries the +2048.
  python eo_capture_table.py [capture_dir] > eo_capture_2026-11-15.csv
use = 1: settled state; use = 0: beam off (EHT readback 0, computed at 100 V), intermediate or discarded.
"""
import os, re, sys

CAP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../../scope_captures')

# (block, shot): (kV, WD mm, probe pA, mode, aperture um, use, note); mode N = Normal, D = Depth, R = Auto resolution
S = {}
def add(block, first, rows):
    for i, r in enumerate(rows): S[(block, first + i)] = r

# Pilot. Beam off until shot 5: LEO-32 computes from the EHT readback (clamped to 100 V).
add('opt_P', 1, [(None, None, None, 'off', 50, 0, 'mag 1000x, beam off'),
                 (0.1, 10, 200, 'N', 50, 0, 'Optibeam on, beam off'),
                 (0.1, 10, 500, 'N', 50, 0, 'beam off'),
                 (0.1, 20, 500, 'N', 50, 0, 'beam off'),
                 (20, 20, 500, 'N', 50, 1, 'beam on'),
                 (20, 20, 200, 'N', 50, 1, '')])
add('opt_A20', 1, [(20, w, 200, 'N', 50, 1, 'WD sweep') for w in (5, 8, 10, 12, 15, 20, 50, 25, 30, 40, 60, 80, 100, 20)])
add('opt_B20', 1, [(20, 20, p, 'N', 50, 1, 'probe sweep') for p in (10, 30, 100, 200, 500, 1000, 2000, 5000, 100000, 200)]
    + [(20, 20, p, 'D', 50, 1, 'Depth') for p in (200, 10, 100, 1000, 100000, 200)]
    + [(20, 20, 200, 'N', 50, 1, 'Depth off')]
    + [(20, 20, 150, 'R', 50, 1, 'Auto resolution on: UI sets 150 pA')]
    + [(20, w, 150, 'R', 50, 1, 'AR WD') for w in (10, 5, 40, 20)]
    + [(20, 20, 150, 'R', a, 1, 'AR aperture') for a in (30, 50)]
    + [(20, 20, 150, 'N', 50, 1, 'AR off, current kept')]
    + [(20, 20, 200, 'N', 50, 1, ''), (20, 20, 200, 'N', 30, 1, 'aperture'), (20, 20, 1000, 'N', 30, 1, ''),
       (20, 20, 1000, 'N', 50, 1, 'aperture'), (20, 20, 200, 'N', 50, 1, ''), (20, 20, 200, 'D', 50, 1, 'Depth on'),
       (20, 20, 200, 'D', 30, 1, 'Depth aperture'), (20, 20, 200, 'D', 50, 1, 'Depth aperture'), (20, 20, 200, 'N', 50, 1, 'Depth off')])

# kV sweep down. "first" = first lens update after the kV change; "nudge" = WD retyped once the readback was stable.
E = [(25, 20.0, 'first'), (30, 20.0, 'first'), (30, 20.1, 'nudge'), (25, 20.1, 'first'), (25, 20.0, 'nudge'),
     (20, 20.0, 'first'), (20, 20.1, 'nudge'), (15, 20.1, 'first'), (15, 20.0, 'nudge'), (10, 20.0, 'first'), (10, 20.1, 'nudge')]
add('opt_E', 1, [(k, w, 200, 'N', 50, 1, n) for k, w, n in E])
add('opt_E', 12, [(10, 20.1, 90, 'R', 50, 1, 'AR on: UI sets 90 pA'), (10, 20.1, 90, 'N', 50, 1, 'AR off'), (10, 20.1, 200, 'N', 50, 1, ''),
                  (7.5, 20.1, 200, 'N', 50, 1, 'first'), (7.5, 20.0, 200, 'N', 50, 1, 'nudge'),
                  (5, 20.0, 200, 'N', 50, 1, 'first'), (5, 20.1, 200, 'N', 50, 1, 'nudge'),
                  (5, 20.1, 70, 'R', 50, 1, 'AR on: UI sets 70 pA'), (5, 20.1, 70, 'N', 50, 1, 'AR off'), (5, 20.1, 200, 'N', 50, 1, ''),
                  (4, 20.1, 200, 'N', 50, 1, 'first'), (4, 20.0, 200, 'N', 50, 1, 'nudge'),
                  (3, 20.0, 200, 'N', 50, 1, 'first'), (3, 20.1, 200, 'N', 50, 1, 'nudge'),
                  (2, 20.1, 200, 'N', 50, 1, 'first'), (2, 20.0, 200, 'N', 50, 1, 'nudge'),
                  (2, 20.0, 50, 'R', 50, 1, 'AR on: UI sets 50 pA'), (2, 20.0, 50, 'N', 50, 1, 'AR off'), (2, 20.0, 200, 'N', 50, 1, ''),
                  (1, 20.0, 200, 'N', 50, 1, 'first'), (1, 20.1, 200, 'N', 50, 1, 'nudge')])
add('opt_E', 33, [(None, None, None, '?', 50, 0, 'discarded (operator restart)')] * 4)

# kV sweep up, magnification, 5 kV block.
up = [(1, 20.1, 'reference')]
for k, w in ((2, 20.0), (3, 20.1), (5, 20.0), (7.5, 20.1), (10, 20.0), (15, 20.1), (20, 20.0), (25, 20.1), (30, 20.0)):
    up += [(k, 20.1 if w == 20.0 else 20.0, 'first'), (k, w, 'nudge')]
add('opt_E2', 1, [(k, w, 200, 'N', 50, 1, n) for k, w, n in up])
add('opt_E2', 20, [(30, 20.0, 200, 'N', 50, 1, f'mag {m}x (no lens writes)') for m in (50, 200, 1000, 5000, 20000, 100000, 1000)])
add('opt_E2', 27, [(None, 20.0, 200, 'N', 50, 0, '30 -> 5 kV: intermediate 20 kV stage'), (5, 20.0, 200, 'N', 50, 1, 'nudge')]
    + [(5, 20.0, p, 'N', 50, 1, 'probe sweep') for p in (10, 30, 100, 200, 500, 1000, 2000, 5000, 100000, 200)]
    + [(5, w, 200, 'N', 50, 1, 'WD sweep') for w in (5, 10, 40, 80, 20)]
    + [(5, 20, p, 'D', 50, 1, 'Depth') for p in (200, 10, 1000, 200)] + [(5, 20, 200, 'N', 50, 1, 'Depth off')])
add('opt_EL', 1, [(3, 20.0, 200, 'N', 50, 1, 'first'), (3, 20.0, 200, 'N', 50, 1, 'nudge')])

REGS = {('chip0', 'DAC0'): 'c1c', ('chip0', 'DAC1'): 'c1f', ('chip0', 'DAC2'): 'c2c', ('chip0', 'DAC3'): 'c2f',
        ('chip1', 'DAC0'): 'obc', ('chip1', 'DAC1'): 'obf'}
LINE = re.compile(r'write n=\w+ (chip\d) (DAC\d)\s+V=\s*(\d+)')


def last_writes(path):
    v = {}
    for line in open(path):
        m = LINE.search(line)
        if m and (m.group(1), m.group(2)) in REGS: v[REGS[m.group(1), m.group(2)]] = int(m.group(3))
    return v


def amps(c, f, objective=False):
    if c is None or f is None: return ''
    return f'{((c << 8) + f + (0 if objective else 2048)) / 1048575 * 3:.5f}'


cols = ['block', 'shot', 'kv', 'wd_mm', 'probe_pa', 'mode', 'aperture_um', 'use', 'note',
        'c1c', 'c1f', 'c2c', 'c2f', 'obc', 'obf', 'I_c1', 'I_c2', 'I_obj']
print(','.join(cols))
for (block, shot), (kv, wd, pa, mode, ap, use, note) in sorted(S.items()):
    p = os.path.join(CAP, f'{block}_{shot:02d}_ch3.txt')
    v = last_writes(p) if os.path.exists(p) else {}
    if not os.path.exists(p): use, note = 0, (note + '; capture missing').strip('; ')
    g = v.get
    row = [block, shot, kv, wd, pa, mode, ap, use, note, g('c1c'), g('c1f'), g('c2c'), g('c2f'), g('obc'), g('obf'),
           amps(g('c1c'), g('c1f')), amps(g('c2c'), g('c2f')), amps(g('obc'), g('obf'), True)]
    print(','.join('' if x is None else str(x) for x in row))
