import {
  ArrowRight,
  ChevronDown,
  CircleDot,
  Github,
  GitBranch,
  HardDrive,
  Layers3,
  Mail,
  Menu,
  MessageSquare,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "@/components/brand/Logo";

type Integration = {
  name: string;
  className: string;
  icon: typeof Github;
};

const integrations: Integration[] = [
  { name: "Slack", className: "orbit-slack", icon: MessageSquare },
  { name: "Gmail", className: "orbit-gmail", icon: Mail },
  { name: "GitHub", className: "orbit-github", icon: Github },
  { name: "Drive", className: "orbit-drive", icon: HardDrive },
  { name: "Jira", className: "orbit-jira", icon: GitBranch },
  { name: "Confluence", className: "orbit-confluence", icon: Layers3 },
  { name: "Linear", className: "orbit-linear", icon: CircleDot },
];

function IntegrationOrbit() {
  return (
    <div className="integration-orbit" aria-hidden="true">
      <svg className="orbit-lines" viewBox="0 0 1100 560" fill="none">
        <path
          d="M103 382C190 120 349 36 550 36c201 0 360 84 447 346"
          stroke="url(#orbit-gradient)"
          strokeWidth="1.15"
        />
        <path
          d="M48 464C213 280 359 226 550 226s337 54 502 238"
          stroke="url(#orbit-gradient-secondary)"
          strokeWidth="0.8"
          strokeDasharray="2 8"
        />
        <defs>
          <linearGradient id="orbit-gradient" x1="130" y1="94" x2="948" y2="425">
            <stop stopColor="#A9C9D8" stopOpacity="0" />
            <stop offset=".28" stopColor="#6E9B92" stopOpacity=".55" />
            <stop offset=".7" stopColor="#A9C9D8" stopOpacity=".55" />
            <stop offset="1" stopColor="#A9C9D8" stopOpacity="0" />
          </linearGradient>
          <linearGradient
            id="orbit-gradient-secondary"
            x1="90"
            y1="380"
            x2="1010"
            y2="380"
          >
            <stop stopColor="#A9C9D8" stopOpacity="0" />
            <stop offset=".5" stopColor="#A9C9D8" stopOpacity=".38" />
            <stop offset="1" stopColor="#A9C9D8" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
      {integrations.map(({ name, className, icon: Icon }) => (
        <div key={name} className={`integration-card ${className}`}>
          <span className={`integration-icon integration-icon-${name.toLowerCase()}`}>
            <Icon />
          </span>
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

function ProductPreview() {
  return (
    <div className="product-preview-wrap" aria-label="Preview of the Cortex application">
      <div className="laptop">
        <div className="laptop-camera" />
        <div className="laptop-screen">
          <aside className="preview-sidebar">
            <div className="preview-brand">
              <LogoMark className="h-4 w-4" />
              <strong>Cortex</strong>
            </div>
            <div className="preview-nav-group">
              <span className="preview-nav-active">⌂ <b>Home</b></span>
              <span>◈ <b>Knowledge</b></span>
              <span>□ <b>Projects</b></span>
              <span>✦ <b>Agents</b></span>
              <span>◌ <b>Activity</b></span>
            </div>
            <div className="preview-nav-bottom">
              <span>⚙ <b>Settings</b></span>
              <span className="preview-user"><i>PR</i> Priya Raman</span>
            </div>
          </aside>
          <div className="preview-main">
            <div className="preview-topline">
              <span>Monday, August 17</span>
              <span className="preview-top-avatar">PR</span>
            </div>
            <div className="preview-greeting">
              <p>Good morning, Priya <span>👋</span></p>
              <h3>Here&apos;s what&apos;s happening across your organization.</h3>
            </div>
            <div className="preview-grid">
              <div className="preview-panel preview-ask">
                <span className="preview-panel-kicker">Ask Cortex anything</span>
                <strong>What changed this week?</strong>
                <span className="preview-search">Search your context <ArrowRight /></span>
              </div>
              <div className="preview-panel">
                <span className="preview-panel-kicker">Recent activity</span>
                <div className="preview-activity"><i className="activity-dot sage" /><span>Product sync notes added</span><small>2m</small></div>
                <div className="preview-activity"><i className="activity-dot blue" /><span>Decision captured in Platform</span><small>1h</small></div>
                <div className="preview-activity"><i className="activity-dot gold" /><span>Agent context refreshed</span><small>3h</small></div>
              </div>
              <div className="preview-panel preview-projects">
                <span className="preview-panel-kicker">Projects</span>
                <strong>Across your organization</strong>
                <div className="preview-project-line"><span>Platform migration</span><b>Active</b></div>
                <div className="preview-project-line"><span>Q3 planning</span><b>On track</b></div>
              </div>
            </div>
          </div>
        </div>
        <div className="laptop-base">
          <span />
        </div>
      </div>
    </div>
  );
}

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="landing-page">
      <div className="landing-landscape" />
      <div className="landing-atmosphere" />

      <header className="landing-nav" aria-label="Primary navigation">
        <Link to="/" className="landing-wordmark" aria-label="Cortex home">
          <LogoMark className="h-5 w-5" />
          <span>CORTEX</span>
        </Link>
        <nav className="landing-links">
          <a href="#product">Product <ChevronDown /></a>
          <a href="#solutions">Solutions <ChevronDown /></a>
          <a href="#resources">Resources <ChevronDown /></a>
          <a href="#pricing">Pricing</a>
          <a href="#company">Company <ChevronDown /></a>
        </nav>
        <div className="landing-actions">
          <Link to="/auth" className="landing-login">Log in</Link>
          <a className="landing-demo" href="mailto:hello@cortex.ai">Book a demo <ArrowRight /></a>
        </div>
        <button
          className="landing-menu"
          type="button"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
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
            <a className="mobile-menu-demo" href="mailto:hello@cortex.ai">Book a demo <ArrowRight /></a>
          </div>
        ) : null}
      </header>

      <main className="landing-main">
        <IntegrationOrbit />
        <div className="landing-copy">
          <div className="landing-eyebrow"><LogoMark className="h-4 w-4" /> Your organization&apos;s second brain</div>
          <h1>
            <span>Unify. Understand.</span>
            <em>Unlock Impact.</em>
          </h1>
          <p>
            Cortex connects your conversations, documents, code, issues, and decisions into a living context layer that your teams and AI agents can use — anywhere.
          </p>
          <div className="landing-ctas">
            <a className="landing-cta-primary" href="mailto:hello@cortex.ai">Book a demo <ArrowRight /></a>
            <Link className="landing-cta-secondary" to="/auth">Explore Cortex <ArrowRight /></Link>
          </div>
        </div>
        <ProductPreview />
      </main>
    </div>
  );
}