from typing import List, Tuple
import math

Point = Tuple[float, float]

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

def _rot(pt: Point, ang: float) -> Point:
    c, s = math.cos(ang), math.sin(ang)
    return (pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c)