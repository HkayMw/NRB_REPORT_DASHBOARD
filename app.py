"""Mzuzu NRB Report Dashboard — Streamlit entry point."""

import streamlit as st

from nrb import auth, config, db, ui
from nrb.views import admin, compliance, monthly, overview, quality, schedule

st.set_page_config(page_title=config.APP_TITLE, page_icon="🪪", layout="wide",
                   initial_sidebar_state="auto")
ui.inject_css()


def _connection_help():
    ui.header("🪪", config.APP_TITLE)
    st.error("No database configured — the app needs a MongoDB Atlas connection.")
    st.markdown(
        """
**One-time setup (free):**

1. Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas)
   (Shared / M0 tier).
2. Create a **database user** (Database Access) and allow access from anywhere
   (Network Access → `0.0.0.0/0`) so Streamlit Cloud can reach it.
3. Copy the connection string: *Database → Connect → Drivers*.
4. Provide it to the app as `MONGODB_URI`:
   - **Locally:** copy `.streamlit/secrets.toml.example` to
     `.streamlit/secrets.toml` and paste the URI there.
   - **Streamlit Cloud:** App → Settings → Secrets →
     `MONGODB_URI = "mongodb+srv://…"`.
5. Reload this page.
        """
    )


if not db.configured():
    _connection_help()
    st.stop()

try:
    db.init_db()
except Exception as e:
    ui.header("🪪", config.APP_TITLE)
    st.error(f"Could not connect to MongoDB: {e}")
    st.caption("Check the MONGODB_URI secret, the database user's password, and "
               "that Network Access allows this host.")
    st.stop()

# First run: force admin account creation.
if db.count_users() == 0 and not auth.is_logged_in():
    auth.render_first_run_setup()
    st.stop()

auth.render_sidebar_auth()

public = db.get_setting("public_viewing", True)
can_view = public or auth.is_logged_in()


def _login_required():
    ui.header("🪪", config.APP_TITLE)
    st.info("Please log in from the sidebar to view the dashboard.")


nav = {}
if can_view:
    nav["Monitor"] = [
        st.Page(overview.render, title="Dashboard", icon="📊", url_path="dashboard",
                default=True),
        st.Page(compliance.render, title="Compliance", icon="✅", url_path="compliance"),
        st.Page(quality.render, title="Data Quality", icon="🧹", url_path="quality"),
    ]
    nav["Reports"] = [
        st.Page(monthly.render, title="Monthly Report", icon="📑", url_path="monthly"),
    ]
else:
    nav[""] = [st.Page(_login_required, title="Home", icon="🏠", default=True)]

if auth.is_admin():
    nav["Manage"] = [
        st.Page(schedule.render, title="Scheduling", icon="🗓️", url_path="scheduling"),
        st.Page(admin.render, title="Admin", icon="⚙️", url_path="admin"),
    ]

st.navigation(nav).run()
