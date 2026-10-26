# FlowPilot — Autonomous Invoice Operations Worker

FlowPilot is a local-first prototype of an AI operations worker. It accepts a task, extracts invoice information from a local PDF/text document, checks for duplicates, optionally pauses for human approval, writes a finance record, and independently reads the record back to verify the outcome.

## What is implemented in this prototype

- FastAPI API and a browser dashboard served by the API.
- PostgreSQL persistence in Docker Compose; SQLite is supported for local tests.
- Invoice extraction from text files and text-based PDFs.
- Natural-language task intake with a deterministic parser that works without an LLM.
- Optional Ollama integration for task interpretation (disabled by default).
- Tool execution with bounded retry for transient failures.
- Duplicate detection and database uniqueness constraints.
- Human approval checkpoint for invoices above a configurable threshold.
- Independent read-after-write verification.
- Persistent task state and audit events.
- Unit/integration tests.

## Scope and safety

This is a sandbox prototype. It does not connect to real finance systems or real company credentials. It does not pay invoices or send external messages. The only write target is the local FlowPilot finance sandbox. Documents are untrusted input; extracted content is treated as data, not as instructions.

## Quick start (Windows + Docker Desktop)

1. Install and start Docker Desktop, using the Linux container engine.
2. Open PowerShell in the extracted `flowpilot` directory.
3. Copy the example environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Start the app and PostgreSQL:

   ```powershell
   docker compose up --build
   ```

5. Open `http://localhost:8000`.
6. Try the sample task:

   `Process the latest invoice from Acme Supplies`

7. To view API docs, open `http://localhost:8000/docs`.

Stop the services with `Ctrl+C`, then:

```powershell
docker compose down
```

To remove the local database volume and reset the sandbox (destructive):

```powershell
docker compose down -v
```

## Run tests

The tests use an isolated SQLite database and do not require Docker:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./test_flowpilot.db"
python -m pytest -q
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Optional local LLM with Ollama

The deterministic task parser is the default and works without a model. To experiment with Ollama:

1. Install Ollama separately and pull a model suitable for your machine, for example `ollama pull qwen2.5:3b`.
2. Set `OLLAMA_ENABLED=true` in `.env`.
3. Set `OLLAMA_MODEL=qwen2.5:3b`.
4. Ensure the Ollama service is reachable from the API container. With Docker Desktop, set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
5. Restart `docker compose up --build`.

When enabled, the optional model is used to interpret task intent into a constrained JSON shape. Tool execution, authorization, duplicate checks and verification remain in application code. The app falls back to deterministic parsing if the model is unavailable or returns invalid output.

## Demo workflow

1. Open the dashboard and submit `Process the latest invoice from Acme Supplies`.
2. The agent locates the sample invoice, extracts its fields and checks for duplicates.
3. If the total exceeds `APPROVAL_THRESHOLD`, the task pauses for approval.
4. Approve or reject it from the dashboard.
5. On approval, FlowPilot writes the record and independently verifies it.
6. Inspect the execution trace and final status.

## API overview

- `GET /api/health`
- `GET /api/invoices`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks`
- `POST /api/tasks/{task_id}/approve`
- `POST /api/tasks/{task_id}/reject`
- `GET /api/tasks/{task_id}/events`
- `POST /api/demo/reset` — resets demo invoice records only; task/audit history remains.

Example task request:

```json
{
  "request": "Process the latest invoice from Acme Supplies",
  "document_name": "acme_invoice.txt"
}
```

## Architecture

`Dashboard → FastAPI → Task Runtime → Planner/Policy → Document Tool → Finance Tool → Verifier`

PostgreSQL stores task state, finance records and audit events. Tool results are structured. Tasks execute synchronously in this MVP; durable asynchronous workers are a planned extension. The agent runtime is intentionally explicit so the execution path and failure behavior can be inspected during a technical interview.

## Reliability design

- Bounded retries for transient tool/database errors.
- Duplicate prevention using a normalized vendor + invoice number uniqueness constraint.
- Approval checkpoint before writing invoices above the configured threshold.
- Independent database read-back for verification.
- Audit events for plan, extraction, duplicate check, approval, write, retry, verification and completion.
- Failed or unverified work is not marked completed.

## Known limitations

- The prototype handles a deliberately narrow invoice workflow and executes requests synchronously (the dashboard waits for the request to finish or reach an approval checkpoint).
- PDF extraction works for text-based PDFs; scanned PDFs require OCR, which is not included.
- Vendor matching and task interpretation are basic; ambiguous tasks should be clarified in a future iteration.
- The optional Ollama path needs a locally running compatible model and is not enabled by default.
- Authentication, multi-tenant isolation, secrets management, production observability and deployment hardening are not production-ready.
- The demo finance sandbox is not an actual accounting integration.

## Next steps

1. Add explicit clarification loops for ambiguous vendor/document matches.
2. Add OCR and stronger document provenance.
3. Add durable background jobs and resumable worker leases.
4. Add authentication, role-based permissions and tenant isolation.
5. Add model/tool evaluation datasets and measure success, recovery and verification rates.
6. Add connector interfaces for real enterprise systems, only with authorized sandbox credentials.


## Founding Engineer architecture additions

- `app/tooling.py` defines an explicit tool registry with required arguments and permission labels. The invoice runtime calls document read/extraction through this registry.
- `app/policy.py` centralizes invoice-write policy and approval decisions outside the LLM.
- `app/browser_tool.py` provides an optional Playwright-based local-page inspection connector with a hostname allowlist. Install Playwright and Chromium separately to use it.
- `docs/ARCHITECTURE.md` explains the execution lifecycle, safety boundaries and production gaps.
- `docs/DEMO_SCRIPT.md` provides a concise, honest walkthrough.

The browser connector is available as a reusable tool and is visible through `GET /api/tools`, but the current invoice workflow does not yet require browser automation to complete its task. Install optional browser support with `pip install -r requirements-browser.txt` followed by `python -m playwright install chromium` in the environment where the browser tool runs. Background workers, company-wide semantic memory, authenticated approval identities and production-grade multi-workflow planning remain future work rather than implemented features.


## Inspect registered tools

Open `http://localhost:8000/api/tools` to see the tool names, descriptions, required arguments and permission labels exposed by the registry.
