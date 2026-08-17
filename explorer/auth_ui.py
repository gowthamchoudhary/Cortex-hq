"""CORTEX — sign-in / sign-up UI.

A Streamlit-rendered auth card in a clean light design: a soft neutral page
background with a centered white card (rounded corners, subtle shadow), gray
pill-less inputs with inset icons, a solid-black primary action, and the three
supported sign-in methods backed by Supabase Auth:

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

The Sign In / Sign Up screens share one card: a heading + subtext at the
top, the form in the middle, and a plain text link at the bottom of the
card that switches between the two (client-side, no rerun).
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
    if not supabase_configured():
        return None  # unconfigured: render the disabled Google row, no error banner
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
<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
"""


def _card_header_html(title: str, sub: str) -> str:
    return (
        f'<div class="auth-logo">{LOGO_SVG}</div>\n'
        f'<h2 class="auth-title" id="auth-title">{title}</h2>\n'
        f'<p class="auth-sub" id="auth-sub">{sub}</p>\n'
        f'<p class="auth-tagline">Cortex makes it usable.</p>\n'
    )


def _divider_html(text: str = "or continue with") -> str:
    return f'<div class="auth-divider"><span>{text}</span></div>'


def _google_button_html(url: str | None) -> str:
    """Google row — same shape whether or not it is configured.

    Unconfigured (url is None) just drops opacity on the identical row so the
    layout never changes shape; the button is genuinely disabled in that case.
    """
    if url:
        return (
            f'<a class="auth-social" href="{url}">'
            f"{GOOGLE_G_SVG}<span>Continue with Google</span></a>"
        )
    return (
        '<div class="auth-social auth-social--disabled" '
        'title="Google sign-in becomes available once SUPABASE_URL and '
        'SUPABASE_ANON_KEY are configured.">'
        f"{GOOGLE_G_SVG}<span>Continue with Google</span></div>"
    )


def _magic_line_html() -> str:
    """Plain-text magic-link toggle: muted lead + bold actionable link."""
    return (
        '<p class="auth-magic-line"><span>No password? </span>'
        '<a href="#" id="auth-magic-toggle">Email me a magic link</a></p>'
    )


