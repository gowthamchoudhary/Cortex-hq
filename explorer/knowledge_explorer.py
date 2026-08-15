"""CORTEX — hero landing page.

A single-viewport landing page in the reference design language: pure-black
background with a soft electric-blue spotlight rising from the bottom, a
minimal top navigation, a waitlist badge, a large sans-serif headline with an
editorial serif-italic accent, an email + CTA group, and a wide translucent
integration panel emerging from the glow near the bottom.

Cortex is a living organizational context layer: it connects scattered
conversations, documents, code, issues, and decisions, resolves entities,
tracks changing facts, preserves evidence and history, and surfaces context
to teams and agents.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="CORTEX — Organizational Context Layer",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Hide Streamlit chrome so the page renders edge-to-edge on pure black.
# ---------------------------------------------------------------------------
CHROME_CSS = """
<style>
  html, body, .stApp {
    background: #050505 !important;
    overflow: hidden;
  }
  #MainMenu, footer, [data-testid="stHeader"],
  [data-testid="stToolbar"], [data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
  }
  [data-testid="stAppViewContainer"] > .main {
    padding: 0 !important;
    background: #050505 !important;
  }
  .block-container {
    padding: 0 !important;
    max-width: 100% !important;
  }
</style>
"""

# ---------------------------------------------------------------------------
# The landing page: full-viewport fixed overlay.
# ---------------------------------------------------------------------------
def _strip_line_indent(raw: str) -> str:
    """Remove leading whitespace from every line of raw HTML.

    Streamlit renders markdown with the `marked` parser, which treats any
    line indented with 4+ spaces as a code block and escapes it (showing
    raw HTML source instead of the page). The readable indentation used in
    PAGE_HTML must therefore be removed before rendering.
    """
    return "\n".join(line.lstrip() if line.strip() else "" for line in raw.splitlines())


PAGE_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');

  #cortex-hero {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: #050505;
    color: #ffffff;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
    overflow: hidden;
    user-select: none;
  }
  #cortex-hero a { -webkit-tap-highlight-color: transparent; }
  #cortex-hero ::selection { background: rgba(59, 130, 246, 0.35); }

  /* ---------- atmospheric glow layers ---------- */
  .glow, .beam { position: absolute; pointer-events: none; }
  .glow-core {
    width: 940px; height: 560px; top: 22%; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side, rgba(37, 99, 235, 0.13), transparent 70%);
    filter: blur(30px);
  }
  .glow-accent {
    width: 860px; height: 300px; top: 40%; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side, rgba(139, 92, 246, 0.10), transparent 72%);
    filter: blur(46px);
  }
  .glow-lower {
    width: 1240px; height: 580px; bottom: -170px; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 62%,
      rgba(37, 99, 235, 0.34), rgba(34, 211, 238, 0.12) 48%, transparent 74%);
    filter: blur(56px);
  }
  .glow-cyan {
    width: 720px; height: 300px; bottom: -96px; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 70%, rgba(34, 211, 238, 0.20), transparent 72%);
    filter: blur(46px);
  }
  .beam {
    width: 620px; height: 840px; top: 10%; left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(to top,
      rgba(56, 189, 248, 0.10), rgba(59, 130, 246, 0.05) 42%, transparent 76%);
    filter: blur(34px);
  }

  /* ---------- top navigation ---------- */
  .nav {
    position: absolute; top: 0; left: 0; right: 0; z-index: 4;
    display: flex; align-items: center; justify-content: space-between;
    padding: 34px clamp(40px, 5.2vw, 84px);
  }
  .brand { display: flex; align-items: center; gap: 13px; }
  .brand-icon {
    width: 38px; height: 38px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: radial-gradient(circle at 32% 28%, rgba(59, 130, 246, 0.28), rgba(30, 58, 138, 0.16));
    border: 1px solid rgba(96, 165, 250, 0.35);
    box-shadow: 0 0 18px rgba(59, 130, 246, 0.35), inset 0 0 10px rgba(59, 130, 246, 0.15);
  }
  .brand-name { font-size: 13.5px; font-weight: 600; letter-spacing: 0.16em; color: #ffffff; }
  .brand-tag {
    display: block; margin-top: 3px;
    font-size: 8.5px; font-weight: 500; letter-spacing: 0.18em; text-transform: uppercase;
    color: #6E7684;
  }
  .nav-links {
    position: absolute; left: 50%; transform: translateX(-50%);
    display: flex; align-items: center; gap: clamp(18px, 2.2vw, 32px);
  }
  .nav-links a {
    font-size: 13.5px; color: #9AA1AC; text-decoration: none;
    display: flex; align-items: center; gap: 5px;
    transition: color 0.15s ease;
  }
  .nav-links a:hover { color: #ffffff; }
  .nav-cta {
    padding: 10px 22px; border-radius: 999px;
    background: #ffffff; color: #0a0b0d;
    font-size: 13.5px; font-weight: 500; text-decoration: none;
    box-shadow: 0 0 24px rgba(96, 165, 250, 0.35);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
  }
  .nav-cta:hover { box-shadow: 0 0 36px rgba(96, 165, 250, 0.55); }
  .nav-cta:active { transform: scale(0.97); }

  /* ---------- hero ---------- */
  .hero {
    position: absolute; top: 42%; left: 50%; z-index: 2;
    transform: translate(-50%, -50%);
    width: 100%; display: flex; flex-direction: column; align-items: center;
    text-align: center;
  }
  .badge {
    display: inline-flex; align-items: center; gap: 12px;
    padding: 6px 16px 6px 8px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.09);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    font-size: 13px; color: #E5E7EB;
  }
  .badge-avatars { display: flex; }
  .avatar {
    width: 22px; height: 22px; border-radius: 50%;
    border: 2px solid #0b0d13; margin-left: -8px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
  }
  .avatar:first-child { margin-left: 0; }
  .a1 { background: linear-gradient(135deg, #60a5fa, #1e3a8a); }
  .a2 { background: linear-gradient(135deg, #a78bfa, #4c1d95); }
  .a3 { background: linear-gradient(135deg, #22d3ee, #164e63); }
  .a4 { background: linear-gradient(135deg, #818cf8, #312e81); }
  .badge b { color: #7ec9ff; font-weight: 600; }

  .headline {
    margin: 28px 0 0;
    font-size: clamp(52px, 6.2vw, 88px);
    line-height: 1.0; font-weight: 600; letter-spacing: -0.02em;
    color: #ffffff;
    text-shadow: 0 0 60px rgba(148, 163, 184, 0.12);
  }
  .accent {
    margin: 14px 0 0;
    font-family: 'Instrument Serif', Georgia, serif;
    font-style: italic; font-weight: 400;
    font-size: clamp(46px, 5vw, 68px); line-height: 1.1;
    background-image: linear-gradient(94deg, #cdb9ff 0%, #ffffff 46%, #8ec9ff 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    filter: drop-shadow(0 0 26px rgba(147, 197, 253, 0.22));
  }
  .sub {
    margin: 24px 0 0;
    max-width: 640px;
    font-size: 17px; line-height: 1.6; color: #9AA1AC;
  }

  /* ---------- email + CTA ---------- */
  .cta {
    margin-top: 34px;
    display: flex; align-items: center;
    width: min(560px, 88vw); height: 58px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 30px; padding: 5px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 12px 44px rgba(0, 0, 0, 0.45);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .cta:focus-within {
    border-color: rgba(96, 165, 250, 0.45);
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.10), 0 12px 44px rgba(0, 0, 0, 0.45);
  }
  .cta input {
    flex: 1; min-width: 0;
    background: transparent; border: 0; outline: none;
    color: #ffffff; font-size: 15px; font-family: inherit;
    padding: 0 22px;
  }
  .cta input::placeholder { color: #767E8B; }
  .cta button {
    width: 212px; height: 48px; border-radius: 25px;
    background: #ffffff; color: #0a0b0d; border: 0; cursor: pointer;
    font-size: 14px; font-weight: 500; font-family: inherit;
    display: flex; align-items: center; justify-content: center; gap: 9px;
    box-shadow: 0 0 28px rgba(96, 165, 250, 0.35);
    transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
  }
  .cta button:hover { background: #eef3fb; box-shadow: 0 0 38px rgba(96, 165, 250, 0.5); }
  .cta button:active { transform: scale(0.98); }
  .cta button svg { margin-left: 1px; }
  .success {
    display: none; margin-top: 20px;
    font-size: 14px; color: #8fd6ff; letter-spacing: 0.01em;
  }

  /* ---------- integration panel ---------- */
  .integrations {
    position: absolute; bottom: -12px; left: 50%; z-index: 3;
    transform: translateX(-50%);
    width: min(960px, 92vw); height: 158px;
    border-radius: 32px; overflow: hidden;
    padding: 24px 40px 26px;
    display: flex; flex-direction: column; align-items: center;
    background: linear-gradient(180deg, rgba(30, 41, 66, 0.50), rgba(8, 11, 18, 0.74));
    border: 1px solid rgba(148, 163, 184, 0.16);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.06),
      0 -18px 60px rgba(37, 99, 235, 0.18),
      0 30px 80px rgba(0, 0, 0, 0.6);
  }
  .integrations .graph {
    position: absolute; inset: 0; width: 100%; height: 100%;
    opacity: 0.55; filter: blur(1px);
    pointer-events: none;
  }
  .integrations-label {
    position: relative; margin: 0 0 18px;
    font-size: 10.5px; font-weight: 500; letter-spacing: 0.3em;
    text-transform: uppercase; color: rgba(226, 232, 240, 0.5);
  }
  .integrations-row {
    position: relative;
    display: flex; align-items: center; justify-content: center;
    gap: clamp(20px, 3.4vw, 46px); flex-wrap: wrap;
  }
  .integ { display: flex; align-items: center; gap: 9px; }
  .integ svg { opacity: 0.92; }
  .integ span {
    font-size: 13.5px; color: #E7EAF1; letter-spacing: 0.01em; white-space: nowrap;
  }
  .integ.more span { color: #AEB6C2; }
  .integ.more svg { opacity: 0.7; }

  @media (max-width: 1180px) {
    .nav-links { display: none; }
    .nav { padding: 28px 38px; }
  }
  @media (max-width: 760px) {
    .headline { font-size: clamp(38px, 9vw, 52px); }
    .accent { font-size: clamp(30px, 7vw, 44px); }
    .sub { font-size: 15px; }
    .cta { height: 54px; }
    .cta button { width: 158px; }
    .integrations { height: auto; padding-bottom: 34px; }
  }
</style>

<div id="cortex-hero">
  <!-- atmospheric light -->
  <div class="beam"></div>
  <div class="glow glow-core"></div>
  <div class="glow glow-accent"></div>
  <div class="glow glow-lower"></div>
  <div class="glow glow-cyan"></div>

  <!-- top navigation -->
  <header class="nav">
    <div class="brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="4" r="1.9" fill="#7EC9FF"/>
          <circle cx="4.8" cy="10.2" r="1.9" fill="#7EC9FF"/>
          <circle cx="19.2" cy="10.2" r="1.9" fill="#7EC9FF"/>
          <circle cx="8.6" cy="18.4" r="1.9" fill="#A5C9F5"/>
          <circle cx="15.4" cy="18.4" r="1.9" fill="#A5C9F5"/>
          <circle cx="12" cy="11.6" r="1.9" fill="#38BDF8"/>
          <path d="M12 5.9 L5.6 9.0 M12 5.9 L18.4 9.0 M5.6 9.0 L8.6 16.6 M18.4 9.0 L15.4 16.6 M12 13.5 L8.6 16.6 M12 13.5 L15.4 16.6"
                stroke="#3B82F6" stroke-width="1.1" opacity="0.85"/>
        </svg>
      </div>
      <div>
        <div class="brand-name">CORTEX</div>
        <div class="brand-tag">Organizational Context Layer</div>
      </div>
    </div>
    <nav class="nav-links">
      <a href="#">Product
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
      </a>
      <a href="#">How It Works</a>
      <a href="#">Use Cases</a>
      <a href="#">Pricing</a>
      <a href="#">Docs</a>
      <a href="#">GitHub</a>
    </nav>
    <a class="nav-cta" href="#" id="nav-cta">Join The Waitlist</a>
  </header>

  <!-- hero content -->
  <main class="hero">
    <div class="badge">
      <div class="badge-avatars">
        <span class="avatar a1"></span>
        <span class="avatar a2"></span>
        <span class="avatar a3"></span>
        <span class="avatar a4"></span>
      </div>
      <span><b>576</b>currently on the waitlist</span>
    </div>

    <h1 class="headline">Understand your<br>organization.</h1>

    <p class="accent">Cortex makes it usable.</p>

    <p class="sub">Connect your scattered conversations, documents, code, issues,<br>
      and decisions into a living context layer that your team and agents can use — anywhere, anytime.</p>

    <form class="cta" id="waitlist-form" novalidate>
      <input type="email" id="waitlist-email" name="email" placeholder="Your work email" autocomplete="email" />
      <button type="submit" id="waitlist-submit">Join The Waitlist
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </button>
    </form>
    <p class="success" id="waitlist-success">You're on the list — welcome to Cortex.</p>
  </main>

  <!-- integration panel emerging from the glow -->
  <section class="integrations">
    <svg class="graph" viewBox="0 0 960 158" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g stroke="#93c5fd" stroke-width="1" opacity="0.35" fill="none">
        <line x1="118" y1="100" x2="232" y2="62"/>
        <line x1="232" y1="62" x2="344" y2="116"/>
        <line x1="232" y1="62" x2="474" y2="38"/>
        <line x1="344" y1="116" x2="474" y2="38"/>
        <line x1="474" y1="38" x2="604" y2="94"/>
        <line x1="604" y1="94" x2="724" y2="44"/>
        <line x1="604" y1="94" x2="836" y2="104"/>
        <line x1="724" y1="44" x2="836" y2="104"/>
      </g>
      <g fill="rgba(96, 165, 250, 0.30)">
        <circle cx="118" cy="100" r="4"/>
        <circle cx="232" cy="62" r="5"/>
        <circle cx="344" cy="116" r="4"/>
        <circle cx="474" cy="38" r="6"/>
        <circle cx="604" cy="94" r="5"/>
        <circle cx="724" cy="44" r="4"/>
        <circle cx="836" cy="104" r="5"/>
      </g>
    </svg>

    <p class="integrations-label">Cortex connects your organization</p>

    <div class="integrations-row">
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
        </svg>
        <span>Slack</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
        </svg>
        <span>Gmail</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
        </svg>
        <span>GitHub</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.215 5.215 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zm5.705-5.7h-11.56a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058A5.215 5.215 0 0 0 24 12.543V1.058a1.001 1.001 0 0 0-1.001-1.001z"/>
        </svg>
        <span>Jira</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M.87 18.12c.193 0 .38.062.536.177l11.173 8.022c.161.117.36.18.564.18.53 0 .96-.43.96-.96v-3.426c0-.541-.218-1.056-.618-1.428l-5.36-4.96 5.36-4.97c.4-.372.618-.885.618-1.427V6.9c0-.531-.43-.96-.96-.96-.204 0-.403.063-.564.18L1.406 14.14c-.156.114-.344.177-.536.177-.53 0-.96.43-.96.96v1.884c0 .53.43.96.96.96zm22.26-.12c0-.203-.063-.38-.177-.536L11.78 9.44c-.16-.116-.36-.18-.563-.18-.531 0-.96.43-.96.96v3.426c0 .541.218 1.057.618 1.428l5.36 4.962-5.36 4.968c-.4.372-.618.885-.618 1.428v3.426c0 .53.43.96.96.96.203 0 .402-.064.564-.18l11.172-8.02c.114-.158.177-.333.177-.537v-1.887c0-.53-.43-.96-.96-.96z"/>
        </svg>
        <span>Confluence</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#AEB9C9" aria-hidden="true">
          <path d="M4.433 22.5l-2.165-3.75L12 3.75l2.165 3.75H6.598L4.433 22.5zm4.712 0L11.31 18h9.257l-2.165 3.75H9.145zM20.168 7.5l2.165 3.75-5.716 9.9-2.164-3.75 5.715-9.9zM15.435 4.5L13.27.75h4.33L19.76 4.5h-4.325zM9.1 4.5h5.716l-2.164 3.75H6.935L9.1 4.5z"/>
        </svg>
        <span>Drive</span>
      </div>
      <div class="integ more">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#AEB9C9" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span>More</span>
      </div>
    </div>
  </section>
</div>

<script>
(function () {
  var form = document.getElementById('waitlist-form');
  var success = document.getElementById('waitlist-success');

  function quietNav() {
    document.querySelectorAll('#cortex-hero a[href="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); });
    });
  }
  quietNav();

  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      form.style.display = 'none';
      success.style.display = 'block';
    });
  }

  var navCta = document.getElementById('nav-cta');
  var email = document.getElementById('waitlist-email');
  if (navCta && email) {
    navCta.addEventListener('click', function (e) {
      e.preventDefault();
      email.focus();
      email.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  }
})();
</script>
"""

st.markdown(CHROME_CSS, unsafe_allow_html=True)
st.markdown(_strip_line_indent(PAGE_HTML), unsafe_allow_html=True)
