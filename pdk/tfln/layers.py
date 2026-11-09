""""Which GDS layers exist."""

from gdsfactory.technology import LayerMap
from gdsfactory.typings import Layer


class LAYER(LayerMap):
    """LayerMap for tfln. Inspired by CSEM open PDK."""

    # ----------------------------------------------------------------
    # Optical waveguide layers
    # ----------------------------------------------------------------
    WG: Layer = (1, 0)
    """Main ridge waveguide layer.
    
    Defines optical waveguide. Assuming a total 600nm TFLN layer, etching leads to
    a ridge height of 400nm, on-top a 200nm base."""

    # ----------------------------------------------------------------
    # Metallization
    # ----------------------------------------------------------------
    MET1: Layer = (10, 0)
    """First metallization layer.
    
    Used for electrodes in EO-modulators, acousto-optic modulators, thermal phase-shifters,
    and periodic poling (PPLN) structures."""
    
    MET2: Layer = (11, 0)
    """Second metallization layer.
    
    Provides an additional metal routing layer for complex electrical circuits and RF circuitry,
    including traveling-wave electrode structures."""

    # ----------------------------------------------------------------
    # Electrical interconnect
    # ----------------------------------------------------------------
    VIA: Layer = (12, 0)
    """Vertical interconnect layer.
    
    Defines electrical connections between MET1 and MET2, enabling multi-layer electrical routing."""

    # ----------------------------------------------------------------
    # Chip release layer
    # ----------------------------------------------------------------

    DEEP_GRID: Layer = (20, 0)
    """Deep etch / chip release layer.

    Defines the deep reactive ion etching (DRIE) grid used
    for chip release from the wafer and the formation of
    optical chip facets.
    """

        # ----------------------------------------------------------------
    # Cladding definition
    # ----------------------------------------------------------------

    CLADDING_OPEN: Layer = (21, 0)
    """Cladding opening layer.

    Defines regions where the deposited SiO2 upper cladding
    is selectively removed to expose electrodes or create
    unclad waveguides and resonators.
    """

    # ----------------------------------------------------------------
    # Non-fabrication / documentation layers
    # ----------------------------------------------------------------

    TEXT: Layer = (100, 0)
    """Text and annotation layer.

    Used for component labels, identification numbers,
    and general layout annotations.
    """

    PORT: Layer = (101, 0)
    """Optical port marker layer.

    Used to visualize and identify optical ports in the layout.
    Not intended for fabrication.
    """

    PORT_ELECTRICAL: Layer = (102, 0)
    """Electrical port marker layer.

    Used to visualize and identify electrical ports
    and connection locations in the layout.
    Not intended for fabrication.
    """

    DEVREC: Layer = (103, 0)
    """Device recognition layer.

    Defines the boundaries of individual photonic devices
    for layout organization and verification.
    Not intended for fabrication.
    """

    FLOORPLAN: Layer = (104, 0)
    """Chip floorplan layer.

    Defines the chip boundary and layout organization regions.
    Not intended for fabrication.
    """