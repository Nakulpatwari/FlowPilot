# FlowPilot Architecture

## 1. Design objective

FlowPilot is a focused prototype of an autonomous company operator. Its first supported business capability is invoice processing.

The system accepts a task, executes a constrained workflow using registered tools, applies application-owned policy checks, pauses for human approval when required, and verifies persisted outcomes.

The runtime and tool interface are separated so additional business capabilities can be introduced without rewriting the entire orchestration layer.

The current implementation is a synchronous, single-workflow prototype rather than a general-purpose autonomous employee platform.

## 2. Execution lifecycle

1. **Goal intake:** The API validates the task request and optional document name.
2. **Planning:** Task interpretation produces a constrained execution plan.
3. **Document reading:** The document tool reads an allowed file from the sample-data directory.
4. **Extraction:** The invoice extraction tool produces structured invoice fields.
5. **Duplicate detection:** The runtime checks whether the vendor and invoice number already exist.
6. **Policy evaluation:** Application-owned rules determine whether a write is permitted and whether approval is required.
7. **Approval checkpoint:** If required, the task is persisted as `awaiting_approval` and execution pauses.
8. **Authorized execution:** After approval, the runtime attempts the invoice write. Selected transient database errors receive bounded retries.
9. **Independent verification:** The runtime queries the database again and compares persisted fields with the extracted values.
10. **Reporting:** The task result, status, and audit events expose what happened and whether verification succeeded.

A duplicate invoice can complete without another write when an existing record is found and verified. Invalid documents and denied operations follow failure paths rather than being reported as successful writes.

## 3. Component responsibilities

| Component | Responsibility |
|---|---|
| `app/main.py` | FastAPI routes, dependency setup, dashboard hosting, task and approval endpoints |
| `app/runtime.py` | Task lifecycle, duplicate checks, policy evaluation, approval handling, bounded retries, database verification, audit events |
| `app/tooling.py` | Explicit tool registry, required-argument validation, permission checks and tool descriptions |
| `app/policy.py` | Deterministic invoice-write policy and approval threshold |
| `app/agent.py` | Document reading, invoice extraction and optional Ollama-based intent interpretation |
| `app/browser_tool.py` | Optional Playwright browser-inspection connector with a local-host allowlist |
| `app/models.py` | SQLAlchemy models for tasks, invoice records and audit events |
| `app/schemas.py` | Pydantic request validation |
| `app/db.py` | Database engine, sessions and schema initialization |
| `app/static/index.html` | Operator dashboard |

## 4. Tool execution and permissions

Tools are registered explicitly rather than generated as arbitrary executable code.

Each tool declares its identifier, required arguments and permission requirements. The registry validates inputs and checks the caller's permission set before dispatching the operation.

The invoice workflow uses registered document-reading and extraction tools. Invoice persistence and policy evaluation remain controlled by the runtime and policy layer.

The optional browser connector is separate from the core invoice workflow. Its presence does not imply that FlowPilot can autonomously operate arbitrary websites or external company systems.

## 5. Policy and human approval

Invoice-write policy is enforced by application code, not delegated to the language model.

The policy evaluates whether a write is allowed and whether the configured approval threshold has been reached. When approval is required, the task stores its `awaiting_approval` status and approval reason before returning control to the reviewer.

The approval endpoint checks that the task is awaiting approval. Rejection records the decision without writing the invoice. Approval records the decision and resumes the invoice-write and verification path.

The current reviewer identity is a demo value, not production authentication. Real deployments require authenticated identities, authorization checks and auditable approval permissions.

## 6. Persistence, duplicate prevention and verification

FlowPilot stores task state, invoice records and audit events using SQLAlchemy. Docker Compose runs PostgreSQL; automated tests use an isolated SQLite database.

Before creating an invoice, the runtime checks for an existing record using normalized vendor identity and invoice number. A database uniqueness constraint provides an additional safeguard against duplicate writes.

After a successful write, FlowPilot performs an independent database read-back. It checks key fields, including vendor, invoice number, amount and due date, and marks the operation successful only when the required checks pass.

A duplicate path similarly verifies the existing record before completing the task.

The application records significant lifecycle events, including task creation, document reading, extraction, duplicate detection, policy evaluation, approval, retries, writes, verification and completion or failure.

## 7. Failure handling

The runtime handles several expected failure cases:

- Missing documents and invalid extraction inputs produce a failed task with an error message.
- Duplicate invoices are handled without an additional write.
- Selected transient database errors receive a bounded retry with a short delay.
- Database uniqueness violations are checked for an existing matching record.
- A missing or mismatched persisted record causes verification to fail rather than being reported as a successful write.

The current retry mechanism is limited to selected database operations. It is not a general retry framework for every tool or failure type. The runtime is synchronous and does not provide durable background execution or automatic recovery after process termination.

## 8. Safety boundaries

- Only explicitly registered tools can be invoked by the runtime.
- Arbitrary model-generated Python, shell commands and unrestricted code execution are not supported.
- Document access is restricted to the configured sample-data directory.
- Browser inspection is restricted to an allowlist of local hosts.
- Invoice-write policy and approval decisions are enforced by application code.
- Documents are treated as untrusted data, not as instructions that can override system policy.
- The prototype uses a local finance sandbox and does not execute payments or connect to real company systems.

These boundaries reduce risk in the demo environment but do not constitute a complete production security model.

## 9. Design trade-offs

**Synchronous execution:** Keeps the workflow simple to inspect and debug. Production operation would require durable workers, leases, recovery and idempotent
