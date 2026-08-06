from __future__ import annotations

import math
from typing import TYPE_CHECKING

from geometry import Point

from .colours import reference_colour
from .drawing import draw_circle, draw_point

if TYPE_CHECKING:
    import matplotlib.pyplot as plt


def draw_board_outline(ax: plt.Axes, radius: float) -> None:
    """Draw PCB mechanical outer boundary."""
    draw_circle(
        ax,
        radius,
        linestyle="-",
        colour=reference_colour("board_outline"),
        linewidth=1.2,
        label="PCB outline",
    )


def draw_keepout(ax: plt.Axes, radius: float) -> None:
    """Draw mechanical keep-out region."""
    draw_circle(
        ax,
        radius,
        linestyle=":",
        colour=reference_colour("keepout"),
        linewidth=1.0,
        label="Keep-out",
    )


def draw_centre_marker(ax: plt.Axes) -> None:
    """Mark PCB centre (0.0, 0.0)."""
    draw_point(
        ax,
        (0.0, 0.0),
        colour=reference_colour("centre"),
        label="Centre",
    )


def draw_coil_label(ax: plt.Axes, position: Point, text: str) -> None:
    """Label an individual coil."""
    ax.annotate(
        text,
        position,
        xytext=(4, 4),
        textcoords="offset points",
        fontsize=8,
    )


def draw_phase_label(
    ax: plt.Axes,
    phase: str,
    angle_deg: float,
    radius: float,
) -> None:
    """Place phase markers around stator perimeter."""
    angle_rad = math.radians(angle_deg)
    position = (radius * math.cos(angle_rad), radius * math.sin(angle_rad))

    ax.annotate(
        phase,
        position,
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
    )


def draw_star_point(ax: plt.Axes, point: Point) -> None:
    """Mark three-phase star connection."""
    draw_point(
        ax,
        point,
        colour=reference_colour("star"),
        label="STAR",
    )


def draw_terminal(ax: plt.Axes, point: Point, name: str) -> None:
    """Mark external phase terminals."""
    draw_point(
        ax,
        point,
        label=name,
    )