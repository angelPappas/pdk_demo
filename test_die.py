"""Test die: every PDK building block in a structure that can be measured with a fibre array.

All structures are 2-port (or 1-in / 2-out) and are fed through grating couplers, so a single
fibre-array scan characterises the die. Placeholders (MET1 boxes) mark the EO / thermal / RF
structures that are not yet part of the PDK.
"""

import gdsfactory as gf
import numpy as np

from ..constants import CONSTANTS
from ..cross_sections import wg
from ..layers import LAYER
from .bend_90 import bend_90
from .bend_s import bend_s
from .directional_coupler import directional_coupler
from .grating_coupler import grating_coupler
from .taper import taper

R = CONSTANTS["bend_radius"]
GC_PITCH = CONSTANTS["gc_pitch"]


def _straight(length: float) -> gf.Component:
    return gf.components.straight(length=length, cross_section=wg)


def _chain(c: gf.Component, parts) -> None:
    """Connect components o1 -> o2 in order and expose the ends as o1 / o2."""
    prev = None
    for p in parts:
        ref = c << p
        if prev is not None:
            ref.connect("o1", prev.ports["o2"], allow_type_mismatch=True)
        prev = ref
        if "first" not in locals():
            first = ref
    c.add_port("o1", port=first.ports["o1"])
    c.add_port("o2", port=prev.ports["o2"])


# ---------------------------------------------------------------- 2-port DUTs
@gf.cell
def dut_straight(length: float = 500.0) -> gf.Component:
    c = gf.Component()
    _chain(c, [_straight(length)])
    return c


def _uturn(sign: int, straight: float = 0.0) -> list:
    """180-degree turn from two bend_90 (+1 = counter-clockwise, -1 = clockwise), straight in between."""
    mid = [_straight(straight)] if straight > 0 else []
    return [bend_90(angle=90 * sign)] + mid + [bend_90(angle=90 * sign)]


@gf.cell
def dut_u_bends(n: int = 4, length: float = 300.0) -> gf.Component:
    """Serpentine of `n` (even) 180-degree turns with a return line, in/out at the same y."""
    assert n % 2 == 0
    parts = [_straight(length)]
    for i in range(n):
        parts += _uturn(1 if i % 2 == 0 else -1) + [_straight(length)]
    # n even -> heading +x at y = n*2R; come back down on the right
    parts += [_straight(R + 40)]
    parts += [bend_90(angle=-90)]
    parts += [_straight((n - 1) * 2 * R)]
    parts += [bend_90(angle=90)]
    c = gf.Component()
    _chain(c, parts)
    return c


@gf.cell
def dut_s_bends(n_pairs: int = 5, dy: float = 25.0, length: float = 100.0) -> gf.Component:
    """Chain of n up/down S-bend pairs (no net lateral shift)."""
    parts = []
    for _ in range(n_pairs):
        parts += [bend_s(dy=dy, length=length), bend_s(dy=-dy, length=length)]
    c = gf.Component()
    _chain(c, parts)
    return c


@gf.cell
def dut_taper_chain(n_pairs: int = 1) -> gf.Component:
    """n back-to-back 1 -> 12 -> 1 um taper pairs."""
    t = taper()
    parts = []
    for _ in range(n_pairs):
        r = gf.Component()
        a = r << t
        b = r << t
        b.dmirror_x()
        b.connect("o2", a.ports["o2"], allow_type_mismatch=True)
        r.add_port("o1", port=a.ports["o1"])
        r.add_port("o2", port=b.ports["o1"])
        parts.append(r)
    c = gf.Component()
    _chain(c, parts)
    return c


@gf.cell
def dut_ring(gap: float = 0.4, radius: float = R, length_x: float = 20.0) -> gf.Component:
    """All-pass racetrack: bus waveguide + racetrack made of four bend_90 and two straights."""
    c = gf.Component()
    pitch = 1.0 + gap
    bus = c << _straight(2 * radius + length_x + 200)
    track = gf.Component()
    prev = None
    for part in [_straight(length_x)] + _uturn(1) + [_straight(length_x)] + _uturn(1):
        ref = track << part
        if prev is not None:
            ref.connect("o1", prev.ports["o2"], allow_type_mismatch=True)
        prev = ref
    tr = c << track
    tr.dmove((100 + radius, pitch))
    c.add_port("o1", port=bus.ports["o1"])
    c.add_port("o2", port=bus.ports["o2"])
    c.info["gap"] = gap
    c.info["radius"] = radius
    return c


