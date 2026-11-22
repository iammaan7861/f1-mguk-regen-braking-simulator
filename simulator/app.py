"""Interactive dashboard for the F1 ERS regenerative-braking simulator.

Run from the project folder:   streamlit run simulator/app.py
(or double-click Run_Simulator_Dashboard.bat)
"""
from __future__ import annotations

import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dash_cache import (get_track, run_eras, run_ice_only, run_lap, run_power_sweep,  # noqa: E402
                        run_stint, run_strategy_comparison, run_superclip_sweep, snapshot_lap,
                        utilisation_from_summary)
from f1_regen import (CAR_2025, CAR_2026, PU_PRESETS, TRACKS, PowerUnit, Strategy,  # noqa: E402
                      )
from f1_regen import analysis as an  # noqa: E402
from f1_regen.plots import corner_groups  # noqa: E402
from f1_regen.simulation import MODE_BRAKE, MODE_FULL, MODE_PART  # noqa: E402
from ui_theme import inject_css, render_banner, style_fig  # noqa: E402

st.set_page_config(page_title="F1 MGU-K Regenerative Braking Energy Simulator",
                   page_icon="\u26a1", layout="wide", initial_sidebar_state="expanded")
inject_css()

C = {"ice": "#6c757d", "deploy": "#7b2cbf", "regen": "#2ca02c", "friction": "#ff7f0e", "clip": "#17a2b8",
     "soc": "#d62728", "brake": "#343a40", "part": "#f2c14e"}
ERA_LABELS = {"2026": "2026 regulations (350 kW MGU-K)", "2014-2025": "2014-2025 hybrid era (120 kW)",
              "2009 KERS": "2009 KERS (60 kW)", "Custom": "Custom power unit"}
SESSION_LABELS = {"race": "Race lap (charge-sustaining)", "quali": "Qualifying lap (full \u2192 empty)",
                  "manual": "Manual (set the parameter yourself)"}
MODE_HELP = {
    "low_speed": ("Deploy below (km/h)", 0.0, 400.0, 230.0, 1.0),
    "high_speed": ("Deploy above (km/h)", 0.0, 400.0, 300.0, 1.0),
    "uniform": ("Fraction of maximum power", 0.0, 1.0, 0.1, 0.01),
    "greedy": ("Energy budget per lap (MJ)", 0.0, 12.0, 2.0, 0.1),
}
TRACK_KEYS = list(TRACKS.keys())
PRESETS = {
    "Monza 2026 race": {
        "ui_track": TRACK_KEYS[0], "ui_era": "2026", "ui_session": "race",
        "ui_mode": "low_speed", "ui_soc": 50, "ui_superclip": False, "ui_clip_v": 300, "ui_regen": True,
    },
    "Street 2026 race": {
        "ui_track": TRACK_KEYS[1] if len(TRACK_KEYS) > 1 else TRACK_KEYS[0], "ui_era": "2026",
        "ui_session": "race", "ui_mode": "low_speed", "ui_soc": 50, "ui_superclip": False,
        "ui_clip_v": 300, "ui_regen": True,
    },
    "Quali full\u2192empty": {
        "ui_track": TRACK_KEYS[0], "ui_era": "2026", "ui_session": "quali",
        "ui_mode": "low_speed", "ui_soc": 100, "ui_superclip": False, "ui_clip_v": 300, "ui_regen": True,
    },
    "Super-clip @300": {
        "ui_track": TRACK_KEYS[0], "ui_era": "2026", "ui_session": "race",
        "ui_mode": "low_speed", "ui_soc": 50, "ui_superclip": True, "ui_clip_v": 300, "ui_regen": True,
    },
}

# Defaults for keyed widgets (must exist before first widget render)
for k, v in {"ui_track": TRACK_KEYS[0], "ui_era": "2026", "ui_session": "race", "ui_mode": "low_speed",
             "ui_soc": 50, "ui_superclip": False, "ui_clip_v": 300, "ui_regen": True,
             "ui_n_laps": 8, "ui_race_laps": 53}.items():
    st.session_state.setdefault(k, v)


# ----------------------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------------------
sb = st.sidebar
sb.title("Set-up")
sb.caption("One-click presets")
pc = sb.columns(2)
preset_names = list(PRESETS)
for i, name in enumerate(preset_names):
    if pc[i % 2].button(name, use_container_width=True, key=f"preset_btn_{i}"):
        st.session_state.update(PRESETS[name])
        st.rerun()

track_name = sb.selectbox("Circuit", TRACK_KEYS, key="ui_track")
era = sb.selectbox("Power unit / regulations", list(ERA_LABELS.keys()), format_func=ERA_LABELS.get,
                   key="ui_era")

