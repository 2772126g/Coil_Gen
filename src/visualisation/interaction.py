from __future__ import annotations

from pathlib import Path


OUTPUT_DIR = Path("output") / "visualisations"


def prepare_output_directory():
    """
    Prepare visualisation output directory.

    Removes previous generated figures so that
    outdated images cannot remain after design changes.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for file in OUTPUT_DIR.iterdir():

        if file.is_file():

            if file.suffix.lower() in {
                ".png",
                ".svg",
                ".pdf",
            }:
                file.unlink()

def save_figure(
    fig,
    filename: str,
):
    """
    Save matplotlib figure in publication formats.

    Outputs:
        PNG  - quick viewing
        can do SVG and PDF if needed
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {
        "png": OUTPUT_DIR / f"{filename}.png",
        "svg": OUTPUT_DIR / f"{filename}.svg",
        "pdf": OUTPUT_DIR / f"{filename}.pdf",
    }

    fig.savefig(
        paths["png"],
        dpi=600,
        bbox_inches="tight",
    )

    print("\nSaved visualisation:")
    
    for path in paths.values():
        print(f"  {path}")