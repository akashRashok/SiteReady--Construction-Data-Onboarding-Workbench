-- Construction Data Onboarding Workbench schema
-- SCHEMA_VERSION=1

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    source_filename TEXT,
    source_path TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 1,
    reference_date TEXT NOT NULL,
    llm_provider TEXT,
    llm_model TEXT,
    mappings_json TEXT,
    fuzzy_candidates_json TEXT,
    artifact_paths_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, source_row_number),
    FOREIGN KEY (run_id) REFERENCES import_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    data TEXT NOT NULL,
    parent_id TEXT,
    id_confidence TEXT NOT NULL,
    review_status TEXT NOT NULL,
    source_rows TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES import_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    source_rows TEXT NOT NULL,
    field TEXT,
    raw_value TEXT,
    normalised_value TEXT,
    message TEXT NOT NULL,
    import_consequence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES import_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT,
    related_entity_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES import_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_source_rows_run ON source_rows(run_id);
CREATE INDEX IF NOT EXISTS idx_entities_run ON entities(run_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(run_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_issues_run ON issues(run_id);
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id);
