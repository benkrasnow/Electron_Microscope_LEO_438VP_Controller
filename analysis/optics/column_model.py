"""LEO 438VP column model as decoded from LEO-32 (g200.440), for checking against captures.
See specifications/ELECTRON_OPTICS_MODEL.md. All lengths in metres, currents in amps.
"""
import math

# Lens laws: f(k^2) = a + b/(2c k^2) + c k^2 / 2 ; k = N (I + rem) / (cal sqrt(Vr))
LENS = {
    'C1': dict(a=0.00144945, b=9.19117e-6, c=1.02404e-5, N=1000, zH=-0.36592, zH2=-0.36737, cal=1.0597, rem=0.0101),
    'C2': dict(a=0.00107975, b=5.24399e-6, c=8.09958e-6, N=1000, zH=-0.20683, zH2=-0.20797, cal=1.0597, rem=0.0101),
    'C3': dict(a=0.00213392, b=1.76339e-5, c=1.4051e-5, N=1030, cal=0.9912, rem=0.0108),
}
XTLK = 0.0422
Z_GUN = -0.534
Z_APERTURE = -0.16
GUN = {  # V: (brightness A/m2/sr, source diameter m, energy spread eV)  -- .cinit table, first rows
    500: (1.62e6, 1.298e-4, 0.38), 1000: (6.15e6, 1.356e-4, 0.53), 1500: (1.32e7, 1.297e-4, 0.64),
    2000: (2.27e7, 1.218e-4, 0.74), 2500: (3.43e7, 1.14e-4, 0.82), 3000: (4.81e7, 1.067e-4, 0.89),
    4000: (8.14e7, 9.42e-5, 1.02), 5000: (1.22e8, 8.39e-5, 1.11), 7500: (2.53e8, 6.54e-5, 1.3),
    10000: (4.22e8, 5.31e-5, 1.44)}


def root_vr(V): return math.sqrt(V * (1 + V / 1021955.1))


def focal(lens, k2):
    p = LENS[lens]; return p['a'] + p['b'] / (2 * p['c'] * k2) + p['c'] * k2 / 2


def dac_to_current(coarse, fine, objective=False):
    """20-bit code over 3 A: code = (coarse << 8) + low byte + 2048 (objective fine = 2048 + low byte)."""
    low = fine - 2048 if objective else fine
    return ((coarse << 8) + low + 2048) / 1048575.0 * 3.0


def current_to_dac(I, objective=False):
    code = round(I / 3.0 * 1048575)
    c = code - 2048
    return c >> 8, (2048 if objective else 0) + (c & 0xff)


def condenser_k(I1, I2, V):
    """Excitations with the C1<->C2 crosstalk (inverse of _calc_condenser_lens_current)."""
    r = root_vr(V); p1, p2 = LENS['C1'], LENS['C2']
    k1 = p1['N'] * (I1 + p1['rem']) / (p1['cal'] * r) + p2['N'] * XTLK * I2 / r
    k2 = p2['N'] * (I2 + p2['rem']) / (p2['cal'] * r) + p1['N'] * XTLK * I1 / r
    return k1, k2


def image(z_obj, zH, zH2, f):
    u = zH - z_obj; v = u * f / (u - f); return zH2 + v, v / u


def crossovers(I1, I2, V):
    k1, k2 = condenser_k(I1, I2, V)
    f1, f2 = focal('C1', k1 * k1), focal('C2', k2 * k2)
    z1, m1 = image(Z_GUN, LENS['C1']['zH'], LENS['C1']['zH2'], f1)
    z2, m2 = image(z1, LENS['C2']['zH'], LENS['C2']['zH2'], f2)
    return dict(k1=k1, k2=k2, f1=f1, f2=f2, z1=z1, m1=m1, z2=z2, m2=m2)


def aperture_current(cx, V, r_ap=15e-6):
    """Brightness-limited current through the final aperture: I = B (pi^2/4) (d0 M)^2 alpha^2,
    alpha = aperture radius / distance from the C2 crossover image."""
    B, d0, dE = GUN[V]
    d = d0 * abs(cx['m1'] * cx['m2'])
    alpha = r_ap / abs(Z_APERTURE - cx['z2'])
    return B * math.pi ** 2 / 4 * d * d * alpha * alpha


if __name__ == '__main__':
    # Probe current captures at 5 kV (scope_tools/SCAN_FIBER_NOTES.md): chip 0 DAC0/1 = C1, DAC2/3 = C2.
    caps = [(50, 1111, 137, 317, 33), (300, 1035, 88, 254, 204), (500, 938, 21, 252, 140), (1000, 827, 155, 250, 4)]
    print('req pA   I1 A    I2 A    f1 mm   f2 mm   z1 mm    z2 mm    M1*M2      model pA   ratio')
    base = None
    for pa, c1, f1, c2, f2 in caps:
        I1, I2 = dac_to_current(c1, f1), dac_to_current(c2, f2)
        cx = crossovers(I1, I2, 5000)
        ip = aperture_current(cx, 5000) * 1e12
        base = base or ip / pa
        print(f'{pa:6d}  {I1:.4f}  {I2:.4f}  {cx["f1"]*1e3:6.2f}  {cx["f2"]*1e3:6.2f}  {cx["z1"]*1e3:7.1f}  {cx["z2"]*1e3:7.1f}  '
              f'{cx["m1"]*cx["m2"]:9.3e}  {ip:9.1f}  {ip / pa / base:5.2f}')
    print('objective: captured coarse 382/550/790 at 5/10/20 kV ->',
          [f'{dac_to_current(c, 2200, True):.3f} A' for c in (382, 550, 790)])
