# Independent Nexus acceptance plan

| Phase | Candidate work | Acceptance |
|---|---|---|
| 0 | Independent MIT repository | Established |
| 1 | Lite / adaptive routing | Synthetic verification |
| 2 | AAF-inspired DAG, queue, journal, output integrity | Legacy parity and feature-by-feature review pending |
| 3 | Unified SQLite persistence | Restart, concurrency and corruption fixtures; crash/stress/fencing pending |
| 4 | Budget and approval gates | External threat model, isolation, dependency and artifact audit pending |
| 5 | Single-host manual handoff | Native/authenticated host adapters and real acceptance pending |
| 6 | Lightweight execution and bounded context | Real token/context measurements and context strategy pending |
| 7 | Paired synthetic benchmark | Real engineering benchmark pending |
| 8 | CI OS matrix | Verify actual jobs and installed artifacts |
| 9 | Stable 1.0 | Blocked on prior acceptance and release process |
| 10 | NAVI adapter | Explicitly deferred; separate integration approval |

## AAF reuse policy

Reimplement the architectural ideas of DAGExecutor, TaskQueue, TaskStore, CompletionJournal, artifact integrity and reconciliation behind a single durable store. Do not import the private AAF runtime or publish its source. No unrestricted shell/Git handlers, global registry, automatic retries or mandatory vector databases. Current sequential engine does not claim legacy parallelism, file artifact access control, merge semantics or recovery parity.

## Real A/B protocol

Pre-register task classes and success criteria before running. Compare same provider, model, initial repository state, prompt, allowed tools and budget, with and without Nexus. At least 10 distinct tasks per class and 3 repetitions; randomize execution order. Record verified quality, latency, input/output tokens, cost, failures and recovery; preserve failures. Include injected interruptions and independent tests. Do not infer AI improvements from arithmetic fixtures. A real host can be approved independently; other providers are never prerequisites for using that host.

## Stable gate

All required tests pass on three OSs; reproducible installation and versioned artifacts; no unexpected dispatch, implicit fallback, ambiguous replay or budget accounting regression; externally reviewed security boundaries and license clearance; real host acceptance and demonstrated value on declared task classes; documented upgrade/rollback and recovery procedure. Integration into NAVI is a later independent decision.

The independent engine now exposes permanent abandonment and metadata-only evidence reports. This is a conservative reconciliation policy, not automatic crash recovery for external side effects.

A paired-record evaluator is implemented in benchmarks/evaluate.py. No real AI measurements were supplied. The evaluator checks matched identities and minimum sample size, not independent authenticity or statistical significance. See docs/BENCHMARK.md.

An experimental Ollama loopback transport is now implemented with mocked protocol tests. Real model inference and cross-provider native adapters remain acceptance gates; no cloud account is required for Core or the local transport.

Alpha 3 adds bounded fixture-only parallel frontiers and content-bound external approval. Real-provider parallelism remains out of scope. AAF file-artifact permissions, merge semantics, independent security review and stress remain pending.

Alpha 4 candidate adds strict JSON merge, logical dependency-scoped immutable file attachments, explicit context projection, integrity scans and sealed backup/restore for inspection. Full AAF equivalence, authenticated access, writable recovery and real token/quality gains are not claimed.

Alpha 5 adds database-format checks, real-inference benchmark tooling and a pinned workflow. Live model results are an experimental gate, not full repository-engineering acceptance.

Alpha 6 candidate adds deterministic-only operational recovery and a gated versioned preview distribution. External replay remains prohibited. Full engineering benchmark, independent audit, production-grade provider validation and NAVI adapter are still separate acceptance gates.

Alpha 7 candidate adds strict JSON parsing and canonical completion checks. Engineering evidence distinguishes full context, direct projected context, and Nexus projected context; repair selection is a bounded task, not arbitrary repository modification. Independent audit and real end-to-end agent engineering remain gates.
