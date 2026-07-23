import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ConfidencePill } from "../components/Pills";
import type { ColumnMapping, EntityType, ImportRun } from "../types";

interface MappingScreenProps {
  run: ImportRun;
  onConfirmed: (run: ImportRun) => void;
}

const IGNORE_VALUE = "__ignore__";

const TARGETS: { entity: EntityType; field: string }[] = [
  { entity: "company", field: "company_name" },
  { entity: "company", field: "abn" },
  { entity: "company", field: "role" },
  { entity: "worker", field: "full_name" },
  { entity: "worker", field: "trade" },
  { entity: "worker", field: "email" },
  { entity: "worker", field: "phone" },
  { entity: "certification", field: "cert_type" },
  { entity: "certification", field: "cert_number" },
  { entity: "certification", field: "issue_date" },
  { entity: "certification", field: "expiry_date" },
];

function targetKey(entity: EntityType | null, field: string | null): string {
  return entity && field ? `${entity}.${field}` : "";
}

function initialChoice(item: ColumnMapping): string {
  const mapped = targetKey(item.target_entity, item.target_field);
  if (mapped) return mapped;
  // Low-confidence / unmapped rows start blank so the user must explicitly
  // pick a target or "Ignore column".
  if (item.confidence === "low" || item.method === "unmapped") return "";
  return IGNORE_VALUE;
}

export function MappingScreen({ run, onConfirmed }: MappingScreenProps) {
  const [mappings, setMappings] = useState<ColumnMapping[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getMappings(run.id)
      .then((m) => {
        setMappings(m);
        const initial: Record<string, string> = {};
        for (const item of m) {
          initial[item.source_column] = initialChoice(item);
        }
        setChoices(initial);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [run.id]);

  const needsChoice = mappings.some((m) => {
    if (m.confidence !== "low" && m.method !== "unmapped") return false;
    const choice = choices[m.source_column];
    return !choice;
  });

  const handleConfirm = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = mappings.map((m) => {
        const value = choices[m.source_column] ?? "";
        const ignored = !value || value === IGNORE_VALUE;
        if (ignored) {
          return {
            source_column: m.source_column,
            target_entity: null,
            target_field: null,
            method: "unmapped" as const,
            confirmed: true,
          };
        }
        const [entity, field] = value.split(".");
        return {
          source_column: m.source_column,
          target_entity: entity as EntityType,
          target_field: field,
          confirmed: true,
        };
      });
      await api.confirmMappings(run.id, payload);
      const processed = await api.process(run.id);
      onConfirmed(processed);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="card spinner">Profiling columns...</div>;

  return (
    <div className="card">
      <h2>Proposed mappings</h2>
      <p className="muted">
        Low-confidence columns must be mapped or ignored before processing continues.
      </p>
      {error && <div className="notice notice-error">{error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source column</th>
              <th>Method</th>
              <th>Confidence</th>
              <th>Sample values</th>
              <th>Target</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => {
              const choice = choices[m.source_column] ?? "";
              const needsAttention =
                (m.confidence === "low" || m.method === "unmapped") && !choice;
              return (
                <tr key={m.source_column}>
                  <td>
                    <strong>{m.source_column}</strong>
                  </td>
                  <td>{m.method.replace(/_/g, " ")}</td>
                  <td>
                    <ConfidencePill level={m.confidence} />
                  </td>
                  <td className="muted">{m.sample_values.join(", ") || "-"}</td>
                  <td>
                    <select
                      value={choice}
                      onChange={(e) =>
                        setChoices((prev) => ({
                          ...prev,
                          [m.source_column]: e.target.value,
                        }))
                      }
                      style={
                        needsAttention ? { borderColor: "var(--error)" } : undefined
                      }
                    >
                      <option value="" disabled>
                        Select mapping…
                      </option>
                      <option value={IGNORE_VALUE}>Ignore column</option>
                      {TARGETS.map((t) => (
                        <option
                          key={`${t.entity}.${t.field}`}
                          value={`${t.entity}.${t.field}`}
                        >
                          {t.entity}.{t.field}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {needsChoice && (
        <div className="notice notice-warning" style={{ marginTop: 12 }}>
          Confirm every low-confidence mapping (pick a target or Ignore column) before
          continuing.
        </div>
      )}

      <div className="btn-row" style={{ marginTop: 16 }}>
        <button className="primary" onClick={handleConfirm} disabled={busy || needsChoice}>
          {busy ? "Processing..." : "Confirm mappings and process"}
        </button>
      </div>
    </div>
  );
}
