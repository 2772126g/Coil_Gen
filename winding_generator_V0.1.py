from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple
import math

Point = Tuple[float, float]


# ===========================================================================
# small polar / arc helpers (local maths frame, +y up)
# ===========================================================================
def polar(r: float, ang_rad: float) -> Point:
    return (r * math.cos(ang_rad), r * math.sin(ang_rad))


def arc_points(r: float, a0: float, a1: float, seg_deg: float = 2.0) -> List[Point]:
    """Chord-approximated arc at radius r from a0 to a1, no coarser than seg_deg."""
    n = max(2, int(abs(math.degrees(a1 - a0)) / seg_deg) + 1)
    return [polar(r, a0 + (a1 - a0) * i / (n - 1)) for i in range(n)]


def _dedupe(pts: List[Point], tol: float = 1e-6) -> List[Point]:
    out: List[Point] = []
    for q in pts:
        if not out or abs(q[0] - out[-1][0]) > tol or abs(q[1] - out[-1][1]) > tol:
            out.append(q)
    return out


def _mirror(pts: List[Point]) -> List[Point]:
    """Reflect a polyline across the x-axis (used for the mirror-paired layers)."""
    return [(x, -y) for x, y in pts]


# ===========================================================================
# [1] SPEC -- the single source of truth
# ===========================================================================
@dataclass(frozen=True)
class WindingSpec:
    """Complete winding parameter set. Defaults = validated 16-pole BIRDS
    baseline (mean radius 27 mm, 68 mm disc, 4 turns x 4 layers, 200/100 um).

    Frozen so a spec can't be mutated mid-build; make a new one via
    dataclasses.replace() to explore a change.
    """
    # --- topology ---
    n_poles: int = 16                  # rotor poles (coils align to pole pitch)
    n_phases: int = 3
    coils_per_phase: int = 8
    n_layers: int = 4                  # copper layers carrying coil turns
    target_turns_per_layer: int = 4

    # --- annulus (mm) ---
    r_inner_mm: float = 23.0
    r_outer_mm: float = 31.0

    # --- copper / fab (mm) ---
    trace_width_mm: float = 0.20
    trace_space_mm: float = 0.10       # min gap between adjacent same-layer traces
    via_pad_mm: float = 0.50           # buried-via landing-pad diameter
    via_drill_mm: float = 0.20         # buried-via drill

    # --- angular ---
    coil_arc_margin_deg: float = 1.0   # dead angle between adjacent coil slots

    # --- keep-out the winding must stay inside (mm, from centre) ---
    keepout_radius_mm: float = 33.88   # inscribed radius of the disc/coil keepout

    # --- inter-pair via bus sits just outside the outer radius (mm) ---
    bus_margin_mm: float = 0.60        # radial offset of the outer stitch via

    # --- names of the coil copper layers, inner->outer stack order ---
    coil_layers: tuple = ("In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu")

    # ---- derived topology ----
    @property
    def n_coils(self) -> int:
        return self.n_phases * self.coils_per_phase

    @property
    def pole_pairs(self) -> int:
        return self.n_poles // 2

    @property
    def slot_pitch_deg(self) -> float:
        return 360.0 / self.n_coils

    @property
    def coil_arc_deg(self) -> float:
        """Usable angular width of one coil after the inter-slot margin."""
        return self.slot_pitch_deg - self.coil_arc_margin_deg

    # ---- derived geometry ----
    @property
    def annulus_width_mm(self) -> float:
        return self.r_outer_mm - self.r_inner_mm

    @property
    def r_mean_mm(self) -> float:
        return 0.5 * (self.r_inner_mm + self.r_outer_mm)

    @property
    def turn_pitch_mm(self) -> float:
        """Centre-to-centre spacing of adjacent turns (one trace + one gap)."""
        return self.trace_width_mm + self.trace_space_mm

    @property
    def total_series_turns(self) -> int:
        """Effective series turns per phase = turns/layer x layers x coils/phase."""
        return self.target_turns_per_layer * self.n_layers * self.coils_per_phase

    @property
    def stitch_radii_mm(self) -> Tuple[float, float]:
        """The two centreline radii where buried vias join the mirror pairs.
        Derived from the annulus (inner half and inner quarter) so they sit
        clear of each other and of the coil tail; no magic numbers."""
        return (self.r_inner_mm + 0.50 * self.annulus_width_mm,   # e.g. 27.0
                self.r_inner_mm + 0.25 * self.annulus_width_mm)   # e.g. 25.0

    @property
    def bus_radius_mm(self) -> float:
        """Radius of the outer inter-pair stitch via (just outside the coil)."""
        return self.r_outer_mm + self.bus_margin_mm

    def __post_init__(self):
        # cheap invariants that would otherwise produce silent nonsense downstream
        if self.n_coils != self.n_phases * self.coils_per_phase:
            raise ValueError("n_coils inconsistency")
        if self.r_outer_mm <= self.r_inner_mm:
            raise ValueError("r_outer must exceed r_inner")
        if len(self.coil_layers) != self.n_layers:
            raise ValueError(
                f"n_layers={self.n_layers} but {len(self.coil_layers)} coil_layers named")
        if self.n_layers % 2 != 0:
            raise ValueError("mirror-pairing needs an even n_layers")


