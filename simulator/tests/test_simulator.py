"""Verification tests for the F1 regenerative-braking simulator.

Run from the project folder:   python -m unittest discover -s simulator/tests -v
"""
from __future__ import annotations

import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1_regen import (PU_2014_2025, PU_2026, PU_KERS_2009, Strategy, simulate_lap,  # noqa: E402
                      simulate_stint)
from f1_regen import analysis as an  # noqa: E402
from f1_regen.ers import Battery, deploy_power_limit_kw  # noqa: E402
from f1_regen.simulation import MODE_BRAKE  # noqa: E402
from f1_regen.strategy import qualifying_strategy, race_strategy  # noqa: E402
from f1_regen.track import monza_like, street_circuit  # noqa: E402

EPS_W = 1.0  # 1 W numerical allowance on power limits


class TestDeployTaper(unittest.TestCase):
    """FIA 2026 Technical Regulations, Art. C5.2.8 deployment limits."""

    def test_normal_mode(self):
        cases = {0: 350, 250: 350, 290: 350, 300: 300, 320: 200, 339.9: 100.5, 342: 60, 344: 20,
                 345: 0, 360: 0}
        for v, p in cases.items():
            self.assertAlmostEqual(deploy_power_limit_kw(v, "fia2026", 350.0), p, places=6, msg=f"{v} km/h")

    def test_override_mode(self):
        cases = {300: 350, 337.5: 350, 340: 300, 350: 100, 355: 0}
        for v, p in cases.items():
            self.assertAlmostEqual(deploy_power_limit_kw(v, "fia2026", 350.0, override=True), p,
                                   places=6, msg=f"{v} km/h")

    def test_no_taper_is_flat(self):
        for v in (0, 150, 300, 360):
            self.assertEqual(deploy_power_limit_kw(v, None, 120.0), 120.0)


class TestBattery(unittest.TestCase):
    def setUp(self):
        self.b = Battery(PU_2026)

    def test_ocv_limits(self):
        self.assertAlmostEqual(self.b.voc(0.0), PU_2026.battery_voc_min_v)
        self.assertAlmostEqual(self.b.voc(self.b.capacity_j), PU_2026.battery_voc_max_v)

    def test_current_equations(self):
        r = self.b.r
        for voc in (720.0, 800.0, 860.0):
            for p in (50e3, 200e3, 350e3):
                i_d = self.b.discharge_current(p, voc)
                self.assertAlmostEqual((voc - i_d * r) * i_d, p, delta=1e-6 * p)
                i_c = self.b.charge_current(p, voc)
                self.assertAlmostEqual((voc + i_c * r) * i_c, p, delta=1e-6 * p)
                self.assertGreater(i_d, p / voc)   # discharging needs more current than P/Voc
                self.assertLess(i_c, p / voc)      # charging stores less than P/Voc


class TestTracks(unittest.TestCase):
    def test_closure(self):
        for tr in (monza_like(), street_circuit()):
            gap = math.hypot(tr.x[-1] - tr.x[0], tr.y[-1] - tr.y[0])
            self.assertLess(gap, 0.5, tr.name)
            self.assertAlmostEqual(abs(tr.heading[-1] - tr.heading[0]), 2 * math.pi, places=6)
            self.assertAlmostEqual(tr.length, float(tr.ds.sum()), places=6)


