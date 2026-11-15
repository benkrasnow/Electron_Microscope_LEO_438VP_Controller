"""Drive LEO-32's GSP column model in the emulator: initialise like LEO-32, apply this machine's
Data.vac calibration, then set kV / WD / probe current and read back lens currents and EO DACs."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from gspemu import GSP, u2f

G200 = r"C:/Users/Ben/Desktop/LEO 438VP - claude/TIGA/g200.440"
LENS = {'C1': 0x1723c0, 'C2': 0x1723c0 + 288, 'C3': 0x172760}   # lens records: [zH, zH', f, k, I, z_xo, M, N, -]
CAL = dict(C1=(1.0597, 0.0101), C2=(1.05973, 0.0101094), C3=(0.991194, 0.0107648))   # Data.vac
XTLK = (0.0422491, 0.0422491)
CONJUGATE = -0.164


class Column:
    def __init__(self, trace=False, cal=None, rem=None):
        self.g = GSP(G200, trace=trace)
        g = self.g
        # EO register ID tables (filled by the PC in LEO-32): 16-bit IDs, field k = register k+1,
        # ID = chip << 5 | register (the control box's numbering: DAC0 = register 16).
        for chip, base in enumerate((0xf7720, 0xf78c0, 0xf7a60, 0xf7c00, 0xf7da0)):
            for k in range(26):
                g.wr(base + 16 * k, 16, (chip << 5) | (k + 1))
        g.call('_gsp_init_EO_board', ('i', 0))
        g.call('_initialise_lens_data')
        g.call('_initialise_focus_lens_data')
        for i, (lens, (c0, r0)) in enumerate(CAL.items()):
            g.call(f'_gsp_set_{lens}_cal', ('f', cal[i] if cal else c0))
            g.call(f'_gsp_set_{lens}_rem', ('f', rem[i] if rem else r0))
        g.call('_gsp_set_lens_xtalk', ('i', 0), ('f', XTLK[0]))
        g.call('_gsp_set_lens_xtalk', ('i', 1), ('f', XTLK[1]))
        g.call('_gsp_set_conjugate_focus', ('f', CONJUGATE))

    def rec(self, lens):
        a = LENS[lens]
        w = [u2f(self.g.rd32(a + 32 * i)) for i in range(9)]
        return dict(zH=w[0], zH2=w[1], f=w[2], k=w[3], I=w[4], z_xo=w[5], M=w[6])

    def state(self):
        return {l: self.rec(l) for l in LENS}

    def eo_dacs(self):
        return dict(self.g.eo_regs)

    def lens_dacs(self):
        """(C1, C2, objective) coarse DAC codes as last written to the EO board."""
        r = self.g.eo_regs
        return r.get(DAC['C1']), r.get(DAC['C2']), r.get(DAC['C3'])

    # LEO-32's call sequence for the user controls
    def set_kv(self, kv): self.g.call('_update_EHT', ('f', kv * 1000.0))
    def set_wd(self, wd_m): self.g.call('_gsp_set_working_dist', ('f', wd_m), ('i', 0))
    def set_probe(self, amps): self.g.call('_gsp_set_probe_current', ('f', amps))
    def set_aperture(self, d_m): self.g.sf(APERTURE, d_m)          # active final-aperture diameter

    def optibeam(self, mode=0, conjugate=0):
        self.g.call('_gsp_set_conjugate_mode', ('i', conjugate))
        self.g.call('_gsp_set_optibeam_mode', ('i', mode))
        self.g.call('_gsp_turn_optibeam_on_off', ('i', 1))


DAC = {'C1': 16, 'C2': 18, 'C3': 48}     # coarse register IDs (chip << 5 | register); fine = +1
APERTURE = 0x174b00                       # float: diameter of the aperture in use (Data.vac Aperture 1 = 30 um)
GUN_NOW = 0x172b20                        # [dE, d0, B, V, sqrt(Vr), ...] at the present kV
PROBE_TABLE = 0x174fa0                    # 5 x 5 floats written by _gsp_import_probe_table (not used by mode 0)

# 5 kV probe-current captures from the EO fiber (coarse DACs C1 / C2 / objective)
CAPTURE_5KV = {50: (1111, 317, 380), 300: (1035, 254, 382), 500: (938, 252, 382), 1000: (827, 250, 383)}
CAPTURE_WD = 0.03655                      # WD that reproduces the captured objective code


def compare(mode=0, conjugate=0, aperture=None, wd=CAPTURE_WD):
    c = Column()
    c.set_kv(5)
    if aperture: c.set_aperture(aperture)
    c.optibeam(mode, conjugate)
    c.set_wd(wd)
    rows = []
    for pa, cap in CAPTURE_5KV.items():
        c.set_probe(pa * 1e-12)
        rows.append((pa, c.lens_dacs(), cap))
    return rows


if __name__ == '__main__':
    print('5 kV, WD %.2f mm: emulated vs captured coarse DACs (C1 / C2 / objective)' % (CAPTURE_WD * 1e3))
    for label, kw in [('mode 0, 30 um (Data.vac)', {}), ('mode 0, 70 um', {'aperture': 70e-6}),
                      ('conjugate, 30 um', {'conjugate': 1})]:
        print(label)
        for pa, emu, cap in compare(**kw):
            print(f'  {pa:5d} pA  emu {emu[0]:4d} / {emu[1]:4d} / {emu[2]:4d}   cap {cap[0]:4d} / {cap[1]:4d} / {cap[2]:4d}')
