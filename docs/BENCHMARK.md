# Real-provider benchmark evidence protocol

Run from the checkout: python -m benchmarks.evaluate records.json

The evaluator accepts a list of paired records. Identity fields: task, class (simple/medium/complex), repeat, host, model, config_sha256, initial_sha256, prompt_sha256, budget. Measurement fields: mode (direct/nexus), passed (bool from independent verifier), latency_ms, input_tokens, output_tokens, recovered (bool). Hashes are lowercase SHA-256. Both arms must share the same identity. Use an independent pristine checkout for each arm, randomize order, preserve failures and specify verifier and interruption scenario in an external preregistration.

At least ten distinct tasks with three repetitions per class are required for the minimum sample. The report compares pass counts, recovery counts, median latency and total reported tokens per arm. It does not certify performance, attest to a model, validate underlying raw logs, or automatically approve a release. If actual usage is unavailable, do not fabricate a record. Record and investigate budget violations separately; this evaluator rejects them. No external records are included in this repository.
