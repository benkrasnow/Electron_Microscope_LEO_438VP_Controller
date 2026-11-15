// Column model; see optics.h. Mirrors analysis/optics/optics_model.py function by function.
#include "optics.h"
#include <math.h>

namespace {

const double N1 = 1000, N2 = 1000, N3 = 1030;
// focal length f(k^2) = a + b / (2 c k^2) + c k^2 / 2
const double LA[3] = {0.00144945, 0.00107975, 0.00213392};
const double LB[3] = {9.19117e-6, 5.24399e-6, 1.76339e-5};
const double LC[3] = {1.02404e-5, 8.09958e-6, 1.4051e-5};
const double ZH1 = -0.365921, ZH1P = -0.367372;      // C1 principal planes
const double ZH2 = -0.206825, ZH2P = -0.207971;      // C2
const double Z_GUN = -0.534, Z_AP = -0.16;           // gun crossover, final aperture
const double F1_MIN = 0.004970677, F1_MAX = 0.0770107, F2_MIN = 0.003679638;
const double K3_MIN = 2.88378, K3_MAX = 10.6798;
const double WD_MIN = 0.001, WD_MAX = 0.12;          // internal WD (m)

// Gun table LEO-32 used on this machine (its "LaB6, standard anode" table): V, B, d0, dE
struct GunRow { double v, b, d0, de; };
const GunRow GUN[] = {
  {500, 8.19e5, 7.845e-5, 0.25}, {1000, 7.25e6, 7.488e-5, 0.42}, {1500, 2.34e7, 6.849e-5, 0.57},
  {2000, 5.11e7, 6.253e-5, 0.70}, {2500, 9.14e7, 5.735e-5, 0.82}, {3000, 1.44e8, 5.29e-5, 0.92},
  {4000, 2.88e8, 4.569e-5, 1.09}, {5000, 4.78e8, 4.014e-5, 1.23}, {7500, 1.13e9, 3.062e-5, 1.51},
  {10000, 2.0e9, 2.458e-5, 1.71}, {15000, 4.14e9, 1.734e-5, 1.98}, {20000, 6.64e9, 1.317e-5, 2.14},
  {25000, 9.32e9, 1.047e-5, 2.25}, {30000, 1.21e10, 8.6e-6, 2.32}, {40000, 1.76e10, 6.18e-6, 2.39}};
const int NGUN = sizeof GUN / sizeof GUN[0];
const double AR_KV[4] = {2, 5, 10, 20};

double sqrtVr(double kv) {
  double v = kv * 1000.0;
  if (v < 100) v = 100;                                // LEO-32 clamps to 100 V
  return sqrt(v * (1.0 + v / 1021955.1));
}

double kSqOfF(int lens, double f) {
  double a = LA[lens], b = LB[lens], c = LC[lens];
  double d = (f - a) * (f - a) - b;
  if (d < 0) d = 0;
  return ((f - a) - sqrt(d)) / c;
}

void c3Planes(double k2, double& zh, double& zhp) {
  zh = 2.12386e-5 * k2 - 0.00805914;
  zhp = -1.19731e-5 * k2 - 0.00792216;
}

// Thin lens from principal planes: image position, magnification v/u.
void image(double zh, double zhp, double f, double zobj, double& zimg, double& m) {
  double u = zh - zobj;
  double v = u * f / (u - f);
  zimg = zhp + v;
  m = v / u;
}

void gun(double kv, double& b, double& d0) {
  double v = kv * 1000.0;
  if (v <= GUN[0].v) { b = GUN[0].b; d0 = GUN[0].d0; return; }
  for (int i = 1; i < NGUN; i++)
    if (v <= GUN[i].v) {
      double t = (v - GUN[i - 1].v) / (GUN[i].v - GUN[i - 1].v);
      b = GUN[i - 1].b + t * (GUN[i].b - GUN[i - 1].b);
      d0 = GUN[i - 1].d0 + t * (GUN[i].d0 - GUN[i - 1].d0);
      return;
    }
  b = GUN[NGUN - 1].b; d0 = GUN[NGUN - 1].d0;
}

// C2 crossover and total condenser magnification for focal lengths f1, f2.
void condState(double f1, double f2, double& z2, double& m) {
  double z1, m1, m2;
  image(ZH1, ZH1P, f1, Z_GUN, z1, m1);
  image(ZH2, ZH2P, f2, z1, z2, m2);
  m = m1 * m2;
}

// sub_4afb0: f1, f2 for total magnification M with the C2 crossover at zt.
void solveCondensers(double M, double zt, double& f1, double& f2) {
  double u1 = ZH1 - Z_GUN, v2 = zt - ZH2P;
  double z1 = (M * u1 * ZH2 + ZH1P * v2) / (M * u1 + v2);
  double v1 = z1 - ZH1P, u2 = ZH2 - z1;
  f1 = u1 * v1 / (u1 + v1);
  f2 = u2 * v2 / (u2 + v2);
}

// C2 held at f2: C1 focal length giving magnification M (M rises with f1).
double f1ForM(double M, double f2) {
  double lo = F1_MIN, hi = F1_MAX, z2, m;
  for (int i = 0; i < 60; i++) {
    double mid = 0.5 * (lo + hi);
    condState(mid, f2, z2, m);
    if (m < M) lo = mid; else hi = mid;
  }
  return 0.5 * (lo + hi);
}

// _calc_excitation_for_WD: objective excitation^2 imaging zobj onto z = wd; also its magnification.
double objective(double wd, double zobj, double k2, double& m) {
  double zh, zhp;
  for (int i = 0; i < 50; i++) {
    c3Planes(k2, zh, zhp);
    double u = zh - zobj, v = wd - zhp;
    double k2n = kSqOfF(2, u * v / (u + v));
    if (k2n < K3_MIN * K3_MIN) k2n = K3_MIN * K3_MIN;
    if (k2n > K3_MAX * K3_MAX) k2n = K3_MAX * K3_MAX;
    bool done = fabs(k2n - k2) < 1e-9;
    k2 = k2n;
    if (done) break;
  }
  c3Planes(k2, zh, zhp);
  m = (wd - zhp) / (zh - zobj);
  return k2;
}

double cs(double k2, double m) {
  double p = 15.0471 / k2 + 0.00261369 + 0.000332747 * k2;
  double q = 1 + m;
  return p * p * p * q * q * q * q;
}

void currents(const OpticsParams& p, double f1, double f2, double k3sq, double srv, double& i1, double& i2, double& i3) {
  double k1 = sqrt(kSqOfF(0, f1)), k2 = sqrt(kSqOfF(1, f2));
  // k1 = N1 (I1+rem1)/(cal1 srv) + N2 xt I2/srv ;  k2 = N2 (I2+rem2)/(cal2 srv) + N1 xt I1/srv
  double a11 = N1 / (p.cal[0] * srv), a12 = N2 * p.xt / srv, b1 = k1 - N1 * p.rem[0] / (p.cal[0] * srv);
  double a21 = N1 * p.xt / srv, a22 = N2 / (p.cal[1] * srv), b2 = k2 - N2 * p.rem[1] / (p.cal[1] * srv);
  double det = a11 * a22 - a12 * a21;
  i1 = (b1 * a22 - a12 * b2) / det;
  i2 = (a11 * b2 - b1 * a21) / det;
  i3 = p.cal[2] * sqrt(k3sq) * srv / N3 - p.rem[2];
}

long codeOf(double amps) {
  if (amps < 0) amps = 0;
  if (amps > 3) amps = 3;
  return lround(amps / 3.0 * 1048575.0);
}

void dac(double amps, bool obj, uint16_t& c, uint16_t& f) {
  long code = codeOf(amps) - 2048;
  if (code < 0) code = 0;
  c = (uint16_t)(code >> 8);
  f = (uint16_t)((code & 0xFF) + (obj ? 2048 : 0));
}

}  // namespace

