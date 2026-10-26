# FlowPilot architecture

## Design objective

Demonstrate a small but real autonomous company operator. The invoice workflow is the first supported business capability; the runtime and tool interface are separated so more workflows can be added without rewriting orchestration.

## Execution lifecycle

1. **Goal intake** — validate the user's request and resolve a supported document.
2. **Plan** — create a constrained sequence of tool operations.
3. **Policy check** — apply application-owned permissions and approval thresholds. The model cannot bypass these checks.
4. **Execute** — call tools through a registry with declared input requirements and permission labels.
5. **Observe** — persist structured outputs and audit events after each important operation.
6. **Adapt** — handle duplicate records, invalid documents and selected transient database failures.
7. **Approval** — persist an `awaiting_approval` checkpoint before a sensitive write.
8. **Verify** — independently query the finance database and compare persisted fields with extracted values.
9. **Report** — return task state, record ID, verification checks and audit evidence.

## Components

- `app/main.py`: FastAPI routes and dashboard hosting.
- `app/runtime.py`: task lifecycle, persistence, retry, approval/resume and verification.
- `app/tooling.py`: reusable tool registry, required-argument checks and permission checks.
- `app/policy.py`: deterministic policy decision for invoice writes.
- `app/agent.py`: sandboxed document reader, extraction and optional Ollama intent interpretation.
- `app/browser_tool.py`: optional Playwright connector restricted to local/allowlisted hosts.
- `app/models.py`: tasks, invoice records and audit events in SQLAlchemy.
- `app/static/index.html`: operator dashboard.

## Safety boundaries

- Tools are registered explicitly; arbitrary model-generated Python or shell commands are never executed.
- File access is restricted to the configured sample-data directory.
- Browser navigation is restricted to an allowlist of local hosts.
- High-value writes pause for human approval.
- Duplicate writes are guarded by application checks and a database uniqueness constraint.
- Documents are untrusted data, not instructions.
- The prototype does not connect to real company systems or payment rails.

## Deliberate trade-offs

- Synchronous execution keeps the prototype small and inspectable; production needs durable workers and leases.
- Deterministic invoice parsing keeps tests reproducible; model extraction needs schema validation and evaluation before use.
- PostgreSQL is used in Docker, while tests use isolated SQLite.
- Ollama is optional and never controls authorization or verification.

## Production work not yet done

Authentication/authorization for real users, tenant isolation, secret management, durable background workers, schema migrations, observability, rate limits, prompt-injection testing, OCR, policy versioning, and production-grade evaluation.
