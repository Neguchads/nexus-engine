# Runtime security verification

The pinned CodeQL workflow analyzes Python in nexus_engine using the default security query suite. It preserves SARIF and fails if results are missing, analysis reports an unsuccessful invocation, or any finding is reported. It does not suppress findings. It is intentionally restricted to shipped runtime; tests, benchmarks, workflows and build tooling need separate review.

The independent package inventory checks wheel member names, RECORD hashes, package identity and the absence of declared runtime dependencies. CI installs the exact wheel outside the checkout. No claim of signed provenance, full dependency vulnerability analysis, hostile filesystem isolation, penetration testing or independent human review is made.

Threat boundary: trusted single local owner, private filesystem and SQLite, no execution of model-supplied commands, explicit selected provider, content-bound approvals, no external replay, and optional local loopback inference. An untrusted model may return incorrect or malicious text; do not execute it automatically. Older binaries must not be used to write a newer database. External-provider usage counters remain reported values rather than a guaranteed pre-call spend limit.
