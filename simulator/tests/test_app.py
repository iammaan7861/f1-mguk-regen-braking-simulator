"""Smoke test of the Streamlit dashboard: main configurations and new analysis tabs."""
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
        at = AppTest.from_file(str(APP), default_timeout=300)
        base = self._run(at, "default")
        self.assertIn("Lap time", base)

        # presets exist
        self.assertTrue(any("Monza" in b.label for b in at.sidebar.button))

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

        # A/B save buttons + strategy / utilisation study buttons should not crash
        for label in ("Save as compare A", "Save as compare B", "Run strategy comparison",
                      "Run power sweep on this circuit"):
            btn = next((b for b in at.button if b.label == label), None)
            self.assertIsNotNone(btn, label)
            btn.click()
            self._run(at, label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
