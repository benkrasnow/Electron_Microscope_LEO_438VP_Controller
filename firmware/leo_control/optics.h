// Column model (specifications/ELECTRON_OPTICS_MODEL.md §13): kV, displayed WD, probe current, Optibeam
// mode and aperture -> C1 / C2 / objective DAC words, as LEO-32 computed them. A line-by-line port of
// analysis/optics/optics_model.py; the constants marked "fit" were fitted to the 2026-11-15 captures.
// No Arduino dependencies, so it can also be built on a PC.
#pragma once
#include <stdint.h>

enum ObeamMode : uint8_t { OBEAM_NORMAL = 0, OBEAM_DEPTH = 1, OBEAM_AUTO = 2 };

struct OpticsParams {
  double cal[3], rem[3];     // lens calibration (effective values LEO-32 used) and remanence (A)
  double xt;                 // C1 <-> C2 crosstalk
  double wdA, wdB;           // internal WD = (displayed WD - wdB) / wdA   (wdB in m)
  double kN, aN;             // Normal: probe-size constant, optimum-angle scale
  double kD, kd0;            // Depth constant, source-size factor
  double thr;                // aperture-limited angle fraction
  double arPa[4];            // Auto resolution probe current at 2 / 5 / 10 / 20 kV (pA)
};

struct OpticsResult {
  uint16_t c1c, c1f, c2c, c2f, objc, objf;   // chip 0 DAC0-3, chip 1 DAC0/1
  double i1, i2, i3;                         // lens currents (A)
  double probePa;                            // probe current used (Auto resolution: chosen)
  double f1, f2, k3, m3, z2, wdInt;          // condenser focal lengths, objective excitation / magnification,
                                             // C2 crossover (m), internal WD (m)
};

namespace Optics {
// mode: ObeamMode; wdMm displayed WD; apUm aperture diameter. Returns false for kV <= 0.
bool compute(const OpticsParams& p, double kv, double wdMm, double probePa, int mode, double apUm, OpticsResult& r);
// Displayed WD (mm) at which the objective gets current code (coarse*256 + fine) with the condensers of r.
double wdForObjective(const OpticsParams& p, double kv, const OpticsResult& r, double code);
double autoResPa(const OpticsParams& p, double kv);
double objectiveCode(double amps);           // objective composite code (coarse*256 + fine) for a current
}
