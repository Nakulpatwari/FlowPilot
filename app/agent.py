import json
import re
from pathlib import Path
from typing import Any
import httpx
import pdfplumber
from .config import INVOICE_DIR, OLLAMA_BASE_URL, OLLAMA_ENABLED, OLLAMA_MODEL

FIELD_PATTERNS = {
    "invoice_number": [r"Invoice\s*(?:Number|No\.?)\s*[:#]?\s*([A-Z0-9-]+)"],
    "vendor": [r"Vendor\s*:\s*(.+)", r"^([A-Z][A-Z &.-]+)\s*[—-]\s*INVOICE"],
    "invoice_date": [r"Invoice\s*Date\s*:\s*(\d{4}-\d{2}-\d{2})"],
    "due_date": [r"Due\s*Date\s*:\s*(\d{4}-\d{2}-\d{2})"],
    "amount": [r"Amount\s*Due\s*:\s*(?:INR\s*)?([0-9,]+(?:\.[0-9]{1,2})?)"],
    "currency": [r"Currency\s*:\s*([A-Z]{3})"],
    "description": [r"Description\s*:\s*(.+)"],
}

def safe_document_path(document_name: str) -> Path:
    name = Path(document_name).name
    if name != document_name or name in {"", ".", ".."}:
        raise ValueError("Invalid document name")
    path = (INVOICE_DIR / name).resolve()
    base = INVOICE_DIR.resolve()
    if path.parent != base or not path.is_file():
        raise FileNotFoundError(f"Document not found in sample_data: {name}")
    return path

def read_document(document_name: str) -> str:
    path = safe_document_path(document_name)
    if path.suffix.lower() == ".pdf":
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return path.read_text(encoding="utf-8")

def extract_invoice(text: str) -> dict[str, Any]:
    result = {}
    for field, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if field == "amount":
                    value = float(value.replace(",", ""))
                result[field] = value
                break
    required = ["invoice_number", "vendor", "invoice_date", "due_date", "amount"]
    missing = [field for field in required if field not in result]
    if missing:
        raise ValueError("Invoice is missing required fields: " + ", ".join(missing))
    result.setdefault("currency", "INR")
    result.setdefault("description", "")
    result["vendor"] = result["vendor"].strip()
    return result

def deterministic_interpret(request: str, requested_document: str | None) -> dict:
    # The prototype intentionally constrains tasks to invoice processing.
    doc = requested_document
    if not doc:
        lowered = request.lower()
        if "bright office" in lowered:
            doc = "bright_office_invoice.txt"
        elif "acme" in lowered:
            doc = "acme_invoice.txt"
        else:
            raise ValueError("Please specify a vendor (Acme Supplies or Bright Office) or choose a document.")
    if not doc.lower().endswith((".txt", ".pdf")):
        raise ValueError("Only .txt and text-based .pdf invoice documents are supported.")
    return {
        "goal": "Create or identify a finance invoice record and verify it",
        "document_name": doc,
        "steps": ["read_document", "extract_invoice", "check_duplicate", "approval_policy", "create_invoice_if_approved", "verify_invoice"],
    }

async def interpret_request(request: str, requested_document: str | None) -> dict:
    if not OLLAMA_ENABLED:
        return deterministic_interpret(request, requested_document)
    prompt = (
        "Return only JSON with keys goal, document_name, steps. This is an invoice-only sandbox. "
        "Never invent filenames. Allowed filenames: acme_invoice.txt, bright_office_invoice.txt. "
        "Choose a filename only if the request names the vendor or user supplied document_name. "
        "Do not add actions outside invoice processing. User request: " + request
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
            )
            response.raise_for_status()
            payload = response.json()
            parsed = json.loads(payload["response"])
            filename = requested_document or parsed.get("document_name")
            if filename not in {"acme_invoice.txt", "bright_office_invoice.txt"}:
                raise ValueError("Model did not return an allowed invoice document.")
            # Never accept model-provided executable tool names.
            return {
                "goal": str(parsed.get("goal", "Process invoice"))[:300],
                "document_name": filename,
                "steps": ["read_document", "extract_invoice", "check_duplicate", "approval_policy", "create_invoice_if_approved", "verify_invoice"],
            }
    except Exception:
        return deterministic_interpret(request, requested_document)


def interpret_request_sync(request: str, requested_document: str | None = None) -> dict:
    """Sync adapter for FastAPI's synchronous task endpoint."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(interpret_request(request, requested_document))
    # This branch is defensive; current endpoint runs as a synchronous route.
    return deterministic_interpret(request, requested_document)
