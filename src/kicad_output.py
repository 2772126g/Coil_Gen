from pathlib import Path


def save_kicad_file(
    lines: list[str],
    filename: str = "pcb_stator_winding",
) -> Path:
    """Save generated KiCad geometry.

    Output:
        output/kicad/<filename>.kicad_pcb
    """
    output_dir = Path("output") / "kicad"
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"{filename}.kicad_pcb"

    header = "(kicad_pcb\n  (version 20240108)\n  (generator pcbnew)\n\n"
    body = "".join(f"  {line}\n" for line in lines)
    footer = ")\n"

    path.write_text(header + body + footer, encoding="utf-8")

    print(f"\nSaved KiCad PCB:\n  {path}")
    return path