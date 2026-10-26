# FlowPilot — Five-Minute Demo Script

## Demo objective

Demonstrate how FlowPilot processes an invoice through a controlled execution lifecycle: interpret the request, extract data, apply policy, request approval when required, persist the record, verify the result, and retain an audit trail.

## 1. Introduce the dashboard — 0:00–0:30

Open the FlowPilot dashboard.

**Say:**

“FlowPilot is a prototype of an autonomous company-operations agent. Instead of simply generating a response, it executes a constrained workflow, records its actions, handles common failure cases, and verifies the result. Today, I’ll demonstrate this through invoice processing.”

Briefly point out the task status, invoice records, and available task details.

## 2. Process an invoice — 0:30–1:15

Submit the request:

`Process the latest invoice from Acme Supplies`

Show the task events and extracted fields:
- Vendor
- Invoice number
- Amount
- Invoice date, if available

**Say:**

“The system resolves the request to a supported sample document, extracts the invoice fields, and evaluates the proposed write against application-defined policy.”

## 3. Demonstrate human approval — 1:15–2:00

Use the high-value invoice scenario, such as the Acme invoice for INR 1,480.50, if it is configured to require approval.

Show the `awaiting_approval` status and the approval reason.

**Say:**

“The configured approval threshold is INR 1,000. Since this invoice exceeds that threshold, FlowPilot pauses before writing the record. The approval decision is enforced by application policy, not left to the language model.”

Approve the task and show that execution resumes.

## 4. Verify the persisted result — 2:00–2:45

Open the invoice list and the completed task details.

Show the saved invoice record and the read-back verification checks.

**Say:**

“After approval, FlowPilot writes the invoice to PostgreSQL and independently reads it back to check that the stored fields match the extracted values. The task is marked complete only after the configured verification succeeds.”

## 5. Demonstrate duplicate detection — 2:45–3:20

Submit the same Acme invoice request again.

Show the duplicate-detection event and the existing invoice reference.

**Say:**

“Repeated requests should not create duplicate invoice records. FlowPilot identifies the existing invoice and reports the existing record rather than inserting another one.”

If useful, show that the invoice count has not increased.

## 6. Demonstrate ambiguity handling — 3:20–3:50

Submit:

`Process the latest invoice`

Show the clarification or failure response produced when the vendor cannot be resolved.

**Say:**

“When the request does not provide enough information to identify the intended invoice, the system should not guess. It asks for clarification or reports that it cannot safely resolve the request.”

## 7. Show the audit trail — 3:50–4:30

Open the task's event history.

Point out relevant events, such as task creation, document reading, extraction, policy evaluation, approval, persistence, duplicate detection, and verification, wherever applicable to that task.

**Say:**

“Each execution leaves a persisted trail of events. This makes the workflow easier to inspect and debug than a black-box agent that only returns a final answer.”

## 8. Close with engineering tradeoffs — 4:30–5:00

**Say:**

“This is a working sandbox prototype, not a production finance integration. It demonstrates constrained tools, policy-based approval, database persistence, duplicate handling, and read-back verification. Production deployment would still require authentication, tenant isolation, durable background workers, stronger monitoring, migrations, and broader security and reliability testing.”

## Demo checklist

- [ ] Dashboard is running.
- [ ] Database is available and contains no confusing old demo records.
- [ ] Acme invoice and approval scenario are ready.
- [ ] Approval action has been tested.
- [ ] Duplicate request returns the existing invoice.
- [ ] Ambiguous request does not create an invoice.
- [ ] Audit events are visible.
- [ ] Terminal and browser tabs are arranged before recording.
- [ ] No `.env` file, credentials, or secrets are visible.

**Fallback:** If a live action fails, show the relevant task events and explain the observed behavior accurately. Do not present a simulated or previously recorded result as a live execution.
