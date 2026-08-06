import math

from spec import WindingSpec, check_fit, report_fit
from winding import build_winding, build_layer, build_coil
from validation import validate
from kicad_export import EmitConfig, emit_kicad
from visualisation.viewer import generate_visualisations
from kicad_output import save_kicad_file


def format_polar(point: tuple[float, float]) -> str:
    """Format a 2D point as Cartesian, radius, and angle in degrees."""
    x, y = point
    r = math.hypot(x, y)
    ang = math.degrees(math.atan2(y, x))
    return f"({x:+.2f}, {y:+.2f})  r={r:.2f}  ang={ang:+.1f}"


def main():
    spec = WindingSpec()

    fit = check_fit(spec)
    print(report_fit(spec, fit))

    # --- [2] Single-Layer Coil ---
    pts = build_layer(spec)
    angles, radii = zip(*[(math.degrees(math.atan2(y, x)), math.hypot(x, y)) for x, y in pts])

    print("\n[2] single-layer coil:")
    print(f"  polyline points : {len(pts)}")
    print(f"  lead terminal   : {format_polar(pts[0])}")
    print(f"  tail terminal   : {format_polar(pts[-1])}")
    print(
        f"  angular extent  : {min(angles):+.1f} .. {max(angles):+.1f} deg "
        f"(slot +/-{spec.coil_arc_deg / 2:.1f})"
    )
    print(f"  radial extent   : {min(radii):.2f} .. {max(radii):.2f} mm")

    # --- [3] Four-Layer Stacked Coil ---
    coil = build_coil(spec)

    print("\n[3] four-layer stacked coil:")
    print(f"  segments (all layers) : {len(coil.segments)}")
    print(f"  buried vias           : {len(coil.vias)}")

    for (x, y), la, lb in coil.vias:
        print(f"     via ({x:.2f},{y:.2f})  {la} <-> {lb}")

    print(f"  phase lead : {format_polar(coil.lead)}")
    print(f"  phase tail : {format_polar(coil.tail)}")

    # --- [4] Full Winding ---
    wdg = build_winding(spec)

    print("\n[4] full winding:")
    print(f"  coils placed  : {len(wdg.coils)}")

    for ph, chain in wdg.chains.items():
        print(f"     phase {ph}: slots {[c.slot for c in chain]}")

    print(
        f"  series links  : {len(wdg.links)}  "
        f"(= {spec.coils_per_phase - 1} x {spec.n_phases} phases)"
    )

    star_x, star_y = wdg.star
    star_r = math.hypot(star_x, star_y)
    print(f"  star spokes   : {len(wdg.spokes)}   star @ ({star_x:+.2f},{star_y:+.2f}) r={star_r:.2f}")

    tot_seg = sum(len(c.segments) for c in wdg.coils) + len(wdg.links) + len(wdg.spokes)
    tot_via = sum(len(c.vias) for c in wdg.coils)
    print(f"  total copper  : {tot_seg} segments, {tot_via} buried vias\n")

    print(validate(wdg))

    # --- [6] KiCad Emit ---
    cfg = EmitConfig(
        centre_x=164.20,
        centre_y=87.00,
        phase_nets={"A": 61, "B": 60, "C": 63},
    )

    lines = emit_kicad(wdg, cfg)
    save_kicad_file(lines, filename="pcb_stator_winding")

    n_segments = sum(1 for line in lines if "(segment" in line)
    n_vias = sum(1 for line in lines if "(via" in line)

    print("\n[6] KiCad emit (coils + buried vias):")
    print(f"  emitted elements : {len(lines)} ({n_segments} segments, {n_vias} vias)")
    print(
        f"  placed at centre : ({cfg.centre_x}, {cfg.centre_y}), "
        f"nets A/B/C = {cfg.phase_nets['A']}/{cfg.phase_nets['B']}/{cfg.phase_nets['C']}"
    )
    print(f"  sample line: {lines[0][:96].strip()}")

    # --- [7] Visualisations ---
    print("\n[7] Generating visualisations:")
    generate_visualisations(spec)


if __name__ == "__main__":
    main()