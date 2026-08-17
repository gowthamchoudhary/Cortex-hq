"""CORTEX — sign-in / sign-up UI.

A Streamlit-rendered auth card in the landing page's design language: a
pure-black canvas with the layered electric-blue atmospheric glow, a dark
translucent card, and the three supported sign-in methods backed by
Supabase Auth:

* **Google OAuth** — Supabase hosted flow. We send the browser to the
  provider authorize URL (PKCE; the code verifier is held in the memory
  storage of the *cached* client, so the same instance must both mint the
  URL and exchange the code). Supabase redirects back with
  ``?code=...`` and we exchange it for a session.
* **Email + password** — signed in directly through supabase-py.
* **Magic link** — ``sign_in_with_otp`` emails a link that lands back
  with ``?token_hash=...&type=magiclink``; we verify it with the email
  the user requested the link with (remembered in session state, with an
  inline "confirm your email" fallback when the email is unknown, e.g. a
  different device).

The page is reachable at ``?view=auth`` from the landing page and doubles
as the OAuth / magic-link callback destination. Sessions live in
``st.session_state`` for the lifetime of the browser tab.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Make the repo root importable. Streamlit only prepends the *script's* own
# directory (explorer/) to sys.path, so `auth.*` (a repo-root package) is
# invisible unless we add the project root ourselves. This lets the module
# run both as `streamlit run explorer/auth_ui.py` and when imported from
# `streamlit run explorer/knowledge_explorer.py`.
# ---------------------------------------------------------------------------
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from auth.supabase_client import get_supabase_client, get_supabase_client_cached  # noqa: E402

APP_BASE_URL = os.environ.get("CORTEX_APP_BASE_URL", "http://localhost:8501").rstrip("/")
AUTH_REDIRECT_URL = f"{APP_BASE_URL}/?view=auth"

# session-state keys
TOKEN_KEY = "cortex_auth_token"
USER_KEY = "cortex_auth_user"
MAGIC_EMAIL_KEY = "cortex_magic_email"
PENDING_MAGIC_KEY = "cortex_pending_magic"
ERROR_KEY = "cortex_auth_error"
OK_KEY = "cortex_auth_ok"
GOOGLE_URL_KEY = "cortex_google_url"

# ---------------------------------------------------------------------------
# Pure auth operations (unit-testable with a fake client).
# ---------------------------------------------------------------------------


def supabase_configured() -> bool:
    """True when the env vars needed to talk to Supabase are present."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY"))


def _client() -> Any:
    """Cached Supabase client — keeps the OAuth PKCE verifier in memory."""
    return get_supabase_client_cached()


def build_google_oauth_url(client: Any) -> str:
    """Return the Supabase-hosted Google authorize URL for this app."""
    resp = client.auth.sign_in_with_oauth(
        {"provider": "google", "options": {"redirect_to": AUTH_REDIRECT_URL}}
    )
    url = getattr(resp, "url", None)
    if not url and isinstance(resp, dict):
        url = resp.get("url")
    if not url:
        raise RuntimeError("Supabase did not return a Google OAuth URL")
    return str(url)


def exchange_google_code(client: Any, code: str) -> Any:
    """Exchange the ``?code=`` Supabase returned after Google OAuth."""
    return client.auth.exchange_code_for_session(
        {"auth_code": code, "redirect_to": AUTH_REDIRECT_URL}
    )


def send_magic_link(client: Any, email: str) -> None:
    """Email a magic-link sign-in URL to ``email``."""
    client.auth.sign_in_with_otp(
        {"email": email, "options": {"email_redirect_to": AUTH_REDIRECT_URL}}
    )


def verify_magic_link(client: Any, email: str, token: str, token_type: str) -> Any:
    """Verify a magic-link ``token_hash`` for ``email``."""
    return client.auth.verify_otp({"email": email, "token": token, "type": token_type})


def sign_in_password(client: Any, email: str, password: str) -> Any:
    """Sign in with email + password; returns an AuthResponse."""
    return client.auth.sign_in_with_password({"email": email, "password": password})