def _signed_in_html(email: str) -> str:
    safe_email = str(email or "you")
    return (
        f'<div class="auth-ok-icon">{CHECK_SVG}</div>\n'
        f'<h2 class="auth-title">You&rsquo;re signed in</h2>\n'
        f'<p class="auth-sub">Signed in as <strong style="color:#18181B">{safe_email}</strong>. '
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


def _render_signin_form() -> None:
    """The Sign In screen: email+password, divider, Google, magic link."""
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

    st.markdown(_magic_line_html(), unsafe_allow_html=True)
    st.markdown('<div id="auth-magic-form" style="display:none">', unsafe_allow_html=True)
    with st.form("cortex_magic", clear_on_submit=True):
        ml_email = st.text_input(
            "Email", placeholder="you@company.com", label_visibility="collapsed", key="ml_email"
        )
        st.form_submit_button(
            "Send magic link", type="secondary", use_container_width=True,
            on_click=_do_magic_link, args=(ml_email,),
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_signup_form() -> None:
    """The Sign Up screen: name/email/password, divider, Google."""
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
            "Create account",
            type="primary",
            use_container_width=True,
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

    # Both screens render; the JS below toggles which one is visible and swaps
    # the heading/subtext/footer via the bottom "Sign Up" / "Sign In" link.
    st.markdown('<div id="auth-signin-form">', unsafe_allow_html=True)
    _render_signin_form()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div id="auth-signup-form" style="display:none">', unsafe_allow_html=True)
    _render_signup_form()
    st.markdown("</div>", unsafe_allow_html=True)

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
    """Render the full auth view (light backdrop + card + behavior scripts)."""
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    _handle_inbound_callbacks()
    _left, _center, _right = st.columns([1, 2, 1])
    with _center:
        _render_card()
    st.markdown(AUTH_JS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Styling (light theme — matches the reference card).
# ---------------------------------------------------------------------------

AUTH_CSS = """
<style>
  html, body, .stApp { overflow: auto !important; }
  [data-testid="stAppViewContainer"] > .main { padding: 0 !important; background: #F4F4F5 !important; }
  .block-container { max-width: 100% !important; padding: 0 !important; }

  /* ---------- centered white card ---------- */
  [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
    position: relative; z-index: 1;
    max-width: 440px; margin: 8vh auto 6vh;
    padding: 42px 36px 26px;
    background: #FFFFFF;
    border: 1px solid rgba(17, 24, 39, 0.06);
    border-radius: 18px;
    box-shadow:
      0 24px 60px rgba(15, 23, 42, 0.10),
      0 2px 10px rgba(15, 23, 42, 0.04);
  }

  /* ---------- logo with dotted-circle accent ---------- */
  .auth-logo {
    position: relative; width: 72px; height: 72px; margin: 0 auto 22px;
    display: flex; align-items: center; justify-content: center;
  }
  .auth-logo::before {
    content: ''; position: absolute; inset: 0;
    border: 1.5px dashed rgba(59, 130, 246, 0.35);
    border-radius: 50%;
  }
  .auth-logo::after {
    content: ''; position: absolute; inset: 9px;
    border: 1.5px dashed rgba(59, 130, 246, 0.16);
    border-radius: 50%;
  }
  .auth-logo svg { position: relative; z-index: 1; }

  /* ---------- card typography ---------- */
  .auth-title {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 27px; font-weight: 650; letter-spacing: -0.02em;
    text-align: center; color: #18181B; margin: 0 0 8px;
  }
  .auth-sub {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14.5px; line-height: 1.55; color: #71717A;
    text-align: center; margin: 0 0 8px;
  }
  .auth-tagline {
    font-family: 'Instrument Serif', Georgia, serif; font-style: italic;
    font-size: 16px; text-align: center; margin: 0 0 26px; color: #64748B;
  }

  /* ---------- inputs (gray fill, no border, inset icon space) ---------- */
  [data-testid="stTextInput"] { margin-bottom: 12px; }
  [data-testid="stTextInput"] input {
    background: #F4F4F5 !important;
    border: 1px solid transparent !important;
    border-radius: 12px !important;
    color: #18181B !important;
    font-size: 15px !important;
    padding: 13px 16px 13px 44px !important;
    box-shadow: none !important;
    caret-color: #2563EB;
    transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  }
  [data-testid="stTextInput"] input::placeholder { color: #A1A1AA; }
  [data-testid="stTextInput"] input:focus {
    background: #FFFFFF !important;
    border-color: rgba(37, 99, 235, 0.4) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
  }

  /* ---------- buttons (black primary, rounded to match inputs) ---------- */
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"] {
    width: 100%; height: 50px; border-radius: 12px !important;
    background: #111111 !important; color: #FFFFFF !important;
    border: none !important; font-weight: 600; font-size: 15px;
    box-shadow: none;
    transition: background 0.15s ease;
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"]:hover {
    background: #000000 !important;
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondary"] {
    width: 100%; height: 48px; border-radius: 12px !important;
    background: #FFFFFF !important; color: #18181B !important;
    border: 1px solid #E4E4E7 !important;
    font-weight: 500; font-size: 14.5px;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-secondary"]:hover {
    background: #FAFAFA !important;
    border-color: #D4D4D8 !important;
  }
  [data-testid="stLinkButton"] {
    display: flex; justify-content: center; align-items: center;
    width: 100%; height: 50px; border-radius: 12px !important;
    background: #111111 !important; color: #FFFFFF !important;
    font-weight: 600; font-size: 15px; text-decoration: none;
    margin-bottom: 12px;
  }
  [data-testid="stLinkButton"]:hover { background: #000000 !important; }
  button[data-testid="stBaseButton-secondary"] {
    width: 100%; height: 46px; border-radius: 12px !important;
    background: #FFFFFF !important; color: #18181B !important;
    border: 1px solid #E4E4E7 !important;
    font-weight: 500; font-size: 14px;
  }
  button[data-testid="stBaseButton-secondary"]:hover {
    background: #FAFAFA !important; border-color: #D4D4D8 !important;
  }

  /* ---------- divider / social / magic / footer ---------- */
  .auth-divider {
    display: flex; align-items: center; gap: 14px;
    margin: 22px 0 20px; color: #A1A1AA;
    font-size: 12.5px; letter-spacing: 0.05em;
  }
  .auth-divider::before, .auth-divider::after {
    content: ''; flex: 1; border-top: 1px dotted #D4D4D8;
  }
  .auth-social {
    display: flex; align-items: center; justify-content: center; gap: 12px;
    width: 100%; height: 50px; border-radius: 12px;
    background: #FFFFFF; border: 1px solid #E4E4E7;
    color: #18181B; font-size: 14.5px; font-weight: 500; text-decoration: none;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .auth-social:hover { background: #FAFAFA; border-color: #D4D4D8; }
  .auth-social--disabled { opacity: 0.5; cursor: not-allowed; }
  .auth-social--disabled:hover { background: #FFFFFF; border-color: #E4E4E7; }
  .auth-magic-line {
    text-align: center; font-size: 13.5px; color: #71717A; margin: 18px 0 0;
  }
  .auth-magic-line a {
    color: #18181B; font-weight: 600; text-decoration: none;
  }
  .auth-magic-line a:hover { text-decoration: underline; }
  .auth-footer {
    text-align: center; margin-top: 24px; padding-top: 18px;
    border-top: 1px solid #F0F0F1;
    font-size: 14px; color: #71717A;
  }
  .auth-footer a { color: #18181B; font-weight: 600; text-decoration: none; }
  .auth-footer a:hover { text-decoration: underline; }
  .auth-ok-icon {
    width: 64px; height: 64px; margin: 0 auto 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: #F0F6FF; border: 1px solid #DBEAFE;
    box-shadow: 0 0 24px rgba(37, 99, 235, 0.12);
  }

  /* ---------- alerts ---------- */
  [data-testid="stAlert"] { border-radius: 12px !important; margin-bottom: 14px !important; }

  @media (max-width: 760px) {
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {
      margin: 4vh auto; padding: 32px 22px 20px; max-width: 100%;
    }
  }
</style>
"""

# ---------------------------------------------------------------------------
# Behavior scripts: hash→query shim (magic-link tokens can arrive in the URL
# fragment), inset field icons, show/hide password toggle, magic-link reveal,
# and the footer Sign Up / Sign In switch.
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

  var ICONS = {
    email: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></svg>',
    password: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    name: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
  };

  function mountIcons() {
    document.querySelectorAll('[data-testid="stTextInput"]').forEach(function (wrap) {
      if (wrap.dataset.iconMounted) return;
      wrap.dataset.iconMounted = '1';
      var label = wrap.querySelector('label');
      var txt = label ? label.textContent.toLowerCase() : '';
      var key = null;
      if (txt.indexOf('email') !== -1) key = 'email';
      else if (txt.indexOf('password') !== -1) key = 'password';
      else if (txt.indexOf('full name') !== -1) key = 'name';
      if (!key) return;
      wrap.style.position = 'relative';
      var input = wrap.querySelector('input');
      if (input) input.style.paddingLeft = '44px';
      var span = document.createElement('span');
      span.innerHTML = ICONS[key];
      span.style.cssText = 'position:absolute;left:15px;top:50%;transform:translateY(-50%);color:#A1A1AA;display:flex;pointer-events:none;';
      wrap.appendChild(span);
    });
  }

  function mountEyes() {
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
      btn.style.cssText = 'position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#A1A1AA;padding:4px;display:flex;';
      btn.addEventListener('click', function () {
        var show = pw.type === 'password';
        pw.type = show ? 'text' : 'password';
        btn.innerHTML = show ? eyeOff : eye;
      });
      wrap.appendChild(btn);
    });
  }

  function bindMagicToggle() {
    var toggle = document.getElementById('auth-magic-toggle');
    if (!toggle || toggle.dataset.bound) return;
    toggle.dataset.bound = '1';
    toggle.addEventListener('click', function (e) {
      e.preventDefault();
      var f = document.getElementById('auth-magic-form');
      if (!f) return;
      var open = f.style.display !== 'none' && f.style.display !== '';
      f.style.display = open ? 'none' : 'block';
      toggle.textContent = open ? 'Email me a magic link' : 'Hide magic link';
    });
  }

  function setMode(mode) {
    var isSignUp = mode === 'signup';
    var signIn = document.getElementById('auth-signin-form');
    var signUp = document.getElementById('auth-signup-form');
    var title = document.getElementById('auth-title');
    var sub = document.getElementById('auth-sub');
    var footer = document.getElementById('auth-footer');
    var magicForm = document.getElementById('auth-magic-form');
    var magicToggle = document.getElementById('auth-magic-toggle');
    if (signIn) signIn.style.display = isSignUp ? 'none' : 'block';
    if (signUp) signUp.style.display = isSignUp ? 'block' : 'none';
    if (title) title.textContent = isSignUp ? 'Create your account' : 'Sign in to Cortex';
    if (sub) sub.textContent = isSignUp
      ? 'Start bringing your organization\\u2019s context into one living layer.'
      : 'Access your organization\\u2019s living context layer.';
    if (magicForm) magicForm.style.display = 'none';
    if (magicToggle) magicToggle.textContent = 'Email me a magic link';
    if (footer) footer.innerHTML = isSignUp
      ? 'Already have an account? <a href="#" id="auth-switch-link">Sign In</a>'
      : 'Don\\u2019t have an account? <a href="#" id="auth-switch-link">Sign Up</a>';
    var link = document.getElementById('auth-switch-link');
    if (link) {
      link.href = '#';
      link.onclick = function (e) {
        e.preventDefault();
        setMode(isSignUp ? 'signin' : 'signup');
        return false;
      };
    }
  }

  function mount() {
    mountIcons();
    mountEyes();
    bindMagicToggle();
    var link = document.getElementById('auth-switch-link');
    if (link && !link.dataset.bound) {
      link.dataset.bound = '1';
      link.onclick = function (e) { e.preventDefault(); setMode('signup'); return false; };
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
