# FlowPilot — Autonomous Company Operations Agent

**A local-first AI employee prototype that executes finance workflows, enforces human approval, and verifies outcomes.**

FlowPilot turns a natural-language request into an inspectable execution workflow. It reads invoice documents, extracts structured information, checks for duplicates, applies approval policies, writes to a PostgreSQL-backed finance sandbox, and independently verifies the persisted result.

Rather than stopping at a generated plan, FlowPilot attempts the operation, records its decisions, and reports whether the outcome was verified.

## Why FlowPilot?

AI employees need more than language generation. They need to use tools, respect permissions, handle failures, involve humans at the right moments, and prove that actions succeeded.

FlowPilot explores these requirements through a focused, runnable invoice-operations workflow.

### Key capabilities

- **Task intake and planning:** Accepts a natural-language request and creates an explicit execution plan.
- **Document processing:** Extracts invoice fields from supported text documents and text-based PDFs.
- **Registered tools:** Exposes tools with declared arguments and permission requirements.
- **Policy enforcement:** Applies invoice-write rules outside the language model.
- **Human-in-the-loop approval:** Pauses high-value invoice writes until a reviewer approves or rejects the task.
- **Duplicate prevention:** Checks existing records and uses database uniqueness constraints as a final safeguard.
- **Independent verification:** Reads persisted data back from the database and checks key fields before marking a write successful.
- **Auditable execution:** Persists task states and events for extraction, policy decisions, approvals, writes, retries, verification, and completion.
- **Optional local LLM:** Supports Ollama-based task interpretation; deterministic parsing remains the default.
- **Dockerized environment:** Runs the API and PostgreSQL using Docker Compose.

## Execution lifecycle

```text
Natural-language request
          |
          v
    Understand task
          |
          v
   Create execution plan
          |
          v
    Read invoice document
          |
          v
    Extract invoice fields
          |
          v
     Check for duplicate
          |
          v
    Evaluate write policy
          |
          v
  Approval required? ---- Yes ---> Await human decision
          |                           |
          No                     Approve / Reject
          |                           |
          +---------------------------+
                      |
               If authorized
                      |
                      v
             Write finance record
                      |
                      v
          Read back from database
                      |
                      v
          Verify persisted fields
                      |
                      v
             Record final outcome
```

Rejected, invalid, or unverified operations must not be represented as successful completion. Duplicate invoices can complete without another write when the existing record is found and verified.

## Architecture

```text
Dashboard / REST API
         |
         v
      FastAPI
         |
         v
    Task runtime
         |
         +---- Task interpretation
         |
         +---- Tool registry
         |       +-- Document reader
         |       +-- Invoice extractor
         |       +-- Optional browser inspection
         |
         +---- Policy and approval gate
         |
         +---- Invoice persistence
         |
         +---- Independent verification
         |
         +---- Audit events
                    |
                    v
               PostgreSQL
```

**Technology stack**

| Component | Technology |
|---|---|
| API | Python, FastAPI |
| Persistence | PostgreSQL, SQLAlchemy |
| Local tests | SQLite, pytest |
| Containerization | Docker, Docker Compose |
| Validation | Pydantic |
| Optional LLM | Ollama |
| Optional browser connector | Playwright |

The current task runtime is synchronous. The optional browser-inspection tool is registered separately and is not required by the invoice workflow.

## Quick start

### Prerequisites

- Windows with Docker Desktop, or another environment supporting Docker Compose
- Git, if cloning the repository

### 1. Clone the repository

```bash
git clone https://github.com/Nakulpatwari/FlowPilot.git
cd FlowPilot
```

### 2. Configure the environment

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Review `.env` and use local development values only. Never commit `.env` or real credentials.

### 3. Start the application

```powershell
docker compose up --build
```

If local port `5432` is already occupied, change only the host-side PostgreSQL port mapping in `docker-compose.yml`, for example from `5432:5432` to `5433:5432`. Keep the internal database connection pointed at the Compose service on port `5432`.

### 4. Open FlowPilot

- Dashboard: http://localhost:8000
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- Registered tools: http://localhost:8000/api/tools

### 5. Try the demo

Submit the following request through the dashboard:

`Process the latest invoice from Acme Supplies`

