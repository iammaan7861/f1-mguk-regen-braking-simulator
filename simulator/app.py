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

from f1_regen import (CAR_2025, CAR_2026, PU_PRESETS, TRACKS, PowerUnit, Strategy,  # noqa: E402
                      Vehicle, simulate_lap, simulate_stint)
from f1_regen import analysis as an  # noqa: E402
from f1_regen.plots import corner_groups  # noqa: E402
from f1_regen.simulation import MODE_BRAKE, MODE_FULL, MODE_PART  # noqa: E402
from f1_regen.strategy import qualifying_strategy, race_strategy  # noqa: E402

st.set_page_config(page_title="F1 ERS Regenerative Braking Simulator", page_icon="\u26a1", layout="wide")

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


# ----------------------------------------------------------------------------------------
# Cached model calls (arguments are plain dicts so Streamlit can hash them)
# ----------------------------------------------------------------------------------------
@st.cache_resource
def get_track(name: str):
    return TRACKS[name]()


@st.cache_data(show_spinner="Simulating lap ...", max_entries=64)
def run_lap(track_name: str, veh_d: dict, pu_d: dict, strat_d: dict, session: str):
    tr = get_track(track_name)
    veh, pu, st_ = Vehicle(**veh_d), PowerUnit(**pu_d), Strategy(**strat_d)
    if pu.ers_enabled and session == "race" and st_.deploy_mode != "none":
        st_ = race_strategy(tr, veh, pu, mode=st_.deploy_mode, soc=st_.soc_start,
                            superclip=st_.superclip, superclip_speed_kph=st_.superclip_speed_kph,
                            name=st_.name, regen=st_.regen)
    elif pu.ers_enabled and session == "quali" and st_.deploy_mode != "none":
        st_ = qualifying_strategy(tr, veh, pu, mode=st_.deploy_mode, superclip=st_.superclip,
                                  superclip_speed_kph=st_.superclip_speed_kph, name=st_.name,
                                  regen=st_.regen)
    return simulate_lap(tr, veh, pu, st_)


@st.cache_data(show_spinner="Simulating reference lap (ICE only) ...", max_entries=16)
def run_ice_only(track_name: str, veh_d: dict, pu_d: dict):
    pu = PowerUnit(**pu_d)
    return simulate_lap(get_track(track_name), Vehicle(**veh_d), pu.ice_only(),
                        Strategy(name="ICE only", deploy_mode="none"))


@st.cache_data(show_spinner="Running all regulation eras (about 10 s) ...", max_entries=4)
def run_eras(track_name: str):
    scen = an.era_scenarios(get_track(track_name))
    return {k: v.summary for k, v in scen.items()}


@st.cache_data(show_spinner="Simulating stint ...", max_entries=16)
def run_stint(track_name: str, veh_d: dict, pu_d: dict, strat_d: dict, n_laps: int):
    laps = simulate_stint(get_track(track_name), Vehicle(**veh_d), PowerUnit(**pu_d), Strategy(**strat_d),
                          n_laps)
    return [{"lap": k + 1, "lap_time_s": lp.lap_time, "soc_end_pct": 100 * lp.soc[-1],
             "deploy_MJ": lp.summary["deploy_MJ"], "harvest_MJ": lp.summary["harvest_MJ"],
             "regen_MJ": lp.summary["regen_MJ"]} for k, lp in enumerate(laps)]


# ----------------------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------------------
sb = st.sidebar
sb.title("\u2699\ufe0f Set-up")
track_name = sb.selectbox("Circuit", list(TRACKS.keys()))
era = sb.selectbox("Power unit / regulations", list(ERA_LABELS.keys()), format_func=ERA_LABELS.get)

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

session = sb.radio("Session", list(SESSION_LABELS.keys()), format_func=SESSION_LABELS.get)
mode = sb.selectbox("Deployment strategy", list(an.MODE_LABELS.keys()) + ["none"],
                    format_func=lambda m: an.MODE_LABELS.get(m, "No deployment"))
