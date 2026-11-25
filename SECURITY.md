# Security policy

Research preview, intended for trusted operators and local private databases. Do not execute untrusted code or provide secrets. The CLI executes only the deterministic fixture; external requests are manual. There is no shell, dynamic plugin loading, network access or automatic provider execution.

Input/response JSON sizes are limited. Plans reject invalid DAGs and over-reservation. SQLite transactions serialize reservations; completed responses are bound to the request and hash. No automatic retry after ambiguity. Hashes detect accidental corruption, not malicious modification of the database and its hashes. The operator controls file permissions, backups and storage integrity. The host field is not authentication and token usage is operator-reported; reservations are not a billing guarantee.

No sandbox or OS process isolation is claimed. External input/output may contain prompt injection or sensitive data. Review it before any transfer or execution. Security audit, dependency and artifact provenance checks, process isolation and real host authorization remain production gates. Do not disclose private vulnerabilities in public issues; use GitHub private vulnerability reporting if enabled.