if era == "Custom":
    base = PU_PRESETS["2026"]
    with sb.expander("Custom power unit", expanded=True):
        ice_kw = st.slider("ICE power (kW)", 300, 700, int(base.ice_power_kw), 10)
        k_kw = st.slider("MGU-K power (kW)", 0, 600, int(base.mguk_power_kw), 10)
        window = st.slider("Usable energy-store window (MJ)", 0.5, 8.0, base.es_window_mj, 0.1)
        cap_on = st.checkbox("Limit harvest per lap", value=True)
        harvest = st.slider("Harvest limit per lap (MJ)", 0.5, 12.0, 8.5, 0.1, disabled=not cap_on)
        taper = st.checkbox("Apply the 2026 speed taper (C5.2.8)", value=True)
        eta_k = st.slider("MGU-K efficiency", 0.85, 0.99, base.mguk_efficiency, 0.01)
        r_b = st.slider("Battery internal resistance (\u03a9)", 0.02, 0.30, base.battery_resistance_ohm, 0.01)
    pu = replace(base, name="Custom power unit", ice_power_kw=float(ice_kw), mguk_power_kw=float(k_kw),
                 es_window_mj=float(window), harvest_limit_mj=float(harvest) if cap_on else None,
                 deploy_taper="fia2026" if taper else None, superclip_power_kw=float(k_kw),
                 mguk_efficiency=float(eta_k), battery_resistance_ohm=float(r_b),
                 ers_enabled=k_kw > 0)
    car = CAR_2026 if taper else CAR_2025
else:
    pu = PU_PRESETS[era]
    car = CAR_2026 if era == "2026" else CAR_2025
tr0 = get_track(track_name)
car = car.with_trim(tr0.aero_trim)

session = sb.radio("Session", list(SESSION_LABELS.keys()), format_func=SESSION_LABELS.get, key="ui_session")
mode = sb.selectbox("Deployment strategy", list(an.MODE_LABELS.keys()) + ["none"],
                    format_func=lambda m: an.MODE_LABELS.get(m, "No deployment"), key="ui_mode")
param = 0.0
if mode in MODE_HELP:
    lab, lo, hi, default, step = MODE_HELP[mode]
    if session == "manual":
        param = sb.slider(lab, lo, hi, float(st.session_state.get("ui_param", default)), step, key="ui_param")
    else:
        sb.caption(f"{lab}: tuned automatically to "
                   + ("finish the lap at the starting SOC." if session == "race"
                      else "start full and finish empty."))
soc_start = st.session_state.ui_soc / 100.0
if session != "quali":
    soc_start = sb.slider("State of charge at the start of the lap (%)", 0, 100, key="ui_soc") / 100
superclip = sb.checkbox("Super-clipping (harvest at full throttle)", key="ui_superclip",
                        help="Above the threshold speed the MGU-K absorbs the surplus ICE power "
                             "(up to its rating) and the car holds speed.")
clip_v = sb.slider("Super-clipping threshold (km/h)", 250, 345, key="ui_clip_v", disabled=not superclip)
regen_on = sb.checkbox("Regenerative braking enabled", key="ui_regen")

with sb.expander("Car parameters"):
    mass = st.slider("Car mass with driver (kg)", 700, 900, int(car.mass_kg), 5)
    bshare = st.slider("Rear-axle share of braking", 0.30, 0.60, car.rear_brake_share, 0.01,
                       help="Only the rear axle is driven, so only this share can be regenerated.")
    cda = st.slider("Drag area CdA (m\u00b2)", 0.8, 1.8, float(car.cda_m2), 0.01)
    cla = st.slider("Downforce area ClA (m\u00b2)", 2.5, 7.0, float(car.cla_m2), 0.05)
    grip = st.slider("Tyre grip scale", 0.85, 1.15, 1.0, 0.01)
n_laps = sb.slider("Laps in stint (Stint tab)", 2, 20, key="ui_n_laps")

veh = replace(car, mass_kg=float(mass), rear_brake_share=float(bshare), cda_m2=float(cda),
              cla_m2=float(cla), mu_lat=car.mu_lat * grip, mu_long=car.mu_long * grip)
strat = Strategy(name=an.MODE_LABELS.get(mode, "No deployment"), deploy_mode=mode, deploy_param=float(param),
                 soc_start=1.0 if session == "quali" else float(soc_start), regen=regen_on,
                 superclip=superclip, superclip_speed_kph=float(clip_v))

veh_d, pu_d, strat_d = asdict(veh), asdict(pu), asdict(strat)
lap = run_lap(track_name, veh_d, pu_d, strat_d, session)
ref = run_ice_only(track_name, veh_d, pu_d)
tr = lap.track
S = lap.summary

# ----------------------------------------------------------------------------------------
# Header and KPIs
# ----------------------------------------------------------------------------------------
render_banner(
    f"{tr.name} · {lap.pu.name} · strategy: {lap.strategy.name}"
    + (f" (param {lap.strategy.deploy_param:.2f})" if mode in MODE_HELP else "")
)

ab1, ab2, ab3 = st.columns([1, 1, 2])
if ab1.button("Save as compare A", use_container_width=True):
    st.session_state["cmp_a"] = snapshot_lap(lap, track_name, session, "A")
    st.toast("Saved configuration A")
