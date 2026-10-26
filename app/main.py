import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db
from .agent import interpret_request
from .models import AuditEvent, Invoice, Task
from .schemas import ApprovalRequest, RejectRequest, TaskCreate
from .runtime import create_task, decide_approval, invoice_to_dict, task_to_dict
from .tooling import build_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="FlowPilot", version="0.1.0", description="Autonomous invoice operations worker sandbox", lifespan=lifespan)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/tools")
def list_tools():
    return build_registry().describe()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "flowpilot"}

@app.get("/api/invoices")
def list_invoices(db: Session = Depends(get_db)):
    rows = db.scalars(select(Invoice).order_by(Invoice.id.desc())).all()
    return [invoice_to_dict(row) for row in rows]

@app.get("/api/tasks")
def list_tasks(db: Session = Depends(get_db)):
    rows = db.scalars(select(Task).order_by(Task.created_at.desc())).all()
    return [task_to_dict(row) for row in rows]

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task_to_dict(task)

@app.get("/api/tasks/{task_id}/events")
def task_events(task_id: str, db: Session = Depends(get_db)):
    if not db.get(Task, task_id):
        raise HTTPException(404, "Task not found")
    events = db.scalars(select(AuditEvent).where(AuditEvent.task_id == task_id).order_by(AuditEvent.id)).all()
    return [{
        "id": e.id, "type": e.event_type, "message": e.message,
        "details": json.loads(e.details_json or "{}"),
        "created_at": e.created_at.isoformat() if e.created_at else None
    } for e in events]

@app.post("/api/tasks", status_code=201)
async def submit_task(payload: TaskCreate, db: Session = Depends(get_db)):
    try:
        plan = await interpret_request(payload.request, payload.document_name)
        task = create_task(db, payload.request, payload.document_name, plan_override=plan)
        return task_to_dict(task)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Task could not be started: {type(exc).__name__}")

@app.post("/api/tasks/{task_id}/approve")
def approve_task(task_id: str, payload: ApprovalRequest, db: Session = Depends(get_db)):
    try:
        return task_to_dict(decide_approval(db, task_id, True, payload.approved_by, payload.note))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Approval execution failed: {type(exc).__name__}")

@app.post("/api/tasks/{task_id}/reject")
def reject_task(task_id: str, payload: RejectRequest, db: Session = Depends(get_db)):
    try:
        return task_to_dict(decide_approval(db, task_id, False, payload.rejected_by, payload.reason))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@app.post("/api/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    # Explicit demo-only operation. Tasks and audit history remain for review.
    db.query(Invoice).delete()
    db.commit()
    return {"status": "ok", "message": "Invoice sandbox cleared; task and audit history retained."}
