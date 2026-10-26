import json
import time
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from .agent import interpret_request_sync
from .tooling import build_registry
from .policy import evaluate_invoice_write
from .config import APPROVAL_THRESHOLD
from .models import AuditEvent, Invoice, Task, utcnow

def log_event(db: Session, task: Task, event_type: str, message: str, details: dict | None = None):
    db.add(AuditEvent(task_id=task.id, event_type=event_type, message=message, details_json=json.dumps(details or {})))
    task.updated_at = utcnow()
    db.commit()

def invoice_to_dict(invoice: Invoice) -> dict:
    return {
        "id": invoice.id, "vendor": invoice.vendor, "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date, "due_date": invoice.due_date, "amount": invoice.amount,
        "currency": invoice.currency, "description": invoice.description,
        "source_document": invoice.source_document,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
    }

def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id, "request": task.request, "document_name": task.document_name,
        "status": task.status, "plan": json.loads(task.plan_json or "[]"),
        "extracted": json.loads(task.extracted_json or "{}"),
        "result": json.loads(task.result_json or "{}"), "error": task.error,
        "approval_reason": task.approval_reason,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }

def create_task(db: Session, request: str, document_name: str | None, plan_override: dict | None = None) -> Task:
    # Planning is supplied by the API route; deterministic parsing is the safe default.
    plan = plan_override or deterministic_interpret(request, document_name)
    task = Task(
        id=str(uuid.uuid4()), request=request, document_name=plan["document_name"],
        status="running", plan_json=json.dumps(plan["steps"]), extracted_json="{}", result_json="{}",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_event(db, task, "task_created", "Task accepted and execution plan created.", {"goal": plan["goal"], "steps": plan["steps"]})
    execute_until_checkpoint(db, task)
    db.refresh(task)
    return task

def execute_until_checkpoint(db: Session, task: Task):
    try:
        task.status = "running"
        task.error = ""
        db.commit()
        log_event(db, task, "execution_started", "Execution started.")
        registry = build_registry()
        permissions = {"documents:read", "invoices:extract", "invoices:read", "invoices:write"}
        document_text = registry.execute("documents.read", {"document_name": task.document_name}, permissions)
        log_event(db, task, "document_read", "Read invoice document.", {"document_name": task.document_name, "characters": len(document_text)})
        extracted = registry.execute("invoices.extract", {"text": document_text}, permissions)
        task.extracted_json = json.dumps(extracted)
        db.commit()
        log_event(db, task, "invoice_extracted", "Extracted required invoice fields.", {"invoice_number": extracted["invoice_number"], "vendor": extracted["vendor"], "amount": extracted["amount"]})

        vendor_norm = " ".join(extracted["vendor"].casefold().split())
        existing = db.scalar(select(Invoice).where(
            Invoice.vendor_normalized == vendor_norm,
            Invoice.invoice_number == extracted["invoice_number"]
        ))
        if existing:
            verified = invoice_to_dict(existing)
            task.result_json = json.dumps({"invoice": verified, "verification": {"verified": True, "method": "database_readback", "duplicate": True}})
            task.status = "completed"
            db.commit()
            log_event(db, task, "duplicate_found", "Matching invoice already exists; no duplicate created.", {"invoice_id": existing.id})
            log_event(db, task, "verification_passed", "Verified existing record from database.", {"invoice_id": existing.id, "duplicate": True})
            log_event(db, task, "task_completed", "Task completed: existing invoice verified.")
            return

        decision = evaluate_invoice_write(extracted, permissions=permissions)
        log_event(db, task, "policy_evaluated", decision.reason, {
            "allowed": decision.allowed, "requires_approval": decision.requires_approval
        })
        if not decision.allowed:
            task.status = "failed"
            task.error = decision.reason
            db.commit()
            log_event(db, task, "policy_denied", decision.reason)
            return
        if decision.requires_approval:
            task.status = "awaiting_approval"
            task.approval_reason = decision.reason
            db.commit()
            log_event(db, task, "approval_required", task.approval_reason, {"threshold": APPROVAL_THRESHOLD})
            return

        create_and_verify(db, task, extracted)
    except (FileNotFoundError, ValueError) as exc:
        task.status = "failed"
        task.error = str(exc)
        db.commit()
        log_event(db, task, "task_failed", "Task failed validation or document access.", {"error": str(exc)})
    except Exception as exc:
        db.rollback()
        task = db.get(Task, task.id)
        if task:
            task.status = "failed"
            task.error = f"Unexpected execution failure: {type(exc).__name__}"
            db.commit()
            log_event(db, task, "task_failed", "Unexpected execution failure.", {"error_type": type(exc).__name__})

def create_and_verify(db: Session, task: Task, extracted: dict):
    vendor_norm = " ".join(extracted["vendor"].casefold().split())
    # Bounded retry; the DB uniqueness constraint is the final duplicate guard.
    last_error = None
    for attempt in range(1, 3):
        try:
            invoice = Invoice(
                vendor=extracted["vendor"], vendor_normalized=vendor_norm,
                invoice_number=extracted["invoice_number"], invoice_date=extracted["invoice_date"],
                due_date=extracted["due_date"], amount=float(extracted["amount"]),
                currency=extracted.get("currency", "INR"), description=extracted.get("description", ""),
                source_document=task.document_name,
            )
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
            log_event(db, task, "invoice_created", "Created finance sandbox invoice record.", {"invoice_id": invoice.id, "attempt": attempt})
            break
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Invoice).where(
                Invoice.vendor_normalized == vendor_norm,
                Invoice.invoice_number == extracted["invoice_number"]
            ))
            if existing:
                invoice = existing
                log_event(db, task, "duplicate_race_prevented", "Unique constraint prevented duplicate creation.", {"invoice_id": existing.id})
                break
            raise
        except OperationalError as exc:
            db.rollback()
            last_error = exc
            log_event(db, task, "retry", f"Transient database error on attempt {attempt}.", {"attempt": attempt})
            if attempt == 2:
                raise last_error
            time.sleep(0.2 * attempt)
    else:
        raise RuntimeError("Invoice write did not succeed")

    # Independent read-back, rather than trusting the create response.
    persisted = db.scalar(select(Invoice).where(
        Invoice.vendor_normalized == vendor_norm,
        Invoice.invoice_number == extracted["invoice_number"]
    ))
    if persisted is None:
        task.status = "failed"
        task.error = "Write returned but independent database verification found no record."
        db.commit()
        log_event(db, task, "verification_failed", task.error)
        return
    checks = {
        "vendor_matches": persisted.vendor == extracted["vendor"],
        "invoice_number_matches": persisted.invoice_number == extracted["invoice_number"],
        "amount_matches": abs(persisted.amount - float(extracted["amount"])) < 0.005,
        "due_date_matches": persisted.due_date == extracted["due_date"],
    }
    verified = all(checks.values())
    task.result_json = json.dumps({
        "invoice": invoice_to_dict(persisted),
        "verification": {"verified": verified, "method": "independent_database_readback", "checks": checks, "duplicate": False},
    })
    task.status = "completed" if verified else "failed"
    task.error = "" if verified else "Persisted invoice did not match extracted values."
    db.commit()
    log_event(db, task, "verification_passed" if verified else "verification_failed",
              "Independent database verification passed." if verified else task.error,
              {"invoice_id": persisted.id, "checks": checks})
    if verified:
        log_event(db, task, "task_completed", "Task completed and verified.", {"invoice_id": persisted.id})

def decide_approval(db: Session, task_id: str, approved: bool, actor: str, note: str = "") -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise LookupError("Task not found")
    if task.status != "awaiting_approval":
        raise ValueError(f"Task is not awaiting approval (status: {task.status})")
    if not approved:
        task.status = "rejected"
        task.error = note or "Approval rejected by reviewer."
        db.commit()
        log_event(db, task, "approval_rejected", "Human reviewer rejected the proposed invoice write.", {"actor": actor, "note": note})
        return task
    log_event(db, task, "approval_granted", "Human reviewer approved the invoice write.", {"actor": actor, "note": note})
    extracted = json.loads(task.extracted_json)
    create_and_verify(db, task, extracted)
    db.refresh(task)
    return task
