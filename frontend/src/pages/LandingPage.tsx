import { ArrowRight, ChevronDown, Menu, Search, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "@/components/brand/Logo";

/* ====================================================================== */
/*  Brand Icons — real SVGs from simple-icons (except Slack)              */
/* ====================================================================== */

function BrandIcon({ path, color, className = "" }: { path: string; color: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill={color}>
      <path d={path} />
    </svg>
  );
}

/* Slack uses a multi-color design — hand-crafted four-bolt mark */
function SlackIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"
        fill="#E01E5A" />
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z"
        fill="#36C5F0" style={{ clipPath: "inset(0 0 50% 0)" }} />
      <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834z"
        fill="#2EB67D" />
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52z"
        fill="#ECB22E" style={{ clipPath: "inset(50% 0 0 0)" }} />
    </svg>
  );
}

const BRAND = {
  gmail: {
    path: "M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z",
    color: "#EA4335",
  },
  github: {
    path: "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12",
    color: "#181717",
  },
  drive: {
    path: "M12.01 1.485c-2.082 0-3.754.02-3.743.047.01.02 1.708 3.001 3.774 6.62l3.76 6.574 3.76-6.574c2.066-3.62 3.764-6.6 3.774-6.62.011-.027-1.661-.047-3.743-.047-1.613 0-3.544 1.527-3.782 1.527S13.623 1.485 12.01 1.485zM7.736 14.948l-3.74 6.496c2.034 1.197 4.554 1.878 7.004 1.878 2.454 0 4.968-.674 7.004-1.878l-3.74-6.496-3.14 5.438S10.02 14.948 7.736 14.948zM1.668 19.444l3.74-6.496-3.74-6.496C.607 7.72 0 9.247 0 10.948s.607 3.228 1.668 4.5z",
    color: "#4285F4",
  },
  jira: {
    path: "M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.577 24h2.056V18.73a5.218 5.218 0 0 0 5.215-5.215h-11.28v-2zm12.43-5.768A5.215 5.215 0 0 0 18.786.53H5.793a5.218 5.218 0 0 0-5.232 5.215v2.057h13.476v-2.057a5.218 5.218 0 0 1 5.232-5.215z",
    color: "#0052CC",
  },
  confluence: {
    path: ".87 18.257c-.248.382-.53.875-.763 1.245a.764.764 0 0 0 .255 1.04l4.965 3.054a.77.77 0 0 0 1.01-.146c2.154-2.718 3.47-4.4 5.833-4.4 2.424 0 3.748 1.722 5.89 4.49a.77.77 0 0 0 1.01.146l4.965-3.054a.77.77 0 0 0 .272-1.04c-.248-.382-.53-.875-.763-1.245C21.827 15.587 19.564 13.35 16.232 12.4c-.523-.147-1.035-.193-1.515-.193-4.675 0-8.113 3.48-9.877 6.05zm13.496-1.762a.77.77 0 0 0 .764-.775.77.77 0 0 0-.764-.775H8.372a.77.77 0 0 0-.763.775.77.77 0 0 0 .763.775h6.03zm-6.254-5.5a.77.77 0 0 0 .763-.775.77.77 0 0 0-.763-.775H5.592a.77.77 0 0 0-.763.775.77.77 0 0 0 .763.775h6.277z",
    color: "#172B4D",
  },
  linear: {
    path: "M2.886 4.18A11.982 11.982 0 0 1 11.99 0C18.624 0 24 5.376 24 12.009c0 3.64-1.62 6.91-4.176 9.126l-1.125-1.992A9.37 9.37 0 0 0 21.6 12.01c0-5.303-4.305-9.61-9.61-9.61a9.61 9.61 0 0 0-8.384 4.928L2.886 4.18zM.262 11.484l1.128 2.008A11.975 11.975 0 0 1 11.99 0v0C6.572.024 2.132 3.822 1.282 8.876l-1.02 2.608zm22.266 1.076c-.058.57-.2 1.12-.41 1.632l-1.264 3.044c-1.37 3.136-4.252 5.28-7.59 5.28-1.43 0-2.77-.408-3.904-1.108l-1.224 2.172A11.982 11.982 0 0 0 11.99 24c7.28 0 13.19-5.91 13.19-13.19 0-3.956-1.752-7.504-4.496-9.9l-1.15 2.116A11.97 11.97 0 0 1 22.314 12c0 1.672-.448 3.244-1.224 4.592l-1.272 3.072a9.39 9.39 0 0 0 3.128-4.104l1.128-2.008.048-.692.504-2.3zM2.886 19.82l1.125 1.992A11.975 11.975 0 0 0 11.99 24v0c5.418-.024 9.858-3.822 10.708-8.876l1.02-2.608-.012-.012L2.886 19.82z",
    color: "#5E6AD2",
  },
} as const;

