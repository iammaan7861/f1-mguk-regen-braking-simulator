"""Circuit model built from straights and constant-radius arcs.

The centre line is discretised into short steps. Each step carries its length
``ds`` and signed curvature ``kappa`` (+ left / anticlockwise, - right).
Two designated straights are stretched or shortened so that the layout closes
exactly on itself, which keeps the track map tidy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class Segment:
    length_m: float = 0.0      # straight length (ignored for arcs)
    radius_m: float = 0.0      # arc radius; 0 means straight
    angle_deg: float = 0.0     # signed turning angle of an arc
    label: str = ""

    @property
    def is_arc(self) -> bool:
        return self.radius_m > 0.0

    @property
    def length(self) -> float:
        if self.is_arc:
            return self.radius_m * math.radians(abs(self.angle_deg))
        return self.length_m

    @property
    def curvature(self) -> float:
        if not self.is_arc:
            return 0.0
        return math.copysign(1.0 / self.radius_m, self.angle_deg)


def straight(length_m: float, label: str = "") -> Segment:
    return Segment(length_m=length_m, label=label)


def arc(radius_m: float, angle_deg: float, label: str = "") -> Segment:
    return Segment(radius_m=radius_m, angle_deg=angle_deg, label=label)


def _close_layout(segments: list[Segment], idx: Sequence[int], heading0: float) -> list[Segment]:
    """Adjust the lengths of two non-parallel straights so the loop closes."""
    total_turn = sum(s.angle_deg for s in segments if s.is_arc)
    if abs(abs(total_turn) - 360.0) > 1e-6:
        raise ValueError(f"Arcs must turn through +/-360 deg in total (got {total_turn:.2f})")

    heading = heading0
    dx = dy = 0.0
    headings = []
    for seg in segments:
        headings.append(heading)
        if seg.is_arc:
            k = seg.curvature
            dtheta = k * seg.length
            dx += (math.sin(heading + dtheta) - math.sin(heading)) / k
            dy += (-math.cos(heading + dtheta) + math.cos(heading)) / k
            heading += dtheta
        else:
            dx += seg.length_m * math.cos(heading)
            dy += seg.length_m * math.sin(heading)

    i, j = idx
    a11, a21 = math.cos(headings[i]), math.sin(headings[i])
    a12, a22 = math.cos(headings[j]), math.sin(headings[j])
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-6:
        raise ValueError("Closure straights must not be parallel")
    da = (-dx * a22 + dy * a12) / det
    db = (-dy * a11 + dx * a21) / det
    out = list(segments)
    for k, d in ((i, da), (j, db)):
        new_len = out[k].length_m + d
        if new_len <= 5.0:
            raise ValueError(f"Closure made straight {k} too short ({new_len:.1f} m)")
        out[k] = Segment(length_m=new_len, label=out[k].label)
    return out


class Track:
    """Discretised closed circuit."""

    def __init__(
        self,
        name: str,
        segments: Sequence[Segment],
        ds: float = 2.0,
        closure_straights: Optional[Sequence[int]] = None,
        heading0_deg: float = 90.0,
        description: str = "",
        aero_trim: str = "low",
    ):
        self.name = name
        self.description = description
        self.aero_trim = aero_trim
        heading0 = math.radians(heading0_deg)
        segs = list(segments)
        if closure_straights:
            segs = _close_layout(segs, closure_straights, heading0)
        self.segments = segs

        ds_list, kap_list, seg_idx = [], [], []
        for k, seg in enumerate(segs):
            n = max(1, int(round(seg.length / ds)))
            ds_list.extend([seg.length / n] * n)
            kap_list.extend([seg.curvature] * n)
            seg_idx.extend([k] * n)

        self.ds = np.asarray(ds_list)
        self.kappa = np.asarray(kap_list)
        self.segment_index = np.asarray(seg_idx)
        self.n_steps = len(self.ds)
        self.s = np.concatenate(([0.0], np.cumsum(self.ds)))
        self.s_mid = 0.5 * (self.s[:-1] + self.s[1:])
        self.length = float(self.s[-1])

        x = np.zeros(self.n_steps + 1)
        y = np.zeros(self.n_steps + 1)
        th = np.zeros(self.n_steps + 1)
        th[0] = heading0
        for i in range(self.n_steps):
            mid = th[i] + 0.5 * self.kappa[i] * self.ds[i]
            x[i + 1] = x[i] + self.ds[i] * math.cos(mid)
            y[i + 1] = y[i] + self.ds[i] * math.sin(mid)
            th[i + 1] = th[i] + self.kappa[i] * self.ds[i]
        self.x, self.y, self.heading = x, y, th

        # corner labels at arc mid-points
        self.corners: list[tuple[str, float, float, float]] = []
        for k, seg in enumerate(segs):
            if seg.is_arc and seg.label:
                steps = np.nonzero(self.segment_index == k)[0]
                mid_step = steps[len(steps) // 2]
                self.corners.append((seg.label, float(self.s_mid[mid_step]),
                                     float(x[mid_step]), float(y[mid_step])))

    @property
    def n_corners(self) -> int:
        return len(self.corners)

    def next_corner_after(self, s_pos: float) -> str:
        for label, s_c, _, _ in self.corners:
            if s_c >= s_pos:
                return label
        return self.corners[0][0] if self.corners else ""

    def summary(self) -> dict:
        arcs = [s for s in self.segments if s.is_arc]
        return {
            "name": self.name,
            "length_m": round(self.length, 1),
            "n_steps": self.n_steps,
            "n_arcs": len(arcs),
            "n_named_corners": self.n_corners,
            "min_radius_m": min(s.radius_m for s in arcs),
            "longest_straight_m": round(max(s.length_m for s in self.segments if not s.is_arc), 1),
        }


def monza_like(ds: float = 2.0) -> Track:
    """High-speed circuit loosely modelled on Monza (clockwise, ~5.8 km)."""
    segs = [
        straight(640, "Main straight"),
        arc(22, -80, "T1 Rettifilo"),
        straight(20),
        arc(25, 80, "T2 Rettifilo"),
        straight(120),
        arc(350, -90, "T3 Curva Grande"),
        straight(420),
        arc(45, 50, "T4 Roggia"),
        straight(15),
        arc(50, -50, "T5 Roggia"),
        straight(300),
        arc(90, -60, "T6 Lesmo 1"),
        straight(180),
        arc(85, -58, "T7 Lesmo 2"),
        straight(1000, "Serraglio"),
        arc(110, 30, "T8 Ascari"),
        straight(10),
        arc(90, -40, "T9 Ascari"),
        straight(10),
        arc(200, 10, "T10 Ascari"),
        straight(950, "Back straight"),
        arc(95, -52, "T11 Parabolica"),
        arc(140, -50),
        arc(220, -50),
        straight(540, "Main straight"),
    ]
    return Track(
        "Monza-like high-speed circuit",
        segs,
        ds=ds,
        closure_straights=(0, 6),
        heading0_deg=90.0,
        description="Long straights and heavy braking into slow chicanes; low-downforce trim.",
        aero_trim="low",
    )


def street_circuit(ds: float = 2.0) -> Track:
    """Stop-and-go street circuit with many slow 90-degree corners (anticlockwise)."""
    segs = [
        straight(500, "Main straight"),
        arc(18, 90, "T1"),
        straight(220),
        arc(22, -90, "T2"),
        straight(160),
        arc(26, 90, "T3"),
        straight(750, "North straight"),
        arc(15, 90, "T4"),
        straight(320),
        arc(45, -45, "T5"),
        straight(90),
        arc(45, 45, "T6"),
        straight(420),
        arc(20, 90, "T7"),
        straight(800, "South straight"),
        arc(16, 90, "T8"),
        straight(260),
        arc(35, -35, "T9"),
        straight(30),
        arc(35, 35, "T10"),
        straight(300, "Main straight"),
    ]
    return Track(
        "Street circuit (stop-and-go)",
        segs,
        ds=ds,
        closure_straights=(6, 12),
        heading0_deg=0.0,
        description="Frequent slow corners joined by short straights; high-downforce trim.",
        aero_trim="high",
    )


TRACKS = {
    "Monza-like (high speed)": monza_like,
    "Street circuit (stop-and-go)": street_circuit,
}
