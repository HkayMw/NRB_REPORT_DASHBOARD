"""Admin: data source, roster, report layout, users, database."""

import json

import pandas as pd
import streamlit as st

from nrb import auth, config, ui
from nrb.application.errors import ApplicationError, log_unexpected
from nrb.application.services.admin_settings import AdminSettingsService
from nrb.application.services.database_backup import (
    BackupRestoreError,
    BackupValidationError,
    DatabaseBackupService,
)
from nrb.application.services.report_configuration import ReportConfigService
from nrb.application.services.user_management import UserManagementService
from nrb.domain import report_config as reportcfg


def render(
    report_config_service: ReportConfigService,
    admin_settings_service: AdminSettingsService,
    user_management_service: UserManagementService,
    database_backup_service: DatabaseBackupService,
):
    ui.header(
        "⚙️", "Administration", "Data source, roster, report layout, users, database"
    )
    if not auth.is_admin():
        st.warning("Administrators only — log in from the sidebar.")
        return
    tab_src, tab_roster, tab_layout, tab_users, tab_db = st.tabs(
        ["Data source", "Roster", "Report layout", "Users", "Database"]
    )
    with tab_src:
        _source_tab(admin_settings_service, auth.current_user())
    with tab_roster:
        _roster_tab(admin_settings_service, auth.current_user())
    with tab_layout:
        _layout_tab(report_config_service, auth.current_user())
    with tab_users:
        _users_tab(user_management_service, auth.current_user())
    with tab_db:
        _database_tab(database_backup_service, auth.current_user())


def _source_tab(admin_settings_service: AdminSettingsService, actor: dict | None):
    url = admin_settings_service.get_sheet_url()
    new_url = st.text_input("Google Sheet URL (form responses)", url)
    c1, c2 = st.columns(2)
    if c1.button("Save & test"):
        try:
            df = admin_settings_service.test_and_save_sheet_url(new_url, actor)
            st.success(f"Connected — {len(df)} rows, {len(df.columns)} columns.")
        except ApplicationError as error:
            st.error(str(error))
        except Exception as error:
            log_unexpected("Render sheet connection test failure", error)
            st.error("Could not read that sheet. Check the URL and sharing access.")
    if c2.button("Clear cache / force refresh"):
        admin_settings_service.clear_source_cache(actor)
        st.success("Cache cleared.")
    public = admin_settings_service.get_public_viewing()
    new_public = st.toggle(
        "Public viewing (dashboards visible without login)",
        value=public,
        help="Report export, scheduling and admin always require login.",
    )
    if new_public != public:
        admin_settings_service.set_public_viewing(new_public, actor)
        st.rerun()


def _roster_tab(admin_settings_service: AdminSettingsService, actor: dict | None):
    st.caption(
        "The roster must match the form's Name dropdown exactly — rows "
        "whose names are not here are excluded as 'unknown'."
    )
    staff = admin_settings_service.list_staff()
    edited = st.data_editor(
        pd.DataFrame(
            [
                {
                    "Form name": s["form_name"],
                    "Full name": s["full_name"],
                    "Active": bool(s["active"]),
                }
                for s in staff
            ]
        ),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="roster_editor",
    )
    if st.button("Save roster"):
        try:
            admin_settings_service.save_roster(edited.to_dict(orient="records"), actor)
        except (ValueError, PermissionError, ApplicationError) as e:
            st.error(str(e))
            return
        st.success("Roster saved.")
        st.rerun()


