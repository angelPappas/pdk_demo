import gdsfactory as gf

from .layers import LAYER
from .cross_sections import wg


TFLN_PDK = gf.Pdk(
    name="TFLN_DEMO",
    version="0.1.0",
    layers=LAYER,
    cross_sections={
        "wg": wg,
    },
)

TFLN_PDK.activate()