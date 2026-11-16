"""LEO 438VP column model for the control box: the decoded LEO-32 / GSP equations (ELECTRON_OPTICS_MODEL.md),
re-implemented in a form that ports line by line to firmware/leo_control/optics.cpp, with constants fitted to
the 2026-11-15 captures (fit_model.py). Inputs: kV (EHT readback), displayed WD, probe current, Optibeam mode,
aperture. Outputs: C1 / C2 / objective DAC words.
"""
import math

# ---------------------------------------------------------------- constants (decoded, Â§2-Â§6)
N1, N2, N3 = 1000.0, 1000.0, 1030.0
LENS = {  # f(k^2) = a + b/(2c k^2) + c k^2 / 2
    1: (0.00144945, 9.19117e-6, 1.02404e-5),
    2: (0.00107975, 5.24399e-6, 8.09958e-6),
    3: (0.00213392, 1.76339e-5, 1.4051e-5)}
ZH1, ZH1P = -0.365921, -0.367372          # C1 principal planes (object / image side)
ZH2, ZH2P = -0.206825, -0.207971          # C2
Z_GUN = -0.534                             # gun crossover
Z_AP = -0.16                               # final aperture
F1_MIN, F1_MAX, F2_MIN = 0.004970677, 0.0770107, 0.003679638   # condenser focal-length limits (sub_4bb40)
K3_MIN, K3_MAX = 2.88378, 10.6798          # objective excitation range
WD_MIN, WD_MAX = 0.001, 0.12               # internal WD range (m)
# gun table LEO-32 used on this machine (index 1 = "LaB6, standard anode"): V, B, d0, dE
GUN = [(500, 8.19e5, 7.845e-5, 0.25), (1000, 7.25e6, 7.488e-5, 0.42), (1500, 2.34e7, 6.849e-5, 0.57),
       (2000, 5.11e7, 6.253e-5, 0.70), (2500, 9.14e7, 5.735e-5, 0.82), (3000, 1.44e8, 5.29e-5, 0.92),
       (4000, 2.88e8, 4.569e-5, 1.09), (5000, 4.78e8, 4.014e-5, 1.23), (7500, 1.13e9, 3.062e-5, 1.51),
       (10000, 2.0e9, 2.458e-5, 1.71), (15000, 4.14e9, 1.734e-5, 1.98), (20000, 6.64e9, 1.317e-5, 2.14),
       (25000, 9.32e9, 1.047e-5, 2.25), (30000, 1.21e10, 8.6e-6, 2.32), (40000, 1.76e10, 6.18e-6, 2.39)]
# tungsten / standard-anode table (this machine's real filament; eo.gun 1)
GUN_W = [(500, 1.62e6, 1.298e-4, 0.38), (1000, 6.15e6, 1.356e-4, 0.53), (1500, 1.32e7, 1.297e-4, 0.64),
         (2000, 2.27e7, 1.218e-4, 0.74), (2500, 3.43e7, 1.14e-4, 0.82), (3000, 4.81e7, 1.067e-4, 0.89),
         (4000, 8.14e7, 9.42e-5, 1.02), (5000, 1.22e8, 8.39e-5, 1.11), (7500, 2.53e8, 6.54e-5, 1.30),
         (10000, 4.22e8, 5.31e-5, 1.44), (15000, 8.59e8, 3.79e-5, 1.64), (20000, 1.42e9, 2.89e-5, 1.77),
         (25000, 2.08e9, 2.3e-5, 1.87), (30000, 2.84e9, 1.89e-5, 1.94), (40000, 4.62e9, 1.35e-5, 2.04)]
# Auto resolution: probe current LEO-32 picks (UI readings 2026-11-15), log-log interpolated
AUTORES = [(2.0, 50.0), (5.0, 70.0), (10.0, 90.0), (20.0, 150.0)]

# ---------------------------------------------------------------- fitted / per-machine parameters
P = dict(cal1=0.93565, cal2=0.9042, cal3=0.991194,     # effective calibrations LEO-32 used (fit; Data.vac: 1.0597 / 1.05973 / 0.991194)
         rem1=0.0101, rem2=0.0101094, rem3=0.0107648,      # Data.vac
         xt=0.0422491,                                     # C1 <-> C2 crosstalk (Data.vac)
         wd_a=1.21696, wd_b=0.001876,                      # internal WD = (displayed WD - wd_b) / wd_a  (PC-side)
         kN=0.95935, aN=0.91561,                           # Normal: probe-size constant, optimum-angle scale (fit)
         kD=12.78728, kd0=1.46246,                         # Depth constant, source-size factor (fit)
         thr=0.95,
         gun=0)                                            # gun table: 0 LaB6 as LEO-32 used it, 1 tungsten (eo.gun)                                         # aperture-limited angle fraction (sub_4bb40)


