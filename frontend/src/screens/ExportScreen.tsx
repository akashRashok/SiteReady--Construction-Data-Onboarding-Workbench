import { useState } from "react";
import { api } from "../api/client";
import type { ExportResult, ImportRun } from "../types";

interface ExportScreenProps {
  run: ImportRun;
  onRunUpdate: (run: ImportRun) => void;
  onGoAudit: () => void;
}

export function ExportScreen({ run, onRunUpdate, onGoAudit }: ExportScreenProps) {
  const [result, setResult] = useState<ExportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        <div style={{ marginTop: 16 }}>
          <div className="notice notice-warning">
            Export is blocked. Resolve the following before exporting:
          </div>
          <div className="table-wrap" style={{ marginTop: 8 }}>
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
        <div style={{ marginTop: 16 }}>
          <div className="notice notice-info">Export complete. Generated artifacts:</div>
          <ul>
            {result.artifacts.map((name) => (
              <li key={name}>
                <a className="link" href={api.artifactUrl(run.id, name)} target="_blank" rel="noreferrer">
                  {name}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
