"""Describes the physical structure of the wafer."""

# All dimensions in micrometers

LNOI_STACK = {
    "substrate": {
        "material": "Silicon",
        "thickness": None,
    },

    "box": {
        "material": "SiO2",
        "thickness": 4.7,
    },

    "ln": {
        "material": "LiNbO3",
        "thickness": 0.6,
        "orientation": "x-cut",
    },

    "cladding": {
        "material": "SiO2",
        "thickness": None,
    },
}