def sqrt_vr(kv):
    v = max(kv * 1000.0, 100.0)            # LEO-32 clamps to 100 V
    return math.sqrt(v * (1.0 + v / 1021955.1))


def f_of_k2(lens, k2):
    a, b, c = LENS[lens]
    return a + b / (2 * c * k2) + c * k2 / 2


def k2_of_f(lens, f):
    a, b, c = LENS[lens]
    d = (f - a) ** 2 - b
    if d < 0: d = 0.0
    return ((f - a) - math.sqrt(d)) / c


def c3_planes(k2):
    return 2.12386e-5 * k2 - 0.00805914, -1.19731e-5 * k2 - 0.00792216


def image(zh, zhp, f, zobj):
    """Thin lens from principal planes: returns (z_image, magnification)."""
    u = zh - zobj
    v = u * f / (u - f)
    return zhp + v, v / u


def gun(kv, table=None):
    g = table or GUN
    v = kv * 1000.0
    if v <= g[0][0]: return g[0][1:]
    for (v0, b0, d0, e0), (v1, b1, d1, e1) in zip(g, g[1:]):
        if v <= v1:
            t = (v - v0) / (v1 - v0)
            return b0 + t * (b1 - b0), d0 + t * (d1 - d0), e0 + t * (e1 - e0)
    return g[-1][1:]


def autores_pa(kv):
    if kv <= AUTORES[0][0]: return AUTORES[0][1]
    for (k0, p0), (k1, p1) in zip(AUTORES, AUTORES[1:]):
        if kv <= k1:
            t = math.log(kv / k0) / math.log(k1 / k0)
            return math.exp(math.log(p0) + t * math.log(p1 / p0))
    k0, p0 = AUTORES[-2]; k1, p1 = AUTORES[-1]
    return p1 * (kv / k1) ** (math.log(p1 / p0) / math.log(k1 / k0))


