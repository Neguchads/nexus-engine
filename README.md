# Nexus Engine

**Adaptive Agent Orchestration Engine** — MIT-licensed standalone research preview, v0.1.0a4.

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
- CI targets Windows, Linux and macOS. Check actual results before claiming OS support.
- No untrusted code sandbox, authenticated cloud integrations, verified token billing, real AI benchmark or production certification.
- The private AAF implementation is not distributed. Useful architectural patterns are reimplemented here; legacy parity remains to be measured.
- NAVI integration is intentionally deferred and must remain optional.

See [acceptance gates](docs/ROADMAP.md) and [security](SECURITY.md).

Use `nexus-engine audit --db state.db --run-id demo` for metadata-only evidence. Permanently stop an ambiguous run with `abandon --reason ... --confirm`; uncertainty remains charged and is never replayed. See handoff documentation.

Real-provider evaluation has a paired-record validator: `python -m benchmarks.evaluate records.json`. See [measurement protocol](docs/BENCHMARK.md). It consumes operator-supplied data; it does not call a model or claim measured token savings.

See [optional local Ollama adapter](docs/OLLAMA.md) for the experimental HTTP path. Real inference is not yet verified.

Optional `workers` in a fixture plan (1–8) enables parallel execution of ready DAG nodes with atomic batch reservations. External agents always remain sequential. Alpha 3 also requires an explicit preview hash for external dispatch; existing stored plan fingerprints are preserved.

Alpha 4 adds explicit dependency-field projection, conflict-rejecting JSON merge, immutable bounded file attachments, database verification and sealed backups. See [data operations](docs/DATA.md). These are owner-controlled local mechanisms, not multi-user authentication or proof of artifact origin. Snapshots are inspection-only to prevent replay from stale state.
