# AI Boundaries — Construction Data Onboarding Workbench

Independent demo. Synthetic data.

This document states where the language model is used, where it is forbidden, and why those boundaries exist. It is part of the demonstration itself: customer data migrations fail when generative systems are allowed to invent facts, approve records, or silently merge identities.

## Deterministic first

Every step that changes whether a record can be imported is implemented in ordinary code:

- CSV parsing and source-row numbering
- Column profiling and mapping proposals
- Entity split and stable ID generation
- Normalisation (names, dates, phones, emails, enums, ABN checksum)
- Validation rules and severity assignment
- Exact duplicate collapse and fuzzy candidate scoring
- Counts in exception reports and implementation summaries
- Export eligibility, parent-child blocking, and CSV generation

Those steps are testable, re-runnable, and independent of model availability. Re-running the same input with the same reference date produces the same IDs and the same issue set.

## Where the LLM is called

Exactly three places, all advisory:

1. **Implementation summary drafting** — turns structured counts and decision totals into a short customer-facing note. The model must not state a number that is absent from its structured input.
2. **Exception narrative** — groups deterministic issue categories into readable prose. Counts still come from the pipeline.
3. **Fuzzy candidate explanation** — given two candidate records and pre-computed evidence, returns only:

```json
{
  "match_strength": "strong | moderate | weak",
  "supporting_evidence": ["..."],
  "conflicting_evidence": ["..."],
  "recommended_human_check": "..."
}
```

The model never returns an identity verdict. The human chooses merge, keep separate, or defer.

## Reliability pattern

Local instruct models often violate schemas. For structured calls the adapter:

1. Requests JSON/format mode
2. Validates against a Pydantic schema
3. Retries once with the validation error fed back
4. Falls back to a deterministic template

If Ollama is stopped or unreachable, the run still completes. Summaries and explanations use templates and the UI continues to show the active provider/model configuration.

## What the model must never do

- Invent a source field value
- Decide that two people or companies are the same
- Approve, reject, override, or export a record
- Calculate report totals
- Bypass the human gate

## Privacy claim (precise, not overstated)

With the default `LLM_PROVIDER=ollama`, prompts are sent to a local Ollama process and are not sent to a hosted LLM provider. That is a deliberate default for migration work involving names, contact details, and licence numbers.

Hosted adapters (`openai`, `anthropic`, `gemini`) are available behind the same `LLMAdapter` interface. Switching to them is an explicit `.env` change. The API and UI surface a visible warning that prompts leave this machine. Missing API keys do not crash the pipeline; drafting falls back to deterministic templates.

This demo does **not** claim production-grade security, compliance, tenant isolation, encryption, retention, or data governance. Using a hosted provider is an explicit configuration change and should be treated as such.

## Why this design

Implementation engineers need to explain every exclusion to a customer. Deterministic rules produce evidence a CSM can defend. The model is useful for drafting language after the facts are settled — not for settling the facts.
