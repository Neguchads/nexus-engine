# Local data operations

All operations are for a trusted single owner, in private local directories. No path is supplied by an AI response. The DB is not an authorization sandbox.

- Attach a file to a completed node (max 1 MiB per file, 32 per run): nexus-engine attach A evidence input.bin --db state.db --run-id demo. Names are logical IDs, not paths. Conflicting replacement fails.
- Extract to a new file only: nexus-engine artifact A evidence output.bin --db state.db --run-id demo. Optional --consumer B checks that B directly depends on A. This is a logical policy, not authenticated access control.
- Merge completed JSON object outputs: nexus-engine merge A B --db state.db --run-id demo. Conflicting values are rejected; provenance lists source completion hashes. Does not edit files or execute code.
- For external provider nodes only, optional immutable context: {"select":{"A":["summary"]},"max_bytes":4096}. Explicit projection omits unselected predecessor fields; unknown requested keys or over-limit projections fail before dispatch. nexus-engine context --db state.db --run-id demo reports encoded byte counts, not token savings.
- Verify database: nexus-engine verify-db --db state.db.
- Snapshot: nexus-engine backup copy.db --db state.db. Restore for inspection: nexus-engine restore recovered.db --db copy.db. Neither overwrites an existing path. Both copies are sealed against new reservations, completions, new runs and artifact writes in alpha 4. The primary remains authoritative; no automatic promotion or rollback of external effects. Backups include all sensitive data. Keep them access-controlled; do not upload them.

Old plans without context retain their original fingerprints. Alpha 4 adds tables on opening older databases. Upgrade a private copy first; a sealed backup is evidence, not a runnable rollback. Do not open an alpha 4 database with an older binary for execution.

Alpha 5 assigns SQLite application_id 1313167445 and user_version 1 when opening a recognized legacy or new database. Future versions and unrelated tables are rejected. Back up privately before upgrade; older binaries do not enforce new-version safeguards.

Alpha 6 supports `nexus-engine recover-fixtures recovered.db --db copy.db --confirm`. Only a verified sealed snapshot with exclusively fixture plans and no outstanding reservation can be promoted into a new database. The source is unchanged. Never promote external-provider history; external snapshots are inspection-only. New databases and extracted files are created with owner-only mode on POSIX; existing database ACLs and Windows directory permissions remain the operator's responsibility.
