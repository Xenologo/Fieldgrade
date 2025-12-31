#!/usr/bin/env bash
set -euo pipefail

# End-to-end Fieldpack demo
#
# Demonstrates:
#   1) Termite bundle sealing + verification + replay
#   2) mite_ecology MEAP-mode import (AUTO_MERGE, REVIEW_ONLY, QUARANTINE)
#   3) Review workflow (approve/reject)
#   4) Deterministic replay verification of KG delta + ingestion hash-chains
#
# This demo creates an isolated runtime under ./.demo_runtime.

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORK="${ROOT}/.demo_runtime"

rm -rf "$WORK"
mkdir -p "$WORK"

python -m venv "$WORK/.venv"
# shellcheck disable=SC1091
. "$WORK/.venv/bin/activate"

python -m pip install -q --upgrade pip
python -m pip install -q -r "$ROOT/termite_fieldpack/requirements.txt"
python -m pip install -q -r "$ROOT/mite_ecology/requirements.txt"
python -m pip install -q -e "$ROOT/termite_fieldpack"
python -m pip install -q -e "$ROOT/mite_ecology"

# -----------------------------
# Configs (isolated runtimes)
# -----------------------------

TERMITE_CFG="$WORK/termite.yaml"
TERMITE_RUNTIME="$WORK/termite_runtime"
BUNDLES_OUT="$WORK/bundles"

cat > "$TERMITE_CFG" <<YAML
termite:
  runtime_root: "${TERMITE_RUNTIME}"
  cas_root: "${TERMITE_RUNTIME}/cas"
  db_path: "${TERMITE_RUNTIME}/termite.sqlite"
  bundles_out: "${BUNDLES_OUT}"
  policy_path: "${ROOT}/termite_fieldpack/config/meap_v1.yaml"
  allowlist_path: "${ROOT}/termite_fieldpack/config/tool_allowlist.yaml"
  offline_mode: true
  network_policy: "deny_by_default"

toolchain:
  toolchain_id: "TERMITE_DEMO_TOOLCHAIN_V1"
  signing:
    enabled: true
    algorithm: "ed25519"
    private_key_path: "${TERMITE_RUNTIME}/keys/toolchain_ed25519.pem"
    public_key_path: "${TERMITE_RUNTIME}/keys/toolchain_ed25519.pub"

ingest:
  max_bytes: 52428800
  extract_text: true
  chunking:
    chunk_chars: 1400
    overlap_chars: 200
    min_chunk_chars: 200

seal:
  include_raw_blobs: true
  include_extracted_blobs: true
  include_provenance: true
  include_sbom: true
  include_kg_delta: true
  deterministic_zip: true

llm:
  provider: "endpoint_only"
  endpoint_base_url: "http://127.0.0.1:8000"
  model: "qwen2.5-coder-0.5b-instruct"
  offline_loopback_only: true
  ping:
    path: "/v1/models"
    timeout_s: 3
  launch:
    enabled: false
    command: []
    cwd: "${TERMITE_RUNTIME}/llm"
    env: {}
    startup_timeout_s: 30
    stop_timeout_s: 10
YAML

# Reusable function: create an ecology config with isolated db/runtime
make_ecology_cfg() {
  local name="$1"
  local cfg_path="$2"
  local runtime="$WORK/ecology_${name}_runtime"
  local db_path="$runtime/mite_ecology.sqlite"
  local imports_root="$runtime/imports"
  local exports_root="$WORK/ecology_${name}_exports"

  mkdir -p "$runtime" "$imports_root" "$exports_root"

  cat > "$cfg_path" <<YAML
mite_ecology:
  runtime_root: "${runtime}"
  db_path: "${db_path}"
  imports_root: "${imports_root}"
  exports_root: "${exports_root}"
  policy_path: "${ROOT}/termite_fieldpack/config/meap_v1.yaml"
  allowlist_path: "${ROOT}/termite_fieldpack/config/tool_allowlist.yaml"
  schemas_dir: "${ROOT}/schemas"
  max_bundle_ops: 200000

embedding:
  hops: 2
  feature_dim: 32
  normalize: true

gat:
  alpha: 0.2
  top_edges: 32

memoga:
  population: 24
  generations: 10
  elite_k: 6
  mutation_rate: 0.35
  crossover_rate: 0.5
  max_nodes_per_genome: 24
  max_edges_per_genome: 40

accept:
  max_new_nodes: 2000
  max_new_edges: 10000
YAML
}