def _layout_tab(report_config_service: ReportConfigService, actor: dict | None):
    st.caption(
        "Controls what the monthly report shows: groups → blocks → rows. Each row "
        "sums one or more form fields; give a row (or a block total) a "
        "`summary_label` to place it on the Report Summary sheet. Fields not "
        "referenced anywhere are ignored by the report."
    )
    cfg = report_config_service.get_report_config()

    # Readable mapping preview.
    rows = []
    for g in cfg["groups"]:
        for b in g["blocks"]:
            for r in b.get("rows", []):
                rows.append(
                    {
                        "Group": g["title"],
                        "Block": b["title"],
                        "Report row": r["label"],
                        "= sum of": " + ".join(r["fields"]),
                        "On summary as": r.get("summary_label") or "—",
                    }
                )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    used = {
        f
        for g in cfg["groups"]
        for b in g["blocks"]
        for r in b.get("rows", [])
        for f in r["fields"]
    }
    ignored = [f for f in config.ALL_NUMERIC_FIELDS if f not in used]
    if ignored:
        st.caption("Form fields currently ignored by the report: " + ", ".join(ignored))

    edited = st.text_area(
        "Edit configuration (JSON)", json.dumps(cfg, indent=2), height=420
    )
    c1, c2 = st.columns(2)
    if c1.button("Validate & save layout"):
        try:
            parsed = json.loads(edited)
            report_config_service.save_report_config(parsed, actor)
            st.success("Report layout saved.")
            st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        except ValueError as e:
            st.error(f"Invalid layout: {e}")
        except PermissionError as e:
            st.error(str(e))
        except ApplicationError as e:
            st.error(str(e))
    if c2.button("Reset to office default"):
        report_config_service.save_report_config(reportcfg.DEFAULT_REPORT_CONFIG, actor)
        st.success("Reset.")
        st.rerun()


def _users_tab(user_management_service: UserManagementService, actor: dict | None):
    users = user_management_service.list_users()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Username": u["username"],
                    "Full name": u["full_name"],
                    "Role": u["role"],
                    "Active": "✅" if u["active"] else "—",
                }
                for u in users
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    with st.form("new_user"):
        st.markdown("**Add user**")
        c1, c2 = st.columns(2)
        username = c1.text_input("Username")
        full_name = c2.text_input("Full name")
        c3, c4 = st.columns(2)
        password = c3.text_input("Password", type="password")
        role = c4.selectbox("Role", ["viewer", "admin"])
        if st.form_submit_button("Create user"):
            try:
                user_management_service.create_user(
                    username, full_name, password, role, actor
                )
                st.success("User created.")
                st.rerun()
            except (ValueError, PermissionError, ApplicationError) as e:
                st.error(str(e))

    if not users:
        return
    st.markdown("**Edit user**")
    pick = st.selectbox("User", [u["username"] for u in users])
    user = next((u for u in users if u["username"] == pick), None)
    if user is None:
        return
    c1, c2, c3 = st.columns(3)
    new_pw = c1.text_input(
        "New password (leave blank to keep)", type="password", key="edit_pw"
    )
    new_role = c2.selectbox(
        "Role",
        ["viewer", "admin"],
        index=0 if user["role"] == "viewer" else 1,
        key="edit_role",
    )
    new_active = c3.checkbox("Active", bool(user["active"]), key="edit_active")
    if st.button("Apply changes"):
        try:
            user_management_service.update_user(
                user["id"], new_role, new_active, new_pw, actor
            )
            st.success("Updated.")
            st.rerun()
        except (ValueError, PermissionError, ApplicationError) as e:
            st.error(str(e))


def _database_tab(database_backup_service: DatabaseBackupService, actor: dict | None):
    ok, detail = database_backup_service.database_status(actor)
    if ok:
        st.success(f"Connected to MongoDB · {detail}")
        st.caption(
            "Users, teams, schedules and settings persist in Atlas — "
            "nothing is lost on app restarts or redeploys. Form responses "
            "stay in Google Sheets as before."
        )
    else:
        st.error(f"MongoDB connection problem: {detail}")

    st.markdown("**Safety backup (JSON)**")
    st.caption(
        "Optional periodic snapshot of app data (accounts, teams, "
        "schedules, settings) — e.g. before big changes."
    )
    if ok:
        st.download_button(
            "⬇️ Download JSON backup",
            json.dumps(
                database_backup_service.create_backup(actor), indent=2, default=str
            ),
            file_name="nrb_dashboard_backup.json",
            mime="application/json",
        )
    up = st.file_uploader("Restore from backup (.json)", type=["json"])
    if up is not None and st.button("Restore now (overwrites current data)"):
        try:
            database_backup_service.restore_backup(json.load(up), actor)
            st.success("Restored.")
            st.rerun()
        except json.JSONDecodeError:
            st.error("Restore failed: uploaded file is not valid JSON.")
        except (BackupValidationError, BackupRestoreError, PermissionError) as e:
            st.error(f"Restore failed: {e}")
        except Exception as error:
            log_unexpected("Render database backup restore failure", error)
            st.error("Restore failed. Check application logs before retrying.")
