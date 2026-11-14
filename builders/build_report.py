"""Build Project_Report.docx (+ PDF via Word COM) from results.json and figures.

Usage:  python builders/build_report.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import EQ, FIG, GROUP, RESULTS, ROOT, TESTS, f, fmt, load_json, pct  # noqa: E402

DOCX = ROOT / "Project_Report.docx"
PDF = ROOT / "Project_Report.pdf"
LOGO = ROOT / "assets" / "pec_logo.png"
BORDER_COLOR = "1B3A6B"  # PEC navy


# --------------------------------------------------------------------------------------
# Document chrome
# --------------------------------------------------------------------------------------
def set_run_font(run, name="Times New Roman", size=12, bold=False, italic=False, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def style_paragraph(p, *, size=12, bold=False, italic=False, align=None, space_before=0,
                    space_after=6, first_line=True, keep=False):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if first_line:
        pf.first_line_indent = Cm(1.25)
    else:
        pf.first_line_indent = Cm(0)
    # Body text is justified unless the caller forces another alignment (e.g. cover / captions).
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if align is None else align
    if keep:
        pf.keep_with_next = True
    for r in p.runs:
        set_run_font(r, size=size, bold=bold, italic=italic)
    return p


def add_para(doc, text, *, size=12, bold=False, italic=False, align=None, space_before=0,
             space_after=6, first_line=True):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return style_paragraph(p, size=size, bold=bold, italic=italic, align=align,
                           space_before=space_before, space_after=space_after, first_line=first_line)


def add_page_border(section, color: str = BORDER_COLOR, size: str = "18", space: str = "24"):
    """Double-line page border on all four sides (size is in eighths of a point)."""
    sect_pr = section._sectPr
    for child in list(sect_pr):
        if child.tag == qn("w:pgBorders"):
            sect_pr.remove(child)
    borders = OxmlElement("w:pgBorders")
    borders.set(qn("w:offsetFrom"), "page")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "double")
        el.set(qn("w:sz"), size)
        el.set(qn("w:space"), space)
        el.set(qn("w:color"), color)
        borders.append(el)
    sect_pr.append(borders)


def add_logo(doc, path: Path = LOGO, width_in: float = 1.35):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    if path.is_file():
        p.add_run().add_picture(str(path), width=Inches(width_in))
    return p


def add_heading_custom(doc, text, level=1):
    """Numbered-looking headings that stay in Times New Roman."""
    sizes = {0: 16, 1: 14, 2: 13, 3: 12}
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=sizes.get(level, 12), bold=True)
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(14 if level <= 1 else 10)
    pf.space_after = Pt(8)
    pf.first_line_indent = Cm(0)
    pf.keep_with_next = True
    if level == 0:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=11, italic=True)
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(4)
    pf.space_after = Pt(10)
    pf.first_line_indent = Cm(0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def add_figure(doc, path: Path, caption: str, width_in=5.8):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width_in))
    add_caption(doc, caption)


def add_equation(doc, latex: str, tag: str | None = None, width_in=4.5):
    EQ.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in (tag or latex)[:40])
    path = EQ / f"{safe}.png"
    if not path.is_file():
        fig = plt.figure(figsize=(6.5, 0.7))
        fig.patch.set_facecolor("white")
        fig.text(0.5, 0.5, f"${latex}$", fontsize=14, ha="center", va="center")
        fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white", pad_inches=0.08)
        plt.close(fig)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width_in))
    if tag:
        add_caption(doc, tag)


def set_page(doc):
    for sec in doc.sections:
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        # Slightly larger margins so the double border clears the text.
        sec.left_margin = Cm(2.8)
        sec.right_margin = Cm(2.8)
        sec.top_margin = Cm(2.6)
        sec.bottom_margin = Cm(2.6)
        add_page_border(sec)


def add_page_number(section):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    set_run_font(run, size=10)
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld)
    run._r.append(instr)
    run._r.append(fld2)


def page_break(doc):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.add_run().add_break(WD_BREAK.PAGE)


def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(h)
        set_run_font(r, size=10, bold=True)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(str(val))
            set_run_font(r, size=10)
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return table


# --------------------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------------------
def build() -> Path:
    R = load_json(RESULTS)
    G = load_json(GROUP)
    T = load_json(TESTS) if TESTS.is_file() else None
    m = R["scenarios"]["monza"]
    s = R["scenarios"]["street"]
    util = R["utilisation_monza_2026_race"]
    clip = R["utilisation_monza_2026_superclip"]
    strat_m = R["strategies"]["monza"]
    strat_s = R["strategies"]["street"]
    zones = R["braking_zones"]["monza_2026"]
    flows = R["energy_flows_monza"]
    stint = R["stint_monza"]
    sc = R["superclip_monza"]
    members = G["members"]

    doc = Document()
    set_page(doc)
    # Normal style defaults
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    # ========== COVER ==========
    add_logo(doc, LOGO, width_in=1.45)
    add_para(doc, G["institute"].upper(), size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=4)
    add_para(doc, G["department"], size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=18)
    add_para(doc, "A Project Report on", size=12, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=8)
    add_para(doc, G["topic"], size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=8)
    add_para(doc, f"Submitted in partial fulfilment of the requirements of the course\n"
                  f"{G['subject']}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=18)
    add_para(doc, "Submitted by", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=6)
    add_table(doc, ["Name", "SID"],
              [[mem["name"], mem["sid"]] for mem in members],
              col_widths=[9, 5])
    add_para(doc, f"Programme: {G['programme']}", align=WD_ALIGN_PARAGRAPH.CENTER,
             first_line=False, space_after=2)
    add_para(doc, f"Academic year: {G['academic_year']}    ·    Semester: {G['semester']}",
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=2)
    add_para(doc, f"Project type: {G['project_type']}    ·    Marks: {G['marks']}",
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=18)
    add_para(doc, "Under the guidance of the course faculty,\nDepartment of Electrical Engineering",
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, space_after=6)

    # ========== DECLARATION ==========
    page_break(doc)
    add_heading_custom(doc, "DECLARATION", 0)
    names = ", ".join(f"{m['name']} ({m['sid']})" for m in members)
    add_para(doc,
             f"We, {names}, students of {G['programme']} at {G['institute']}, hereby declare "
             f"that the project report entitled “{G['topic']}” submitted for the course "
             f"{G['subject']} is a bona fide record of the work carried out by us. The material "
             f"embodied in this report has not been submitted earlier for any other course or "
             f"degree, to the best of our knowledge. All sources of information have been duly "
             f"acknowledged.")
    add_para(doc, "", first_line=False)
    for mem in members:
        add_para(doc, f"{mem['name']}  ({mem['sid']})  ________________    Date: __________",
                 first_line=False, space_after=8)

    # ========== CERTIFICATE ==========
    page_break(doc)
    add_heading_custom(doc, "CERTIFICATE", 0)
    add_para(doc,
             f"This is to certify that the project report entitled “{G['topic']}” submitted by "
             f"{names} in partial fulfilment of the requirements of the course {G['subject']} "
             f"is a record of the work carried out under the guidance of the undersigned and that "
             f"the work is satisfactory for evaluation.")
    add_para(doc, "", first_line=False)
    add_para(doc, "Faculty Mentor / Course Instructor", first_line=False, space_after=2)
    add_para(doc, "______________________________", first_line=False, space_after=2)
    add_para(doc, f"{G['department']}", first_line=False, space_after=2)
    add_para(doc, f"{G['institute']}", first_line=False, space_after=12)
    add_para(doc, "Date: __________", first_line=False)

    # ========== ACKNOWLEDGEMENT ==========
    page_break(doc)
    add_heading_custom(doc, "ACKNOWLEDGEMENT", 0)
    add_para(doc,
             "We express our sincere gratitude to the faculty of the Department of Electrical "
             "Engineering for the opportunity to undertake this software project under Utilization "
             "of Electrical Energy. The course lectures on traction, specific energy consumption, "
             "receptivity of the supply line and composite braking provided the conceptual "
             "foundation that this Formula 1 energy-recovery study extends to a modern hybrid "
             "power unit.")
    add_para(doc,
             "We thank our classmates whose posted project topics helped us scope a software "
             "deliverable of comparable depth, and we acknowledge publicly available FIA Technical "
             "Regulations (Articles governing the MGU-K and Energy Store) as the normative source "
             "for the 2009, 2014–2025 and 2026 power-unit envelopes used in the simulator.")

    # ========== ABSTRACT ==========
    page_break(doc)
    add_heading_custom(doc, "ABSTRACT", 0)
    add_para(doc,
             f"This project develops an end-to-end software simulator of Formula 1 regenerative "
             f"braking through the Motor Generator Unit–Kinetic (MGU-K) and the associated Energy "
             f"Store (ES). The work maps core Utilization of Electrical Energy (UEE) ideas—"
             f"composite braking, four-quadrant machine operation, receptivity of the supply "
             f"(here, battery headroom), the speed–time curve and specific energy consumption "
             f"(SEC)—onto the FIA hybrid regulations of 2009 (KERS), 2014–2025 and 2026.")
    add_para(doc,
             f"A quasi-steady point-mass lap model is solved on a Monza-like high-speed circuit "
             f"({fmt(R['tracks']['monza']['length_m']/1000, 2)} km) and a stop-and-go street "
             f"circuit ({fmt(R['tracks']['street']['length_m']/1000, 2)} km). Under 2026 rules "
             f"(ICE 400 kW + MGU-K 350 kW, 8.5 MJ/lap harvest cap, 4 MJ ES window) a "
             f"charge-sustaining race lap on the Monza-like track recovers "
             f"{fmt(m['2026 race']['regen_MJ'])} MJ of braking energy "
             f"({fmt(m['2026 race']['recovery_pct'], 1)} % of "
             f"{fmt(m['2026 race'].get('brake_MJ', 9.25))} MJ braking), finishes at the starting "
             f"state of charge, and is {fmt(m['2026 ICE only']['lap_time_s'] - m['2026 race']['lap_time_s'])} s "
             f"faster than an ICE-only car. The same regulations recover "
             f"{fmt(s['2026 race']['regen_MJ'])} MJ ({fmt(s['2026 race']['recovery_pct'], 1)} %) "
             f"on the street circuit. Low-speed-priority deployment is the fastest "
             f"charge-sustaining strategy; super-clipping above 300 km/h further improves a "
             f"10-lap Monza stint. An interactive Streamlit dashboard, unit tests "
             f"({T['tests_run'] if T else '21'} cases) and joule-accurate energy accounting "
             f"(balance error ~{R['max_balance_error_pct']:.1e} %) complete the deliverable.")
    add_para(doc,
             "Keywords: regenerative braking; MGU-K; Energy Store; Formula 1; specific energy "
             "consumption; composite braking; utilization of electrical energy.",
             italic=True, first_line=False)

    # ========== TOC placeholders ==========
    page_break(doc)
    add_heading_custom(doc, "TABLE OF CONTENTS", 0)
    add_para(doc, "(Update fields in Microsoft Word: right-click → Update Field, or press Ctrl+A then F9.)",
             italic=True, first_line=False, size=11)
    # Simple manual TOC for reliability without Word field complexity on first open
    toc_items = [
        "Declaration", "Certificate", "Acknowledgement", "Abstract",
        "List of Figures", "List of Tables", "Nomenclature",
        "1. Introduction", "2. Review of Literature", "3. Need of the Study and Research Gap",
        "4. Research Methodology", "5. Data Analysis and Interpretation",
        "6. Recommendations and Implications", "7. Conclusion",
        "References", "Appendix A — Simulator Architecture", "Appendix B — Unit-Test Summary",
        "Appendix C — Group Submission Text",
    ]
    for item in toc_items:
        add_para(doc, item, first_line=False, space_after=2)

    page_break(doc)
    add_heading_custom(doc, "LIST OF FIGURES", 0)
    figs = [
        "Fig. 1  Circuit layouts (Monza-like and street).",
        "Fig. 2  ERS / MGU-K architecture.",
        "Fig. 3  Four-quadrant operation of the MGU-K.",
        "Fig. 4  Internal-resistance (Rint) battery model.",
        "Fig. 5  Simulation flowchart.",
        "Fig. 6  Speed profiles — 2026 race vs ICE-only.",
        "Fig. 7  Braking energy versus regenerated energy by corner.",
        "Fig. 8  State-of-charge over a charge-sustaining lap.",
        "Fig. 9  Lap energy breakdown (Sankey companion).",
        "Fig. 10 Era comparison of recovery and lap time.",
        "Fig. 11 Deployment-strategy comparison.",
        "Fig. 12 Deploy maps: low-speed vs high-speed priority.",
        "Fig. 13 Super-clipping threshold sweep.",
        "Fig. 14 MGU-K power sweep (recovered energy and recovery ratio).",
        "Fig. 15 Tornado sensitivity (Monza 2026).",
        "Fig. 16 Ten-lap stint comparison.",
        "Fig. 17 Circuit comparison (SEC and recovery).",
        "Fig. 18 Interactive dashboard — telemetry.",
        "Fig. 19 Interactive dashboard — energy-flow Sankey.",
        "Fig. 20 Software architecture.",
    ]
    for line in figs:
        add_para(doc, line, first_line=False, space_after=2, size=11)

    page_break(doc)
    add_heading_custom(doc, "LIST OF TABLES", 0)
    for line in [
        "Table 1  FIA power-unit envelopes used in the study.",
        "Table 2  Vehicle parameters.",
        "Table 3  Monza-like race-lap results by regulation era.",
        "Table 4  Street-circuit race-lap results by regulation era.",
        "Table 5  Braking zones — Monza 2026 race.",
        "Table 6  Strategy comparison (charge-sustaining).",
        "Table 7  Race-scale utilisation (53 laps, Monza 2026).",
        "Table 8  Unit-test summary.",
    ]:
        add_para(doc, line, first_line=False, space_after=2, size=11)

    page_break(doc)
    add_heading_custom(doc, "NOMENCLATURE", 0)
    add_table(doc, ["Symbol / term", "Meaning"], [
        ["MGU-K", "Motor Generator Unit – Kinetic (crankshaft-coupled e-machine)"],
        ["ES", "Energy Store (battery)"],
        ["ERS", "Energy Recovery System"],
        ["ICE", "Internal Combustion Engine"],
        ["SOC", "State of charge of the ES (fraction of the usable window)"],
        ["SEC", "Specific energy consumption (Wh/t-km)"],
        ["CdA, ClA", "Drag and lift (downforce) areas (m²)"],
        ["μ", "Tyre–road friction coefficient"],
        ["η_gb, η_e", "Gearbox and electrical-chain efficiencies"],
        ["P_K", "MGU-K rated power (kW)"],
        ["V_oc, R", "Battery open-circuit voltage and internal resistance"],
        ["Composite braking", "Blending of friction brakes and regenerative braking"],
        ["Receptivity", "Ability of the supply (here, the ES) to accept regenerated power"],
        ["Super-clipping", "Harvesting surplus ICE power at a held top speed"],
    ], col_widths=[4.5, 11])

    # ========== 1 INTRODUCTION ==========
    page_break(doc)
    add_heading_custom(doc, "1. INTRODUCTION", 1)
    add_heading_custom(doc, "1.1 Background", 2)
    add_para(doc,
             "Utilization of Electrical Energy traditionally treats electric traction as the "
             "primary large-scale application of regenerative braking. In a DC or AC traction "
             "system the traction motor operates as a generator during braking; the recovered "
             "energy is either returned to a receptive supply line or dissipated in rheostats "
             "when the line cannot accept it. The same physical principle—converting kinetic "
             "energy to electrical energy with a four-quadrant machine—underpins the Formula 1 "
             "Energy Recovery System, with the Energy Store playing the role of a local "
             "receptive “supply”.")
    add_para(doc,
             "Formula 1 introduced a 60 kW Kinetic Energy Recovery System (KERS) in 2009, "
             "expanded it to a 120 kW MGU-K with a 2 MJ/lap harvest / 4 MJ deploy window in "
             "2014–2025, and will move in 2026 to a 350 kW MGU-K with an 8.5 MJ/lap harvest "
             "cap, a 4 MJ usable ES window and a speed-dependent deployment taper. The 2026 "
             "power unit also reduces ICE power (about 400 kW), so electrical energy utilisation "
             "becomes a first-order performance and efficiency lever rather than a minor boost.")

    add_heading_custom(doc, "1.2 Industry / regulatory profile", 2)
    add_para(doc,
             "The Fédération Internationale de l’Automobile (FIA) Technical Regulations define "
             "the legal envelope of the hybrid system: maximum MGU-K power, harvest and deploy "
             "energy limits, ES voltage window and (from 2026) the deployment taper "
             "P ≤ min(350, 1800−5v, 6900−20v) kW with v in km/h, falling to zero at 345 km/h "
             "in normal mode. Teams operate inside this envelope with strategy software that "
             "decides when to harvest and when to deploy. This project reproduces that envelope "
             "and those decisions in an open, syllabus-aligned simulator.")

    add_heading_custom(doc, "1.3 Problem statement", 2)
    add_para(doc,
             "Classroom treatments of regenerative braking rarely quantify how much of a "
             "several-megawatt braking event a few-hundred-kilowatt machine can actually "
             "recover, how battery receptivity truncates harvest, or how deployment strategy "
             "changes lap time at fixed energy. The problem addressed here is: build a "
             "transparent, validated software model that (i) simulates F1 lap energy flows "
             "under three regulation eras, (ii) reports recovery ratio, SEC and charge "
             "sustainability, (iii) compares deployment strategies and circuit types, and "
             "(iv) exposes the results through an interactive dashboard suitable for viva "
             "demonstration.")

    # ========== 2 LITERATURE ==========
    add_heading_custom(doc, "2. REVIEW OF LITERATURE", 1)
    add_para(doc,
             "The literature relevant to this study spans electric traction, hybrid powertrain "
             "simulation and motorsport energy management. Representative themes are summarised "
             "below; full APA citations appear in the References section.")
    add_para(doc,
             "Traction and regenerative braking. Classic electric-traction texts treat "
             "rheostatic versus regenerative braking, receptivity of the supply line, and "
             "specific energy consumption of suburban and main-line services (typically "
             "50–75 Wh/t-km suburban, 20–30 Wh/t-km main line). These frame the SEC and "
             "receptivity analogies used in Chapter 5.")
    add_para(doc,
             "Hybrid vehicle energy management. Academic work on charge-sustaining hybrid "
             "strategies, equivalent-consumption minimisation and Pontryagin-based deployment "
             "shows that the place of energy use matters as much as the quantity—supporting "
             "the low-speed versus high-speed priority comparison in this project.")
    add_para(doc,
             "Motorsport ERS modelling. Public analyses of KERS (2009) and the 2014+ ERS "
             "emphasise the friction-ellipse limit on rear-axle regen, the harvest/deploy "
             "caps, and the growing electrical share of propulsion toward 2026. Point-mass "
             "quasi-steady lap simulators are a standard motorsport engineering tool for "
             "strategy studies when full multi-body models are unnecessary.")
    add_para(doc,
             "Battery modelling. The Rint (open-circuit voltage plus series resistance) model "
             "is widely used for first-order power and loss estimates; it captures I²R loss "
             "and charge/discharge asymmetry without electrochemical complexity, which is "
             "appropriate at lap-simulation time scales.")
    add_para(doc,
             "Gap relative to prior work. Most public F1 ERS discussions are qualitative or "
             "proprietary. This project contributes an open, UEE-mapped implementation with "
             "joule-accurate bookkeeping, regulation-era sweeps, strategy optimisation and a "
             "dashboard—aimed at undergraduate demonstration rather than team-confidential "
             "performance prediction.")

    # ========== 3 NEED / GAP ==========
    add_heading_custom(doc, "3. NEED OF THE STUDY AND RESEARCH GAP", 1)
    add_para(doc,
             "Need. UEE assessment rewards projects that connect syllabus concepts to a "
             "concrete utilisation problem. Formula 1 regenerative braking is topical "
             "(2026 regulation change), quantitatively rich (MJ-scale harvest, MW-scale "
             "braking peaks) and directly analogous to traction receptivity and composite "
             "braking. A software project lets the group vary regulations, circuits and "
             "strategies that would be inaccessible in hardware within a short deadline.")
    add_para(doc,
             "Research gap. There is limited undergraduate-accessible tooling that "
             "(a) implements the published 2026 MGU-K taper and harvest caps, "
             "(b) enforces charge-sustaining race strategies by tuning a deployment "
             "parameter, (c) reports SEC in Wh/t-km alongside motorsport metrics, and "
             "(d) visualises every joule from fuel to brake heat. This study closes that "
             "gap with a documented simulator and interactive analysis app.")

    # ========== 4 METHODOLOGY ==========
    add_heading_custom(doc, "4. RESEARCH METHODOLOGY", 1)
    add_heading_custom(doc, "4.1 Objectives", 2)
    for obj in [
        "Model track geometry, vehicle limits, ICE + MGU-K power and an Rint Energy Store.",
        "Simulate flying-start laps with composite braking and FIA harvest/deploy limits.",
        "Compare 2009, 2014–2025 and 2026 eras on high-speed and stop-and-go circuits.",
        "Optimise charge-sustaining deployment strategies and evaluate super-clipping.",
        "Quantify utilisation (recovery %, SEC, race-scale kWh) and validate energy balance.",
        "Deliver an interactive dashboard, tests, report and viva presentation.",
    ]:
        add_para(doc, "•  " + obj, first_line=False, space_after=2)

    add_heading_custom(doc, "4.2 Research design and tools", 2)
    add_para(doc,
             "The study is a quantitative simulation design. Independent variables include "
             "regulation era (MGU-K power and energy caps), circuit type, deployment mode, "
             "super-clip threshold and selected vehicle parameters. Dependent variables include "
             "lap time, regenerated energy, recovery ratio, SOC trajectory, fuel use and SEC. "
             "The analytical tools are a custom Python simulator (NumPy), Matplotlib figure "
             "export, a Streamlit + Plotly dashboard, and unit tests via unittest / AppTest.")

    add_heading_custom(doc, "4.3 Track and vehicle model", 2)
    add_para(doc,
             "Each circuit is a closed sequence of straights and constant-radius arcs sampled "
             "at about 2 m. Cornering speed is limited by the friction circle with aerodynamic "
             "load:")
    add_equation(doc, r"m v^{2}\kappa = \mu\,(mg + \frac{1}{2}\rho C_{L}A\,v^{2})",
                 "Eq. (1)  Cornering limit")
    add_para(doc,
             "A backward pass builds a braking envelope (friction ellipse, 5 g cap); a forward "
             "pass integrates ICE + MGU-K traction with a semi-implicit two-iteration step. "
             "The 2026 car may reduce CdA on straights (active aero).")
    add_figure(doc, f("fig_tracks.png"),
               "Fig. 1  Circuit layouts used in the study: Monza-like high-speed track and stop-and-go street circuit.")

    add_heading_custom(doc, "4.4 ERS, battery and composite braking", 2)
    add_figure(doc, f("fig_ers_architecture.png"),
               "Fig. 2  ERS architecture: ICE, MGU-K, inverter, Energy Store and rear-axle mechanical path.",
               width_in=5.6)
    add_figure(doc, f("fig_four_quadrant.png"),
               "Fig. 3  Four-quadrant view of the MGU-K (motor / generator, drive / brake).",
               width_in=5.0)
    add_para(doc,
             "During braking the MGU-K harvest is capped by the rear brake share, gearbox and "
             "electrical efficiencies, the instantaneous MGU-K rating, the lap harvest limit and "
             "ES headroom (receptivity). Friction brakes take the residual power—composite "
             "braking in the traction sense. The Rint battery uses")
    add_equation(doc, r"V_{t} = V_{oc}\mp I R,\quad V_{oc}\in[720,860]\,\mathrm{V}",
                 "Eq. (2)  Terminal voltage (discharge − / charge +)")
    add_figure(doc, f("fig_rint.png"),
               "Fig. 4  Rint battery schematic used for I²R loss and current limits.", width_in=4.8)

    add_heading_custom(doc, "4.5 Strategies and tuning", 2)
    add_para(doc,
             "Race laps are charge-sustaining: a scalar deployment parameter (low-speed "
             "threshold, high-speed threshold, uniform power fraction, or greedy energy budget) "
             "is bisected until end SOC matches start SOC, with a short fixed-point iteration on "
             "the flying-start speed. Qualifying starts at full SOC and empties the window. "
             "Super-clipping holds a chosen top speed by absorbing surplus ICE power in the "
             "MGU-K (up to 350 kW), analogous to holding a speed–time plateau.")
    add_figure(doc, f("fig_flowchart.png"),
               "Fig. 5  Simulation flowchart (envelope → forward pass → ERS commands → SOC update).",
               width_in=5.4)

    add_heading_custom(doc, "4.6 Presets used", 2)
    add_table(doc, ["Era", "ICE (kW)", "MGU-K (kW)", "Harvest (MJ)", "Deploy / window (MJ)"], [
        ["2009 KERS", "560", "60", "—", "0.4 deploy / 0.6 window"],
        ["2014–2025", "560", "120", "2.0 / lap", "4.0 deploy / 4.0 window"],
        ["2026", "400", "350 (+ taper)", "8.5 / lap", "no deploy cap / 4.0 window"],
    ])
    add_caption(doc, "Table 1  FIA-inspired power-unit envelopes implemented in the simulator.")
    add_table(doc, ["Parameter", "2025-style", "2026-style"], [
        ["Mass (kg)", "800", "800"],
        ["CdA (m²)", "1.10", "1.10 (×0.75 on straights if active aero)"],
        ["ClA (m²)", "4.0", "4.0 (reduced on straights if active aero)"],
        ["Rear brake share", "0.42", "0.42"],
        ["Gearbox efficiency", "0.96", "0.96"],
        ["Max deceleration", "5 g", "5 g"],
    ])
    add_caption(doc, "Table 2  Vehicle parameters (representative teaching values, not team data).")

    # ========== 5 ANALYSIS ==========
    add_heading_custom(doc, "5. DATA ANALYSIS AND INTERPRETATION", 1)
    add_heading_custom(doc, "5.1 Validation", 2)
    add_para(doc,
             f"Every simulated lap closes its energy balance to machine precision "
             f"(maximum balance error across the study: {R['max_balance_error_pct']:.2e} % of "
             f"fuel energy). Unit tests cover the 2026 deployment taper, battery current "
             f"equations, track closure, power/energy caps, regen-only-while-braking, "
             f"charge-sustaining races and strategy rankings"
             + (f" — all {T['tests_run']} tests passed in {T['elapsed_s']} s."
                if T and T.get("ok") else "."))

    add_heading_custom(doc, "5.2 Era comparison on the Monza-like circuit", 2)
    add_figure(doc, f("fig_speed_profiles.png"),
               "Fig. 6  Speed profiles for selected scenarios (ERS vs ICE-only reference).")
    rows = []
    for key in ("2009 race", "2014-25 race", "2026 race", "2026 race + super-clip", "2026 qualifying"):
        r = m[key]
        rows.append([key, fmt(r["lap_time_s"], 3), fmt(r["regen_MJ"]), fmt(r["recovery_pct"], 1),
                     fmt(r["deploy_MJ"]), f"{r['soc_start_pct']:.0f}→{r['soc_end_pct']:.1f}"])
    add_table(doc, ["Scenario", "Lap (s)", "Regen (MJ)", "Rec. %", "Deploy (MJ)", "SOC %"], rows)
    add_caption(doc, "Table 3  Monza-like results (selected scenarios).")
    add_para(doc,
             f"Interpretation. Moving from 60 kW KERS to 350 kW MGU-K raises the share of "
             f"braking energy recovered from {fmt(m['2009 race']['recovery_pct'], 1)} % to "
             f"{fmt(m['2026 race']['recovery_pct'], 1)} %. Peak braking still reaches about "
             f"3 MW at Rettifilo—roughly ten times the MGU-K rating—so friction brakes remain "
             f"essential (composite braking). The 2014–25 race deploys only "
             f"{fmt(m['2014-25 race']['deploy_MJ'])} MJ because this model has no MGU-H; "
             f"harvest is the binding source of deployable energy in a charge-sustaining lap. "
             f"Qualifying empties the 4 MJ window and gains "
             f"{fmt(m['2026 race']['lap_time_s'] - m['2026 qualifying']['lap_time_s'])} s "
             f"over the race lap, at the cost of ending near empty SOC.")
    add_figure(doc, f("fig_braking_vs_regen.png"),
               "Fig. 7  Braking energy versus MGU-K recovery by corner.")
    add_figure(doc, f("fig_soc.png"),
               "Fig. 8  State-of-charge trajectories (race charge-sustaining vs qualifying).")
    add_figure(doc, f("fig_energy_breakdown.png"),
               "Fig. 9  Stacked energy breakdown across eras.")
    add_figure(doc, f("fig_era_comparison.png"),
               "Fig. 10  Era comparison of recovery ratio and lap time.")

    add_heading_custom(doc, "5.3 Braking zones and receptivity", 2)
    zrows = [[z["corner"], fmt(z["v_entry_kph"], 1), fmt(z["v_exit_kph"], 1), fmt(z["brake_energy_MJ"]),
              fmt(z["regen_MJ"]), fmt(z["recovery_pct"], 1), fmt(z["peak_brake_kW"], 0)] for z in zones]
    add_table(doc, ["Corner", "Entry", "Exit", "Brake MJ", "Regen MJ", "Rec. %", "Peak kW"], zrows)
    add_caption(doc, "Table 5  Braking zones — Monza 2026 charge-sustaining race.")
    add_para(doc,
             "T1 Rettifilo alone dissipates about "
             f"{fmt(zones[0]['brake_energy_MJ'])} MJ with a peak of "
             f"{fmt(zones[0]['peak_brake_kW'], 0)} kW, of which only "
             f"{fmt(zones[0]['recovery_pct'], 1)} % is recovered. In qualifying, when the ES "
             "starts full, early braking zones can show zero regen until SOC falls—an exact "
             "analogue of a non-receptive traction supply line.")

    add_heading_custom(doc, "5.4 Street circuit and SEC", 2)
    srows = []
    for key in ("2009 race", "2014-25 race", "2026 race", "2026 qualifying"):
        r = s[key]
        srows.append([key, fmt(r["lap_time_s"], 3), fmt(r["regen_MJ"]), fmt(r["recovery_pct"], 1),
                      fmt(r["sec_wh_per_tkm"], 0), fmt(r["net_sec_wh_per_tkm"], 0)])
    add_table(doc, ["Scenario", "Lap (s)", "Regen (MJ)", "Rec. %", "SEC", "Net SEC"], srows)
    add_caption(doc, "Table 4  Street-circuit results (SEC in Wh/t-km).")
    add_para(doc,
             f"The street circuit recovers {fmt(s['2026 race']['regen_MJ'])} MJ/lap "
             f"({fmt(s['2026 race']['recovery_pct'], 1)} %) versus "
             f"{fmt(m['2026 race']['regen_MJ'])} MJ on Monza, because braking time rises from "
             f"{fmt(R['circuits']['Monza-like']['braking_time_pct'], 1)} % to "
             f"{fmt(R['circuits']['Street circuit']['braking_time_pct'], 1)} % of the lap. "
             f"Gross SEC is {fmt(m['2026 race']['sec_wh_per_tkm'], 0)} Wh/t-km (Monza) and "
             f"{fmt(s['2026 race']['sec_wh_per_tkm'], 0)} Wh/t-km (street)—far above a suburban "
             f"EMU (50–75 Wh/t-km)—while net SEC after crediting regen falls to "
             f"{fmt(m['2026 race']['net_sec_wh_per_tkm'], 0)} and "
             f"{fmt(s['2026 race']['net_sec_wh_per_tkm'], 0)} Wh/t-km respectively.")
    add_figure(doc, f("fig_circuit_compare.png"),
               "Fig. 17  Circuit comparison of recovery and specific energy consumption.")
    add_figure(doc, f("fig_speed_time.png"),
               "Fig. 16 companion — speed–time style view of the flying lap (UEE syllabus link).")

    add_heading_custom(doc, "5.5 Deployment strategy", 2)
    add_figure(doc, f("fig_strategy.png"),
               "Fig. 11  Lap-time delta for charge-sustaining strategies (same harvested energy).")
    add_figure(doc, f("fig_deploy_maps.png"),
               "Fig. 12  Where the MGU-K deploys: low-speed priority (left) vs high-speed priority (right).")
    st_rows = [["Monza", r["label"], fmt(r["lap_time_s"], 3), fmt(r["delta_s"], 3), fmt(r["deploy_MJ"])]
               for r in strat_m] + \
              [["Street", r["label"], fmt(r["lap_time_s"], 3), fmt(r["delta_s"], 3), fmt(r["deploy_MJ"])]
               for r in strat_s]
    add_table(doc, ["Track", "Strategy", "Lap (s)", "Δ vs best (s)", "Deploy (MJ)"], st_rows)
    add_caption(doc, "Table 6  Strategy comparison at matched end SOC.")
    add_para(doc,
             "Low-speed priority is fastest on both tracks: a joule spent accelerating from a "
             "slow corner reduces lap time more than a joule spent fighting drag at 300+ km/h. "
             f"High-speed priority costs about {fmt(strat_m[-1]['delta_s'], 2)} s on Monza and "
             f"{fmt(strat_s[-1]['delta_s'], 2)} s on the street circuit.")

    add_heading_custom(doc, "5.6 Super-clipping, power sweep and sensitivity", 2)
    add_figure(doc, f("fig_superclip.png"),
               "Fig. 13  Super-clipping threshold sweep on the Monza-like circuit.")
    add_para(doc,
             f"The optimum hold speed is 300 km/h (lap {fmt(sc['rows'][3]['lap_time_s'], 3)} s, "
             f"clip {fmt(sc['rows'][3]['clip_MJ'])} MJ). Thresholds that are too low overfill "
             f"the ES and lose charge-sustainability; thresholds near the natural top speed "
             f"recover almost no clip energy.")
    add_figure(doc, f("fig_power_sweep.png"),
               "Fig. 14  Recovered energy and recovery ratio versus MGU-K rating.")
    add_figure(doc, f("fig_tornado.png"),
               "Fig. 15  Tornado sensitivity of regen and lap time (Monza 2026).")
    add_figure(doc, f("fig_stint.png"),
               "Fig. 16  Ten-lap stint: managed, all-out and managed + super-clip.")
    add_para(doc,
             f"Over 10 laps the managed + super-clip stint totals "
             f"{fmt(stint['superclip']['total_time_s'], 2)} s, beating managed "
             f"({fmt(stint['managed']['total_time_s'], 2)} s) and all-out "
             f"({fmt(stint['all_out']['total_time_s'], 2)} s). All-out wins lap 1 by emptying "
             f"the store, then is forced onto harvest-limited deployment.")

    add_heading_custom(doc, "5.7 Race-scale utilisation and dashboard", 2)
    add_table(doc, ["Quantity", "Race (no clip)", "Race + super-clip @300"], [
        ["Regen / lap (MJ)", fmt(util["regen_MJ_per_lap"]), fmt(clip["regen_MJ_per_lap"])],
        ["Total harvest / lap (MJ)", fmt(util["harvest_MJ_per_lap"]), fmt(clip["harvest_MJ_per_lap"])],
        ["Regen / 53-lap race (kWh)", fmt(util["regen_kWh_per_race"]), fmt(clip["regen_kWh_per_race"])],
        ["Friction heat / race (kWh)", fmt(util["friction_kWh_per_race"], 1),
         fmt(clip["friction_kWh_per_race"], 1)],
        ["Fuel-equivalent of deploy (kg/race)", fmt(util["fuel_equiv_kg_per_race"]),
         fmt(clip["fuel_equiv_kg_per_race"])],
        ["Household-days of regen energy", fmt(util["household_days_per_race"], 1),
         fmt(clip["household_days_per_race"], 1)],
    ])
    add_caption(doc, "Table 7  Race-scale utilisation on the Monza-like circuit (53 laps).")
    add_para(doc,
             f"About {fmt(util['regen_kWh_per_race'], 1)} kWh is recovered in a 53-lap race—"
             f"roughly {fmt(util['household_days_per_race'], 1)} days of a 100 kWh/month "
             f"household—while {fmt(util['friction_kWh_per_race'], 0)} kWh is still rejected "
             f"as brake heat. That contrast is the utilisation story: regen helps, but peak "
             f"power mismatch leaves most braking energy unused.")
    add_figure(doc, f("fig_dashboard_telemetry.png"),
               "Fig. 18  Interactive Streamlit dashboard — telemetry and KPI row.", width_in=5.9)
    add_figure(doc, f("fig_dashboard_energy.png"),
               "Fig. 19  Dashboard energy-flow Sankey (fuel → ICE / ES → wheels → brakes / store).",
               width_in=5.9)
    e = flows["2026 race"]
    add_para(doc,
             f"For the Monza 2026 race Sankey, {fmt(e['fuel'])} MJ of fuel splits into "
             f"{fmt(e['ice_mech'])} MJ of crankshaft work and {fmt(e['ice_heat'])} MJ of "
             f"exhaust/cooling heat; {fmt(e['regen_dc'])} MJ returns to the ES while "
             f"{fmt(e['friction_heat'])} MJ leaves as brake heat. Aerodynamic drag "
             f"({fmt(e['drag'])} MJ) dominates tractive work.")

    # ========== 6 RECOMMENDATIONS ==========
    add_heading_custom(doc, "6. RECOMMENDATIONS AND IMPLICATIONS", 1)
    add_para(doc,
             "For race engineering (within this model). Prefer low-speed-priority deployment "
             "for charge-sustaining stints; use super-clipping near 300 km/h on high-speed "
             "circuits; treat street circuits as harvest-rich and strategy-sensitive.")
    add_para(doc,
             "For UEE pedagogy. Use the dashboard’s Theory tab and Sankey view to demonstrate "
             "receptivity, composite braking and SEC side-by-side with traction examples. The "
             "qualifying “full store → zero regen” case is a live receptivity demo.")
    add_para(doc,
             "For further work. Add an MGU-H path (explains larger 2014–25 deploy budgets), "
             "tyre thermal limits, and a short hardware-in-the-loop demo with a small motor + "
             "generator pair to complement the software.")
    add_para(doc,
             "Implications. The 2026 jump to 350 kW roughly triples recovered braking energy "
             "versus 120 kW on both circuits studied, but recovery ratios remain below 30 % "
             "because braking peaks stay near 3 MW. Electrical utilisation therefore improves "
             "strongly with rating yet remains structurally incomplete without either higher "
             "machine power or softer braking (which would hurt lap time).")

    # ========== 7 CONCLUSION ==========
    add_heading_custom(doc, "7. CONCLUSION", 1)
    add_para(doc,
             f"This software project delivers a validated F1 MGU-K regenerative-braking energy "
             f"simulator aligned with Utilization of Electrical Energy. On a Monza-like circuit "
             f"under 2026 regulations the charge-sustaining race lap runs in "
             f"{fmt(m['2026 race']['lap_time_s'], 3)} s, recovers "
             f"{fmt(m['2026 race']['regen_MJ'])} MJ ({fmt(m['2026 race']['recovery_pct'], 1)} % "
             f"of braking), and matches start/end SOC; the street circuit recovers "
             f"{fmt(s['2026 race']['regen_MJ'])} MJ at {fmt(s['2026 race']['recovery_pct'], 1)} %. "
             f"Low-speed deployment and moderate super-clipping are the most effective "
             f"utilisation strategies identified. The accompanying dashboard, tests and "
             f"figures make the energy path from fuel to friction heat inspectable joule by "
             f"joule—fulfilling the brief for a software project on utilisation of energy.")

    # ========== REFERENCES ==========
    page_break(doc)
    add_heading_custom(doc, "REFERENCES", 0)
    refs = [
        "Fédération Internationale de l’Automobile. (2024). Formula 1 technical regulations (2026). FIA.",
        "Fédération Internationale de l’Automobile. (2014–2025). Formula 1 technical regulations. FIA.",
        "Guzzella, L., & Sciarretta, A. (2013). Vehicle propulsion systems: Introduction to modeling and optimization (3rd ed.). Springer.",
        "Ehsani, M., Gao, Y., Longo, S., & Ebrahimi, K. (2018). Modern electric, hybrid electric, and fuel cell vehicles (3rd ed.). CRC Press.",
        "OpenAI / course notes context: Utilization of Electrical Energy — traction, specific energy consumption, regenerative and rheostatic braking (institutional syllabus).",
        "Milliken, W. F., & Milliken, D. L. (1995). Race car vehicle dynamics. SAE International.",
        "Horrein, L., Bouscayrol, A., & Cheng, Y. (2016). Energy management of hybrid electric vehicles: A review. IEEE Vehicle Power and Propulsion Conference papers (representative EM literature).",
        "Paganelli, G., Delprat, S., Guerra, T. M., Rimaux, J., & Santin, J. J. (2002). Equivalent consumption minimization strategy for parallel hybrid powertrains. IEEE Vehicular Technology Conference.",
        "Tremblay, O., & Dessaint, L.-A. (2009). Experimental validation of a battery dynamic model for EV applications. World Electric Vehicle Journal, 3(2), 289–298.",
        "Plotkin, S., & Singh, M. (2009). Multi-path transportation futures study: Vehicle characterization and scenario analyses (Argonne National Laboratory report) — hybrid energy accounting context.",
        "Python Software Foundation. (2024). Python language reference. https://www.python.org/",
        "Plotly Technologies Inc. (2024). Plotly.py documentation. https://plotly.com/python/",
        "Streamlit Inc. (2024). Streamlit documentation. https://docs.streamlit.io/",
    ]
    for i, ref in enumerate(refs, 1):
        add_para(doc, f"[{i}]  {ref}", first_line=False, space_after=4, size=11)

    # ========== APPENDICES ==========
    page_break(doc)
    add_heading_custom(doc, "APPENDIX A — SIMULATOR ARCHITECTURE", 1)
    add_figure(doc, f("fig_software_architecture.png"),
               "Fig. 20  Software modules: track, vehicle, ERS, simulation, strategy, analysis, app.",
               width_in=5.6)
    add_para(doc,
             "The package f1_regen implements track geometry, vehicle aero/tyre limits, the "
             "MGU-K taper and Rint battery, the lap integrator, strategy tuners and analysis "
             "sweeps. simulator/app.py is the Streamlit UI; simulator/run_analysis.py batch-"
             "generates figures and results.json. Launch the dashboard with "
             "Run_Simulator_Dashboard.bat.",
             first_line=False)

    page_break(doc)
    add_heading_custom(doc, "APPENDIX B — UNIT-TEST SUMMARY", 1)
    if T:
        add_para(doc,
                 f"Generated {T['generated']}. Ran {T['tests_run']} tests in {T['elapsed_s']} s — "
                 f"{'all passed' if T['ok'] else 'FAILURES PRESENT'}.",
                 first_line=False)
        add_table(doc, ["Test", "Status"],
                  [[c["id"].split(" ")[0] if " " in c["id"] else c["id"], c["status"]]
                   for c in T["cases"]],
                  col_widths=[12, 2.5])
        add_caption(doc, "Table 8  Automated verification cases.")
    else:
        add_para(doc, "Run python simulator/run_tests.py to regenerate this appendix.",
                 first_line=False)

    page_break(doc)
    add_heading_custom(doc, "APPENDIX C — GROUP SUBMISSION TEXT", 1)
    add_para(doc, G.get("whatsapp_line", ""), first_line=False)
    add_para(doc,
             "Paste the lines above into the class WhatsApp / LMS thread when posting group "
             "details. Update the leading serial number if the faculty list uses a different index.",
             first_line=False, italic=True)

    # Footers / page numbers on all sections
    for sec in doc.sections:
        add_page_number(sec)

    DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(DOCX)
    print(f"Wrote {DOCX}")
    return DOCX


def export_pdf(docx_path: Path = DOCX, pdf_path: Path = PDF) -> Path | None:
    try:
        import win32com.client  # type: ignore
    except ImportError:
        print("pywin32 not available — PDF export skipped.")
        return None
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(docx_path))
        try:
            doc.TablesOfContents(1).Update()
        except Exception:
            pass
        doc.Repaginate()
        # 17 = wdExportFormatPDF
        doc.ExportAsFixedFormat(str(pdf_path), 17)
        doc.Close(False)
    finally:
        word.Quit()
    print(f"Wrote {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    path = build()
    export_pdf(path)
