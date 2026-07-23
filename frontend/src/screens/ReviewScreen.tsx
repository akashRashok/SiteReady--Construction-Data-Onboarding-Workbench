import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { SeverityPill, StatusPill } from "../components/Pills";
import type {
  EntityRecord,
  EntityType,
  FuzzyCandidate,
  ImportRun,
  Issue,
  ReviewPayload,
} from "../types";

interface ReviewScreenProps {
  run: ImportRun;
  onRunUpdate: (run: ImportRun) => void;
  onGoExport: () => void;
}

const ENTITY_ORDER: EntityType[] = ["company", "worker", "certification"];

type StatusFilter = "all" | "pending_review" | "with_errors" | "approved" | "rejected";

function entityLabel(e: EntityRecord): string {
  const d = e.data;
  if (e.entity_type === "company") return String(d.company_name ?? e.id);
  if (e.entity_type === "worker") return String(d.full_name ?? e.id);
  return `${String(d.cert_type ?? "cert")} ${String(d.cert_number ?? e.id)}`;
}

function entitySubtitle(e: EntityRecord): string {
  const d = e.data;
  if (e.entity_type === "company") {
    return [d.role, d.abn ? `ABN ${d.abn}` : null].filter(Boolean).join(" · ") || e.id;
  }
  if (e.entity_type === "worker") {
    return [d.trade, d.email, d.phone].filter(Boolean).join(" · ") || e.id;
  }
  return [d.cert_number, d.issue_date, d.expiry_date].filter(Boolean).join(" · ") || e.id;
}

function transformTitle(issue: Issue): string {
  if (issue.rule_id === "exact_duplicate_collapse") {
    return "Exact duplicate rows collapsed";
  }
  if (issue.rule_id.startsWith("transform_")) {
    const field = issue.field ?? "value";
    return `Normalised ${field.replace(/_/g, " ")}`;
  }
  return issue.message || issue.rule_id.replace(/_/g, " ");
}

function displayValue(value: string | null | undefined, empty = "—"): string {
  if (value === null || value === undefined || value === "") return empty;
  return value;
}

