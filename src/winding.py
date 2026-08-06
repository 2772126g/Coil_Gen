from dataclasses import dataclass
from typing import List, Tuple
import math

from geometry import Point, polar, arc_points, _dedupe, _mirror, _rot
from spec import WindingSpec, check_fit

Segment = Tuple[Point, Point, str]
Via = Tuple[Point, str, str]

@dataclass
class Coil:
    """One complete multi-layer coil in local coords: netted copper as segments
    + buried vias, with the two external terminals identified. `lead` is the
    phase-in terminal (first coil layer, outer +arc corner); `tail` is the
    phase-out terminal (last coil layer, outer -arc corner)."""
    segments: List[Segment]
    vias: List[Via]
    lead: Point
    tail: Point
    layer_pts: dict          # layer -> polyline (for previews / crossing checks)

@dataclass
class PlacedCoil:
    slot: int
    angle_deg: float
    phase: str
    segments: List[Segment]      # rotated copper
    vias: List[Via]              # rotated buried vias
    lead: Point                  # rotated phase-in terminal
    tail: Point                  # rotated phase-out terminal

@dataclass
class Winding:
    spec: WindingSpec
    coils: List[PlacedCoil]
    links: List[Segment]         # inter-coil series links (tail[k] -> lead[k+1])
    spokes: List[Segment]        # star spokes (last tail -> star point)
    leads: dict                  # phase -> phase-lead point (route to driver)
    star: Point                  # common neutral point
    link_layer: str              # layer the links/spokes are drawn on

    @property
    def chains(self) -> dict:
        """phase -> series-ordered list of PlacedCoil (lead coil first)."""
        out = {}
        for ph in phase_labels(self.spec.n_phases):
            out[ph] = sorted([c for c in self.coils if c.phase == ph],
                             key=lambda c: c.slot)
        return out
    
def build_layer(spec: WindingSpec, turns: int | None = None,
                seg_deg: float = 2.0) -> List[Point]:
    """One coil layer as an ordered polyline in local coords (origin-centred,
    coil pointing along +x, +y up). Returns the point list; the first point is
    the outer lead terminal, the last is the centreline tail terminal."""
    if turns is None:
        turns = check_fit(spec).achievable_turns_per_layer
    ri, ro = spec.r_inner_mm, spec.r_outer_mm
    pitch = spec.turn_pitch_mm
    half = math.radians(spec.coil_arc_deg) / 2.0
    dang = pitch / ri                       # angular inset per nested loop

    pts: List[Point] = []
    for k in range(turns):
        a = half - k * dang
        Ro = ro - k * pitch
        Ri = ri + k * pitch
        if a <= 0 or Ri >= Ro - 1e-6:       # ran out of room -> stop cleanly
            break
        pts.append(polar(Ro, +a))           # outer +a corner (lead on k=0)
        pts.append(polar(Ri, +a))           # radial leg inward on the +a side
        pts += arc_points(Ri, +a, -a, seg_deg)   # inner arc +a -> -a
        pts.append(polar(Ro, -a))           # radial leg outward on the -a side
        a_next = half - (k + 1) * dang
        # outer arc back toward +a for the next loop; the final loop closes to
        # the centreline (0 deg) so the four layers' tails coincide there.
        pts += (arc_points(Ro, -a, +a_next, seg_deg) if k < turns - 1
                else arc_points(Ro, -a, 0.0, seg_deg))
    return _dedupe(pts)

