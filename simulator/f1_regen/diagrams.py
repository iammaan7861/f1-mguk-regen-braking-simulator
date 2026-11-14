"""Schematic diagrams (block diagrams, flowchart, circuits) drawn with matplotlib."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

from .plots import COL, WIDTH, setup_style  # noqa: E402

setup_style()


def _canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def _box(ax, x, y, w, h, text, fc="#ffffff", ec="#333333", fs=8, bold=False, ls="-", lw=1.1):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=ec, lw=lw, ls=ls))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            weight="bold" if bold else "normal", linespacing=1.25)


def _diamond(ax, x, y, w, h, text, fc="#fff3cd", fs=7.5):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
                         closed=True, fc=fc, ec="#333333", lw=1.1))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def _arrow(ax, p1, p2, color="#333333", lw=1.3, style="-|>", ls="-", rad=0.0, ms=10):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, color=color, lw=lw, ls=ls,
                                 mutation_scale=ms, connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=0, shrinkB=0))


def _save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    return path


# ----------------------------------------------------------------------------------------
def fig_ers_architecture(path):
    fig, ax = _canvas(WIDTH, 4.1, 12, 7.8)
    fs = 7.0
    _box(ax, 1.35, 6.9, 2.4, 0.95, "Fuel tank\n(sustainable fuel)", fc="#f1f3f5", fs=fs)
    _box(ax, 4.75, 6.9, 2.5, 0.95, "ICE\n1.6 L V6 turbo", fc="#e9ecef", bold=True, fs=fs)
    _box(ax, 8.45, 6.9, 2.6, 0.95, "Turbo + MGU-H\n(2014-25 only)", fc="#ffffff", ls="--", fs=6.6)
    _box(ax, 4.75, 4.85, 2.5, 0.95, "Crankshaft and\ngearbox", fc="#e9ecef", fs=fs)
    _box(ax, 8.45, 4.85, 2.4, 0.95, "Rear wheels", fc="#dee2e6", bold=True, fs=fs)
    _box(ax, 10.65, 2.95, 2.3, 0.95, "Friction brakes\n(all 4 wheels)", fc="#ffe8cc", fs=fs)
    _box(ax, 4.75, 2.85, 2.5, 1.1, "MGU-K\nPM synchronous\nmotor-generator", fc="#e7f5ff", bold=True,
         fs=6.6)
    _box(ax, 1.35, 2.85, 2.4, 1.1, "CU-K\nbidirectional\ninverter", fc="#e7f5ff", fs=fs)
    _box(ax, 1.35, 0.75, 2.5, 0.95, "Energy store (ES)\nLi-ion battery", fc="#ebfbee", bold=True,
         fs=6.6)

    _arrow(ax, (2.55, 6.9), (3.5, 6.9))
    ax.text(3.02, 7.0, "fuel", fontsize=6.3, ha="center", va="bottom")
    _arrow(ax, (6.0, 6.9), (7.15, 6.9), ls="--")
    ax.text(6.57, 7.0, "exhaust", fontsize=6.3, ha="center", va="bottom")
    _arrow(ax, (4.75, 6.42), (4.75, 5.33), lw=2.0)
    _arrow(ax, (6.0, 4.85), (7.25, 4.85), lw=2.0, style="<|-|>")
    ax.text(6.35, 4.97, "torque", fontsize=6.3, ha="center", va="bottom")
    _arrow(ax, (4.35, 3.4), (4.35, 4.37), color=COL["deploy"], lw=1.8)
    _arrow(ax, (5.15, 4.37), (5.15, 3.4), color=COL["regen"], lw=1.8)
    _arrow(ax, (3.5, 3.05), (2.55, 3.05), color=COL["regen"], lw=1.6)
    _arrow(ax, (2.55, 2.65), (3.5, 2.65), color=COL["deploy"], lw=1.6)
    ax.text(3.02, 3.55, "3-phase\nAC", fontsize=6, ha="center", va="bottom")
    _arrow(ax, (1.05, 2.3), (1.05, 1.23), color=COL["regen"], lw=1.6)
    _arrow(ax, (1.65, 1.23), (1.65, 2.3), color=COL["deploy"], lw=1.6)
    ax.text(1.85, 1.77, "HV DC bus", fontsize=6, ha="left", va="center")
    _arrow(ax, (9.2, 4.37), (10.1, 3.43), lw=1.4)
    _arrow(ax, (11.2, 3.43), (11.6, 4.2), color=COL["friction"], lw=1.4)
    ax.text(11.65, 4.28, "heat", fontsize=6.3, ha="center", va="bottom", color=COL["friction"])
    _arrow(ax, (8.0, 6.42), (5.6, 3.4), color="0.55", ls="--", lw=1.0)
    ax.text(8.0, 5.75, "MGU-H energy\n(2014-25 only)", fontsize=5.8, color="0.45", ha="left",
            va="center")

    ax.text(3.95, 1.25, "Deployment (motoring):  ES \u2192 CU-K \u2192 MGU-K \u2192 wheels",
            color=COL["deploy"], fontsize=6.8, ha="left", va="center")
    ax.text(3.95, 0.8, "Regeneration (braking):  wheels \u2192 MGU-K \u2192 CU-K \u2192 ES",
            color=COL["regen"], fontsize=6.8, ha="left", va="center")
    ax.text(3.95, 0.35, "2026 limits: 350 kW, 8.5 MJ harvest per lap, 4 MJ usable SOC window",
            fontsize=6.3, ha="left", va="center", color="0.25")
    return _save(fig, path)


def fig_four_quadrant(path):
    fig, ax = plt.subplots(figsize=(WIDTH * 0.62, 3.2))
    ax.axhline(0, color="k", lw=1)
    ax.axvline(0, color="k", lw=1)
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 1.15, 1.15, color=COL["deploy"], alpha=0.13, lw=0))
    ax.add_patch(Rectangle((-1.15, 0), 1.15, 1.15, color=COL["regen"], alpha=0.15, lw=0))
    ax.add_patch(Rectangle((-1.15, -1.15), 2.3, 1.15, color="0.9", alpha=0.6, lw=0))
    ax.text(0.58, 0.72, "Quadrant I\nForward motoring\n(MGU-K deploys)\nT > 0, N > 0\nES -> wheels",
            ha="center", va="center", fontsize=7.2, color="#4b1d7a")
    ax.text(-0.58, 0.72, "Quadrant II\nForward braking\n(regenerative)\nT < 0, N > 0\nwheels -> ES",
            ha="center", va="center", fontsize=7.2, color="#1b5e20")
    ax.text(-0.58, -0.6, "Quadrant III\nReverse motoring\n(not used in F1)", ha="center", va="center",
            fontsize=7, color="0.45")
    ax.text(0.58, -0.6, "Quadrant IV\nReverse braking\n(not used in F1)", ha="center", va="center",
            fontsize=7, color="0.45")
    ax.annotate("", xy=(1.18, 0), xytext=(-1.18, 0), arrowprops=dict(arrowstyle="-|>", lw=1))
    ax.annotate("", xy=(0, 1.18), xytext=(0, -1.18), arrowprops=dict(arrowstyle="-|>", lw=1))
    ax.text(1.17, -0.08, "Torque T", ha="right", va="top", fontsize=7.5)
    ax.text(0.04, 1.16, "Speed N", ha="left", va="top", fontsize=7.5)
    return _save(fig, path)


def fig_rint(path):
    fig, ax = _canvas(WIDTH * 0.62, 2.3, 8, 4)
    ax.plot([1, 1], [0.8, 1.55], color="k", lw=1.4)
    ax.plot([1, 1], [2.45, 3.2], color="k", lw=1.4)
    ax.plot([0.55, 1.45], [2.45, 2.45], color="k", lw=2.2)
    ax.plot([0.75, 1.25], [2.2, 2.2], color="k", lw=3.2)
    ax.plot([0.55, 1.45], [1.95, 1.95], color="k", lw=2.2)
    ax.plot([0.75, 1.25], [1.7, 1.7], color="k", lw=3.2)
    ax.plot([1, 1], [1.7, 1.55], color="k", lw=1.4)
    ax.text(0.35, 2.08, r"$V_{oc}(SOC)$", ha="right", va="center", fontsize=8)
    ax.plot([1, 2.5], [3.2, 3.2], color="k", lw=1.4)
    zx = [2.5, 2.7, 2.9, 3.1, 3.3, 3.5, 3.7, 3.9, 4.1]
    zy = [3.2, 3.45, 2.95, 3.45, 2.95, 3.45, 2.95, 3.45, 3.2]
    ax.plot(zx, zy, color="k", lw=1.4)
    ax.text(3.3, 3.62, r"$R$", ha="center", fontsize=8.5)
    ax.plot([4.1, 6.0], [3.2, 3.2], color="k", lw=1.4)
    ax.plot([1, 6.0], [0.8, 0.8], color="k", lw=1.4)
    for yy, s in ((3.2, "+"), (0.8, "-")):
        ax.plot(6.0, yy, "o", mfc="white", mec="k", ms=6)
        ax.text(6.25, yy, s, fontsize=10, va="center")
    ax.annotate("", xy=(5.4, 3.2), xytext=(4.6, 3.2), arrowprops=dict(arrowstyle="-|>", lw=1.2))
    ax.text(5.0, 3.38, r"$I$", ha="center", fontsize=8.5)
    ax.annotate("", xy=(6.6, 3.0), xytext=(6.6, 1.0), arrowprops=dict(arrowstyle="<|-|>", lw=1))
    ax.text(6.75, 2.0, r"$V_t = V_{oc} \mp IR$", fontsize=8, va="center")
    ax.text(3.4, 1.85, "Rint equivalent circuit\nof the energy store", ha="center", fontsize=7.5,
            color="0.3")
    return _save(fig, path)


def fig_flowchart(path):
    fig, ax = _canvas(WIDTH, 8.6, 10.6, 17.4)
    c = "#e7f5ff"
    xc, bw, fs = 5.3, 8.2, 7.2
    left, right = xc - bw / 2, xc + bw / 2
    _box(ax, xc, 16.7, 2.6, 0.7, "START", fc="#d3f9d8", bold=True)
    _box(ax, xc, 15.55, bw, 1.0, "Inputs: track segments, vehicle (mass, aero, tyres),\n"
         "power unit and ERS limits, deployment strategy", fc="#f8f9fa", fs=fs)
    _box(ax, xc, 14.35, bw, 0.8, "Discretise the circuit ($ds$ = 2 m): curvature, x-y coordinates",
         fc=c, fs=fs)
    _box(ax, xc, 13.25, bw, 0.8, r"Cornering limit:  $m v^2 \kappa = \mu\,(m g + \frac{1}{2}\rho C_L A\,v^2)$",
         fc=c, fs=fs)
    _box(ax, xc, 12.15, bw, 0.8, "Backward pass: maximum-braking envelope (friction ellipse, 5 g cap)",
         fc=c, fs=fs)
    _box(ax, xc, 11.0, bw, 0.9, "Forward pass, step $i$: ERS command from the strategy\n"
         "(deploy power, 2026 speed taper, energy and SOC limits, super-clip)", fc="#f3f0ff", fs=fs)
    _box(ax, xc, 9.85, bw, 0.8, r"Full-throttle candidate speed $v_{acc}$ (ICE + MGU-K, traction limit)",
         fc="#f3f0ff", fs=fs)
    _diamond(ax, xc, 8.55, 4.8, 1.4, "$v_{acc}\\leq$ envelope\nspeed at node $i+1$ ?", fs=7)
    _box(ax, 2.45, 6.75, 2.4, 1.15, "FULL THROTTLE\nICE + MGU-K\ndeployment", fc="#e5dbff", fs=6.8)
    _diamond(ax, 7.7, 6.75, 2.9, 1.3, "Required\nforce $\\geq$ 0 ?", fs=6.8)
    _box(ax, 5.0, 4.75, 2.4, 1.15, "PART THROTTLE\nICE only\n(cornering)", fc="#fff3bf", fs=6.8)
    _box(ax, 8.15, 4.75, 3.2, 1.45, "BRAKING\nregen = min(rear share \u00d7 $P_b$,\n"
         "$P_{MGU-K}$, lap and SOC caps)\nfriction brakes = remainder", fc="#d3f9d8", fs=6.4)
    _box(ax, xc, 3.05, bw, 0.85, "Energy-store update (Rint): current, $I^2R$ loss, SOC, lap counters;\n"
         "time step $dt = 2\\,ds\\,/\\,(v_i + v_{i+1})$", fc="#ebfbee", fs=fs)
    _box(ax, xc, 1.85, bw, 0.75, "Lap results: lap time, energy flows, energy-balance check", fc=c, fs=fs)
    _box(ax, xc, 0.75, bw, 0.75, "Strategy tuner (bisection) \u2192 outputs: plots, tables, report",
         fc="#f8f9fa", fs=fs)

    for y1, y2 in ((16.35, 16.05), (15.05, 14.75), (13.95, 13.65), (12.85, 12.55), (11.75, 11.45),
                   (10.55, 10.25), (9.45, 9.25)):
        _arrow(ax, (xc, y1), (xc, y2))
    _arrow(ax, (xc - 2.4, 8.55), (2.45, 8.55), style="-")
    _arrow(ax, (2.45, 8.55), (2.45, 7.33))
    ax.text(2.55, 8.68, "yes", fontsize=7)
    _arrow(ax, (xc + 2.4, 8.55), (7.7, 7.4))
    ax.text(7.82, 8.0, "no", fontsize=7)
    _arrow(ax, (6.25, 6.75), (5.0, 6.75), style="-")
    _arrow(ax, (5.0, 6.75), (5.0, 5.33))
    ax.text(5.45, 6.86, "yes", fontsize=7)
    _arrow(ax, (7.7, 6.1), (7.7, 5.48))
    ax.text(7.82, 5.72, "no", fontsize=7)
    _arrow(ax, (2.45, 6.17), (2.45, 3.48))
    _arrow(ax, (5.0, 4.17), (5.0, 3.48))
    _arrow(ax, (7.7, 4.02), (7.7, 3.48))
    _arrow(ax, (xc, 2.62), (xc, 2.23))
    _arrow(ax, (xc, 1.47), (xc, 1.13))
    rx = right + 0.6
    _arrow(ax, (right, 3.05), (rx, 3.05), style="-")
    _arrow(ax, (rx, 3.05), (rx, 11.0), style="-")
    _arrow(ax, (rx, 11.0), (right, 11.0))
    ax.text(rx + 0.12, 7.2, "next step $i+1$", rotation=90, fontsize=7, ha="left", va="center")
    lx = left - 0.45
    _arrow(ax, (left, 1.85), (lx, 1.85), style="-", color="0.4")
    _arrow(ax, (lx, 1.85), (lx, 11.0), style="-", color="0.4")
    _arrow(ax, (lx, 11.0), (left, 11.0), color="0.4")
    ax.text(lx - 0.1, 6.0, "re-run lap with tuned strategy", rotation=90, fontsize=6.5, ha="right",
            va="center", color="0.35")
    return _save(fig, path)


def fig_software_architecture(path):
    fig, ax = _canvas(WIDTH, 3.9, 12, 7.4)
    ax.add_patch(FancyBboxPatch((0.2, 3.35), 11.6, 3.75, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#f8f9fa", ec="#adb5bd", lw=1))
    ax.text(0.45, 6.82, "Core model: Python package  f1_regen", fontsize=7.5, weight="bold", va="center")
    fs = 6.2
    mods = [
        (1.7, 5.7, "config.py\nvehicle, power unit,\nstrategy presets"),
        (4.57, 5.7, "track.py\nstraights + arcs,\nclosure, x-y map"),
        (7.43, 5.7, "ers.py\nRint battery,\n2026 deploy taper"),
        (10.3, 5.7, "simulation.py\nQSS lap model,\nenergy book-keeping"),
        (3.13, 4.25, "strategy.py\nbisection tuning\nof deployment"),
        (6.0, 4.25, "analysis.py\nscenarios, sweeps,\nbraking zones"),
        (8.87, 4.25, "plots.py, diagrams.py\nreport figures"),
    ]
    for x, y, t in mods:
        _box(ax, x, y, 2.65, 1.05, t, fc="#e7f5ff", fs=fs)
    apps = [
        (1.6, 1.85, "app.py\nStreamlit dashboard\n(interactive what-if)", "#fff3bf"),
        (4.53, 1.85, "run_analysis.py\nbatch study \u2192 figures,\nresults.json, CSV", "#d3f9d8"),
        (7.47, 1.85, "tests/\nenergy-balance and\nlimit checks", "#ffe3e3"),
        (10.4, 1.85, "builders/\nreport (DOCX, PDF),\nslides (PPTX)", "#f3f0ff"),
    ]
    for x, y, t, fc in apps:
        _box(ax, x, y, 2.65, 1.15, t, fc=fc, fs=fs)
    for x, _, _, _ in apps:
        _arrow(ax, (x, 3.32), (x, 2.45), color="0.35")
    yb = 0.75
    _arrow(ax, (4.53, 1.27), (4.53, yb), color="0.35", style="-")
    _arrow(ax, (4.53, yb), (10.4, yb), color="0.35", style="-")
    _arrow(ax, (10.4, yb), (10.4, 1.27), color="0.35")
    ax.text(7.47, yb - 0.12, "results.json and figures feed the report and slide builders", fontsize=6.2,
            ha="center", va="top", color="0.35")
    return _save(fig, path)
