import math

from spec import WindingSpec, check_fit, report_fit
from winding import build_winding, build_layer, build_coil
from validation import validate
from kicad_export import EmitConfig, emit_kicad, connection_map

def main():

    spec = WindingSpec()
    fit = check_fit(spec)
    print(report_fit(spec, fit))

    pts = build_layer(spec)
    ang = [math.degrees(math.atan2(y, x)) for x, y in pts]
    rr = [math.hypot(x, y) for x, y in pts]
    print("\n[2] single-layer coil:")
    print(f"  polyline points : {len(pts)}")
    print(f"  lead terminal   : ({pts[0][0]:+.2f}, {pts[0][1]:+.2f})  "
          f"r={math.hypot(*pts[0]):.2f}  ang={math.degrees(math.atan2(pts[0][1], pts[0][0])):+.1f}")
    print(f"  tail terminal   : ({pts[-1][0]:+.2f}, {pts[-1][1]:+.2f})  "
          f"r={math.hypot(*pts[-1]):.2f}  ang={math.degrees(math.atan2(pts[-1][1], pts[-1][0])):+.1f}")
    print(f"  angular extent  : {min(ang):+.1f} .. {max(ang):+.1f} deg "
          f"(slot +/-{spec.coil_arc_deg/2:.1f})")
    print(f"  radial extent   : {min(rr):.2f} .. {max(rr):.2f} mm")

    coil = build_coil(spec)
    print("\n[3] four-layer stacked coil:")
    print(f"  segments (all layers) : {len(coil.segments)}")
    print(f"  buried vias           : {len(coil.vias)}")
    for xy, la, lb in coil.vias:
        print(f"     via ({xy[0]:.2f},{xy[1]:.2f})  {la} <-> {lb}")
    print(f"  phase lead : ({coil.lead[0]:+.2f},{coil.lead[1]:+.2f})  "
          f"r={math.hypot(*coil.lead):.2f} ang={math.degrees(math.atan2(coil.lead[1], coil.lead[0])):+.1f}")
    print(f"  phase tail : ({coil.tail[0]:+.2f},{coil.tail[1]:+.2f})  "
          f"r={math.hypot(*coil.tail):.2f} ang={math.degrees(math.atan2(coil.tail[1], coil.tail[0])):+.1f}")

    wdg = build_winding(spec)
    print("\n[4] full winding:")
    print(f"  coils placed  : {len(wdg.coils)}")
    for ph, chain in wdg.chains.items():
        print(f"     phase {ph}: slots {[c.slot for c in chain]}")
    print(f"  series links  : {len(wdg.links)}  (= {spec.coils_per_phase - 1} x "
          f"{spec.n_phases} phases)")
    print(f"  star spokes   : {len(wdg.spokes)}   star @ "
          f"({wdg.star[0]:+.2f},{wdg.star[1]:+.2f}) r={math.hypot(*wdg.star):.2f}")
    tot_seg = sum(len(c.segments) for c in wdg.coils) + len(wdg.links) + len(wdg.spokes)
    tot_via = sum(len(c.vias) for c in wdg.coils)
    print(f"  total copper  : {tot_seg} segments, {tot_via} buried vias")

    print()
    print(validate(wdg))

    # [6] emit onto a specific board (the BIRDS layout) -- board-agnostic call
    cfg = EmitConfig(centre_x=164.20, centre_y=87.00,
                     phase_nets={"A": 61, "B": 60, "C": 63})
    lines = emit_kicad(wdg, cfg)
    print("\n[6] KiCad emit (coils + buried vias):")
    print(f"  emitted elements : {len(lines)}  "
          f"({sum('(segment' in x for x in lines)} segments, "
          f"{sum('(via' in x for x in lines)} vias)")
    print(f"  placed at centre : ({cfg.centre_x}, {cfg.centre_y}), "
          f"nets A/B/C = {cfg.phase_nets['A']}/{cfg.phase_nets['B']}/{cfg.phase_nets['C']}")
    print("  sample line:", lines[0][:96].strip())



if __name__ == "__main__":
    main()