def sign_up_password(client: Any, name: str, email: str, password: str) -> Any:
    """Create an email/password account (optional display name)."""
    data: dict[str, Any] = {"email": email, "password": password}
    if name:
        data["options"] = {"data": {"full_name": name}}
    return client.auth.sign_up(data)


# ---------------------------------------------------------------------------
# Session helpers.
# ---------------------------------------------------------------------------


def is_signed_in() -> bool:
    return bool(st.session_state.get(TOKEN_KEY))


def _current_user() -> dict[str, str] | None:
    return st.session_state.get(USER_KEY) if is_signed_in() else None


def _store_session(auth_response: Any) -> None:
    session = getattr(auth_response, "session", None)
    if session is None:
        raise RuntimeError("Sign-in succeeded but Supabase returned no session")
    user = getattr(auth_response, "user", None)
    st.session_state[TOKEN_KEY] = session.access_token
    st.session_state[USER_KEY] = {
        "user_id": str(getattr(user, "id", "") or "") if user is not None else "",
        "email": str(getattr(user, "email", "") or "") if user is not None else "",
    }


def sign_out() -> None:
    """Clear the local session and tell Supabase to invalidate it."""
    try:
        get_supabase_client().auth.sign_out()
    except Exception:
        # Local sign-out must still work if Supabase is unreachable.
        pass
    for key in (TOKEN_KEY, USER_KEY, ERROR_KEY, OK_KEY, PENDING_MAGIC_KEY, GOOGLE_URL_KEY):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Action handlers (called from widget callbacks, then rerun).
# ---------------------------------------------------------------------------


def _do_password_sign_in(email: str, password: str) -> None:
    try:
        _store_session(sign_in_password(_client(), email.strip(), password))
        st.session_state[OK_KEY] = "signed_in"
    except Exception as exc:  # noqa: BLE001 — surface any provider error to the user
        st.session_state[ERROR_KEY] = f"Sign-in failed: {exc}"
    st.rerun()


def _do_sign_up(name: str, email: str, password: str) -> None:
    try:
        resp = sign_up_password(_client(), name.strip(), email.strip(), password)
        if getattr(resp, "session", None) is not None:
            _store_session(resp)
            st.session_state[OK_KEY] = "signed_in"
        else:
            st.session_state[OK_KEY] = "confirm_email"
    except Exception as exc:  # noqa: BLE001
        st.session_state[ERROR_KEY] = f"Sign-up failed: {exc}"
    st.rerun()


def _do_magic_link(email: str) -> None:
    try:
        send_magic_link(_client(), email.strip())
        st.session_state[MAGIC_EMAIL_KEY] = email.strip()
        st.session_state[OK_KEY] = "magic_sent"
    except Exception as exc:  # noqa: BLE001
        st.session_state[ERROR_KEY] = f"Could not send magic link: {exc}"
    st.rerun()


def _do_magic_confirm(email: str, token: str, token_type: str) -> None:
    try:
        _store_session(verify_magic_link(_client(), email.strip(), token, token_type))
        st.session_state.pop(PENDING_MAGIC_KEY, None)
        st.session_state[OK_KEY] = "signed_in"
    except Exception as exc:  # noqa: BLE001
        st.session_state[ERROR_KEY] = f"Magic link verification failed: {exc}"
    st.rerun()


def _google_url() -> str | None:
    """Build (once per session) and cache the Google OAuth URL."""
    cached = st.session_state.get(GOOGLE_URL_KEY)
    if cached:
        return str(cached)
    try:
        url = build_google_oauth_url(_client())
        st.session_state[GOOGLE_URL_KEY] = url
        return url
    except Exception as exc:  # noqa: BLE001
        st.session_state[ERROR_KEY] = f"Google sign-in unavailable: {exc}"
        return None


# ---------------------------------------------------------------------------
# Inbound callbacks (Google ``?code=``, magic link ``?token_hash=``).
# ---------------------------------------------------------------------------


def _clear_callback_params() -> None:
    """Remove OAuth/magic-link callback params but stay on the auth view."""
    params = st.query_params
    for key in ("code", "token_hash", "type", "error", "error_description"):
        params.pop(key, None)
    params["view"] = "auth"


