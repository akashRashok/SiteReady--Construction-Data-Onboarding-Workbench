export type EntityType = "company" | "worker" | "certification";

export type ReviewStatus =
  | "pending_review"
  | "approved"
  | "approved_with_override"
  | "rejected"
  | "excluded_by_rule";

export type Severity = "error" | "warning" | "info";

export type RunStatus =
  | "created"
  | "ingested"
  | "mapping_pending"
  | "processing"
  | "review_pending"
  | "approved"
  | "exported"
  | "failed";

export interface ImportRun {
  id: string;
  name: string;
  status: RunStatus;
  source_filename: string | null;
  source_path: string | null;
  is_synthetic: boolean;
  reference_date: string;
  llm_provider: string | null;
  llm_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface ColumnMapping {
  source_column: string;
  target_entity: EntityType | null;
  target_field: string | null;
  method: "exact_header" | "alias" | "heuristic" | "unmapped";
  confidence: "high" | "medium" | "low";
  sample_values: string[];
  confirmed: boolean;
}

export interface EntityRecord {
  id: string;
  run_id: string;
  entity_type: EntityType;
  data: Record<string, unknown>;
  parent_id: string | null;
  id_confidence: "high" | "medium" | "low";
  review_status: ReviewStatus;
  source_rows: number[];
  created_at: string;
  updated_at: string;
}

export interface Issue {
  id: string;
  run_id: string;
  rule_id: string;
  severity: Severity;
  entity_type: EntityType | null;
  entity_id: string | null;
  source_rows: number[];
  field: string | null;
  raw_value: string | null;
  normalised_value: string | null;
  message: string;
  import_consequence: string | null;
  created_at: string;
}

export interface DuplicateGroup {
  canonical_id: string;
  duplicate_ids: string[];
  duplicate_count: number;
  comparison_key: string;
}

export interface FuzzyCandidate {
  entity_type: EntityType;
  left_id: string;
  right_id: string;
  score: number;
  supporting_evidence: string[];
  conflicting_evidence: string[];
  llm_explanation?: LlmMatchExplanation | null;
}

export interface LlmMatchExplanation {
  match_strength: "strong" | "moderate" | "weak";
  supporting_evidence: string[];
  conflicting_evidence: string[];
  recommended_human_check: string;
  source: "llm" | "fallback";
}

export interface ReviewPayload {
  entities: EntityRecord[];
  issues: Issue[];
  exact_duplicates: DuplicateGroup[];
  fuzzy_candidates: FuzzyCandidate[];
}

export interface ExportBlocker {
  entity_id: string;
  entity_type: EntityType;
  reason: string;
}

export interface ExportResult {
  status: "exported" | "blocked";
  blockers: ExportBlocker[];
  artifacts: string[];
}

export interface AuditTrace {
  entity: EntityRecord;
  source_rows: { source_row_number: number; raw_data: Record<string, unknown> }[];
  transformations: Issue[];
  issues: Issue[];
  decisions: {
    id: string;
    decision: string;
    reason: string | null;
    related_entity_id: string | null;
    created_at: string;
  }[];
}
