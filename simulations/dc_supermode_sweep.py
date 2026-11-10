"""
Directional coupler, step 1: supermode estimate in Lumerical MODE (fast, no 3D FDTD).

For two parallel WG1 ridges (base width WG_BASE) separated by an edge-to-edge BASE gap,
solve the even and odd TE-like supermodes. With dn = n_even - n_odd:
    full-transfer length Lc = lambda / (2 dn),   50:50 length L50 = lambda / (4 dn)
Straight section only: the bends add extra coupling, which the FDTD run captures.
UNTESTED against a live Lumerical install. Run from the folder holding tfln_common.py.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

GAPS_UM = np.round(np.arange(0.30, 0.71, 0.05), 3)       # edge-to-edge gap at the ridge BASE
WAVELENGTHS = [1530e-9, 1550e-9, 1570e-9]
N_SLICES = 40
N_TRIAL = 12
TRIAL_N = 2.05
Z_BELOW = 3e-6
Y_SPAN = 14e-6
HIDE = True
OUT_DIR = "dc_supermodes"
_warned = set()


def read(mode, tag, name):
    try:
        return float(np.real(np.squeeze(mode.getdata(tag, name))))
    except Exception as e:
        if name not in _warned:
            print(f"WARNING: could not read '{name}': {e}")
            _warned.add(name)
        return np.nan


def build(mode):
    mode.switchtolayout()
    mode.deleteall()
    mode.addrect(name="oxide", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN,
                 z_min=-BOX_T, z_max=FILM_T + CLAD_T)
    mode.set("material", "SiO2 (Glass) - Palik")
    mode.addrect(name="slab", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN, z_min=0, z_max=SLAB_T)
    mode.set("material", LN_NAME)
    for side in "AB":
        for i, (z0, z1, w) in enumerate(slice_levels(N_SLICES, WG_BASE)):
            mode.addrect(name=f"ridge{side}_{i}", x=0, x_span=2e-6, y=0, y_span=w,
                         z_min=z0, z_max=z1)
            mode.set("material", LN_NAME)
    mode.addmesh(name="ridge_mesh")
    mode.set("x", 0); mode.set("y", 0); mode.set("y span", 6e-6)
    mode.set("z min", -0.1e-6); mode.set("z max", FILM_T + 0.1e-6)
    mode.set("override x mesh", 0)
    mode.set("override y mesh", 1); mode.set("dy", 15e-9)
    mode.set("override z mesh", 1); mode.set("dz", 15e-9)
    mode.addfde()
    mode.set("solver type", "2D X normal")
    mode.set("x", 0); mode.set("y", 0); mode.set("y span", Y_SPAN)
    mode.set("z min", -Z_BELOW); mode.set("z max", FILM_T + CLAD_T)
    for bc in ["y min bc", "y max bc", "z min bc", "z max bc"]:
        mode.set(bc, "PML")
    mode.set("define y mesh by", "maximum mesh step"); mode.set("dy", 40e-9)
    mode.set("define z mesh by", "maximum mesh step"); mode.set("dz", 30e-9)
    mode.set("number of trial modes", N_TRIAL)
    mode.set("use max index", 0)
    mode.set("n", TRIAL_N)


def set_gap(mode, gap):
    mode.switchtolayout()
    d = WG_BASE + gap                                     # centre-to-centre
    for side, sign in (("A", 1), ("B", -1)):
        for i in range(N_SLICES):
            mode.setnamed(f"ridge{side}_{i}", "y", sign * d / 2)


def solve(mode, wl):
    set_ln_index(mode, wl, "3d")
    mode.setnamed("FDE", "wavelength", wl)
    ret = mode.findmodes()
    try:
        n = int(ret)
    except (TypeError, ValueError):
        n = N_TRIAL
    mods = []
    for m in range(1, n + 1):
        tag = f"FDE::data::mode{m}"
        neff, te = read(mode, tag, "neff"), read(mode, tag, "TE polarization fraction")
        if not (np.isnan(neff) or np.isnan(te)):
            mods.append(dict(neff=neff, te=te))
    return mods


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = lumapi.MODE(hide=HIDE)
    create_ln(mode)
    set_ln_index(mode, WAVELENGTH, "3d")
    build(mode)
    mode.save(os.path.join(OUT_DIR, "dc_supermodes.lms"))
    rows = []
    for gap in GAPS_UM:
        set_gap(mode, gap * 1e-6)
        for wl in WAVELENGTHS:
            mods = solve(mode, wl)
            te = sorted([m for m in mods if m["te"] > 0.5], key=lambda m: -m["neff"])
            tm = sorted([m for m in mods if m["te"] <= 0.5], key=lambda m: -m["neff"])
            if len(te) < 2:
                print(f"gap {gap}, {wl * 1e9:.0f} nm: fewer than 2 TE-like modes found")
                continue
            dn = te[0]["neff"] - te[1]["neff"]
            rows.append(dict(gap_um=gap, wl_nm=wl * 1e9, n_even=te[0]["neff"], n_odd=te[1]["neff"],
                             dn=dn, L50_um=wl / (4 * dn) * 1e6, Lc_um=wl / (2 * dn) * 1e6,
                             third_te_neff=te[2]["neff"] if len(te) > 2 else np.nan,
                             tm_top_neff=tm[0]["neff"] if tm else np.nan))
            print(f"gap {gap:.2f}  {wl * 1e9:.0f} nm  dn {dn:.5f}  L50 {rows[-1]['L50_um']:.1f} um")
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT_DIR}/dc_supermodes.csv", index=False)
    for wl, g in df.groupby("wl_nm"):
        plt.semilogy(g.gap_um, g.L50_um, "o-", label=f"{wl:.0f} nm")
    plt.xlabel("Base gap (um)"); plt.ylabel("50:50 length L50 (um)"); plt.legend()
    plt.savefig(f"{OUT_DIR}/L50_vs_gap.png", dpi=150)
    mode.close()
