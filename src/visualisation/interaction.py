from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import matplotlib.pyplot as plt

OUTPUT_DIR = Path("output") / "visualisations"
IMAGE_EXTENSIONS = {".png", ".svg", ".pdf"}


def prepare_output_directory() -> Path:
    """Prepare visualisation output directory.

    Removes previous generated figures so that outdated images cannot remain
    after design changes.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for file in OUTPUT_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
            file.unlink()

    return OUTPUT_DIR


def save_figure(
    fig: plt.Figure,
    filename: str,
    formats: tuple[str, ...] = ("png",),
) -> dict[str, Path]:
    """Save matplotlib figure in publication formats.

    Parameters
    ----------
    fig:
        The Matplotlib figure instance to save.
    filename:
        Target base name without extension.
    formats:
        File extensions to render (default is ("png",); can include "svg", "pdf").
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saved_paths = {}
    print("\nSaved visualisation:")

    for fmt in formats:
        ext = fmt.lstrip(".")
        path = OUTPUT_DIR / f"{filename}.{ext}"
        
        fig.savefig(
            path,
            dpi=600 if ext == "png" else None,
            bbox_inches="tight",
        )
        saved_paths[ext] = path
        print(f"  {path}")

    return saved_paths