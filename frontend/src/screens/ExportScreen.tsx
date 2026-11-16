import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { ExportResult, ImportRun } from "../types";

interface ExportScreenProps {
  run: ImportRun;
  onRunUpdate: (run: ImportRun) => void;
  onGoAudit: () => void;
}

type ArtifactGroup = "import_ready" | "excluded" | "reports";

interface ArtifactMeta {
  hint: string;
  group: ArtifactGroup;
}

const ARTIFACT_META: Record<string, ArtifactMeta> = {
  "companies_import_ready.csv": {
    group: "import_ready",
    hint: "Approved companies ready to import.",
  },
  "workers_import_ready.csv": {
    group: "import_ready",
    hint: "Approved workers with an import-ready company.",
  },
  "certifications_import_ready.csv": {
    group: "import_ready",
    hint: "Approved certifications with import-ready worker and company.",
  },
  "companies_excluded.csv": {
    group: "excluded",
    hint: "Companies left out of import, with reasons.",
  },
  "workers_excluded.csv": {
    group: "excluded",
    hint: "Workers left out (rejected, blocked parent, or not approved).",
  },
  "certifications_excluded.csv": {
    group: "excluded",
    hint: "Certifications left out, with reasons.",
  },
  "exception_report.json": {
    group: "reports",
    hint: "Issue counts by rule and severity (deterministic).",
  },
  "exception_report.md": {
    group: "reports",
    hint: "Readable exception summary; may include advisory AI narrative.",
  },
  "audit_log.json": {
    group: "reports",
    hint: "Full lineage: run, entities, issues, and decisions.",
  },
  "implementation_summary.md": {
    group: "reports",
    hint: "Customer-facing note from structured counts (AI or template).",
  },
};

const GROUP_ORDER: ArtifactGroup[] = ["import_ready", "excluded", "reports"];

const GROUP_LABELS: Record<ArtifactGroup, string> = {
  import_ready: "Import-ready",
  excluded: "Excluded",
  reports: "Reports & audit",
};

function artifactMeta(name: string): ArtifactMeta {
  if (ARTIFACT_META[name]) return ARTIFACT_META[name];
  if (name.endsWith("_import_ready.csv")) {
    return { group: "import_ready", hint: "Approved records ready for import." };
  }
  if (name.endsWith("_excluded.csv")) {
    return { group: "excluded", hint: "Excluded records with reasons." };
  }
  return { group: "reports", hint: "Export report." };
}

export function ExportScreen({ run, onRunUpdate, onGoAudit }: ExportScreenProps) {
  const [result, setResult] = useState<ExportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    if (!result || result.status !== "exported") return [];
    const buckets: Record<ArtifactGroup, string[]> = {
      import_ready: [],
      excluded: [],
      reports: [],
    };
    for (const name of result.artifacts) {
      buckets[artifactMeta(name).group].push(name);
    }
    return GROUP_ORDER.filter((g) => buckets[g].length > 0).map((group) => ({
      group,
      label: GROUP_LABELS[group],
      files: buckets[group],
    }));
  }, [result]);

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.export(run.id);
      setResult(res);
      const refreshed = await api.getRun(run.id);
      onRunUpdate(refreshed);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Generate package</h2>
      <p className="muted">
        Export is blocked while any entity is pending review. Approved records become
        import-ready files; excluded records are written with reasons.
      </p>
      {error && <div className="notice notice-error">{error}</div>}

      <div className="btn-row">
        <button className="primary" onClick={handleExport} disabled={busy}>
          {busy ? "Exporting..." : "Generate export"}
        </button>
        {result?.status === "exported" && (
          <button className="ghost" onClick={onGoAudit}>
            Go to audit
          </button>
        )}
      </div>

      {result?.status === "blocked" && (
        <div className="export-blockers">
          <div className="notice notice-warning">
            Export is blocked. Resolve the following before exporting:
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Type</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {result.blockers.map((b) => (
                  <tr key={b.entity_id}>
                    <td>{b.entity_id}</td>
                    <td>{b.entity_type}</td>
                    <td>{b.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result?.status === "exported" && (
        <div className="artifact-panel">
          <div className="artifact-panel-head">
            <span className="artifact-status">Export complete</span>
            <span className="muted">
              {result.artifacts.length} file
              {result.artifacts.length === 1 ? "" : "s"}
            </span>
          </div>
          {grouped.map((section) => (
            <div key={section.group} className="artifact-group">
              <div className="artifact-group-label">{section.label}</div>
              <div className="table-wrap">
                <table className="artifact-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>What it is</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {section.files.map((name) => (
                      <tr key={name}>
                        <td className="artifact-file">{name}</td>
                        <td className="artifact-desc">{artifactMeta(name).hint}</td>
                        <td className="artifact-action">
                          <a
                            className="link"
                            href={api.artifactUrl(run.id, name)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Download
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