type IntegrationDef = {
  name: string;
  className: string;
  brandKey: keyof typeof BRAND;
  isSlack?: boolean;
};

const integrations: IntegrationDef[] = [
  { name: "GitHub", className: "orbit-github", brandKey: "github" },
  { name: "Drive", className: "orbit-drive", brandKey: "drive" },
  { name: "Confluence", className: "orbit-confluence", brandKey: "confluence" },
  { name: "Slack", className: "orbit-slack", brandKey: "gmail", isSlack: true },
  { name: "Linear", className: "orbit-linear", brandKey: "linear" },
  { name: "Gmail", className: "orbit-gmail", brandKey: "gmail" },
  { name: "Jira", className: "orbit-jira", brandKey: "jira" },
];

/* ====================================================================== */
/*  Navbar                                                                 */
/* ====================================================================== */

function CortexNavbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="landing-nav" aria-label="Primary navigation">
      <Link to="/" className="landing-wordmark" aria-label="Cortex home">
        <LogoMark className="h-5 w-5" />
        <span>CORTEX</span>
      </Link>
      <nav className="landing-links">
        <a href="#product">
          Product <ChevronDown />
        </a>
        <a href="#solutions">
          Solutions <ChevronDown />
        </a>
        <a href="#resources">
          Resources <ChevronDown />
        </a>
        <a href="#pricing">Pricing</a>
        <a href="#company">
          Company <ChevronDown />
        </a>
      </nav>
      <div className="landing-actions">
        <Link to="/auth" className="landing-login">
          Log in
        </Link>
        <a className="landing-demo" href="mailto:hello@cortex.ai">
          Book a demo <ArrowRight />
        </a>
      </div>
      <button
        className="landing-menu"
        type="button"
        aria-label={menuOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((o) => !o)}
      >
        {menuOpen ? <X /> : <Menu />}
      </button>
      {menuOpen ? (
        <div className="landing-mobile-menu">
          <a href="#product" onClick={() => setMenuOpen(false)}>Product</a>
          <a href="#solutions" onClick={() => setMenuOpen(false)}>Solutions</a>
          <a href="#resources" onClick={() => setMenuOpen(false)}>Resources</a>
          <a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a>
          <a href="#company" onClick={() => setMenuOpen(false)}>Company</a>
          <Link to="/auth" onClick={() => setMenuOpen(false)}>Log in</Link>
          <a className="mobile-menu-demo" href="mailto:hello@cortex.ai" onClick={() => setMenuOpen(false)}>
            Book a demo <ArrowRight />
          </a>
        </div>
      ) : null}
    </header>
  );
}

/* ====================================================================== */
/*  Integration Orbit — wide elliptical arc with brand cards              */
/* ====================================================================== */

