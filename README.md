# mite_ecology_fullstack (Fieldpack-grade)

This monorepo provides:

## Canonical dev setup (recommended)

Use the bootstrap scripts to get to a known-good environment (runtime + dev deps + editable installs).

**Linux / WSL (bash):**

```bash
bash scripts/bootstrap_dev.sh
make test
```

**Windows (PowerShell):**

```powershell
.\scripts\bootstrap_dev.ps1
python -m pytest -q
```

After bootstrapping, you can run the CLIs (`termite`, `mite-ecology`, `fieldgrade-ui`) or follow the fast-start flows below.

### Warnings policy

Pytest is configured to treat `DeprecationWarning` and `PendingDeprecationWarning` as errors (CI gate).
If a new dependency or change introduces these warnings, fix or isolate it before merging.

## 1) `termite_fieldpack/` (Termux/field/offline)
A fieldable toolchain that can:

- **Ingest** files into a **CAS** (content-addressed blobs) + **SQLite** + **FTS5** (when available)
- Emit **hash-chained provenance** events (append-only)
- Store KG delta ops (`kg_delta.jsonl`) describing observed nodes/edges
- **Seal** deterministic, signed bundles (manifest + SBOM + provenance + kg_delta + blobs)
- **Verify** bundles against **MEAP v1** policy + toolchain allowlist
- **Replay** bundles conservatively (structural checks only; no tool re-exec)

## 2) `mite_ecology/` (design-time)
A minimal-but-real pipeline:

- Import verified termite bundles and apply `kg_delta.jsonl` to the KG
- Compute **deterministic GNN embeddings** via message passing (CPU / NumPy)
- Compute **deterministic GAT-style attention** over edges for a chosen context node
- Mine motifs from top-attention edges
- Run a **memoized deterministic GA** to evolve motif-derived genomes
- Export a minimal **neuroarch DSL** JSON + a tiny python skeleton

## Termite-owned local LLM runtime (optional but recommended)

Termite can **own the runtime identity** of your local OpenAI-compatible endpoint (llama.cpp server / vLLM / etc.).

- Configure `termite_fieldpack/config/termite.yaml` → `llm.*`
- Start / stop / ping via:

```bash
cd termite_fieldpack
./bin/termite llm status --json
./bin/termite llm ping
./bin/termite llm start        # launches if llm.launch.enabled=true, otherwise "marks active" after ping
./bin/termite llm stop
```

When `mite_ecology/configs/ecology.yaml` sets `llm.endpoint_source: termite`, the `mite-ecology llm-*` commands will query Termite for the active endpoint (base_url, model, endpoint_id, toolchain_id) and record this binding in the `llm_calls.request_json` audit record.

---

## Fast start (Linux / Termux-like)

```bash
# One-time setup
bash scripts/bootstrap_dev.sh

# (or manual setup)
# python -m venv .venv
# . .venv/bin/activate
# pip install -r termite_fieldpack/requirements.txt
# pip install -r mite_ecology/requirements.txt
# pip install -e termite_fieldpack
# pip install -e mite_ecology

# Termite runtime
cd termite_fieldpack
./bin/termite init
./bin/termite ingest ../README.md
./bin/termite search "field"
BUNDLE=$(./bin/termite seal --label demo)

./bin/termite verify "$BUNDLE"
./bin/termite replay "$BUNDLE"

# mite_ecology: import + embed + attention + motifs + GA + export
cd ../mite_ecology
./bin/mite-ecology init
./bin/mite-ecology import-bundle "$BUNDLE"
./bin/mite-ecology gnn
./bin/mite-ecology gat
./bin/mite-ecology motifs
./bin/mite-ecology ga
./bin/mite-ecology export
```

Outputs appear under:
- termite bundles: `termite_fieldpack/artifacts/bundles_out/`
- mite_ecology exports: `mite_ecology/artifacts/export/`

---

## Fast start (Windows / PowerShell)

```powershell
# One-time setup
.\scripts\bootstrap_dev.ps1

# (or manual setup)
# python -m venv .venv
# .\.venv\Scripts\Activate.ps1
# pip install -r termite_fieldpack\requirements.txt
# pip install -r mite_ecology\requirements.txt
# pip install -e termite_fieldpack
# pip install -e mite_ecology

# (Optional) confirm entrypoints
Get-Command termite
Get-Command mite-ecology

# Termite runtime
cd termite_fieldpack
python -m termite.cli init
python -m termite.cli ingest ..\README.md
$BUNDLE = (python -m termite.cli seal --label demo).Trim()
python -m termite.cli verify $BUNDLE
python -m termite.cli replay $BUNDLE

# mite_ecology: import + embed + attention + motifs + GA + export
cd ..\mite_ecology
python -m mite_ecology.cli init
python -m mite_ecology.cli import-bundle $BUNDLE
python -m mite_ecology.cli gnn
python -m mite_ecology.cli gat
python -m mite_ecology.cli motifs
python -m mite_ecology.cli ga
python -m mite_ecology.cli export
```

Or run everything in one command:

```powershell
.\run_demo.ps1
```

## Notes
- No heavy ML deps (no torch); everything is CPU + deterministic NumPy.
- The MEAP policy is in `termite_fieldpack/config/meap_v1.yaml`.
- Signature keys are generated into `termite_fieldpack/runtime/keys/` on first `termite init`.

## Platform guides

- Android (Termux): see `TERMUX.md`
- Windows laptop guide — see `WINDOWS.md` (WSL2 recommended)

