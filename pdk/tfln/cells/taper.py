"""Linear lateral taper between the 1.0 um waveguide and a wide section (e.g. a grating)."""

import gdsfactory as gf

from ..constants import CONSTANTS
from ..cross_sections import wg


@gf.cell
def taper(
    length: float = CONSTANTS["taper_length"],
    width1: float = CONSTANTS["wg_width"],
    width2: float = CONSTANTS["taper_width_wide"],
) -> gf.Component:
    """Linear taper. Widths are ridge BASE widths as drawn in the GDS (um).

    Ports: o1 (narrow side, left), o2 (wide side, right).
    """
    c = gf.Component()
    ref = c << gf.components.taper(
        length=length,
        width1=width1,
        width2=width2,
        cross_section=wg,
    )
    c.add_ports(ref.ports)
    c.info["length"] = length
    c.info["width1"] = width1
    c.info["width2"] = width2
    return c