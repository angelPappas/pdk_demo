"""
Directional coupler, step 2: 3D FDTD of the full coupler (straight section + S-bends).

Layout (x = propagation, y = lateral, z = vertical): two WG1 arms, base gap GAP between
the ridge bases in the coupled section of length LENGTH, then sine S-bends out to a
centre-to-centre port separation PORT_SEP.
A TE mode is launched in the bottom-left arm. Power monitors on the right measure
    T_through (bottom-right) and T_cross (top-right).
Split ratio = T_cross / (T_cross + T_through).  Monitors integrate TE + TM power.
Set RUN_SPARAMS = True afterwards to build the 4-port S-parameter sweep and export a .dat
for INTERCONNECT.

UNTESTED against a live Lumerical install; lines marked CHECK may need adjusting.
A 3D run is heavy: check the cell estimate, start with MESH_ACCURACY = 1 or 2.
LN is non-dispersive here (index fixed at the centre wavelength).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

# (gap_um, length_um) pairs: take them from dc_supermode_sweep.py (L50 for each gap).
DESIGNS = [(0.40, 21.0)]   # 19 um already run: cross 0.454 at 1550 nm
PORT_SEP_UM = 4.0                    # centre-to-centre separation at the ports
S_BEND_L_UM = 20.0
LEAD_UM = 3.0                        # straight lead-in/out
WL_START, WL_STOP, N_FREQ = 1530e-9, 1570e-9, 11
N_SLICES = 10
MESH_ACCURACY = 2
DX, DY, DZ = 30e-9, 30e-9, 20e-9
SIM_TIME = 3500e-15
RUN_SPARAMS = True  # build the 4-port S-parameter sweep and export a .dat for INTERCONNECT
HIDE = True
OUT_DIR = os.path.abspath("dc_fdtd")   # absolute: Lumerical changes its working directory on save
Y_PAD = 2.5e-6
Z_MIN, Z_MAX = -1.0e-6, FILM_T + 0.9e-6


def build(fdtd, gap, length):
    um = 1e-6
    s_len, lead, port_sep = S_BEND_L_UM * um, LEAD_UM * um, PORT_SEP_UM * um
    x_end = length / 2 + s_len + lead
    d_c = WG_BASE + gap
    y_half = port_sep / 2 + WG_BASE / 2 + Y_PAD
    fdtd.switchtolayout()
    fdtd.deleteall()
    fdtd.addrect(name="oxide", x=0, x_span=2 * x_end + 4 * um, y=0, y_span=2 * y_half + 4 * um,
                 z_min=-BOX_T, z_max=FILM_T + CLAD_T)
    fdtd.set("material", "SiO2 (Glass) - Palik")
    fdtd.addrect(name="slab", x=0, x_span=2 * x_end + 4 * um, y=0, y_span=2 * y_half + 4 * um,
                 z_min=0, z_max=SLAB_T)
    fdtd.set("material", LN_NAME)
    x = np.linspace(-x_end - 1 * um, x_end + 1 * um, 700)
    for sign, tag in ((1, "top"), (-1, "bot")):
        y = arm_centerline(sign, x, length, d_c, port_sep, s_len)
        for i, (z0, z1, w) in enumerate(slice_levels(N_SLICES, WG_BASE)):
            fdtd.addpoly(name=f"ridge_{tag}_{i}", x=0, y=0, z_min=z0, z_max=z1)
            fdtd.set("vertices", offset_polygon(x, y, w))
            fdtd.set("material", LN_NAME)
    zc = FILM_T / 2
    fdtd.addfdtd(dimension="3D", x=0, y=0, z=(Z_MIN + Z_MAX) / 2, x_span=2 * x_end,
                 y_span=2 * y_half, z_span=Z_MAX - Z_MIN)
    fdtd.set("simulation time", SIM_TIME)
    fdtd.set("mesh accuracy", MESH_ACCURACY)                          # CHECK
    fdtd.setglobalsource("wavelength start", WL_START)
    fdtd.setglobalsource("wavelength stop", WL_STOP)
    fdtd.setglobalmonitor("frequency points", N_FREQ)
    fdtd.addmesh(name="guide_mesh", x=0, x_span=2 * x_end, y=0, y_span=2 * y_half - 1 * um,
                 z_min=-0.1e-6, z_max=FILM_T + 0.1e-6)
    fdtd.set("override x mesh", 1); fdtd.set("dx", DX)
    fdtd.set("override y mesh", 1); fdtd.set("dy", DY)
    fdtd.set("override z mesh", 1); fdtd.set("dz", DZ)
    x_p = x_end - 0.8 * um
    if not RUN_SPARAMS:
        fdtd.addmode(name="src", injection_axis="x-axis", direction="Forward", x=-x_p,
                     y=-port_sep / 2, y_span=3 * um, z=zc, z_span=1.8 * um)
        fdtd.set("mode selection", "fundamental TE mode")             # CHECK
        for name, y0, y1 in (("T_through", -y_half, 0), ("T_cross", 0, y_half)):
            fdtd.addpower(name=name, monitor_type="2D X-normal", x=x_p, y=(y0 + y1) / 2,
                          y_span=(y1 - y0) - 1 * um, z=zc, z_span=1.8 * um)
        fdtd.addpower(name="field_xy", monitor_type="2D Z-normal", x=0, x_span=2 * x_end,
                      y=0, y_span=2 * y_half - 1 * um, z=zc)
    else:
        for k, (xs, ys, d) in enumerate([(-x_p, -port_sep / 2, "Forward"), (-x_p, port_sep / 2, "Forward"),
                                         (x_p, -port_sep / 2, "Backward"), (x_p, port_sep / 2, "Backward")], 1):
            fdtd.addport(name=f"port {k}", x=xs, y=ys, y_span=3 * um, z=zc, z_span=1.8 * um,
                         direction=d)
            fdtd.set("mode selection", "fundamental TE mode")         # CHECK
    return x_end


def find_sweep(fdtd):
    """Return the name of the S-parameter sweep object (name differs between docs/versions)."""
    for cand in ("s-parameter sweep", "S-parameter sweep", "sweep"):
        try:
            fdtd.getsweep(cand, "Excite all ports")      # raises if the object does not exist
            return cand
        except Exception:
            continue
    raise RuntimeError("Could not find the S-parameter sweep object. Open the saved .fsp in the "
                       "FDTD GUI, check its name under 'Optimization and Sweeps', and put it in "
                       "find_sweep().")


def run_sparams(fdtd, out_file):
    fdtd.addsweep(3)                                     # 3 = S-parameter sweep
    sweep = find_sweep(fdtd)
    print("Using sweep object:", sweep)
    for key, val in {"Excite all ports": 1, "auto symmetry": 1, "include group delay": 1}.items():
        try:
            fdtd.setsweep(sweep, key, val)
        except Exception as e:
            print(f"setsweep '{key}' failed: {e}")      # CHECK property names
    fdtd.runsweep(sweep)
    fdtd.exportsweep(sweep, out_file)                    # Lumerical .dat; add "touchstone" for .s4p
    print("Exported", out_file)


def results(fdtd, gap, length):
    rows = []
    t_thr = np.abs(np.squeeze(fdtd.transmission("T_through")))
    t_crs = np.abs(np.squeeze(fdtd.transmission("T_cross")))
    f = np.squeeze(fdtd.getdata("T_through", "f"))
    lam = 299792458.0 / f
    for l, tt, tc in zip(lam, t_thr, t_crs):
        tot = tt + tc
        rows.append(dict(gap_um=gap, length_um=length, wl_nm=l * 1e9, T_through=tt, T_cross=tc,
                         split_cross=tc / tot, excess_loss_dB=-10 * np.log10(tot)))
    return pd.DataFrame(rows).sort_values("wl_nm")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    fdtd = lumapi.FDTD(hide=HIDE)
    create_ln(fdtd)
    set_ln_index(fdtd, WAVELENGTH, "3d")
    frames = []
    for gap_um, length_um in DESIGNS:
        gap, length = gap_um * 1e-6, length_um * 1e-6
        x_end = build(fdtd, gap, length)
        cells = (2 * x_end / DX) * ((PORT_SEP_UM + 6) * 1e-6 / DY) * ((FILM_T + 0.2e-6) / DZ)
        print(f"gap {gap_um} um, L {length_um} um: ~{cells / 1e6:.0f} M cells in the fine-mesh region")
        name = os.path.join(OUT_DIR, f"dc_g{gap_um}_L{length_um}")
        fdtd.save(name + ".fsp")
        if RUN_SPARAMS:
            run_sparams(fdtd, name + ".dat")
            continue
        fdtd.run()
        df = results(fdtd, gap_um, length_um)
        df.to_csv(name + ".csv", index=False)
        frames.append(df)
        mid = df.iloc[len(df) // 2]
        print(f"  centre {mid.wl_nm:.0f} nm: cross {mid.split_cross:.3f}, "
              f"excess loss {mid.excess_loss_dB:.2f} dB")
    if frames:
        pd.concat(frames).to_csv(os.path.join(OUT_DIR, "dc_summary.csv"), index=False)
    fdtd.close()