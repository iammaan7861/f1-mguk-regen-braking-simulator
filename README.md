# F1 MGU-K Regenerative Braking Energy Simulator

Software project for **Utilization of Electrical Energy (UEE)** — Punjab Engineering College (Deemed to be University), Chandigarh.

**Topic:** F1 MGU-K Regenerative Braking Energy Simulator

## Group

| Name | SID |
|------|-----|
| Babbalpreet Singh | 23104092 |
| Anmoldeep Singh | 23104111 |
| Priyanshu | 23104112 |
| Deepanshu | 23104069 |
| Sarthak | 23104115 |

WhatsApp / LMS one-liner is in [`Group_Submission.txt`](Group_Submission.txt). Edit `group_details.json` if a name spelling should change, then rebuild the report/PPT.

## What you get

| Deliverable | Path |
|-------------|------|
| Interactive dashboard | `Run_Simulator_Dashboard.bat` or `streamlit run simulator/app.py` |
| Project report | `Project_Report.docx` / `Project_Report.pdf` |
| Viva slides | `Presentation.pptx` / `Presentation.pdf` |
| Results + figures | `outputs/results.json`, `outputs/figures/` |
| Group post text | `Group_Submission.txt` |

## Quick start

```bat
pip install -r requirements.txt
Run_Simulator_Dashboard.bat
```

Optional full rebuild (analysis + screenshots + tests + report + PPT):

```bat
python build_all.py
```

Report/PPT only (uses existing `outputs/`):

```bat
Rebuild_Report_and_PPT.bat
```

## Suggested task split

| Member | Focus |
|--------|--------|
| Babbalpreet Singh | Physics / ERS model, energy balance, viva theory questions |
| Anmoldeep Singh | Strategy tuner, era/circuit studies, Tables 3–6 |
| Priyanshu | Streamlit dashboard + live demo path |
| Deepanshu | Figures, report Chapters 5–6, utilisation numbers |
| Sarthak | Presentation, Group_Submission post, test run / Appendix B |

## Timeline (after Diwali break)

1. Fill semester on the cover page (`group_details.json` → rebuild).
2. Dry-run the dashboard together once; each member can explain one tab.
3. Print / submit `Project_Report.pdf`; keep DOCX for edits.
4. Viva: open dashboard → Telemetry → Energy flow → Braking zones → Theory.

## Syllabus mapping (UEE ↔ F1)

| UEE idea | Simulator counterpart |
|----------|----------------------|
| Composite braking | MGU-K regen + friction residual |
| Receptivity of supply | ES SOC headroom (full store → zero regen) |
| Speed–time curve | Lap speed / time profiles |
| SEC (Wh/t-km) | Gross and net SEC vs EMU 50–75 Wh/t-km |
| Four-quadrant operation | MGU-K motor / generator modes |

## Notes / limitations

- Teaching model with representative parameters — **not** confidential team data.
- **MGU-H is not modelled**; 2014–25 charge-sustaining deploy is therefore harvest-limited (~0.73 MJ on Monza).
- Confirm submission date with your UEE faculty (peer guidelines mention mid/late October 2026).