# ===========================================================================
# FEASIBILITY GATE -- does the requested winding physically fit?
# ===========================================================================
@dataclass
class FitResult:
    feasible: bool
    achievable_turns_per_layer: int
    turns_fit_radial: int
    turns_fit_tangential: int
    arc_width_inner_mm: float
    arc_width_mean_mm: float
    radial_fill: float                 # fraction of annulus width used by copper
    tangential_fill_inner: float       # fraction of inner arc used by copper
    total_series_turns: int
    notes: List[str] = field(default_factory=list)


def check_fit(spec: WindingSpec) -> FitResult:
    """Pure arithmetic feasibility check -- run before drawing anything.

    A wedge coil's nested loops stack BOTH radially (across the annulus width)
    and tangentially (across the wedge arc). The binding limits:
        radial     : how many turn-pitches fit across (r_outer - r_inner),
                     leaving the centre band for the return/via.
        tangential : how many fit across the arc width at the INNER radius
                     (narrowest, worst case). A nested loop consumes a turn
                     pitch on BOTH tangential sides, hence the factor of 2.
    """
    tp = spec.turn_pitch_mm

    # radial: reserve one via pad's width at the centre of the annulus
    usable_radial = spec.annulus_width_mm - spec.via_pad_mm
    turns_fit_radial = max(0, int(usable_radial // tp))

    arc_inner = math.radians(spec.coil_arc_deg) * spec.r_inner_mm
    arc_mean = math.radians(spec.coil_arc_deg) * spec.r_mean_mm
    usable_tangential = arc_inner - spec.via_pad_mm
    turns_fit_tangential = max(0, int(usable_tangential // (2 * tp)))

    achievable = min(turns_fit_radial, turns_fit_tangential,
                     spec.target_turns_per_layer)

    radial_fill = (spec.target_turns_per_layer * tp) / spec.annulus_width_mm
    tang_fill_inner = (spec.target_turns_per_layer * 2 * tp) / arc_inner

    notes: List[str] = []
    if turns_fit_radial < spec.target_turns_per_layer:
        notes.append(
            f"RADIAL binding: {turns_fit_radial} turns fit across "
            f"{spec.annulus_width_mm:.1f} mm (target {spec.target_turns_per_layer}).")
    if turns_fit_tangential < spec.target_turns_per_layer:
        notes.append(
            f"TANGENTIAL binding: {turns_fit_tangential} turns fit across "
            f"{arc_inner:.2f} mm inner arc (target {spec.target_turns_per_layer}).")
    if achievable == spec.target_turns_per_layer:
        notes.append("Target turns/layer achieved on both axes.")
    if tang_fill_inner > 1.0:
        notes.append(f"TANGENTIAL OVERFILL at inner radius "
                     f"({tang_fill_inner * 100:.0f}%).")
    if radial_fill > 1.0:
        notes.append(f"RADIAL OVERFILL ({radial_fill * 100:.0f}%).")

    feasible = (achievable >= 1 and radial_fill <= 1.0 and tang_fill_inner <= 1.0)

    return FitResult(
        feasible=feasible,
        achievable_turns_per_layer=achievable,
        turns_fit_radial=turns_fit_radial,
        turns_fit_tangential=turns_fit_tangential,
        arc_width_inner_mm=arc_inner,
        arc_width_mean_mm=arc_mean,
        radial_fill=radial_fill,
        tangential_fill_inner=tang_fill_inner,
        total_series_turns=(achievable * spec.n_layers * spec.coils_per_phase),
        notes=notes,
    )


def report_fit(spec: WindingSpec, fit: FitResult) -> str:
    """Human-readable feasibility summary (returns the text; caller prints)."""
    L = []
    add = L.append
    add("=" * 64)
    add("PCB STATOR WINDING -- FEASIBILITY GATE")
    add("=" * 64)
    add(f"  poles / pole-pairs : {spec.n_poles} / {spec.pole_pairs}")
    add(f"  coils (total)      : {spec.n_coils}  "
        f"({spec.coils_per_phase}/phase x {spec.n_phases})")
    add(f"  annulus            : ri={spec.r_inner_mm} ro={spec.r_outer_mm}  "
        f"(width {spec.annulus_width_mm:.1f} mm, mean r {spec.r_mean_mm:.1f})")
    add(f"  trace / space      : {spec.trace_width_mm*1e3:.0f}/"
        f"{spec.trace_space_mm*1e3:.0f} um  (pitch {spec.turn_pitch_mm*1e3:.0f} um)")
    add(f"  slot pitch / arc   : {spec.slot_pitch_deg:.1f} deg  "
        f"({spec.coil_arc_deg:.1f} usable)")
    add(f"  arc width @inner   : {fit.arc_width_inner_mm:.2f} mm   "
        f"@mean {fit.arc_width_mean_mm:.2f} mm")
    add("-" * 64)
    add(f"  turns fit RADIAL     : {fit.turns_fit_radial}")
    add(f"  turns fit TANGENTIAL : {fit.turns_fit_tangential}")
    add(f"  target turns/layer   : {spec.target_turns_per_layer}")
    add(f"  >> ACHIEVABLE/layer  : {fit.achievable_turns_per_layer}")
    add(f"  radial fill          : {fit.radial_fill*100:.0f}%")
    add(f"  tangential fill @ri  : {fit.tangential_fill_inner*100:.0f}%")
    add("-" * 64)
    add(f"  series turns/phase   : {fit.total_series_turns}"
        f"  (= {fit.achievable_turns_per_layer} x {spec.n_layers} layers "
        f"x {spec.coils_per_phase} coils)")
    add(f"  FEASIBLE             : {'YES' if fit.feasible else 'NO'}")
    if fit.notes:
        add("  notes:")
        for n in fit.notes:
            add(f"    - {n}")
    add("=" * 64)
    return "\n".join(L)


# ===========================================================================
# [2] SINGLE-LAYER COIL GEOMETRY
# ===========================================================================
# The corrected nested-loop coil. A wedge coil cannot spiral a full turn, so it
# is wound as concentric loops. The critical property (which the earlier
# serpentine version got wrong) is that every radial leg carries current in a
# CONSISTENT sense -- all "+a" legs go one way and all "-a" legs the other -- so
# the loops' MMF ADDS instead of cancelling. Each loop k is inset by one turn
# pitch radially (Ro-k*pitch, Ri+k*pitch) and by one angular pitch (dang) so the
# loops nest without touching. The path is one continuous open polyline from the
# outer +a corner (the phase-lead end) to the centreline (the tail end).
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


# ===========================================================================
# [3] FOUR-LAYER STACK -- mirror-paired, buried-via stitched
# ===========================================================================
# Segment/via record types kept deliberately plain (tuples) so the emit stage
# can serialise them without importing anything.
#   Segment = (a: Point, b: Point, layer: str)
#   Via     = (xy: Point, layer_a: str, layer_b: str)
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


def _rot(pt: Point, ang: float) -> Point:
    c, s = math.cos(ang), math.sin(ang)
    return (pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c)


def phase_labels(n_phases: int) -> List[str]:
    """Phase names A, B, C, ... for n_phases."""
    return [chr(ord("A") + i) for i in range(n_phases)]


# ===========================================================================
# [4] FULL WINDING -- N-coil array, series links, star neutral
# ===========================================================================
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


# ===========================================================================
# [5] VALIDATION SUITE
# ===========================================================================
# Geometry-level self-checks. These verify the winding is electrically sound
# (connected, no shorts) and physically buildable (inside keep-out, vias spaced,
# no same-layer crossings) BEFORE anything is emitted. The MMF-adding property
# of the mirror-pairing is a magnetic result verified separately by the EM model
# (winding_PATCHED) -- it is not re-derived here.
def _ccw(a: Point, b: Point, c: Point) -> float:
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def _seg_cross(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """Proper segment intersection, excluding shared endpoints (touching is OK)."""
    for q in (p1, p2):
        for r in (p3, p4):
            if abs(q[0] - r[0]) < 1e-7 and abs(q[1] - r[1]) < 1e-7:
                return False
    d1, d2 = _ccw(p3, p4, p1), _ccw(p3, p4, p2)
    d3, d4 = _ccw(p1, p2, p3), _ccw(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


@dataclass
class ValidationReport:
    ok: bool
    lines: List[str]

    def __str__(self) -> str:
        return "\n".join(self.lines)


def validate(wdg: Winding, min_hole_gap_mm: float = 0.45) -> ValidationReport:
    """Run the full geometric/electrical self-check on a built winding."""
    spec = wdg.spec
    labels = phase_labels(spec.n_phases)
    lines: List[str] = ["VALIDATION"]
    ok = True

    def key(pt: Point, layer: str):
        return (round(pt[0], 3), round(pt[1], 3), layer)

    # -- (1) per-coil topology: 1 component, exactly 2 loose ends, no branches --
    from collections import defaultdict
    bad_coils = 0
    for c in wdg.coils:
        uf = _UF()
        deg = defaultdict(int)
        for a, b, l in c.segments:
            uf.union(key(a, l), key(b, l)); deg[key(a, l)] += 1; deg[key(b, l)] += 1
        for xy, l1, l2 in c.vias:
            uf.union(key(xy, l1), key(xy, l2)); deg[key(xy, l1)] += 1; deg[key(xy, l2)] += 1
        comps = len({uf.find(k) for k in uf.p})
        loose = sum(1 for d in deg.values() if d == 1)
        branch = sum(1 for d in deg.values() if d > 2)
        if comps != 1 or loose != 2 or branch != 0:
            bad_coils += 1
    lines.append(f"  (1) per-coil topology : {'all ' + str(len(wdg.coils)) + ' PASS' if bad_coils == 0 else str(bad_coils) + ' FAIL'}")
    ok &= (bad_coils == 0)

    # -- (2) per-phase connectivity: coils + links + spoke form ONE net --
    # buried vias join layers at a point; links/spokes join across coils.
    for ph in labels:
        uf = _UF()
        chain = [c for c in wdg.coils if c.phase == ph]
        for c in chain:
            for a, b, l in c.segments:
                uf.union(key(a, l), key(b, l))
            for xy, l1, l2 in c.vias:
                uf.union(key(xy, l1), key(xy, l2))
        for a, b, l in wdg.links + wdg.spokes:
            # only this phase's links (identified by touching this phase's copper)
            uf.union(key(a, l), key(b, l))
        # recompute components restricted to this phase's coil nodes
        nodes = set()
        for c in chain:
            for a, b, l in c.segments:
                nodes.add(key(a, l)); nodes.add(key(b, l))
        comps = len({uf.find(n) for n in nodes})
        status = "OK" if comps == 1 else f"{comps} islands FAIL"
        lines.append(f"  (2) phase {ph} connectivity : {status}")
        ok &= (comps == 1)

    # -- (3) same-layer geometric crossings --
    # Coil copper is physical and must never cross another phase's coil on the
    # same layer (that would be a short). Links/spokes are drawn here as direct
    # tail->lead topology; on a real board they are bus-routed (separate radii/
    # layers) so they don't cross -- so link crossings are reported for
    # information, not treated as a failure of the winding itself.
    coil_by_layer = defaultdict(list)    # layer -> (a,b,phase) for COIL copper
    for c in wdg.coils:
        for a, b, l in c.segments:
            coil_by_layer[l].append((a, b, c.phase))
    coil_shorts = 0
    for l, ss in coil_by_layer.items():
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                if ss[i][2] == ss[j][2]:
                    continue
                if _seg_cross(ss[i][0], ss[i][1], ss[j][0], ss[j][1]):
                    coil_shorts += 1
    lines.append(f"  (3) coil cross-phase shorts : {coil_shorts} "
                 f"{'OK' if coil_shorts == 0 else 'FAIL'}")
    ok &= (coil_shorts == 0)

    # informational: how many direct links cross coil copper (-> bus-route these)
    link_cross = 0
    for a, b, l in wdg.links + wdg.spokes:
        for ca, cb, cph in coil_by_layer.get(l, []):
            if _seg_cross(a, b, ca, cb):
                link_cross += 1
    lines.append(f"      (info) direct links crossing coils : {link_cross} "
                 f"-> bus-route at integration")

    # -- (4) buried-via hole-to-hole spacing --
    holes = [xy for c in wdg.coils for xy, l1, l2 in c.vias]
    min_gap = 1e9
    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            d = math.hypot(holes[i][0] - holes[j][0], holes[i][1] - holes[j][1])
            if d < min_gap:
                min_gap = d
    lines.append(f"  (4) min via-hole gap : {min_gap:.3f} mm "
                 f"(need >= {min_hole_gap_mm}) {'OK' if min_gap >= min_hole_gap_mm else 'FAIL'}")
    ok &= (min_gap >= min_hole_gap_mm)

    # -- (5) keep-out: all coil copper inside the inscribed keep-out radius --
    maxr = max(math.hypot(a[0], a[1])
               for c in wdg.coils for a, b, l in c.segments)
    lines.append(f"  (5) max coil radius : {maxr:.2f} mm "
                 f"(keep-out {spec.keepout_radius_mm}) "
                 f"{'OK' if maxr <= spec.keepout_radius_mm else 'EXCEEDS'}")
    ok &= (maxr <= spec.keepout_radius_mm)

    lines.append(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return ValidationReport(ok=ok, lines=lines)


# ===========================================================================
# [6] BOARD-AGNOSTIC KiCAD EMIT
# ===========================================================================
# The ONLY stage that knows about a specific board: it takes a placement centre
# and a phase->net map and serialises the local geometry into KiCad tracks/vias.
# Coordinate transform: local maths (origin-centred, +y up) -> board
# (x + cx, -y + cy), because KiCad's y-axis points down.
import uuid as _uuid


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


# ===========================================================================
if __name__ == "__main__":
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
