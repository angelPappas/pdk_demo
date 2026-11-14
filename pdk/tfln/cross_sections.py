import gdsfactory as gf

from .constants import CONSTANTS
from .layers import LAYER


def wg(
    width: float = CONSTANTS["wg_width"],
    radius: float = CONSTANTS["wg_radius"],
) -> gf.CrossSection:
    return gf.cross_section.cross_section(
        width=width,
        layer=LAYER.WG,
        radius=radius,
        radius_min=radius,
    )