import type {
  AuditTrace,
  ColumnMapping,
  ExportResult,
  ImportRun,
  ReviewPayload,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, init);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export interface HealthInfo {
  status: string;
  notice: string;
  llm_provider: string;
  llm_model: string;
  llm_hosted?: boolean;
  llm_warning?: string | null;
}

export interface LlmSettings {
  provider: string;
  model: string;
  is_hosted: boolean;
  warning: string | null;
  ollama_base_url: string;
  openai_base_url: string;
  anthropic_base_url: string;
  gemini_base_url: string;
  openai_api_key_set: boolean;
  anthropic_api_key_set: boolean;
  gemini_api_key_set: boolean;
  openai_api_key_preview: string | null;
  anthropic_api_key_preview: string | null;
  gemini_api_key_preview: string | null;
  providers: string[];
  model_presets: Record<string, string[]>;
  notice: string;
}

export interface SwmsEvidence {
  value: string | string[] | Record<string, string>[] | null;
  source_text: string;
  page?: number | null;
  validation_error?: string;
  raw_value?: string;
}

export interface SwmsJobStep {
  step: string;
  hazard: string;
  risk_rating: string;
  control_measures: string;
}

export interface SwmsFields {
  swms_number?: string | null;
  document_title?: string | null;
  contractor_name?: string | null;
  contractor_abn?: string | null;
  project_name?: string | null;
  site_address?: string | null;
  activity?: string | null;
  date_prepared?: string | null;
  review_date?: string | null;
  responsible_person?: string | null;
  high_risk_categories?: string[];
  ppe_required?: string[];
  plant_and_equipment?: string[];
  required_competencies_licences?: string[];
  job_steps?: SwmsJobStep[];
  [key: string]: string | string[] | SwmsJobStep[] | null | undefined;
}

export interface SwmsExtractResult {
  disclaimer: string;
  source_file: string;
  fields: SwmsFields;
  evidence: Record<string, SwmsEvidence>;
  llm_used: boolean;
  artifact_path?: string;
  warning?: string;
}

export const api = {
  health: () => request<HealthInfo>("/health"),

  getLlmSettings: () => request<LlmSettings>("/settings/llm"),

  updateLlmSettings: (body: Record<string, string>) =>
    request<LlmSettings>("/settings/llm", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  resetLlmSettings: () =>
    request<LlmSettings>("/settings/llm", { method: "DELETE" }),

  createRun: (name: string, referenceDate: string) =>
    request<ImportRun>("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, reference_date: referenceDate }),
    }),

  listRuns: () => request<ImportRun[]>("/runs"),

  getRun: (id: string) => request<ImportRun>(`/runs/${id}`),

  deleteRun: (id: string) =>
    request<void>(`/runs/${id}`, { method: "DELETE" }),

  uploadCsv: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportRun>(`/runs/${id}/upload`, {
      method: "POST",
      body: form,
    });
  },

  getMappings: (id: string) =>
    request<ColumnMapping[]>(`/runs/${id}/mappings`),

  confirmMappings: (id: string, mappings: Partial<ColumnMapping>[]) =>
    request<ImportRun>(`/runs/${id}/mappings/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    }),

  process: (id: string) =>
    request<ImportRun>(`/runs/${id}/process`, { method: "POST" }),

  getReview: (id: string) => request<ReviewPayload>(`/runs/${id}/review`),

  decide: (
    id: string,
    decision: {
      entity_id: string;
      decision: string;
      reason?: string | null;
      related_entity_id?: string | null;
    },
  ) =>
    request<void>(`/runs/${id}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    }),

  decideBatch: (
    id: string,
    decisions: Array<{
      entity_id: string;
      decision: string;
      reason?: string | null;
      related_entity_id?: string | null;
    }>,
  ) =>
    request<void>(`/runs/${id}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decisions }),
    }),

  export: (id: string) =>
    request<ExportResult>(`/runs/${id}/export`, { method: "POST" }),

  getAudit: (id: string, entityId: string) =>
    request<AuditTrace>(`/runs/${id}/audit/${entityId}`),

  artifactUrl: (id: string, name: string) =>
    `${BASE}/runs/${id}/artifacts/${name}`,

  extractSwms: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<SwmsExtractResult>("/swms/extract", {
      method: "POST",
      body: form,
    });
  },
};
