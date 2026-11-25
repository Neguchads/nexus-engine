# Experimental local Ollama adapter

The optional adapter sends an explicitly approved single request to the fixed loopback endpoint 127.0.0.1:11434/api/generate. No provider installation, credentials, arbitrary URLs, redirects, tools, filesystem commands or model downloads. API contract: https://docs.ollama.com/api/generate .

Choose an already-installed local model tag in examples/ollama.json and review task/dependency content before dispatch. The model is part of the immutable node input. A local server is trusted and may itself relay requests; Nexus cannot attest offline inference or control server-side network access. Use an offline or egress-restricted server if necessary.

```sh
nexus-engine start examples/ollama.json --db local.db --run-id local
nexus-engine ollama-step --db local.db --run-id local --approve
nexus-engine audit --db local.db --run-id local
```

Each step reserves before HTTP. The adapter requests structured JSON and bounds output generation and payload sizes. Server-reported input/output counts settle the reservation only if valid. The output cap does not enforce the total pre-call token budget. Timeouts are socket-operation timeouts, not a guaranteed total inference deadline; incomplete, mismatched or over-budget responses remain unresolved. No retries. A server/model mismatch is not grounds for automatic fallback.

Mocked HTTP tests verify the protocol and fail-closed behavior. A real model execution is not yet qualified. Other hosts continue to use independent manual handoffs.
