# AAF behavioral review — independent Nexus scope

This is a capability mapping, not a line-by-line port, license clearance, or independent certification. The private AAF source remains excluded. Nexus implements its own narrow trusted-owner contract; adopting the complete legacy runtime is not required.

| Legacy architectural capability | Nexus implementation | Scope and evidence |
|---|---|---|
| DAGExecutor / WorkflowValidator | contracts.validate, engine.run | Validated dependency order, cycles and bounded deterministic frontiers; external calls sequential |
| TaskQueue / TaskStore | Store.next, reserve_batch, submit | Transactional local queue, pre-reservation, no implicit dispatch of ambiguous work |
| CheckpointStore / CompletionJournal | Store._load and audit | Canonical JSON, request/completion SHA-256, idempotent settlement; local integrity not adversarial attestation |
| ArtifactStore / ArtifactAccessController | Store.attach and artifact | Bounded immutable attachments, direct dependency scope; no authenticated multi-user ACL |
| MergeEngine | Store.merge | Conflict-rejecting JSON object merge only; no semantic source-code merge |
| Router / StopPolicy | contracts.route, validate, reservations | Lite/durable choice, explicit bounded accounting; no automatic token-budget guarantee from provider |
| Reconciler | abandon, snapshot, recover-fixtures | No silent retry; deterministic snapshot promotion only; external side effects are not rolled back |
| HITLGateway | preview and approval hash | Explicit content binding; trusted operator, not authenticated identity |
| EventLog / AutoAudit | audit, verify_all, CI | Metadata evidence, unit tests and static scan; not a full telemetry platform |
| SecretsVault, unrestricted shell/Git, global skill registry | Intentionally excluded | No credential store or model-supplied command execution in runtime |
| RAG / CourseProcessor / GC / OrphanDetector | Not adopted | Optional future integrations only when a measured need exists |

The prior selected AAF regression results are historical evidence for the original code, not Nexus parity. Current tests establish behavior within the declared independent contract. No claim that every legacy feature is implemented. The original runtime is not a mandatory dependency, and the future NAVI adapter remains out of scope.

Remaining acceptance: representative end-to-end engineering tasks, independent security review, one real selected-host engineering workflow, and review of rights/provenance before any original legacy code is distributed. The historical repair pilot is intentionally narrow and does not replace that evaluation.
