import { ArrowRight, ChevronDown, Menu, Search, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "@/components/brand/Logo";

/* ====================================================================== */
/*  Real brand icons from @icons-pack/react-simple-icons                  */
/* ====================================================================== */

import {
  SiGmail,
  SiGithub,
  SiGoogledrive,
  SiJira,
  SiConfluence,
  SiLinear,
} from "@icons-pack/react-simple-icons";

/* Slack isn't in the package — hand-crafted multi-color mark */
function SlackIcon({ size = 24 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <path
        d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"
        fill="#E01E5A"
      />
      <path
        d="M6.313 8.834a2.527 2.527 0 0 1-2.521-2.52A2.528 2.528 0 0 1 6.313 3.79a2.527 2.527 0 0 1 2.521 2.522v2.522H6.313z"
        fill="#36C5F0"
      />
      <path
        d="M8.834 6.313a2.528 2.528 0 0 1 2.521-2.521 2.528 2.528 0 0 1 2.521 2.521V8.83a2.528 2.528 0 0 1-2.521 2.521 2.527 2.527 0 0 1-2.521-2.52V6.313z"
        fill="#2EB67D"
      />
      <path
        d="M15.165 6.313a2.528 2.528 0 0 1 2.523-2.521A2.528 2.528 0 0 1 20.21 6.313a2.527 2.527 0 0 1-2.522 2.52h-2.523V6.313z"
        fill="#ECB22E"
      />
      <path
        d="M17.688 8.834a2.528 2.528 0 0 1 2.523 2.521 2.527 2.527 0 0 1-2.523 2.521h-6.312A2.528 2.528 0 0 1 8.834 11.355a2.528 2.528 0 0 1 2.52-2.521h6.312z"
        fill="#36C5F0"
      />
      <path
        d="M15.165 17.688a2.527 2.527 0 0 1 2.523 2.523A2.528 2.528 0 0 1 15.165 22.73a2.527 2.527 0 0 1-2.52-2.52v-2.522h2.52z"
        fill="#E01E5A"
      />
      <path
        d="M12.643 17.688a2.528 2.528 0 0 1-2.521 2.523 2.527 2.527 0 0 1-2.521-2.523v-6.312A2.528 2.528 0 0 1 10.122 8.834a2.527 2.527 0 0 1 2.521 2.521v6.313z"
        fill="#2EB67D"
      />
      <path
        d="M8.834 15.165a2.528 2.528 0 0 1-2.521 2.523A2.527 2.527 0 0 1 3.79 15.165a2.528 2.528 0 0 1 2.522-2.52h2.522v2.52z"
        fill="#ECB22E"
      />
    </svg>
  );
}

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
        <Link className="landing-cta-primary" to="/auth">
          Get started <ArrowRight />
        </Link>
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
          <Link className="mobile-menu-demo" to="/auth" onClick={() => setMenuOpen(false)}>
            Get started <ArrowRight />
          </Link>
        </div>
      ) : null}
    </header>
  );
}

/* ====================================================================== */
/*  Integration Orbit — wide elliptical arc with real brand cards         */
/* ====================================================================== */

type IntegrationDef = {
  name: string;
  className: string;
  icon: React.ReactNode;
};

const integrations: IntegrationDef[] = [
  {
    name: "GitHub",
    className: "orbit-github",
    icon: <SiGithub size={26} color="#181717" />,
  },
  {
    name: "Drive",
    className: "orbit-drive",
    icon: <SiGoogledrive size={26} color="#4285F4" />,
  },
  {
    name: "Confluence",
    className: "orbit-confluence",
    icon: <SiConfluence size={26} color="#172B4D" />,
  },
  {
    name: "Slack",
    className: "orbit-slack",
    icon: <SlackIcon size={26} />,
  },
  {
    name: "Linear",
    className: "orbit-linear",
    icon: <SiLinear size={26} color="#5E6AD2" />,
  },
  {
    name: "Gmail",
    className: "orbit-gmail",
    icon: <SiGmail size={26} color="#EA4335" />,
  },
  {
    name: "Jira",
    className: "orbit-jira",
    icon: <SiJira size={26} color="#0052CC" />,
  },
];

function IntegrationOrbit() {
  return (
    <div className="integration-orbit" aria-hidden="true">
      {/* SVG orbit — large smooth elliptical path spanning the hero */}
      <svg
        className="orbit-lines"
        viewBox="0 0 1536 864"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        {/* Primary orbit arc */}
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
        {/* Secondary inner arc — dashed */}
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

      {/* Travelling particles */}
      <div className="orbit-particle" />
      <div className="orbit-particle" />
      <div className="orbit-particle" />

      {/* Real brand integration cards */}
      {integrations.map(({ name, className, icon }) => (
        <div
          key={name}
          className={`integration-card ${className} float-${name.toLowerCase()}`}
        >
          <span className="integration-icon">{icon}</span>
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

/* ====================================================================== */
/*  Cortex Dashboard (inside MacBook)                                     */
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
          <span className="preview-nav-active">
            <b>⌂ Home</b>
          </span>
          <span>
            <b>🔍 Search</b>
          </span>
          <span>
            <b>◈ Knowledge</b>
          </span>
          <span>
            <b>□ Projects</b>
          </span>
          <span>
            <b>✦ Decisions</b>
          </span>
          <span>
            <b>◆ Agents</b>
          </span>
          <span>
            <b>◌ Activity</b>
          </span>
        </div>
        <div className="preview-nav-bottom">
          <span>
            <b>⚙ Settings</b>
          </span>
        </div>
      </aside>

      <div className="preview-main">
        <div className="preview-topline">
          <span>
            <Search
              style={{
                width: 10,
                height: 10,
                display: "inline",
                verticalAlign: "middle",
                marginRight: 4,
                opacity: 0.45,
              }}
            />
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
            <strong>
              &ldquo;What changed across the organization this week?&rdquo;
            </strong>
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
/*  MacBook Preview — realistic MacBook Pro                                */
/* ====================================================================== */

function MacBookPreview() {
  return (
    <div
      className="product-preview-wrap"
      aria-label="Preview of the Cortex application"
    >
      {/* Contact shadow on the stone */}
      <div className="laptop-shadow" />

      <div className="laptop">
        {/* Display lid */}
        <div className="laptop-lid">
          {/* Camera notch */}
          <div className="laptop-camera">
            <div className="laptop-camera-lens" />
          </div>
          {/* Screen */}
          <div className="laptop-screen">
            <CortexDashboard />
          </div>
        </div>
        {/* Hinge */}
        <div className="laptop-hinge" />
        {/* Base / keyboard deck edge-on */}
        <div className="laptop-base">
          <div className="laptop-notch" />
        </div>
      </div>
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

      {/* Navbar */}
      <CortexNavbar />

      {/* Orbit + integration cards */}
      <IntegrationOrbit />

      {/* Hero content — centered text */}
      <div className="landing-hero">
        <div className="landing-eyebrow">
          <LogoMark className="h-4 w-4" /> Your organization&apos;s second
          brain
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
          <Link className="landing-cta-primary" to="/auth">
            Get started <ArrowRight />
          </Link>
        </div>
      </div>

      {/* MacBook — sits on the stone pedestal */}
      <MacBookPreview />
    </div>
  );
}
