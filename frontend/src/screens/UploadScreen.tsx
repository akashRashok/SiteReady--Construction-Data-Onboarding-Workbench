import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ImportRun } from "../types";

interface UploadScreenProps {
  run: ImportRun | null;
  onRunReady: (run: ImportRun) => void;
  onSelectRun: (run: ImportRun) => void;
}

export function UploadScreen({ run, onRunReady, onSelectRun }: UploadScreenProps) {
  const [name, setName] = useState("Construction onboarding demo");
  const [referenceDate, setReferenceDate] = useState("2025-06-15");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ImportRun[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const refreshRuns = () => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
  };

  useEffect(refreshRuns, []);

  const handleUpload = async () => {
    setError(null);
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Select a CSV file to upload.");
      return;
    }
    setBusy(true);
    try {
      const created = run ?? (await api.createRun(name, referenceDate));
      const updated = await api.uploadCsv(created.id, file);
      onRunReady(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteRun(id);
    refreshRuns();
  };

  return (
    <>
      <div className="card">
        <h2>Source file</h2>
        <p className="muted">
          Upload one denormalised construction onboarding CSV. Each row is a
          worker–certification pairing with redundant company details.
        </p>
        <div className="notice notice-warning" style={{ marginBottom: 16 }}>
          Independent demo. Synthetic data only. Do not upload real customer data.
        </div>

        <div className="field">
          <label htmlFor="run-name">Run name</label>
          <input
            id="run-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Acme onboarding batch"
          />
        </div>

        <div className="field">
          <label htmlFor="ref-date">
            Reference date (drives all expiry checks so counts are reproducible)
          </label>
          <input
            id="ref-date"
            type="date"
            value={referenceDate}
            onChange={(e) => setReferenceDate(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="csv-file">Source CSV</label>
          <input id="csv-file" type="file" accept=".csv,text/csv" ref={fileRef} />
        </div>

        {error && <div className="notice notice-error">{error}</div>}

        <div className="btn-row" style={{ marginTop: 12 }}>
          <button className="primary" onClick={handleUpload} disabled={busy}>
            {busy ? "Uploading..." : "Upload and profile"}
          </button>
        </div>
      </div>

      {runs.length > 0 && (
        <div className="card">
          <h3>Runs</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Reference date</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{r.status.replace(/_/g, " ")}</td>
                    <td>{r.reference_date}</td>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                    <td>
                      <div className="inline-actions">
                        <button className="ghost" onClick={() => onSelectRun(r)}>
                          Open
                        </button>
                        <button className="danger" onClick={() => handleDelete(r.id)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
