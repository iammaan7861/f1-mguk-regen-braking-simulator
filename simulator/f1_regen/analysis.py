"""Scenario runner and post-processing used by the dashboard and the report."""
from __future__ import annotations

from dataclasses import replace

from .config import (PU_2014_2025, PU_2026, PU_KERS_2009, PowerUnit, Strategy, Vehicle, car_for)
from .simulation import MODE_BRAKE, LapResult, simulate_lap, simulate_stint
from .strategy import qualifying_strategy, race_strategy
from .track import Track

ERAS = {
    "2009": PU_KERS_2009,
    "2014-25": PU_2014_2025,
    "2026": PU_2026,
}

MODE_LABELS = {
    "low_speed": "Low-speed priority",
    "uniform": "Uniform power",
    "greedy": "Greedy (deploy early)",
    "high_speed": "High-speed priority",
}

MONZA_RACE_LAPS = 53


def vehicle_for(track: Track, pu: PowerUnit) -> Vehicle:
    return car_for(pu).with_trim(track.aero_trim)


# ----------------------------------------------------------------------------------------
# Main scenario set
# ----------------------------------------------------------------------------------------
def era_scenarios(track: Track) -> dict[str, LapResult]:
    """ICE-only, race (charge-sustaining) and qualifying laps for every regulation era."""
    out: dict[str, LapResult] = {}
    for era, pu in ERAS.items():
        veh = vehicle_for(track, pu)
        out[f"{era} ICE only"] = simulate_lap(track, veh, pu.ice_only(),
                                              Strategy(name="ICE only", deploy_mode="none"))
        out[f"{era} race"] = simulate_lap(track, veh, pu, race_strategy(track, veh, pu))
        out[f"{era} qualifying"] = simulate_lap(track, veh, pu, qualifying_strategy(track, veh, pu))
    pu = PU_2026
    veh = vehicle_for(track, pu)
    clip = race_strategy(track, veh, pu, superclip=True, superclip_speed_kph=300.0,
                         name="Race + super-clipping")
    out["2026 race + super-clip"] = simulate_lap(track, veh, pu, clip)
    return out


# ----------------------------------------------------------------------------------------
# Braking zones
# ----------------------------------------------------------------------------------------
def braking_zones(lap: LapResult, merge_gap_m: float = 40.0) -> list[dict]:
    """Energy recovered in each braking zone of a lap."""
    tr = lap.track
    is_brake = lap.mode == MODE_BRAKE
    zones: list[list[int]] = []
    i, n = 0, len(is_brake)
    while i < n:
        if is_brake[i]:
            j = i
            while j + 1 < n and is_brake[j + 1]:
                j += 1
            if zones and tr.s[i] - tr.s[zones[-1][1] + 1] < merge_gap_m:
                zones[-1][1] = j
            else:
                zones.append([i, j])
            i = j + 1
        else:
            i += 1
    rows = []
    for a, b in zones:
        sl = slice(a, b + 1)
        dt = lap.dt[sl]
        e_brake = float((lap.p_brake[sl] * dt).sum())
        e_regen = float((lap.p_regen[sl] * dt).sum())
        if e_brake < 0.05e6:
            continue
        rows.append({
            "corner": tr.next_corner_after(float(tr.s[b + 1]) - 30.0),
            "s_start_m": float(tr.s[a]),
            "length_m": float(tr.s[b + 1] - tr.s[a]),
            "v_entry_kph": float(lap.v[a] * 3.6),
            "v_exit_kph": float(lap.v[b + 1] * 3.6),
            "duration_s": float(dt.sum()),
            "brake_energy_MJ": e_brake / 1e6,
            "regen_MJ": e_regen / 1e6,
            "friction_MJ": float((lap.p_friction[sl] * dt).sum()) / 1e6,
            "recovery_pct": 100.0 * e_regen / e_brake,
            "peak_brake_kW": float(lap.p_brake[sl].max() / 1e3),
            "kinetic_drop_MJ": 0.5 * lap.vehicle.effective_mass
            * (lap.v[a] ** 2 - lap.v[b + 1] ** 2) / 1e6,
        })
    return rows


