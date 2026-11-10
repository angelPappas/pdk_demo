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

Convention: BASE_WIDTHS_UM is the width at the BASE of the ridge (the width
drawn in the GDS). The top is narrower by 2*h/tan(angle). The sloped wall is
built as a staircase of N_SLICES thin rectangles, which keeps the geometry
unambiguous.

Outputs (in OUT_DIR): wg1_sweep.csv, wg1_bend.csv (optional), and PNG plots.
UNTESTED against a live Lumerical install: check the property names marked
with "CHECK" if a call raises an error (they can differ between versions).
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")  # CHECK: your version
import lumapi

# ------------------------------ settings ------------------------------
WAVELENGTH = 1550e-9
ANGLES_DEG = [60, 70, 80]
BASE_WIDTHS_UM = np.round(np.arange(0.6, 1.81, 0.1), 3)
MIN_TOP_UM = 0.1         # skip cases whose ridge top would be narrower than this

FILM_T = 600e-9          # LN film thickness
RIDGE_H = 400e-9         # ridge height above the slab
SLAB_T = FILM_T - RIDGE_H
BOX_T = 4.7e-6           # buried oxide
CLAD_T = 1.5e-6          # oxide above the film (assumption)
N_OX = 1.444             # SiO2 at 1550 nm (used for the slab-mode estimate)

N_SLICES = 40            # staircase slices for the sloped wall
N_TRIAL = 12             # trial modes per solve
TRIAL_N = 2.05           # mode search is centred near this index (above TE0, below bulk LN)
Z_BELOW = 3e-6           # simulation region extends this far below the film (inside the BOX)
Y_SPAN = 8e-6            # lateral simulation width (PML at the edges)
COMPUTE_NG = True        # 3 wavelengths per case for the group index
DLAMBDA = 10e-9

LOAD_SWEEP_CSV = False  # True: skip the width sweep and reuse OUT_DIR/wg1_sweep.csv
RUN_BEND = True
BEND_ANGLE = 70
BEND_WIDTHS_UM = [0.8, 1.0, 1.2, 1.4]   # base widths
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
    mode.switchtolayout()
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
    mode.set("z min", -Z_BELOW)
    mode.set("z max", FILM_T + CLAD_T)
    for bc in ["y min bc", "y max bc", "z min bc", "z max bc"]:
        mode.set(bc, "PML")
    mode.set("define y mesh by", "maximum mesh step")
    mode.set("dy", 40e-9)
    mode.set("define z mesh by", "maximum mesh step")
    mode.set("dz", 30e-9)
    mode.set("number of trial modes", N_TRIAL)
    mode.set("use max index", 0)
    mode.set("n", TRIAL_N)
    mode.set("bent waveguide", 0)


def top_width_um(w_base_um, angle_deg):
    return w_base_um - 2 * RIDGE_H * 1e6 / np.tan(np.radians(angle_deg))


def set_ridge(mode, w_base, angle_deg):
    """w_base in metres: width at the bottom of the ridge (GDS width)."""
    mode.switchtolayout()
    t = np.tan(np.radians(angle_deg))
    for i in range(N_SLICES):
        hc = (i + 0.5) * RIDGE_H / N_SLICES
        mode.setnamed(f"ridge_{i}", "y span", w_base - 2 * hc / t)


# ------------------------------ solving ------------------------------
_warned = set()


def _read(mode, tag, name):
    """Read one mode result; print the first error for each result name."""
    try:
        return float(np.real(np.squeeze(mode.getdata(tag, name))))
    except Exception as e:
        if name not in _warned:
            print(f"WARNING: could not read '{name}': {e}")
            _warned.add(name)
        return np.nan


def solve(mode, wl):
    mode.switchtolayout()
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
        neff = _read(mode, tag, "neff")
        te = _read(mode, tag, "TE polarization fraction")
        loss = _read(mode, tag, "loss")                      # dB/m
        aeff = _read(mode, tag, "mode effective area")
        if np.isnan(neff) or np.isnan(te):
            continue
        mods.append(dict(neff=neff, te=te, loss_dBcm=(loss / 100.0 if not np.isnan(loss) else 0.0),
                         aeff_um2=aeff * 1e12))
    if not mods:
        print(f"WARNING: no modes read at {wl * 1e9:.0f} nm (findmodes returned {ret!r})")
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
        for w in BASE_WIDTHS_UM:
            w_top = top_width_um(w, ang)
            if w_top < MIN_TOP_UM:
                print(f"angle {ang}, base {w}: top would be {w_top:.2f} um, skipped")
                continue
            set_ridge(mode, w * 1e-6, ang)
            mods = solve(mode, WAVELENGTH)
            te, tm, guided = classify(mods, slab_n)
            if not te:
                print(f"angle {ang}, base {w}: no TE-like mode found")
                continue
            row = dict(angle=ang, w_base_um=w, w_top_um=w_top, slab_n=slab_n,
                       te0_neff=te[0]["neff"], te0_tefrac=te[0]["te"],
                       te0_loss_dBcm=te[0]["loss_dBcm"], te0_aeff_um2=te[0]["aeff_um2"],
                       n_guided_te=len(guided),
                       te1_neff=te[1]["neff"] if len(te) > 1 else np.nan,
                       te1_loss_dBcm=te[1]["loss_dBcm"] if len(te) > 1 else np.nan,
                       tm0_neff=tm[0]["neff"] if tm else np.nan)
            if COMPUTE_NG:
                te_m = classify(solve(mode, WAVELENGTH - DLAMBDA), slab_n)[0]
                te_p = classify(solve(mode, WAVELENGTH + DLAMBDA), slab_n)[0]
                if te_m and te_p:
                    dn = (te_p[0]["neff"] - te_m[0]["neff"]) / (2 * DLAMBDA)
                    row["te0_ng"] = te[0]["neff"] - WAVELENGTH * dn
            rows.append(row)
            print(f"angle {ang:>2}  base {w:.2f} um (top {w_top:.2f})  "
                  f"TE0 neff {row['te0_neff']:.4f}  TE1 neff {row['te1_neff']:.4f}  "
                  f"guided TE modes {row['n_guided_te']}")
    return pd.DataFrame(rows)


