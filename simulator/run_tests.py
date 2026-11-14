"""Run the unit and dashboard smoke tests and write a summary for the report.

Usage:  python simulator/run_tests.py
Writes outputs/test_results.json
"""
from __future__ import annotations

import json
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "test_results.json"
TESTS = Path(__file__).resolve().parent / "tests"


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS), pattern="test_*.py")
    t0 = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    elapsed = time.perf_counter() - t0
    cases = []
    for test, err in result.failures + result.errors:
        cases.append({"id": str(test), "status": "FAIL" if (test, err) in result.failures else "ERROR",
                      "detail": err.splitlines()[-1] if err else ""})
    # successes are not tracked by TextTestResult; rebuild from the suite
    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                yield from walk(t)
            else:
                yield t

    failed_ids = {c["id"] for c in cases}
    for t in walk(suite):
        tid = str(t)
        if tid not in failed_ids:
            cases.append({"id": tid, "status": "PASS", "detail": ""})
    cases.sort(key=lambda c: c["id"])
    payload = {
        "generated": datetime.now().strftime("%d %B %Y, %H:%M"),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "ok": result.wasSuccessful(),
        "elapsed_s": round(elapsed, 1),
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}  ({payload['tests_run']} tests, "
          f"{'OK' if payload['ok'] else 'FAILED'} in {payload['elapsed_s']} s)")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
