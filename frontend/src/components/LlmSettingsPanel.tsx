import { useEffect, useMemo, useState } from "react";
import { api, type LlmSettings } from "../api/client";

interface LlmSettingsPanelProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

type FormState = {
  provider: string;
  model: string;
  ollama_base_url: string;
  openai_base_url: string;
  anthropic_base_url: string;
  gemini_base_url: string;
  openai_api_key: string;
  anthropic_api_key: string;
  gemini_api_key: string;
};

const EMPTY_FORM: FormState = {
  provider: "ollama",
  model: "llama3.1:latest",
  ollama_base_url: "http://localhost:11434",
  openai_base_url: "https://api.openai.com/v1",
  anthropic_base_url: "https://api.anthropic.com",
  gemini_base_url: "https://generativelanguage.googleapis.com/v1beta",
  openai_api_key: "",
  anthropic_api_key: "",
  gemini_api_key: "",
};

export function LlmSettingsPanel({ open, onClose, onSaved }: LlmSettingsPanelProps) {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setMessage(null);
    api
      .getLlmSettings()
      .then((s) => {
        setSettings(s);
        setForm({
          provider: s.provider,
          model: s.model,
          ollama_base_url: s.ollama_base_url,
          openai_base_url: s.openai_base_url,
          anthropic_base_url: s.anthropic_base_url,
          gemini_base_url: s.gemini_base_url,
          openai_api_key: "",
          anthropic_api_key: "",
          gemini_api_key: "",
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [open]);

  const presets = useMemo(() => {
    if (!settings) return [];
    return settings.model_presets[form.provider] ?? [];
  }, [settings, form.provider]);

  const hosted = ["openai", "anthropic", "gemini"].includes(form.provider);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleProviderChange = (provider: string) => {
    const nextPresets = settings?.model_presets[provider] ?? [];
    setForm((prev) => ({
      ...prev,
      provider,
      model: nextPresets[0] ?? prev.model,
    }));
  };

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const payload: Record<string, string> = {
        provider: form.provider,
        model: form.model,
        ollama_base_url: form.ollama_base_url,
        openai_base_url: form.openai_base_url,
        anthropic_base_url: form.anthropic_base_url,
        gemini_base_url: form.gemini_base_url,
      };
      if (form.openai_api_key.trim()) payload.openai_api_key = form.openai_api_key.trim();
      if (form.anthropic_api_key.trim()) {
        payload.anthropic_api_key = form.anthropic_api_key.trim();
      }
      if (form.gemini_api_key.trim()) payload.gemini_api_key = form.gemini_api_key.trim();

      const saved = await api.updateLlmSettings(payload);
      setSettings(saved);
      setForm((prev) => ({
        ...prev,
        openai_api_key: "",
        anthropic_api_key: "",
        gemini_api_key: "",
      }));
      setMessage("Model settings saved. New runs will use this provider.");
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleClearKey = async (provider: "openai" | "anthropic" | "gemini") => {
    setBusy(true);
    setError(null);
    try {
      const key =
        provider === "openai"
          ? "openai_api_key"
          : provider === "anthropic"
            ? "anthropic_api_key"
            : "gemini_api_key";
      const saved = await api.updateLlmSettings({ [key]: "-" });
      setSettings(saved);
      setMessage(`${provider} API key cleared.`);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.resetLlmSettings();
      setSettings(saved);
      setForm({
        provider: saved.provider,
        model: saved.model,
        ollama_base_url: saved.ollama_base_url,
        openai_base_url: saved.openai_base_url,
        anthropic_base_url: saved.anthropic_base_url,
        gemini_base_url: saved.gemini_base_url,
        openai_api_key: "",
        anthropic_api_key: "",
        gemini_api_key: "",
      });
      setMessage("Reset to .env defaults.");
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        className="settings-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="llm-settings-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-header">
          <div>
            <h2 id="llm-settings-title">Model connectors</h2>
            <p className="muted">
              Configure the advisory LLM. Validation and export stay deterministic.
            </p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </div>

        {error && <div className="notice notice-error">{error}</div>}
        {message && <div className="notice notice-info">{message}</div>}
        {hosted && (
          <div className="notice notice-error">
            Hosted provider selected: prompts leave this machine. This is an explicit
            configuration change, not the default.
          </div>
        )}

        <div className="field">
          <label htmlFor="llm-provider">Provider</label>
          <select
            id="llm-provider"
            value={form.provider}
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            {(settings?.providers ?? ["ollama"]).map((p) => (
              <option key={p} value={p}>
                {p}
                {p === "ollama" ? " (local default)" : ""}
                {p === "fallback" ? " (no model calls)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="llm-model">Model</label>
          <input
            id="llm-model"
            list="llm-model-presets"
            value={form.model}
            onChange={(e) => setField("model", e.target.value)}
            placeholder="Model id"
          />
          <datalist id="llm-model-presets">
            {presets.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          {presets.length > 0 && (
            <div className="preset-row">
              {presets.map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`filter-chip ${form.model === m ? "active" : ""}`}
                  onClick={() => setField("model", m)}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {form.provider === "ollama" && (
          <div className="field">
            <label htmlFor="ollama-url">Ollama base URL</label>
            <input
              id="ollama-url"
              value={form.ollama_base_url}
              onChange={(e) => setField("ollama_base_url", e.target.value)}
            />
          </div>
        )}

        {form.provider === "openai" && (
          <>
            <div className="field">
              <label htmlFor="openai-key">
                OpenAI API key
                {settings?.openai_api_key_set
                  ? ` (saved: ${settings.openai_api_key_preview})`
                  : " (not set)"}
              </label>
              <input
                id="openai-key"
                type="password"
                autoComplete="off"
                value={form.openai_api_key}
                onChange={(e) => setField("openai_api_key", e.target.value)}
                placeholder="Leave blank to keep current key"
              />
              {settings?.openai_api_key_set && (
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => handleClearKey("openai")}
                >
                  Clear saved key
                </button>
              )}
            </div>
            <div className="field">
              <label htmlFor="openai-url">OpenAI base URL</label>
              <input
                id="openai-url"
                value={form.openai_base_url}
                onChange={(e) => setField("openai_base_url", e.target.value)}
              />
            </div>
          </>
        )}

        {form.provider === "anthropic" && (
          <>
            <div className="field">
              <label htmlFor="anthropic-key">
                Anthropic API key
                {settings?.anthropic_api_key_set
                  ? ` (saved: ${settings.anthropic_api_key_preview})`
                  : " (not set)"}
              </label>
              <input
                id="anthropic-key"
                type="password"
                autoComplete="off"
                value={form.anthropic_api_key}
                onChange={(e) => setField("anthropic_api_key", e.target.value)}
                placeholder="Leave blank to keep current key"
              />
              {settings?.anthropic_api_key_set && (
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => handleClearKey("anthropic")}
                >
                  Clear saved key
                </button>
              )}
            </div>
            <div className="field">
              <label htmlFor="anthropic-url">Anthropic base URL</label>
              <input
                id="anthropic-url"
                value={form.anthropic_base_url}
                onChange={(e) => setField("anthropic_base_url", e.target.value)}
              />
            </div>
          </>
        )}

        {form.provider === "gemini" && (
          <>
            <div className="field">
              <label htmlFor="gemini-key">
                Gemini API key
                {settings?.gemini_api_key_set
                  ? ` (saved: ${settings.gemini_api_key_preview})`
                  : " (not set)"}
              </label>
              <input
                id="gemini-key"
                type="password"
                autoComplete="off"
                value={form.gemini_api_key}
                onChange={(e) => setField("gemini_api_key", e.target.value)}
                placeholder="Leave blank to keep current key"
              />
              {settings?.gemini_api_key_set && (
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => handleClearKey("gemini")}
                >
                  Clear saved key
                </button>
              )}
            </div>
            <div className="field">
              <label htmlFor="gemini-url">Gemini base URL</label>
              <input
                id="gemini-url"
                value={form.gemini_base_url}
                onChange={(e) => setField("gemini_base_url", e.target.value)}
              />
            </div>
          </>
        )}

        <div className="drawer-actions">
          <button className="primary" type="button" disabled={busy} onClick={handleSave}>
            {busy ? "Saving…" : "Save settings"}
          </button>
          <button className="ghost" type="button" disabled={busy} onClick={handleReset}>
            Reset to .env
          </button>
        </div>
      </aside>
    </div>
  );
}
