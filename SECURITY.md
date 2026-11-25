# Security policy

Research preview, intended for trusted operators and local private databases. Do not execute untrusted code or provide secrets. The default CLI executes the deterministic fixture; external requests are manual except for the explicit experimental Ollama step. No shell or dynamic plugin loading. Ollama HTTP is restricted to fixed loopback, without redirects or automatic retries.

Input/response JSON sizes are limited. Plans reject invalid DAGs and over-reservation. SQLite transactions serialize reservations; completed responses are bound to the request and hash. No automatic retry after ambiguity. Hashes detect accidental corruption, not malicious modification of the database and its hashes. The operator controls file permissions, backups and storage integrity. The host field is not authentication and token usage is operator-reported; reservations are not a billing guarantee.

No sandbox or OS process isolation is claimed. External input/output may contain prompt injection or sensitive data. Review it before any transfer or execution. Security audit, dependency and artifact provenance checks, process isolation and real host authorization remain production gates. Do not disclose private vulnerabilities in public issues; use GitHub private vulnerability reporting if enabled.

Abandonment permanently denies subsequent dispatch and submission; the outstanding reservation remains charged. Metadata-only audit excludes raw payloads but still reveals operational metadata and hashes; treat it as potentially sensitive.

The local Ollama server is trusted and may itself have network access. The adapter is not an offline-inference attestation or hard total-time/token cap. No remote endpoints are accepted. Only use a reviewed local model and explicit approval; model output remains untrusted data.