param = 0.0
soc_start = 0.5
if mode in MODE_HELP:
    lab, lo, hi, default, step = MODE_HELP[mode]
    if session == "manual":
        param = sb.slider(lab, lo, hi, default, step)
    else:
        sb.caption(f"{lab}: tuned automatically to "
                   + ("finish the lap at the starting SOC." if session == "race"
                      else "start full and finish empty."))
if session != "quali":
    soc_start = sb.slider("State of charge at the start of the lap (%)", 0, 100, 50, 5) / 100
superclip = sb.checkbox("Super-clipping (harvest at full throttle)", value=False,
                        help="Above the threshold speed the MGU-K absorbs the surplus ICE power "
                             "(up to its rating) and the car holds speed.")
clip_v = sb.slider("Super-clipping threshold (km/h)", 250, 345, 300, 5, disabled=not superclip)
regen_on = sb.checkbox("Regenerative braking enabled", value=True)

with sb.expander("Car parameters"):
    mass = st.slider("Car mass with driver (kg)", 700, 900, int(car.mass_kg), 5)
    bshare = st.slider("Rear-axle share of braking", 0.30, 0.60, car.rear_brake_share, 0.01,
                       help="Only the rear axle is driven, so only this share can be regenerated.")
    cda = st.slider("Drag area CdA (m\u00b2)", 0.8, 1.8, float(car.cda_m2), 0.01)
    cla = st.slider("Downforce area ClA (m\u00b2)", 2.5, 7.0, float(car.cla_m2), 0.05)
    grip = st.slider("Tyre grip scale", 0.85, 1.15, 1.0, 0.01)
n_laps = sb.slider("Laps in stint (Stint tab)", 2, 20, 8)

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
st.title("\u26a1 Formula 1 ERS Regenerative Braking Simulator")
st.caption(f"{tr.name} \u00b7 {lap.pu.name} \u00b7 {lap.vehicle.name} \u00b7 strategy: {lap.strategy.name}"
           + (f" (parameter {lap.strategy.deploy_param:.2f})" if mode in MODE_HELP else ""))

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

TAB_NAMES = ["Telemetry", "Track map", "Energy flow", "Braking zones", "Battery", "Compare eras", "Stint",
             "Theory"]