if ab2.button("Save as compare B", use_container_width=True):
    st.session_state["cmp_b"] = snapshot_lap(lap, track_name, session, "B")
    st.toast("Saved configuration B")
ab3.caption("Open the **A/B compare** tab after saving two setups.")

k = st.columns(7)
k[0].metric("Lap time", f"{S['lap_time_s']:.3f} s", f"{S['lap_time_s'] - ref.lap_time:+.3f} s vs ICE only",
            delta_color="inverse")
k[1].metric("Braking energy", f"{S['brake_energy_MJ']:.2f} MJ")
k[2].metric("Recovered (braking)", f"{S['regen_MJ']:.2f} MJ", f"{S['recovery_pct']:.1f} % of braking")
k[3].metric("Total harvest", f"{S['harvest_MJ']:.2f} MJ",
            f"super-clip {S['clip_MJ']:.2f} MJ" if S["clip_MJ"] > 0 else None)
k[4].metric("Deployed", f"{S['deploy_MJ']:.2f} MJ", f"peak {S['peak_deploy_kW']:.0f} kW", delta_color="off")
k[5].metric("SOC start \u2192 end", f"{S['soc_start_pct']:.0f} \u2192 {S['soc_end_pct']:.0f} %")
k[6].metric("Fuel per lap", f"{S['fuel_kg']:.3f} kg", f"{S['fuel_kg'] - ref.summary['fuel_kg']:+.3f} kg",
            delta_color="inverse")

TAB_NAMES = ["Telemetry", "Track map", "Energy flow", "Braking zones", "Battery", "Strategy",
             "Utilisation", "Compare eras", "A/B compare", "Stint", "Theory"]
start_tab = st.query_params.get("tab")
tabs = st.tabs(TAB_NAMES, default=start_tab if start_tab in TAB_NAMES else None)
x_km = tr.s / 1000
xm_km = tr.s_mid / 1000

