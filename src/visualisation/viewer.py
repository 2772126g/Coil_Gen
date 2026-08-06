from __future__ import annotations

from pathlib import Path
import shutil

import matplotlib.pyplot as plt

from spec import WindingSpec
from winding import build_winding

from .colours import layer_colour, phase_colour
from .drawing import draw_segment, draw_via
from .overlays import (
    draw_board_outline,
    draw_centre_marker,
    draw_coil_label,
    draw_keepout,
    draw_star_point,
)


def clear_visualisation_folder() -> None:
    """Remove old PNG visualisations to prevent stale images remaining."""
    folder = Path("output") / "visualisations"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, filename: str) -> Path:
    """Save figure as a high-resolution PNG."""
    folder = Path("output") / "visualisations"
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{filename}.png"
    fig.savefig(path, dpi=600, bbox_inches="tight")
    print(f"Saved: {path}")
    return path


def draw_winding(
    ax: plt.Axes,
    wdg,
    show_layers: bool = False,
    selected_layer: str | None = None,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Draw winding copper and return coordinate bounds (x_range, y_range)."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    has_points = False

    for coil in wdg.coils:
        for a, b, layer in coil.segments:
            if selected_layer is not None and layer != selected_layer:
                continue

            colour = layer_colour(layer) if show_layers else phase_colour(coil.phase)
            draw_segment(ax, a, b, colour=colour, linewidth=0.8)

            min_x, max_x = min(min_x, a[0], b[0]), max(max_x, a[0], b[0])
            min_y, max_y = min(min_y, a[1], b[1]), max(max_y, a[1], b[1])
            has_points = True

        # Only display vias on complete views
        if selected_layer is None:
            for xy, _, _ in coil.vias:
                draw_via(ax, xy, colour="purple")
                min_x, max_x = min(min_x, xy[0]), max(max_x, xy[0])
                min_y, max_y = min(min_y, xy[1]), max(max_y, xy[1])
                has_points = True

    return ((min_x, max_x), (min_y, max_y)) if has_points else None


def label_coils(ax: plt.Axes, wdg) -> None:
    """Draw coil labels at lead positions."""
    for coil in wdg.coils:
        draw_coil_label(ax, coil.lead, f"C{coil.slot:02d}\n{coil.phase}")


def setup_plot(ax: plt.Axes, spec: WindingSpec, title: str) -> None:
    """Add mechanical references and styling."""
    draw_board_outline(ax, spec.keepout_radius_mm)
    draw_keepout(ax, spec.keepout_radius_mm)
    draw_centre_marker(ax)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(title)


def render_view(
    spec: WindingSpec,
    wdg,
    filename: str,
    title: str,
    show_layers: bool = False,
    selected_layer: str | None = None,
    labels: bool = False,
) -> None:
    """Render a single figure view and save it to disk."""
    fig, ax = plt.subplots(figsize=(8, 8))

    setup_plot(ax, spec, title)
    draw_star_point(ax, wdg.star)

    bounds = draw_winding(
        ax,
        wdg,
        show_layers=show_layers,
        selected_layer=selected_layer,
    )

    if labels:
        label_coils(ax, wdg)

    if bounds:
        (min_x, max_x), (min_y, max_y) = bounds
        margin = 3.0
        ax.set_xlim(min_x - margin, max_x + margin)
        ax.set_ylim(min_y - margin, max_y + margin)

    plt.tight_layout()
    save_figure(fig, filename)
    plt.close(fig)


def generate_visualisations(spec: WindingSpec | None = None) -> None:
    """Generate all standard stator winding visualisations."""
    spec = spec or WindingSpec()
    clear_visualisation_folder()

    wdg = build_winding(spec)

    # Overview plots
    render_view(
        spec,
        wdg,
        "winding_phase",
        "PCB Reaction Wheel Stator - Phase View",
        show_layers=False,
        labels=True,
    )
    render_view(
        spec,
        wdg,
        "winding_layers",
        "PCB Reaction Wheel Stator - Layer View",
        show_layers=True,
    )

    # Individual layer plots
    layers = sorted({layer for coil in wdg.coils for _, _, layer in coil.segments})

    for layer in layers:
        filename = f"layer_{layer.replace('.', '_')}"
        render_view(
            spec,
            wdg,
            filename,
            f"PCB Reaction Wheel Stator - {layer}",
            show_layers=True,
            selected_layer=layer,
        )


if __name__ == "__main__":
    generate_visualisations()