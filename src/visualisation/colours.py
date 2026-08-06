from __future__ import annotations

_PHASE_COLOURS = {
    "A": "tab:red",
    "B": "tab:blue",
    "C": "tab:green",
}

def phase_colour(phase: str) -> str:
    """
    Return display colour for a motor phase.
    """

    return _PHASE_COLOURS.get(
        phase,
        "black",
    )

_LAYER_COLOURS = {
    "F.Cu": "gold",
    "B.Cu": "purple",

    "In1.Cu": "tab:orange",
    "In2.Cu": "tab:blue",
    "In3.Cu": "tab:green",
    "In4.Cu": "tab:red",
    "In5.Cu": "tab:purple",
    "In6.Cu": "tab:brown",
}

def layer_colour(layer: str) -> str:
    """
    Return display colour for a PCB copper layer.
    """

    return _LAYER_COLOURS.get(
        layer,
        "black",
    )

_REFERENCE_COLOURS = {
    "board_outline": "black",
    "keepout": "grey",
    "centre": "black",
    "star": "purple",
}

def reference_colour(name: str) -> str:
    """
    Return colour for mechanical overlays.
    """

    return _REFERENCE_COLOURS.get(
        name,
        "black",
    )