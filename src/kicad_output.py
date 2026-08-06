from pathlib import Path

def save_kicad_file(
    lines,
    filename="pcb_stator_winding",
):
    """
    Save generated KiCad geometry.

    Output:
        output/kicad/<filename>.kicad_pcb
    """

    folder = Path("output") / "kicad"

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = folder / f"{filename}.kicad_pcb"

    with open(path, "w") as f:

        f.write(
            "(kicad_pcb\n"
            "  (version 20240108)\n"
            "  (generator pcbnew)\n\n"
        )

        # write generated segments/vias

        for line in lines:

            f.write(
                "  "
                + line
                + "\n"
            )

        f.write(
            ")\n"
        )

    print(
        "\nSaved KiCad PCB:"
    )

    print(
        f"  {path}"
    )

    return path