# ---------------- Telemetry ----------------
with tabs[0]:
    show_ref = st.toggle("Show ICE-only reference lap", value=True)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.42, 0.38, 0.20],
                        subplot_titles=("Speed", "Power at the MGU-K / brakes", "Energy-store state of charge"))
    if show_ref:
        fig.add_trace(go.Scatter(x=x_km, y=ref.v * 3.6, name=f"ICE only ({ref.lap_time:.2f} s)",
                                 line=dict(color="#adb5bd", width=1.5)), 1, 1)
    fig.add_trace(go.Scatter(x=x_km, y=lap.v * 3.6, name=f"This lap ({lap.lap_time:.2f} s)",
                             line=dict(color="#d62728", width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=xm_km, y=lap.p_deploy / 1e3, name="MGU-K deployment", fill="tozeroy",
                             line=dict(color=C["deploy"], width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=xm_km, y=-lap.p_regen / 1e3, name="MGU-K regeneration", fill="tozeroy",
                             line=dict(color=C["regen"], width=1)), 2, 1)
    if S["clip_MJ"] > 0:
        fig.add_trace(go.Scatter(x=xm_km, y=-lap.p_clip / 1e3, name="Super-clipping harvest", fill="tozeroy",
                                 line=dict(color=C["clip"], width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=xm_km, y=-(lap.p_regen + lap.p_friction) / 1e3, name="Friction brakes",
                             line=dict(color=C["friction"], width=1, dash="dot")), 2, 1)
    fig.add_trace(go.Scatter(x=x_km, y=lap.soc * 100, name="SOC", line=dict(color=C["soc"], width=1.5)), 3, 1)
    for _, _, s_c, _, _ in corner_groups(tr, 160.0):
        fig.add_vline(x=s_c / 1000, line=dict(color="#2d3548", width=1))
    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="kW (+ out / \u2212 in)", row=2, col=1)
    fig.update_yaxes(title_text="%", range=[-3, 103], row=3, col=1)
    fig.update_xaxes(title_text="Distance from the start/finish line (km)", row=3, col=1)
    st.plotly_chart(style_fig(fig, 760))
    tel = pd.DataFrame({"s_m": tr.s_mid, "speed_kph": 0.5 * (lap.v[:-1] + lap.v[1:]) * 3.6,
                        "deploy_kW": lap.p_deploy / 1e3, "regen_kW": lap.p_regen / 1e3,
                        "clip_kW": lap.p_clip / 1e3, "friction_kW": lap.p_friction / 1e3,
                        "soc_pct": lap.soc[1:] * 100, "batt_current_A": lap.i_batt,
                        "batt_voltage_V": lap.v_batt})
    st.download_button("Download this lap's telemetry (CSV)", tel.to_csv(index=False).encode(),
                       file_name="lap_telemetry.csv", mime="text/csv")

# ---------------- Track map ----------------
with tabs[1]:
    what = st.radio("Colour the circuit by", ["Speed", "Operating mode", "Regeneration power", "Deployment power"],
                    horizontal=True)
    highlight = st.session_state.get("highlight_corner")
    if highlight:
        st.info(f"Highlighting braking zone: **{highlight}** (set from the Braking zones tab).")
        if st.button("Clear highlight"):
            st.session_state.pop("highlight_corner", None)
            st.rerun()
    xs, ys = tr.x[1:], tr.y[1:]
    if what == "Speed":
        col, cs, title = 0.5 * (lap.v[:-1] + lap.v[1:]) * 3.6, "Turbo", "km/h"
    elif what == "Regeneration power":
        col, cs, title = (lap.p_regen + lap.p_clip) / 1e3, "Greens", "kW"
    elif what == "Deployment power":
        col, cs, title = lap.p_deploy / 1e3, "Purples", "kW"
    else:
        col, cs, title = None, None, None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tr.x, y=tr.y, mode="lines", line=dict(color="#2d3548", width=12),
                             hoverinfo="skip", showlegend=False))
    if col is not None:
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", showlegend=False,
                                 marker=dict(color=col, colorscale=cs, size=6, colorbar=dict(title=title)),
                                 text=[f"s = {s:.0f} m, {c:.0f} {title}" for s, c in zip(tr.s_mid, col)],
                                 hoverinfo="text"))
    else:
        cats = [("Braking + regeneration", lap.mode == MODE_BRAKE, C["regen"]),
                ("Full throttle + deployment", (lap.mode == MODE_FULL) & (lap.p_deploy > 1e3), C["deploy"]),
                ("Super-clipping", (lap.mode == MODE_FULL) & (lap.p_clip > 1e3), C["clip"]),
                ("Full throttle, ICE only", (lap.mode == MODE_FULL) & (lap.p_deploy <= 1e3) & (lap.p_clip <= 1e3),
                 C["ice"]),
                ("Part throttle", lap.mode == MODE_PART, C["part"])]
        for name, m, c in cats:
            if m.any():
                fig.add_trace(go.Scatter(x=xs[m], y=ys[m], mode="markers", name=name,
                                         marker=dict(color=c, size=6)))
    mx, my = 0.5 * (tr.x.min() + tr.x.max()), 0.5 * (tr.y.min() + tr.y.max())
    for _, label, _, cx, cy in corner_groups(tr):
        ux, uy = cx - mx, cy - my
        d = float(np.hypot(ux, uy)) or 1.0
        ux, uy = ux / d, uy / d
        emph = highlight and highlight in label
        fig.add_annotation(x=cx, y=cy, text=label, showarrow=True, arrowhead=0,
                           arrowcolor="#d62728" if emph else "#b22222",
                           ax=38 * ux, ay=-38 * uy,
                           font=dict(size=14 if emph else 12, color="#d62728" if emph else "#b22222",
                                     family="Arial Black" if emph else None),
                           xanchor="left" if ux > 0.35 else ("right" if ux < -0.35 else "center"),
                           yanchor="bottom" if uy > 0.35 else ("top" if uy < -0.35 else "middle"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    st.plotly_chart(style_fig(fig, 650))

# ---------------- Energy flow ----------------
with tabs[2]:
    f = an.energy_flow(lap)
    eta_e = lap.pu.electrical_chain_efficiency
    clip_mech = (f["clip_dc"] + f["pt_dc"]) / eta_e if eta_e else 0.0
    node_colours = {
        "Fuel": "#495057", "Energy store (discharge)": "#2b8a3e", "ICE crankshaft": "#adb5bd",
        "MGU-K as motor": C["deploy"], "Drivetrain": "#868e96", "Wheels (tractive work)": "#343a40",
        "Braking (kinetic energy)": "#495057", "MGU-K as generator": C["regen"],
        "Exhaust and cooling heat": "#ced4da", "Aerodynamic drag": "#4c78a8", "Rolling resistance": "#72b7b2",
        "Friction-brake heat": C["friction"], "Gearbox losses": "#b279a2", "Electrical losses": "#8c564b",
        "Energy store (charge)": "#2b8a3e",
    }
    links = [
        ("Fuel", "ICE crankshaft", f["ice_mech"]), ("Fuel", "Exhaust and cooling heat", f["ice_heat"]),
        ("Energy store (discharge)", "MGU-K as motor", f["deploy_dc"]),
        ("Energy store (discharge)", "Electrical losses", f["battery_loss"]),
        ("ICE crankshaft", "Drivetrain", f["ice_mech"] - clip_mech),
        ("ICE crankshaft", "MGU-K as generator", clip_mech),
        ("MGU-K as motor", "Drivetrain", f["deploy_mech"]),
        ("MGU-K as motor", "Electrical losses", f["deploy_dc"] - f["deploy_mech"]),
        ("Drivetrain", "Gearbox losses", max(0.0, f["gearbox_loss"] - f["regen_gearbox_loss"])),
        ("Drivetrain", "Wheels (tractive work)", f["tractive"]),
        ("Wheels (tractive work)", "Aerodynamic drag", f["drag"]),
        ("Wheels (tractive work)", "Rolling resistance", f["rolling"]),
        ("Wheels (tractive work)", "Braking (kinetic energy)", f["brake_total"]),
        ("Braking (kinetic energy)", "Friction-brake heat", f["friction_heat"]),
        ("Braking (kinetic energy)", "MGU-K as generator", f["regen_wheel"]),
        ("MGU-K as generator", "Gearbox losses", f["regen_gearbox_loss"]),
        ("MGU-K as generator", "Electrical losses",
         f["regen_emachine_loss"] + clip_mech - f["clip_dc"] - f["pt_dc"]),
        ("MGU-K as generator", "Energy store (charge)", f["regen_dc"] + f["clip_dc"] + f["pt_dc"]),
    ]
    links = [(a, b, v) for a, b, v in links if v > 1e-4]
    names = [n for n in node_colours if any(n in (a, b) for a, b, _ in links)]
    ix = {n: i for i, n in enumerate(names)}
    totals = {n: max(sum(v for a, _, v in links if a == n), sum(v for _, b, v in links if b == n))
              for n in names}
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[f"{n}  {totals[n]:.2f} MJ" for n in names], color=[node_colours[n] for n in names],
                  pad=22, thickness=18),
        link=dict(source=[ix[a] for a, _, _ in links], target=[ix[b] for _, b, _ in links],
                  value=[v for _, _, v in links],
                  customdata=[f"{v:.2f} MJ" for _, _, v in links],
                  hovertemplate="%{source.label} \u2192 %{target.label}: %{customdata}<extra></extra>"),
        textfont=dict(size=14, color="#e8eaed")))
    st.plotly_chart(style_fig(fig, 600))
    bal = pd.DataFrame([
        ("Fuel chemical energy", f["fuel"]), ("ICE heat (exhaust, coolant)", f["ice_heat"]),
        ("Aerodynamic drag", f["drag"]), ("Rolling resistance", f["rolling"]),
        ("Friction-brake heat", f["friction_heat"]), ("Gearbox losses", f["gearbox_loss"]),
        ("MGU-K and inverter losses", f["emachine_loss"]), ("Battery I\u00b2R loss", f["battery_loss"]),
        ("Change in stored electrical energy", f["es_change"]), ("Change in kinetic energy", f["ke_change"]),
    ], columns=["Energy flow over the lap", "MJ"])
    c1, c2 = st.columns([1.2, 1])
    c1.dataframe(bal.style.format({"MJ": "{:.3f}"}), hide_index=True)
    c2.info(f"Energy balance error: {S['balance_error_J']:.2e} J "
            f"({S['balance_error_pct']:.1e} % of the fuel energy).\n\n"
            f"Specific energy consumption: **{S['sec_wh_per_tkm']:.0f} Wh/t-km** "
            f"({S['net_sec_wh_per_tkm']:.0f} Wh/t-km net); suburban EMU ≈ 50–75 Wh/t-km.")

