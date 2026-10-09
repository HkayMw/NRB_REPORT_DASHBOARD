"""Report Dashboard: Streamlit entry point (live office app or public demo)."""

import streamlit as st

from nrb import auth, config, ui
from nrb.application.services.admin_settings import AdminSettingsService
from nrb.application.errors import log_unexpected
from nrb.application.services.authentication import AuthenticationService
from nrb.application.services.authorization import AuthorizationService
from nrb.application.services.database_backup import DatabaseBackupService
from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.services.generate_monthly_report import MonthlyReportService
from nrb.application.services.report_configuration import ReportConfigService
from nrb.application.services.report_footer import ReportFooterService
from nrb.application.services.schedule_management import ScheduleService
from nrb.application.services.user_management import UserManagementService
from nrb.infrastructure.repositories.admin_settings import MongoAdminSettingsRepository
from nrb.infrastructure.repositories.database_backup import (
    MongoDatabaseBackupRepository,
)
from nrb.infrastructure.repositories.report_config import MongoReportConfigRepository
from nrb.infrastructure.repositories.schedules import MongoScheduleRepository
from nrb.infrastructure.repositories.users import MongoUserRepository
from nrb.infrastructure.repositories import mongo as db
from nrb.infrastructure.exporters import excel as export
from nrb.infrastructure.data_sources import demo_csv, google_sheets
from nrb.domain import roles
from nrb.domain.passwords import hash_password, verify_password
from nrb.views import admin, compliance, monthly, overview, quality, schedule

sheets = demo_csv if config.DEMO_MODE else google_sheets

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="auto",
)
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
except Exception as error:
    log_unexpected("Initialize MongoDB", error)
    ui.header("🪪", config.APP_TITLE)
    st.error(
        "Could not initialize the database. Check the connection settings and logs."
    )
    st.stop()

if config.DEMO_MODE:
    db.ensure_demo_accounts(hash_password)

user_repository = MongoUserRepository()
authorization_service = AuthorizationService(user_repository)
authentication_service = AuthenticationService(
    user_repository, hash_password, verify_password
)

# First run: force admin account creation.
if authentication_service.count_users() == 0 and not auth.is_logged_in():
    auth.render_first_run_setup(authentication_service)
    st.stop()

auth.render_sidebar_auth(authentication_service)
if config.DEMO_MODE:
    ui.demo_notice()

report_config_service = ReportConfigService(
    MongoReportConfigRepository(), authorization_service
)
settings_repository = MongoAdminSettingsRepository()
reporting_data_service = ReportingDataService(settings_repository, sheets)
admin_settings_service = AdminSettingsService(
    settings_repository,
    sheets.fetch_responses,
    sheets.clear_cache,
    authorization_service,
)
can_view = admin_settings_service.can_view_dashboard(auth.is_logged_in())
report_footer_service = ReportFooterService(settings_repository, authorization_service)
user_management_service = UserManagementService(
    user_repository, hash_password, authorization_service
)
database_backup_service = DatabaseBackupService(
    MongoDatabaseBackupRepository(), authorization_service
)
schedule_service = ScheduleService(MongoScheduleRepository(), authorization_service)
monthly_report_service = MonthlyReportService(export)


def _login_required():
    ui.header("🪪", config.APP_TITLE)
    st.info("Please log in from the sidebar to view the dashboard.")


nav = {}
if can_view:
    nav["Monitor"] = [
        st.Page(
            lambda: overview.render(report_config_service, reporting_data_service),
            title="Dashboard",
            icon="📊",
            url_path="dashboard",
            default=True,
        ),
        st.Page(
            lambda: compliance.render(schedule_service, reporting_data_service),
            title="Compliance",
            icon="✅",
            url_path="compliance",
        ),
        st.Page(
            lambda: quality.render(reporting_data_service),
            title="Data Quality",
            icon="🧹",
            url_path="quality",
        ),
    ]
    nav["Reports"] = [
        st.Page(
            lambda: monthly.render(
                report_config_service,
                report_footer_service,
                reporting_data_service,
                monthly_report_service,
            ),
            title="Monthly Report",
            icon="📑",
            url_path="monthly",
        ),
    ]
else:
    nav[""] = [st.Page(_login_required, title="Home", icon="🏠", default=True)]

manage = []
if auth.can(roles.CREATE_SCHEDULE):
    manage.append(
        st.Page(
            lambda: schedule.render(schedule_service),
            title="Scheduling",
            icon="🗓️",
            url_path="scheduling",
        )
    )
if auth.is_admin() or auth.can(roles.MANAGE_ROSTER):
    manage.append(
        st.Page(
            lambda: admin.render(
                report_config_service,
                admin_settings_service,
                user_management_service,
                database_backup_service,
            ),
            title="Admin",
            icon="⚙️",
            url_path="admin",
        )
    )
if manage:
    nav["Manage"] = manage

st.navigation(nav).run()
