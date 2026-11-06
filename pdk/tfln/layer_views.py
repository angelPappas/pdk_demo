"""Colors and visibility for the GDS layers in the PDK."""

from gdsfactory.technology import LayerViews, LayerView

from .layers import LAYER


LAYER_VIEWS = LayerViews(
    layer_views={
        LAYER.WG: LayerView(
            layer=LAYER.WG,
            color="#30A24B",
            name="WG1",
        ),
        LAYER.MET1: LayerView(
            layer=LAYER.MET1,
            color="#FF0000",
            name="MET1",
        ),
        LAYER.MET2: LayerView(
            layer=LAYER.MET2,
            color="#800080",
            name="MET2",
        ),
        LAYER.VIA: LayerView(
            layer=LAYER.VIA,
            color="#808080",
            name="VIA",
        ),
    }
)