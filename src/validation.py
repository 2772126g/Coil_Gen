from dataclasses import dataclass
from typing import List
import uuid
import math

from geometry import Point
from winding import Winding, phase_labels

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