# ---------------- Braking zones ----------------
with tabs[3]:
    zones = an.braking_zones(lap)
    if zones:
        dfz = pd.DataFrame(zones)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dfz["corner"], y=dfz["brake_energy_MJ"], name="Braking energy",
                             marker_color="#adb5bd"))
        fig.add_trace(go.Bar(x=dfz["corner"], y=dfz["regen_MJ"], name="Recovered by MGU-K",
                             marker_color=C["regen"]))
        fig.update_layout(barmode="group", yaxis_title="MJ")
        st.plotly_chart(style_fig(fig, 380))
        pick = st.selectbox("Highlight a corner on the Track map", ["(none)"] + list(dfz["corner"]))
        if pick != "(none)":
            st.session_state["highlight_corner"] = pick
            st.caption(f"Selected **{pick}** — open the Track map tab to see it emphasised.")
        show = dfz[["corner", "v_entry_kph", "v_exit_kph", "duration_s", "brake_energy_MJ", "regen_MJ",
                    "recovery_pct", "peak_brake_kW"]].rename(columns={
                        "corner": "Corner", "v_entry_kph": "Entry (km/h)", "v_exit_kph": "Exit (km/h)",
                        "duration_s": "Duration (s)", "brake_energy_MJ": "Braking (MJ)",
                        "regen_MJ": "Recovered (MJ)", "recovery_pct": "Recovered (%)",
                        "peak_brake_kW": "Peak braking power (kW)"})
        st.dataframe(show.style.format(precision=2), hide_index=True)
        st.caption("Peak braking ≈ 3 MW ≫ 350 kW MGU-K — most energy still becomes friction heat.")
    else:
        st.info("No significant braking zones.")

