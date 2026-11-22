"""Shared Streamlit / Plotly look for the F1 ERS dashboard (dark theme)."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
GROUP_PATH = ROOT / "group_details.json"

CSS = """
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
  div[data-testid="stMetric"] {
    background: #1a1f2b; border: 1px solid #2d3548; border-radius: 8px;
    padding: 0.55rem 0.75rem;
  }
  div[data-testid="stMetric"] label { font-size: 0.78rem !important; color: #9aa0a6 !important; }
  div[data-testid="stMetricValue"] { font-size: 1.35rem !important; color: #e8eaed !important; }
  div[data-testid="stMetricDelta"] { color: #b0b3b8 !important; }
  .ers-banner {
    background: linear-gradient(105deg, #121826 0%, #1b3a6b 45%, #8b1e2d 100%);
    border: 1px solid #2d3548; color: #fff; border-radius: 10px;
    padding: 0.9rem 1.15rem; margin-bottom: 0.85rem;
  }
  .ers-banner h1 { color: #fff !important; font-size: 1.55rem; margin: 0 0 0.25rem 0; }
  .ers-banner p { margin: 0; opacity: 0.9; font-size: 0.92rem; color: #e8eaed !important; }
  div[data-testid="stTabs"] button[role="tab"] { font-weight: 600; }
  footer { visibility: hidden; }
  [data-testid="stSidebar"] { background: #0b0e14; }
</style>
"""

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(14,17,23,0.35)",
    font=dict(family="Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#e8eaed"),
    margin=dict(t=48, b=40, l=50, r=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
    hovermode="x unified",
    colorway=["#e63946", "#4cc9f0", "#2ec4b6", "#f4a261", "#9b5de5", "#adb5bd"],
)


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def load_group() -> dict:
    if GROUP_PATH.is_file():
        return json.loads(GROUP_PATH.read_text(encoding="utf-8"))
    return {"topic": "F1 MGU-K Regenerative Braking Energy Simulator", "members": []}


def render_banner(caption: str = "") -> None:
    g = load_group()
    members = " · ".join(f"{m['name']} ({m['sid']})" for m in g.get("members", []) if m.get("name"))
    topic = g.get("short_title") or g.get("topic") or "F1 ERS Simulator"
    extra = f"<p>{caption}</p>" if caption else ""
    st.markdown(
        f'<div class="ers-banner"><h1>{topic}</h1>'
        f'<p>{members}</p>{extra}</div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int | None = None):
    kw = dict(PLOTLY_LAYOUT)
    if height is not None:
        kw["height"] = height
    fig.update_layout(**kw)
    return fig
