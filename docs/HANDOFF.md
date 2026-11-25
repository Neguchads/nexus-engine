# Manual provider protocol

The operator selects exactly one host in the plan, with a bounded per-node reservation. External host names identify a protocol choice, not authentication. A handoff creates a persistent request before emitting any payload. The user must review the input and explicitly approve each release. Do not put secrets in a plan. Use a trusted local directory.

```sh
nexus-engine start examples/external.json --db state.db --run-id external
nexus-engine next --db state.db --run-id external --approve
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