# ---------------------------------------------------------- multi-port DUTs
@gf.cell
def dut_dc(length: float = CONSTANTS["dc_length"], gap: float = CONSTANTS["dc_gap"]) -> gf.Component:
    """Directional coupler, 1 input, both outputs spread to the fibre-array pitch.

    Ports: o1 input (left), o2 = through/bar output, o3 = cross output (both right).
    """
    c = gf.Component()
    dc = c << directional_coupler(length=length, gap=gap)
    dc.dmove((0, 2))  # o1 (bottom-left) at y = 0
    dy = GC_PITCH / 2 - 2
    bt = c << bend_s(dy=dy, length=300)
    bb = c << bend_s(dy=-dy, length=300)
    bb.connect("o1", dc.ports["o4"], allow_type_mismatch=True)
    bt.connect("o1", dc.ports["o3"], allow_type_mismatch=True)
    stub = c << _straight(20)
    stub.connect("o1", dc.ports["o2"], allow_type_mismatch=True)
    c.add_port("o1", port=dc.ports["o1"])
    c.add_port("o2", port=bb.ports["o2"])
    c.add_port("o3", port=bt.ports["o2"])
    c.info["gap"] = gap
    c.info["length"] = length
    return c


@gf.cell
def dut_mzi(delta_length: float = 200.0, dc_length: float = CONSTANTS["dc_length"]) -> gf.Component:
    """Unbalanced MZI built from two PDK couplers. The long arm rises over a U-detour.

    delta_length is the path-length difference (um). Ports: o1 input, o2/o3 outputs.
    """
    c = gf.Component()
    dc_in = c << directional_coupler(length=dc_length)
    dc_in.dmove((0, 2))
    dc_out = c << directional_coupler(length=dc_length)
    # reference arm: straight; long arm: up 90, straight, down 90 plus extra length
    arm_x = 2 * R + 40
    ref_arm = c << _straight(arm_x + 2 * R)   # same horizontal extent as the long arm
    ref_arm.connect("o1", dc_in.ports["o4"], allow_type_mismatch=True)
    # long arm
    up = c << bend_90(angle=90)
    up.connect("o1", dc_in.ports["o3"], allow_type_mismatch=True)
    # path difference = (2*pi - 4) * R + 2 * v  ->  solve for the vertical leg v
    v = (delta_length - (2 * np.pi - 4) * R) / 2
    if v < 0:
        raise ValueError(f"delta_length must be >= {(2 * np.pi - 4) * R:.0f} um for R={R} um")
    leg1 = c << _straight(max(v, 0.01))
    leg1.connect("o1", up.ports["o2"], allow_type_mismatch=True)
    top = c << bend_90(angle=-90)
    top.connect("o1", leg1.ports["o2"], allow_type_mismatch=True)
    mid = c << _straight(arm_x - 2 * R)
    mid.connect("o1", top.ports["o2"], allow_type_mismatch=True)
    top2 = c << bend_90(angle=-90)
    top2.connect("o1", mid.ports["o2"], allow_type_mismatch=True)
    leg2 = c << _straight(max(v, 0.01))
    leg2.connect("o1", top2.ports["o2"], allow_type_mismatch=True)
    down = c << bend_90(angle=90)
    down.connect("o1", leg2.ports["o2"], allow_type_mismatch=True)
    # output coupler: attach so that its o2 (top-left) meets the long arm, o1 the reference arm
    dc_out.connect("o2", down.ports["o2"], allow_type_mismatch=True)
    dy = GC_PITCH / 2 - 2
    bt = c << bend_s(dy=dy, length=300)
    bb = c << bend_s(dy=-dy, length=300)
    bb.connect("o1", dc_out.ports["o4"], allow_type_mismatch=True)
    bt.connect("o1", dc_out.ports["o3"], allow_type_mismatch=True)
    c.add_port("o1", port=dc_in.ports["o1"])
    c.add_port("o2", port=bb.ports["o2"])
    c.add_port("o3", port=bt.ports["o2"])
    c.info["delta_length"] = delta_length
    return c


