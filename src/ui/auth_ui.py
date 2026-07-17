import streamlit as st

from services.auth_service import AuthService


def _get_remembered_identifier() -> str:
    try:
        return str(st.query_params.get("login_id", "")).strip()
    except Exception:
        return ""


def _set_remembered_identifier(identifier: str) -> None:
    try:
        if identifier:
            st.query_params["login_id"] = identifier
        else:
            params = dict(st.query_params)
            params.pop("login_id", None)
            st.query_params.clear()
            for key, value in params.items():
                st.query_params[key] = value
    except Exception:
        # Query param persistence is a convenience feature; auth must not depend on it.
        return


def render_login_panel(auth_service: AuthService) -> None:
    st.markdown(
        "<style>div[data-testid='column']:nth-of-type(2) {margin: auto;}</style>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<div style='text-align:center;'><h1>Login / Register</h1></div>",
            unsafe_allow_html=True,
        )
        if st.session_state.pop("force_login_view", False):
            st.session_state["auth_action"] = "Login"

        if "auth_action" not in st.session_state:
            st.session_state["auth_action"] = "Login"

        option = st.radio(
            "Choose action:", ["Login", "Register"], horizontal=True, key="auth_action"
        )
        if option == "Register":
            st.subheader("Register")
            st.caption("Tip: Email is case-insensitive. Username is case-sensitive.")
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            username = st.text_input("Username")
            username_status = st.empty()
            if username:
                if not auth_service.is_username_available(username):
                    username_status.error("Username is not available.")
                else:
                    username_status.success("Username is available.")
            email = st.text_input("Email")
            email_status = st.empty()
            if email.strip():
                if not auth_service.is_email_available(email):
                    email_status.error("Email is already registered.")
                else:
                    email_status.success("Email is available.")
            password = st.text_input("Password", type="password")
            password2 = st.text_input("Repeat Password", type="password")
            st.caption(
                "Password must include uppercase, lowercase, number, special character, and 8+ length."
            )
            if st.button("Register"):
                required_fields = [first_name, last_name, username, email, password, password2]
                if not all(field.strip() for field in required_fields):
                    st.error("All fields are required.")
                elif password != password2:
                    st.error("Passwords do not match.")
                elif not auth_service.is_strong_password(password):
                    st.error(
                        "Password must be at least 8 characters, include uppercase, lowercase, number, and special character."
                    )
                elif not auth_service.is_username_available(username):
                    st.error("Username is not available.")
                elif not auth_service.is_email_available(email):
                    st.error("Email is already registered. Try logging in.")
                else:
                    registered, register_error = auth_service.register_user(
                        username, email, first_name, last_name, password
                    )
                    if registered:
                        st.session_state["post_register_notice"] = (
                            "Registration successful! Please log in."
                        )
                        st.session_state["post_register_identifier"] = email.strip().lower()
                        st.session_state["force_login_view"] = True
                        st.session_state["logged_in"] = False
                        st.session_state["username"] = ""
                        st.rerun()
                    else:
                        st.error(register_error or "Registration failed. Please try again.")
        else:
            post_register_notice = st.session_state.pop("post_register_notice", "")
            if post_register_notice:
                st.success(post_register_notice)

            st.subheader("Login")
            st.caption("You can log in with username or email.")
            remembered_identifier = _get_remembered_identifier()
            post_register_identifier = st.session_state.pop("post_register_identifier", "")
            default_identifier = post_register_identifier or remembered_identifier
            user_or_email = st.text_input("Username or Email", value=default_identifier)
            password = st.text_input("Password", type="password")
            remember_identifier = st.checkbox(
                "Remember username/email on this device",
                value=bool(remembered_identifier),
                help="Stores only the username/email in the URL for faster login. Password is never stored.",
            )
            if st.button("Login"):
                ok, message = auth_service.authenticate_user_with_reason(
                    user_or_email.strip(), password
                )
                if ok:
                    if remember_identifier:
                        _set_remembered_identifier(user_or_email.strip())
                    else:
                        _set_remembered_identifier("")
                    username = (
                        auth_service.get_username_by_identifier(user_or_email) or user_or_email
                    )
                    session_id = auth_service.create_session(username)
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["session_id"] = session_id
                    st.session_state["role"] = auth_service.get_user_role(username)
                    st.success(f"Login successful! Welcome, {username}.")
                    st.rerun()
                else:
                    st.error(message or "Invalid username/email or password.")
                    if not auth_service.get_username_by_identifier(user_or_email):
                        st.info(
                            "No user found with that username/email in the active database. "
                            "If you already registered, make sure you're in the same environment."
                        )