def _handle_inbound_callbacks() -> None:
    params = st.query_params
    code = params.get("code")
    token_hash = params.get("token_hash")
    token_type = params.get("type")

    if code:
        try:
            _store_session(exchange_google_code(_client(), str(code)))
            st.session_state[OK_KEY] = "signed_in"
        except Exception as exc:  # noqa: BLE001
            st.session_state[ERROR_KEY] = f"Google sign-in failed: {exc}"
        _clear_callback_params()
        st.rerun()
        return

    if token_hash and token_type:
        email = st.session_state.get(MAGIC_EMAIL_KEY, "")
        if email:
            try:
                _store_session(verify_magic_link(_client(), email, str(token_hash), str(token_type)))
                st.session_state[OK_KEY] = "signed_in"
            except Exception as exc:  # noqa: BLE001
                st.session_state[ERROR_KEY] = f"Magic link verification failed: {exc}"
            _clear_callback_params()
            st.rerun()
        else:
            # Email unknown (e.g. link opened on another device) — ask inline.
            st.session_state[PENDING_MAGIC_KEY] = (str(token_hash), str(token_type))
            _clear_callback_params()
            st.rerun()


# ---------------------------------------------------------------------------
# Card HTML fragments.
# ---------------------------------------------------------------------------

LOGO_SVG = """
<svg width="52" height="52" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <circle cx="12" cy="4" r="1.9" fill="#7EC9FF"/>
  <circle cx="4.8" cy="10.2" r="1.9" fill="#7EC9FF"/>
  <circle cx="19.2" cy="10.2" r="1.9" fill="#7EC9FF"/>
  <circle cx="8.6" cy="18.4" r="1.9" fill="#A5C9F5"/>
  <circle cx="15.4" cy="18.4" r="1.9" fill="#A5C9F5"/>
  <circle cx="12" cy="11.6" r="1.9" fill="#38BDF8"/>
  <path d="M12 5.9 L5.6 9.0 M12 5.9 L18.4 9.0 M5.6 9.0 L8.6 16.6 M18.4 9.0 L15.4 16.6 M12 13.5 L8.6 16.6 M12 13.5 L15.4 16.6"
        stroke="#3B82F6" stroke-width="1.1" opacity="0.85"/>
</svg>
"""

GOOGLE_G_SVG = """
<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
  <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/>
  <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
  <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
  <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.1 5.7l6.2 5.2C36.9 40.9 44 36 44 24c0-1.3-.1-2.6-.4-3.9z"/>
</svg>
"""

CHECK_SVG = """
<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#7EC9FF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
"""


def _card_header_html(title: str, sub: str) -> str:
    return (
        f'<div class="auth-logo">{LOGO_SVG}</div>\n'
        f'<h2 class="auth-title">{title}</h2>\n'
        f'<p class="auth-sub">{sub}</p>\n'
        f'<p class="auth-tagline">Cortex makes it usable.</p>\n'
    )


def _divider_html(text: str = "Or continue with") -> str:
    return f'<div class="auth-divider"><span>{text}</span></div>'


def _google_button_html(url: str | None) -> str:
    if not url:
        return (
            '<div class="auth-social" style="opacity:.55;cursor:not-allowed;">'
            f"{GOOGLE_G_SVG}<span>Google sign-in unavailable</span></div>"
        )
    return f'<a class="auth-social" href="{url}">{GOOGLE_G_SVG}<span>Continue with Google</span></a>'


def _magic_header_html() -> str:
    return (
        '<p class="auth-magic-head">No password? '
        "<span>Email me a magic link instead</span></p>"
    )


def _config_notice_html() -> str:
    return (
        '<div class="auth-notice"><strong>Sign-in is not configured yet.</strong><br>'
        "Add <code>SUPABASE_URL</code> and <code>SUPABASE_ANON_KEY</code> in "
        "Freebuff → Keys/API keys to enable Google, email + password, and magic-link sign-in.</div>"
    )


def _signed_in_html(email: str) -> str:
    safe_email = str(email or "you")
    return (
        f'<div class="auth-ok-icon">{CHECK_SVG}</div>\n'
        f'<h2 class="auth-title">You&rsquo;re signed in</h2>\n'
        f'<p class="auth-sub">Signed in as <strong style="color:#E7EAF1">{safe_email}</strong>. '
        "Head back to Cortex to explore your organization&rsquo;s context layer.</p>\n"
    )


