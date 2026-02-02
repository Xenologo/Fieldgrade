# Fieldgrade review (OpenClaw lens + Larval AGI framing)

Date: 2026-02-02

This document captures an architectural review of **Fieldgrade** through the **OpenClaw** lens (Mites, Memites, MetaMites) and the proposed **Larval AGI** framework. It highlights existing strengths, identifies functional gaps, and suggests how the repo could evolve into a dynamical “larval” agent with open-ended learning and localized convergence.

---

## 1. Observations from the codebase

### 1.1 Modular packaging

- The monorepo is split into **termite_fieldpack**, **mite_ecology**, **fieldgrade_ui**, and **schemas/resources**. This layered structure already suggests a natural **hardware / ecology / interface** separation.
- **Termite Fieldpack** acts as a ingestion and bundle–sealing engine: it ingests files into a content-addressed store, produces **hash-chained provenance** and **deterministic, signed bundles**. It is a good candidate for **observational Mites** (sensing and recording environment changes).
- **Mite Ecology** imports sealed bundles, applies deterministic GNN embeddings, GAT attention, motif mining, and a genetic algorithm to evolve **neuroarch genomes**. This could map to **transformation Mites** or **Memites** for processing and expanding the knowledge graph.
- **StudSpec** and **TubeSpec** schemas (in `mite_ecology/specs.py` and `termite_fieldpack/termite/specs.py`) provide standardized descriptions of “Memites” or “tools”—they specify `kind`, I/O schemas, determinism levels, resource constraints and dependencies. This is a key infrastructure component: a **compatibility contract** for building plug-and-play skills (Mites).

### 1.2 Determinism and reproducibility

- Deterministic replay is a central principle: Termite produces sealed bundles, and Mite Ecology replays them, ensuring **identical on-disk artefacts** when inputs and environment are the same. This matches OpenClaw’s emphasis on **verifiable executions** and facilitates later “freeze-core” operations in Larval AGI.
- The run_demo script shows end-to-end ingestion → seal → verify → import with multiple modes (AUTO_MERGE, REVIEW_ONLY, QUARANTINE); the review process encourages human oversight, akin to how a MetaMite might orchestrate approvals.

### 1.3 Platform coverage and UI

- Termux and Windows guides offer step-by-step instructions for running the pipeline on Android, WSL2, or native PowerShell. Combined with a FastAPI UI exposing registry and KG query endpoints, this matches OpenClaw’s “gateway” layer, albeit without dynamic control loops.

---

## 2. Mapping to OpenClaw’s Mites, Memites, MetaMites

| OpenClaw concept | Evidence in Fieldgrade | Gaps / areas for extension |
| --- | --- | --- |
| **Mites** (atomic tools) | Termite ingest / seal; Mite-Ecology embedding, GAT, GA; CLI commands. Each stage can be viewed as a Mite. | Lacks standardized call signatures for screen capture, UI interaction or low-level OS actions needed for computer-use agents. No explicit SoM/ARIA overlay or concurrency control yet. |
| **Memites** (assemblies specifying I/O, constraints) | `StudSpec` and `TubeSpec` define schema-based contracts for “Memite” units, with fields for I/O, determinism, resource limits and dependencies. | Need a runtime that reads these specs to dynamically load and execute Mites. Need a versioned Memite registry and enforcement engine, similar to OpenClaw’s tool registry and policy gating. |
| **MetaMites** (planners/critics/schedulers) | The repository currently lacks explicit planning or arbitration layers. The run_demo script orchestrates a pipeline, but there is no agentic reasoning or safety policy. | Introduce a **MetaMite Planner** that can decompose high-level goals into sequences of Memites (e.g., ingest → import → run GNN → mine motifs), schedule them, enforce safety constraints, and verify outcomes. A **Critic MetaMite** could ensure determinism, check resource budgets, and gate destructive actions. |

---

## 3. Gaps relative to an OpenClaw-style agent

