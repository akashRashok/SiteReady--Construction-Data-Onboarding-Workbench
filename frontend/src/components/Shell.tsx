import type { HealthInfo } from "../api/client";
import type { ImportRun } from "../types";
import type { Step } from "../App";

interface TopBarProps {
  health: HealthInfo | null;
  run: ImportRun | null;
  onOpenSettings: () => void;
}

export function TopBar({ health, run, onOpenSettings }: TopBarProps) {
  const provider = run?.llm_provider ?? health?.llm_provider ?? "—";
  const model = run?.llm_model ?? health?.llm_model ?? "—";
  const hosted = health?.llm_hosted === true;
  const warning = health?.llm_warning ?? null;

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="brand-mark" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M4 6h16v2H4V6zm0 5h10v2H4v-2zm0 5h16v2H4v-2z" fill="#1a73e8" />
            <path d="M16 9l4 3-4 3V9z" fill="#34a853" />
          </svg>
        </span>
        <div className="brand-text">
          <span className="brand-product">Onboarding Workbench</span>
          <span className="brand-sub">Construction data migration</span>
        </div>
      </div>

      <div className="topbar-center">
        <button type="button" className="project-selector" disabled title="Current run">
          <span className="project-label">Run</span>
          <span className="project-name">{run?.name ?? "No run selected"}</span>
          {run && <span className="project-status">{run.status.replace(/_/g, " ")}</span>}
        </button>
      </div>

      <div className="topbar-actions">
        <button
          type="button"
          className={`model-chip ${hosted ? "is-hosted" : "is-local"}`}
          title={
            hosted
              ? warning ?? "Hosted provider — click to edit connectors"
              : "Local model — click to edit connectors"
          }
          onClick={onOpenSettings}
          aria-label={`Model settings: ${provider} ${model}`}
        >
          <span className={`model-chip-dot ${hosted ? "dot-hosted" : "dot-local"}`} />
          <span className="model-chip-text">
            <span className="model-chip-provider">{provider}</span>
            <span className="model-chip-sep">/</span>
            <span className="model-chip-model">{model}</span>
          </span>
          <span className="model-chip-caret" aria-hidden="true">
            ▾
          </span>
        </button>
        <span className="demo-chip" title="Independent demo. Synthetic data.">
          Demo data
        </span>
      </div>
    </header>
  );
}

interface SideNavProps {
  step: Step;
  steps: { id: Step; label: string; short: string }[];
  reachable: (target: Step) => boolean;
  onNavigate: (step: Step) => void;
}

export function SideNav({ step, steps, reachable, onNavigate }: SideNavProps) {
  return (
    <aside className="sidenav" aria-label="Workflow">
      <div className="sidenav-section-label">Workflow</div>
      <nav className="sidenav-nav">
        {steps.map((s, index) => {
          const active = step === s.id;
          const enabled = reachable(s.id);
          return (
            <button
              key={s.id}
              type="button"
              className={`sidenav-item ${active ? "active" : ""}`}
              disabled={!enabled}
              onClick={() => onNavigate(s.id)}
            >
              <span className="sidenav-index">{index + 1}</span>
              <span className="sidenav-label">{s.short}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidenav-footer">
        <div className="sidenav-footer-title">Disclaimer</div>
        <p>Independent demo. Synthetic data. Not affiliated with any commercial product.</p>
      </div>
    </aside>
  );
}
