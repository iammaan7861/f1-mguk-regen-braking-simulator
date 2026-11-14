"""Build Presentation.pptx (+ PDF via PowerPoint COM) for the viva.

Usage:  python builders/build_presentation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FIG, GROUP, RESULTS, ROOT, f, fmt, load_json  # noqa: E402

PPTX = ROOT / "Presentation.pptx"
PDF = ROOT / "Presentation.pdf"
LOGO = ROOT / "assets" / "pec_logo.png"

BG = RGBColor(0xF8, 0xF9, 0xFA)
ACCENT = RGBColor(0xD6, 0x27, 0x28)
DARK = RGBColor(0x21, 0x25, 0x29)
MUTED = RGBColor(0x49, 0x50, 0x57)


def _set_run(run, *, size=18, bold=False, color=DARK, font="Calibri"):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def _blank(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # light background
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG
    return slide


def _title(slide, text, top=0.35, size=28):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.7))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = text
    _set_run(p.runs[0], size=size, bold=True, color=ACCENT)
    return box


def _bullets(slide, lines, left=0.6, top=1.2, width=12.0, height=5.5, size=18):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.level = 0
        p.space_after = Pt(8)
        _set_run(p.runs[0], size=size, color=DARK)
    return box


def _pic(slide, path: Path, left, top, width):
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width))


def _footer(slide, text):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(7.05), Inches(12.3), Inches(0.3))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = text
    _set_run(p.runs[0], size=10, color=MUTED)


def build() -> Path:
    R = load_json(RESULTS)
    G = load_json(GROUP)
    m = R["scenarios"]["monza"]
    s = R["scenarios"]["street"]
    util = R["utilisation_monza_2026_race"]
    members = G["members"]

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    foot = f"{G['short_title']}  ·  {G['subject']}  ·  PEC Chandigarh"

    # 1 Title
    sl = _blank(prs)
    if LOGO.is_file():
        _pic(sl, LOGO, 5.9, 0.35, 1.5)
    _title(sl, G["topic"], top=2.0, size=30)
    box = sl.shapes.add_textbox(Inches(0.8), Inches(3.0), Inches(11.5), Inches(2.5))
    tf = box.text_frame
    tf.clear()
    lines = [
        f"{G['subject']}  ·  Software project ({G['marks']} marks)",
        G["institute"],
        G["department"],
        "",
        "  ·  ".join(f"{mem['name']} ({mem['sid']})" for mem in members),
    ]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line if line else " "
        p.alignment = PP_ALIGN.CENTER
        if p.runs:
            _set_run(p.runs[0], size=16 if i < 4 else 14, color=DARK, bold=(i == 0))
    _footer(sl, foot)

    # 2 Agenda
    sl = _blank(prs)
    _title(sl, "Agenda")
    _bullets(sl, [
        "1. Motivation — UEE meets Formula 1 regenerative braking",
        "2. Objectives and syllabus mapping",
        "3. Simulator physics (track, composite braking, Rint battery, FIA limits)",
        "4. Key results — eras, circuits, strategies, super-clipping",
        "5. Utilisation numbers and interactive dashboard",
        "6. Validation, conclusions and viva demo path",
    ])
    _footer(sl, foot)

    # 3 Motivation
    sl = _blank(prs)
    _title(sl, "Why this topic?")
    _bullets(sl, [
        "UEE core ideas: composite braking, receptivity, speed–time curve, SEC (Wh/t-km).",
        "F1 ERS is the same physics with a local Energy Store instead of a supply line.",
        "2026 rules: ICE ≈ 400 kW + MGU-K 350 kW → electrical utilisation is first-order.",
        "Software scope fits a short deadline; hardware would not.",
        f"Group topic: {G['topic']}",
    ], size=17)
    _footer(sl, foot)

    # 4 Objectives
    sl = _blank(prs)
    _title(sl, "Objectives")
    _bullets(sl, [
        "Simulate flying laps with ICE + MGU-K under 2009 / 2014–25 / 2026 envelopes.",
        "Enforce charge-sustaining race strategies by tuning deployment.",
        "Compare high-speed vs stop-and-go circuits and deployment policies.",
        "Report recovery %, SEC, race-scale kWh and joule-accurate energy balance.",
        "Ship Streamlit dashboard + tests + report for viva.",
    ])
    _footer(sl, foot)

    # 5 Architecture
    sl = _blank(prs)
    _title(sl, "Simulator architecture")
    _pic(sl, f("fig_software_architecture.png"), 0.7, 1.15, 12.0)
    _footer(sl, foot)

    # 6 ERS
    sl = _blank(prs)
    _title(sl, "ERS / MGU-K architecture")
    _pic(sl, f("fig_ers_architecture.png"), 1.2, 1.1, 10.8)
    _footer(sl, foot)

    # 7 Physics
    sl = _blank(prs)
    _title(sl, "Physics in one slide")
    _bullets(sl, [
        "Cornering: m v²κ = μ (mg + ½ ρ ClA v²); backward braking envelope + 5 g cap.",
        "Forward pass: ICE + MGU-K, traction limit, semi-implicit step.",
        "Regen ≤ rear share × brake power × η_gb × η_e, and ≤ PK, harvest cap, SOC headroom.",
        "Friction brakes take the rest → composite braking.",
        "Battery: Vt = Voc ∓ I R  (Voc 720–860 V, R = 0.08 Ω).",
        "2026 deploy taper: PK ≤ min(350, 1800−5v, 6900−20v) kW → 0 at 345 km/h.",
    ], size=16)
    _footer(sl, foot)

    # 8 Circuits
    sl = _blank(prs)
    _title(sl, "Circuits")
    _pic(sl, f("fig_tracks.png"), 0.8, 1.2, 11.7)
    _footer(sl, foot)

    # 9 Headline results
    sl = _blank(prs)
    _title(sl, "Headline results — 2026 race")
    _bullets(sl, [
        f"Monza-like: {fmt(m['2026 race']['lap_time_s'], 3)} s · regen {fmt(m['2026 race']['regen_MJ'])} MJ "
        f"({fmt(m['2026 race']['recovery_pct'], 1)} %) · SOC 50→50 % · "
        f"Δ vs ICE {fmt(m['2026 ICE only']['lap_time_s'] - m['2026 race']['lap_time_s'])} s.",
        f"Street: {fmt(s['2026 race']['lap_time_s'], 3)} s · regen {fmt(s['2026 race']['regen_MJ'])} MJ "
        f"({fmt(s['2026 race']['recovery_pct'], 1)} %).",
        f"Qualifying Monza deploys {fmt(m['2026 qualifying']['deploy_MJ'])} MJ, lap "
        f"{fmt(m['2026 qualifying']['lap_time_s'], 3)} s.",
        "Peak braking ≈ 3 MW ≫ 350 kW MGU-K → most energy still becomes brake heat.",
    ], size=16)
    _footer(sl, foot)

    # 10 Era comparison
    sl = _blank(prs)
    _title(sl, "Regulation eras")
    _pic(sl, f("fig_era_comparison.png"), 0.9, 1.15, 11.5)
    _footer(sl, foot)

    # 11 Strategy
    sl = _blank(prs)
    _title(sl, "Where you spend a joule matters")
    _pic(sl, f("fig_deploy_maps.png"), 0.6, 1.15, 12.1)
    _footer(sl, foot)

    # 12 Super-clip + stint
    sl = _blank(prs)
    _title(sl, "Super-clipping & stint")
    _pic(sl, f("fig_superclip.png"), 0.4, 1.15, 6.2)
    _pic(sl, f("fig_stint.png"), 6.8, 1.15, 6.0)
    _footer(sl, foot)

    # 13 Power sweep
    sl = _blank(prs)
    _title(sl, "Recovery vs MGU-K rating")
    _pic(sl, f("fig_power_sweep.png"), 0.9, 1.15, 11.5)
    _footer(sl, foot)

    # 14 Utilisation
    sl = _blank(prs)
    _title(sl, "Utilisation at race scale (Monza, 53 laps)")
    _bullets(sl, [
        f"Recovered: {fmt(util['regen_kWh_per_race'])} kWh / race "
        f"(≈ {fmt(util['household_days_per_race'], 1)} household-days at 100 kWh/month).",
        f"Still wasted as friction heat: {fmt(util['friction_kWh_per_race'], 0)} kWh / race.",
        f"Fuel-equivalent of deployed electrical work: {fmt(util['fuel_equiv_kg_per_race'])} kg / race.",
        f"SEC {fmt(util['sec_wh_per_tkm'], 0)} Wh/t-km "
        f"(net {fmt(util['net_sec_wh_per_tkm'], 0)} after regen) vs EMU ≈ 50–75 Wh/t-km.",
        "UEE takeaway: receptivity + power mismatch set the utilisation ceiling.",
    ], size=16)
    _footer(sl, foot)

    # 15 Dashboard
    sl = _blank(prs)
    _title(sl, "Interactive dashboard")
    _pic(sl, f("fig_dashboard_telemetry.png"), 0.55, 1.05, 12.2)
    _footer(sl, foot)

    # 16 Energy Sankey
    sl = _blank(prs)
    _title(sl, "Energy flow (Sankey)")
    _pic(sl, f("fig_dashboard_energy.png"), 1.4, 1.05, 10.5)
    _footer(sl, foot)

    # 17 Validation
    sl = _blank(prs)
    _title(sl, "Validation")
    _bullets(sl, [
        f"Max energy-balance error across studies: {R['max_balance_error_pct']:.1e} % of fuel energy.",
        "21 automated tests: taper, battery equations, caps, charge-sustaining, strategy ranking, AppTest.",
        "Race strategies finish within 0.5 % SOC of the start (except 2009 deploy-limited cases).",
        "Limitation: MGU-H not modelled → 2014–25 race deploy is harvest-bound (~0.73 MJ).",
    ], size=16)
    _footer(sl, foot)

    # 18 Conclusion
    sl = _blank(prs)
    _title(sl, "Conclusions")
    _bullets(sl, [
        "Open F1 MGU-K simulator mapped onto UEE syllabus concepts.",
        f"2026 Monza race recovers {fmt(m['2026 race']['recovery_pct'], 1)} % of braking; "
        f"street recovers {fmt(s['2026 race']['recovery_pct'], 1)} %.",
        "Best charge-sustaining policy: low-speed priority (+ super-clip ≈ 300 km/h on Monza).",
        "Dashboard + report ready for viva demonstration.",
        "Thank you — questions welcome.",
    ], size=17)
    box = sl.shapes.add_textbox(Inches(0.8), Inches(5.6), Inches(11.7), Inches(1.0))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = "  ·  ".join(f"{mem['name']}" for mem in members)
    p.alignment = PP_ALIGN.CENTER
    _set_run(p.runs[0], size=14, color=MUTED)
    _footer(sl, foot)

    prs.save(PPTX)
    print(f"Wrote {PPTX}  ({len(prs.slides)} slides)")
    return PPTX


def export_pdf(pptx_path: Path = PPTX, pdf_path: Path = PDF) -> Path | None:
    try:
        import win32com.client  # type: ignore
    except ImportError:
        print("pywin32 not available — PDF export skipped.")
        return None
    app = win32com.client.DispatchEx("PowerPoint.Application")
    # WithWindow=False keeps it quieter on some setups
    try:
        pres = app.Presentations.Open(str(pptx_path), WithWindow=False)
        # 32 = ppSaveAsPDF
        pres.SaveAs(str(pdf_path), 32)
        pres.Close()
    finally:
        app.Quit()
    print(f"Wrote {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    path = build()
    export_pdf(path)