def _magic_confirm_html() -> str:
    return (
        '<div class="auth-logo">' + LOGO_SVG + "</div>\n"
        '<h2 class="auth-title">Finish signing in</h2>\n'
        '<p class="auth-sub">Enter the email you used to request the magic link '
        "so we can verify it.</p>\n"
    )


def _card_footer_html() -> str:
    return (
        '<p class="auth-footer" id="auth-footer">'
        "Don&rsquo;t have an account? <a href=\"#\" id=\"auth-switch-link\">Sign Up</a></p>"
    )


# ---------------------------------------------------------------------------
# Card rendering.
# ---------------------------------------------------------------------------


def _render_magic_email_confirm() -> None:
    token, token_type = st.session_state[PENDING_MAGIC_KEY]
    st.markdown(_magic_confirm_html(), unsafe_allow_html=True)
    error = st.session_state.pop(ERROR_KEY, None)
    if error:
        st.error(error)
    with st.form("cortex_magic_confirm", clear_on_submit=True):
        email = st.text_input(
            "Email", placeholder="you@company.com", label_visibility="collapsed", key="mc_email"
        )
        st.form_submit_button(
            "Verify magic link",
            type="primary",
            use_container_width=True,
            on_click=_do_magic_confirm,
            args=(email, token, token_type),
        )


def _render_signed_in_card() -> None:
    user = _current_user() or {}
    email = user.get("email") or ""
    st.markdown(_signed_in_html(email), unsafe_allow_html=True)
    st.link_button("Continue to Cortex", APP_BASE_URL, type="primary", use_container_width=True)
    if st.button("Sign out", type="secondary", use_container_width=True):
        sign_out()
        st.rerun()


def _render_signin_tab() -> None:
    with st.form("cortex_signin", clear_on_submit=True):
        email = st.text_input(
            "Email", placeholder="you@company.com", label_visibility="collapsed", key="si_email"
        )
        password = st.text_input(
            "Password", type="password", placeholder="Password", label_visibility="collapsed",
            key="si_password",
        )
        st.form_submit_button(
            "Sign In", type="primary", use_container_width=True,
            on_click=_do_password_sign_in, args=(email, password),
        )

    st.markdown(_divider_html(), unsafe_allow_html=True)
    st.markdown(_google_button_html(_google_url()), unsafe_allow_html=True)

    st.markdown(_magic_header_html(), unsafe_allow_html=True)
    with st.form("cortex_magic", clear_on_submit=True):
        ml_email = st.text_input(
            "Email", placeholder="you@company.com", label_visibility="collapsed", key="ml_email"
        )
        st.form_submit_button(
            "Email me a magic link", type="secondary", use_container_width=True,
            on_click=_do_magic_link, args=(ml_email,),
        )


def _render_signup_tab() -> None:
    with st.form("cortex_signup", clear_on_submit=True):
        name = st.text_input(
            "Full name", placeholder="Ada Lovelace", label_visibility="collapsed", key="su_name"
        )
        email = st.text_input(
            "Email", placeholder="you@company.com", label_visibility="collapsed", key="su_email"
        )
        password = st.text_input(
            "Password", type="password", placeholder="Create a password",
            label_visibility="collapsed", key="su_password",
        )
        st.form_submit_button(
            "Create account", type="primary", use_container_width=True,
            on_click=_do_sign_up, args=(name, email, password),
        )

    st.markdown(_divider_html(), unsafe_allow_html=True)
    st.markdown(_google_button_html(_google_url()), unsafe_allow_html=True)


def _render_forms_card() -> None:
    st.markdown(
        _card_header_html("Sign in to Cortex", "Access your organization\u2019s living context layer."),
        unsafe_allow_html=True,
    )

    error = st.session_state.pop(ERROR_KEY, None)
    ok = st.session_state.pop(OK_KEY, None)
    if error:
        st.error(error)
    elif ok == "magic_sent":
        st.success("Magic link sent — check your inbox, then tap the link to sign in.")
    elif ok == "confirm_email":
        st.success("Account created — check your email to confirm, then sign in.")

    if not supabase_configured():
        st.markdown(_config_notice_html(), unsafe_allow_html=True)
        return

    tab_signin, tab_signup = st.tabs(["Sign In", "Sign Up"])
    with tab_signin:
        _render_signin_tab()
    with tab_signup:
        _render_signup_tab()

    st.markdown(_card_footer_html(), unsafe_allow_html=True)


