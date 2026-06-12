"""
Central authentication module for Bioreactor Manager.
Self-contained — depends only on Python stdlib + PyYAML (Streamlit ships with it).

Public API (unchanged from previous implementation):
    init_auth()                 -> sets up auth state once per session
    render_sidebar_auth()       -> draws login form / user info / logout in sidebar
    require_role(role)          -> Streamlit-level guard; calls st.stop() if user lacks role
    current_user()              -> returns username string or None
    current_role()              -> 'viewer' | 'editor' | 'admin'
    is_authenticated()          -> bool

Design notes:
- Passwords hashed with PBKDF2-SHA256, 200,000 iterations (NIST SP 800-132).
- 1-hour idle timeout via session_state timestamp (refreshes on every render).
- 5 failed attempts in a session locks login for 5 minutes (rate limiting).
- No browser cookie: refresh = re-login. Tradeoff documented for stakeholder.
- Role hierarchy: admin > editor > viewer. Anonymous users are 'viewer'.
"""
import datetime
import hashlib
import hmac
import os
import streamlit as st
import yaml

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.yaml")
IDLE_TIMEOUT_SECONDS = 3600          # 1 hour
LOCKOUT_THRESHOLD = 5                # failed attempts before lockout
LOCKOUT_SECONDS = 300                # 5 minutes
PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "sha256"
ROLE_HIERARCHY = {'viewer': 0, 'editor': 1, 'admin': 2}


# --- PASSWORD HASHING ---------------------------------------------------------

def hash_password(plaintext, salt=None):
    """
    Hash a password with PBKDF2-SHA256.
    Returns a string formatted as: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, plaintext.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plaintext, stored):
    """Constant-time comparison against the stored hash."""
    try:
        algo, iters_str, salt_hex, hash_hex = stored.split('$')
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac(PBKDF2_ALGO, plaintext.encode('utf-8'), salt, iters)
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


# --- CONFIG LOADING -----------------------------------------------------------

def _load_config():
    with open(USERS_FILE, encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_user(username):
    config = _load_config()
    return config.get('credentials', {}).get('usernames', {}).get(username)

# --- SESSION STATE INIT -------------------------------------------------------

def init_auth():
    """Idempotent — safe to call on every render."""
    if 'auth_config' not in st.session_state:
        st.session_state.auth_config = _load_config()
    if 'auth_user' not in st.session_state:
        st.session_state.auth_user = None
    if 'auth_role' not in st.session_state:
        st.session_state.auth_role = 'viewer'
    if 'auth_failed_attempts' not in st.session_state:
        st.session_state.auth_failed_attempts = 0
    if 'auth_locked_until' not in st.session_state:
        st.session_state.auth_locked_until = None


def is_authenticated():
    return st.session_state.get('auth_user') is not None


def current_user():
    return st.session_state.get('auth_user')


def current_role():
    return st.session_state.get('auth_role', 'viewer')


def _has_role(required):
    return ROLE_HIERARCHY[current_role()] >= ROLE_HIERARCHY[required]


# --- LOGIN / LOGOUT -----------------------------------------------------------

def _resolve_role(user_record):
    roles = user_record.get('roles', [])
    if 'admin' in roles:
        return 'admin'
    if 'editor' in roles:
        return 'editor'
    return 'viewer'


def _attempt_login(username, password):
    """Returns (success, message)."""
    config = st.session_state.auth_config
    users = config.get('credentials', {}).get('usernames', {})
    record = users.get(username)
    if record is None:
        return False, "Invalid username or password"
    stored = record.get('password', '')
    if not verify_password(password, stored):
        return False, "Invalid username or password"
    st.session_state.auth_user = username
    st.session_state.auth_role = _resolve_role(record)
    st.session_state.auth_failed_attempts = 0
    st.session_state.auth_locked_until = None
    st.session_state.last_activity = datetime.datetime.now()
    return True, f"Welcome, {username}"


def _logout():
    for key in ('auth_user', 'auth_role', 'last_activity'):
        st.session_state.pop(key, None)
    st.session_state.auth_user = None
    st.session_state.auth_role = 'viewer'


def _is_locked_out():
    """Returns (locked, seconds_remaining)."""
    locked_until = st.session_state.get('auth_locked_until')
    if locked_until is None:
        return False, 0
    now = datetime.datetime.now()
    if now >= locked_until:
        st.session_state.auth_locked_until = None
        st.session_state.auth_failed_attempts = 0
        return False, 0
    return True, int((locked_until - now).total_seconds())


# --- IDLE TIMEOUT -------------------------------------------------------------

def enforce_idle_timeout():
    if not is_authenticated():
        return
    now = datetime.datetime.now()
    last = st.session_state.get('last_activity')
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed > IDLE_TIMEOUT_SECONDS:
            _logout()
            st.warning("⏱️ Session expired after 1 hour of inactivity. Please log in again.")
            st.rerun()
    st.session_state.last_activity = now


# --- SIDEBAR WIDGET -----------------------------------------------------------

def render_sidebar_auth():
    """Call at top of every page."""
    init_auth()
    enforce_idle_timeout()

    with st.sidebar:
        st.markdown("### 🔐 Account")
        if is_authenticated():
            st.success(f"**{current_user()}** ({current_role()})")
            if st.button("Logout", key="logout_btn", use_container_width=True):
                _logout()
                st.rerun()
        else:
            locked, secs = _is_locked_out()
            if locked:
                mins = secs // 60
                st.error(f"🔒 Too many failed attempts. Try again in {mins}m {secs % 60}s.")
                return

            with st.form("login_form_sidebar", clear_on_submit=False):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                ok, msg = _attempt_login(username.strip(), password)
                if ok:
                    st.rerun()
                else:
                    st.session_state.auth_failed_attempts += 1
                    remaining = LOCKOUT_THRESHOLD - st.session_state.auth_failed_attempts
                    if remaining <= 0:
                        st.session_state.auth_locked_until = (
                            datetime.datetime.now() + datetime.timedelta(seconds=LOCKOUT_SECONDS)
                        )
                        st.error(f"🔒 {LOCKOUT_THRESHOLD} failed attempts — locked for 5 minutes.")
                    else:
                        st.error(f"{msg} ({remaining} attempt(s) remaining)")

            st.caption("Login required for Reservation, Simulation, Admin pages.")


# --- PAGE GUARD ---------------------------------------------------------------

def require_role(required_role):
    """Block page if user lacks required_role. Call after render_sidebar_auth()."""
    if not _has_role(required_role):
        st.error(f"🔒 This page requires **{required_role}** role or higher.")
        if not is_authenticated():
            st.info("Please log in using the form in the sidebar.")
        else:
            st.info(f"Logged in as **{current_user()}** with role **{current_role()}**. "
                    f"Contact an admin if you need additional access.")
        st.stop()
