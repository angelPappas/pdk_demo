"""Design rules and checks (DRC) of the TFLN demo PDK.

Rule values live in constants.csv (single source of truth, rows ``drc_*``). This file does two things:

1. ``write_drc_deck()`` writes ``tfln.lydrc``, a KLayout DRC macro that a user runs on any GDS
   (KLayout: Tools > Macros, or ``klayout -b -r tfln.lydrc -rd input=chip.gds -rd report=chip.lyrdb``).
2. ``check()`` runs the same width / space rules from Python (klayout.db, installed with gdsfactory),
   so the PDK cells can be checked in a script or in CI without opening KLayout.

The minimum bend radius is not a layout-polygon rule: it stays in the cross-section
(``radius_min`` in cross_sections.py), where gdsfactory checks it when routing.

Run ``python -m pdk.tfln.drc`` to write the deck and check every PDK cell plus one deliberately bad cell.
"""

from __future__ import annotations

from pathlib import Path
import tempfile

import gdsfactory as gf
import klayout.db as kdb

from .constants import CONSTANTS
from .layers import LAYER

ANGLE = CONSTANTS["drc_angle_limit"]

# (rule name, layer name, kind, limit in um)
RULES = [
    ("WG.W.1", "WG", "width", CONSTANTS["drc_wg_min_width"]),
    ("WG.S.1", "WG", "space", CONSTANTS["drc_wg_min_space"]),
    ("MET1.W.1", "MET1", "width", CONSTANTS["drc_met1_min_width"]),
    ("MET1.S.1", "MET1", "space", CONSTANTS["drc_met1_min_space"]),
]


def write_drc_deck(path: str | Path = "tfln.lydrc") -> Path:
    """Write the rules above as a KLayout DRC macro (.lydrc)."""
    lines = ["# TFLN_DEMO design rules (values from constants.csv)", 'report("TFLN_DEMO DRC", $report)', ""]
    for name in ("WG", "MET1"):
        layer, dtype = getattr(LAYER, name)
        lines.append(f"{name} = input({layer}, {dtype})")
    lines.append("")
    for rule, layer, kind, limit in RULES:
        lines.append(
            f'{layer}.{kind}({limit}.um, angle_limit({ANGLE:g})).output("{rule}", "{layer} {kind} < {limit} um")'
        )
    script = "\n".join(lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<klayout-macro>\n'
        " <description>TFLN_DEMO DRC</description>\n <version/>\n <category>drc</category>\n"
        " <prolog/>\n <epilog/>\n <doc/>\n <autorun>false</autorun>\n <autorun-early>false</autorun-early>\n"
        " <shortcut/>\n <show-in-menu>true</show-in-menu>\n <group-name>drc_scripts</group-name>\n"
        " <menu-path>tools_menu.drc.end</menu-path>\n <interpreter>dsl</interpreter>\n"
        " <dsl-interpreter-name>drc-dsl-xml</dsl-interpreter-name>\n"
        f" <text>{script}\n</text>\n</klayout-macro>\n"
    )
    path = Path(path)
    path.write_text(xml)
    return path


def check(component: gf.Component) -> dict[str, int]:
    """Run the rules on a component; returns {rule name: number of violations}."""
    with tempfile.TemporaryDirectory() as tmp:
        gds = Path(tmp) / "c.gds"
        component.write_gds(gds)
        ly = kdb.Layout()
        ly.read(str(gds))
    top = ly.top_cell()
    dbu = ly.dbu
    result = {}
    for rule, layer, kind, limit in RULES:
        li = ly.find_layer(*getattr(LAYER, layer))
        if li is None:
            result[rule] = 0
            continue
        region = kdb.Region(top.begin_shapes_rec(li))
        region.merge()
        d = round(limit / dbu)
        fn = region.width_check if kind == "width" else region.space_check
        result[rule] = fn(d, False, kdb.Region.Projection, ANGLE).count()
    return result


if __name__ == "__main__":
    from . import pdk  # noqa: F401  (activates the PDK)
    from .cells.directional_coupler import directional_coupler
    from .cells.grating_coupler import grating_coupler
    from .cells.mmi_1x2 import mmi_1x2
    from .cells.racetrack_resonator import racetrack_resonator
    from .cells.taper import taper
    from .cross_sections import wg

    print("wrote", write_drc_deck())
    cells = {
        "directional_coupler": directional_coupler(),
        "taper": taper(),
        "grating_coupler": grating_coupler(),
        "mmi_1x2": mmi_1x2(),
        "racetrack_resonator": racetrack_resonator(),
        "BAD: coupler gap 0.2 um": directional_coupler(gap=0.2),
        "BAD: 0.3 um straight": gf.components.straight(length=20, cross_section=wg(width=0.3)),
    }
    for name, c in cells.items():
        res = check(c)
        print(f"{name:28s}", "clean" if not any(res.values()) else {k: v for k, v in res.items() if v})