def _placeholder(label: str, length: float = 1000.0) -> gf.Component:
    """Waveguide with a MET1 box on top: stands for an EO / thermal / RF structure not yet in the PDK."""
    c = gf.Component()
    w = c << _straight(length)
    box = c << gf.components.rectangle(size=(length * 0.6, 60), layer=LAYER.MET1)
    box.dmove((length * 0.2, -30))
    t = c << gf.components.text(text=label, size=25, layer=LAYER.TEXT)
    t.dmove((length * 0.2 + 10, 40))
    c.add_port("o1", port=w.ports["o1"])
    c.add_port("o2", port=w.ports["o2"])
    return c


# ----------------------------------------------------------------- the die
def _label(text: str, size: float = 18.0) -> gf.Component:
    return gf.components.text(text=text, size=size, layer=LAYER.TEXT)


@gf.cell
def test_die(width: float = 8000.0, height: float = 6600.0, margin: float = 120.0) -> gf.Component:
    """Test die floorplan (um). Left GC: grating toward the left edge; right GC: toward the right edge."""
    die = gf.Component()
    gc = grating_coupler()
    gc_len = gc.dxsize
    x_left = margin + gc_len + 20      # o1 of the left grating couplers
    x_right = width - margin - gc_len - 20
    span = x_right - x_left

    rows = [
        # (label, dut)
        ("REF GC-GC", dut_straight(10.0)),
        ("STRAIGHT 0.5 mm", dut_straight(500.0)),
        ("STRAIGHT 2.5 mm", dut_straight(2500.0)),
        ("STRAIGHT 5 mm", dut_straight(5000.0)),
        ("TAPER x1 (200 um)", dut_taper_chain(1)),
        ("TAPER x4", dut_taper_chain(4)),
        ("S-BEND x2 (dy25 L100)", dut_s_bends(1)),
        ("S-BEND x10", dut_s_bends(5)),
        ("S-BEND x20", dut_s_bends(10)),
        ("U-BEND 180 x2 R100", dut_u_bends(2)),
        ("U-BEND 180 x4", dut_u_bends(4)),
        ("U-BEND 180 x8", dut_u_bends(8)),
        ("DC L10 g0.4", dut_dc(length=10)),
        ("DC L16 g0.4", dut_dc(length=16)),
        ("DC L21 g0.4 (design)", dut_dc()),
        ("DC L26 g0.4", dut_dc(length=26)),
        ("DC L21 g0.3", dut_dc(gap=0.3)),
        ("DC L21 g0.5", dut_dc(gap=0.5)),
        ("MZI dL=300", dut_mzi(300)),
        ("MZI dL=600", dut_mzi(600)),
        ("RING g0.3 R100", dut_ring(gap=0.3)),
        ("RING g0.4", dut_ring(gap=0.4)),
        ("RING g0.5", dut_ring(gap=0.5)),
        ("EO MZM (TBD)", _placeholder("EO MZM - TBD")),
        ("THERMAL PS (TBD)", _placeholder("HEATER - TBD")),
        ("RF LINE (TBD)", _placeholder("RF TL - TBD")),
    ]

    y = margin + 100
    row_info = []
    gap_rows = 40
    for name, dut in rows:
        ports = {p.name: p for p in dut.ports}
        o1 = ports["o1"]
        x0 = x_left + (span - dut.dxsize) / 2 - dut.dxmin
        ref = die << dut
        ref.dmove((x0 - 0, y - o1.center[1]))
        # per-port grating couplers and feeder straights
        for p in ref.ports:
            px, py = p.center
            if abs(p.orientation - 180) < 1:
                g = die << gc
                g.drotate(180)
                g.dmove((x_left, py))
                L = px - x_left
            else:
                g = die << gc
                g.dmove((x_right, py))
                L = x_right - px
            if L > 0.01:
                s = die << _straight(L)
                s.dmove((min(px, x_left if abs(p.orientation - 180) < 1 else x_right), py))
        lab = die << _label(name)
        lab.dmove((x_left + 30, y + 14))
        ys = [p.center[1] for p in ref.ports]
        bb = ref.dbbox()
        row_info.append((name, float(min(ys) - 10), float(max(max(ys), bb.top) + 10)))
        y = max(max(ys) + 60, bb.top) + gap_rows + 20

    outline = gf.components.rectangle(size=(width, max(height, y + margin)), layer=LAYER.FLOORPLAN)
    die << outline
    die.info["row_names"] = [r[0] for r in row_info]
    die.info["row_y0"] = [r[1] for r in row_info]
    die.info["row_y1"] = [r[2] for r in row_info]
    die.info["rows"] = len(rows)
    die.info["height_used"] = y
    return die