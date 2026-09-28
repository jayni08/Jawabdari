"""Shared look & feel for every Jawabdari page: page setup, CSS, banner header, badges, cards.

Only presentation lives here - no business rules (those stay in services.py).
All text passed into the HTML helpers is escaped, so user-typed names are always safe.
"""

import html

import streamlit as st

# Brand colours (kept in one place so every page matches)
INDIGO = "#4338ca"
GREEN = "#1e7a3c"
AMBER = "#b45309"
RED = "#b42318"
GREY = "#5f6368"
CONTRACTOR_BLUE = "#2a78d6"   # chart series 1 (validated colour-blind-safe pair)
CITY_ORANGE = "#eb6834"       # chart series 2

CSS = """
<style>
/* ---------- layout ---------- */
.block-container, [data-testid="stMainBlockContainer"] {
  padding-top: 4.6rem !important; padding-bottom: 3rem; max-width: 1200px; }
h1, h2, h3 { letter-spacing: -0.01em; }
hr { margin: 1.2rem 0; }

/* ---------- metric tiles as cards ---------- */
[data-testid="stMetric"] {
  background: #ffffff; border: 1px solid #e2e4ef; border-radius: 14px;
  padding: 14px 16px; box-shadow: 0 1px 2px rgba(28, 29, 43, 0.04);
}
[data-testid="stMetricLabel"] p {
  font-size: 0.78rem; font-weight: 600; color: #5b5f77;
  text-transform: uppercase; letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] { font-weight: 700; }

/* ---------- bordered containers become white cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stVerticalBlock"][class*="border"] {
  background: #ffffff;
}

/* ---------- banner header ---------- */
.jw-hero {
  position: relative; overflow: hidden; border-radius: 18px; padding: 24px 28px 22px;
  margin: 0 0 18px; color: #ffffff;
  background: linear-gradient(125deg, #231f6b 0%, #4338ca 55%, #6d5df2 100%);
  box-shadow: 0 8px 24px rgba(67, 56, 202, 0.18);
}
.jw-hero::after {             /* saffron accent bar */
  content: ""; position: absolute; left: 0; bottom: 0; height: 5px; width: 100%;
  background: linear-gradient(90deg, #f5b700, #ff8a3d);
}
.jw-eyebrow { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; opacity: 0.8; }
.jw-title { font-size: 1.9rem; font-weight: 800; line-height: 1.2; margin: 4px 0 6px; }
.jw-sub { font-size: 1rem; opacity: 0.92; max-width: 780px; line-height: 1.5; }
.jw-brand { position: absolute; right: 24px; top: 20px; text-align: right; opacity: 0.9;
  font-size: 0.8rem; line-height: 1.4; }
.jw-brand b { font-size: 1.05rem; letter-spacing: 0.02em; }
@media (max-width: 640px) {
  .jw-hero { padding: 18px 18px 18px; }
  .jw-title { font-size: 1.45rem; }
  .jw-brand { display: none; }
}

/* ---------- section titles ---------- */
.jw-section { margin: 22px 0 8px; }
.jw-section .t { font-size: 1.15rem; font-weight: 700; }
.jw-section .c { color: #5b5f77; font-size: 0.9rem; margin-top: 2px; }

/* ---------- badges ---------- */
.jw-pill { display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; white-space: nowrap; }
.jw-pill.green { background: #e3f4e8; color: #145c2a; }
.jw-pill.amber { background: #fff1d6; color: #7a4b00; }
.jw-pill.red   { background: #fde4e2; color: #8a1c14; }
.jw-pill.grey  { background: #eceef3; color: #3c4043; }
.jw-pill.indigo{ background: #e7e6fb; color: #2e2789; }

/* ---------- big status banner (citizen pages, results) ---------- */
.jw-status { border-radius: 14px; padding: 16px 18px; margin: 6px 0 14px;
  font-size: 1.12rem; line-height: 1.55; border: 1px solid transparent; }
.jw-status .h { font-size: 1.35rem; font-weight: 800; margin-bottom: 4px; }
.jw-status.green { background: #e7f5ec; border-color: #b7e0c3; color: #0f3d1d; }
.jw-status.amber { background: #fff4e0; border-color: #f5d49a; color: #4d2f00; }
.jw-status.grey  { background: #f0f1f4; border-color: #d9dbe2; color: #202124; }

/* ---------- fact grid ---------- */
.jw-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 8px 0 14px; }
.jw-fact { background: #ffffff; border: 1px solid #e2e4ef; border-radius: 12px; padding: 10px 12px; }
.jw-fact .k { font-size: 0.72rem; font-weight: 600; color: #5b5f77; text-transform: uppercase;
  letter-spacing: 0.04em; }
.jw-fact .v { font-size: 1.02rem; font-weight: 600; margin-top: 2px; overflow-wrap: anywhere; }
.jw-stars { color: #f5a623; letter-spacing: 1px; }

/* ---------- work card header (inside st.container) ---------- */
.jw-card-title { font-weight: 700; font-size: 1.02rem; }
.jw-card-meta { color: #5b5f77; font-size: 0.86rem; margin-top: 2px; }

/* ---------- timeline ---------- */
.jw-timeline { border-left: 2px solid #e2e4ef; margin-left: 8px; padding-left: 16px; }
.jw-tl-item { position: relative; margin: 0 0 12px; }
.jw-tl-item::before { content: ""; position: absolute; left: -23px; top: 5px; width: 12px; height: 12px;
  border-radius: 50%; background: #4338ca; border: 2px solid #ffffff; box-shadow: 0 0 0 1px #c7c9f5; }
.jw-tl-date { font-size: 0.78rem; color: #5b5f77; font-weight: 600; }
.jw-tl-text { font-size: 0.95rem; }

/* ---------- page links look like big primary buttons (Public board -> Report) ---------- */
[data-testid="stPageLink"] a {
  background: #4338ca; border-radius: 12px; padding: 0.75rem 1rem; justify-content: center;
  box-shadow: 0 4px 12px rgba(67, 56, 202, 0.25);
}
[data-testid="stPageLink"] a, [data-testid="stPageLink"] a * { color: #ffffff !important; font-size: 1.05rem; }
[data-testid="stPageLink"] a:hover { background: #3730a3; }

/* ---------- buttons a touch bolder ---------- */
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a { font-weight: 600; }
</style>
"""


