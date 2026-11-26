# Nexus Engine

**Adaptive Agent Orchestration Engine** — MIT-licensed standalone research preview, v0.1.0a10.

Nexus provides lightweight deterministic execution and a durable DAG journal with single-provider selection. It does not require NAVI, an AI subscription or a provider SDK. The standard library is the only runtime dependency.

## Quick start

Python 3.11+:

```sh
python -m pip install .
nexus-engine plan examples/simple.json
nexus-engine run examples/simple.json
nexus-engine run examples/durable.json --db state.db --run-id demo
nexus-engine run examples/durable.json --db state.db --run-id demo
python -m unittest discover -s tests -v
python -m benchmarks.compare
```

Lite skips SQLite for one-node deterministic tasks without resume. Durable validates a DAG, binds reservations to a run and node, records outputs and verifies hashes on recovery. Unsettled requests are never automatically dispatched again. The database must be owner-controlled and private.

## External agents

Codex, Claude Code, Gemini, Copilot and Ollama are **alternative manual handoff identities**, not installed or authenticated integrations. Codex, Claude Code, Gemini and Copilot use manual handoffs. Ollama also has an experimental, explicit loopback adapter. No provider switching. See [handoff protocol](docs/HANDOFF.md).

## Project status

- Implemented candidate: adaptive fixture path, durable DAG with optional bounded deterministic parallelism, reservations, transactional journal, integrity checks, explicit manual handoffs and synthetic benchmark.
- CI tests Windows, Linux and macOS; refer to the exact release's verification results.
- No untrusted code sandbox, authenticated cloud integrations, verified token billing or production certification.
- AAF Core and Nexus Engine are original projects developed by Gustavo (Neguchads). Nexus draws on architectural experience from the author's own AAF Core; the private AAF Core implementation is not distributed. See [AAF capability review](docs/AAF-PARITY.md) for the supported scope.
- NAVI integration is intentionally deferred and must remain optional.

See [acceptance gates](docs/ROADMAP.md) and [security](SECURITY.md).

Use `nexus-engine audit --db state.db --run-id demo` for metadata-only evidence. Permanently stop an ambiguous run with `abandon --reason ... --confirm`; uncertainty remains charged and is never replayed. See handoff documentation.

Real-provider evaluation has a paired-record validator: `python -m benchmarks.evaluate records.json`. See [measurement protocol](docs/BENCHMARK.md). It consumes operator-supplied data; it does not call a model or claim measured token savings.

See [optional local Ollama adapter](docs/OLLAMA.md) for the experimental HTTP path. Real Ollama pilots verify transport/accounting; the 0.5B quality gate failed, while 7B controlled pilots passed. See benchmark documentation for limitations.

Optional `workers` in a fixture plan (1–8) enables parallel execution of ready DAG nodes with atomic batch reservations. External agents always remain sequential. Alpha 3 also requires an explicit preview hash for external dispatch; existing stored plan fingerprints are preserved.

Alpha 4 adds explicit dependency-field projection, conflict-rejecting JSON merge, immutable bounded file attachments, database verification and sealed backups. See [data operations](docs/DATA.md). These are owner-controlled local mechanisms, not multi-user authentication or proof of artifact origin. Snapshots are inspection-only to prevent replay from stale state.

Alpha 5 adds database version marking, pinned CI actions, and an isolated real-inference experiment. The experiment is not production certification; inspect the evidence report and its scope.

Alpha 6 adds explicit fixture-only backup promotion, private new database/export creation and a main-only prerelease workflow that publishes the exact tested wheel after the six-platform CI matrix passes. External snapshots remain sealed and no stable certification is implied.

Alpha 7 hardens JSON parsing and completion equality, and introduces release-package inventory and a controlled repair-selection benchmark with a matched projected-context control.

For a locally authorized Codex CLI session, the optional codex-import command settles a reviewed single-turn JSONL trace using CLI-reported usage. Nexus never starts Codex, accesses its account or switches providers. See docs/HANDOFF.md.

Alpha 9 adds a CLI version command, rejects overflowed JSON numbers, and tests upgrades from exact released alpha 6 and alpha 8 wheels with isolated deterministic rollback and uninstall checks. See docs/DATA.md and CI evidence; no external-provider rollback is supported.

[Open-source credits, provenance and distribution review](CREDITS.md).

Alpha 10 consolidates the author credits, license notices, historical source repair evidence, and same-revision security/upgrade gates before prerelease publication. The current scope is a trusted-owner local orchestration research preview, not a general autonomous coding agent or sandbox.
