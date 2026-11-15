"""Test die for the racetrack-resonator work: waveguides, bends, our directional coupler and the racetrack.

Measurement scheme: ONE 4-fibre array (pitch `gc_pitch` = 127 um), all gratings on the left of each structure.
  fibre 2 = laser input;  fibre 1 (above) and fibre 3 (below) = photodetectors.
Every structure therefore has its input grating at y = 0 and its output grating(s) at y = -pitch (fibre 3)
and, for the coupler, also at y = +pitch (fibre 1).
  * WAVEGUIDE  loop-backs of growing length (cutback).
  * BENDS      loop-backs of the SAME total length with a growing number of 180-degree turns.
  * DC         our racetrack coupler and a sweep of length and gap: through -> fibre 3, cross -> fibre 1.
  * RACETRACK  the resonator for the same coupler variants, plus a longer ring: bus output -> fibre 3.
Each structure is a `unit` with its own grating column. The three used fibre positions of a unit are kept free of
other gratings (clearance window), so any unit can be measured on its own.
Run:  python -m pdk.tfln.cells.test_die_racetrack     (from the repo root) -> gds/tfln_racetrack_die.gds
"""

import math
from pathlib import Path

import gdsfactory as gf

from ..constants import CONSTANTS
from ..cross_sections import wg
from ..layers import LAYER
from .directional_coupler import directional_coupler
from .grating_coupler import grating_coupler
from .racetrack_resonator import racetrack_resonator

R = CONSTANTS["bend_radius"]
PITCH = CONSTANTS["gc_pitch"]
DC_GAP = CONSTANTS["racetrack_dc_gap"]
DC_LEN = CONSTANTS["racetrack_dc_length"]
DC_SBEND = CONSTANTS["racetrack_dc_s_bend_length"]
DC_LEAD = CONSTANTS["racetrack_dc_lead_length"]
FEED = 60.0                       # straight between a grating and the structure


# ------------------------------------------------------------------ helpers
def _straight(length: float) -> gf.Component:
    return gf.components.straight(length=length, cross_section=wg)


def _bend(sign: int) -> gf.Component:
    """Circular 90-degree bend: +1 turns left (counter-clockwise), -1 turns right."""
    return gf.components.bend_circular(radius=R, angle=90 * sign, cross_section=wg(radius=R))


def _chain(parts) -> gf.Component:
    """Connect components o1 -> o2 in order; expose the two ends as o1 / o2."""
    c = gf.Component()
    prev = first = None
    for p in parts:
        ref = c << p
        if prev is not None:
            ref.connect("o1", prev.ports["o2"], allow_type_mismatch=True)
        else:
            first = ref
        prev = ref
    c.add_port("o1", port=first.ports["o1"])
    c.add_port("o2", port=prev.ports["o2"])
    return c


def _label(text: str, size: float = 20.0) -> gf.Component:
    return gf.components.text(text=text, size=size, layer=LAYER.TEXT)


def _u_back(sign: int, vertical: float, back: float) -> list:
    """From a port heading +x: U-turn (sign -1 = down, +1 = up), then a straight heading -x of length `back`."""
    return [_bend(sign), _straight(vertical), _bend(sign), _straight(back)]


# ----------------------------------------------------------- the structures
def loopback(n_turns: int, total_length: float) -> gf.Component:
    """Input o1 at the origin, output o2 at (0, -PITCH). Top arm: straight, `n_turns` (even) 180-degree
    turns going up, then a final U-turn down to the output. Total path length = total_length.

    Bend count = 2 * n_turns + 2 (the final U-turn is in every structure).
    """
    assert n_turns % 2 == 0
    v = PITCH + n_turns * 2 * R - 2 * R                     # vertical leg of the final U-turn
    arcs = (n_turns + 1) * math.pi * R                      # n_turns serpentine turns + the final U-turn
    straight = (total_length - arcs - v) / (n_turns + 2)    # same length for every straight segment
    if straight < 10:
        raise ValueError(f"total_length {total_length} too short for {n_turns} turns")
    parts = [_straight(straight)]
    for i in range(n_turns):
        s = 1 if i % 2 == 0 else -1
        parts += [_bend(s), _bend(s), _straight(straight)]
    parts += _u_back(-1, v, straight)
    return _chain(parts)