def run_bend(mode):
    rows = []
    slab_n = slab_neff_te(WAVELENGTH)
    for w in BEND_WIDTHS_UM:
        if top_width_um(w, BEND_ANGLE) < MIN_TOP_UM:
            continue
        set_ridge(mode, w * 1e-6, BEND_ANGLE)
        mode.setnamed("FDE", "bent waveguide", 1)
        mode.setnamed("FDE", "bend orientation", 0)         # CHECK: 0 = in-plane bend
        for r in BEND_RADII_UM:
            mode.switchtolayout()
            mode.setnamed("FDE", "bend radius", r * 1e-6)
            te, _, _ = classify(solve(mode, WAVELENGTH), slab_n)
            if te:
                rows.append(dict(w_base_um=w, radius_um=r, te0_neff=te[0]["neff"],
                                 te0_loss_dBcm=te[0]["loss_dBcm"]))
        mode.switchtolayout()
        mode.setnamed("FDE", "bent waveguide", 0)
    return pd.DataFrame(rows)


# ------------------------------ analysis ------------------------------
def make_plots(df, bend):
    for ang, g in df.groupby("angle"):
        plt.plot(g.w_base_um, g.te0_neff, label=f"TE0 {ang} deg")
        plt.plot(g.w_base_um, g.te1_neff, "--", label=f"TE1 {ang} deg")
    plt.axhline(df.slab_n.iloc[0], color="k", ls=":", label="slab TE mode")
    plt.xlabel("Base width (um)"); plt.ylabel("neff"); plt.legend(fontsize=7)
    plt.savefig(f"{OUT_DIR}/neff_vs_width.png", dpi=150); plt.clf()

    for ang, g in df.groupby("angle"):
        plt.plot(g.w_base_um, g.te0_tefrac, label=f"{ang} deg")
    plt.xlabel("Base width (um)"); plt.ylabel("TE fraction of TE0"); plt.legend()
    plt.savefig(f"{OUT_DIR}/te_fraction.png", dpi=150); plt.clf()

    if "te0_ng" in df:
        for ang, g in df.groupby("angle"):
            plt.plot(g.w_base_um, g.te0_ng, label=f"{ang} deg")
        plt.xlabel("Base width (um)"); plt.ylabel("TE0 group index"); plt.legend()
        plt.savefig(f"{OUT_DIR}/group_index.png", dpi=150); plt.clf()

    if bend is not None and len(bend):
        for w, g in bend.groupby("w_base_um"):
            plt.semilogy(g.radius_um, g.te0_loss_dBcm.clip(lower=1e-6), "o-", label=f"{w} um")
        plt.xlabel("Bend radius (um)"); plt.ylabel("TE0 loss (dB/cm)"); plt.legend()
        plt.savefig(f"{OUT_DIR}/bend_loss.png", dpi=150); plt.clf()


def summarise(df):
    piv = df.pivot(index="w_base_um", columns="angle", values="te0_neff")
    print("\nTE0 neff spread across angles at each base width (smaller = less angle-sensitive):")
    print((piv.max(axis=1) - piv.min(axis=1)).round(4).to_string())
    for ang, g in df.groupby("angle"):
        g = g.sort_values("w_base_um")
        ok = g[g.n_guided_te == 1]
        print(f"angle {ang}: single guided TE mode for base widths up to "
              f"{ok.w_base_um.max() if len(ok) else 'none in range'} um")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = lumapi.MODE(hide=HIDE)
    if CREATE_LN:
        create_ln(mode)
    set_ln_index(mode, WAVELENGTH)
    build_static(mode)
    mode.save(os.path.join(OUT_DIR, "wg1_sweep.lms"))

    if LOAD_SWEEP_CSV:
        df = pd.read_csv(f"{OUT_DIR}/wg1_sweep.csv")
    else:
        df = run_sweep(mode)
        df.to_csv(f"{OUT_DIR}/wg1_sweep.csv", index=False)
    bend = None
    if RUN_BEND:
        bend = run_bend(mode)
        bend.to_csv(f"{OUT_DIR}/wg1_bend.csv", index=False)
    make_plots(df, bend)
    summarise(df)
    mode.close()