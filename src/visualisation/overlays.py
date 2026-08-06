from __future__ import annotations

import math

from geometry import Point

from .colours import reference_colour
from .drawing import draw_circle, draw_point

def draw_board_outline(
    ax,
    radius: float,
):
    """
    Draw PCB mechanical outer boundary.
    """

    draw_circle(
        ax,
        radius,
        linestyle="-",
        colour=reference_colour("board_outline"),
        linewidth=1.2,
        label="PCB outline",
    )

def draw_keepout(
    ax,
    radius: float,
):
    """
    Draw mechanical keep-out region.
    """
    draw_circle(
        ax,
        radius,
        linestyle=":",
        colour=reference_colour("keepout"),
        linewidth=1.0,
        label="Keep-out",
    )

def draw_centre_marker(
    ax,
):
    """
    Mark PCB centre.
    """

    draw_point(
        ax,
        (0.0, 0.0),
        colour=reference_colour("centre"),
        label="Centre",
    )

def draw_coil_label(
    ax,
    position: Point,
    text: str,
):
    """
    Label an individual coil.
    """

    ax.annotate(
        text,
        position,
        xytext=(4, 4),
        textcoords="offset points",
        fontsize=8,
    )

def draw_phase_label(
    ax,
    phase: str,
    angle_deg: float,
    radius: float,
):
    """
    Place phase markers around stator perimeter.
    """

    angle = math.radians(
        angle_deg
    )

    position = (
        radius * math.cos(angle),
        radius * math.sin(angle),
    )

    ax.annotate(
        phase,
        position,
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
    )

def draw_star_point(
    ax,
    point: Point,
):
    """
    Mark three-phase star connection.
    """

    draw_point(
        ax,
        point,
        colour=reference_colour("star"),
        label="STAR",
    )

def draw_terminal(
    ax,
    point: Point,
    name: str,
):
    """
    Mark external phase terminals.
    """

    draw_point(
        ax,
        point,
        label=name,
    )