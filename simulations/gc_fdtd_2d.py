"""
Grating coupler: 2D FDTD sweep of period and fill factor (fibre -> waveguide efficiency).

2D axes: x = propagation, y = VERTICAL, z = out of plane (TE: E along z).
Stack: Si substrate, 4.7 um BOX, 600 nm LN film (full film = input waveguide, left),
grating = 400 nm sloped teeth on the 200 nm slab, oxide cladding of thickness CLAD_UM,
then AIR on top. A Gaussian beam (fibre) is launched in air at FIBER_ANGLES_DEG, so the
oxide/air interface (partial reflection, Fabry-Perot with the grating) is included.
Efficiency is the power leaving through a monitor in the film on the left (all modes).

Limitations: a 2D model assumes a laterally infinite slab; the real device has a lateral
taper (not modelled). Use it to compare designs, then check the best one in 3D.
Angles are in AIR (negative sign = the working sign found in the first test).
UNTESTED against a live Lumerical install; lines marked CHECK may need adjusting.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

PERIODS_UM = [0.95]
FILL_FACTORS = [0.6]
FIBER_ANGLES_DEG = [-6.0, -8.0, -10.0]
CLAD_THICKNESSES_UM = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]

# PERIODS_UM = np.round(np.arange(0.90, 1.001, 0.025), 3)   # Stage 2: [best period]
# FILL_FACTORS = [0.5, 0.6, 0.7]       # tooth BASE width / period   (Stage 2: [best fill])
N_PERIODS = 20
# FIBER_ANGLES_DEG = [-8.0]            # in AIR. Stage 2: [-6.0, -8.0, -10.0]
# CLAD_THICKNESSES_UM = [1.5]          # Stage 2: 1.0 ... 1.6 in 0.1 steps (Fabry-Perot period ~0.54 um)
AIR_ABOVE_UM = 2.0
MFD_UM = 10.4
WL_START, WL_STOP, N_FREQ = 1500e-9, 1600e-9, 41
LEAD_UM = 6.0
RIGHT_UM = 4.0
SIM_TIME = 3000e-15
DX, DY = 15e-9, 10e-9
HIDE = True
OUT_DIR = os.path.abspath("gc_fdtd")   # absolute: Lumerical changes its working directory on save
C = 299792458.0


def build(fdtd, period, ff, angle, clad_um):
    um = 1e-6
    lead, right = LEAD_UM * um, RIGHT_UM * um
    clad = clad_um * um
    x_end = N_PERIODS * period + right
    off = RIDGE_H / np.tan(np.radians(ANGLE_DEG))
    base = ff * period
    if base - 2 * off < 0.05 * um:
        return None                                                   # tooth top would vanish
    fdtd.switchtolayout()
    fdtd.deleteall()
    z0 = dict(z=0, z_span=1e-6)
    fdtd.addrect(name="Si", x_min=-lead - 2 * um, x_max=x_end + 2 * um, y_min=-BOX_T - 3 * um,
                 y_max=-BOX_T, **z0)
    fdtd.set("material", "Si (Silicon) - Palik")
    fdtd.addrect(name="oxide", x_min=-lead - 2 * um, x_max=x_end + 2 * um, y_min=-BOX_T,
                 y_max=FILM_T + clad, **z0)
    fdtd.set("material", "SiO2 (Glass) - Palik")
    fdtd.addrect(name="film_in", x_min=-lead - 2 * um, x_max=0, y_min=0, y_max=FILM_T, **z0)
    fdtd.set("material", LN_NAME)
    fdtd.addrect(name="slab", x_min=0, x_max=x_end + 2 * um, y_min=0, y_max=SLAB_T, **z0)
    fdtd.set("material", LN_NAME)
    for i in range(N_PERIODS):
        xb0 = i * period + (period - base)                            # trench first, then tooth
        xb1 = xb0 + base
        V = np.array([[xb0, SLAB_T - 1e-9], [xb1, SLAB_T - 1e-9], [xb1 - off, FILM_T], [xb0 + off, FILM_T]])
        fdtd.addpoly(name=f"tooth_{i}", x=0, y=0, **z0)
        fdtd.set("vertices", V)
        fdtd.set("material", LN_NAME)
    fdtd.addfdtd(dimension="2D", x_min=-lead, x_max=x_end, y_min=-BOX_T - 0.5 * um,
                 y_max=FILM_T + clad + AIR_ABOVE_UM * um, z=0, z_span=0.1 * um)
    fdtd.set("simulation time", SIM_TIME)
    fdtd.set("mesh accuracy", 3)                                      # CHECK
    fdtd.setglobalsource("wavelength start", WL_START)
    fdtd.setglobalsource("wavelength stop", WL_STOP)
    fdtd.setglobalmonitor("frequency points", N_FREQ)
    fdtd.addmesh(name="film_mesh", x_min=-lead, x_max=x_end, y_min=-0.2 * um, y_max=FILM_T + 0.3 * um,
                 z=0, z_span=0.1 * um)
    fdtd.set("override x mesh", 1); fdtd.set("dx", DX)
    fdtd.set("override y mesh", 1); fdtd.set("dy", DY)
    w0 = MFD_UM * um / 2
    fdtd.addgaussian(name="fiber", injection_axis="y-axis", direction="Backward",
                     x=N_PERIODS * period / 2, x_span=min(3 * MFD_UM * um, x_end + lead - 0.5 * um),
                     y=FILM_T + clad + 1.0 * um, z=0, z_span=0.1 * um)   # source in AIR
    fdtd.set("waist radius w0", w0)                                   # CHECK
    fdtd.set("angle theta", angle)
    fdtd.set("polarization angle", 90)                                # CHECK: 90 = E out of plane (TE)
    fdtd.addpower(name="T_wg", monitor_type="2D X-normal", x=-lead / 2, y=FILM_T / 2,
                  y_span=1.6 * um, z=0, z_span=0.1 * um)
    return x_end


def metrics(lam, eff):
    i = int(np.argmax(eff))
    pk = eff[i]
    band = lam[eff >= pk * 10 ** (-0.1)]
    return lam[i], pk, (band.max() - band.min()) if len(band) else np.nan


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    fdtd = lumapi.FDTD(hide=HIDE)
    create_ln(fdtd)
    set_ln_index(fdtd, WAVELENGTH, "2d_xy")
    rows = []
    for clad_um in CLAD_THICKNESSES_UM:
        for angle in FIBER_ANGLES_DEG:
            for period in PERIODS_UM:
                for ff in FILL_FACTORS:
                    if build(fdtd, period * 1e-6, ff, angle, clad_um) is None:
                        print(f"period {period}, ff {ff}: tooth top too narrow, skipped")
                        continue
                    fdtd.save(os.path.join(OUT_DIR, "gc.fsp"))
                    fdtd.run()
                    eff = np.abs(np.squeeze(fdtd.transmission("T_wg")))
                    lam = C / np.squeeze(fdtd.getdata("T_wg", "f"))
                    order = np.argsort(lam)
                    lam, eff = lam[order] * 1e9, eff[order]
                    pk_lam, pk, bw1 = metrics(lam, eff)
                    rows.append(dict(clad_um=clad_um, angle_deg=angle, period_um=period, fill=ff,
                                     peak_eff=pk, peak_wl_nm=pk_lam, bw_1dB_nm=bw1,
                                     eff_1550=float(np.interp(1550, lam, eff))))
                    print(f"clad {clad_um:.2f} angle {angle:+.1f} period {period:.3f} ff {ff:.1f}: "
                          f"peak {pk:.3f} ({10 * np.log10(pk):.1f} dB) at {pk_lam:.0f} nm, "
                          f"eff@1550 {rows[-1]['eff_1550']:.3f}")
                    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "gc_sweep_air.csv"), index=False)
    df = pd.DataFrame(rows)
    for (cl, ang, ff), g in df.groupby(["clad_um", "angle_deg", "fill"]):
        plt.plot(g.period_um, g.peak_wl_nm, "o-", label=f"clad {cl}, {ang:+.1f} deg, fill {ff}")
    plt.axhline(1550, color="k", ls=":")
    plt.xlabel("Period (um)"); plt.ylabel("Peak wavelength (nm)"); plt.legend()
    plt.savefig(os.path.join(OUT_DIR, "peak_wavelength_air.png"), dpi=150)
    fdtd.close()