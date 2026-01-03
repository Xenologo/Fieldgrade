# LLM Runtime (Laptop Mode)

Fieldgrade’s “laptop mode” runs an OpenAI-compatible LLM server that is **owned and controlled by Termite**.

The goal is one-button reliability:
- Termite can `start/stop/status/ping` a local OpenAI-compatible server.
- The active endpoint identity is persisted in `termite_fieldpack/runtime/llm/active_endpoint.json`.
- `termite llm chat` prefers the active endpoint when it is running.
- `mite_ecology llm-sync` can bind to the Termite endpoint via `endpoint_source: termite`.

## Quickstart

1) Edit `termite_fieldpack/config/termite.yaml`:

- Keep safe default (manual operator-run server):
  - `llm.provider: endpoint_only`
  - `llm.launch.enabled: false`

- Laptop mode:
  - Set `llm.launch.enabled: true`
  - Set `llm.model` (required)
  - Set `llm.host`/`llm.port` (defaults: `127.0.0.1:8789`)
  - Provide either:
    - `llm.launch.command` (recommended, cross-platform), or
    - `llm.provider: llama_cpp_server|vllm` to use a template command.

2) Start the server:

- `python -m termite.cli llm start`

3) Check status and readiness:

- `python -m termite.cli llm status --json`
- `python -m termite.cli llm ping`

4) Stop:

- `python -m termite.cli llm stop`

## Notes

- Readiness uses `GET /v1/models` (OpenAI-compatible).
- On Windows, stop uses a `taskkill` fallback to avoid stale PID state.
- The state file is written atomically to avoid partially-written JSON.
