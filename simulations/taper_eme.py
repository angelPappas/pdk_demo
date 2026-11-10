"""
Grating-coupler taper (1.0 um -> 12 um base width) with the Lumerical EME solver (in MODE).

Step 1 (default): sweep the taper LENGTH at one wavelength; print/save the TE0 -> TE0 transmission
        |S21|^2 and the total power into all other modes (= scattering/mode-conversion loss).
Step 2 (RUN_WAVELENGTH_SWEEP = True): for the chosen length, get S21/S12 (and S11/S22) versus
        wavelength, save them to taper_sparams.npz/.csv and write an INTERCONNECT-style .dat.

Axes: x = propagation, y = lateral, z = vertical (same as the coupler scripts).
Geometry: Si, 4.7 um BOX, 200 nm slab, 400 nm sloped ridge whose BASE width follows W(x) (linear
or power-law with exponent TAPER_EXP; 1.0 = linear), oxide cladding 1.6 um, air above.
Set BUILD_ONLY = True to just build + save the .lms and inspect it in the GUI first.

NOT tested against a live Lumerical install. The EME property names / result names below follow
the Lumerical docs but are the most likely place for a first error: lines marked CHECK.
If the .dat export disagrees with INTERCONNECT, use the EME analysis window's
"Export to INTERCONNECT" button on the saved .lms instead (the S-matrix CSV/NPZ is always saved).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

W_NARROW_UM, W_WIDE_UM = 1.0, 12.0
TAPER_EXP = 1.0                         # 1.0 = linear; <1 widens faster at the start
LENGTHS_UM = [50.0, 100.0, 150.0, 200.0, 300.0]
FINAL_LENGTH_UM = 200.0                 # used by the wavelength sweep
RUN_WAVELENGTH_SWEEP = False
WAVELENGTHS_NM = np.linspace(1530, 1570, 9)
LEAD_UM = 5.0                           # straight sections either side
N_SLICES = 8
N_MODES = 30                            # modes per cell group (12 um wide section is multimode)
CELLS_TAPER_PER_UM = 0.4                # EME cells in the taper group
Y_SPAN_UM = 24.0
Z_BELOW, Z_ABOVE = 2.0e-6, 1.6e-6 + 1.5e-6   # window below the film / above the film top
BUILD_ONLY = False
HIDE = False
OUT_DIR = os.path.abspath("taper_eme")
C = 299792458.0


def width_at(x_um, L_um):
    t = np.clip(x_um / L_um, 0, 1)
    return W_NARROW_UM + (W_WIDE_UM - W_NARROW_UM) * t ** TAPER_EXP


def set_port_mode(mode, port, number):
    """Pick the mode of an EME port. The property name differs between versions, so try a few
    and, if none works, print the real property list so it can be fixed here."""
    for key in ("mode number", "mode numbers", "mode", "mode index", "user mode"):
        try:
            mode.set(key, number)
            return key
        except Exception:
            continue
    print(f"Could not set the mode on {port}. Properties of this object are:")
    try:
        print(mode.getnamed("EME::Ports::" + port))
    except Exception as e:
        print("  (could not list them:", e, ")")
    print("Leaving the default 'mode selection'. Mode 1 = highest-index mode of the port cross-section.")
    try:
        mode.set("mode selection", "fundamental mode")
    except Exception:
        pass


def pick_te_mode(mode, x, tag, n_modes=12):
    """Rank (1-based, by decreasing neff, as the EME orders them) of the highest-index TE-like
    mode at cross-section x. Uses a temporary 2D FDE solver and its TE polarization fraction."""
    um = 1e-6
    mode.addfde()                                      # MODE has one FDE object, always named "FDE"
    mode.set("solver type", "2D X normal")
    mode.set("x", x); mode.set("y", 0); mode.set("y span", Y_SPAN_UM * um)
    mode.set("z min", -Z_BELOW); mode.set("z max", FILM_T + Z_ABOVE)
    for bc in ("y min bc", "y max bc", "z min bc", "z max bc"):
        mode.set(bc, "PML")
    mode.set("define y mesh by", "maximum mesh step"); mode.set("dy", 60e-9)
    mode.set("define z mesh by", "maximum mesh step"); mode.set("dz", 40e-9)
    mode.set("wavelength", WAVELENGTH)
    mode.set("number of trial modes", n_modes)
    mode.set("use max index", 1)                       # highest-index modes first, like the EME
    ret = mode.findmodes()
    n = int(ret) if ret is not None else n_modes
    found = []
    for m in range(1, n + 1):
        try:
            neff = float(np.real(np.squeeze(mode.getdata(f"FDE::data::mode{m}", "neff"))))
            te = float(np.real(np.squeeze(mode.getdata(f"FDE::data::mode{m}", "TE polarization fraction"))))
        except Exception:
            continue
        found.append((m, neff, te))
    print(f"  {tag}: modes (rank, neff, TE fraction):")
    for m, neff, te in found:
        print(f"     {m:2d}  {neff:.4f}  {te:.2f}")
    mode.switchtolayout()
    mode.select("FDE")
    mode.delete()
    te_modes = [m for m, neff, te in found if te > 0.5]
    if not te_modes:
        print("  WARNING: no TE-like mode found; using mode 1")
        return 1
    return te_modes[0]


def build(mode, L_um):
    um = 1e-6
    mode.switchtolayout()
    mode.deleteall()
    lead, Lt = LEAD_UM * um, L_um * um
    x0, x1 = -lead, Lt + lead
    xs = dict(x_min=x0 - 1 * um, x_max=x1 + 1 * um, y=0, y_span=Y_SPAN_UM * um + 4 * um)
    mode.addrect(name="Si", z_min=-BOX_T - 3 * um, z_max=-BOX_T, **xs)
    mode.set("material", "Si (Silicon) - Palik")
    mode.addrect(name="oxide", z_min=-BOX_T, z_max=FILM_T + CLAD_T, **xs)
    mode.set("material", "SiO2 (Glass) - Palik")
    mode.addrect(name="slab", z_min=0, z_max=SLAB_T, **xs)
    mode.set("material", LN_NAME)
    xu = np.linspace(0, L_um, 201)                       # taper outline points (um)
    w_base = width_at(xu, L_um) * um
    x_all = np.concatenate([[x0 / um - 1], xu, [L_um + LEAD_UM + 1]]) * um
    w_all = np.concatenate([[w_base[0]], w_base, [w_base[-1]]])
    # taper is defined between 0 and L; straights are extended to x0, x1
    x_all[0], x_all[-1] = x0 - 1 * um, x1 + 1 * um
    for i, (z0, z1, wz) in enumerate(slice_levels(N_SLICES, 1.0)):
        shrink = (1.0 - wz) * um          # base width minus width at this slice height
        hw = (w_all - shrink) / 2
        V = np.concatenate([np.column_stack([x_all, hw]), np.column_stack([x_all[::-1], -hw[::-1]])])
        mode.addpoly(name=f"ridge_{i}", x=0, y=0, z_min=z0, z_max=z1)
        mode.set("vertices", V)
        mode.set("material", LN_NAME)
    mode.addmesh(name="ridge_mesh", x_min=x0, x_max=x1, y=0, y_span=Y_SPAN_UM * um,
                 z_min=-0.1 * um, z_max=FILM_T + 0.1 * um)
    mode.set("override x mesh", 0)
    mode.set("override y mesh", 1); mode.set("dy", 40e-9)
    mode.set("override z mesh", 1); mode.set("dz", 25e-9)
    # EME region: three cell groups (lead, taper, lead)
    mode.addeme()
    mode.set("x min", x0); mode.set("y", 0); mode.set("y span", Y_SPAN_UM * um)
    mode.set("z min", -Z_BELOW); mode.set("z max", FILM_T + Z_ABOVE)
    mode.set("wavelength", WAVELENGTH)
    mode.set("number of cell groups", 3)
    mode.set("group spans", np.array([[lead], [Lt], [lead]]))
    n_taper = max(8, int(round(CELLS_TAPER_PER_UM * L_um)))
    mode.set("cells", np.array([[1], [n_taper], [1]]))
    mode.set("subcell method", np.array([[0], [1], [0]]))             # CHECK: 0 none, 1 CVCS
    mode.set("number of modes for all cell groups", N_MODES)
    mode.set("energy conservation", "conserve energy")                # CHECK
    for bc in ("y min bc", "y max bc", "z min bc", "z max bc"):
        mode.set(bc, "PML")
    mode.set("define y mesh by", "maximum mesh step"); mode.set("dy", 60e-9)    # CHECK
    mode.set("define z mesh by", "maximum mesh step"); mode.set("dz", 40e-9)
    mode.set("display cells", 0)
    # ports: fundamental TE mode on both sides
    te_rank = {"port_1": pick_te_mode(mode, -lead / 2, "in"),
               "port_2": pick_te_mode(mode, Lt + lead / 2, "out")}
    print(f"  TE-like mode numbers used: {te_rank}")
    for name, loc in (("port_1", "left"), ("port_2", "right")):
        mode.select("EME::Ports::" + name)                            # CHECK: default ports exist
        mode.set("mode selection", "user select")
        set_port_mode(mode, name, te_rank[name])


_printed = False


def te0_s_matrix(mode):
    """Return (S11, S21, S12, S22, total_power_out) for the TE0 mode at both ends."""
    mode.emepropagate()
    s = mode.getresult("EME", "user s matrix")                        # CHECK
    S = np.squeeze(np.array(s["user s matrix"] if isinstance(s, dict) else s))
    global _printed
    if not _printed:
        print("  S-matrix shape:", S.shape)
        print("  |S|^2 =\n", np.round(np.abs(S) ** 2, 5))
        _printed = True
    return S


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = lumapi.MODE(hide=HIDE)
    create_ln(mode)
    set_ln_index(mode, WAVELENGTH, "3d")
    rows = []
    lengths = [FINAL_LENGTH_UM] if RUN_WAVELENGTH_SWEEP else LENGTHS_UM
    for L in lengths:
        build(mode, L)
        mode.save(os.path.join(OUT_DIR, f"taper_L{L:.0f}.lms"))
        if BUILD_ONLY:
            print(f"L {L}: built and saved (BUILD_ONLY)")
            continue
        if not RUN_WAVELENGTH_SWEEP:
            mode.run()                                                # cell + mode solve
            S = te0_s_matrix(mode)
            t = float(np.abs(S[1, 0]) ** 2) if S.ndim == 2 else float("nan")
            rows.append(dict(length_um=L, T_TE0=t, loss_dB=-10 * np.log10(t), exp=TAPER_EXP))
            print(f"L {L:6.0f} um: T(TE0->TE0) {t:.4f}  ({-10 * np.log10(t):.3f} dB)")
            pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "taper_length_sweep.csv"), index=False)
        else:
            out = []
            for wl_nm in WAVELENGTHS_NM:
                set_ln_index(mode, wl_nm * 1e-9, "3d")
                mode.setnamed("EME", "wavelength", wl_nm * 1e-9)
                mode.run()
                S = te0_s_matrix(mode)
                out.append(S)
                print(f"{wl_nm:.0f} nm: |S21|^2 = {abs(S[1, 0]) ** 2:.4f}")
            out = np.array(out)                                       # (n_wl, 2, 2)
            np.savez(os.path.join(OUT_DIR, "taper_sparams.npz"), wl_nm=WAVELENGTHS_NM, S=out)
            pd.DataFrame({"wl_nm": WAVELENGTHS_NM,
                          "S11_abs": abs(out[:, 0, 0]), "S21_abs": abs(out[:, 1, 0]),
                          "S12_abs": abs(out[:, 0, 1]), "S22_abs": abs(out[:, 1, 1]),
                          "S21_phase": np.unwrap(np.angle(out[:, 1, 0]))}).to_csv(
                os.path.join(OUT_DIR, "taper_sparams.csv"), index=False)
            # INTERCONNECT-style N-port file: one block per (output, input) pair, f ascending
            f = C / (WAVELENGTHS_NM * 1e-9)
            order = np.argsort(f)
            with open(os.path.join(OUT_DIR, "taper_sparams.dat"), "w") as fh:
                for o, i in ((1, 0), (0, 1), (0, 0), (1, 1)):         # S21, S12, S11, S22
                    fh.write(f"('port {o + 1}','TE',1,'port {i + 1}',1,'transmission')\n")  # CHECK format
                    fh.write(f"({len(f)},3)\n")
                    for k in order:
                        fh.write(f"{f[k]:.9e} {abs(out[k, o, i]):.9e} {np.angle(out[k, o, i]):.9e}\n")
            print("Saved S-parameters in", OUT_DIR)
    if HIDE:
        mode.close()