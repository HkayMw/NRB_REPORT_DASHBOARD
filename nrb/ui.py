"""Shared UI: global CSS (incl. mobile tweaks) and page headers."""

import streamlit as st

_CSS = """
<style>
/* Hide Streamlit chrome viewers don't need */
/* Hide the hosting toolbar's Fork / GitHub / Deploy buttons and the footer.
   Keep [data-testid="stToolbar"] itself visible: it also holds the button
   that re-opens a collapsed sidebar. */
[data-testid="stToolbarActions"], .stDeployButton, footer,
[data-testid="stDecoration"] { display: none !important; }

/* Tighter, capped content column (leave room for the fixed app header) */
.block-container { padding-top: 3.2rem; padding-bottom: 4rem; max-width: 1200px; }

/* Page header */
.nrb-header { margin-bottom: 0.4rem; }
.nrb-header h1 {
    font-size: 2rem; font-weight: 800; letter-spacing: -0.02em;
    margin: 0 0 0.15rem 0; padding: 0;
}
.nrb-header .nrb-sub { color: rgba(150, 158, 170, 1); font-size: 0.95rem; margin: 0; }
.nrb-header .nrb-bar {
    width: 3.2rem; height: 4px; border-radius: 2px;
    background: var(--primary-color, #10b981); margin: 0.55rem 0 0.2rem 0;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: rgba(140, 150, 165, 0.07);
    border: 1px solid rgba(140, 150, 165, 0.18);
    border-radius: 0.6rem; padding: 0.9rem 1rem;
}
[data-testid="stMetricLabel"] { opacity: 0.85; }

/* Sidebar polish */
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
[data-testid="stSidebarHeader"] { padding-bottom: 0; }

/* Buttons and tabs */
.stButton > button, .stDownloadButton > button { border-radius: 0.5rem; }
.stTabs [data-baseweb="tab-list"] { gap: 0.25rem; }

/* Code blocks (WhatsApp message) wrap on small screens */
.stCode pre, pre code { white-space: pre-wrap !important; word-break: break-word; }

/* Phones */
@media (max-width: 640px) {
    .block-container { padding-left: 0.9rem; padding-right: 0.9rem; padding-top: 2.6rem; }
    .nrb-header h1 { font-size: 1.45rem; }
    [data-testid="stMetric"] { padding: 0.6rem 0.7rem; }
    [data-testid="stMetricValue"] { font-size: 1.35rem; }
    .stTabs [data-baseweb="tab"] { padding: 0.35rem 0.55rem; font-size: 0.85rem; }
}
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def header(icon: str, title: str, subtitle: str = ""):
    sub = f'<p class="nrb-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="nrb-header"><h1>{icon}&nbsp; {title}</h1>'
        f'<div class="nrb-bar"></div>{sub}</div>',
        unsafe_allow_html=True,
    )


def demo_notice():
    """Sidebar note explaining the demo data and the published logins."""
    from nrb import config

    accounts = "\n".join(
        f"- **{username}** ({role})" for username, _, role in config.DEMO_ACCOUNTS
    )
    with st.sidebar:
        st.info(
            "**Demo build.** All names and figures are synthetic, generated for "
            f"{config.DEMO_DATA_START:%B %Y} to {config.DEMO_AS_OF:%B %Y}. "
            f"The demo treats {config.DEMO_AS_OF:%d %B %Y} as today.\n\n"
            f"Try a login (password **{config.DEMO_PASSWORD}**):\n{accounts}\n\n"
            "Changes are kept in memory and reset when the app restarts."
        )
