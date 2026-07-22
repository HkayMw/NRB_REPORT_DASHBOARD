"""Admin: data source, roster, report layout, users, backup."""

import json
import os

import pandas as pd
import streamlit as st

from nrb import auth, config, data, db, reportcfg, sheets


def render():
    st.title("⚙️ Administration")
    if not auth.is_admin():
        st.warning("Administrators only — log in from the sidebar.")
        return
    tab_src, tab_roster, tab_layout, tab_users, tab_backup = st.tabs(
        ["Data source", "Roster", "Report layout", "Users", "Backup"])
    with tab_src:
        _source_tab()
    with tab_roster:
        _roster_tab()
    with tab_layout:
        _layout_tab()
    with tab_users:
        _users_tab()
    with tab_backup:
        _backup_tab()


def _source_tab():
    url = data.get_sheet_url()
    new_url = st.text_input("Google Sheet URL (form responses)", url)
    c1, c2 = st.columns(2)
    if c1.button("Save & test"):
        try:
            df = sheets.fetch_responses(new_url)
            db.set_setting("sheet_url", new_url)
            st.success(f"Connected — {len(df)} rows, {len(df.columns)} columns.")
        except Exception as e:
            st.error(f"Could not read that sheet: {e}")
    if c2.button("Clear cache / force refresh"):
        sheets.clear_cache()
        st.success("Cache cleared.")
    public = db.get_setting("public_viewing", True)
    new_public = st.toggle(
        "Public viewing (dashboards visible without login)", value=public,
        help="Report export, scheduling and admin always require login.")
    if new_public != public:
        db.set_setting("public_viewing", new_public)
        st.rerun()


def _roster_tab():
    st.caption("The roster must match the form's Name dropdown exactly — rows "
               "whose names are not here are excluded as 'unknown'.")
    staff = db.list_staff()
    edited = st.data_editor(
        pd.DataFrame([{"Form name": s["form_name"], "Full name": s["full_name"],
                       "Active": bool(s["active"])} for s in staff]),
        num_rows="dynamic", width="stretch", hide_index=True, key="roster_editor",
    )
    if st.button("Save roster"):
        new_names = [str(r["Form name"]).strip() for _, r in edited.iterrows()
                     if str(r.get("Form name", "")).strip()]
        if len(new_names) != len(set(new_names)):
            st.error("Duplicate form names in the table.")
            return
        existing = {s["form_name"]: s for s in staff}
        for _, r in edited.iterrows():
            name = str(r.get("Form name", "")).strip()
            if not name:
                continue
            prev = existing.pop(name, None)
            db.upsert_staff(name, str(r.get("Full name", "") or ""),
                            bool(r.get("Active", True)),
                            staff_id=prev["id"] if prev else None)
        for leftover in existing.values():
            db.delete_staff(leftover["id"])
        st.success("Roster saved.")
        st.rerun()


def _layout_tab():
    st.caption(
        "Controls what the monthly report shows: groups → blocks → rows. Each row "
        "sums one or more form fields; give a row (or a block total) a "
        "`summary_label` to place it on the Report Summary sheet. Fields not "
        "referenced anywhere are ignored by the report."
    )
    cfg = reportcfg.get_report_config()

    # Readable mapping preview.
    rows = []
    for g in cfg["groups"]:
        for b in g["blocks"]:
            for r in b.get("rows", []):
                rows.append({"Group": g["title"], "Block": b["title"],
                             "Report row": r["label"],
                             "= sum of": " + ".join(r["fields"]),
                             "On summary as": r.get("summary_label") or "—"})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    used = {f for g in cfg["groups"] for b in g["blocks"]
            for r in b.get("rows", []) for f in r["fields"]}
    ignored = [f for f in config.ALL_NUMERIC_FIELDS if f not in used]
    if ignored:
        st.caption("Form fields currently ignored by the report: " + ", ".join(ignored))

    edited = st.text_area("Edit configuration (JSON)",
                          json.dumps(cfg, indent=2), height=420)
    c1, c2 = st.columns(2)
    if c1.button("Validate & save layout"):
        try:
            parsed = json.loads(edited)
            reportcfg.save_report_config(parsed)
            st.success("Report layout saved.")
            st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        except ValueError as e:
            st.error(f"Invalid layout: {e}")
    if c2.button("Reset to office default"):
        reportcfg.save_report_config(reportcfg.DEFAULT_REPORT_CONFIG)
        st.success("Reset.")
        st.rerun()


def _users_tab():
    users = db.list_users()
    st.dataframe(pd.DataFrame([{
        "Username": u["username"], "Full name": u["full_name"],
        "Role": u["role"], "Active": "✅" if u["active"] else "—",
    } for u in users]), width="stretch", hide_index=True)

    with st.form("new_user"):
        st.markdown("**Add user**")
        c1, c2 = st.columns(2)
        username = c1.text_input("Username")
        full_name = c2.text_input("Full name")
        c3, c4 = st.columns(2)
        password = c3.text_input("Password", type="password")
        role = c4.selectbox("Role", ["viewer", "admin"])
        if st.form_submit_button("Create user"):
            if not username.strip() or len(password) < 8:
                st.error("Username required; password must be at least 8 characters.")
            elif db.get_user(username.strip()):
                st.error("Username already exists.")
            else:
                db.create_user(username, auth.hash_password(password), role, full_name)
                st.success("User created.")
                st.rerun()

    st.markdown("**Edit user**")
    pick = st.selectbox("User", [u["username"] for u in users])
    user = next(u for u in users if u["username"] == pick)
    me = auth.current_user()
    c1, c2, c3 = st.columns(3)
    new_pw = c1.text_input("New password (leave blank to keep)", type="password",
                           key="edit_pw")
    new_role = c2.selectbox("Role", ["viewer", "admin"],
                            index=0 if user["role"] == "viewer" else 1, key="edit_role")
    new_active = c3.checkbox("Active", bool(user["active"]), key="edit_active")
    if st.button("Apply changes"):
        if user["id"] == me["id"] and (new_role != "admin" or not new_active):
            st.error("You cannot demote or deactivate your own account.")
        else:
            fields = {"role": new_role, "active": int(new_active)}
            if new_pw:
                if len(new_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                    return
                fields["pw_hash"] = auth.hash_password(new_pw)
            db.update_user(user["id"], **fields)
            st.success("Updated.")
            st.rerun()


def _backup_tab():
    st.caption(
        "⚠️ On Streamlit Community Cloud the local disk is wiped on every reboot "
        "or redeploy — users, teams, schedules and settings live in this SQLite "
        "file. Download a backup after making changes, and restore it after a "
        "redeploy."
    )
    if os.path.exists(db.DB_PATH):
        with open(db.DB_PATH, "rb") as f:
            st.download_button("⬇️ Download database backup", f.read(),
                               file_name="nrb_dashboard_backup.db")
    up = st.file_uploader("Restore from backup (.db)", type=["db"])
    if up is not None and st.button("Restore now (overwrites current data)"):
        with open(db.DB_PATH, "wb") as f:
            f.write(up.getbuffer())
        st.success("Restored — reloading.")
        st.rerun()