def _dc_structure(length: float, gap: float) -> gf.Component:
    """Input o1 at the origin, through output o2 at (0, -PITCH) and cross output o3 at (0, +PITCH)."""
    c = gf.Component()
    dc = c << directional_coupler(gap=gap, length=length, s_bend_length=DC_SBEND)
    dc.dmove((FEED + DC_LEAD, -dc.ports["o1"].center[1]))            # lower-left input at y = 0
    leads = {}
    for name in ("o1", "o3", "o4"):                               # o2 (upper left) is left unconnected
        s = c << _straight(DC_LEAD)
        s.connect("o1", dc.ports[name], allow_type_mismatch=True)
        leads[name] = s
    feed = c << _straight(FEED)
    feed.connect("o2", leads["o1"].ports["o2"], allow_type_mismatch=True)
    x_end = leads["o3"].ports["o2"].center[0]
    # through (lower right, y = 0) goes down to y = -PITCH; cross (upper right) goes up to y = +PITCH
    y_cross = leads["o4"].ports["o2"].center[1]
    thr = c << _chain(_u_back(-1, PITCH - 2 * R, x_end))
    thr.dmove((x_end, 0))
    crs = c << _chain(_u_back(+1, PITCH - y_cross - 2 * R, x_end))
    crs.dmove((x_end, y_cross))
    c.add_port("o1", port=feed.ports["o1"])
    c.add_port("o2", port=thr.ports["o2"])
    c.add_port("o3", port=crs.ports["o2"])
    return c


def _ring_structure(gap: float, coupling_length: float, lead_length: float = DC_LEAD) -> gf.Component:
    """Input o1 at the origin; bus output goes down to o2 at (0, -PITCH)."""
    c = gf.Component()
    ring = c << racetrack_resonator(gap=gap, coupling_length=coupling_length, s_bend_length=DC_SBEND,
                                    lead_length=lead_length)
    ring.dmove((FEED - ring.ports["o1"].center[0], -ring.ports["o1"].center[1]))
    feed = c << _straight(FEED)
    feed.connect("o2", ring.ports["o1"], allow_type_mismatch=True)
    x_out = ring.ports["o2"].center[0]
    back = c << _chain(_u_back(-1, PITCH - 2 * R, x_out))
    back.dmove((x_out, 0))
    c.add_port("o1", port=feed.ports["o1"])
    c.add_port("o2", port=back.ports["o2"])
    return c


# ------------------------------------------------------------------- units
def make_unit(gc, name: str, structure: gf.Component, outputs=("o2",)) -> gf.Component:
    """Structure + gratings on its ports + label. Local origin: the input grating's o1 (at (0, 0)).
    The bounding box handed to the floorplan includes the clearance window of the four fibres."""
    u = gf.Component()
    s = u << structure
    for pn in ("o1",) + tuple(outputs):
        g = u << gc
        g.connect("o1", s.ports[pn], allow_type_mismatch=True)
    lab = u << _label(name)
    lab.dmove((FEED + 40, 14))
    bb = u.dbbox()
    gc_len = gc.dxsize
    # clearance window: the 3 used fibre positions (+127, 0, -127), +/- 25 um (fibre 4 is unused)
    y_lo, y_hi = min(bb.bottom, -PITCH - 25), max(bb.top, PITCH + 25)
    u.info["box"] = (float(bb.left), float(y_lo), float(bb.right), float(y_hi))
    u.info["name"] = name
    return u


