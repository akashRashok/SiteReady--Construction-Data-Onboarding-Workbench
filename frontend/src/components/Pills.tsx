import type { ReviewStatus, Severity } from "../types";

export function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`pill pill-${severity}`}>{severity}</span>;
}

export function StatusPill({ status }: { status: ReviewStatus }) {
  return <span className={`pill pill-${status}`}>{status.replace(/_/g, " ")}</span>;
}

export function ConfidencePill({ level }: { level: "high" | "medium" | "low" }) {
  return <span className={`pill pill-${level}`}>{level}</span>;
}
