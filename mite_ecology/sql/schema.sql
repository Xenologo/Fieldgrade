PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  attrs_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  edge_key TEXT NOT NULL UNIQUE,   -- deterministic: sha256(src|dst|type|attrs_json_canon)
  src TEXT NOT NULL,
  dst TEXT NOT NULL,
  type TEXT NOT NULL,
  attrs_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);

CREATE TABLE IF NOT EXISTS node_embeddings (
  node_id TEXT PRIMARY KEY,
  dim INTEGER NOT NULL,
  vec_json TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edge_attention (
  edge_id INTEGER PRIMARY KEY,
  score REAL NOT NULL,
  context_node_id TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS motifs (
  motif_id TEXT PRIMARY KEY,
  context_node_id TEXT NOT NULL,
  motif_json TEXT NOT NULL,
  score REAL NOT NULL,
  created_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genomes (
  genome_id TEXT PRIMARY KEY,
  context_node_id TEXT NOT NULL,
  genome_json TEXT NOT NULL,
  created_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genome_eval (
  genome_id TEXT PRIMARY KEY,
  fitness REAL NOT NULL,
  eval_json TEXT NOT NULL,
  evaluated_utc TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS kg_deltas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  context_node_id TEXT,
  delta_kind TEXT NOT NULL,
  delta_payload TEXT NOT NULL,
  prev_hash TEXT,
  delta_hash TEXT NOT NULL,
  chain_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_kg_deltas_context ON kg_deltas(context_node_id);
CREATE TABLE IF NOT EXISTS ingested_bundles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  bundle_sha256 TEXT NOT NULL,
  bundle_name TEXT NOT NULL,
  verified_ok INTEGER NOT NULL,
  verify_reason TEXT,
  policy_id TEXT,
  policy_hash TEXT,
  allowlist_hash TEXT,
  toolchain_id TEXT,
  bundle_map_hash TEXT,
  ops_count INTEGER NOT NULL,
  kg_delta_hash TEXT,
  ingest_kind TEXT NOT NULL, -- MERGED|STAGED|QUARANTINED
  prev_hash TEXT,
  ingest_hash TEXT NOT NULL,
  notes TEXT
);


CREATE UNIQUE INDEX IF NOT EXISTS uidx_ingested_bundles_sha ON ingested_bundles(bundle_sha256);
CREATE INDEX IF NOT EXISTS idx_ingested_bundles_ts ON ingested_bundles(ts_utc);


CREATE TABLE IF NOT EXISTS staged_bundles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  bundle_sha256 TEXT NOT NULL,
  bundle_name TEXT NOT NULL,
  verified_ok INTEGER NOT NULL,
  verify_reason TEXT,
  policy_id TEXT,
  policy_hash TEXT,
  allowlist_hash TEXT,
  toolchain_id TEXT,
  bundle_map_hash TEXT,
  ops_count INTEGER NOT NULL,
  kg_delta_payload TEXT NOT NULL,
  kg_delta_hash TEXT NOT NULL,
  status TEXT NOT NULL, -- PENDING|APPROVED|REJECTED|QUARANTINED
  policy_mode TEXT NOT NULL, -- AUTO_MERGE|REVIEW_ONLY|QUARANTINE|KILL
  contracts_report_json TEXT,
  kg_shacl_report_json TEXT,
  decision_ts_utc TEXT,
  decision_actor TEXT,
  decision_notes TEXT,
  prev_hash TEXT,
  stage_hash TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uidx_staged_bundles_sha ON staged_bundles(bundle_sha256);
CREATE INDEX IF NOT EXISTS idx_staged_bundles_status ON staged_bundles(status);
CREATE INDEX IF NOT EXISTS idx_staged_bundles_ts ON staged_bundles(ts_utc);




CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  context_node_id TEXT,
  scope_rule TEXT,
  endpoint_base_url TEXT NOT NULL,
  model TEXT NOT NULL,
  temperature REAL NOT NULL,
  prompt_hash TEXT NOT NULL,
  context_hash TEXT NOT NULL,
  request_json TEXT NOT NULL,
  response_text TEXT NOT NULL,
  response_hash TEXT NOT NULL,
  parsed_kind TEXT,
  parsed_payload TEXT,
  parsed_hash TEXT,
  validation_ok INTEGER NOT NULL,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_context ON llm_calls(context_node_id);