# ----------------------------------------------------------------------------------------
# Energy flow
# ----------------------------------------------------------------------------------------
def energy_flow(lap: LapResult) -> dict:
    """Lap energy flows in MJ (for Sankey diagrams and stacked bars)."""
    e = {k: v / 1e6 for k, v in lap.energy.items() if isinstance(v, float)}
    eta_e = lap.pu.electrical_chain_efficiency
    eta_gb = lap.vehicle.gearbox_efficiency
    regen_wheel = e["regen_wheel"]
    deploy_mech = e["deploy_dc"] * eta_e
    return {
        "fuel": e["fuel"],
        "ice_heat": e["ice_heat"],
        "ice_mech": e["ice"],
        "deploy_dc": e["deploy_dc"],
        "deploy_mech": deploy_mech,
        "tractive": e["tractive"],
        "drag": e["drag"],
        "rolling": e["rolling"],
        "brake_total": e["brake"],
        "friction_heat": e["friction"],
        "regen_wheel": regen_wheel,
        "regen_gearbox_loss": regen_wheel * (1 - eta_gb),
        "regen_emachine_loss": regen_wheel * eta_gb * (1 - eta_e),
        "regen_dc": e["regen_dc"],
        "clip_dc": e["clip_dc"],
        "pt_dc": e["pt_dc"],
        "battery_loss": e["battery"],
        "gearbox_loss": e["gearbox"],
        "emachine_loss": e["emachine"],
        "es_change": (lap.energy["es_end"] - lap.energy["es_start"]) / 1e6,
        "ke_change": e["ke_change"],
    }


# ----------------------------------------------------------------------------------------
# Strategy studies
# ----------------------------------------------------------------------------------------
def strategy_comparison(track: Track, pu: PowerUnit = PU_2026, soc: float = 0.5) -> list[dict]:
    """Same energy (charge-sustaining), different places to deploy it."""
    veh = vehicle_for(track, pu)
    rows = []
    for mode, label in MODE_LABELS.items():
        st = race_strategy(track, veh, pu, mode=mode, soc=soc, name=label)
        lap = simulate_lap(track, veh, pu, st)
        rows.append({"mode": mode, "label": label, "param": st.deploy_param, "lap": lap,
                     **{k: lap.summary[k] for k in ("lap_time_s", "deploy_MJ", "harvest_MJ",
                                                    "top_speed_kph", "soc_end_pct")}})
    best = min(r["lap_time_s"] for r in rows)
    for r in rows:
        r["delta_s"] = r["lap_time_s"] - best
    return rows


def superclip_sweep(track: Track, thresholds=(285, 290, 295, 300, 305, 310, 315, 320, 330)) -> dict:
    pu = PU_2026
    veh = vehicle_for(track, pu)
    base = simulate_lap(track, veh, pu, race_strategy(track, veh, pu))
    rows = []
    for vt in thresholds:
        st = race_strategy(track, veh, pu, superclip=True, superclip_speed_kph=float(vt))
        lap = simulate_lap(track, veh, pu, st)
        s = lap.summary
        rows.append({"threshold_kph": vt, "lap_time_s": s["lap_time_s"], "clip_MJ": s["clip_MJ"],
                     "regen_MJ": s["regen_MJ"], "deploy_MJ": s["deploy_MJ"],
                     "top_speed_kph": s["top_speed_kph"], "soc_end_pct": s["soc_end_pct"]})
    return {"baseline_lap_time_s": base.summary["lap_time_s"],
            "baseline_regen_MJ": base.summary["regen_MJ"], "rows": rows}


# ----------------------------------------------------------------------------------------
# Sensitivity studies
# ----------------------------------------------------------------------------------------
def power_sweep(track: Track, powers_kw=(60, 120, 180, 240, 300, 350, 400, 500, 600)) -> list[dict]:
    """Braking energy that an MGU-K of a given rating can recover (no regulatory energy caps)."""
    rows = []
    veh = vehicle_for(track, PU_2026)
    for p in powers_kw:
        pu = replace(PU_2026, name=f"MGU-K {p} kW", mguk_power_kw=float(p), harvest_limit_mj=None,
                     deploy_limit_mj=None, deploy_taper=None)
        st = race_strategy(track, veh, pu)
        lap = simulate_lap(track, veh, pu, st)
        s = lap.summary
        rows.append({"power_kw": p, "regen_MJ": s["regen_MJ"], "brake_energy_MJ": s["brake_energy_MJ"],
                     "recovery_pct": s["recovery_pct"], "lap_time_s": s["lap_time_s"],
                     "deploy_MJ": s["deploy_MJ"]})
    return rows