def _render_card() -> None:
    if PENDING_MAGIC_KEY in st.session_state:
        _render_magic_email_confirm()
        return
    if is_signed_in():
        _render_signed_in_card()
        return
    _render_forms_card()


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def render_auth_page() -> None:
    """Render the full auth view (backdrop + card + behavior scripts)."""
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    st.markdown(BACKDROP_HTML, unsafe_allow_html=True)
    _handle_inbound_callbacks()
    _left, _center, _right = st.columns([1, 2, 1])
    with _center:
        _render_card()
    st.markdown(AUTH_JS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Styling.
# ---------------------------------------------------------------------------

AUTH_CSS = """
<style>
  html, body, .stApp { overflow: auto !important; }
  [data-testid="stAppViewContainer"] > .main { padding: 0 !important; background: #050505 !important; }
  .block-container { max-width: 100% !important; padding: 0 !important; }

  /* ---------- atmospheric backdrop (same layered light as the landing page) ---------- */
  #auth-bg { position: fixed; inset: 0; z-index: 0; background: #050505; overflow: hidden; pointer-events: none; }
  #auth-bg .glow, #auth-bg .beam { position: absolute; }
  #auth-bg .glow-hero {
    width: 900px; height: 420px; top: -140px; left: 50%; transform: translateX(-50%);
    background: radial-gradient(closest-side, rgba(77, 60, 255, 0.07), transparent 72%);
    filter: blur(60px);
  }
  #auth-bg .glow-navy {
    width: 1500px; height: 700px; bottom: -260px; left: 50%; transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 62%, rgba(11, 31, 102, 0.42), rgba(7, 16, 43, 0.30) 52%, transparent 80%);
    filter: blur(72px);
  }
  #auth-bg .glow-lower {
    width: 1200px; height: 560px; bottom: -200px; left: 50%; transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 70%, rgba(22, 77, 255, 0.34), rgba(20, 107, 255, 0.18) 46%, transparent 76%);
    filter: blur(64px);
  }
  #auth-bg .glow-cyan {
    width: 820px; height: 380px; bottom: -150px; left: 50%; transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 76%, rgba(40, 215, 255, 0.40), rgba(20, 107, 255, 0.26) 38%, transparent 74%);
    filter: blur(54px);
  }
  #auth-bg .beam {
    width: 620px; height: 900px; bottom: -200px; left: 50%; transform: translateX(-50%);
    background: linear-gradient(to top, rgba(40, 215, 255, 0.18), rgba(22, 77, 255, 0.13) 24%, rgba(22, 77, 255, 0.07) 48%, transparent 74%);
    filter: blur(48px);
  }

  /* ---------- centered card ---------- */
  [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
    position: relative; z-index: 1;
    max-width: 560px; margin: 9vh auto 6vh;
    padding: 44px 44px 30px;
    background: linear-gradient(180deg, rgba(16, 19, 27, 0.92), rgba(8, 10, 15, 0.95));
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 28px;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.05),
      0 30px 90px rgba(0, 0, 0, 0.6),
      0 0 70px rgba(22, 77, 255, 0.10);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
  }

  /* ---------- card typography ---------- */
  .auth-logo { display: flex; justify-content: center; margin-bottom: 22px; }
  .auth-title {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 30px; font-weight: 600; letter-spacing: -0.02em;
    text-align: center; color: #ffffff; margin: 0 0 8px;
  }
  .auth-sub {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14.5px; line-height: 1.55; color: #9AA1AC;
    text-align: center; margin: 0 0 26px;
  }
  .auth-tagline {
    font-family: 'Instrument Serif', Georgia, serif; font-style: italic;
    font-size: 17.5px; text-align: center; margin: -12px 0 26px;
    background-image: linear-gradient(92deg, #e9c9ff 0%, #8f7bff 60%, #86b8ff 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }

  /* ---------- inputs ---------- */
  [data-testid="stTextInput"] { margin-bottom: 12px; }
  [data-testid="stTextInput"] input {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
    border-radius: 14px !important;
    color: #ffffff !important;
    font-size: 15px !important;
    padding: 14px 16px !important;
    box-shadow: none !important;
    caret-color: #7EC9FF;
  }
  [data-testid="stTextInput"] input::placeholder { color: #6B7280; }
  [data-testid="stTextInput"] input:focus {
    border-color: rgba(96, 165, 250, 0.55) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.14) !important;
  }

  /* ---------- buttons ---------- */
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"] {
    width: 100%; height: 54px; border-radius: 999px !important;
    background: #ffffff !important; color: #0a0b0d !important;
    border: none !important; font-weight: 600; font-size: 15.5px;
    box-shadow: 0 0 30px rgba(22, 77, 255, 0.30);
    transition: box-shadow 0.2s ease, background 0.2s ease;
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"]:hover {
    background: #eef3fb !important;
    box-shadow: 0 0 44px rgba(22, 77, 255, 0.45);
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondary"] {
    width: 100%; height: 50px; border-radius: 999px !important;
    background: rgba(255, 255, 255, 0.04) !important; color: #C9D2DF !important;
    border: 1px solid rgba(148, 163, 184, 0.22) !important;
    font-weight: 500; font-size: 14.5px;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(255, 255, 255, 0.08) !important;
    border-color: rgba(148, 163, 184, 0.38) !important;
  }
  [data-testid="stLinkButton"] {
    display: flex; justify-content: center; align-items: center;
    width: 100%; height: 54px; border-radius: 999px !important;
    background: #ffffff !important; color: #0a0b0d !important;
    font-weight: 600; font-size: 15.5px; text-decoration: none;
    box-shadow: 0 0 30px rgba(22, 77, 255, 0.30);
    margin-bottom: 12px;
  }
  [data-testid="stLinkButton"]:hover { background: #eef3fb !important; }
  button[data-testid="stBaseButton-secondary"] {
    width: 100%; height: 46px; border-radius: 999px !important;
    background: transparent !important; color: #9AA1AC !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
    font-weight: 500; font-size: 14px;
  }
  button[data-testid="stBaseButton-secondary"]:hover {
    color: #E7EAF1 !important; border-color: rgba(148, 163, 184, 0.4) !important;
  }

  /* ---------- tabs (segmented control) ---------- */
  [data-testid="stTabs"] { display: flex; justify-content: center; margin-bottom: 6px; }
  [data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 6px; padding: 4px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 999px;
  }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 999px; padding: 8px 26px;
    color: #9AA1AC; font-size: 14px; font-weight: 500;
    background: transparent;
  }
  [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: #ffffff; color: #0a0b0d;
  }
  [data-testid="stTabs"] [data-baseweb="tab-panel"] { padding: 20px 0 0; }

  /* ---------- divider / social / misc ---------- */
  .auth-divider {
    display: flex; align-items: center; gap: 14px;
    margin: 22px 0; color: #6E7684;
    font-size: 12.5px; letter-spacing: 0.04em;
  }
  .auth-divider::before, .auth-divider::after {
    content: ''; flex: 1; border-top: 1px dashed rgba(148, 163, 184, 0.22);
  }
  .auth-social {
    display: flex; align-items: center; justify-content: center; gap: 12px;
    width: 100%; height: 52px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #E7EAF1; font-size: 15px; font-weight: 500; text-decoration: none;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .auth-social:hover { background: rgba(255, 255, 255, 0.09); border-color: rgba(148, 163, 184, 0.4); }
  .auth-magic-head { text-align: center; font-size: 13px; color: #6E7684; margin: 24px 0 14px; }
  .auth-magic-head span { color: #C9D2DF; }
  .auth-footer {
    text-align: center; margin-top: 26px; padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.12);
    font-size: 14px; color: #9AA1AC;
  }
  .auth-footer a { color: #ffffff; font-weight: 600; text-decoration: none; }
  .auth-footer a:hover { text-decoration: underline; }
  .auth-notice {
    margin: 4px 0 8px; padding: 14px 16px; border-radius: 14px;
    background: rgba(22, 77, 255, 0.08);
    border: 1px solid rgba(96, 165, 250, 0.25);
    color: #C7D4E8; font-size: 13.5px; line-height: 1.55; text-align: center;
  }
  .auth-notice code { color: #93c5fd; }
  .auth-ok-icon {
    width: 64px; height: 64px; margin: 0 auto 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: radial-gradient(circle at 32% 28%, rgba(59, 130, 246, 0.3), rgba(23, 37, 84, 0.18));
    border: 1px solid rgba(96, 165, 250, 0.35);
    box-shadow: 0 0 30px rgba(59, 130, 246, 0.35);
  }

  @media (max-width: 760px) {
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
      margin: 4vh auto; padding: 32px 22px 24px; max-width: 100%;
    }
  }
</style>
"""

BACKDROP_HTML = """
<div id="auth-bg">
  <div class="beam"></div>
  <div class="glow glow-hero"></div>
  <div class="glow glow-navy"></div>
  <div class="glow glow-lower"></div>
  <div class="glow glow-cyan"></div>
</div>
"""

# ---------------------------------------------------------------------------
# Behavior scripts: hash→query shim (magic-link tokens can arrive in the URL
# fragment), show/hide password toggle, and the footer Sign-Up link.
# ---------------------------------------------------------------------------

AUTH_JS = """
<script>
(function () {
  // 1) Some Supabase setups deliver the magic-link token in the URL hash
  //    (#token_hash=...) instead of the query string — promote it to a
  //    query param and reload so the server can see it.
  if (location.hash && location.hash.indexOf('token_hash=') !== -1) {
    var extra = new URLSearchParams(location.hash.slice(1));
    var q = new URLSearchParams(location.search);
    extra.forEach(function (v, k) { q.set(k, v); });
    location.search = q.toString();
    return;
  }

  function mount() {
    // 2) Show/hide password eye toggle.
    document.querySelectorAll('[data-testid="stTextInput"] input[type="password"]').forEach(function (pw) {
      if (pw.dataset.eyeMounted) return;
      pw.dataset.eyeMounted = '1';
      var wrap = pw.closest('[data-testid="stTextInput"]');
      if (!wrap) return;
      wrap.style.position = 'relative';
      pw.style.paddingRight = '44px';
      var eye = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>';
      var eyeOff = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Toggle password visibility');
      btn.innerHTML = eye;
      btn.style.cssText = 'position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#8A93A3;padding:4px;display:flex;';
      btn.addEventListener('click', function () {
        var show = pw.type === 'password';
        pw.type = show ? 'text' : 'password';
        btn.innerHTML = show ? eyeOff : eye;
      });
      wrap.appendChild(btn);
    });

    // 3) Footer "Sign Up" ⇄ "Sign In" link switches the active tab.
    var link = document.getElementById('auth-switch-link');
    var tabs = document.querySelectorAll('[data-testid="stTabs"] [data-baseweb="tab"]');
    var footer = document.getElementById('auth-footer');
    if (link && tabs.length) {
      var findTab = function (label) {
        return Array.prototype.slice.call(tabs).find(function (t) {
          return t.textContent.trim().toLowerCase().indexOf(label) !== -1;
        });
      };
      var signInTab = findTab('sign in');
      var signUpTab = findTab('sign up');
      var activeIsSignUp = signUpTab && signUpTab.getAttribute('aria-selected') === 'true';
      var target = activeIsSignUp ? signInTab : signUpTab;
      var label = activeIsSignUp ? 'Sign In' : 'Sign Up';
      if (footer) footer.innerHTML = (activeIsSignUp
        ? 'Already have an account? <a href="#" id="auth-switch-link">Sign In</a>'
        : 'Don\u2019t have an account? <a href="#" id="auth-switch-link">Sign Up</a>');
      link = document.getElementById('auth-switch-link');
      if (link && target) {
        link.href = '#';
        link.onclick = function (e) { e.preventDefault(); target.click(); return false; };
      }
    }
  }

  var tries = 0;
  var timer = setInterval(function () {
    mount();
    if (++tries > 12) clearInterval(timer);
  }, 250);
})();
</script>
"""
