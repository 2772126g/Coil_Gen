from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from spec import WindingSpec
from winding import build_winding

from .colours import phase_colour, layer_colour
from .drawing import draw_segment, draw_via
from .overlays import (
    draw_board_outline,
    draw_keepout,
    draw_centre_marker,
    draw_coil_label,
    draw_star_point,
)

def clear_visualisation_folder():
    """
    Remove old PNG visualisations.

    Prevents stale images remaining when:
    - layer count changes
    - coil parameters change
    - filenames change
    """

    folder = Path("output") / "visualisations"

    if not folder.exists():
        return

    for file in folder.glob("*.png"):
        file.unlink()

def save_figure(
    fig,
    filename: str,
):
    """
    Save figure as high-resolution PNG.
    """

    folder = Path("output") / "visualisations"

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = folder / f"{filename}.png"

    fig.savefig(
        path,
        dpi=600,
        bbox_inches="tight",
    )

    print(f"Saved: {path}")

def draw_winding(
    ax,
    wdg,
    show_layers: bool = False,
    selected_layer: str | None = None,
):
    """
    Draw winding copper.

    Parameters
    ----------
    show_layers:
        False -> phase colours
        True  -> PCB layer colours

    selected_layer:
        If supplied, only draw that copper layer.
    """

    xs = []
    ys = []

    for coil in wdg.coils:

        for a, b, layer in coil.segments:

            if selected_layer is not None:

                if layer != selected_layer:
                    continue


            if show_layers:

                colour = layer_colour(layer)

            else:

                colour = phase_colour(
                    coil.phase
                )


            draw_segment(
                ax,
                a,
                b,
                colour=colour,
                linewidth=0.8,
            )


            xs.extend(
                [
                    a[0],
                    b[0],
                ]
            )

            ys.extend(
                [
                    a[1],
                    b[1],
                ]
            )
        # Only display vias on complete views

        if selected_layer is None:

            for xy, _, _ in coil.vias:

                draw_via(
                    ax,
                    xy,
                    colour="purple",
                )

                xs.append(
                    xy[0]
                )

                ys.append(
                    xy[1]
                )


    return xs, ys

def label_coils(
    ax,
    wdg,
):

    for coil in wdg.coils:

        draw_coil_label(
            ax,
            coil.lead,
            f"C{coil.slot:02d}\n{coil.phase}",
        )



def setup_plot(
    ax,
    spec,
    title,
):
    """
    Add mechanical references.
    """

    draw_board_outline(
        ax,
        spec.keepout_radius_mm,
    )

    draw_keepout(
        ax,
        spec.keepout_radius_mm,
    )

    draw_centre_marker(
        ax,
    )


    ax.set_aspect(
        "equal"
    )

    ax.grid(
        True,
        linestyle="--",
        linewidth=0.5,
        alpha=0.4,
    )


    ax.set_xlabel(
        "X (mm)"
    )

    ax.set_ylabel(
        "Y (mm)"
    )

    ax.set_title(
        title
    )

def render_view(
    spec,
    wdg,
    filename,
    title,
    show_layers=False,
    selected_layer=None,
    labels=False,
):
    fig, ax = plt.subplots(
        figsize=(8, 8),
    )

    setup_plot(
        ax,
        spec,
        title,
    )

    draw_star_point(
        ax,
        wdg.star,
    )

    xs, ys = draw_winding(
        ax,
        wdg,
        show_layers=show_layers,
        selected_layer=selected_layer,
    )

    if labels:

        label_coils(
            ax,
            wdg,
        )

    if xs and ys:

        margin = 3.0

        ax.set_xlim(
            min(xs)-margin,
            max(xs)+margin,
        )

        ax.set_ylim(
            min(ys)-margin,
            max(ys)+margin,
        )

    plt.tight_layout()


    save_figure(
        fig,
        filename,
    )

    plt.close(fig)

def generate_visualisations(
    spec: WindingSpec | None = None,
):
    if spec is None:

        spec = WindingSpec()

    clear_visualisation_folder()

    wdg = build_winding(
        spec
    )

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

    layers = sorted(
        {
            layer
            for coil in wdg.coils
            for _, _, layer in coil.segments
        }
    )

    for layer in layers:

        filename = (
            "layer_"
            + layer.replace(
                ".",
                "_",
            )
        )

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