1. **Lack of a real-time observation loop** – Termite ingests static files; there is no screen capture, UI interaction or continuous environment sampling. To emulate OpenClaw’s “Observe–Reason–Act” cycle, one needs Mites for capturing screenshots (or ARIA trees), building SoM overlays, and feeding them to a vision-language model.
2. **No unified actuation layer** – Fieldgrade does not provide Mites to act on an operating system (mouse clicks, keyboard input, ADB commands). Therefore, it cannot perform tasks like “open a browser and click a button,” which OpenClaw performs via Windows SendInput or Android ADB.
3. **Absence of a planner and critic** – There is no orchestrator to reason about multi-step plans, evaluate sub-goals, or enforce kill-switches and policy constraints. The run_demo script is deterministic but manual.
4. **No concept of a growing skill library** – Although Mite Ecology uses motifs and genetic algorithms, it does not store or reuse learned skills. An OpenClaw-style agent would compile successful skills into a library (Voyager-like) for future retrieval.

---

## 4. Bringing in the “Larval AGI” concept

The larval AGI described here is a dynamical, self-curriculum learner with localized plastic parameters. Building on Fieldgrade’s deterministic framework:

1. **Stable core vs. plastic modules** – Fieldgrade already enforces determinism via a frozen base (sealed bundles and deterministic pipelines). To implement localized plasticity, one could augment Mite-Ecology with adapter modules or LoRA layers that are updated per task while keeping the core models immutable.
2. **Goal generation and novelty** – Introduce a MetaMite goal generator that proposes tasks based on the KG’s current knowledge gaps, measuring novelty and learnability using metrics on the graph. The open-endedness utility could combine novelty (e.g., new graph motifs) with ease of assimilation into the KG.
3. **Skill library and reuse** – After completing a pipeline run, encapsulate the resulting motif/genome as a skill Memite, store it with regression tests and metadata (akin to Voyager’s skill library), and update the Memite registry.
4. **Memory and replay** – Leverage Fieldgrade’s CAS and replay logs as the memory component ($\mathcal{M}_t$), ensuring that the larva can revisit past bundles or replay KG deltas. Use rehearsal (re-importing bundles or re-running pipelines) to prevent forgetting when new Memites are added.
5. **Stabilizers** – Integrate EWC/SI or gradient-orthogonalization mechanisms into any trainable component to protect prior competencies. The deterministic environment helps by providing fixed training data; replay mechanisms would complement this.

---

## 5. Suggested roadmap to evolve Fieldgrade into a Larval agent with Mites/Memites/MetaMites

1. **Implement an Agent Gateway**: Build a Memite registry and loader that uses the existing `StudSpec`/`TubeSpec` definitions to discover Mites, enforce constraints (determinism, resource limits), and expose them via a common API.
2. **Add Observation and Actuation Mites**: Create wrappers around Windows and Android APIs (SendInput, ADB) and screen-capture libraries. Each wrapper should conform to the StudSpec contract, include an SoM/ARIA overlay, and support kill-switch semantics.
3. **Introduce a Planner/Critic MetaMite**: This MetaMite would accept a high-level goal, consult the Memite registry, plan sequences (ingest → generate plan → run LL model → act), monitor progress, and pause/rollback on drift. The critic enforces policy (e.g. forbidding external network calls) and determinism.
4. **Create a Goal Generator**: Use language models (possibly running via Termite’s LLM runtime interface) to propose self-generated goals. Combine novelty (e.g. new KG motifs) with learnability when selecting which goal to pursue.
5. **Embed Localized Learning**: When training new models or adapters, restrict updates to plastic parameters (LoRA/adapter modules), leaving base weights unchanged. Log and hash those updates for reproducibility and later transfer.
6. **Build a Skill Library**: After a successful run, compile the pipeline into a new Memite with test coverage. Index by retrieval keys (graph motifs, input domains) and reuse in future plans.

---

## Final thoughts

Fieldgrade already excels at deterministic ingestion and KG synthesis; this makes it a solid foundation for an OpenClaw-style agent. However, to reach a full Larval AGI—an open-ended, self-driven learner with localized convergence—it needs an interactive observation/action loop, a planning and criticism layer, and mechanisms for local plasticity and skill consolidation.
