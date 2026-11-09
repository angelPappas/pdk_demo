"""S-bend with a smooth (sine-integral) lateral profile."""

import gdsfactory as gf
import numpy as np

from ..constants import CONSTANTS
from ..cross_sections import wg


@gf.cell
def bend_s(
    dy: float = 1.3,
    length: float = CONSTANTS["s_bend_length"],
    width: float = CONSTANTS["wg_width"],
    npoints: int = 201,
) -> gf.Component:
    """S-bend that shifts the waveguide laterally by `dy` over `length`.

    The lateral profile is y(t) = dy * (t - sin(2*pi*t) / (2*pi)), t = x / length.
    It has zero slope and zero curvature at both ends (no kink where it meets a
    straight), and it is the same profile used in the Lumerical FDTD coupler model.

    Args:
        dy: lateral offset between input and output centrelines (um).
            Positive shifts up (+y).
        length: extent along the propagation direction x (um).
        width: waveguide width at the ridge base, as drawn in the GDS (um).
        npoints: number of points on the centreline.
    """
    t = np.linspace(0.0, 1.0, npoints)
    x = length * t
    y = dy * (t - np.sin(2 * np.pi * t) / (2 * np.pi))
    path = gf.Path(np.column_stack([x, y]))

    c = gf.Component()
    ref = c << path.extrude(wg(width=width))
    # The finite-difference end tangents are ~1e-4 deg off axis, which puts instances
    # off-grid. The ideal profile is exactly horizontal at both ends, so set that.
    xs = wg(width=width)
    c.add_port(name="o1", center=(0, 0), width=width, orientation=180, cross_section=xs)
    c.add_port(name="o2", center=(length, dy), width=width, orientation=0, cross_section=xs)
    c.info["dy"] = dy
    c.info["length"] = length
    c.info["width"] = width
    # peak curvature of the profile: dy * 2*pi / length**2  ->  minimum radius
    c.info["min_radius"] = float(length**2 / (2 * np.pi * abs(dy))) if dy else float("inf")
    return c