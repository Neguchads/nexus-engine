# Security policy

Research preview, intended for trusted operators and local private databases. Do not execute untrusted code or provide secrets. The default CLI executes the deterministic fixture; external requests are manual except for the explicit experimental Ollama step. No shell or dynamic plugin loading. Ollama HTTP is restricted to fixed loopback, without redirects or automatic retries.

Input/response JSON sizes are limited. Plans reject invalid DAGs and over-reservation. SQLite transactions serialize reservations; completed responses are bound to the request and hash. No automatic retry after ambiguity. Hashes detect accidental corruption, not malicious modification of the database and its hashes. The operator controls file permissions, backups and storage integrity. The host field is not authentication and token usage is operator-reported; reservations are not a billing guarantee.

No sandbox or OS process isolation is claimed. External input/output may contain prompt injection or sensitive data. Review it before any transfer or execution. Security audit, dependency and artifact provenance checks, process isolation and real host authorization remain production gates. Do not disclose private vulnerabilities in public issues; use GitHub private vulnerability reporting if enabled.

Abandonment permanently denies subsequent dispatch and submission; the outstanding reservation remains charged. Metadata-only audit excludes raw payloads but still reveals operational metadata and hashes; treat it as potentially sensitive.

The local Ollama server is trusted and may itself have network access. The adapter is not an offline-inference attestation or hard total-time/token cap. No remote endpoints are accepted. Only use a reviewed local model and explicit approval; model output remains untrusted data.

External dispatch requires a content-bound approval hash, not merely a boolean. It is not a secret, signature or authentication; trusted operator review remains mandatory. Fixture-only parallel batches reserve the whole ready frontier before execution. No automatic replay of a partially completed batch. Plans without workers keep their original fingerprints and single-worker behavior.

Artifact names are logical identifiers, not paths. Attachments are owner-imported and bound to a completed node; hashes verify integrity, not authorship. Logical consumer scope is checked against direct dependencies, not authenticated identity. A trusted owner can read all local data. Backups contain private payloads and are sealed against dispatch by this version; no automated restoration of external side effects. Store in private directories; no hostile filesystem or database threat model.

Alpha 5 rejects unrelated database tables and unsupported schema/application versions, and pins workflow dependencies to immutable action commits. It does not sandbox the host owner or a compromised SQLite file.

New local files use exclusive creation and owner-only POSIX mode, and databases must be regular files. Fixture-only snapshot promotion requires explicit confirmation and rejects external plans or unsettled reservations. Preview release publication is a separate main-only job after the verification matrix, with a scoped contents-write token and no overwrite. These controls do not certify hostile-host isolation.

Alpha 7 rejects duplicate JSON keys and non-finite constants at input, storage and model-response boundaries. Completion idempotency uses canonical JSON equality, distinguishing booleans from integers. These are local integrity controls, not independent audit sign-off.

The optional Codex trace importer reads a bounded local JSONL file, rejects failed or ambiguous turns and binds the normalized answer to an existing reserved request. It never executes a provider or accesses credentials. CLI logs are operator-provided and not cryptographically attested.