function IntegrationOrbit() {
  return (
    <div className="integration-orbit" aria-hidden="true">
      {/* SVG orbit — large smooth elliptical path spanning the hero */}
      <svg className="orbit-lines" viewBox="0 0 1536 864" fill="none" preserveAspectRatio="xMidYMid slice">
        {/* Primary orbit arc — thin, elegant, visible */}
        <ellipse
          cx="768"
          cy="420"
          rx="680"
          ry="340"
          stroke="rgba(35,80,90,0.22)"
          strokeWidth="1.2"
          strokeLinecap="round"
          fill="none"
        />
        {/* Secondary inner arc — dashed, subtle depth */}
        <ellipse
          cx="768"
          cy="420"
          rx="560"
          ry="270"
          stroke="rgba(110,158,146,0.14)"
          strokeWidth="0.8"
          strokeDasharray="4 12"
          fill="none"
        />
      </svg>

      {/* Travelling particles along a matching path */}
      <div className="orbit-particle" />
      <div className="orbit-particle" />
      <div className="orbit-particle" />

      {/* Integration cards with real brand icons */}
      {integrations.map(({ name, className, brandKey, isSlack }) => (
        <div
          key={name}
          className={`integration-card ${className} float-${name.toLowerCase()}`}
        >
          <span className={`integration-icon ${name.toLowerCase()}-icon`}>
            {isSlack ? (
              <SlackIcon />
            ) : (
              <BrandIcon path={BRAND[brandKey].path} color={BRAND[brandKey].color} />
            )}
          </span>
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

/* ====================================================================== */
/*  Cortex Dashboard (inside MacBook) — bright, readable, polished        */
/* ====================================================================== */

function CortexDashboard() {
  return (
    <>
      <aside className="preview-sidebar">
        <div className="preview-brand">
          <LogoMark className="h-4 w-4" />
          <strong>Cortex</strong>
        </div>
        <div className="preview-nav-group">
          <span className="preview-nav-active"><b>⌂ Home</b></span>
          <span><b>🔍 Search</b></span>
          <span><b>◈ Knowledge</b></span>
          <span><b>□ Projects</b></span>
          <span><b>✦ Decisions</b></span>
          <span><b>◆ Agents</b></span>
          <span><b>◌ Activity</b></span>
        </div>
        <div className="preview-nav-bottom">
          <span><b>⚙ Settings</b></span>
        </div>
      </aside>

      <div className="preview-main">
        <div className="preview-topline">
          <span>
            <Search style={{ width: 10, height: 10, display: "inline", verticalAlign: "middle", marginRight: 4, opacity: 0.45 }} />
            Search Cortex…
          </span>
          <span className="preview-top-avatar">PR</span>
        </div>

        <div className="preview-greeting">
          <p>Good morning, Priya 👋</p>
          <h3>Here&apos;s what&apos;s happening across your organization.</h3>
        </div>

        <div className="preview-grid">
          {/* Ask Cortex */}
          <div className="preview-panel preview-ask">
            <span className="preview-panel-kicker">Ask Cortex anything</span>
            <strong>&ldquo;What changed across the organization this week?&rdquo;</strong>
            <span className="preview-search">
              What do you want to know? <ArrowRight />
            </span>
          </div>

          {/* Recent Activity */}
          <div className="preview-panel">
            <span className="preview-panel-kicker">Recent activity</span>
            <div className="preview-activity">
              <i className="activity-dot sage" />
              <span>Platform team discussed Atlas</span>
              <small>Slack · 2h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot blue" />
              <span>Atlas migration PR merged</span>
              <small>GitHub · 1h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot gold" />
              <span>Q4 planning document received</span>
              <small>Gmail · 3h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot sage" />
              <span>Customer region issue → QA</span>
              <small>Jira · 5h ago</small>
            </div>
          </div>

          {/* Projects */}
          <div className="preview-panel">
            <span className="preview-panel-kicker">Projects</span>
            <div className="preview-project-line">
              <span>Atlas</span>
              <b>72%</b>
            </div>
            <div className="preview-project-line">
              <span>Q4 Planning</span>
              <b>80%</b>
            </div>
            <div className="preview-project-line">
              <span>Platform Migration</span>
              <b>45%</b>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ====================================================================== */
/*  MacBook Preview — thin dark bezel, sits on stone pedestal             */
/* ====================================================================== */

function MacBookPreview() {
  return (
    <div className="product-preview-wrap" aria-label="Preview of the Cortex application">
      <div className="laptop">
        <div className="laptop-camera" />
        <div className="laptop-screen">
          <CortexDashboard />
        </div>
        <div className="laptop-base" />
      </div>
      {/* Contact shadow on the stone */}
      <div className="laptop-shadow" />
    </div>
  );
}

/* ====================================================================== */
/*  Landing Page — Viewport-First Composition                             */
/* ====================================================================== */

export function LandingPage() {
  return (
    <div className="landing-page">
      {/* Background — vivid landscape */}
      <div className="landing-landscape" />
      <div className="landing-atmosphere" />

      {/* Navbar — floating pill, absolute positioned */}
      <CortexNavbar />

      {/* Orbit + integration cards — spans full hero */}
      <IntegrationOrbit />

      {/* Hero content — centered text, absolutely positioned in viewport */}
      <div className="landing-hero">
        <div className="landing-eyebrow">
          <LogoMark className="h-4 w-4" /> Your organization&apos;s second brain
        </div>
        <h1 className="landing-headline">
          <span>Unify. Understand.</span>
          <em>Unlock Impact.</em>
        </h1>
        <p className="landing-desc">
          Cortex connects your conversations, documents, code, issues, and
          decisions into a living context layer that your teams and AI agents
          can use — anywhere.
        </p>
        <div className="landing-ctas">
          <a className="landing-cta-primary" href="mailto:hello@cortex.ai">
            Book a demo <ArrowRight />
          </a>
          <Link className="landing-cta-secondary" to="/auth">
            Explore Cortex <ArrowRight />
          </Link>
        </div>
      </div>

      {/* MacBook — absolute positioned at bottom of viewport, centered on stone */}
      <MacBookPreview />
    </div>
  );
}