def esc(value):
    """Escape any value for safe use inside HTML."""
    return html.escape("" if value is None else str(value))


def setup(title, icon, layout="wide"):
    """Call first on every page: browser tab title/icon + shared CSS."""
    st.set_page_config(page_title=f"{title} · Jawabdari", page_icon=icon, layout=layout)
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle="", eyebrow="Ahmedabad Municipal Corporation", show_brand=True):
    """Gradient banner at the top of a page. `title`/`subtitle` are escaped."""
    brand = ('<div class="jw-brand"><b>Jawabdari</b><br>जवाबदारी · જવાબદારી</div>'
             if show_brand else "")
    st.markdown(
        f'<div class="jw-hero">{brand}<div class="jw-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="jw-title">{esc(title)}</div><div class="jw-sub">{esc(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def section(title, caption=""):
    """Section heading with an optional grey caption line."""
    cap = f'<div class="c">{esc(caption)}</div>' if caption else ""
    st.markdown(f'<div class="jw-section"><div class="t">{esc(title)}</div>{cap}</div>',
                unsafe_allow_html=True)


def pill(text, tone="grey"):
    """Small rounded badge as an HTML string (tone: green, amber, red, grey, indigo)."""
    return f'<span class="jw-pill {tone}">{esc(text)}</span>'


def status_banner(heading, body, tone="green"):
    """Big coloured result / status box (tone: green, amber, grey)."""
    st.markdown(
        f'<div class="jw-status {tone}"><div class="h">{esc(heading)}</div>{esc(body)}</div>',
        unsafe_allow_html=True,
    )


def facts(items):
    """Two-column grid of label/value facts. `items` = list of (label, value, is_html)."""
    cells = []
    for label, value, is_html in items:
        shown = value if is_html else esc(value)
        cells.append(f'<div class="jw-fact"><div class="k">{esc(label)}</div><div class="v">{shown}</div></div>')
    st.markdown(f'<div class="jw-facts">{"".join(cells)}</div>', unsafe_allow_html=True)


def card_header(title, meta="", badge_html=""):
    """Title row used inside st.container(border=True) cards."""
    st.markdown(
        f'<div class="jw-card-title">{esc(title)} {badge_html}</div>'
        f'<div class="jw-card-meta">{esc(meta)}</div>',
        unsafe_allow_html=True,
    )


def timeline(events, icons):
    """Vertical timeline of audit events (list of dicts with created_at, event_type, details)."""
    items = []
    for e in events:
        icon = icons.get(e["event_type"], "•")
        items.append(
            f'<div class="jw-tl-item"><div class="jw-tl-date">{esc(e["created_at"][:10])} · '
            f'{icon} {esc(e["event_type"].replace("_", " ").title())}</div>'
            f'<div class="jw-tl-text">{esc(e["details"])}</div></div>'
        )
    st.markdown(f'<div class="jw-timeline">{"".join(items)}</div>', unsafe_allow_html=True)


def stars(score):
    """Score 0-100 -> '★★★☆☆' (1 to 5 stars)."""
    filled = max(1, min(5, round(score / 20)))
    return "★" * filled + "☆" * (5 - filled)


def score_tone(score):
    return "red" if score < 60 else ("amber" if score < 85 else "green")