start_tab = st.query_params.get("tab")  # e.g. http://localhost:8501/?tab=Energy%20flow
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
        fig.add_vline(x=s_c / 1000, line=dict(color="#e9ecef", width=1))
    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="kW (+ out / \u2212 in)", row=2, col=1)
    fig.update_yaxes(title_text="%", range=[-3, 103], row=3, col=1)
    fig.update_xaxes(title_text="Distance from the start/finish line (km)", row=3, col=1)
    fig.update_layout(height=760, hovermode="x unified", legend=dict(orientation="h", y=1.07),
                      margin=dict(t=60, b=40))
    st.plotly_chart(fig)
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
    fig.add_trace(go.Scatter(x=tr.x, y=tr.y, mode="lines", line=dict(color="#dee2e6", width=12),
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
        fig.add_annotation(x=cx, y=cy, text=label, showarrow=True, arrowhead=0, arrowcolor="#b22222",
                           ax=38 * ux, ay=-38 * uy, font=dict(size=12, color="#b22222"),
                           xanchor="left" if ux > 0.35 else ("right" if ux < -0.35 else "center"),
                           yanchor="bottom" if uy > 0.35 else ("top" if uy < -0.35 else "middle"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=650, margin=dict(t=20, b=20), legend=dict(orientation="h"))
    st.plotly_chart(fig)

# ---------------- Energy flow ----------------
with tabs[2]:
    f = an.energy_flow(lap)
    eta_e = lap.pu.electrical_chain_efficiency
    clip_mech = (f["clip_dc"] + f["pt_dc"]) / eta_e if eta_e else 0.0
    # The store appears twice (discharge on the left, charge on the right) so the diagram has no cycle;
    # charge minus discharge is the change in stored energy. I²R losses are booked on the discharge side.
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
        textfont=dict(size=14, color="#212529")))
    fig.update_layout(height=600, margin=dict(t=20, b=20, l=10, r=10))
    st.plotly_chart(fig)
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
            f"({S['balance_error_pct']:.1e} % of the fuel energy). Every joule of fuel is accounted for "
            f"as heat, drag, rolling, brake heat or a change in stored energy.\n\n"
            f"Specific energy consumption: **{S['sec_wh_per_tkm']:.0f} Wh/t-km** "
            f"({S['net_sec_wh_per_tkm']:.0f} Wh/t-km net of regenerated energy); "
            f"a suburban EMU train uses roughly 50\u201375 Wh/t-km.")

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
        fig.update_layout(barmode="group", height=380, yaxis_title="MJ", margin=dict(t=30))
        st.plotly_chart(fig)
        show = dfz[["corner", "v_entry_kph", "v_exit_kph", "duration_s", "brake_energy_MJ", "regen_MJ",
                    "recovery_pct", "peak_brake_kW"]].rename(columns={
                        "corner": "Corner", "v_entry_kph": "Entry (km/h)", "v_exit_kph": "Exit (km/h)",
                        "duration_s": "Duration (s)", "brake_energy_MJ": "Braking (MJ)",
                        "regen_MJ": "Recovered (MJ)", "recovery_pct": "Recovered (%)",
                        "peak_brake_kW": "Peak braking power (kW)"})
        st.dataframe(show.style.format(precision=2), hide_index=True)
        st.caption("Peak braking power reaches about 3 MW, roughly ten times what even the 350 kW MGU-K can "
                   "absorb, so most braking energy still becomes heat in the friction brakes.")
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
    fig.update_layout(height=760, showlegend=False, margin=dict(t=40))
    st.plotly_chart(fig)
    c1, c2, c3 = st.columns(3)
    c1.metric("Peak current", f"{S['peak_batt_current_A']:.0f} A")
    c2.metric("Battery loss per lap", f"{S['battery_loss_MJ'] * 1000:.0f} kJ")
    c3.metric("Usable window", f"{lap.pu.es_window_mj:.1f} MJ "
              f"({lap.pu.battery_voc_min_v:.0f}\u2013{lap.pu.battery_voc_max_v:.0f} V)")

# ---------------- Compare eras ----------------
with tabs[5]:
    st.write("Each regulation era on the selected circuit: ICE only, a charge-sustaining race lap and a "
             "qualifying lap (energy store full at the start, empty at the line).")
    if st.button("Run the comparison"):
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
        fig.update_layout(height=380, yaxis_title="Lap time (s)",
                          yaxis_range=[df["Lap time (s)"].min() - 2, df["Lap time (s)"].max() + 0.5])
        st.plotly_chart(fig)

# ---------------- Stint ----------------
with tabs[6]:
    st.write("Consecutive laps with the current settings: the speed and state of charge at the line carry over "
             "to the next lap. A strategy that spends more than it recovers runs the battery flat.")
    rows = run_stint(track_name, veh_d, pu_d, asdict(lap.strategy), n_laps)
    dfs = pd.DataFrame(rows)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Lap time", "SOC at the end of each lap"))
    fig.add_trace(go.Scatter(x=dfs["lap"], y=dfs["lap_time_s"], mode="lines+markers", name="Lap time"), 1, 1)
    fig.add_trace(go.Scatter(x=dfs["lap"], y=dfs["soc_end_pct"], mode="lines+markers", name="SOC",
                             line=dict(color="#2b8a3e")), 1, 2)
    fig.update_yaxes(title_text="s", row=1, col=1)
    fig.update_yaxes(title_text="%", range=[-3, 103], row=1, col=2)
    fig.update_layout(height=380, showlegend=False)
    st.plotly_chart(fig)
    st.dataframe(dfs.style.format(precision=3), hide_index=True)

# ---------------- Theory ----------------
with tabs[7]:
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
