from dataclasses import dataclass, field
from typing import List, Tuple
import math

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
