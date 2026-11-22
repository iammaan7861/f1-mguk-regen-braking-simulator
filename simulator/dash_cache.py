"""Cached simulation / study runners for the Streamlit dashboard."""
from __future__ import annotations

from dataclasses import asdict, replace

import streamlit as st

from f1_regen import PowerUnit, Strategy, Vehicle, simulate_lap, simulate_stint
from f1_regen import analysis as an
from f1_regen.strategy import qualifying_strategy, race_strategy
from f1_regen import TRACKS


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


@st.cache_data(show_spinner="Comparing deployment strategies ...", max_entries=8)
def run_strategy_comparison(track_name: str, pu_d: dict, soc: float = 0.5):
    rows = an.strategy_comparison(get_track(track_name), PowerUnit(**pu_d), soc=soc)
    return [{k: v for k, v in r.items() if k != "lap"} for r in rows]


@st.cache_data(show_spinner="Sweeping MGU-K power ratings ...", max_entries=8)
def run_power_sweep(track_name: str, powers: tuple[int, ...]):
    return an.power_sweep(get_track(track_name), powers_kw=powers)


@st.cache_data(show_spinner="Sweeping super-clip thresholds ...", max_entries=4)
def run_superclip_sweep(track_name: str, thresholds: tuple[int, ...]):
    return an.superclip_sweep(get_track(track_name), thresholds=thresholds)


def utilisation_from_summary(summary: dict, pu_d: dict, race_laps: int,
                             household_kwh_per_month: float = 100.0) -> dict:
    """Race-scale utilisation from a lap summary dict (no LapResult required)."""
    pu = PowerUnit(**pu_d)
    regen_mj = summary["regen_MJ"]
    harvest_mj = summary["harvest_MJ"]
    deploy_mech_mj = summary["deploy_MJ"] * pu.electrical_chain_efficiency
    fuel_equiv_kg = (deploy_mech_mj / pu.ice_efficiency) / pu.fuel_lhv_mj_kg
    race_regen_kwh = regen_mj * race_laps / 3.6
    return {
        "race_laps": race_laps,
        "regen_MJ_per_lap": regen_mj,
        "harvest_MJ_per_lap": harvest_mj,
        "regen_kWh_per_lap": regen_mj / 3.6,
        "regen_kWh_per_race": race_regen_kwh,
        "friction_MJ_per_lap": summary["friction_MJ"],
        "friction_kWh_per_race": summary["friction_MJ"] * race_laps / 3.6,
        "deploy_mech_MJ_per_lap": deploy_mech_mj,
        "fuel_equiv_kg_per_lap": fuel_equiv_kg,
        "fuel_equiv_kg_per_race": fuel_equiv_kg * race_laps,
        "household_kwh_per_month": household_kwh_per_month,
        "household_days_per_race": race_regen_kwh / (household_kwh_per_month / 30.0),
        "sec_wh_per_tkm": summary["sec_wh_per_tkm"],
        "net_sec_wh_per_tkm": summary["net_sec_wh_per_tkm"],
    }


def snapshot_lap(lap, track_name: str, session: str, label: str) -> dict:
    """Serializable A/B snapshot for session_state."""
    return {
        "label": label,
        "track_name": track_name,
        "session": session,
        "strategy": lap.strategy.name,
        "param": lap.strategy.deploy_param,
        "summary": dict(lap.summary),
        "s_km": (lap.track.s / 1000.0).tolist(),
        "v_kph": (lap.v * 3.6).tolist(),
        "soc_pct": (lap.soc * 100.0).tolist(),
        "veh": asdict(lap.vehicle),
        "pu": asdict(lap.pu),
        "strat": asdict(lap.strategy),
    }
