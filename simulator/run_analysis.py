"""Run the complete simulation study and write figures, tables and results.json.

Usage:  python simulator/run_analysis.py
Outputs go to  outputs/figures, outputs/csv and outputs/results.json
"""
from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from f1_regen import CAR_2025, CAR_2026, PU_2014_2025, PU_2026, PU_KERS_2009  # noqa: E402
from f1_regen import analysis as an  # noqa: E402
from f1_regen import diagrams as dg  # noqa: E402
from f1_regen import plots as pl  # noqa: E402
from f1_regen.track import monza_like, street_circuit  # noqa: E402

ROOT = HERE.parent
OUT = ROOT / "outputs"
FIG = OUT / "figures"
CSV = OUT / "csv"

SUMMARY_KEYS = [
    "lap_time_s", "avg_speed_kph", "top_speed_kph", "min_speed_kph", "time_full_pct", "time_part_pct",
    "time_brake_pct", "braking_time_s", "brake_energy_MJ", "regen_MJ", "clip_MJ", "harvest_MJ",
    "deploy_MJ", "friction_MJ", "recovery_pct", "soc_start_pct", "soc_end_pct", "fuel_MJ", "fuel_kg",
    "drag_MJ", "rolling_MJ", "gearbox_loss_MJ", "emachine_loss_MJ", "battery_loss_MJ",
    "peak_brake_power_kW", "peak_regen_kW", "peak_deploy_kW", "peak_batt_current_A", "peak_decel_g",
    "peak_accel_g", "sec_wh_per_tkm", "net_sec_wh_per_tkm", "balance_error_pct",
]


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items() if k != "lap"}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def _lap_record(lap):
    rec = {k: lap.summary[k] for k in SUMMARY_KEYS}
    st = lap.strategy
    rec.update(strategy=st.name, deploy_mode=st.deploy_mode, deploy_param=st.deploy_param,
               superclip=st.superclip, pu=lap.pu.name, vehicle=lap.vehicle.name)
    return rec


