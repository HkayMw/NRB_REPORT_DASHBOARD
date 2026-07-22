"""Mzuzu NRB Report Dashboard — Streamlit entry point."""

import streamlit as st

from nrb import auth, config, db
from nrb.views import admin, compliance, monthly, overview, quality, schedule

st.set_page_config(page_title=config.APP_TITLE, page_icon="🪪", layout="wide")

db.init_db()

# First run: force admin account creation.
if db.count_users() == 0 and not auth.is_logged_in():
    auth.render_first_run_setup()
    st.stop()

auth.render_sidebar_auth()

public = db.get_setting("public_viewing", True)
can_view = public or auth.is_logged_in()


def _login_required():
    st.title(config.APP_TITLE)
    st.info("Please log in from the sidebar to view the dashboard.")


pages = []
if can_view:
    pages += [
        st.Page(overview.render, title="Dashboard", icon="📊", url_path="dashboard",
                default=True),
        st.Page(compliance.render, title="Compliance", icon="✅", url_path="compliance"),
        st.Page(quality.render, title="Data Quality", icon="🧹", url_path="quality"),
        st.Page(monthly.render, title="Monthly Report", icon="📑", url_path="monthly"),
    ]
else:
    pages.append(st.Page(_login_required, title="Home", icon="🏠", default=True))

if auth.is_admin():
    pages += [
        st.Page(schedule.render, title="Scheduling", icon="🗓️", url_path="scheduling"),
        st.Page(admin.render, title="Admin", icon="⚙️", url_path="admin"),
    ]

st.navigation(pages).run()
