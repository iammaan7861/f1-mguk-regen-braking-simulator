"""Shared Streamlit / Plotly look for the F1 ERS dashboard."""
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
    background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px;
    padding: 0.55rem 0.75rem;
  }
  div[data-testid="stMetric"] label { font-size: 0.78rem !important; color: #495057 !important; }
  div[data-testid="stMetricValue"] { font-size: 1.35rem !important; color: #212529 !important; }
  .ers-banner {
    background: linear-gradient(90deg, #1b3a6b 0%, #d62728 100%);
    color: #fff; border-radius: 10px; padding: 0.85rem 1.1rem; margin-bottom: 0.85rem;
  }
  .ers-banner h1 { color: #fff !important; font-size: 1.55rem; margin: 0 0 0.25rem 0; }
  .ers-banner p { margin: 0; opacity: 0.92; font-size: 0.92rem; }
  .ers-chip-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.4rem 0 0.6rem 0; }
  div[data-testid="stTabs"] button[role="tab"] { font-weight: 600; }
  footer { visibility: hidden; }
</style>
"""

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#212529"),
    margin=dict(t=48, b=40, l=50, r=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified",
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