class Column:
    def __init__(self, **over):
        self.p = dict(P, **over)

    # ------------------------------------------------ condensers
    def cond_state(self, f1, f2):
        """Crossover position and total magnification for condenser focal lengths f1, f2."""
        z1, m1 = image(ZH1, ZH1P, f1, Z_GUN)
        z2, m2 = image(ZH2, ZH2P, f2, z1)
        return z2, m1 * m2

    def solve_condensers(self, M, zt):
        """sub_4afb0: f1, f2 that give total magnification M with the C2 crossover at zt."""
        u1 = ZH1 - Z_GUN
        v2 = zt - ZH2P
        z1 = (M * u1 * ZH2 + ZH1P * v2) / (M * u1 + v2)
        v1 = z1 - ZH1P
        u2 = ZH2 - z1
        return u1 * v1 / (u1 + v1), u2 * v2 / (u2 + v2)

    def f1_for_M(self, M, f2):
        """C2 held at f2: C1 focal length giving total magnification M (bisection, M rises with f1)."""
        lo, hi = F1_MIN, F1_MAX
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.cond_state(mid, f2)[1] < M: lo = mid
            else: hi = mid
        return 0.5 * (lo + hi)

    # ------------------------------------------------ objective
    def objective(self, wd, zobj, k2=34.0):
        """_calc_excitation_for_WD: excitation imaging zobj onto z = wd (internal WD)."""
        for _ in range(50):
            zh, zhp = c3_planes(k2)
            u, v = zh - zobj, wd - zhp
            f = u * v / (u + v)
            k2n = k2_of_f(3, f)
            k2n = min(max(k2n, K3_MIN ** 2), K3_MAX ** 2)
            if abs(k2n - k2) < 1e-9: break
            k2 = k2n
        zh, zhp = c3_planes(k2)
        return k2, (wd - zhp) / (zh - zobj)          # excitation^2, magnification v/u

    @staticmethod
    def cs(k2, m):
        Pk = 15.0471 / k2 + 0.00261369 + 0.000332747 * k2
        return Pk ** 3 * (1 + m) ** 4

    # ------------------------------------------------ currents / DACs
    def currents(self, f1, f2, f3k2, srv):
        p = self.p
        k1, k2 = math.sqrt(k2_of_f(1, f1)), math.sqrt(k2_of_f(2, f2))
        # k1 = N1 (I1+rem1)/(cal1 srv) + N2 xt I2/srv ; k2 = N2 (I2+rem2)/(cal2 srv) + N1 xt I1/srv
        a11, a12, b1 = N1 / (p['cal1'] * srv), N2 * p['xt'] / srv, k1 - N1 * p['rem1'] / (p['cal1'] * srv)
        a21, a22, b2 = N1 * p['xt'] / srv, N2 / (p['cal2'] * srv), k2 - N2 * p['rem2'] / (p['cal2'] * srv)
        det = a11 * a22 - a12 * a21
        i1 = (b1 * a22 - a12 * b2) / det
        i2 = (a11 * b2 - b1 * a21) / det
        i3 = p['cal3'] * math.sqrt(f3k2) * srv / N3 - p['rem3']
        return i1, i2, i3

    @staticmethod
    def dac(i, objective=False):
        code = int(round(min(max(i, 0.0), 3.0) / 3.0 * 1048575))
        c, f = (code - 2048) >> 8, (code - 2048) & 0xFF
        return max(c, 0), (2048 + f) if objective else f

    # ------------------------------------------------ the whole column
    def compute(self, kv, wd_disp, probe_pa, mode='N', aperture=50e-6):
        """mode: 'N' Normal, 'D' Depth, 'R' Auto resolution. Returns dict with DACs and state."""
        p = self.p
        srv = sqrt_vr(kv)
        if mode == 'R': probe_pa = autores_pa(kv)
        ip = probe_pa * 1e-12
        wd = min(max((wd_disp - p['wd_b']) / p['wd_a'], WD_MIN), WD_MAX)
        B, d0, dE = gun(kv, GUN_W if p['gun'] >= 0.5 else GUN)
        d0 *= p['kd0']
        r = aperture / 2
        Kl = 1.30364e-9 / srv
        f1, f2 = 0.02, 0.02
        k3 = 34.0
        for _ in range(3):                                  # condensers <-> objective (object = C2 crossover)
            z2, _m = self.cond_state(f1, f2)
            k3, m3 = self.objective(wd, z2, k3)
            zh3, zh3p = c3_planes(k3)
            v3 = wd - zh3p
            if mode == 'D':
                KI = p['kD'] * 0.53 * math.sqrt(ip / B)
                f2 = F2_MIN
                # C1 such that d * alpha = K_I with alpha set by the aperture seen from the C2 crossover
                lo, hi = F1_MIN, F1_MAX
                for _ in range(60):
                    f1 = 0.5 * (lo + hi)
                    z2, M = self.cond_state(f1, f2)
                    u3 = zh3 - z2
                    alpha = r / (Z_AP - z2) * u3 / v3
                    if d0 * M * alpha < KI: lo = f1         # LEO-32's Depth law (empirical form, see spec §6.7)
                    else: hi = f1
                continue
            KI = p['kN'] * 0.53 * math.sqrt(ip / B)
            alpha = p['aN'] * ((KI ** 2 + Kl ** 2) / (3 * (0.278 * self.cs(k3, m3)) ** 2)) ** 0.125
            d = KI / alpha
            M = d / (d0 * m3)                               # condenser demagnification (objective adds m3)
            # C2 crossover that makes the aperture define alpha: s = z_ap - z_t
            den = alpha * v3 - r
            if den > (1 - p['thr']) * alpha * v3:      # LEO-32 gives up above thr of the aperture-limited angle
                s = r * (zh3 - Z_AP) / den
                zt = Z_AP - s
                f1, f2 = self.solve_condensers(M, zt)
            else:
                f2 = 0.0
            if not (F2_MIN <= f2) :
                f2 = F2_MIN
                f1 = self.f1_for_M(M, f2)
            f1 = min(max(f1, F1_MIN), F1_MAX)
        z2, M = self.cond_state(f1, f2)
        k3, m3 = self.objective(wd, z2, k3)
        i1, i2, i3 = self.currents(f1, f2, k3, srv)
        return dict(c1=self.dac(i1), c2=self.dac(i2), obj=self.dac(i3, True), i=(i1, i2, i3),
                    f=(f1, f2), z2=z2, M=M, k3=math.sqrt(k3), m3=m3, probe_pa=probe_pa)


if __name__ == '__main__':
    c = Column()
    for kv, wd, pa, mode in ((20, 20e-3, 200, 'N'), (20, 20e-3, 200, 'D'), (5, 20e-3, 200, 'N'), (20, 5e-3, 200, 'N')):
        r = c.compute(kv, wd, pa, mode)
        print(kv, wd, pa, mode, r['c1'], r['c2'], r['obj'], ['%.4f' % x for x in r['i']], 'z2 %.4f' % r['z2'])