namespace Optics {

double autoResPa(const OpticsParams& p, double kv) {
  if (kv <= AR_KV[0]) return p.arPa[0];
  int i = 1;
  while (i < 3 && kv > AR_KV[i]) i++;
  double t = log(kv / AR_KV[i - 1]) / log(AR_KV[i] / AR_KV[i - 1]);   // beyond 20 kV: extrapolate the last segment
  return exp(log(p.arPa[i - 1]) + t * log(p.arPa[i] / p.arPa[i - 1]));
}

double objectiveCode(double amps) { return (double)codeOf(amps); }

bool compute(const OpticsParams& p, double kv, double wdMm, double probePa, int mode, double apUm, OpticsResult& r) {
  if (!(kv > 0)) return false;
  double srv = sqrtVr(kv);
  if (mode == OBEAM_AUTO) probePa = autoResPa(p, kv);
  double ip = probePa * 1e-12;
  double wd = (wdMm * 1e-3 - p.wdB) / p.wdA;
  if (wd < WD_MIN) wd = WD_MIN;
  if (wd > WD_MAX) wd = WD_MAX;
  double B, d0;
  gun(kv, B, d0);
  d0 *= p.kd0;
  double rad = apUm * 0.5e-6;
  double kl = 1.30364e-9 / srv;
  double f1 = 0.02, f2 = 0.02, k3 = 34.0, m3 = 0.1, z2, M;
  for (int pass = 0; pass < 3; pass++) {           // condensers <-> objective (object = C2 crossover)
    condState(f1, f2, z2, M);
    k3 = objective(wd, z2, k3, m3);
    double zh3, zh3p;
    c3Planes(k3, zh3, zh3p);
    double v3 = wd - zh3p;
    if (mode == OBEAM_DEPTH) {
      double ki = p.kD * 0.53 * sqrt(ip / B);
      f2 = F2_MIN;
      double lo = F1_MIN, hi = F1_MAX;                // C1 so that d0 * M * alpha = K (LEO-32's Depth law, fit)
      for (int i = 0; i < 60; i++) {
        f1 = 0.5 * (lo + hi);
        condState(f1, f2, z2, M);
        double alpha = rad / (Z_AP - z2) * (zh3 - z2) / v3;
        if (d0 * M * alpha < ki) lo = f1; else hi = f1;
      }
      continue;
    }
    double ki = p.kN * 0.53 * sqrt(ip / B);
    double c = 0.278 * cs(k3, m3);
    double alpha = p.aN * pow((ki * ki + kl * kl) / (3 * c * c), 0.125);
    double d = ki / alpha;
    double Mreq = d / (d0 * m3);                    // condenser demagnification (the objective adds m3)
    double den = alpha * v3 - rad;
    if (den > (1 - p.thr) * alpha * v3) {           // C2 crossover where the aperture defines alpha
      double s = rad * (zh3 - Z_AP) / den;
      solveCondensers(Mreq, Z_AP - s, f1, f2);
    } else f2 = 0;
    if (!(f2 >= F2_MIN)) { f2 = F2_MIN; f1 = f1ForM(Mreq, f2); }
    if (f1 < F1_MIN) f1 = F1_MIN;
    if (f1 > F1_MAX) f1 = F1_MAX;
  }
  condState(f1, f2, z2, M);
  k3 = objective(wd, z2, k3, m3);
  currents(p, f1, f2, k3, srv, r.i1, r.i2, r.i3);
  dac(r.i1, false, r.c1c, r.c1f);
  dac(r.i2, false, r.c2c, r.c2f);
  dac(r.i3, true, r.objc, r.objf);
  r.probePa = probePa; r.f1 = f1; r.f2 = f2; r.k3 = sqrt(k3); r.m3 = m3; r.z2 = z2; r.wdInt = wd;
  return true;
}

double wdForObjective(const OpticsParams& p, double kv, const OpticsResult& r, double code) {
  // Objective current rises monotonically as the WD shrinks: bisection on the internal WD.
  double srv = sqrtVr(kv), lo = WD_MIN, hi = WD_MAX, k3 = r.k3 * r.k3, m;
  for (int i = 0; i < 50; i++) {
    double mid = 0.5 * (lo + hi);
    k3 = objective(mid, r.z2, k3, m);
    double amps = p.cal[2] * sqrt(k3) * srv / N3 - p.rem[2];
    if (codeOf(amps) > code) lo = mid; else hi = mid;
  }
  return (0.5 * (lo + hi) * p.wdA + p.wdB) * 1e3;
}

}  // namespace Optics