# ---------------------------------------------------------------- the die
@gf.cell
def racetrack_die(margin: float = 100.0, gap: float = 40.0, total: float = 3500.0) -> gf.Component:
    """Test die (um), rows listed from the bottom:
      1  waveguide 0.5 mm loop, then the bend chains (6, 14, 22 bends, 22 rightmost)
      2  waveguide 3.5 mm loop, waveguide 0.3 mm loop (reference)
      3  racetrack L3 (design), DC L1, DC L2, DC L5
      4+ everything else (waveguide 1.5 mm, remaining racetracks and DCs), wrapped to the die width.
    The die is as wide as the widest of rows 1-3; the units of a row are spread evenly over that width."""
    die = gf.Component()
    gc = grating_coupler()
    U = {}

    def add(key, name, structure, outputs=("o2",)):
        U[key] = make_unit(gc, name, structure, outputs)

    for L in (total, 1500.0, 500.0, 300.0):
        add(("wg", L), f"WG LOOP {L / 1000:g} mm" + (" (REF)" if L == 300 else ""), loopback(0, L))
    for n in (2, 6, 10):
        add(("bend", n), f"BENDS {2 * n + 2} ({total / 1000:g} mm)", loopback(n, total))
    rings = [(DC_GAP, 2.0, DC_LEAD, f"L2"), (DC_GAP, DC_LEN, DC_LEAD, f"L{DC_LEN:g} (design)"),
             (DC_GAP, 4.0, DC_LEAD, "L4"), (0.35, DC_LEN, DC_LEAD, f"g0.35 L{DC_LEN:g}"),
             (0.45, DC_LEN, DC_LEAD, f"g0.45 L{DC_LEN:g}"), (DC_GAP, DC_LEN, 103.0, f"L{DC_LEN:g} LONG")]
    for g_, L_, lead_, tag in rings:
        label = f"RING {tag}" if tag.startswith("g0") else f"RING g{g_:.2f} {tag}"
        add(("ring", g_, L_, lead_), label, _ring_structure(g_, L_, lead_))
    for g_, L_ in [(DC_GAP, 1.0), (DC_GAP, 2.0), (DC_GAP, DC_LEN), (DC_GAP, 4.0), (DC_GAP, 5.0), (0.35, DC_LEN), (0.45, DC_LEN)]:
        tag = " (design)" if (g_, L_) == (DC_GAP, DC_LEN) else ""
        add(("dc", g_, L_), f"DC g{g_:.2f} L{L_:g}{tag}", _dc_structure(L_, g_), ("o2", "o3"))

    rows = [
        [("wg", 500.0), ("bend", 2), ("bend", 6), ("bend", 10)],
        [("ring", DC_GAP, DC_LEN, DC_LEAD), ("dc", DC_GAP, 1.0), ("dc", DC_GAP, 2.0), ("dc", DC_GAP, 5.0)],
    ]
    # two directional couplers sit in the free space above the short units of the bottom row
    on_top = {("wg", 500.0): ("dc", 0.35, DC_LEN), ("bend", 2): ("dc", 0.45, DC_LEN)}
    longest = ("wg", total)           # above the two DCs, spanning the first columns of the bottom row
    short = ("wg", 300.0)             # reference loop: third unit of the DC row, right of the 0.45 gap DC
    used = {k for r in rows for k in r} | set(on_top.values()) | {longest, short}
    rest = [k for k in U if k not in used]                     # insertion order: wg, rings, dcs

    def row_w(keys):
        return sum(U[k].info["box"][2] - U[k].info["box"][0] for k in keys) + gap * (len(keys) - 1)

    inner = max(row_w(r) for r in rows) + 60.0                # a little air so stacked units fit their columns
    cur = []
    for k in rest:                                             # wrap the remaining units to the same width
        if cur and row_w(cur + [k]) > inner:
            rows.append(cur)
            cur = []
        cur.append(k)
    if cur:
        rows.append(cur)

    y = margin
    extra = 140.0                     # extra width after column 1 of the bottom row, so the short loop clears column 2
    inner += extra
    names, pos = [], []
    def box_hw(k):
        b = U[k].info["box"]
        return b[3] - b[1], b[2] - b[0]

    for ri, keys in enumerate(rows):
        h = max(box_hw(k)[0] + (gap + box_hw(on_top[k])[0] if k in on_top else 0) for k in keys)
        if ri == 0:                    # the longest loop goes above the first two stacked units
            h = max(h, box_hw(keys[0])[0] + gap + box_hw(on_top[keys[0]])[0] + gap + box_hw(longest)[0],
                    box_hw(keys[1])[0] + gap + box_hw(on_top[keys[1]])[0] + gap + box_hw(longest)[0])
        free = inner - sum(U[k].info["box"][2] - U[k].info["box"][0] for k in keys) - (extra if ri == 0 else 0.0)
        step = free / (len(keys) - 1) if len(keys) > 1 else 0.0     # even spacing across the die width
        x = margin
        for k in keys:
            u = U[k]
            x0, y0, x1, y1 = u.info["box"]
            ref = die << u
            ref.dmove((x - x0, y - y0))
            names.append(u.info["name"])
            pos.append((float(x - x0), float(y - y0)))       # position of the input grating's o1
            if k in on_top:                                  # unit stacked right above this one
                t = U[on_top[k]]
                tx0, ty0, tx1, ty1 = t.info["box"]
                assert tx1 - tx0 <= (x1 - x0) + step, "stacked unit wider than its column"
                ref = die << t
                ref.dmove((x - tx0, y + (y1 - y0) + gap - ty0))
                names.append(t.info["name"])
                pos.append((float(x - tx0), float(y + (y1 - y0) + gap - ty0)))
                if k == ("bend", 2):                         # short loop right of that DC, same height, right next to it
                    sb = U[short].info["box"]
                    sx = x + (tx1 - tx0) + gap - sb[0]
                    sy = y + (y1 - y0) + gap - sb[1]
                    assert sx + sb[0] >= x + (tx1 - tx0) + gap - 1e-6, "short loop overlaps the stacked DC"
                    ref = die << U[short]
                    ref.dmove((sx, sy))
                    names.append(U[short].info["name"])
                    pos.append((float(sx), float(sy)))
            if ri == 0 and k == keys[0]:
                x_first = x - x0
            if ri == 0 and k == keys[1]:                     # longest loop above the DCs of columns 1 and 2
                tops = [y + (b[3] - b[1]) + gap + (U[on_top[kk]].info["box"][3] - U[on_top[kk]].info["box"][1])
                        for kk, b in ((keys[0], U[keys[0]].info["box"]), (keys[1], U[keys[1]].info["box"]))]
                lb = U[longest].info["box"]
                ref = die << U[longest]
                ly = max(tops) + gap - lb[1]
                ref.dmove((margin - lb[0], ly))
                names.append(U[longest].info["name"])
                pos.append((float(margin - lb[0]), float(ly)))
            x += (x1 - x0) + step + (extra if ri == 0 and k == keys[1] else 0.0)
        y += h + gap
    width, height = inner + 2 * margin, y - gap + margin
    die << gf.components.rectangle(size=(width, height), layer=LAYER.FLOORPLAN)
    die.info["row_names"] = names
    die.info["input_grating_xy"] = pos
    die.info["width"], die.info["height"] = width, height
    return die


if __name__ == "__main__":
    from .. import pdk  # noqa: F401  (activates the PDK)
    out = Path("gds")
    out.mkdir(exist_ok=True)
    d = racetrack_die()
    d.write_gds(out / "tfln_racetrack_die.gds")
    print("wrote", out / "tfln_racetrack_die.gds", f"({d.dxsize:.0f} x {d.dysize:.0f} um, {len(d.info['row_names'])} structures)")