class TestLapPhysics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monza = monza_like()
        cls.street = street_circuit()
        cls.laps = {}
        for tr in (cls.monza, cls.street):
            for era, pu in an.ERAS.items():
                veh = an.vehicle_for(tr, pu)
                cls.laps[(tr.name, era, "ice")] = simulate_lap(tr, veh, pu.ice_only(),
                                                               Strategy(name="ICE", deploy_mode="none"))
                cls.laps[(tr.name, era, "race")] = simulate_lap(tr, veh, pu, race_strategy(tr, veh, pu))
                cls.laps[(tr.name, era, "quali")] = simulate_lap(tr, veh, pu,
                                                                 qualifying_strategy(tr, veh, pu))
            veh = an.vehicle_for(tr, PU_2026)
            clip = race_strategy(tr, veh, PU_2026, superclip=True, superclip_speed_kph=290.0)
            cls.laps[(tr.name, "2026", "clip")] = simulate_lap(tr, veh, PU_2026, clip)

    def test_energy_balance_closes(self):
        for key, lap in self.laps.items():
            self.assertLess(abs(lap.energy["balance_error"]), 1e-3, key)  # joules, of ~1e8 J

    def test_ice_only_has_no_electrical_flow(self):
        for key, lap in self.laps.items():
            if key[2] == "ice":
                self.assertEqual(lap.summary["regen_MJ"], 0.0)
                self.assertEqual(lap.summary["deploy_MJ"], 0.0)
                self.assertAlmostEqual(lap.summary["friction_MJ"], lap.summary["brake_energy_MJ"])

    def test_power_limits(self):
        for key, lap in self.laps.items():
            pu = lap.pu
            if not pu.ers_enabled:
                continue
            p_k = pu.mguk_power_kw * 1e3
            self.assertLessEqual(lap.p_regen.max(), p_k + EPS_W, key)
            self.assertLessEqual(lap.p_harvest.max(), p_k + EPS_W, key)
            v_start = lap.v[:-1] * 3.6
            lim = np.array([deploy_power_limit_kw(v, pu.deploy_taper, pu.mguk_power_kw)
                            for v in v_start]) * 1e3
            self.assertTrue(np.all(lap.p_deploy <= lim + EPS_W), key)

    def test_energy_limits_and_soc_window(self):
        for key, lap in self.laps.items():
            pu = lap.pu
            if not pu.ers_enabled:
                continue
            s = lap.summary
            if pu.harvest_limit_mj is not None:
                self.assertLessEqual(s["harvest_MJ"], pu.harvest_limit_mj + 1e-9, key)
            if pu.deploy_limit_mj is not None:
                self.assertLessEqual(s["deploy_MJ"], pu.deploy_limit_mj + 1e-9, key)
            st = lap.strategy
            self.assertGreaterEqual(lap.soc.min(), st.soc_min - 1e-6, key)
            self.assertLessEqual(lap.soc.max(), st.soc_max + 1e-6, key)

    def test_regen_only_while_braking_and_rear_axle_share(self):
        for key, lap in self.laps.items():
            if not lap.pu.ers_enabled:
                continue
            self.assertTrue(np.all(lap.p_regen[lap.mode != MODE_BRAKE] == 0.0), key)
            veh, pu = lap.vehicle, lap.pu
            ceiling = veh.rear_brake_share * veh.gearbox_efficiency * pu.electrical_chain_efficiency
            self.assertTrue(np.all(lap.p_regen <= ceiling * lap.p_brake + EPS_W), key)

    def test_braking_is_physical(self):
        for key, lap in self.laps.items():
            self.assertLessEqual(lap.summary["peak_decel_g"], lap.vehicle.max_decel_g + 0.05, key)
            self.assertLess(lap.summary["top_speed_kph"], 360.0, key)

    def test_race_strategy_is_charge_sustaining(self):
        for key, lap in self.laps.items():
            if key[2] == "race" and key[1] != "2009":
                self.assertAlmostEqual(lap.soc[-1], lap.soc[0], delta=0.005, msg=str(key))

    def test_ers_makes_the_car_faster(self):
        for tr in (self.monza.name, self.street.name):
            for era in an.ERAS:
                t_ice = self.laps[(tr, era, "ice")].lap_time
                self.assertLess(self.laps[(tr, era, "race")].lap_time, t_ice)
                self.assertLess(self.laps[(tr, era, "quali")].lap_time, t_ice)

    def test_recovery_grows_with_regulation_era(self):
        for tr in (self.monza.name, self.street.name):
            rec = [self.laps[(tr, era, "race")].summary["recovery_pct"] for era in ("2009", "2014-25", "2026")]
            self.assertTrue(rec[0] < rec[1] < rec[2], (tr, rec))

    def test_street_circuit_recovers_more_than_monza(self):
        m = self.laps[(self.monza.name, "2026", "race")].summary["regen_MJ"]
        s = self.laps[(self.street.name, "2026", "race")].summary["regen_MJ"]
        self.assertGreater(s, m)


class TestStudies(unittest.TestCase):
    def test_low_speed_priority_is_best(self):
        rows = an.strategy_comparison(monza_like())
        best = min(rows, key=lambda r: r["lap_time_s"])
        self.assertEqual(best["mode"], "low_speed")

    def test_recovered_energy_rises_with_mguk_power(self):
        rows = an.power_sweep(street_circuit(), powers_kw=(60, 120, 350, 600))
        regen = [r["regen_MJ"] for r in rows]
        self.assertTrue(all(b > a for a, b in zip(regen, regen[1:])), regen)

    def test_stint_carries_state(self):
        tr = monza_like()
        veh = an.vehicle_for(tr, PU_2026)
        st = Strategy(name="all-out", deploy_mode="greedy", deploy_param=12.0, soc_start=0.5)
        laps = simulate_stint(tr, veh, PU_2026, st, 3)
        self.assertAlmostEqual(laps[1].soc[0], laps[0].soc[-1])
        self.assertAlmostEqual(laps[1].v[0], laps[0].v[-1])
        self.assertLess(laps[0].lap_time, laps[1].lap_time)  # lap 1 spends the stored energy

    def test_heavier_car_recovers_more(self):
        tr = monza_like()
        veh = an.vehicle_for(tr, PU_2026)
        laps = [simulate_lap(tr, replace(veh, mass_kg=m), PU_2026,
                             race_strategy(tr, replace(veh, mass_kg=m), PU_2026)) for m in (760.0, 840.0)]
        self.assertGreater(laps[1].summary["brake_energy_MJ"], laps[0].summary["brake_energy_MJ"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