# ---------------- Battery ----------------
with tabs[4]:
    t = lap.t[1:]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("Current (+ discharge, \u2212 charge)", "Terminal voltage",
                                        "I\u00b2R loss", "State of charge"))
    fig.add_trace(go.Scatter(x=t, y=lap.i_batt, line=dict(color="#d62728", width=1), name="Current"), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=lap.v_batt, line=dict(color="#1f77b4", width=1), name="Voltage"), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=lap.p_batt_loss / 1e3, fill="tozeroy", line=dict(color="#8c564b", width=1),
                             name="Loss"), 3, 1)
    fig.add_trace(go.Scatter(x=lap.t, y=lap.soc * 100, line=dict(color="#2b8a3e", width=1.5), name="SOC"), 4, 1)
    for r, lab in enumerate(["A", "V", "kW", "%"], start=1):
        fig.update_yaxes(title_text=lab, row=r, col=1)
    fig.update_xaxes(title_text="Time (s)", row=4, col=1)
    st.plotly_chart(style_fig(fig, 760).update_layout(showlegend=False))
    c1, c2, c3 = st.columns(3)
    c1.metric("Peak current", f"{S['peak_batt_current_A']:.0f} A")
    c2.metric("Battery loss per lap", f"{S['battery_loss_MJ'] * 1000:.0f} kJ")
    c3.metric("Usable window", f"{lap.pu.es_window_mj:.1f} MJ "
              f"({lap.pu.battery_voc_min_v:.0f}\u2013{lap.pu.battery_voc_max_v:.0f} V)")

# ---------------- Strategy ----------------
with tabs[5]:
    st.write("Charge-sustaining strategies on the **current circuit and power unit** — same harvested "
             "energy, different places to spend it.")
    if st.button("Run strategy comparison", type="primary"):
        st.session_state["strat_" + track_name + pu.name] = run_strategy_comparison(
            track_name, pu_d, soc=0.5 if session == "quali" else float(soc_start))
    rows = st.session_state.get("strat_" + track_name + pu.name)
    if rows:
        dfs = pd.DataFrame(rows)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dfs["label"], y=dfs["lap_time_s"], name="Lap time",
                             marker_color=["#d62728" if d == 0 else "#868e96" for d in dfs["delta_s"]],
                             text=[f"+{d:.3f} s" if d > 0 else "best" for d in dfs["delta_s"]],
                             textposition="outside"))
        fig.update_yaxes(title_text="Lap time (s)",
                         range=[dfs["lap_time_s"].min() - 0.3, dfs["lap_time_s"].max() + 0.5])
        st.plotly_chart(style_fig(fig, 400))
        st.dataframe(dfs[["label", "param", "lap_time_s", "delta_s", "deploy_MJ", "harvest_MJ",
                          "top_speed_kph", "soc_end_pct"]].rename(columns={
                              "label": "Strategy", "param": "Parameter", "lap_time_s": "Lap (s)",
                              "delta_s": "\u0394 vs best (s)", "deploy_MJ": "Deploy (MJ)",
                              "harvest_MJ": "Harvest (MJ)", "top_speed_kph": "Top speed",
                              "soc_end_pct": "SOC end %"}).style.format(precision=3), hide_index=True)
        st.caption("Low-speed priority is usually fastest: a joule spent from a slow corner beats a joule "
                   "spent fighting drag at 300+ km/h.")
    else:
        st.info("Click **Run strategy comparison** (a few seconds).")

    st.subheader("Super-clipping threshold sweep")
    if st.button("Run super-clip sweep"):
        st.session_state["clip_" + track_name] = run_superclip_sweep(
            track_name, (285, 290, 295, 300, 305, 310, 315, 320, 330))
    clip = st.session_state.get("clip_" + track_name)
    if clip:
        dfc = pd.DataFrame(clip["rows"])
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Lap time", "Clip harvest"))
        fig.add_trace(go.Scatter(x=dfc["threshold_kph"], y=dfc["lap_time_s"], mode="lines+markers",
                                 name="Lap"), 1, 1)
        fig.add_trace(go.Scatter(x=dfc["threshold_kph"], y=dfc["clip_MJ"], mode="lines+markers",
                                 name="Clip MJ", line=dict(color=C["clip"])), 1, 2)
        fig.update_xaxes(title_text="Hold speed (km/h)")
        fig.update_yaxes(title_text="s", row=1, col=1)
        fig.update_yaxes(title_text="MJ", row=1, col=2)
        st.plotly_chart(style_fig(fig, 380).update_layout(showlegend=False))
        best = dfc.loc[dfc["lap_time_s"].idxmin()]
        st.success(f"Fastest hold in this sweep: **{best['threshold_kph']:.0f} km/h** "
                   f"({best['lap_time_s']:.3f} s, clip {best['clip_MJ']:.2f} MJ).")