def tornado(track: Track) -> dict:
    """Effect of +/- changes in key parameters on energy recovered and lap time (2026 race)."""
    pu0 = PU_2026
    veh0 = vehicle_for(track, pu0)
    base_lap = simulate_lap(track, veh0, pu0, race_strategy(track, veh0, pu0))
    cases = [
        ("Car mass (720 / 880 kg)", "veh", "mass_kg", 720.0, 880.0),
        ("Rear brake share (0.34 / 0.50)", "veh", "rear_brake_share", 0.34, 0.50),
        ("MGU-K efficiency (0.90 / 0.98)", "pu", "mguk_efficiency", 0.90, 0.98),
        ("Battery resistance (0.04 / 0.16 \u03a9)", "pu", "battery_resistance_ohm", 0.04, 0.16),
        ("Drag area CdA (0.99 / 1.21 m\u00b2)", "veh", "cda_m2", 0.99, 1.21),
        ("Tyre grip \u03bc (\u22125 % / +5 %)", "veh", "grip", 0.95, 1.05),
        ("Peak deceleration (4.5 / 5.5 g)", "veh", "max_decel_g", 4.5, 5.5),
    ]
    rows = []
    for label, kind, attr, lo, hi in cases:
        res = []
        for val in (lo, hi):
            veh, pu = veh0, pu0
            if kind == "veh" and attr == "grip":
                veh = replace(veh0, mu_lat=veh0.mu_lat * val, mu_long=veh0.mu_long * val)
            elif kind == "veh":
                veh = replace(veh0, **{attr: val})
            else:
                pu = replace(pu0, **{attr: val})
            lap = simulate_lap(track, veh, pu, race_strategy(track, veh, pu))
            res.append(lap.summary)
        rows.append({"label": label,
                     "regen_lo": res[0]["regen_MJ"], "regen_hi": res[1]["regen_MJ"],
                     "lap_lo": res[0]["lap_time_s"], "lap_hi": res[1]["lap_time_s"],
                     "rec_pct_lo": res[0]["recovery_pct"], "rec_pct_hi": res[1]["recovery_pct"]})
    return {"base_regen_MJ": base_lap.summary["regen_MJ"],
            "base_lap_time_s": base_lap.summary["lap_time_s"],
            "base_recovery_pct": base_lap.summary["recovery_pct"], "rows": rows}


# ----------------------------------------------------------------------------------------
# Multi-lap stint
# ----------------------------------------------------------------------------------------
def stint_comparison(track: Track, n_laps: int = 10) -> dict:
    pu = PU_2026
    veh = vehicle_for(track, pu)
    managed = race_strategy(track, veh, pu, name="Managed (charge-sustaining, low-speed priority)")
    all_out = Strategy(name="All-out (deploy whenever possible)", deploy_mode="greedy",
                       deploy_param=12.0, soc_start=managed.soc_start)
    clip = race_strategy(track, veh, pu, superclip=True, superclip_speed_kph=300.0,
                         name="Managed + super-clipping above 300 km/h")
    out = {}
    for key, st in (("managed", managed), ("all_out", all_out), ("superclip", clip)):
        laps = simulate_stint(track, veh, pu, st, n_laps)
        out[key] = {
            "name": st.name,
            "lap_times": [lp.lap_time for lp in laps],
            "soc_end": [100.0 * lp.soc[-1] for lp in laps],
            "soc_start": 100.0 * laps[0].soc[0],
            "deploy_MJ": [lp.summary["deploy_MJ"] for lp in laps],
            "harvest_MJ": [lp.summary["harvest_MJ"] for lp in laps],
            "total_time_s": float(sum(lp.lap_time for lp in laps)),
        }
    return out


# ----------------------------------------------------------------------------------------
# Energy utilisation perspective
# ----------------------------------------------------------------------------------------
def utilisation_figures(lap: LapResult, race_laps: int = MONZA_RACE_LAPS,
                        household_kwh_per_month: float = 100.0) -> dict:
    s = lap.summary
    eta_e = lap.pu.electrical_chain_efficiency
    regen_mj = s["regen_MJ"]
    harvest_mj = s["harvest_MJ"]
    deploy_mech_mj = s["deploy_MJ"] * eta_e
    fuel_equiv_mj = deploy_mech_mj / lap.pu.ice_efficiency
    fuel_equiv_kg = fuel_equiv_mj / lap.pu.fuel_lhv_mj_kg
    race_regen_kwh = regen_mj * race_laps / 3.6
    return {
        "race_laps": race_laps,
        "regen_MJ_per_lap": regen_mj,
        "harvest_MJ_per_lap": harvest_mj,
        "regen_kWh_per_lap": regen_mj / 3.6,
        "regen_kWh_per_race": race_regen_kwh,
        "friction_MJ_per_lap": s["friction_MJ"],
        "friction_kWh_per_race": s["friction_MJ"] * race_laps / 3.6,
        "deploy_mech_MJ_per_lap": deploy_mech_mj,
        "fuel_equiv_kg_per_lap": fuel_equiv_kg,
        "fuel_equiv_kg_per_race": fuel_equiv_kg * race_laps,
        "household_kwh_per_month": household_kwh_per_month,
        "household_days_per_race": race_regen_kwh / (household_kwh_per_month / 30.0),
        "sec_wh_per_tkm": s["sec_wh_per_tkm"],
        "net_sec_wh_per_tkm": s["net_sec_wh_per_tkm"],
    }