def _write_csv(path, rows, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


def _telemetry_csv(lap, path):
    rows = []
    for i in range(lap.track.n_steps):
        rows.append({
            "s_m": lap.s[i + 1], "t_s": lap.t[i + 1], "speed_kph": lap.v[i + 1] * 3.6,
            "mode": int(lap.mode[i]), "ice_kW": lap.p_ice[i] / 1e3, "deploy_kW": lap.p_deploy[i] / 1e3,
            "regen_kW": lap.p_regen[i] / 1e3, "clip_kW": lap.p_clip[i] / 1e3,
            "brake_kW": lap.p_brake[i] / 1e3, "friction_kW": lap.p_friction[i] / 1e3,
            "soc_pct": lap.soc[i + 1] * 100, "batt_current_A": lap.i_batt[i],
            "batt_voltage_V": lap.v_batt[i], "batt_loss_kW": lap.p_batt_loss[i] / 1e3,
        })
    _write_csv(path, rows)


def main() -> dict:
    t0 = time.time()
    for d in (FIG, CSV):
        d.mkdir(parents=True, exist_ok=True)

    monza, street = monza_like(), street_circuit()
    print("Running era scenarios ...")
    scen_m = an.era_scenarios(monza)
    scen_s = an.era_scenarios(street)
    print(f"  done ({time.time() - t0:.1f} s)")

    zones_m26 = an.braking_zones(scen_m["2026 race"])
    zones_m14 = an.braking_zones(scen_m["2014-25 race"])
    zones_s26 = an.braking_zones(scen_s["2026 race"])

    print("Strategy, super-clip, sensitivity and stint studies ...")
    strat_m = an.strategy_comparison(monza)
    strat_s = an.strategy_comparison(street)
    clip_m = an.superclip_sweep(monza)
    sweep_m = an.power_sweep(monza)
    sweep_s = an.power_sweep(street)
    torn = an.tornado(monza)
    stint = an.stint_comparison(monza, n_laps=10)
    util = an.utilisation_figures(scen_m["2026 race"])
    util_q = an.utilisation_figures(scen_m["2026 race + super-clip"])
    print(f"  done ({time.time() - t0:.1f} s)")

    circuits = {}
    for name, scen, tr in (("Monza-like", scen_m, monza), ("Street circuit", scen_s, street)):
        s = scen["2026 race"].summary
        km = tr.length / 1000
        circuits[name] = {
            "length_km": km, "n_braking_zones": len(an.braking_zones(scen["2026 race"])),
            "brake_MJ": s["brake_energy_MJ"], "regen_MJ": s["regen_MJ"],
            "brake_MJ_km": s["brake_energy_MJ"] / km, "regen_MJ_km": s["regen_MJ"] / km,
            "friction_MJ_km": s["friction_MJ"] / km, "braking_time_pct": s["time_brake_pct"],
            "recovery_pct": s["recovery_pct"], "sec": s["sec_wh_per_tkm"],
            "net_sec": s["net_sec_wh_per_tkm"], "avg_speed_kph": s["avg_speed_kph"],
            "lap_time_s": s["lap_time_s"],
        }

    print("Drawing figures ...")
    colors = {"ICE only": pl.COL["ice"], "2014-25 ERS (race)": pl.COL["2014-25"],
              "2026 ERS (race)": pl.COL["2026"]}
    figs = {}
    figs["tracks"] = pl.fig_tracks([monza, street], FIG / "fig_tracks.png")
    figs["track_maps"] = pl.fig_track_maps(scen_m["2026 race + super-clip"], FIG / "fig_track_maps.png")
    figs["speed_profiles"] = pl.fig_speed_profiles(
        {"ICE only (2026 PU)": scen_m["2026 ICE only"], "2014-25 ERS (race)": scen_m["2014-25 race"],
         "2026 ERS (race)": scen_m["2026 race"]},
        FIG / "fig_speed_profiles.png",
        colors={"ICE only (2026 PU)": pl.COL["ice"], "2014-25 ERS (race)": pl.COL["2014-25"],
                "2026 ERS (race)": pl.COL["2026"]})
    t1 = max(zones_m26, key=lambda z: z["brake_energy_MJ"])
    figs["braking_vs_regen"] = pl.fig_braking_vs_regen(scen_m["2026 race"], scen_m["2014-25 race"],
                                                       FIG / "fig_braking_vs_regen.png", t1)
    figs["soc"] = pl.fig_soc({"2026 race (charge-sustaining)": scen_m["2026 race"],
                              "2026 qualifying": scen_m["2026 qualifying"],
                              "2014-25 qualifying": scen_m["2014-25 qualifying"]},
                             scen_m["2026 qualifying"], FIG / "fig_soc.png",
                             colors={"2026 race (charge-sustaining)": pl.COL["2026"],
                                     "2026 qualifying": "#ff7f0e",
                                     "2014-25 qualifying": pl.COL["2014-25"]})
    figs["battery"] = pl.fig_battery(scen_m["2026 qualifying"], FIG / "fig_battery.png")
    flows = {
        "2009 KERS race": an.energy_flow(scen_m["2009 race"]),
        "2014-25 race": an.energy_flow(scen_m["2014-25 race"]),
        "2026 race": an.energy_flow(scen_m["2026 race"]),
        "2026 qualifying": an.energy_flow(scen_m["2026 qualifying"]),
    }
    figs["energy_breakdown"] = pl.fig_energy_breakdown(flows, flows["2026 race"],
                                                       FIG / "fig_energy_breakdown.png")
    scen_m_sum = {k: v.summary for k, v in scen_m.items()}
    figs["era_comparison"] = pl.fig_era_comparison(scen_m_sum, FIG / "fig_era_comparison.png")
    figs["strategy"] = pl.fig_strategy(strat_m, FIG / "fig_strategy.png")
    low = next(r for r in strat_m if r["mode"] == "low_speed")
    high = next(r for r in strat_m if r["mode"] == "high_speed")
    figs["deploy_maps"] = pl.fig_deploy_maps(low["lap"], high["lap"], FIG / "fig_deploy_maps.png",
                                             "Low-speed priority", "High-speed priority")
    figs["superclip"] = pl.fig_superclip(clip_m, FIG / "fig_superclip.png")
    figs["power_sweep"] = pl.fig_power_sweep({"Monza-like": sweep_m, "Street circuit": sweep_s},
                                             FIG / "fig_power_sweep.png")
    figs["tornado"] = pl.fig_tornado(torn, FIG / "fig_tornado.png")
    figs["stint"] = pl.fig_stint(stint, FIG / "fig_stint.png")
    figs["deploy_limits"] = pl.fig_deploy_limits(FIG / "fig_deploy_limits.png")
    figs["speed_time"] = pl.fig_speed_time(scen_m["2026 race"], FIG / "fig_speed_time.png")
    figs["circuit_compare"] = pl.fig_circuit_compare(circuits, FIG / "fig_circuit_compare.png")
    figs["ers_architecture"] = dg.fig_ers_architecture(FIG / "fig_ers_architecture.png")
    figs["four_quadrant"] = dg.fig_four_quadrant(FIG / "fig_four_quadrant.png")
    figs["rint"] = dg.fig_rint(FIG / "fig_rint.png")
    figs["flowchart"] = dg.fig_flowchart(FIG / "fig_flowchart.png")
    figs["software_architecture"] = dg.fig_software_architecture(FIG / "fig_software_architecture.png")
    print(f"  {len(figs)} figures ({time.time() - t0:.1f} s)")

    _telemetry_csv(scen_m["2026 race"], CSV / "telemetry_monza_2026_race.csv")
    _telemetry_csv(scen_m["2026 qualifying"], CSV / "telemetry_monza_2026_qualifying.csv")
    _write_csv(CSV / "braking_zones_monza_2026_race.csv", zones_m26)
    _write_csv(CSV / "scenarios_monza.csv", [{"scenario": k, **_lap_record(v)} for k, v in scen_m.items()])
    _write_csv(CSV / "scenarios_street.csv", [{"scenario": k, **_lap_record(v)} for k, v in scen_s.items()])

    results = {
        "generated": datetime.now().strftime("%d %B %Y, %H:%M"),
        "tracks": {"monza": monza.summary(), "street": street.summary()},
        "track_corners": {"monza": [c[0] for c in monza.corners], "street": [c[0] for c in street.corners]},
        "vehicles": {"2025": asdict(CAR_2025), "2026": asdict(CAR_2026),
                     "low_trim": asdict(CAR_2026.with_trim("low")),
                     "high_trim": asdict(CAR_2026.with_trim("high"))},
        "power_units": {"2009": asdict(PU_KERS_2009), "2014-25": asdict(PU_2014_2025),
                        "2026": asdict(PU_2026)},
        "scenarios": {"monza": {k: _lap_record(v) for k, v in scen_m.items()},
                      "street": {k: _lap_record(v) for k, v in scen_s.items()}},
        "braking_zones": {"monza_2026": zones_m26, "monza_2014": zones_m14, "street_2026": zones_s26},
        "energy_flows_monza": flows,
        "strategies": {"monza": strat_m, "street": strat_s},
        "superclip_monza": clip_m,
        "power_sweep": {"monza": sweep_m, "street": sweep_s},
        "tornado_monza": torn,
        "stint_monza": stint,
        "utilisation_monza_2026_race": util,
        "utilisation_monza_2026_superclip": util_q,
        "circuits": circuits,
        "max_balance_error_pct": max(v.summary["balance_error_pct"]
                                     for v in list(scen_m.values()) + list(scen_s.values())),
        "figures": {k: Path(v).name for k, v in figs.items()},
    }
    with open(OUT / "results.json", "w", encoding="utf-8") as f:
        json.dump(_clean(results), f, indent=1)
    print(f"Wrote {OUT / 'results.json'}  (total {time.time() - t0:.1f} s)")
    return results


if __name__ == "__main__":
    main()
