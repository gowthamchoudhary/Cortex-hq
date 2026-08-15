"""CORTEX — hero landing page.

A single-viewport landing page in the reference design language: a mostly
pure-black canvas with a soft, concentrated electric-blue light emerging from
the lower center, a minimal top navigation, a small eyebrow, a large
sans-serif headline with an editorial serif-italic accent, a pill CTA, and a
wide translucent integration panel rising out of the bottom glow.

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
    -moz-osx-font-smoothing: grayscale;
    overflow: hidden;
    user-select: none;
  }
  #cortex-hero a { -webkit-tap-highlight-color: transparent; }
  #cortex-hero ::selection { background: rgba(59, 130, 246, 0.35); }

  /* ---------- atmospheric light: black base, blue/violet glow rises from below ---------- */
  .glow, .beam { position: absolute; pointer-events: none; }
  /* dark-blue atmospheric haze behind the headline */
  .glow-hero {
    width: 1120px; height: 540px; top: 22%; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side,
      rgba(59, 130, 246, 0.15), rgba(76, 29, 149, 0.10) 46%, transparent 76%);
    filter: blur(54px);
  }
  /* very subtle purple illumination around the accent line */
  .glow-accent {
    width: 920px; height: 340px; top: 38%; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side,
      rgba(139, 92, 246, 0.12), rgba(59, 130, 246, 0.06) 48%, transparent 74%);
    filter: blur(48px);
  }
  /* electric-blue glow emerging from the lower center */
  .glow-lower {
    width: 1320px; height: 700px; bottom: -260px; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 78%,
      rgba(34, 211, 238, 0.17), rgba(59, 130, 246, 0.26) 40%,
      rgba(30, 58, 138, 0.13) 56%, transparent 78%);
    filter: blur(62px);
  }
  /* cyan highlight at the very bottom center */
  .glow-cyan {
    width: 760px; height: 320px; bottom: -110px; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(closest-side at 50% 70%,
      rgba(34, 211, 238, 0.20), transparent 72%);
    filter: blur(46px);
  }
  /* soft blue-to-cyan beam rising behind the hero */
  .beam {
    width: 580px; height: 940px; bottom: -160px; left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(to top,
      rgba(34, 211, 238, 0.14), rgba(59, 130, 246, 0.10) 32%, transparent 70%);
    filter: blur(42px);
  }

  /* ---------- top navigation ---------- */
  .nav {
    position: absolute; top: 0; left: 0; right: 0; z-index: 4;
    display: flex; align-items: center; justify-content: space-between;
    padding: 36px clamp(70px, 5.5vw, 88px);
  }
  .brand { display: flex; align-items: center; gap: 13px; }
  .brand-icon {
    width: 38px; height: 38px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: radial-gradient(circle at 32% 28%, rgba(59, 130, 246, 0.22), rgba(23, 37, 84, 0.14));
    border: 1px solid rgba(96, 165, 250, 0.30);
    box-shadow: 0 0 16px rgba(59, 130, 246, 0.28), inset 0 0 10px rgba(59, 130, 246, 0.12);
  }
  .brand-name { font-size: 13.5px; font-weight: 600; letter-spacing: 0.16em; color: #F5F5F5; }
  .brand-tag {
    display: block; margin-top: 3px;
    font-size: 8.5px; font-weight: 500; letter-spacing: 0.18em; text-transform: uppercase;
    color: #6E7684;
  }
  .nav-links {
    position: absolute; left: 50%; transform: translateX(-50%);
    display: flex; align-items: center; gap: clamp(20px, 2.4vw, 34px);
  }
  .nav-links a {
    font-size: 13.5px; color: #98A0AC; text-decoration: none;
    display: flex; align-items: center; gap: 5px;
    transition: color 0.15s ease;
  }
  .nav-links a:hover { color: #F5F5F5; }
  .nav-cta {
    display: inline-flex; align-items: center; justify-content: center;
    width: 132px; height: 40px; border-radius: 999px;
    background: #ffffff; color: #0a0b0d;
    font-size: 13.5px; font-weight: 500; text-decoration: none;
    box-shadow: 0 0 22px rgba(96, 165, 250, 0.30);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
  }
  .nav-cta:hover { box-shadow: 0 0 34px rgba(96, 165, 250, 0.5); }
  .nav-cta:active { transform: scale(0.97); }

  /* ---------- hero ---------- */
  .hero {
    position: absolute; top: 16.5%; left: 50%; z-index: 2;
    transform: translateX(-50%);
    width: 100%; display: flex; flex-direction: column; align-items: center;
    text-align: center;
  }
  .eyebrow {
    display: inline-flex; align-items: center; gap: 9px;
    padding: 7px 16px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    font-size: 10.5px; font-weight: 500; letter-spacing: 0.22em;
    text-transform: uppercase; color: #9AA1AC;
  }
  .eyebrow::before {
    content: ''; width: 5px; height: 5px; border-radius: 50%;
    background: #7EC9FF;
    box-shadow: 0 0 8px rgba(96, 165, 250, 0.9);
  }

  .headline {
    margin: 26px 0 0;
    font-size: clamp(52px, 5.6vw, 78px);
    line-height: 1.02; font-weight: 500; letter-spacing: -0.02em;
    color: #ffffff;
  }
  .accent {
    margin: 10px 0 0;
    font-family: 'Instrument Serif', Georgia, serif;
    font-style: italic; font-weight: 400;
    font-size: clamp(50px, 5.3vw, 74px); line-height: 1.06;
    background-image: linear-gradient(92deg, #d0b6ff 0%, #ffffff 42%, #7db8ff 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    filter: drop-shadow(0 0 36px rgba(147, 160, 255, 0.26));
  }
  .sub {
    margin: 20px 0 0;
    max-width: 640px;
    font-size: 17px; line-height: 1.6; color: #9AA1AC;
  }

  /* ---------- pill CTA ---------- */
  .cta {
    margin-top: 32px;
    display: flex; align-items: center;
    padding: 6px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 31px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 14px 44px rgba(0, 0, 0, 0.5);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .cta:hover {
    border-color: rgba(96, 165, 250, 0.28);
    box-shadow: 0 14px 44px rgba(0, 0, 0, 0.5), 0 0 34px rgba(37, 99, 235, 0.14);
  }
  .cta a {
    display: inline-flex; align-items: center; justify-content: center; gap: 10px;
    width: 206px; height: 48px; border-radius: 25px;
    background: #ffffff; color: #0a0b0d;
    font-size: 15px; font-weight: 500; text-decoration: none;
    box-shadow: 0 0 26px rgba(96, 165, 250, 0.30);
    transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
  }
  .cta a:hover { background: #eef3fb; box-shadow: 0 0 38px rgba(96, 165, 250, 0.48); }
  .cta a:active { transform: scale(0.98); }
  .cta a svg { margin-left: 1px; }

  /* ---------- integration panel emerging from the glow ---------- */
  .integrations {
    position: absolute; bottom: -70px; left: 50%; z-index: 3;
    transform: translateX(-50%);
    width: min(1000px, 92vw); height: 262px;
    border-radius: 34px; overflow: hidden;
    padding: 30px 44px;
    display: flex; flex-direction: column; align-items: center;
    background: linear-gradient(180deg, rgba(24, 30, 44, 0.42), rgba(6, 9, 15, 0.80));
    border: 1px solid rgba(148, 163, 184, 0.14);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.05),
      0 -24px 80px rgba(37, 99, 235, 0.16),
      0 40px 90px rgba(0, 0, 0, 0.65);
  }
  .integrations .graph {
    position: absolute; inset: 0; width: 100%; height: 100%;
    opacity: 0.5; filter: blur(1.2px);
    pointer-events: none;
  }
  .integrations-label {
    position: relative; margin: 0 0 22px;
    font-size: 10.5px; font-weight: 500; letter-spacing: 0.3em;
    text-transform: uppercase; color: rgba(226, 232, 240, 0.48);
  }
  .integrations-row {
    position: relative;
    display: flex; align-items: center; justify-content: center;
    gap: clamp(20px, 3.2vw, 44px); flex-wrap: wrap;
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
    .nav { padding: 28px 40px; }
  }
  @media (max-width: 760px) {
    .headline { font-size: clamp(38px, 9vw, 52px); }
    .accent { font-size: clamp(30px, 7vw, 44px); }
    .sub { font-size: 15px; }
    .cta a { width: 172px; height: 46px; }
    .integrations { height: auto; padding-bottom: 40px; }
  }
</style>

<div id="cortex-hero">
  <!-- atmospheric light -->
  <div class="beam"></div>
  <div class="glow glow-hero"></div>
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
    <a class="nav-cta" href="#">Explore Cortex</a>
  </header>

  <!-- hero content -->
  <main class="hero">
    <div class="eyebrow">Organizational Context Layer</div>

    <h1 class="headline">Understand your<br>organization.</h1>

    <p class="accent">Cortex makes it usable.</p>

    <p class="sub">Connect your scattered conversations, documents, code, issues, and decisions into a living context layer that your team and agents can use — anywhere, anytime.</p>

    <div class="cta">
      <a href="#">Explore Cortex
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </a>
    </div>
  </main>

  <!-- integration panel emerging from the glow -->
  <section class="integrations">
    <svg class="graph" viewBox="0 0 1000 262" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g stroke="#93c5fd" stroke-width="1" opacity="0.30" fill="none">
        <line x1="120" y1="180" x2="240" y2="120"/>
        <line x1="240" y1="120" x2="360" y2="196"/>
        <line x1="240" y1="120" x2="500" y2="74"/>
        <line x1="360" y1="196" x2="500" y2="74"/>
        <line x1="500" y1="74" x2="620" y2="160"/>
        <line x1="620" y1="160" x2="760" y2="92"/>
        <line x1="620" y1="160" x2="872" y2="178"/>
        <line x1="760" y1="92" x2="872" y2="178"/>
        <line x1="120" y1="180" x2="360" y2="196"/>
      </g>
      <g fill="rgba(96, 165, 250, 0.28)">
        <circle cx="120" cy="180" r="4"/>
        <circle cx="240" cy="120" r="5"/>
        <circle cx="360" cy="196" r="4"/>
        <circle cx="500" cy="74" r="6"/>
        <circle cx="620" cy="160" r="5"/>
        <circle cx="760" cy="92" r="4"/>
        <circle cx="872" cy="178" r="5"/>
      </g>
      <g fill="rgba(226, 232, 240, 0.32)" font-family="Inter, sans-serif" font-size="9">
        <text x="96" y="202">Person</text>
        <text x="466" y="64">Project</text>
        <text x="726" y="82">Repository</text>
        <text x="848" y="198">Issue</text>
        <text x="588" y="182">Decision</text>
        <text x="330" y="214">Document</text>
      </g>
    </svg>

    <p class="integrations-label">Cortex connects your organization</p>

    <div class="integrations-row">
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
        </svg>
        <span>Slack</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
        </svg>
        <span>Gmail</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
        </svg>
        <span>GitHub</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.215 5.215 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zm5.705-5.7h-11.56a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058A5.215 5.215 0 0 0 24 12.543V1.058a1.001 1.001 0 0 0-1.001-1.001z"/>
        </svg>
        <span>Jira</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M.87 18.12c.193 0 .38.062.536.177l11.173 8.022c.161.117.36.18.564.18.53 0 .96-.43.96-.96v-3.426c0-.541-.218-1.056-.618-1.428l-5.36-4.96 5.36-4.97c.4-.372.618-.885.618-1.427V6.9c0-.531-.43-.96-.96-.96-.204 0-.403.063-.564.18L1.406 14.14c-.156.114-.344.177-.536.177-.53 0-.96.43-.96.96v1.884c0 .53.43.96.96.96zm22.26-.12c0-.203-.063-.38-.177-.536L11.78 9.44c-.16-.116-.36-.18-.563-.18-.531 0-.96.43-.96.96v3.426c0 .541.218 1.057.618 1.428l5.36 4.962-5.36 4.968c-.4.372-.618.885-.618 1.428v3.426c0 .53.43.96.96.96.203 0 .402-.064.564-.18l11.172-8.02c.114-.158.177-.333.177-.537v-1.887c0-.53-.43-.96-.96-.96z"/>
        </svg>
        <span>Confluence</span>
      </div>
      <div class="integ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#B7C0CD" aria-hidden="true">
          <path d="M4.433 22.5l-2.165-3.75L12 3.75l2.165 3.75H6.598L4.433 22.5zm4.712 0L11.31 18h9.257l-2.165 3.75H9.145zM20.168 7.5l2.165 3.75-5.716 9.9-2.164-3.75 5.715-9.9zM15.435 4.5L13.27.75h4.33L19.76 4.5h-4.325zM9.1 4.5h5.716l-2.164 3.75H6.935L9.1 4.5z"/>
        </svg>
        <span>Drive</span>
      </div>
      <div class="integ more">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#B7C0CD" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span>More</span>
      </div>
    </div>
  </section>
</div>

<script>
(function () {
  document.querySelectorAll('#cortex-hero a[href="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); });
  });
})();
</script>
"""

st.markdown(CHROME_CSS, unsafe_allow_html=True)
st.markdown(_strip_line_indent(PAGE_HTML), unsafe_allow_html=True)
