import { useRef, useState } from "react";
import {
  api,
  type SwmsEvidence,
  type SwmsExtractResult,
  type SwmsJobStep,
} from "../api/client";

const SUMMARY_FIELDS: { key: string; label: string }[] = [
  { key: "swms_number", label: "SWMS number" },
  { key: "document_title", label: "Document title" },
  { key: "contractor_name", label: "Contractor" },
  { key: "contractor_abn", label: "Contractor ABN" },
  { key: "project_name", label: "Project" },
  { key: "site_address", label: "Site address" },
  { key: "activity", label: "Activity" },
  { key: "date_prepared", label: "Date prepared" },
  { key: "review_date", label: "Review date" },
  { key: "responsible_person", label: "Responsible person" },
];

const LIST_SECTIONS: { key: string; label: string }[] = [
  { key: "high_risk_categories", label: "High-risk categories" },
  { key: "ppe_required", label: "PPE required" },
  { key: "plant_and_equipment", label: "Plant and equipment" },
  { key: "required_competencies_licences", label: "Competencies / licences" },
];

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.join("; ") : "—";
  return String(value);
}

function fieldValue(
  fields: SwmsExtractResult["fields"],
  evidence: Record<string, SwmsEvidence>,
  key: string,
): string {
  const fromField = fields[key];
  if (fromField !== null && fromField !== undefined && fromField !== "") {
    return displayValue(fromField);
  }
  const fromEvidence = evidence[key]?.value;
  if (
    fromEvidence !== null &&
    fromEvidence !== undefined &&
    fromEvidence !== "" &&
    !Array.isArray(fromEvidence)
  ) {
    return String(fromEvidence);
  }
  return "—";
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function asJobSteps(value: unknown): SwmsJobStep[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is SwmsJobStep =>
      typeof item === "object" &&
      item !== null &&
      "step" in item &&
      "hazard" in item,
  );
}

export function SwmsScreen() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [result, setResult] = useState<SwmsExtractResult | null>(null);

  const handleExtract = async () => {
    setError(null);
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Select a SWMS PDF to extract.");
      return;
    }
    setSelectedName(file.name);
    setBusy(true);
    try {
      const extracted = await api.extractSwms(file);
      setResult(extracted);
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "swms_extract.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const abnEvidence = result?.evidence.contractor_abn;
  const jobSteps = asJobSteps(result?.fields.job_steps);
  const populatedCount = result
    ? SUMMARY_FIELDS.filter(
        ({ key }) => fieldValue(result.fields, result.evidence, key) !== "—",
      ).length
    : 0;

  return (
    <>
      <div className="card">
        <h2>Extract SWMS PDF</h2>
        <p className="muted">
          Secondary flow: upload one machine-readable Safe Work Method Statement.
          Labelled fields and the job-steps table are extracted deterministically
          with source evidence retained. Use{" "}
          <code>fixtures/SWMS_Roof_Sheeting_Working_at_Heights.pdf</code>.
        </p>
        <div className="notice notice-warning">
          Independent demo. Synthetic data only. Do not upload real customer documents.
          Scanned/image-only PDFs will not yield values.
        </div>

        <div className="field">
          <label htmlFor="swms-file">SWMS PDF</label>
          <input
            id="swms-file"
            type="file"
            accept=".pdf,application/pdf"
            ref={fileRef}
            onChange={(e) =>
              setSelectedName(e.target.files?.[0]?.name ?? null)
            }
          />
          {selectedName && (
            <p className="muted" style={{ marginTop: 6 }}>
              Selected: {selectedName}
            </p>
          )}
        </div>

        {error && <div className="notice notice-error">{error}</div>}

        <div className="btn-row">
          <button
            type="button"
            className="primary"
            onClick={handleExtract}
            disabled={busy}
          >
            {busy ? "Extracting…" : "Extract"}
          </button>
          {result && (
            <button type="button" className="ghost" onClick={handleDownloadJson}>
              Download swms_extract.json
            </button>
          )}
        </div>
      </div>

      {result && (
        <>
          <div className="card">
            <h2>Document fields</h2>
            <p className="muted">
              Source: <code>{result.source_file}</code>
              {" · "}
              {populatedCount} of {SUMMARY_FIELDS.length} fields
              {" · "}
              {jobSteps.length} job step{jobSteps.length === 1 ? "" : "s"}
              {result.llm_used ? " · LLM assisted" : " · Deterministic only"}
            </p>
            {result.warning && (
              <div className="notice notice-warning">{result.warning}</div>
            )}
            {abnEvidence?.validation_error && (
              <div className="notice notice-warning">
                Contractor ABN validation: {abnEvidence.validation_error}
                {abnEvidence.raw_value
                  ? ` (raw: ${abnEvidence.raw_value})`
                  : ""}
              </div>
            )}
            <div className="swms-field-list">
              {SUMMARY_FIELDS.map(({ key, label }) => {
                const evidence = result.evidence[key];
                const value = fieldValue(result.fields, result.evidence, key);
                const page =
                  evidence?.page !== null && evidence?.page !== undefined
                    ? `p.${evidence.page}`
                    : null;
                return (
                  <div key={key} className="swms-field-row">
                    <div className="swms-field-label">{label}</div>
                    <div
                      className={
                        value === "—"
                          ? "swms-field-value is-empty"
                          : "swms-field-value"
                      }
                    >
                      {value}
                    </div>
                    <div className="swms-evidence">
                      {evidence?.source_text ?? "—"}
                      {page ? ` · ${page}` : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <h2>Lists</h2>
            <div className="swms-list-grid">
              {LIST_SECTIONS.map(({ key, label }) => {
                const items = asStringList(result.fields[key]);
                const evidence = result.evidence[key];
                return (
                  <section key={key} className="swms-list-section">
                    <h3>
                      {label}{" "}
                      <span className="muted">({items.length})</span>
                    </h3>
                    {items.length === 0 ? (
                      <p className="muted">None found</p>
                    ) : (
                      <ul>
                        {items.map((item, index) => (
                          <li key={`${key}-${index}`}>{item}</li>
                        ))}
                      </ul>
                    )}
                    {evidence?.source_text &&
                      evidence.source_text !== "not found" && (
                        <p className="swms-evidence muted">
                          {evidence.source_text}
                        </p>
                      )}
                  </section>
                );
              })}
            </div>
          </div>

          <div className="card">
            <h2>Job steps</h2>
            {jobSteps.length === 0 ? (
              <p className="muted">No job-steps table found in the PDF.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Step</th>
                      <th>Hazard</th>
                      <th>Risk rating</th>
                      <th>Control measures</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobSteps.map((row, index) => (
                      <tr key={`${row.step}-${index}`}>
                        <td>{row.step || "—"}</td>
                        <td>{row.hazard || "—"}</td>
                        <td>{row.risk_rating || "—"}</td>
                        <td>{row.control_measures || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
