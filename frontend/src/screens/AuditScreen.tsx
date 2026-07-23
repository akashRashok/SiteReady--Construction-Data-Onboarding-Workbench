import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditTrace, EntityRecord, ImportRun } from "../types";

interface AuditScreenProps {
  run: ImportRun;
}

function entityLabel(e: EntityRecord): string {
  const d = e.data;
  if (e.entity_type === "company") return String(d.company_name ?? e.id);
  if (e.entity_type === "worker") return String(d.full_name ?? e.id);
  return `${String(d.cert_type ?? "cert")} ${String(d.cert_number ?? e.id)}`;
}

export function AuditScreen({ run }: AuditScreenProps) {
  const [entities, setEntities] = useState<EntityRecord[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [trace, setTrace] = useState<AuditTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getReview(run.id)
      .then((p) => setEntities(p.entities))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [run.id]);

  useEffect(() => {
    if (!selected) return;
    api
      .getAudit(run.id, selected)
      .then(setTrace)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [run.id, selected]);

  return (
    <div className="card">
      <h2>Field lineage</h2>
      <p className="muted">
        Select an entity to trace values back through transformations to the original source row.
      </p>
      {error && <div className="notice notice-error">{error}</div>}

      <div className="field">
        <label htmlFor="audit-entity">Entity</label>
        <select id="audit-entity" value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Select an entity...</option>
          {entities.map((e) => (
            <option key={e.id} value={e.id}>
              [{e.entity_type}] {entityLabel(e)}
            </option>
          ))}
        </select>
      </div>

      {trace && (
        <>
          <h3>Canonical record</h3>
          <pre
            style={{
              background: "var(--surface-muted)",
              padding: 12,
              borderRadius: 8,
              overflowX: "auto",
              fontSize: 12,
            }}
          >
            {JSON.stringify(trace.entity.data, null, 2)}
          </pre>

          <h3>Transformations</h3>
          {trace.transformations.length === 0 ? (
            <p className="muted">No transformations recorded.</p>
          ) : (
            <ul className="evidence-list">
              {trace.transformations.map((t) => (
                <li key={t.id}>
                  {t.field}: <span className="raw-value">{t.raw_value ?? "-"}</span> →{" "}
                  <span className="norm-value">{t.normalised_value ?? "-"}</span>
                </li>
              ))}
            </ul>
          )}

          <h3>Source rows</h3>
          {trace.source_rows.map((sr) => (
            <details key={sr.source_row_number}>
              <summary>Row {sr.source_row_number}</summary>
              <pre
                style={{
                  background: "var(--surface-muted)",
                  padding: 12,
                  borderRadius: 8,
                  overflowX: "auto",
                  fontSize: 12,
                }}
              >
                {JSON.stringify(sr.raw_data, null, 2)}
              </pre>
            </details>
          ))}

          {trace.decisions.length > 0 && (
            <>
              <h3>Decisions</h3>
              <ul className="evidence-list">
                {trace.decisions.map((d) => (
                  <li key={d.id}>
                    {d.decision}
                    {d.reason ? ` — ${d.reason}` : ""} ({new Date(d.created_at).toLocaleString()})
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