export function ReviewScreen({ run, onRunUpdate, onGoExport }: ReviewScreenProps) {
  const [payload, setPayload] = useState<ReviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [entityType, setEntityType] = useState<EntityType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending_review");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .getReview(run.id)
      .then(setPayload)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [run.id]);

  useEffect(load, [load]);

  const issuesByEntity = useMemo(() => {
    const map: Record<string, Issue[]> = {};
    for (const issue of payload?.issues ?? []) {
      if (!issue.entity_id) continue;
      (map[issue.entity_id] ??= []).push(issue);
    }
    return map;
  }, [payload]);

  const approvableIds = useMemo(() => {
    if (!payload) return [];
    return payload.entities
      .filter((e) => {
        if (e.review_status !== "pending_review") return false;
        const hasError = (issuesByEntity[e.id] ?? []).some(
          (i) => i.severity === "error",
        );
        return !hasError;
      })
      .map((e) => e.id);
  }, [payload, issuesByEntity]);

  const decide = async (
    entityId: string,
    decision: string,
    relatedEntityId?: string,
  ) => {
    setError(null);
    let reason: string | null = null;
    if (decision === "override") {
      reason = window.prompt("Enter a reason for overriding this error (required):");
      if (!reason) return;
    }
    setBusyId(entityId);
    try {
      await api.decide(run.id, {
        entity_id: entityId,
        decision,
        reason,
        related_entity_id: relatedEntityId ?? null,
      });
      const refreshed = await api.getRun(run.id);
      onRunUpdate(refreshed);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const approveAllEligible = async () => {
    if (!payload || approvableIds.length === 0) return;
    const confirmed = window.confirm(
      `Approve ${approvableIds.length} pending entit${
        approvableIds.length === 1 ? "y" : "ies"
      } with no errors?\n\nRecords with errors still need Override (with a reason).`,
    );
    if (!confirmed) return;
    setError(null);
    setBulkBusy(true);
    try {
      await api.decideBatch(
        run.id,
        approvableIds.map((entity_id) => ({
          entity_id,
          decision: "approve",
          reason: null,
          related_entity_id: null,
        })),
      );
      const refreshed = await api.getRun(run.id);
      onRunUpdate(refreshed);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBulkBusy(false);
    }
  };

  const filteredEntities = useMemo(() => {
    if (!payload) return [];
    const q = query.trim().toLowerCase();
    return payload.entities.filter((e) => {
      if (entityType !== "all" && e.entity_type !== entityType) return false;
      const issues = issuesByEntity[e.id] ?? [];
      const hasError = issues.some((i) => i.severity === "error");
      if (statusFilter === "pending_review" && e.review_status !== "pending_review") {
        return false;
      }
      if (statusFilter === "with_errors" && !hasError) return false;
      if (statusFilter === "approved" && !e.review_status.startsWith("approved")) {
        return false;
      }
      if (statusFilter === "rejected" && e.review_status !== "rejected") return false;
      if (!q) return true;
      return (
        entityLabel(e).toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        entitySubtitle(e).toLowerCase().includes(q)
      );
    });
  }, [payload, entityType, statusFilter, query, issuesByEntity]);

  if (loading) return <div className="card spinner">Loading review data…</div>;
  if (!payload) return <div className="card notice notice-error">{error ?? "No data"}</div>;

  const pendingCount = payload.entities.filter(
    (e) => e.review_status === "pending_review",
  ).length;
  const errorCount = payload.issues.filter((i) => i.severity === "error").length;
  const warningCount = payload.issues.filter((i) => i.severity === "warning").length;

  return (
    <div className="review-layout">
      <div className="review-toolbar card">
        <div className="review-metrics">
          <Metric label="Entities" value={payload.entities.length} />
          <Metric label="Errors" value={errorCount} tone="error" />
          <Metric label="Warnings" value={warningCount} tone="warning" />
          <Metric label="Exact dupes" value={payload.exact_duplicates.length} />
          <Metric label="Fuzzy" value={payload.fuzzy_candidates.length} />
          <Metric label="Pending" value={pendingCount} tone="warning" />
        </div>
        <div className="review-toolbar-actions">
          <button
            type="button"
            className="ghost"
            onClick={approveAllEligible}
            disabled={bulkBusy || busyId !== null || approvableIds.length === 0}
            title={
              approvableIds.length === 0
                ? "No pending entities without errors"
                : `Approve ${approvableIds.length} pending entities without errors`
            }
          >
            {bulkBusy
              ? "Approving…"
              : `Approve all${approvableIds.length > 0 ? ` (${approvableIds.length})` : ""}`}
          </button>
          <button
            className="primary"
            onClick={onGoExport}
            disabled={pendingCount > 0 || bulkBusy}
            title={
              pendingCount > 0
                ? `${pendingCount} entities still pending review`
                : "Continue to export"
            }
          >
            Continue to export
          </button>
        </div>
      </div>

      {error && <div className="notice notice-error">{error}</div>}

      <div className="card review-table-card">
        <div className="review-filters">
          <div className="tab-row" role="tablist" aria-label="Entity type">
            <button
              type="button"
              className={`tab ${entityType === "all" ? "active" : ""}`}
              onClick={() => setEntityType("all")}
            >
              All
            </button>
            {ENTITY_ORDER.map((type) => (
              <button
                key={type}
                type="button"
                className={`tab ${entityType === type ? "active" : ""}`}
                onClick={() => setEntityType(type)}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}s
              </button>
            ))}
          </div>

          <div className="review-filter-controls">
            <div className="filter-chip-row" role="group" aria-label="Status filter">
              {(
                [
                  ["all", "All"],
                  ["pending_review", "Pending"],
                  ["with_errors", "Errors"],
                  ["approved", "Approved"],
                  ["rejected", "Rejected"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`filter-chip ${statusFilter === value ? "active" : ""}`}
                  onClick={() => setStatusFilter(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="search-field">
              <span className="search-icon" aria-hidden="true">
                ⌕
              </span>
              <input
                type="search"
                placeholder="Filter by name, id, trade…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search entities"
              />
            </label>
          </div>
        </div>

        <div className="table-wrap review-table-wrap">
          <table className="review-table">
            <thead>
              <tr>
                <th style={{ width: 36 }} />
                <th>Record</th>
                <th>Type</th>
                <th>Source rows</th>
                <th>Issues</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntities.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-row">
                    No entities match this filter.
                  </td>
                </tr>
              )}
              {filteredEntities.map((entity) => {
                const issues = issuesByEntity[entity.id] ?? [];
                const problems = issues.filter((i) => i.severity !== "info");
                const transforms = issues.filter((i) => i.severity === "info");
                const errorN = problems.filter((i) => i.severity === "error").length;
                const warnN = problems.filter((i) => i.severity === "warning").length;
                const expanded = expandedId === entity.id;
                const hasError = errorN > 0;
                return (
                  <Fragment key={entity.id}>
                    <tr className={`review-row ${expanded ? "expanded" : ""}`}>
                      <td>
                        <button
                          type="button"
                          className="icon-btn"
                          aria-expanded={expanded}
                          aria-label={expanded ? "Collapse details" : "Expand details"}
                          onClick={() =>
                            setExpandedId(expanded ? null : entity.id)
                          }
                        >
                          {expanded ? "▾" : "▸"}
                        </button>
                      </td>
                      <td>
                        <div className="record-primary">{entityLabel(entity)}</div>
                        <div className="record-secondary">{entitySubtitle(entity)}</div>
                      </td>
                      <td className="mono-cell">{entity.entity_type}</td>
                      <td className="mono-cell">{entity.source_rows.join(", ")}</td>
                      <td>
                        <div className="issue-counts">
                          {errorN > 0 && (
                            <span className="count-chip count-error">{errorN} error</span>
                          )}
                          {warnN > 0 && (
                            <span className="count-chip count-warning">{warnN} warn</span>
                          )}
                          {transforms.length > 0 && (
                            <span className="count-chip count-info">
                              {transforms.length} change
                              {transforms.length === 1 ? "" : "s"}
                            </span>
                          )}
                          {errorN === 0 && warnN === 0 && transforms.length === 0 && (
                            <span className="muted">None</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <StatusPill status={entity.review_status} />
                      </td>
                      <td>
                        <div className="inline-actions">
                          <button
                            className="primary"
                            disabled={
                              bulkBusy || busyId === entity.id || hasError
                            }
                            onClick={() => decide(entity.id, "approve")}
                            title={
                              hasError
                                ? "Resolve errors with Override first"
                                : "Approve for import"
                            }
                          >
                            Approve
                          </button>
                          {hasError && (
                            <button
                              className="ghost"
                              disabled={bulkBusy || busyId === entity.id}
                              onClick={() => decide(entity.id, "override")}
                            >
                              Override
                            </button>
                          )}
                          <button
                            className="danger"
                            disabled={bulkBusy || busyId === entity.id}
                            onClick={() => decide(entity.id, "reject")}
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="review-detail-row">
                        <td colSpan={7}>
                          <EntityDetail
                            entity={entity}
                            problems={problems}
                            transforms={transforms}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {payload.fuzzy_candidates.length > 0 && (
        <FuzzySection
          candidates={payload.fuzzy_candidates}
          entities={payload.entities}
          busyId={busyId}
          onDecide={decide}
        />
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "error" | "warning";
}) {
  return (
    <div className={`metric ${tone ? `metric-${tone}` : ""}`}>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function EntityDetail({
  entity,
  problems,
  transforms,
}: {
  entity: EntityRecord;
  problems: Issue[];
  transforms: Issue[];
}) {
  return (
    <div className="entity-detail">
      <div className="entity-detail-meta">
        <span>
          <strong>ID</strong> <code>{entity.id}</code>
        </span>
        <span>
          <strong>Confidence</strong> {entity.id_confidence}
        </span>
        <span>
          <strong>Parent</strong> {entity.parent_id ?? "—"}
        </span>
      </div>

      <section className="detail-section">
        <h3>Validation issues</h3>
        {problems.length === 0 ? (
          <p className="muted">No errors or warnings on this record.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Field</th>
                  <th>Original value</th>
                  <th>Canonical value</th>
                  <th>What was found</th>
                  <th>Import impact</th>
                </tr>
              </thead>
              <tbody>
                {problems.map((issue) => (
                  <tr key={issue.id}>
                    <td>
                      <SeverityPill severity={issue.severity} />
                    </td>
                    <td className="mono-cell">{issue.field ?? "—"}</td>
                    <td className="raw-value">{displayValue(issue.raw_value)}</td>
                    <td className="norm-value">{displayValue(issue.normalised_value)}</td>
                    <td>{issue.message}</td>
                    <td className="muted">{issue.import_consequence ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="detail-section">
        <h3>Automatic clean-ups applied</h3>
        <p className="muted detail-help">
          These are deterministic code changes (not AI). Original spreadsheet values are
          preserved for audit; only the canonical field is updated.
        </p>
        {transforms.length === 0 ? (
          <p className="muted">No automatic clean-ups were applied to this record.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>What changed</th>
                  <th>Field</th>
                  <th>Before (raw)</th>
                  <th>After (canonical)</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {transforms.map((t) => (
                  <tr key={t.id}>
                    <td>{transformTitle(t)}</td>
                    <td className="mono-cell">{t.field ?? "—"}</td>
                    <td className="raw-value">{displayValue(t.raw_value)}</td>
                    <td className="norm-value">{displayValue(t.normalised_value)}</td>
                    <td>{t.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function FuzzySection({
  candidates,
  entities,
  busyId,
  onDecide,
}: {
  candidates: FuzzyCandidate[];
  entities: EntityRecord[];
  busyId: string | null;
  onDecide: (id: string, decision: string, related?: string) => void;
}) {
  const byId = useMemo(() => {
    const m: Record<string, EntityRecord> = {};
    for (const e of entities) m[e.id] = e;
    return m;
  }, [entities]);

  return (
    <div className="card">
      <h2>Fuzzy duplicate candidates</h2>
      <p className="muted">
        Scored with RapidFuzz. Nothing is merged unless you choose Merge.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Candidate A</th>
              <th>Candidate B</th>
              <th>Score</th>
              <th>Supporting evidence</th>
              <th>Conflicts</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const left = byId[c.left_id];
              const right = byId[c.right_id];
              return (
                <tr key={`${c.left_id}-${c.right_id}`}>
                  <td>
                    <div className="record-primary">
                      {left ? entityLabel(left) : c.left_id}
                    </div>
                  </td>
                  <td>
                    <div className="record-primary">
                      {right ? entityLabel(right) : c.right_id}
                    </div>
                  </td>
                  <td className="mono-cell">{c.score.toFixed(1)}</td>
                  <td>
                    <ul className="evidence-list support compact">
                      {c.supporting_evidence.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                    {c.llm_explanation && (
                      <div className="notice notice-info" style={{ marginTop: 6 }}>
                        Advisory ({c.llm_explanation.source}):{" "}
                        {c.llm_explanation.match_strength} —{" "}
                        {c.llm_explanation.recommended_human_check}
                      </div>
                    )}
                  </td>
                  <td>
                    {c.conflicting_evidence.length === 0 ? (
                      <span className="muted">None</span>
                    ) : (
                      <ul className="evidence-list conflict compact">
                        {c.conflicting_evidence.map((e, i) => (
                          <li key={i}>{e}</li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td>
                    <div className="inline-actions">
                      <button
                        className="ghost"
                        disabled={busyId === c.right_id}
                        onClick={() => onDecide(c.right_id, "merge", c.left_id)}
                      >
                        Merge into A
                      </button>
                      <button
                        className="ghost"
                        disabled={busyId === c.right_id}
                        onClick={() => onDecide(c.right_id, "keep_separate", c.left_id)}
                      >
                        Keep separate
                      </button>
                      <button
                        disabled={busyId === c.right_id}
                        onClick={() => onDecide(c.right_id, "defer", c.left_id)}
                      >
                        Defer
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
