"""
WG1 width sweep for a TFLN rib waveguide in Lumerical MODE (Python API).

Stack (assumptions, see notes):
    600 nm x-cut LN film on 4.7 um SiO2 (BOX) on Si, oxide cladding,
    400 nm ridge on a 200 nm slab, sidewall angle ANGLES_DEG (measured from slab).

Axis mapping in MODE (cross-section in the y-z plane, propagation along x):
    x = propagation  = crystal Y  -> n_o
    y = lateral      = crystal Z  -> n_e   (TE-like light is polarised along y)
    z = vertical     = crystal X  -> n_o
So the diagonal index tensor is [n_o, n_e, n_o].

Convention: TOP_WIDTHS_UM is the width at the TOP of the ridge (mask width).
The base is wider by 2*h/tan(angle). The sloped wall is built as a staircase
of N_SLICES thin rectangles, which keeps the geometry unambiguous.

Outputs (in OUT_DIR): wg1_sweep.csv, wg1_bend.csv (optional), and PNG plots.
UNTESTED against a live Lumerical install: check the property names marked
with "CHECK" if a call raises an error (they can differ between versions).
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# sys.path.append(r"C:\Program Files\Lumerical\v242\api\python")  # CHECK: your version
import lumapi

# ------------------------------ settings ------------------------------
WAVELENGTH = 1550e-9
ANGLES_DEG = [60, 70, 80]
TOP_WIDTHS_UM = np.round(np.arange(0.8, 2.01, 0.1), 3)

FILM_T = 600e-9          # LN film thickness
RIDGE_H = 400e-9         # ridge height above the slab
SLAB_T = FILM_T - RIDGE_H
BOX_T = 4.7e-6           # buried oxide
CLAD_T = 1.5e-6          # oxide above the film (assumption)
N_OX = 1.444             # SiO2 at 1550 nm (used for the slab-mode estimate)

N_SLICES = 40            # staircase slices for the sloped wall
N_TRIAL = 10             # trial modes per solve
Y_SPAN = 8e-6            # lateral simulation width (PML at the edges)
COMPUTE_NG = True        # 3 wavelengths per case for the group index
DLAMBDA = 10e-9

RUN_BEND = True
BEND_ANGLE = 70
BEND_WIDTHS_UM = [1.0, 1.2, 1.4, 1.6]
BEND_RADII_UM = [20, 30, 50, 80, 120]

CREATE_LN = True         # False: use an LN material you created in the GUI
LN_NAME = "LN_xcut"
HIDE = True
OUT_DIR = "wg1_sweep"


# ------------------------------ materials ------------------------------
def sellmeier(wl_um):
    """Ordinary and extraordinary index (fit quoted in the Luxtelligence manual)."""
    l2 = wl_um ** 2
    no = np.sqrt(1.834 + 3.0 * l2 / (l2 - 0.20315 ** 2))
    ne = np.sqrt(2.513 + 2.0 * l2 / (l2 - 0.21738 ** 2))
    return no, ne


def slab_neff_te(wl):
    """TE slab mode of the 200 nm LN slab between oxides (E along y -> n_e)."""
    _, ne = sellmeier(wl * 1e6)
    k = 2 * np.pi / wl
    t = SLAB_T

    def f(n):
        u = k * t / 2 * np.sqrt(ne ** 2 - n ** 2)
        w = k * t / 2 * np.sqrt(n ** 2 - N_OX ** 2)
        return u * np.tan(u) - w

    lo, hi = N_OX + 1e-6, ne - 1e-6
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def create_ln(mode):
    name = mode.addmaterial("(n,k) Material")          # CHECK
    mode.setmaterial(name, "name", LN_NAME)
    mode.setmaterial(LN_NAME, "Anisotropy", 1)         # CHECK: 1 = diagonal


def set_ln_index(mode, wl):
    no, ne = sellmeier(wl * 1e6)
    try:
        mode.setmaterial(LN_NAME, "Refractive Index", np.array([[no, ne, no]]))
    except Exception:                                   # CHECK: older naming
        for key, val in zip(["Refractive Index", "Refractive Index 2",
                             "Refractive Index 3"], [no, ne, no]):
            mode.setmaterial(LN_NAME, key, float(val))


# ------------------------------ geometry ------------------------------
def build_static(mode):
    mode.switchtolayout()
    mode.deleteall()
    mode.addrect(name="oxide", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN,
                 z_min=-BOX_T, z_max=FILM_T + CLAD_T)
    mode.set("material", "SiO2 (Glass) - Palik")
    mode.addrect(name="Si", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN,
                 z_min=-BOX_T - 20e-6, z_max=-BOX_T)
    mode.set("material", "Si (Silicon) - Palik")
    mode.addrect(name="slab", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN,
                 z_min=0, z_max=SLAB_T)
    mode.set("material", LN_NAME)
    for i in range(N_SLICES):
        z0 = SLAB_T + i * RIDGE_H / N_SLICES
        z1 = SLAB_T + (i + 1) * RIDGE_H / N_SLICES
        mode.addrect(name=f"ridge_{i}", x=0, x_span=2e-6, y=0, y_span=1e-6,
                     z_min=z0, z_max=z1)
        mode.set("material", LN_NAME)

    mode.addmesh(name="ridge_mesh")
    mode.set("x", 0)
    mode.set("y", 0)
    mode.set("y span", 3.6e-6)
    mode.set("z min", -0.1e-6)
    mode.set("z max", FILM_T + 0.1e-6)
    mode.set("override x mesh", 0)
    mode.set("override y mesh", 1)
    mode.set("dy", 15e-9)
    mode.set("override z mesh", 1)
    mode.set("dz", 15e-9)

    mode.addfde()
    mode.set("solver type", "2D X normal")
    mode.set("x", 0)
    mode.set("y", 0)
    mode.set("y span", Y_SPAN)
    mode.set("z min", -BOX_T - 1e-6)
    mode.set("z max", FILM_T + CLAD_T)
    for bc in ["y min bc", "y max bc", "z min bc", "z max bc"]:
        mode.set(bc, "PML")
    mode.set("define y mesh by", "maximum mesh step")
    mode.set("dy", 40e-9)
    mode.set("define z mesh by", "maximum mesh step")
    mode.set("dz", 30e-9)
    mode.set("number of trial modes", N_TRIAL)
    mode.set("search", "max index")                     # CHECK
    mode.set("bent waveguide", 0)


def set_ridge(mode, w_top, angle_deg):
    t = np.tan(np.radians(angle_deg))
    for i in range(N_SLICES):
        hc = (i + 0.5) * RIDGE_H / N_SLICES
        w = w_top + 2 * (RIDGE_H - hc) / t
        mode.setnamed(f"ridge_{i}", "y span", w)


# ------------------------------ solving ------------------------------
def solve(mode, wl):
    set_ln_index(mode, wl)
    mode.setnamed("FDE", "wavelength", wl)
    ret = mode.findmodes()
    try:
        n = int(ret)
    except (TypeError, ValueError):
        n = N_TRIAL
    mods = []
    for m in range(1, n + 1):
        tag = f"FDE::data::mode{m}"
        try:
            neff = complex(np.squeeze(mode.getdata(tag, "neff")))
            te = float(np.real(np.squeeze(mode.getdata(tag, "TE polarization fraction"))))
            loss = float(np.real(np.squeeze(mode.getdata(tag, "loss"))))   # dB/m
        except Exception:
            continue
        try:
            aeff = float(np.real(np.squeeze(mode.getdata(tag, "mode effective area"))))
        except Exception:
            aeff = np.nan
        mods.append(dict(neff=neff.real, te=te, loss_dBcm=loss / 100.0, aeff_um2=aeff * 1e12))
    return mods


def classify(mods, slab_n):
    te = sorted([m for m in mods if m["te"] > 0.5], key=lambda m: -m["neff"])
    tm = sorted([m for m in mods if m["te"] <= 0.5], key=lambda m: -m["neff"])
    guided_te = [m for m in te if m["neff"] > slab_n + 0.01 and m["loss_dBcm"] < 1.0]
    return te, tm, guided_te


def run_sweep(mode):
    rows = []
    slab_n = slab_neff_te(WAVELENGTH)
    print(f"Estimated TE slab-mode index: {slab_n:.4f}")
    for ang in ANGLES_DEG:
        for w in TOP_WIDTHS_UM:
            set_ridge(mode, w * 1e-6, ang)
            mods = solve(mode, WAVELENGTH)
            te, tm, guided = classify(mods, slab_n)
            if not te:
                print(f"angle {ang}, width {w}: no TE-like mode found")
                continue
            row = dict(angle=ang, w_top_um=w,
                       w_base_um=w + 2 * RIDGE_H * 1e6 / np.tan(np.radians(ang)),
                       slab_n=slab_n,
                       te0_neff=te[0]["neff"], te0_tefrac=te[0]["te"],
                       te0_loss_dBcm=te[0]["loss_dBcm"], te0_aeff_um2=te[0]["aeff_um2"],
                       n_guided_te=len(guided),
                       te1_neff=te[1]["neff"] if len(te) > 1 else np.nan,
                       te1_loss_dBcm=te[1]["loss_dBcm"] if len(te) > 1 else np.nan,
                       tm0_neff=tm[0]["neff"] if tm else np.nan)
            if COMPUTE_NG:
                nm = solve(mode, WAVELENGTH - DLAMBDA)
                npl = solve(mode, WAVELENGTH + DLAMBDA)
                te_m = classify(nm, slab_n)[0]
                te_p = classify(npl, slab_n)[0]
                if te_m and te_p:
                    dn = (te_p[0]["neff"] - te_m[0]["neff"]) / (2 * DLAMBDA)
                    row["te0_ng"] = te[0]["neff"] - WAVELENGTH * dn
            rows.append(row)
            print(f"angle {ang:>2}  w_top {w:.2f} um  TE0 neff {row['te0_neff']:.4f}  "
                  f"guided TE modes {row['n_guided_te']}")
    return pd.DataFrame(rows)


def run_bend(mode):
    rows = []
    set_ln_index(mode, WAVELENGTH)
    mode.setnamed("FDE", "bent waveguide", 1)
    mode.setnamed("FDE", "bend orientation", 0)         # CHECK: 0 = in-plane bend
    slab_n = slab_neff_te(WAVELENGTH)
    for w in BEND_WIDTHS_UM:
        set_ridge(mode, w * 1e-6, BEND_ANGLE)
        for r in BEND_RADII_UM:
            mode.setnamed("FDE", "bend radius", r * 1e-6)
            te, _, _ = classify(solve(mode, WAVELENGTH), slab_n)
            if te:
                rows.append(dict(w_top_um=w, radius_um=r, te0_neff=te[0]["neff"],
                                 te0_loss_dBcm=te[0]["loss_dBcm"]))
    mode.setnamed("FDE", "bent waveguide", 0)
    return pd.DataFrame(rows)


# ------------------------------ analysis ------------------------------
def make_plots(df, bend):
    for ang, g in df.groupby("angle"):
        plt.plot(g.w_top_um, g.te0_neff, label=f"TE0 {ang} deg")
        plt.plot(g.w_top_um, g.te1_neff, "--", label=f"TE1 {ang} deg")
    plt.axhline(df.slab_n.iloc[0], color="k", ls=":", label="slab TE mode")
    plt.xlabel("Top width (um)"); plt.ylabel("neff"); plt.legend(fontsize=7)
    plt.savefig(f"{OUT_DIR}/neff_vs_width.png", dpi=150); plt.clf()

    for ang, g in df.groupby("angle"):
        plt.plot(g.w_top_um, g.te0_tefrac, label=f"{ang} deg")
    plt.xlabel("Top width (um)"); plt.ylabel("TE fraction of TE0"); plt.legend()
    plt.savefig(f"{OUT_DIR}/te_fraction.png", dpi=150); plt.clf()

    if "te0_ng" in df:
        for ang, g in df.groupby("angle"):
            plt.plot(g.w_top_um, g.te0_ng, label=f"{ang} deg")
        plt.xlabel("Top width (um)"); plt.ylabel("TE0 group index"); plt.legend()
        plt.savefig(f"{OUT_DIR}/group_index.png", dpi=150); plt.clf()

    if bend is not None and len(bend):
        for w, g in bend.groupby("w_top_um"):
            plt.semilogy(g.radius_um, g.te0_loss_dBcm.clip(lower=1e-6), "o-", label=f"{w} um")
        plt.xlabel("Bend radius (um)"); plt.ylabel("TE0 loss (dB/cm)"); plt.legend()
        plt.savefig(f"{OUT_DIR}/bend_loss.png", dpi=150); plt.clf()


def summarise(df):
    spread = (df.pivot(index="w_top_um", columns="angle", values="te0_neff")
                .agg(lambda r: r.max() - r.min(), axis=1))
    print("\nTE0 neff spread across angles (smaller = less angle-sensitive):")
    print(spread.round(4).to_string())
    for ang, g in df.groupby("angle"):
        g = g.sort_values("w_top_um")
        ok = g[g.n_guided_te == 1]
        print(f"angle {ang}: single guided TE mode for widths up to "
              f"{ok.w_top_um.max() if len(ok) else 'n/a'} um (check for gaps in the table)")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = lumapi.MODE(hide=HIDE)
    if CREATE_LN:
        create_ln(mode)
    set_ln_index(mode, WAVELENGTH)
    build_static(mode)
    mode.save(os.path.join(OUT_DIR, "wg1_sweep.lms"))

    df = run_sweep(mode)
    df.to_csv(f"{OUT_DIR}/wg1_sweep.csv", index=False)
    bend = None
    if RUN_BEND:
        bend = run_bend(mode)
        bend.to_csv(f"{OUT_DIR}/wg1_bend.csv", index=False)
    make_plots(df, bend)
    summarise(df)
    mode.close()