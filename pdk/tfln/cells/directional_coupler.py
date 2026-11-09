"""Directional coupler: two parallel arms joined to sine S-bends."""

import gdsfactory as gf

from ..constants import CONSTANTS
from .bend_s import bend_s


@gf.cell
def directional_coupler(
    gap: float = CONSTANTS["dc_gap"],
    length: float = CONSTANTS["dc_length"],
    width: float = CONSTANTS["wg_width"],
    port_separation: float = CONSTANTS["dc_port_separation"],
    s_bend_length: float = CONSTANTS["s_bend_length"],
) -> gf.Component:
    """Symmetric 2x2 directional coupler.

    Args:
        gap: edge-to-edge gap between the ridge BASES in the coupled section (um).
            The ridge sidewalls are sloped, so the gap at the top is larger.
        length: straight coupled length, without the S-bends (um).
        width: waveguide width at the ridge base (um).
        port_separation: centre-to-centre distance between the two arms at the ports (um).
        s_bend_length: length of each S-bend along x (um).

    Ports (anticlockwise from bottom-left): o1, o2 (left, bottom/top), o3, o4 (right, top/bottom).
    """
    pitch = width + gap                       # centre-to-centre in the coupled section
    dy = (port_separation - pitch) / 2        # each arm moves this far out in the S-bend
    if dy <= 0:
        raise ValueError(f"port_separation ({port_separation}) must exceed width + gap ({pitch})")

    c = gf.Component()
    bend = bend_s(dy=dy, length=s_bend_length, width=width)
    xs_width = width

    straight = gf.components.straight(length=length, cross_section=gf.get_cross_section("wg", width=xs_width))

    x0 = s_bend_length                        # coupled section starts after the left S-bends
    arms = {}
    for name, yc in (("top", pitch / 2), ("bot", -pitch / 2)):
        s = c << straight
        s.move((x0, yc))
        arms[name] = s

    # Left side: bends go outwards, to the left of the straights (mirrored in x).
    # Right side: bends go outwards, to the right.
    b_top_r = c << bend
    b_top_r.connect("o1", arms["top"].ports["o2"])
    b_bot_r = c << bend
    b_bot_r.mirror_y()
    b_bot_r.connect("o1", arms["bot"].ports["o2"], allow_type_mismatch=True)

    b_top_l = c << bend
    b_top_l.mirror_x()
    b_top_l.connect("o1", arms["top"].ports["o1"], allow_type_mismatch=True)
    b_bot_l = c << bend
    b_bot_l.mirror_x().mirror_y()
    b_bot_l.connect("o1", arms["bot"].ports["o1"], allow_type_mismatch=True)

    c.add_port("o1", port=b_bot_l.ports["o2"])
    c.add_port("o2", port=b_top_l.ports["o2"])
    c.add_port("o3", port=b_top_r.ports["o2"])
    c.add_port("o4", port=b_bot_r.ports["o2"])
    c.info["gap"] = gap
    c.info["length"] = length
    c.info["width"] = width
    c.info["port_separation"] = port_separation
    c.info["s_bend_length"] = s_bend_length
    return c