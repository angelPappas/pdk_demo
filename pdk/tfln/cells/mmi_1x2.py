"""1x2 multimode interference splitter: access tapers + rectangular multimode section."""

import gdsfactory as gf

from ..constants import CONSTANTS
from ..cross_sections import wg
from ..layers import LAYER
from .taper import taper


@gf.cell
def mmi_1x2(
    width: float = CONSTANTS["mmi_width"],
    length: float = CONSTANTS["mmi_length"],
    taper_width: float = CONSTANTS["mmi_taper_width"],
    taper_length: float = CONSTANTS["mmi_taper_length"],
    port_offset: float = CONSTANTS["mmi_port_offset"],
    wg_width: float = CONSTANTS["wg_width"],
) -> gf.Component:
    """Symmetric 1x2 MMI. All widths are ridge BASE widths as drawn in the GDS (um).

    The multimode section runs from x = 0 to x = length, centred on y = 0. The input taper
    ends at x = 0 on the axis; the two output tapers start at x = length at y = +-port_offset.

    Ports (anticlockwise from the left, same convention as the directional coupler):
        o1 input (left), o2 bottom output (right), o3 top output (right).
    """
    if port_offset + taper_width / 2 > width / 2:
        raise ValueError("output tapers must fit inside the multimode section")
    if 2 * port_offset - taper_width <= 0:
        raise ValueError("the two output tapers would overlap: reduce taper_width or raise port_offset")

    c = gf.Component()
    body = c << gf.components.rectangle(size=(length, width), layer=LAYER.WG, centered=False)
    body.dmove((0, -width / 2))

    t_in = c << taper(length=taper_length, width1=wg_width, width2=taper_width)
    t_in.dmove((-taper_length, 0))
    outs = {}
    for sign, name in ((-1, "bot"), (1, "top")):
        t = c << taper(length=taper_length, width1=wg_width, width2=taper_width)
        t.dmirror_x()
        t.dmove((length + taper_length, sign * port_offset))
        outs[name] = t
    t_bot, t_top = outs["bot"], outs["top"]

    c.add_port("o1", port=t_in.ports["o1"])
    c.add_port("o2", port=t_bot.ports["o1"])
    c.add_port("o3", port=t_top.ports["o1"])
    c.info["width"] = width
    c.info["length"] = length
    c.info["port_offset"] = port_offset
    return c