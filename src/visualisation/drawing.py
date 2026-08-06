from __future__ import annotations

import matplotlib.patches as patches

from geometry import Point

def setup_axes(
    ax,
    title: str | None = None,
):
    """
    Configure matplotlib axis for PCB geometry viewing.
    """

    ax.set_aspect(
        "equal",
        adjustable="box",
    )

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.set_xlabel(
        "X position (mm)"
    )

    ax.set_ylabel(
        "Y position (mm)"
    )

    if title:
        ax.set_title(title)

def set_view_limits(
    ax,
    radius: float,
):
    """
    Set symmetric view limits around origin.
    """

    ax.set_xlim(
        -radius,
        radius,
    )

    ax.set_ylim(
        -radius,
        radius,
    )


def draw_circle(
    ax,
    radius: float,
    linestyle: str = "--",
    colour: str = "black",
    linewidth: float = 1.0,
    label: str | None = None,
):
    """
    Draw a circular reference boundary.
    """

    circle = patches.Circle(
        (0, 0),
        radius,
        fill=False,
        linestyle=linestyle,
        linewidth=linewidth,
        edgecolor=colour,
        label=label,
    )

    ax.add_patch(circle)


def draw_polyline(
    ax,
    points: list[Point],
    colour: str = "black",
    linewidth: float = 1.0,
    label: str | None = None,
):
    """
    Draw a connected copper path.
    """

    xs = [
        p[0]
        for p in points
    ]

    ys = [
        p[1]
        for p in points
    ]

    ax.plot(
        xs,
        ys,
        linewidth=linewidth,
        color=colour,
        label=label,
    )

def draw_segment(
    ax,
    a: Point,
    b: Point,
    colour: str = "black",
    linewidth: float = 1.0,
):
    """
    Draw one copper segment.
    """

    ax.plot(
        [a[0], b[0]],
        [a[1], b[1]],
        linewidth=linewidth,
        color=colour,
    )

def draw_point(
    ax,
    point: Point,
    colour: str = "black",
    label: str | None = None,
):
    """
    Draw a point marker.
    """

    ax.scatter(
        [point[0]],
        [point[1]],
        color=colour,
        s=20,
    )

    if label:
        ax.annotate(
            label,
            point,
            xytext=(5, 5),
            textcoords="offset points",
        )

def draw_via(
    ax,
    point: Point,
    colour: str = "purple",
    diameter: float = 0.5,
):
    """
    Draw buried/blind via footprint.
    """

    via = patches.Circle(
        point,
        diameter / 2,
        fill=False,
        edgecolor=colour,
        linewidth=1.0,
    )

    ax.add_patch(via)