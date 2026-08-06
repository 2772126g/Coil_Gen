from dataclasses import dataclass
from typing import List

import uuid as _uuid

from geometry import Point
from winding import Winding

def _board(pt: Point, cx: float, cy: float) -> Point:
    return (round(pt[0] + cx, 4), round(-pt[1] + cy, 4))


@dataclass
class EmitConfig:
    """Everything board-specific needed to place the winding. Nothing here lives
    in WindingSpec, so the same winding drops onto any layout."""
    centre_x: float
    centre_y: float
    phase_nets: dict                    # phase label -> KiCad net number
    track_width_mm: float = 0.20
    via_pad_mm: float = 0.45
    via_drill_mm: float = 0.20
    via_kind: str = "blind"             # buried/blind vias for coil-layer stitches
    include_links: bool = False         # emit direct links/spokes too (see note)


def emit_kicad(wdg: Winding, cfg: EmitConfig) -> List[str]:
    """Serialise the winding to KiCad s-expression lines (segments + vias),
    placed at cfg.centre and netted per cfg.phase_nets.

    By default only the physical coils + buried vias are emitted. The series
    links and star spokes are NOT emitted as copper by default because, drawn
    directly, they cross coil copper; they should be bus-routed during board
    integration (use connection_map() for the wiring order). Set
    include_links=True to emit them as-is anyway (e.g. for a quick preview).
    """
    cx, cy = cfg.centre_x, cfg.centre_y
    out: List[str] = []

    def seg(a: Point, b: Point, layer: str, net: int) -> str:
        A, B = _board(a, cx, cy), _board(b, cx, cy)
        return (f'\t(segment (start {A[0]:.4f} {A[1]:.4f}) (end {B[0]:.4f} {B[1]:.4f}) '
                f'(width {cfg.track_width_mm}) (layer "{layer}") (net {net}) '
                f'(uuid "{_uuid.uuid4()}"))')

    def via(xy: Point, l1: str, l2: str, net: int) -> str:
        P = _board(xy, cx, cy)
        kind = "via " + (cfg.via_kind + " " if cfg.via_kind else "")
        return (f'\t({kind}(at {P[0]:.4f} {P[1]:.4f}) (size {cfg.via_pad_mm}) '
                f'(drill {cfg.via_drill_mm}) (layers "{l1}" "{l2}") (net {net}) '
                f'(uuid "{_uuid.uuid4()}"))')

    for c in wdg.coils:
        net = cfg.phase_nets[c.phase]
        for a, b, l in c.segments:
            if a != b:
                out.append(seg(a, b, l, net))
        for xy, l1, l2 in c.vias:
            out.append(via(xy, l1, l2, net))

    if cfg.include_links:
        # map link/spoke phase by nearest coil terminal (they were built per-phase)
        for ph, chain in wdg.chains.items():
            net = cfg.phase_nets[ph]
            for k in range(len(chain) - 1):
                out.append(seg(chain[k].tail, chain[k + 1].lead, wdg.link_layer, net))
            out.append(seg(chain[-1].tail, wdg.star, wdg.link_layer, net))

    return out


def connection_map(wdg: Winding, cfg: EmitConfig | None = None) -> str:
    """Text wiring map for board integration: per-phase series order, the phase
    leads (route to driver), and the star point. Coordinates are local unless an
    EmitConfig is given, in which case they are board coordinates."""
    def place(pt):
        if cfg is None:
            return f"({pt[0]:+.2f},{pt[1]:+.2f})"
        b = _board(pt, cfg.centre_x, cfg.centre_y)
        return f"({b[0]:.2f},{b[1]:.2f})"

    L = ["# winding connection map",
         f"# {wdg.spec.n_coils} coils, {wdg.spec.n_phases} phases x "
         f"{wdg.spec.coils_per_phase}, star-connected", ""]
    for ph, chain in wdg.chains.items():
        order = " -> ".join(f"C{c.slot:02d}@{c.angle_deg:.0f}" for c in chain)
        L.append(f"phase {ph}:")
        L.append(f"  LEAD {place(wdg.leads[ph])} -> {order} -> STAR")
        L.append(f"  series links (bus-route): " +
                 ", ".join(f"C{chain[k].slot:02d}.tail->C{chain[k+1].slot:02d}.lead"
                           for k in range(len(chain) - 1)))
        L.append("")
    L.append(f"STAR (neutral, place net-tie): {place(wdg.star)}")
    L.append("phase LEADS route to driver U/V/W terminals.")
    return "\n".join(L)