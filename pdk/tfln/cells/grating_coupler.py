"""Grating coupler: linear taper to a wide grating of sloped-sidewall teeth."""

import gdsfactory as gf

from ..constants import CONSTANTS
from ..layers import LAYER
from .taper import taper


@gf.cell
def grating_coupler(
    period: float = CONSTANTS["gc_period"],
    fill: float = CONSTANTS["gc_fill"],
    n_periods: int = int(CONSTANTS["gc_n_periods"]),
    width: float = CONSTANTS["taper_width_wide"],
    taper_length: float = CONSTANTS["taper_length"],
    fiber_angle: float = CONSTANTS["gc_fiber_angle"],
) -> gf.Component:
    """Taper (narrow waveguide -> `width`) followed by `n_periods` teeth.

    Matches the FDTD model: the wide ridge ends at x = 0 (taper end), then each period is a
    trench of (1 - fill) * period followed by a tooth of fill * period (BASE widths, as drawn).

    Ports: o1 = waveguide (left); fiber = marker at the grating centre (info holds the tilt).
    """
    tooth = fill * period
    c = gf.Component()
    tp = c << taper(length=taper_length, width2=width)
    c.add_port("o1", port=tp.ports["o1"])

    x0 = taper_length                              # the grating starts at the end of the taper
    for k in range(n_periods):
        xa = x0 + k * period + (period - tooth)
        xb = xa + tooth
        c.add_polygon([(xa, -width / 2), (xb, -width / 2), (xb, width / 2), (xa, width / 2)],
                      layer=LAYER.WG)

    x_c = x0 + n_periods * period / 2
    c.add_port(name="fiber", center=(x_c, 0), width=10.4, orientation=90,
               layer=LAYER.PORT, port_type="placement")
    c.info["period"] = period
    c.info["fill"] = fill
    c.info["n_periods"] = n_periods
    c.info["fiber_angle"] = fiber_angle
    c.info["grating_length"] = n_periods * period
    return c