# ---------------- Utilisation ----------------
with tabs[6]:
    race_laps = st.slider("Race distance (laps)", 10, 70, key="ui_race_laps")
    u = utilisation_from_summary(S, pu_d, int(race_laps))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Regen / race", f"{u['regen_kWh_per_race']:.2f} kWh")
    m2.metric("Friction heat / race", f"{u['friction_kWh_per_race']:.1f} kWh")
    m3.metric("Fuel-equivalent of deploy", f"{u['fuel_equiv_kg_per_race']:.2f} kg")
    m4.metric("Household-days of regen", f"{u['household_days_per_race']:.1f} d",
              help="Assuming 100 kWh/month household use")
    st.write(
        f"Gross SEC **{u['sec_wh_per_tkm']:.0f} Wh/t-km** "
        f"(net **{u['net_sec_wh_per_tkm']:.0f}** after regen). "
        f"Suburban EMU trains sit around 50–75 Wh/t-km — F1 is energy-intense because of aero drag "
        f"and hard braking."
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Recovered", x=["This lap", f"{race_laps}-lap race"],
                         y=[u["regen_kWh_per_lap"], u["regen_kWh_per_race"]], marker_color=C["regen"]))
    fig.add_trace(go.Bar(name="Friction heat", x=["This lap", f"{race_laps}-lap race"],
                         y=[u["friction_MJ_per_lap"] / 3.6, u["friction_kWh_per_race"]],
                         marker_color=C["friction"]))
    fig.update_layout(barmode="group", yaxis_title="kWh")
    st.plotly_chart(style_fig(fig, 360))

    st.subheader("Recovery vs MGU-K rating")
    if st.button("Run power sweep on this circuit"):
        st.session_state["pwr_" + track_name] = run_power_sweep(
            track_name, (60, 120, 180, 240, 300, 350, 400, 500, 600))
    pwr = st.session_state.get("pwr_" + track_name)
    if pwr:
        dfp = pd.DataFrame(pwr)
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Energy recovered", "Recovery ratio"))
        fig.add_trace(go.Scatter(x=dfp["power_kw"], y=dfp["regen_MJ"], mode="lines+markers",
                                 name="Regen MJ"), 1, 1)
        fig.add_trace(go.Scatter(x=dfp["power_kw"], y=dfp["recovery_pct"], mode="lines+markers",
                                 name="Recovery %", line=dict(color="#d62728")), 1, 2)
        for x in (60, 120, 350):
            fig.add_vline(x=x, line=dict(color="#adb5bd", dash="dot", width=1), row=1, col=1)
            fig.add_vline(x=x, line=dict(color="#adb5bd", dash="dot", width=1), row=1, col=2)
        fig.update_xaxes(title_text="MGU-K rating (kW)")
        fig.update_yaxes(title_text="MJ", row=1, col=1)
        fig.update_yaxes(title_text="%", row=1, col=2)
        st.plotly_chart(style_fig(fig, 380).update_layout(showlegend=False))
    else:
        st.info("Click **Run power sweep** to see how recovery scales with machine rating.")

# ---------------- Compare eras ----------------
with tabs[7]:
    st.write("Each regulation era on the selected circuit: ICE only, charge-sustaining race, and qualifying.")
    if st.button("Run the era comparison"):
        st.session_state["eras_" + track_name] = run_eras(track_name)
    res = st.session_state.get("eras_" + track_name)
    if res:
        df = pd.DataFrame([{"Scenario": k, "Lap time (s)": v["lap_time_s"], "Top speed (km/h)": v["top_speed_kph"],
                            "Recovered (MJ)": v["regen_MJ"], "Super-clip (MJ)": v["clip_MJ"],
                            "Deployed (MJ)": v["deploy_MJ"], "Recovery (%)": v["recovery_pct"],
                            "Fuel (kg)": v["fuel_kg"]} for k, v in res.items()])
        st.dataframe(df.style.format(precision=2), hide_index=True)
        fig = go.Figure(go.Bar(x=df["Scenario"], y=df["Lap time (s)"],
                               marker_color=["#adb5bd" if "ICE" in s else ("#d62728" if "2026" in s else
                                             ("#1f77b4" if "2014" in s else "#9467bd")) for s in df["Scenario"]]))
        fig.update_layout(yaxis_title="Lap time (s)",
                          yaxis_range=[df["Lap time (s)"].min() - 2, df["Lap time (s)"].max() + 0.5])
        st.plotly_chart(style_fig(fig, 380))

