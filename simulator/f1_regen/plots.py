"""Matplotlib figures of simulation results for the project report."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from .ers import deploy_power_limit_kw  # noqa: E402
from .simulation import MODE_BRAKE, MODE_FULL, MODE_PART, LapResult  # noqa: E402

COL = {
    "ice": "#6c757d",
    "2009": "#9467bd",
    "2014-25": "#1f77b4",
    "2026": "#d62728",
    "regen": "#2ca02c",
    "friction": "#ff7f0e",
    "deploy": "#7b2cbf",
    "clip": "#17a2b8",
    "loss": "#8c564b",
    "brake": "#343a40",
    "part": "#f2c14e",
}
WIDTH = 6.3  # inches, A4 text width


def setup_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


setup_style()


def _save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    return path


def corner_groups(track, gap_m: float = 200.0) -> list[tuple[str, str, float, float, float]]:
    """Merge corners closer than gap_m: (short label, long label, s, x, y), e.g. 'T8-10', 'T8-10 Ascari'."""
    groups: list[list[tuple]] = []
    for c in track.corners:
        if groups and c[1] - groups[-1][-1][1] < gap_m:
            groups[-1].append(c)
        else:
            groups.append([c])
    out = []
    for g in groups:
        nums = [c[0].split()[0] for c in g]
        names = list(dict.fromkeys(" ".join(c[0].split()[1:]).rstrip(" 0123456789") for c in g))
        short = nums[0] if len(g) == 1 else f"{nums[0]}-{nums[-1].lstrip('T')}"
        name = " / ".join(n for n in names if n)
        if len(g) == 1:
            name = " ".join(g[0][0].split()[1:])
        out.append((short, f"{short} {name}".strip(), float(np.mean([c[1] for c in g])),
                    float(np.mean([c[2] for c in g])), float(np.mean([c[3] for c in g]))))
    return out


def _corner_ticks(ax, track, scale: float = 1e-3):
    for short, _, s_c, _, _ in corner_groups(track, gap_m=160.0):
        ax.axvline(s_c * scale, color="0.85", lw=0.6, zorder=0)
        ax.text(s_c * scale, 1.01, short, transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=6.3, color="0.35")


def _colored_line(ax, x, y, c, cmap, norm, lw=3.0):
    pts = np.column_stack([x, y]).reshape(-1, 1, 2)
    segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(segs, cmap=cmap, norm=norm, linewidths=lw, capstyle="round")
    lc.set_array(c if np.ma.isMaskedArray(c) else np.asarray(c))
    ax.add_collection(lc)
    return lc


def _track_frame(ax, track, pad=80):
    ax.set_xlim(track.x.min() - pad, track.x.max() + pad)
    ax.set_ylim(track.y.min() - pad, track.y.max() + pad)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)


def _start_marker(ax, track):
    x0, y0, th = track.x[0], track.y[0], track.heading[0]
    nx, ny = -np.sin(th), np.cos(th)
    # put the label on the outside of the circuit
    if (track.x.mean() - x0) * nx + (track.y.mean() - y0) * ny > 0:
        nx, ny = -nx, -ny
    ax.plot([x0 - 45 * nx, x0 + 45 * nx], [y0 - 45 * ny, y0 + 45 * ny], color="k", lw=2.5)
    ax.annotate("", xy=(x0 + 160 * np.cos(th), y0 + 160 * np.sin(th)), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color="k", lw=1.2))
    ax.text(x0 + 70 * nx, y0 + 70 * ny, "S/F", fontsize=7,
            ha="left" if nx > 0.3 else ("right" if nx < -0.3 else "center"),
            va="bottom" if ny > 0.3 else ("top" if ny < -0.3 else "center"))


# ----------------------------------------------------------------------------------------
def fig_tracks(tracks, path):
    fig, axes = plt.subplots(1, len(tracks), figsize=(WIDTH, 3.6))
    for ax, tr in zip(np.atleast_1d(axes), tracks):
        ax.plot(tr.x, tr.y, color="0.15", lw=2.2)
        _start_marker(ax, tr)
        cx, cy = 0.5 * (tr.x.min() + tr.x.max()), 0.5 * (tr.y.min() + tr.y.max())
        for _, label, _, x, y in corner_groups(tr):
            dx, dy = x - cx, y - cy
            d = np.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            ax.plot(x, y, "o", ms=2.5, color="#b22222")
            ax.annotate(label, (x, y), xytext=(x + 110 * ux, y + 110 * uy), fontsize=6.3,
                        ha="left" if ux > 0.35 else ("right" if ux < -0.35 else "center"),
                        va="bottom" if uy > 0.35 else ("top" if uy < -0.35 else "center"),
                        color="#b22222")
        _track_frame(ax, tr, pad=330)
        ax.set_title(f"{tr.name}\n{tr.length / 1000:.2f} km, {tr.n_corners} named corners", fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


def fig_track_maps(lap: LapResult, path):
    tr = lap.track
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.9))
    v = 0.5 * (lap.v[:-1] + lap.v[1:]) * 3.6
    norm = plt.Normalize(v.min(), v.max())
    lc = _colored_line(axes[0], tr.x, tr.y, v, "turbo", norm)
    cb = fig.colorbar(lc, ax=axes[0], shrink=0.75, pad=0.02)
    cb.set_label("Speed (km/h)")
    _start_marker(axes[0], tr)
    _track_frame(axes[0], tr, pad=120)
    axes[0].set_title("(a) Speed")

    cat = np.zeros(tr.n_steps)
    cat[lap.mode == MODE_PART] = 1
    cat[(lap.mode == MODE_FULL)] = 2
    cat[(lap.mode == MODE_FULL) & (lap.p_deploy > 1e3)] = 3
    cat[(lap.mode == MODE_FULL) & (lap.p_clip > 1e3)] = 4
    cat[lap.mode == MODE_BRAKE] = 5
    colors = [COL["part"], COL["part"], COL["ice"], COL["deploy"], COL["clip"], COL["regen"]]
    cmap = matplotlib.colors.ListedColormap(colors)
    norm2 = matplotlib.colors.BoundaryNorm(np.arange(-0.5, 6.5, 1), cmap.N)
    _colored_line(axes[1], tr.x, tr.y, cat, cmap, norm2)
    _start_marker(axes[1], tr)
    _track_frame(axes[1], tr, pad=120)
    axes[1].set_title("(b) ERS operating mode")
    handles = [Line2D([], [], color=COL["regen"], lw=3, label="Braking + MGU-K regeneration"),
               Line2D([], [], color=COL["deploy"], lw=3, label="Full throttle + MGU-K deployment"),
               Line2D([], [], color=COL["ice"], lw=3, label="Full throttle, ICE only"),
               Line2D([], [], color=COL["part"], lw=3, label="Part throttle (cornering)")]
    if (lap.p_clip > 1e3).any():
        handles.insert(3, Line2D([], [], color=COL["clip"], lw=3, label="Super-clipping (harvest)"))
    axes[1].legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.32), fontsize=7,
                   ncol=1, frameon=False)
    fig.tight_layout()
    return _save(fig, path)


def fig_speed_profiles(laps: dict, path, colors: dict | None = None):
    fig, ax = plt.subplots(figsize=(WIDTH, 2.9))
    first = next(iter(laps.values()))
    for label, lap in laps.items():
        c = (colors or {}).get(label)
        ax.plot(lap.s / 1000, lap.v * 3.6, lw=1.2, label=f"{label} ({lap.lap_time:.2f} s)", color=c)
    _corner_ticks(ax, first.track)
    ax.set_xlabel("Distance from start/finish line (km)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_xlim(0, first.track.length / 1000)
    ax.legend(loc="lower right", ncol=1)
    fig.tight_layout()
    return _save(fig, path)


def fig_braking_vs_regen(lap_a: LapResult, lap_b: LapResult, path, zone: dict, label_a="2026",
                         label_b="2014-25"):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.9), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    s = lap_a.s_mid / 1000
    ax.fill_between(s, lap_a.p_brake / 1e3, color="0.82", label="Total braking power at wheels", lw=0)
    ax.plot(s, lap_a.p_regen / 1e3, color=COL["2026"], lw=1.1, label=f"MGU-K recovered ({label_a})")
    ax.plot(lap_b.s_mid / 1000, lap_b.p_regen / 1e3, color=COL["2014-25"], lw=1.1,
            label=f"MGU-K recovered ({label_b})")
    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Power (kW)")
    ax.set_title("(a) Braking power vs recovered power over a lap")
    ax.set_xlim(0, lap_a.track.length / 1000)
    ax.legend(loc="upper right", fontsize=7)

    ax = axes[1]
    for lap, col, lab in ((lap_a, COL["2026"], label_a), (lap_b, COL["2014-25"], label_b)):
        s0 = zone["s_start_m"]
        m = (lap.s_mid >= s0 - 20) & (lap.s_mid <= s0 + zone["length_m"] + 60)
        t = np.cumsum(lap.dt[m]) - lap.dt[m][0]
        if lap is lap_a:
            ax.fill_between(t, lap.p_brake[m] / 1e3, color="0.82", lw=0, label="Braking power")
            ax.fill_between(t, lap.p_regen[m] / 1e3, color=COL["regen"], alpha=0.5, lw=0,
                            label="Recovered (2026)")
        ax.plot(t, lap.p_regen[m] / 1e3, color=col, lw=1.2)
        ax.axhline(lap.pu.mguk_power_kw, color=col, ls="--", lw=0.8)
        ax.text(t[-1], lap.pu.mguk_power_kw + 25, f"{lap.pu.mguk_power_kw:.0f} kW limit ({lab})",
                ha="right", va="bottom", fontsize=6.3, color=col,
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.5))
    ax.set_xlabel("Time from start of braking (s)")
    ax.set_title(f"(b) Braking into {zone['corner'].split()[0]}")
    ax.legend(loc="upper right", fontsize=6.5)
    fig.tight_layout()
    return _save(fig, path)


def fig_soc(laps: dict, quali: LapResult, path, colors: dict | None = None):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8))
    ax = axes[0]
    for label, lap in laps.items():
        ax.plot(lap.s / 1000, lap.soc * 100, lw=1.3, label=label, color=(colors or {}).get(label))
    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("State of charge of ES window (%)")
    ax.set_ylim(-3, 103)
    ax.set_title("(a) Energy-store state of charge")
    ax.legend(fontsize=6.5, loc="upper right")
    ax = axes[1]
    t = quali.t[1:]
    e_h = np.cumsum(quali.p_harvest * quali.dt) / 1e6
    e_d = np.cumsum(quali.p_deploy * quali.dt) / 1e6
    ax.plot(t, e_h, color=COL["regen"], lw=1.4, label="Cumulative energy recovered")
    ax.plot(t, e_d, color=COL["deploy"], lw=1.4, label="Cumulative energy deployed")
    ax.set_xlabel("Lap time (s)")
    ax.set_ylabel("Energy (MJ)")
    ax.set_title("(b) Qualifying lap energy counters (2026)")
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    return _save(fig, path)


def fig_battery(lap: LapResult, path):
    fig, axes = plt.subplots(3, 1, figsize=(WIDTH, 4.4), sharex=True)
    t = lap.t[1:]
    axes[0].plot(t, lap.i_batt, color=COL["2026"], lw=0.9)
    axes[0].axhline(0, color="k", lw=0.5)
    axes[0].set_ylabel("Current (A)")
    axes[0].set_title("Energy-store electrical behaviour (+ discharge / - charge)")
    axes[1].plot(t, lap.v_batt, color=COL["2014-25"], lw=0.9)
    axes[1].set_ylabel("Terminal\nvoltage (V)")
    axes[2].fill_between(t, lap.p_batt_loss / 1e3, color=COL["loss"], lw=0, alpha=0.8)
    axes[2].set_ylabel("I$^2$R loss (kW)")
    axes[2].set_xlabel("Time (s)")
    fig.tight_layout()
    return _save(fig, path)


def fig_energy_breakdown(flows: dict, balance: dict, path):
    """(a) fate of braking energy per configuration, (b) lap energy balance (one lap)."""
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.1), gridspec_kw={"width_ratios": [1.05, 1]})
    ax = axes[0]
    labels = list(flows.keys())
    rec = np.array([flows[k]["regen_dc"] for k in labels])
    loss = np.array([flows[k]["regen_gearbox_loss"] + flows[k]["regen_emachine_loss"] for k in labels])
    fric = np.array([flows[k]["friction_heat"] for k in labels])
    y = np.arange(len(labels))
    ax.barh(y, rec, color=COL["regen"], label="Stored in ES (DC)")
    ax.barh(y, loss, left=rec, color=COL["loss"], label="Conversion losses")
    ax.barh(y, fric, left=rec + loss, color=COL["friction"], label="Friction-brake heat")
    for yi, r, tot in zip(y, rec, rec + loss + fric):
        ax.text(tot + 0.15, yi, f"{100 * r / tot:.0f} %", va="center", fontsize=7)
    ax.set_yticks(y, [lab.replace(" race", "\nrace").replace(" qualifying", "\nqualifying")
                      for lab in labels], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Braking energy per lap (MJ)\n(% = share stored in the ES)")
    ax.set_xlim(0, max(rec + loss + fric) * 1.22)
    ax.set_title("(a) Where the braking energy goes")
    ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.45, -0.32), ncol=2, frameon=False)

    ax = axes[1]
    items = [("ICE heat (exhaust, coolant)", balance["ice_heat"], "#adb5bd"),
             ("Aerodynamic drag", balance["drag"], "#4c78a8"),
             ("Friction-brake heat", balance["friction_heat"], COL["friction"]),
             ("Rolling resistance", balance["rolling"], "#72b7b2"),
             ("Gearbox losses", balance["gearbox_loss"], "#b279a2"),
             ("MGU-K + inverter losses", balance["emachine_loss"], COL["loss"]),
             ("Battery I$^2$R loss", balance["battery_loss"], "#e45756")]
    vals = np.array([max(0.0, v) for _, v, _ in items])
    ax.pie(vals, colors=[c for _, _, c in items], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.42, edgecolor="white", linewidth=0.8))
    ax.text(0, 0, f"Fuel\n{balance['fuel']:.1f} MJ", ha="center", va="center", fontsize=8)
    ax.legend([f"{n}: {v:.2f} MJ" for (n, _, _), v in zip(items, vals)], loc="upper center",
              bbox_to_anchor=(0.5, 0.02), fontsize=6.3, frameon=False, ncol=1)
    ax.set_title("(b) Lap energy sinks (2026 race lap)")
    fig.tight_layout(w_pad=2.5)
    return _save(fig, path)


def fig_era_comparison(scen: dict, path):
    eras = ["2009", "2014-25", "2026"]
    names = {"2009": "2009\n60 kW", "2014-25": "2014-25\n120 kW", "2026": "2026\n350 kW"}
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 2.7))
    x = np.arange(len(eras))
    w = 0.38
    gain_r = [scen[f"{e} ICE only"]["lap_time_s"] - scen[f"{e} race"]["lap_time_s"] for e in eras]
    gain_q = [scen[f"{e} ICE only"]["lap_time_s"] - scen[f"{e} qualifying"]["lap_time_s"] for e in eras]
    axes[0].bar(x - w / 2, gain_r, w, color="#4c78a8", label="Race lap")
    axes[0].bar(x + w / 2, gain_q, w, color="#f58518", label="Qualifying lap")
    axes[0].set_ylabel("Lap time gained (s)")
    axes[0].set_title("(a) Lap time gain from ERS")
    axes[0].legend(fontsize=7)
    regen = [scen[f"{e} race"]["regen_MJ"] for e in eras]
    dep = [scen[f"{e} qualifying"]["deploy_MJ"] for e in eras]
    axes[1].bar(x - w / 2, regen, w, color=COL["regen"], label="Recovered (race)")
    axes[1].bar(x + w / 2, dep, w, color=COL["deploy"], label="Deployed (qualifying)")
    axes[1].set_ylabel("Energy per lap (MJ)")
    axes[1].set_title("(b) Electrical energy per lap")
    axes[1].set_ylim(0, max(dep + regen) * 1.45)
    axes[1].legend(fontsize=6.5, loc="upper left")
    axes[0].set_ylim(0, max(gain_q + gain_r) * 1.3)
    axes[0].legend(fontsize=6.5, loc="upper left")
    rec = [scen[f"{e} race"]["recovery_pct"] for e in eras]
    axes[2].bar(x, rec, 0.55, color=[COL[e] for e in eras])
    for xi, r in zip(x, rec):
        axes[2].text(xi, r + 0.5, f"{r:.1f}%", ha="center", fontsize=7)
    axes[2].set_ylabel("Braking energy recovered (%)")
    axes[2].set_title("(c) Recovery ratio")
    axes[2].set_ylim(0, max(rec) * 1.18)
    for ax in axes:
        ax.set_xticks(x, [names[e] for e in eras], fontsize=7)
    fig.tight_layout()
    return _save(fig, path)


def fig_strategy(rows: list, path):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8), gridspec_kw={"width_ratios": [1, 1.5]})
    labels = [r["label"] for r in rows]
    d = [r["delta_s"] for r in rows]
    cols = ["#2ca02c", "#4c78a8", "#f58518", "#d62728"]
    axes[0].barh(labels, d, color=cols[: len(rows)])
    for i, (val, r) in enumerate(zip(d, rows)):
        axes[0].text(val + 0.02, i, f"+{val:.2f} s" if val > 0 else f"{r['lap_time_s']:.2f} s (best)",
                     va="center", fontsize=7)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Lap time vs best (s)")
    axes[0].set_xlim(0, max(d) * 1.6 + 0.1)
    axes[0].set_title("(a) Same energy, different use")
    ax = axes[1]
    for r, c in zip(rows, cols):
        lap = r["lap"]
        ax.plot(lap.s_mid / 1000, lap.p_deploy / 1e3, lw=0.9, color=c, label=r["label"])
    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("MGU-K deployment (kW)")
    ax.set_title("(b) Where the energy is deployed")
    ax.set_xlim(0, rows[0]["lap"].track.length / 1000)
    ax.set_ylim(0, 470)
    ax.legend(fontsize=6.3, loc="upper center", ncol=2, frameon=True)
    fig.tight_layout()
    return _save(fig, path)


def fig_deploy_maps(lap_a: LapResult, lap_b: LapResult, path, title_a: str, title_b: str):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.3))
    vmax = max(lap_a.p_deploy.max(), lap_b.p_deploy.max()) / 1e3
    norm = plt.Normalize(0, vmax)
    cmap = matplotlib.colormaps["plasma"].copy()
    cmap.set_bad(alpha=0.0)
    for ax, lap, title in ((axes[0], lap_a, title_a), (axes[1], lap_b, title_b)):
        tr = lap.track
        ax.plot(tr.x, tr.y, color="0.82", lw=3.2, zorder=0)
        p = np.ma.masked_less(lap.p_deploy / 1e3, 1.0)
        lc = _colored_line(ax, tr.x, tr.y, p, cmap, norm, lw=4.2)
        _start_marker(ax, tr)
        _track_frame(ax, tr, pad=150)
        ax.set_title(f"{title}\nlap {lap.lap_time:.2f} s, {lap.summary['deploy_MJ']:.2f} MJ deployed",
                     fontsize=8.5)
    cb = fig.colorbar(lc, ax=axes, shrink=0.7, pad=0.02)
    cb.set_label("MGU-K deployment (kW); grey = none")
    return _save(fig, path)


def fig_superclip(sweep: dict, path):
    rows = sweep["rows"]
    th = [r["threshold_kph"] for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.6))
    ax2 = ax.twinx()
    ax2.bar(th, [r["clip_MJ"] for r in rows], width=3.5, color=COL["clip"], alpha=0.45,
            label="Energy harvested by super-clipping")
    ax2.set_ylabel("Super-clip energy (MJ/lap)")
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.plot(th, [r["lap_time_s"] for r in rows], "o-", color=COL["2026"], lw=1.4, ms=4,
            label="Lap time with super-clipping")
    ax.axhline(sweep["baseline_lap_time_s"], color="k", ls="--", lw=0.8,
               label="Braking regeneration only")
    ax.set_xlabel("Super-clipping starts above (km/h)")
    ax.set_ylabel("Lap time (s)")
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right")
    fig.tight_layout()
    return _save(fig, path)


def fig_power_sweep(sweeps: dict, path):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8))
    styles = [("#d62728", "o"), ("#1f77b4", "s")]
    for (name, rows), (c, mk) in zip(sweeps.items(), styles):
        p = [r["power_kw"] for r in rows]
        axes[0].plot(p, [r["regen_MJ"] for r in rows], marker=mk, color=c, lw=1.3, ms=4, label=name)
        axes[1].plot(p, [r["recovery_pct"] for r in rows], marker=mk, color=c, lw=1.3, ms=4, label=name)
    for ax in axes:
        for pk, lab in ((60, "2009"), (120, "2014-25"), (350, "2026")):
            ax.axvline(pk, color="0.6", ls=":", lw=0.9)
            ax.text(pk + 8, 0.97, lab, transform=ax.get_xaxis_transform(), ha="left", va="top",
                    fontsize=6.3, color="0.35", rotation=90)
        ax.set_xlabel("MGU-K power rating (kW)")
    axes[0].set_ylabel("Energy recovered by braking (MJ/lap)")
    axes[0].set_title("(a) Recovered energy")
    axes[1].set_ylabel("Share of braking energy recovered (%)")
    axes[1].set_title("(b) Recovery ratio")
    axes[0].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    return _save(fig, path)


def fig_tornado(t: dict, path):
    rows = sorted(t["rows"], key=lambda r: abs(r["regen_hi"] - r["regen_lo"]))
    base = t["base_regen_MJ"]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.8))
    y = np.arange(len(rows))
    for yi, r in zip(y, rows):
        lo, hi = r["regen_lo"] - base, r["regen_hi"] - base
        ax.barh(yi, lo, color="#4c78a8", height=0.55)
        ax.barh(yi, hi, color="#f58518", height=0.55)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(y, [r["label"] for r in rows], fontsize=7)
    ax.set_xlabel(f"Change in energy recovered per lap (MJ), base = {base:.2f} MJ")
    ax.legend(handles=[Line2D([], [], color="#4c78a8", lw=6, label="Low value"),
                       Line2D([], [], color="#f58518", lw=6, label="High value")], fontsize=7,
              loc="lower right")
    ax.set_title("Sensitivity of braking-energy recovery (2026 race lap)")
    fig.tight_layout()
    return _save(fig, path)


def fig_stint(stint: dict, path):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.0))
    cols = {"managed": "#2ca02c", "all_out": "#d62728", "superclip": COL["clip"]}
    short = {"managed": "Managed", "all_out": "All-out", "superclip": "Managed + super-clip"}
    for key, d in stint.items():
        laps = np.arange(1, len(d["lap_times"]) + 1)
        axes[0].plot(laps, d["lap_times"], "o-", ms=3.5, lw=1.2, color=cols.get(key),
                     label=f"{short.get(key, key)} ({d['total_time_s']:.1f} s)")
        axes[1].plot(np.concatenate(([0], laps)), [d["soc_start"]] + d["soc_end"], "o-", ms=3.5,
                     lw=1.2, color=cols.get(key), label=short.get(key, key))
    axes[0].set_xlabel("Lap")
    axes[0].set_ylabel("Lap time (s)")
    axes[0].set_title("(a) Lap time (10-lap total in brackets)")
    axes[0].legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False)
    axes[1].set_xlabel("Lap")
    axes[1].set_ylabel("SOC at end of lap (%)")
    axes[1].set_title("(b) Energy-store state of charge")
    axes[1].set_ylim(-3, 103)
    axes[1].legend(fontsize=6.5, loc="upper right")
    fig.tight_layout()
    return _save(fig, path)


def fig_deploy_limits(path):
    v = np.linspace(0, 370, 741)
    fig, ax = plt.subplots(figsize=(WIDTH, 2.5))
    ax.plot(v, [deploy_power_limit_kw(x, "fia2026", 350.0) for x in v], color=COL["2026"], lw=1.6,
            label="2026, normal (Art. C5.2.8)")
    ax.plot(v, [deploy_power_limit_kw(x, "fia2026", 350.0, override=True) for x in v],
            color=COL["2026"], lw=1.2, ls="--", label="2026, Overtake/override mode")
    ax.plot(v, np.full_like(v, 120.0), color=COL["2014-25"], lw=1.4, label="2014-2025 MGU-K")
    ax.plot(v, np.full_like(v, 60.0), color=COL["2009"], lw=1.4, label="2009 KERS")
    ax.set_xlabel("Car speed (km/h)")
    ax.set_ylabel("Max deployment power (kW)")
    ax.set_xlim(0, 370)
    ax.set_ylim(0, 380)
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(0.01, 0.62))
    fig.tight_layout()
    return _save(fig, path)


def fig_speed_time(lap: LapResult, path):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.7), gridspec_kw={"width_ratios": [1, 1.5]})
    ax = axes[0]
    t = np.array([0, 20, 60, 85, 100])
    v = np.array([0, 60, 60, 52, 0])
    ax.plot(t, v, color="k", lw=1.5)
    spans = [(0, 20, "Acceleration", "#c7e9c0"), (20, 60, "Free running", "#deebf7"),
             (60, 85, "Coasting", "#fdd0a2"), (85, 100, "Braking", "#fcbba1")]
    for a, b, lab, c in spans:
        ax.axvspan(a, b, color=c, alpha=0.8, lw=0)
        wide = b - a > 20
        ax.text((a + b) / 2, 64, lab, ha="center", va="bottom", fontsize=6.5,
                rotation=0 if wide else 90)
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_title("(a) Idealised train run")
    ax = axes[1]
    tt = lap.t
    vv = lap.v * 3.6
    cat = np.where(lap.mode == MODE_BRAKE, 0, np.where(lap.mode == MODE_PART, 1, 2))
    cmap = matplotlib.colors.ListedColormap([COL["regen"], COL["part"], COL["ice"]])
    norm = matplotlib.colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)
    _colored_line(ax, tt, vv, cat, cmap, norm, lw=2.0)
    ax.set_xlim(0, tt[-1])
    ax.set_ylim(0, vv.max() * 1.08)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_title("(b) F1 lap (simulated, 2026 race lap)")
    ax.legend(handles=[Line2D([], [], color=COL["ice"], lw=3, label="Acceleration / full throttle"),
                       Line2D([], [], color=COL["part"], lw=3, label="Part throttle (cornering)"),
                       Line2D([], [], color=COL["regen"], lw=3, label="Braking (regeneration)")],
              fontsize=6.5, loc="lower right")
    fig.tight_layout()
    return _save(fig, path)


def fig_circuit_compare(rows: dict, path):
    """rows: name -> dict(brake_MJ_km, regen_MJ_km, friction_MJ_km, braking_time_pct)"""
    names = list(rows.keys())
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.6))
    x = np.arange(len(names))
    w = 0.36
    axes[0].bar(x - w / 2, [rows[n]["brake_MJ_km"] for n in names], w, color="0.6",
                label="Braking energy")
    axes[0].bar(x + w / 2, [rows[n]["regen_MJ_km"] for n in names], w, color=COL["regen"],
                label="Recovered (2026)")
    axes[0].set_ylabel("Energy per km (MJ/km)")
    axes[0].set_title("(a) Braking energy density")
    axes[0].legend(fontsize=7)
    axes[1].bar(x - w / 2, [rows[n]["sec"] for n in names], w, color="#4c78a8",
                label="Specific energy consumption")
    axes[1].bar(x + w / 2, [rows[n]["net_sec"] for n in names], w, color="#72b7b2",
                label="Net of regenerated energy")
    axes[1].set_ylabel("Wh per tonne-km")
    axes[1].set_title("(b) Specific energy consumption")
    axes[1].set_ylim(0, max(rows[n]["sec"] for n in names) * 1.35)
    axes[1].legend(fontsize=6.5, loc="upper left")
    axes[0].set_ylim(0, max(rows[n]["brake_MJ_km"] for n in names) * 1.3)
    for ax in axes:
        ax.set_xticks(x, names, fontsize=7.5)
    fig.tight_layout()
    return _save(fig, path)
