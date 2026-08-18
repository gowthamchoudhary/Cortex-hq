import { ArrowRight, ChevronDown, Menu, Search, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "@/components/brand/Logo";

/* ====================================================================== */
/*  Brand Icons — real SVGs from simple-icons                             */
/* ====================================================================== */

function BrandIcon({ path, color, className = "" }: { path: string; color: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill={color}>
      <path d={path} />
    </svg>
  );
}

const BRAND = {
  slack: {
    // Slack brand mark — the four-color hashtag/bolt
    path: "M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z",
    color: "#E01E5A",
  },
  gmail: {
    path: "M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z",
    color: "#EA4335",
  },
  github: {
    path: "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12",
    color: "#24292F",
  },
  drive: {
    path: "M7.71 24.938l-4.6-7.973L8.3 4.374l4.594 7.966zm11.766-.18L24 16.97l-4.58-7.966L14.832 4.374zM.142 16.983l4.6 7.968 4.586-7.98L4.74 9.003zm7.756-13.59L3.31 11.373l4.586 7.968 4.586-7.968zm9.572 0L12.882 11.373l4.586 7.968 4.586-7.968z",
    color: "#4285F4",
  },
  jira: {
    path: "M11.027 2.012c.355-.605 1.264-.605 1.62 0l5.51 9.47c.347.594-.116 1.356-.81 1.356h-3.15a.6.6 0 0 0-.518.299l-2.003 3.468a.6.6 0 0 1-1.036 0L9.372 13.137a.6.6 0 0 0-.518-.299H5.704c-.694 0-1.157-.762-.81-1.356l5.51-9.47zM.49 14.518c-.355.605-.07 1.374.598 1.585l5.187 1.652a.6.6 0 0 0 .474-.05l3.694-2.395a.6.6 0 0 1-.674-1.003L.49 14.518zm23.02 0c.355.605.07 1.374-.598 1.585l-5.187 1.652a.6.6 0 0 1-.474-.05l-3.694-2.395a.6.6 0 0 1 .674-1.003l9.28 2.211z",
    color: "#0052CC",
  },
  confluence: {
    path: "M4.2 18.3c-.2.5-.7.7-1.2.5C1.7 18 1 17 1 15.7V8.3c0-1.3.7-2.3 1.8-2.8.5-.2 1 .1 1.2.5.3.6.7 1.4 1.2 2.2.8 1.3 1.8 2.7 2.8 4.2.3.5.9.6 1.4.3l5.5-3.2c.5-.3.6-.9.3-1.4-.8-1.3-1.6-2.5-2.4-3.7-.3-.5-.1-1.1.4-1.4.2-.1.3-.2.5-.2h4.9c1.3 0 2.3.7 2.8 1.8.2.5.1 1-.3 1.3-.7.5-1.5 1.1-2.2 1.7-.8.7-1.7 1.5-2.5 2.3-.3.3-.3.8 0 1.1l3.6 3.6c.3.3.3.8 0 1.1-.6.6-1.4 1-2.2 1h-4.9c-.5 0-1-.2-1.4-.5-.8-.6-1.6-1.4-2.4-2.3-1-.9-1.9-1.9-2.8-2.9-.3-.4-.8-.5-1.2-.3z",
    color: "#172B4D",
  },
  linear: {
    path: "M3.19 12.36c.16-.44.46-.78.87-1.01l5.67-3.27c.41-.24.87-.24 1.28 0l5.67 3.27c.41.23.71.57.87 1.01l1.11 3.07c.16.44.08.88-.22 1.21l-5.67 5.67c-.41.41-.96.63-1.52.63h0c-.57 0-1.12-.22-1.52-.63l-5.67-5.67c-.3-.33-.38-.77-.22-1.21l1.11-3.07zM12 1.35c.41 0 .87.24 1.28.47l5.67 3.27c.41.23.71.57.87 1.01l1.11 3.07c.16.44.08.88-.22 1.21l-5.67 5.67c-.41.41-.96.63-1.52.63h0c-.57 0-1.12-.22-1.52-.63l-5.67-5.67c-.3-.33-.38-.77-.22-1.21l1.11-3.07c.16-.44.46-.78.87-1.01L10.72 1.82c.41-.23.87-.47 1.28-.47z",
    color: "#5E6AD2",
  },
} as const;

type IntegrationDef = {
  name: string;
  className: string;
  brandKey: keyof typeof BRAND;
};

const integrations: IntegrationDef[] = [
  { name: "Slack", className: "orbit-slack", brandKey: "slack" },
  { name: "Gmail", className: "orbit-gmail", brandKey: "gmail" },
  { name: "GitHub", className: "orbit-github", brandKey: "github" },
  { name: "Drive", className: "orbit-drive", brandKey: "drive" },
  { name: "Jira", className: "orbit-jira", brandKey: "jira" },
  { name: "Confluence", className: "orbit-confluence", brandKey: "confluence" },
  { name: "Linear", className: "orbit-linear", brandKey: "linear" },
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
/*  Integration Orbit                                                      */
/* ====================================================================== */

function IntegrationOrbit() {
  return (
    <div className="integration-orbit" aria-hidden="true">
      {/* SVG orbit path — visible, elegant arc */}
      <svg className="orbit-lines" viewBox="0 0 1100 560" fill="none">
        {/* Primary arc — visible but not heavy */}
        <path
          d="M103 382C190 120 349 36 550 36c201 0 360 84 447 346"
          stroke="rgba(35,80,90,0.28)"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
        {/* Secondary dashed arc — depth */}
        <path
          d="M48 464C213 280 359 226 550 226s337 54 502 238"
          stroke="rgba(110,158,146,0.18)"
          strokeWidth="0.9"
          strokeDasharray="3 10"
        />
      </svg>

      {/* Travelling particles */}
      <div className="orbit-particle" />
      <div className="orbit-particle" />
      <div className="orbit-particle" />

      {/* Integration cards with real brand icons */}
      {integrations.map(({ name, className, brandKey }) => (
        <div
          key={name}
          className={`integration-card ${className} float-${name.toLowerCase()}`}
        >
          <span className={`integration-icon ${name.toLowerCase()}-icon`}>
            <BrandIcon path={BRAND[brandKey].path} color={BRAND[brandKey].color} />
          </span>
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

/* ====================================================================== */
/*  Cortex Dashboard (inside MacBook)                                      */
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
            <Search style={{ width: 11, height: 11, display: "inline", verticalAlign: "middle", marginRight: 5, opacity: 0.45 }} />
            Search Cortex…
          </span>
          <span className="preview-top-avatar">PR</span>
        </div>

        <div className="preview-greeting">
          <p>Good morning, Priya <span>👋</span></p>
          <h3>Here&apos;s what&apos;s happening across your organization.</h3>
        </div>

        <div className="preview-grid">
          {/* Ask Cortex */}
          <div className="preview-panel preview-ask">
            <span className="preview-panel-kicker">Ask Cortex anything</span>
            <strong>What changed across the organization this week?</strong>
            <span className="preview-search">
              What do you want to know? <ArrowRight />
            </span>
          </div>

          {/* Recent Activity */}
          <div className="preview-panel">
            <span className="preview-panel-kicker">Recent activity</span>
            <div className="preview-activity">
              <i className="activity-dot sage" />
              <span>Design system updated</span>
              <small>Figma · 2h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot blue" />
              <span>API rate limit discussion</span>
              <small>Slack · 1h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot sage" />
              <span>Data pipeline improved</span>
              <small>GitHub · 3h ago</small>
            </div>
            <div className="preview-activity">
              <i className="activity-dot gold" />
              <span>Q4 planning kickoff</span>
              <small>Google Docs · 5h ago</small>
            </div>
          </div>

          {/* Projects */}
          <div className="preview-panel">
            <span className="preview-panel-kicker">Projects</span>
            <div className="preview-project-line">
              <span>Website Redesign</span>
              <b>72%</b>
            </div>
            <div className="preview-project-line">
              <span>Mobile App</span>
              <b>45%</b>
            </div>
            <div className="preview-project-line">
              <span>Q4 Planning</span>
              <b>80%</b>
            </div>
            <div className="preview-project-line">
              <span>Knowledge Base</span>
              <b>90%</b>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ====================================================================== */
/*  MacBook Preview                                                        */
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
    </div>
  );
}

/* ====================================================================== */
/*  Landing Page                                                           */
/* ====================================================================== */

export function LandingPage() {
  return (
    <div className="landing-page">
      {/* Vivid background */}
      <div className="landing-landscape" />
      <div className="landing-atmosphere" />

      {/* Floating navbar */}
      <CortexNavbar />

      <main className="landing-main">
        {/* Orbit + integration cards */}
        <IntegrationOrbit />

        {/* Hero copy */}
        <div className="landing-copy">
          <div className="landing-eyebrow">
            <LogoMark className="h-4 w-4" /> Your organization&apos;s second brain
          </div>
          <h1>
            <span>Unify. Understand.</span>
            <em>Unlock Impact.</em>
          </h1>
          <p>
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

        {/* MacBook with dashboard */}
        <MacBookPreview />
      </main>
    </div>
  );
}
