"""
Shared definitions for the TFLN WG1 simulations (directional coupler, grating coupler).

Stack: 600 nm x-cut LN on 4.7 um SiO2 (BOX), oxide cladding, 400 nm ridge on a 200 nm
slab. WG_BASE is the BASE width of the ridge (the width drawn in the GDS). The sloped
wall (ANGLE_DEG, from the slab surface) is built as a staircase of thin layers.

LN index tensor in the simulation axes:
    3D / MODE : x = propagation (crystal Y), y = lateral (crystal Z), z = vertical (crystal X)
                -> diag [n_o, n_e, n_o]
    2D FDTD   : x = propagation, y = vertical, z = out of plane (TE: E along z)
                -> diag [n_o, n_o, n_e]
"""
import numpy as np

FILM_T = 600e-9
RIDGE_H = 400e-9
SLAB_T = FILM_T - RIDGE_H
BOX_T = 4.7e-6
CLAD_T = 1.6e-6          # 1.6 um: best grating-coupler efficiency (cladding sweep)
ANGLE_DEG = 70.0
WG_BASE = 1.0e-6          # chosen from the width sweep
WAVELENGTH = 1550e-9
LN_NAME = "LN_xcut"


def sellmeier(wl_um):
    """Ordinary / extraordinary index of LN (fit quoted in the Luxtelligence manual)."""
    l2 = wl_um ** 2
    no = np.sqrt(1.834 + 3.0 * l2 / (l2 - 0.20315 ** 2))
    ne = np.sqrt(2.513 + 2.0 * l2 / (l2 - 0.21738 ** 2))
    return float(no), float(ne)


def ln_tensor(wl, kind="3d"):
    no, ne = sellmeier(wl * 1e6)
    return [no, ne, no] if kind == "3d" else [no, no, ne]


def create_ln(app):
    name = app.addmaterial("(n,k) Material")
    app.setmaterial(name, "name", LN_NAME)
    app.setmaterial(LN_NAME, "Anisotropy", 1)          # 1 = diagonal


def set_ln_index(app, wl, kind="3d"):
    """Constant (non-dispersive) anisotropic LN at wavelength wl."""
    app.switchtolayout()
    n = ln_tensor(wl, kind)
    try:
        app.setmaterial(LN_NAME, "Refractive Index", np.array([n]))
    except Exception:
        for key, val in zip(["Refractive Index", "Refractive Index 2", "Refractive Index 3"], n):
            app.setmaterial(LN_NAME, key, float(val))


def slice_levels(n_slices, w_base, angle_deg=ANGLE_DEG):
    """[(z0, z1, width)] for the staircase ridge, z measured from the BOX top."""
    t = np.tan(np.radians(angle_deg))
    out = []
    for i in range(n_slices):
        z0 = SLAB_T + i * RIDGE_H / n_slices
        z1 = SLAB_T + (i + 1) * RIDGE_H / n_slices
        hc = (i + 0.5) * RIDGE_H / n_slices
        out.append((z0, z1, w_base - 2 * hc / t))
    return out


def top_width(w_base, angle_deg=ANGLE_DEG):
    return w_base - 2 * RIDGE_H / np.tan(np.radians(angle_deg))


def smooth_s(t):
    """0 -> 1 S-curve with zero slope and zero curvature at both ends."""
    return t - np.sin(2 * np.pi * t) / (2 * np.pi)


def arm_centerline(sign, x, length, d_c, d_p, s_len):
    """y(x) of one coupler arm. sign=+1 top, -1 bottom.
    d_c = centre-to-centre spacing in the coupled section, d_p = at the ports."""
    ax = np.abs(x)
    t = np.clip((ax - length / 2) / s_len, 0.0, 1.0)
    return sign * (d_c / 2 + (d_p - d_c) / 2 * smooth_s(t))


def offset_polygon(x, y, width):
    """Closed polygon (N,2) of a path of constant width."""
    dy = np.gradient(y, x)
    s = np.sqrt(1 + dy ** 2)
    nx, ny = -dy / s, 1 / s
    up = np.column_stack([x + nx * width / 2, y + ny * width / 2])
    lo = np.column_stack([x - nx * width / 2, y - ny * width / 2])
    return np.vstack([up, lo[::-1]])