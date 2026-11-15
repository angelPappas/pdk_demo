"""All-pass racetrack resonator built around the symmetric directional-coupler cell."""

import gdsfactory as gf

from ..constants import CONSTANTS
from ..cross_sections import wg
from .directional_coupler import directional_coupler


def _straight(length: float) -> gf.Component:
    return gf.components.straight(length=length, cross_section=wg)


def _bend(radius: float) -> gf.Component:
    """Circular 90-degree bend (counter-clockwise) with the default PDK cross-section."""
    return gf.components.bend_circular(radius=radius, angle=90, cross_section=wg(radius=radius))


@gf.cell
def racetrack_resonator(
    gap: float = CONSTANTS["racetrack_dc_gap"],
    coupling_length: float = CONSTANTS["racetrack_dc_length"],
    s_bend_length: float = CONSTANTS["racetrack_dc_s_bend_length"],
    lead_length: float = CONSTANTS["racetrack_dc_lead_length"],
    radius: float = CONSTANTS["bend_radius"],
    port_separation: float = CONSTANTS["dc_port_separation"],
) -> gf.Component:
    """Single-bus racetrack: the symmetric DC, four 90-degree bends and one straight.

    The coupler cell is the one simulated in Tidy3D (dc_tidy3d/): coupled straight `coupling_length`
    at `gap`, sine S-bends of `s_bend_length`, and `lead_length` straights at all four ports; the
    port planes of the simulation are the outer ends of those leads. The lower arm is the bus, the
    upper arm is the ring. The ring leaves the upper-right lead, makes a U-turn upward (two bends),
    runs back as a straight of the same length as the whole coupler cell (2 * x_end), makes a second
    U-turn and re-enters the upper-left lead.

    Ports: o1 = bus input (left), o2 = bus output (right), both at the outer ends of the bus leads.

    The ring ports are found by POSITION (upper-left / upper-right), not by name, so this cell does
    not depend on the o3 / o4 numbering of `directional_coupler`.
    """
    c = gf.Component()
    dc = c << directional_coupler(gap=gap, length=coupling_length, s_bend_length=s_bend_length,
                                  port_separation=port_separation)
    ports = sorted(dc.ports, key=lambda p: (p.dcenter[0], p.dcenter[1]))     # left-bottom, left-top, right-bottom, right-top
    p_ll, p_ul, p_lr, p_ur = ports

    def lead(port, name):
        s = c << _straight(lead_length)
        s.connect("o1", port, allow_type_mismatch=True)
        return s

    l_ll, l_ul, l_lr, l_ur = lead(p_ll, "ll"), lead(p_ul, "ul"), lead(p_lr, "lr"), lead(p_ur, "ur")
    cell_length = coupling_length + 2 * s_bend_length + 2 * lead_length          # = 2 * x_end

    # ring: upper-right lead -> bend, bend -> straight -> bend, bend -> upper-left lead
    prev = l_ur
    for part in (_bend(radius), _bend(radius), _straight(cell_length),
                 _bend(radius), _bend(radius)):
        ref = c << part
        ref.connect("o1", prev.ports["o2"], allow_type_mismatch=True)
        prev = ref
    # the last bend must end exactly on the upper-left lead (loop closure)
    dx = prev.ports["o2"].dcenter[0] - l_ul.ports["o2"].dcenter[0]
    dy = prev.ports["o2"].dcenter[1] - l_ul.ports["o2"].dcenter[1]
    if abs(dx) > 1e-3 or abs(dy) > 1e-3:
        raise ValueError(f"racetrack does not close: gap of ({dx:.4f}, {dy:.4f}) um")

    c.add_port("o1", port=l_ll.ports["o2"])
    c.add_port("o2", port=l_lr.ports["o2"])
    c.info["gap"] = gap
    c.info["coupling_length"] = coupling_length
    c.info["s_bend_length"] = s_bend_length
    c.info["lead_length"] = lead_length
    c.info["radius"] = radius
    c.info["cell_length"] = cell_length
    c.info["ring_length"] = 2 * cell_length + 2 * 3.141592653589793 * radius     # 2 straights + 4 quarter-circles
    return c