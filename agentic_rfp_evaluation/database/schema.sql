CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    weight REAL NOT NULL CHECK (weight > 0),
    max_score REAL NOT NULL DEFAULT 10,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS supplier_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id INTEGER NOT NULL,
    supplier_name TEXT NOT NULL,
    submission_date TEXT,
    experience_rating REAL,
    absolute_score REAL,
    ppi REAL,
    final_rank INTEGER,
    result_json TEXT,
    warnings TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id)
);

CREATE TABLE IF NOT EXISTS proposal_chunks (
    document_hash TEXT NOT NULL,
    source_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    heading TEXT,
    section_path_json TEXT,
    boundary_type TEXT,
    embedding_text TEXT,
    embedding_json TEXT,
    embedding_model TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_hash, chunk_index)
);
