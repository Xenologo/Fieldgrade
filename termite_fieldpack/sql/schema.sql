PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS blobs (
  sha256 TEXT PRIMARY KEY,
  kind TEXT NOT NULL,              -- raw | extract | aux
  size_bytes INTEGER NOT NULL,
  created_utc TEXT NOT NULL,
  source_path TEXT
);

CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  mime TEXT,
  raw_blob_sha256 TEXT NOT NULL,
  extract_blob_sha256 TEXT,
  created_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  start_char INTEGER NOT NULL,
  end_char INTEGER NOT NULL,
  text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  created_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  prev_hash TEXT,
  event_hash TEXT NOT NULL
);

-- optional: store KG delta ops as JSONL lines
CREATE TABLE IF NOT EXISTS kg_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  op_json TEXT NOT NULL,
  op_hash TEXT NOT NULL
);

-- LLM calls (audited). Request/response payloads may be stored as aux blobs in CAS.
CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  endpoint_base_url TEXT NOT NULL,
  model TEXT NOT NULL,
  temperature REAL NOT NULL,
  prompt_hash TEXT NOT NULL,
  request_aux_sha256 TEXT,
  response_aux_sha256 TEXT,
  response_hash TEXT NOT NULL,
  prev_hash TEXT,
  call_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts_utc);

-- Tool runs (audited, allowlist-governed)
CREATE TABLE IF NOT EXISTS tool_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  argv_json TEXT NOT NULL,
  exit_code INTEGER NOT NULL,
  stdout_aux_sha256 TEXT,
  stderr_aux_sha256 TEXT,
  prev_hash TEXT,
  run_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_ts ON tool_runs(ts_utc);



CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  doc_id UNINDEXED,
  chunk_id UNINDEXED,
  path UNINDEXED,
  tokenize = 'unicode61'
);

CREATE TRIGGER IF NOT EXISTS trg_chunks_ai AFTER INSERT ON chunks
BEGIN
  INSERT INTO chunks_fts(text, doc_id, chunk_id, path)
  VALUES (NEW.text, NEW.doc_id, NEW.id, (SELECT path FROM docs WHERE id = NEW.doc_id));
END;
