import { useEffect, useState } from "react";
import { api, type HealthInfo } from "./api/client";
import { SideNav, TopBar } from "./components/Shell";
import { LlmSettingsPanel } from "./components/LlmSettingsPanel";
import type { ImportRun } from "./types";
import { UploadScreen } from "./screens/UploadScreen";
import { MappingScreen } from "./screens/MappingScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { ExportScreen } from "./screens/ExportScreen";
import { AuditScreen } from "./screens/AuditScreen";

export type Step = "upload" | "mapping" | "review" | "export" | "audit";

const STEPS: { id: Step; label: string; short: string }[] = [
  { id: "upload", label: "Upload", short: "Upload" },
  { id: "mapping", label: "Mapping", short: "Mapping" },
  { id: "review", label: "Review", short: "Review" },
  { id: "export", label: "Export", short: "Export" },
  { id: "audit", label: "Audit", short: "Audit" },
];

const PAGE_COPY: Record<Step, { title: string; crumb: string }> = {
  upload: { title: "Upload source data", crumb: "Upload" },
  mapping: { title: "Confirm column mappings", crumb: "Mapping" },
  review: { title: "Review entities", crumb: "Review" },
  export: { title: "Export artifacts", crumb: "Export" },
  audit: { title: "Audit trail", crumb: "Audit" },
};

function stepIndex(step: Step): number {
  return STEPS.findIndex((s) => s.id === step);
}

export function App() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [run, setRun] = useState<ImportRun | null>(null);
  const [step, setStep] = useState<Step>("upload");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const refreshHealth = () => {
    api.health().then(setHealth).catch(() => setHealth(null));
  };

  useEffect(() => {
    refreshHealth();
  }, []);

  const reachable = (target: Step): boolean => {
    if (!run) return target === "upload";
    const idx = stepIndex(target);
    const order: Record<ImportRun["status"], number> = {
      created: 0,
      ingested: 1,
      mapping_pending: 1,
      processing: 2,
      review_pending: 2,
      approved: 3,
      exported: 4,
      failed: 0,
    };
    return idx <= Math.max(order[run.status], 0) + 1;
  };

  const page = PAGE_COPY[step];

  return (
    <div className="app-shell">
      <TopBar
        health={health}
        run={run}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="shell-body">
        <SideNav
          step={step}
          steps={STEPS}
          reachable={reachable}
          onNavigate={setStep}
        />
        <div className="main-column">
          <div className="page-header">
            <div className="breadcrumbs">
              <span>Onboarding Workbench</span>
              <span className="crumb-sep">/</span>
              <span>{page.crumb}</span>
              {run && (
                <>
                  <span className="crumb-sep">/</span>
                  <span className="crumb-current">{run.name}</span>
                </>
              )}
            </div>
            <h1 className="page-title">{page.title}</h1>
          </div>

          <main className="page-content">
            {step === "upload" && (
              <UploadScreen
                run={run}
                onRunReady={(r) => {
                  setRun(r);
                  setStep("mapping");
                }}
                onSelectRun={setRun}
              />
            )}
            {step === "mapping" && run && (
              <MappingScreen
                run={run}
                onConfirmed={(r) => {
                  setRun(r);
                  setStep("review");
                }}
              />
            )}
            {step === "review" && run && (
              <ReviewScreen
                run={run}
                onRunUpdate={setRun}
                onGoExport={() => setStep("export")}
              />
            )}
            {step === "export" && run && (
              <ExportScreen
                run={run}
                onRunUpdate={setRun}
                onGoAudit={() => setStep("audit")}
              />
            )}
            {step === "audit" && run && <AuditScreen run={run} />}
          </main>
        </div>
      </div>

      <LlmSettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={refreshHealth}
      />
    </div>
  );
}
