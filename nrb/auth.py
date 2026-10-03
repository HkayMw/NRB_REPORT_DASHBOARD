"""Streamlit session authentication and login/setup rendering."""

import streamlit as st

from nrb.application.errors import ApplicationError, log_unexpected
from nrb.application.services.authentication import AuthenticationService


def current_user():
    return st.session_state.get("auth_user")


def is_admin():
    u = current_user()
    return bool(u and u["role"] == "admin")


def is_logged_in():
    return current_user() is not None


def login(username: str, password: str, service: AuthenticationService) -> bool:
    user = service.authenticate(username, password)
    if not user:
        return False
    st.session_state["auth_user"] = user
    return True


def logout():
    st.session_state.pop("auth_user", None)


def render_sidebar_auth(service: AuthenticationService):
    """Login/logout box in the sidebar."""
    u = current_user()
    with st.sidebar:
        if u:
            st.caption(f"Signed in as **{u['username']}** ({u['role']})")
            if st.button("Log out", width="stretch"):
                logout()
                st.rerun()
        else:
            with st.expander("🔐 Staff login"):
                with st.form("login_form", border=False):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    if st.form_submit_button("Log in", width="stretch"):
                        try:
                            if login(username, password, service):
                                st.rerun()
                            else:
                                st.error("Invalid username or password.")
                        except ApplicationError as error:
                            st.error(str(error))
                        except Exception as error:
                            log_unexpected("Render login failure", error)
                            st.error(
                                "Login is temporarily unavailable. Please try again."
                            )


def render_first_run_setup(service: AuthenticationService):
    """Force creation of the first admin account when no users exist."""
    from nrb import ui

    ui.header("🪪", "First-time setup")
    st.info("No user accounts exist yet. Create the administrator account to continue.")
    with st.form("setup_form"):
        username = st.text_input("Admin username")
        full_name = st.text_input("Full name")
        pw1 = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create admin account"):
            try:
                service.create_first_admin(username, full_name, pw1, pw2)
                st.success("Admin account created — please log in from the sidebar.")
                st.rerun()
            except (ValueError, PermissionError) as e:
                st.error(str(e))
            except ApplicationError as error:
                st.error(str(error))
            except Exception as error:
                log_unexpected("Render first administrator setup failure", error)
                st.error(
                    "Could not create the administrator account. Please try again."
                )
