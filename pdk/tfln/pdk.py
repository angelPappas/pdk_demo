import gdsfactory as gf

from .layers import LAYER
from .layer_views import LAYER_VIEWS
from .cross_sections import wg
from .cells.bend_s import bend_s
from .cells.directional_coupler import directional_coupler
from .cells.taper import taper
from .cells.grating_coupler import grating_coupler
from .cells.mmi_1x2 import mmi_1x2


TFLN_PDK = gf.Pdk(
    name="TFLN_DEMO",
    version="0.1.0",
    layers=LAYER,
    layer_views=LAYER_VIEWS,
    cross_sections={
        "wg": wg,
    },
    cells={
        "bend_s": bend_s,
        "directional_coupler": directional_coupler,
        "taper": taper,
        "grating_coupler": grating_coupler,
        "mmi_1x2": mmi_1x2,
    },
)

TFLN_PDK.activate()