"""
Waveguide building block (MODE): TE0 effective index and group index of the chosen WG1,
straight and bent, versus wavelength. Writes wg_model.json, which circuit_models.py reads.

    ng(lambda) = neff - lambda * d(neff)/d(lambda)      (quadratic fit of neff around 1550 nm)

Bent case: for a ring of radius R, neff is referenced to the centre of the ridge, so the ring
FSR is lambda^2 / (ng_bend * 2 pi R). The straight ng (MZI) and the bend ng (ring) can differ.
UNTESTED against a live Lumerical install; lines marked CHECK may need adjusting.
"""
import json
import os
import sys

import numpy as np

sys.path.append(r"C:\Program Files\Lumerical\v261\api\python")
import lumapi
from tfln_common import *

WAVELENGTHS = np.arange(1500e-9, 1600.1e-9, 10e-9)
BEND_RADII_UM = [100.0]
N_SLICES = 40
N_TRIAL = 12
TRIAL_N = 2.05
Z_BELOW = 3e-6
Y_SPAN = 8e-6
HIDE = True
OUT_DIR = os.path.abspath("wg_model")


def read(mode, tag, name):
    try:
        return float(np.real(np.squeeze(mode.getdata(tag, name))))
    except Exception as e:
        print(f"WARNING: could not read '{name}': {e}")
        return np.nan


def build(mode):
    mode.switchtolayout()
    mode.deleteall()
    mode.addrect(name="oxide", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN, z_min=-BOX_T,
                 z_max=FILM_T + CLAD_T)
    mode.set("material", "SiO2 (Glass) - Palik")
    mode.addrect(name="slab", x=0, x_span=2e-6, y=0, y_span=3 * Y_SPAN, z_min=0, z_max=SLAB_T)
    mode.set("material", LN_NAME)
    for i, (z0, z1, w) in enumerate(slice_levels(N_SLICES, WG_BASE)):
        mode.addrect(name=f"ridge_{i}", x=0, x_span=2e-6, y=0, y_span=w, z_min=z0, z_max=z1)
        mode.set("material", LN_NAME)
    mode.addmesh(name="ridge_mesh")
    mode.set("x", 0); mode.set("y", 0); mode.set("y span", 3e-6)
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
    mode.set("bent waveguide", 0)


def te0(mode, wl):
    set_ln_index(mode, wl, "3d")
    mode.setnamed("FDE", "wavelength", wl)
    ret = mode.findmodes()
    try:
        n = int(ret)
    except (TypeError, ValueError):
        n = N_TRIAL
    best = None
    for m in range(1, n + 1):
        tag = f"FDE::data::mode{m}"
        neff, te = read(mode, tag, "neff"), read(mode, tag, "TE polarization fraction")
        if np.isnan(neff) or te <= 0.5:
            continue
        if best is None or neff > best[0]:
            best = (neff, te, read(mode, tag, "loss") / 100.0)      # loss in dB/cm
    if best is None:
        raise RuntimeError(f"no TE-like mode at {wl * 1e9:.0f} nm")
    return best


def fit(wls, neff):
    x = (wls - WAVELENGTH) * 1e6                          # um from 1550 nm
    n2, n1, n0 = np.polyfit(x, neff, 2)                   # neff = n0 + n1 x + n2 x^2 (x in um)
    lam_um = wls * 1e6
    ng = neff_fit = n0 + n1 * x + n2 * x ** 2
    ng = neff_fit - lam_um * (n1 + 2 * n2 * x)
    d_ps = -(WAVELENGTH / 299792458.0) * (2 * n2 * 1e12) / 1e-6     # ps/(nm km)
    return dict(neff_poly=[n0, n1, n2], neff_fit=list(neff_fit), ng=list(ng), D_ps_nm_km=d_ps,
                ng_1550=float(n0 - (WAVELENGTH * 1e6) * n1))


def sweep(mode, bent_radius=None):
    mode.switchtolayout()
    if bent_radius is None:
        mode.setnamed("FDE", "bent waveguide", 0)
    else:
        mode.setnamed("FDE", "bent waveguide", 1)
        mode.setnamed("FDE", "bend radius", bent_radius)
        mode.setnamed("FDE", "bend orientation", 0)       # CHECK: 0 = in-plane bend
    res = [te0(mode, wl) for wl in WAVELENGTHS]
    neff = np.array([r[0] for r in res])
    out = dict(neff=list(neff), te_fraction=[r[1] for r in res], loss_dB_cm=[r[2] for r in res])
    out.update(fit(WAVELENGTHS, neff))
    return out


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = lumapi.MODE(hide=HIDE)
    create_ln(mode)
    build(mode)
    mode.save(os.path.join(OUT_DIR, "wg_model.lms"))
    model = dict(config=dict(base_width_um=WG_BASE * 1e6, angle_deg=ANGLE_DEG, clad_um=CLAD_T * 1e6,
                             lam0_nm=WAVELENGTH * 1e9),
                 wavelength_nm=list(WAVELENGTHS * 1e9), straight=sweep(mode), bend={})
    s = model["straight"]
    print(f"straight: neff {s['neff_poly'][0]:.4f}, ng {s['ng_1550']:.4f}, D {s['D_ps_nm_km']:.0f} ps/nm/km")
    for r in BEND_RADII_UM:
        b = sweep(mode, r * 1e-6)
        model["bend"][str(r)] = b
        print(f"bend R={r:.0f} um: neff {b['neff_poly'][0]:.4f}, ng {b['ng_1550']:.4f}, "
              f"loss {b['loss_dB_cm'][len(WAVELENGTHS) // 2]:.3g} dB/cm, "
              f"TE fraction {b['te_fraction'][len(WAVELENGTHS) // 2]:.3f}")
    with open(os.path.join(OUT_DIR, "wg_model.json"), "w") as f:
        json.dump(model, f, indent=1)
    mode.close()