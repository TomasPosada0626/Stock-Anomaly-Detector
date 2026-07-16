import streamlit as st

from services.auth_service import AuthService


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
        option = st.radio("Choose action:", ["Login", "Register"], horizontal=True)
        if option == "Register":
            st.subheader("Register")
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
                        st.success("Registration successful! Please log in.")
                        st.session_state["logged_in"] = False
                        st.session_state["username"] = username
                        st.session_state["login_mode"] = True
                        st.rerun()
                    else:
                        st.error(register_error or "Registration failed. Please try again.")
        else:
            st.subheader("Login")
            user_or_email = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                ok, message = auth_service.authenticate_user_with_reason(user_or_email, password)
                if ok:
                    username = (
                        auth_service.get_username_by_identifier(user_or_email) or user_or_email
                    )
                    session_id = auth_service.create_session(username)
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["session_id"] = session_id
                    st.success(f"Login successful! Welcome, {username}.")
                    st.rerun()
                else:
                    st.error(message or "Invalid username/email or password.")
