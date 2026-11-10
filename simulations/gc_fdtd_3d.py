"""
Grating coupler, 3D check of the 2D-optimised design (fibre -> wide waveguide efficiency).

Axes (3D, same as the coupler scripts): x = propagation, y = lateral, z = vertical.
Geometry: Si substrate, 4.7 um BOX, 200 nm LN slab everywhere, 400 nm sloped teeth of lateral
width W_GRATING_UM (trench first, then tooth, as in gc_fdtd_2d.py), a wide input ridge of the
same width on the left, oxide cladding CLAD_UM, then air. A Gaussian beam in air (s-polarised,
E along y) is launched at FIBER_ANGLES_DEG in the x-z plane. Efficiency = power in the wide
ridge on the left (all modes). The lateral taper to the 1.0 um waveguide is NOT included:
it is a separate loss (adiabatic taper, typically < 0.2 dB if long enough).

Fibre-angle SIGN: the 2D scripts found that a negative angle works with injection along +y;
the 3D axes are rotated, so the sign may flip. Both signs are run by default; keep the better.
Not tested against a live Lumerical install; lines marked CHECK may need adjusting.
Heavy: check the printed cell estimate. Start with MESH_ACCURACY = 2.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

PERIOD_UM = 0.945
FILL = 0.6                       # tooth BASE width / period
N_PERIODS = 20
CLAD_UM = 1.6
FIBER_ANGLES_DEG = [8.0]   # in AIR
W_GRATING_UM = 12.0              # lateral width of grating and input ridge (about 1.15 x MFD)
MFD_UM = 10.4
AIR_ABOVE_UM = 2.0
WL_START, WL_STOP, N_FREQ = 1500e-9, 1600e-9, 21
LEAD_UM = 6.0
RIGHT_UM = 4.0
N_SLICES = 8                     # staircase slices of the sloped sidewalls
MESH_ACCURACY = 2
DX, DY, DZ = 30e-9, 80e-9, 20e-9
SIM_TIME = 3000e-15
Y_PAD_UM = 2.0
HIDE = False                     # False: the Lumerical GUI opens, so you can inspect the design
BUILD_ONLY = False               # True: build and save the .fsp files only, no simulation
OUT_DIR = os.path.abspath("gc_fdtd_3d")   # absolute: Lumerical changes cwd on save
C = 299792458.0


def build(fdtd, angle):
    um = 1e-6
    period, lead, right = PERIOD_UM * um, LEAD_UM * um, RIGHT_UM * um
    wg, clad = W_GRATING_UM * um, CLAD_UM * um
    base = FILL * period
    off = RIDGE_H / np.tan(np.radians(ANGLE_DEG))
    if base - 2 * off < 0.05 * um:
        raise ValueError("tooth top would vanish")
    x_end = N_PERIODS * period + right
    y_half = wg / 2 + Y_PAD_UM * um
    z_lo, z_hi = -BOX_T - 0.5 * um, FILM_T + clad + AIR_ABOVE_UM * um
    fdtd.switchtolayout()
    fdtd.deleteall()
    xs = dict(x_min=-lead - 2 * um, x_max=x_end + 2 * um, y=0, y_span=2 * y_half + 4 * um)
    fdtd.addrect(name="Si", z_min=z_lo - 1 * um, z_max=-BOX_T, **xs)
    fdtd.set("material", "Si (Silicon) - Palik")
    fdtd.addrect(name="oxide", z_min=-BOX_T, z_max=FILM_T + clad, **xs)
    fdtd.set("material", "SiO2 (Glass) - Palik")
    fdtd.addrect(name="slab", z_min=0, z_max=SLAB_T, **xs)
    fdtd.set("material", LN_NAME)
    # input ridge (left): lateral sidewalls sloped, built as slices
    for i, (z0, z1, w) in enumerate(slice_levels(N_SLICES, wg)):
        fdtd.addrect(name=f"lead_{i}", x_min=-lead - 2 * um, x_max=0, y=0, y_span=w, z_min=z0, z_max=z1)
        fdtd.set("material", LN_NAME)
    # grating teeth: each tooth is a stack of slices of decreasing x-width
    for k in range(N_PERIODS):
        xb0 = k * period + (period - base)
        for i, (z0, z1, w) in enumerate(slice_levels(N_SLICES, base)):
            xc = xb0 + base / 2
            fdtd.addrect(name=f"tooth_{k}_{i}", x=xc, x_span=w, y=0, y_span=wg - 0.0,
                         z_min=z0, z_max=z1)
            fdtd.set("material", LN_NAME)
    fdtd.addfdtd(dimension="3D", x_min=-lead, x_max=x_end, y=0, y_span=2 * y_half,
                 z_min=z_lo, z_max=z_hi)
    fdtd.set("simulation time", SIM_TIME)
    fdtd.set("mesh accuracy", MESH_ACCURACY)                            # CHECK
    fdtd.setglobalsource("wavelength start", WL_START)
    fdtd.setglobalsource("wavelength stop", WL_STOP)
    fdtd.setglobalmonitor("frequency points", N_FREQ)
    fdtd.addmesh(name="film_mesh", x_min=-lead, x_max=x_end, y=0, y_span=2 * y_half,
                 z_min=-0.2 * um, z_max=FILM_T + 0.3 * um)
    fdtd.set("override x mesh", 1); fdtd.set("dx", DX)
    fdtd.set("override y mesh", 1); fdtd.set("dy", DY)
    fdtd.set("override z mesh", 1); fdtd.set("dz", DZ)
    fdtd.addgaussian(name="fiber", injection_axis="z-axis", direction="Backward",
                     x=N_PERIODS * period / 2, x_span=min(3 * MFD_UM * um, x_end + lead - 0.5 * um),
                     y=0, y_span=2 * y_half - 0.2 * um, z=FILM_T + clad + 1.0 * um)
    fdtd.set("waist radius w0", MFD_UM * um / 2)                        # CHECK
    fdtd.set("angle theta", angle)
    fdtd.set("polarization angle", 90)                                  # CHECK: 90 = E along y (s-pol)
    fdtd.addpower(name="T_wg", monitor_type="2D X-normal", x=-lead / 2, y=0, y_span=2 * y_half - 0.2 * um,
                  z=FILM_T / 2, z_span=1.6 * um)
    cells = ((x_end + lead) / DX) * (2 * y_half / DY) * ((FILM_T + 0.5e-6) / DZ)
    return cells


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    fdtd = lumapi.FDTD(hide=HIDE)
    create_ln(fdtd)
    set_ln_index(fdtd, WAVELENGTH, "3d")
    rows = []
    for angle in FIBER_ANGLES_DEG:
        cells = build(fdtd, angle)
        print(f"angle {angle:+.1f}: ~{cells / 1e6:.0f} M cells in the fine-mesh region")
        fdtd.save(os.path.join(OUT_DIR, f"gc3d_a{angle:+.0f}.fsp"))   # saved BEFORE running
        if BUILD_ONLY:
            print("  BUILD_ONLY: saved, not run")
            continue
        fdtd.run()
        eff = np.abs(np.squeeze(fdtd.transmission("T_wg")))
        lam = C / np.squeeze(fdtd.getdata("T_wg", "f"))
        order = np.argsort(lam)
        lam, eff = lam[order] * 1e9, eff[order]
        i = int(np.argmax(eff))
        band = lam[eff >= eff[i] * 10 ** (-0.1)]
        rows.append(dict(angle_deg=angle, period_um=PERIOD_UM, fill=FILL, clad_um=CLAD_UM,
                         width_um=W_GRATING_UM, peak_eff=eff[i], peak_wl_nm=lam[i],
                         bw_1dB_nm=band.max() - band.min(), eff_1550=float(np.interp(1550, lam, eff))))
        print(f"  peak {eff[i]:.3f} ({10 * np.log10(eff[i]):.1f} dB) at {lam[i]:.0f} nm, "
              f"1 dB BW {rows[-1]['bw_1dB_nm']:.0f} nm, eff@1550 {rows[-1]['eff_1550']:.3f}")
        pd.DataFrame({"wl_nm": lam, "eff": eff}).to_csv(
            os.path.join(OUT_DIR, f"gc3d_spectrum_a{angle:+.0f}.csv"), index=False)
        pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "gc3d_summary.csv"), index=False)
    if HIDE:
        fdtd.close()          # with the GUI visible, leave it open so you can look at the results