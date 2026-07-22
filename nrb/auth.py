"""Password hashing (PBKDF2, stdlib only) and Streamlit session auth."""

import hashlib
import hmac
import secrets

import streamlit as st

from nrb import db

_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"pbkdf2${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iters)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def current_user():
    return st.session_state.get("auth_user")


def is_admin():
    u = current_user()
    return bool(u and u["role"] == "admin")


def is_logged_in():
    return current_user() is not None


def login(username: str, password: str) -> bool:
    user = db.get_user(username.strip())
    if user and verify_password(password, user["pw_hash"]):
        st.session_state["auth_user"] = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
        }
        return True
    return False


def logout():
    st.session_state.pop("auth_user", None)


def render_sidebar_auth():
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
                        if login(username, password):
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")


def render_first_run_setup():
    """Force creation of the first admin account when no users exist."""
    st.title("First-time setup")
    st.info(
        "No user accounts exist yet. Create the administrator account to continue."
    )
    with st.form("setup_form"):
        username = st.text_input("Admin username")
        full_name = st.text_input("Full name")
        pw1 = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create admin account"):
            if not username.strip() or not pw1:
                st.error("Username and password are required.")
            elif len(pw1) < 8:
                st.error("Use a password of at least 8 characters.")
            elif pw1 != pw2:
                st.error("Passwords do not match.")
            else:
                db.create_user(username, hash_password(pw1), role="admin",
                               full_name=full_name)
                st.success("Admin account created — please log in from the sidebar.")
                st.rerun()
