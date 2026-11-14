"""Rebuild analysis figures, dashboard screenshots, tests, report and presentation.

Usage:  python build_all.py
Optional flags:  --skip-analysis  --skip-shots  --skip-tests  --skip-pdf
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], label: str) -> None:
    print(f"\n=== {label} ===")
    print(">", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {r.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild the UEE F1 project deliverables.")
    ap.add_argument("--skip-analysis", action="store_true")
    ap.add_argument("--skip-shots", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--skip-pdf", action="store_true")
    args = ap.parse_args()
    py = sys.executable

    if not args.skip_analysis:
        run([py, "simulator/run_analysis.py"], "Analysis + figures")
    if not args.skip_shots:
        run([py, "simulator/capture_dashboard.py"], "Dashboard screenshots")
    if not args.skip_tests:
        run([py, "simulator/run_tests.py"], "Unit + dashboard tests")

    if args.skip_pdf:
        run([py, "-c",
             "import sys; sys.path.insert(0, 'builders'); from build_report import build; build()"],
            "Project report (DOCX)")
        run([py, "-c",
             "import sys; sys.path.insert(0, 'builders'); from build_presentation import build; build()"],
            "Presentation (PPTX)")
    else:
        run([py, "builders/build_report.py"], "Project report + PDF")
        run([py, "builders/build_presentation.py"], "Presentation + PDF")

    print("\nAll done. Deliverables are in the project root and outputs/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
