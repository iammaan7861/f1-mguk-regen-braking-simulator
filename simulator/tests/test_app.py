"""Smoke test of the Streamlit dashboard: every main configuration renders without errors."""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

APP = Path(__file__).resolve().parents[1] / "app.py"


def _sel(at, label):
    return next(s for s in at.sidebar.selectbox if s.label == label)


def _cbox(at, prefix):
    return next(c for c in at.sidebar.checkbox if c.label.startswith(prefix))


@unittest.skipIf(AppTest is None, "streamlit not installed")
class TestDashboard(unittest.TestCase):
    def _run(self, at, label):
        at.run()
        self.assertEqual([e.message for e in at.exception], [], label)
        return {m.label: m.value for m in at.metric}

    def test_configurations(self):
        """Dashboard renders without errors for every era, session, circuit and strategy."""
        at = AppTest.from_file(str(APP), default_timeout=300)
        base = self._run(at, "default")
        self.assertIn("Lap time", base)

        at.sidebar.radio[0].set_value("quali")
        quali = self._run(at, "qualifying")
        self.assertNotEqual(quali["Lap time"], base["Lap time"])

        at.sidebar.radio[0].set_value("race")
        for era in ("2014-2025", "2009 KERS", "Custom", "2026"):
            _sel(at, "Power unit / regulations").set_value(era)
            self._run(at, era)

        _sel(at, "Circuit").set_value("Street circuit (stop-and-go)")
        street = self._run(at, "street")
        self.assertNotEqual(street["Lap time"], base["Lap time"])

        _cbox(at, "Super-clipping").set_value(True)
        self._run(at, "super-clipping")
        for mode in ("uniform", "greedy", "high_speed", "none", "low_speed"):
            _sel(at, "Deployment strategy").set_value(mode)
            self._run(at, mode)

        _cbox(at, "Regenerative").set_value(False)
        no_regen = self._run(at, "regen off")
        self.assertEqual(no_regen["Recovered (braking)"], "0.00 MJ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