# ---------------- A/B compare ----------------
with tabs[8]:
    a, b = st.session_state.get("cmp_a"), st.session_state.get("cmp_b")
    if not a or not b:
        st.warning("Save two setups with the **Save as compare A/B** buttons above the KPI row.")
    else:
        st.write(f"**A:** {a['track_name']} · {a['strategy']} · {a['session']}  \n"
                 f"**B:** {b['track_name']} · {b['strategy']} · {b['session']}")
        keys = ["lap_time_s", "regen_MJ", "recovery_pct", "deploy_MJ", "harvest_MJ", "fuel_kg",
                "sec_wh_per_tkm", "top_speed_kph"]
        labels = ["Lap time (s)", "Regen (MJ)", "Recovery (%)", "Deploy (MJ)", "Harvest (MJ)",
                  "Fuel (kg)", "SEC (Wh/t-km)", "Top speed (km/h)"]
        table = pd.DataFrame({
            "Metric": labels,
            "A": [a["summary"][k] for k in keys],
            "B": [b["summary"][k] for k in keys],
            "B − A": [b["summary"][k] - a["summary"][k] for k in keys],
        })
        st.dataframe(table.style.format({"A": "{:.3f}", "B": "{:.3f}", "B − A": "{:+.3f}"}), hide_index=True)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Speed", "SOC"),
                            vertical_spacing=0.08)
        fig.add_trace(go.Scatter(x=a["s_km"], y=a["v_kph"], name="A speed",
                                 line=dict(color="#d62728", width=2)), 1, 1)
        fig.add_trace(go.Scatter(x=b["s_km"], y=b["v_kph"], name="B speed",
                                 line=dict(color="#1f77b4", width=2)), 1, 1)
        fig.add_trace(go.Scatter(x=a["s_km"], y=a["soc_pct"], name="A SOC",
                                 line=dict(color="#d62728", width=1.5, dash="dot")), 2, 1)
        fig.add_trace(go.Scatter(x=b["s_km"], y=b["soc_pct"], name="B SOC",
                                 line=dict(color="#1f77b4", width=1.5, dash="dot")), 2, 1)
        fig.update_yaxes(title_text="km/h", row=1, col=1)
        fig.update_yaxes(title_text="%", range=[-3, 103], row=2, col=1)
        fig.update_xaxes(title_text="Distance (km)", row=2, col=1)
        st.plotly_chart(style_fig(fig, 620))

# ---------------- Stint ----------------
with tabs[9]:
    st.write("Consecutive laps with the current settings — SOC and speed carry over at the line.")
    rows = run_stint(track_name, veh_d, pu_d, asdict(lap.strategy), int(n_laps))
    dfs = pd.DataFrame(rows)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Lap time", "SOC at the end of each lap"))
    fig.add_trace(go.Scatter(x=dfs["lap"], y=dfs["lap_time_s"], mode="lines+markers", name="Lap time"), 1, 1)
    fig.add_trace(go.Scatter(x=dfs["lap"], y=dfs["soc_end_pct"], mode="lines+markers", name="SOC",
                             line=dict(color="#2b8a3e")), 1, 2)
    fig.update_yaxes(title_text="s", row=1, col=1)
    fig.update_yaxes(title_text="%", range=[-3, 103], row=1, col=2)
    st.plotly_chart(style_fig(fig, 380).update_layout(showlegend=False))
    st.dataframe(dfs.style.format(precision=3), hide_index=True)

# ---------------- Theory ----------------
with tabs[10]:
    st.subheader("Model equations")
    st.latex(r"m\,v^2\kappa \le \mu_y\left(m g + \tfrac12\rho C_L A\, v^2\right) \quad\text{(cornering limit)}")
    st.latex(r"F_t = m_e\,a + \tfrac12\rho C_D A\, v^2 + C_{rr}\left(m g + \tfrac12\rho C_L A\, v^2\right)"
             r"\quad\text{(tractive effort)}")
    st.latex(r"P_{regen} = \min\left(\beta_r P_{brake}\,\eta_{gb}\eta_{e},\; P_{MGU\text{-}K},\; "
             r"\frac{E_{cap}-E_{harv}}{\Delta t},\; \frac{E_{max}-E}{\Delta t}\right)")
    st.latex(r"V_t = V_{oc}(SOC) \mp I R, \qquad P_{loss} = I^2 R")
    st.latex(r"P_{K,max}(v) = \begin{cases}350\ \text{kW} & v < 290\\ 1800 - 5v & 290 \le v < 340\\ "
             r"6900 - 20v & 340 \le v < 345\\ 0 & v \ge 345\end{cases}\quad (v\ \text{in km/h, FIA 2026 C5.2.8})")
    st.subheader("Electric traction (UEE) \u2194 Formula 1")
    st.table(pd.DataFrame([
        ("Regenerative braking of traction motors", "MGU-K generating on the rear axle"),
        ("Composite braking (electric + mechanical)", "Brake-by-wire blending of MGU-K and friction brakes"),
        ("Receptivity of the supply line", "Headroom in the energy store (full battery cannot recover)"),
        ("Adhesive weight and coefficient of adhesion", "Normal load incl. aerodynamic downforce, tyre grip"),
        ("Speed-time curve: acceleration, free run, coasting, braking", "Full throttle, (super-)clipping, "
         "lift-and-coast, braking"),
        ("Specific energy consumption (Wh/t-km)", "Fuel + electrical energy per tonne-km"),
        ("Four-quadrant drive", "MGU-K motoring (Q I) and regenerating (Q II)"),
    ], columns=["Traction concept", "F1 equivalent"]))
    st.subheader("60-second viva path")
    st.markdown(
        "1. Preset **Monza 2026 race** → Telemetry KPI row  \n"
        "2. **Energy flow** Sankey → every joule accounted for  \n"
        "3. **Strategy** → low-speed beats high-speed  \n"
        "4. **Utilisation** → race kWh vs friction heat  \n"
        "5. Preset **Quali** → receptivity (full store truncates early regen)"
    )