Follow the task status and execution events. Depending on the invoice and configured policy, the task may complete, identify an existing record, fail validation, or pause for approval.

Stop the application with `Ctrl+C`. To stop and remove the containers while preserving the database volume:

```powershell
docker compose down
```

To delete the local demo database volume as well, use `docker compose down -v`. **This is destructive and removes persisted database data.**

## Run the automated tests

The tests use an isolated SQLite database and do not require a running PostgreSQL instance.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./test_flowpilot.db"
python -m pytest tests -v
```

If PowerShell blocks virtual-environment activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The current test suite contains nine tests covering high-value approval, duplicate handling, rejection, missing required invoice information, audit persistence, tool permissions, policy enforcement, and tool discovery.

In the development session, all nine tests passed locally. Results may differ across environments or code changes; run the suite to verify the current checkout.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/tools` | Inspect registered tools |
| GET | `/api/invoices` | List finance sandbox records |
| GET | `/api/tasks` | List execution tasks |
| GET | `/api/tasks/{task_id}` | Inspect a task |
| POST | `/api/tasks` | Submit a task |
| POST | `/api/tasks/{task_id}/approve` | Approve a pending write |
| POST | `/api/tasks/{task_id}/reject` | Reject a pending write |
| GET | `/api/tasks/{task_id}/events` | Inspect the audit trail |
| POST | `/api/demo/reset` | Clear invoice records in the demo sandbox |

Example request:

```json
{
  "request": "Process the latest invoice from Acme Supplies",
  "document_name": "acme_invoice.txt"
}
```

## Reliability and safety

FlowPilot includes several safeguards:

- **Approval boundary:** Invoice writes above the configured threshold pause for human approval.
- **Duplicate checks:** Existing records are checked before a new invoice is created.
- **Database constraint:** A uniqueness constraint provides an additional duplicate safeguard.
- **Bounded retries:** Selected transient database errors receive a limited retry attempt.
- **Read-back verification:** The application queries the database after a write and checks important persisted fields.
- **Auditability:** Task execution and decisions are recorded as persistent events.
- **Input handling:** Missing or invalid documents fail with a structured task error.
- **Sandbox isolation:** The prototype writes only to its local finance sandbox and does not pay invoices or send external messages.

These mechanisms improve inspectability and reliability, but they do not establish production-grade security or guarantee recovery from every failure.

## Validation performed

The development session demonstrated:

- Nine automated tests passing.
- Successful processing and database verification of sample invoices.
- Duplicate detection when the same invoice was submitted again.
- A high-value invoice entering `awaiting_approval` before its write.
- Successful approval followed by persistence and verification.
- Clean task failure for a missing document.
- A two-request concurrency smoke test in which both tasks completed and one matching invoice record was observed.

The concurrency result is a smoke test, not a comprehensive load test. Further stress testing and stronger concurrency validation are needed before production use.

## Known limitations

FlowPilot is an engineering prototype, not a production-ready finance platform.

- The workflow is deliberately narrow and executes synchronously.
- Task interpretation defaults to deterministic parsing; Ollama integration is optional.
- Scanned PDFs require OCR, which is not included.
- Vendor matching and ambiguous-request clarification are basic.
- The browser connector is optional and is not part of the core invoice execution path.
- Approval identity is a demo mechanism, not production authentication.
- Multi-tenant isolation, role-based access control, and production secrets management are not implemented to production standards.
- Durable background workers, resumable execution, production observability, and broad enterprise integrations remain future work.

## Roadmap

1. Add durable background execution and resumable task recovery.
2. Strengthen concurrency and idempotency testing.
3. Add explicit clarification loops for ambiguous requests.
4. Improve document provenance and add OCR support.
5. Introduce authentication, role-based permissions, and tenant isolation.
6. Build evaluation datasets for task success, retries, recovery, and verification.
7. Add authorized sandbox connectors for additional business workflows.

## Project documentation

- [Architecture and design decisions](docs/ARCHITECTURE.md)
- [Demo walkthrough](docs/DEMO_SCRIPT.md)

## Design principle

**An AI employee should not merely say that work is complete. It should execute authorized actions, verify the resulting state, and leave an inspectable record of what happened.**

FlowPilot is a focused exploration of that principle.