def build_coil(spec: WindingSpec) -> Coil:
    """Stack the single-layer coil across `n_layers`, mirror-pairing alternate
    layers so their magnetic moments ADD, and stitch the layers in series with
    buried vias into one continuous path lead -> tail.

    Stacking rule (validated for the 4-layer baseline): layers alternate
    original / mirrored-and-reversed. The mirror flips the current sense
    geometrically while the reversal keeps the series path continuous, so all
    four layers circulate the same way and the MMF sums (the
    [orig, mirror, orig, mirror] pattern; [orig, mirror, mirror, orig] cancels).

    Series stitching (4-layer):
        L0.tail --centreline jumper--> via(r_a) --> L1  (buried via L0<->L1)
        L1.lead --outer bus--> via --> L2               (buried via L1<->L2)
        L2.tail --centreline jumper--> via(r_b) --> L3  (buried via L2<->L3)
    leaving L0.lead as the phase lead and L3.tail as the phase tail.
    """
    if spec.n_layers != 4:
        raise NotImplementedError(
            "build_coil currently implements the validated 4-layer stitching; "
            "extend the stitch scheme for other even layer counts.")

    L0 = build_layer(spec)
    layer_names = list(spec.coil_layers)
    # [orig, mirror-reversed, orig, mirror-reversed]
    polys = [list(L0),
             list(reversed(_mirror(L0))),
             list(L0),
             list(reversed(_mirror(L0)))]
    layer_pts = {name: pts for name, pts in zip(layer_names, polys)}

    segs: List[Segment] = []
    vias: List[Via] = []

    # winding copper on every layer
    for name, pts in layer_pts.items():
        for a, b in zip(pts[:-1], pts[1:]):
            segs.append((a, b, name))

    L2n, L3n, L4n, L5n = layer_names          # local aliases (In2..In5 by default)
    r_a, r_b = spec.stitch_radii_mm
    tail_pt = L0[-1]                           # centreline tail, shared by orig layers
    va = (r_a, 0.0)
    vb = (r_b, 0.0)

    # pair 1 (L0<->L1): both tails jumper inward along the centreline to va
    segs.append((tail_pt, va, L2n)); segs.append((tail_pt, va, L3n))
    vias.append((va, L2n, L3n))
    # pair 2 (L2<->L3): tails jumper inward to vb
    segs.append((tail_pt, vb, L4n)); segs.append((tail_pt, vb, L5n))
    vias.append((vb, L4n, L5n))

    # inter-pair (L1<->L2): join at the outer bus corner
    half = math.radians(spec.coil_arc_deg) / 2.0
    rbus = spec.bus_radius_mm
    in3_lead = layer_pts[L3n][-1]             # (-arc, r_outer)
    in4_lead = layer_pts[L4n][0]              # (+arc, r_outer)
    bA = polar(rbus, -half)
    bB = polar(rbus, +half)
    segs.append((in3_lead, bA, L3n))
    vias.append((bA, L3n, L4n))
    for a, b in zip(arc_points(rbus, -half, +half)[:-1],
                    arc_points(rbus, -half, +half)[1:]):
        segs.append((a, b, L4n))              # tangential bus on L2
    segs.append((bB, in4_lead, L4n))

    lead = layer_pts[L2n][0]                  # +arc outer corner -> phase lead
    tail = layer_pts[L5n][-1]                 # -arc outer corner -> phase tail
    return Coil(segments=segs, vias=vias, lead=lead, tail=tail, layer_pts=layer_pts)

def build_winding(spec: WindingSpec) -> Winding:
    """Replicate the stacked coil into the complete N-coil winding, assign
    phases (interleaved A,B,C,...), wire each phase's coils in series, and join
    the phase tails at a common star point. All local coordinates.

    Phasing: coils sit every slot_pitch; phases interleave so same-phase coils
    are n_phases slots apart. For the baseline that is 45 deg mechanical = one
    whole electrical cycle (pole_pairs = 8), so same-phase coils share polarity
    and simply series-add; the 120 deg relationship comes from the mechanical
    offset between phases.
    """
    base = build_coil(spec)
    labels = phase_labels(spec.n_phases)
    pitch = math.radians(spec.slot_pitch_deg)
    link_layer = spec.coil_layers[0]

    coils: List[PlacedCoil] = []
    for slot in range(spec.n_coils):
        ang = slot * pitch
        ph = labels[slot % spec.n_phases]
        coils.append(PlacedCoil(
            slot=slot, angle_deg=math.degrees(ang), phase=ph,
            segments=[(_rot(a, ang), _rot(b, ang), l) for a, b, l in base.segments],
            vias=[(_rot(xy, ang), l1, l2) for xy, l1, l2 in base.vias],
            lead=_rot(base.lead, ang),
            tail=_rot(base.tail, ang)))

    # per-phase series links + collect tails
    links: List[Segment] = []
    leads: dict = {}
    tails: dict = {}
    for ph in labels:
        chain = sorted([c for c in coils if c.phase == ph], key=lambda c: c.slot)
        leads[ph] = chain[0].lead
        for k in range(len(chain) - 1):
            links.append((chain[k].tail, chain[k + 1].lead, link_layer))
        tails[ph] = chain[-1].tail

    # star point: circular-mean angle of the three tails, just outside the coils
    tail_ang = [math.atan2(tails[ph][1], tails[ph][0]) for ph in labels]
    mx = sum(math.cos(a) for a in tail_ang) / len(tail_ang)
    my = sum(math.sin(a) for a in tail_ang) / len(tail_ang)
    star = polar(spec.r_outer_mm + 2.5, math.atan2(my, mx))

    spokes: List[Segment] = [(tails[ph], star, link_layer) for ph in labels]

    return Winding(spec=spec, coils=coils, links=links, spokes=spokes,
                   leads=leads, star=star, link_layer=link_layer)

def phase_labels(n_phases: int) -> List[str]:
    """Phase names A, B, C, ... for n_phases."""
    return [chr(ord("A") + i) for i in range(n_phases)]