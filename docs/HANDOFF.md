# Manual provider protocol

The operator selects exactly one host in the plan, with a bounded per-node reservation. External host names identify a protocol choice, not authentication. A handoff creates a persistent request before emitting any payload. The user must review the input and explicitly approve each release. Do not put secrets in a plan. Use a trusted local directory.

```sh
nexus-engine start examples/external.json --db state.db --run-id external
nexus-engine preview --db state.db --run-id external
# Review the payload and copy its approval_sha256:
nexus-engine next --db state.db --run-id external --approve --approval-sha256 REVIEWED_HASH
```

Manually deliver the displayed JSON to the chosen provider only. Ask it for JSON with exactly these fields: request_id (copy from request), host (copy from request), output (JSON result), usage (integer total reported tokens, not synthetic). If reliable usage is unavailable, do not invent a number; the reservation remains unresolved. The operator verifies result, identity and usage outside Nexus.

Save the reviewed response to answer.json and submit:

```sh
nexus-engine submit answer.json --db state.db --run-id external
nexus-engine status --db state.db --run-id external
```

A second identical submission is idempotent. A conflicting response or incorrect identity is rejected. A pending request cannot be dispatched again. Preserve the original request securely; if it was lost, stop and reconcile manually rather than creating a replacement run that repeats side effects. The protocol does not prove the host actually ran or enforce its token cap. No remote API, subprocess, credentials, provider installation or fallback is implemented.

Future adapter: versioned capabilities, exact model/config identity, scoped permission per invocation, cancellation and timeout, resource accounting, and deterministic result verification. Use one approved host. No NAVI-specific imports.

## Reconciliation

`nexus-engine audit --db state.db --run-id external` provides hashes, reservation and completion states without task payloads. If an outstanding request cannot be reconciled from the original response, `nexus-engine abandon --db state.db --run-id external --reason "outcome unknown" --confirm` permanently stops the run. This does not cancel or roll back the external operation or release its reservation. Never use a new run ID as a workaround for an unknown side effect.

Approval is bound to the exact run, plan, node, inputs, dependency outputs and reservation. An approval hash is not an authentication credential. A trusted human must review the preview before dispatch; the engine rejects mismatched or stale hashes. External providers remain strictly sequential.

## Optional Codex CLI trace import

The Codex CLI documents structured JSONL via codex exec --json and usage in turn.completed (https://developers.openai.com/blog/eval-skills). After reviewing and reserving a Codex request with preview/next, use your own authenticated CLI in an isolated trusted workspace, with read-only sandbox and no secrets in the prompt. Ask Codex to return only JSON with request_id copied from the reserved request and output containing the result. Redirect JSONL stdout to a private UTF-8 trace file. Review the complete trace and successful process exit before importing:

    nexus-engine codex-import trace.jsonl --db state.db --run-id external --confirm

The importer requires exactly one complete successful turn, checks the final agent JSON and request ID, and uses input_tokens + output_tokens reported by the CLI (cached and reasoning counts are not added a second time). It rejects malformed or ambiguous traces, conflicting request IDs, and over-budget completion through Store.submit. Only the normalized result is persisted; raw trace remains in your private file. The importer does not execute Codex, grant account permissions, authenticate a trace, guarantee billing or enforce the provider's tool sandbox. The trace may contain sensitive content. Do not share it publicly. Native execution remains operator-controlled. Other agents retain independent JSON handoffs.