run_pipeline() {
  local cfg="$1"
  mite-ecology --config "$cfg" gnn
  mite-ecology --config "$cfg" gat
  mite-ecology --config "$cfg" motifs
  mite-ecology --config "$cfg" ga
  mite-ecology --config "$cfg" export
  mite-ecology --config "$cfg" replay-verify
}

# -----------------------------
# Termite: init → ingest → seal
# -----------------------------

echo "[1/4] Termite: init"
termite --config "$TERMITE_CFG" init

echo "[1/4] Termite: ingest sample resources"
termite --config "$TERMITE_CFG" ingest "$ROOT/README.md"
termite --config "$TERMITE_CFG" ingest "$ROOT/resources/mite_componentry_manifest_from_prompt_cache.jsonl"

echo "[1/4] Termite: seal bundle"
BUNDLE_PATH="$(termite --config "$TERMITE_CFG" seal --label demo)"

echo "[1/4] Termite: verify + replay"
termite verify "$BUNDLE_PATH" --policy "$ROOT/termite_fieldpack/config/meap_v1.yaml" --allowlist "$ROOT/termite_fieldpack/config/tool_allowlist.yaml"
termite replay "$BUNDLE_PATH" --policy "$ROOT/termite_fieldpack/config/meap_v1.yaml" --allowlist "$ROOT/termite_fieldpack/config/tool_allowlist.yaml"

echo "Bundle: $BUNDLE_PATH"

# -----------------------------
# mite_ecology: import under modes
# -----------------------------

echo "[2/4] mite_ecology: AUTO_MERGE"
ECO_AUTO="$WORK/ecology_auto.yaml"
make_ecology_cfg "auto" "$ECO_AUTO"
mite-ecology --config "$ECO_AUTO" init
mite-ecology --config "$ECO_AUTO" import-bundle "$BUNDLE_PATH" --mode AUTO_MERGE --actor "demo" --notes "auto merge demo"
run_pipeline "$ECO_AUTO"

echo "[3/4] mite_ecology: REVIEW_ONLY -> approve"
ECO_REVIEW="$WORK/ecology_review.yaml"
make_ecology_cfg "review" "$ECO_REVIEW"
mite-ecology --config "$ECO_REVIEW" init
mite-ecology --config "$ECO_REVIEW" import-bundle "$BUNDLE_PATH" --mode REVIEW_ONLY --actor "demo" --notes "review-only demo"

# Extract staged id from review-list output
STAGED_ID="$(mite-ecology --config "$ECO_REVIEW" review-list --status PENDING | sed -n 's/^\[\([0-9]\+\)\].*/\1/p' | head -n 1)"
if [[ -z "${STAGED_ID}" ]]; then
  echo "ERROR: expected a staged bundle in REVIEW_ONLY mode" >&2
  exit 2
fi

mite-ecology --config "$ECO_REVIEW" review-approve "$STAGED_ID" --actor "demo" --notes "approved in demo"
run_pipeline "$ECO_REVIEW"

echo "[4/4] mite_ecology: QUARANTINE -> reject"
ECO_QUAR="$WORK/ecology_quarantine.yaml"
make_ecology_cfg "quarantine" "$ECO_QUAR"
mite-ecology --config "$ECO_QUAR" init
mite-ecology --config "$ECO_QUAR" import-bundle "$BUNDLE_PATH" --mode QUARANTINE --actor "demo" --notes "quarantine demo"

QID="$(mite-ecology --config "$ECO_QUAR" review-list --status QUARANTINED | sed -n 's/^\[\([0-9]\+\)\].*/\1/p' | head -n 1)"
if [[ -z "${QID}" ]]; then
  echo "ERROR: expected a staged bundle in QUARANTINE mode" >&2
  exit 2
fi

mite-ecology --config "$ECO_QUAR" review-reject "$QID" --actor "demo" --notes "rejected in demo"

echo "Done. Demo runtimes are under: $WORK"