## Deployment (Docker Compose)

This repo uses Docker Compose file stacking for dev vs production.

- Local dev (exposes `http://127.0.0.1:8787` directly):
   - `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`

- Single-host production (Caddy TLS termination; do not expose `8787` directly):
   - `docker compose -f compose.yaml -f compose.production.yaml up -d --build`
   - See `docs/DEPLOY_PROD_SINGLEHOST.md` and `docs/DEPLOY_CHECKLIST.md`.

For production proxy header trust, prefer trusting only the Docker network CIDR (instead of `*`):

- Bring the stack up once so the network exists.
- Get the subnet CIDR:
   - `docker network inspect fg_next_default --format '{{(index .IPAM.Config 0).Subnet}}'`
- Set:
   - `FG_FORWARDED_ALLOW_IPS=<that CIDR>` (example: `172.18.0.0/16`)
- If the network name differs, it’s usually `<project>_default`; discover via:
   - `docker network ls | grep _default`



## Strict deterministic mode

This stack is designed so that **the same inputs produce the same on-disk artifacts** (hashes, deltas, reports),
provided you run in the same environment and do not introduce new non-deterministic external signals.

Determinism is enforced by:

- Canonical JSON serialization (`sort_keys`, stable separators) everywhere hashes are computed.
- Hash-chained logs (`termite.events`, `mite_ecology.kg_deltas`, `mite_ecology.ingested_bundles`, `termite.llm_calls`, `termite.tool_runs`).
- Deterministic GNN embeddings and GAT attention scoring (no stochastic dropout/training steps in this repo).
- Deterministic memo-GA RNG (`xorshift64*`) seeded from stable hashes (context node + cycle).
- Conservative merge: `mite-ecology import-bundle` validates bundle policy/signature then validates each op against `schemas/kg_delta.json`.

**Important:** LLM output is treated as *exogenous* unless cached.
`mite-ecology llm-*` records prompt/context hashes and stores raw responses,
but any *live* LLM call can vary across runs unless you only replay cached responses.

## Quick start (monorepo)

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# init
./termite_fieldpack/bin/termite init
./mite_ecology/bin/mite-ecology init

# ingest something (termite)
./termite_fieldpack/bin/termite ingest ./termite_fieldpack/docs/field_ops.md

# seal + verify (termite)
./termite_fieldpack/bin/termite seal --label demo
./termite_fieldpack/bin/termite verify ./artifacts/bundles_out/*.zip

# import into mite_ecology + run deterministic extrusion
./mite_ecology/bin/mite-ecology import-bundle ./artifacts/bundles_out/*.zip --notes "demo import"
./mite_ecology/bin/mite-ecology auto-run --cycles 3
```

## Termite LLM runtime ownership

Termite can manage an OpenAI-compatible local server and becomes the **runtime identity owner**:

```sh
./termite_fieldpack/bin/termite llm start
./termite_fieldpack/bin/termite llm ping
./termite_fieldpack/bin/termite llm status --json
./termite_fieldpack/bin/termite llm chat --prompt "Emit a strict kg_delta.jsonl for ..."
./termite_fieldpack/bin/termite llm stop
```

For Termux usage, configure `termite_fieldpack/config/termite.yaml` with either:
- `provider: endpoint_only` (you launch the server), or
- `provider: llama_cpp_server|vllm` with `launch.command` enabled (Termite launches it).

---

## MEAP modes and review workflow (mite_ecology)

`mite-ecology import-bundle` can override the policy mode per import.

- `AUTO_MERGE` applies the KG delta immediately and records a hash-chained ingest event.
- `REVIEW_ONLY` stages the KG delta as `PENDING` for human approval.
- `QUARANTINE` stages the KG delta as `QUARANTINED` (explicitly separated from normal review).
- `KILL` refuses ingestion.

Commands:

```bash
# stage
./mite_ecology/bin/mite-ecology import-bundle ./termite_fieldpack/artifacts/bundles_out/demo*.zip --mode REVIEW_ONLY --actor "alice" --notes "needs review"

# inspect staged queue
./mite_ecology/bin/mite-ecology review-list --status PENDING

# approve / reject
./mite_ecology/bin/mite-ecology review-approve 123 --actor "alice" --notes "ok"
./mite_ecology/bin/mite-ecology review-reject  124 --actor "alice" --notes "no"

# verify deterministic replay integrity
./mite_ecology/bin/mite-ecology replay-verify
```

## End-to-end demo

From the monorepo root:

```bash
./run_demo.sh
```

On Windows (PowerShell):

```powershell
.\run_demo.ps1
```

The demo:

1. Initializes an isolated Termite runtime.
2. Ingests a few resources and seals a deterministic, signed bundle.
3. Verifies and replays the bundle (structural checks only).
4. Imports the bundle into mite_ecology in three ways:
   - `AUTO_MERGE`
   - `REVIEW_ONLY` (approved)
   - `QUARANTINE` (rejected)
5. Runs the deterministic pipeline and replay verification on the merged cases.

---

## Local UI (single page)

This repo includes an optional local UI that wraps the CLI commands (upload/ingest, bundle ops, ecology pipeline, graph explorer, logs).

On Windows (PowerShell):

```powershell
./run_ui.ps1
```

Then open:

```text
http://127.0.0.1:8787/
```



## Android (Termux)

See `TERMUX.md` for a Termux-native install and run flow (including scripts).
