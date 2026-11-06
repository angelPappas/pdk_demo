import gdsfactory as gf

from .layers import LAYER


def wg(
    width: float = 1.0,
    radius: float = 50.0,
) -> gf.CrossSection:
    return gf.cross_section.cross_section(
        width=width,
        layer=LAYER.WG,
        radius=radius,
    )