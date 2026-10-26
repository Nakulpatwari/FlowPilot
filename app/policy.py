"""Deterministic policy checks. The LLM never grants itself permissions."""
from dataclasses import dataclass
from .config import APPROVAL_THRESHOLD

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str

def evaluate_invoice_write(invoice: dict, *, permissions: set[str] | None = None) -> PolicyDecision:
    permissions = permissions or {"invoices:read", "invoices:write"}
    if "invoices:write" not in permissions:
        return PolicyDecision(False, False, "The current execution context does not have invoice-write permission.")
    try:
        amount = float(invoice["amount"])
    except (KeyError, TypeError, ValueError):
        return PolicyDecision(False, False, "Invoice amount is missing or invalid.")
    if amount < 0:
        return PolicyDecision(False, False, "Negative invoice amounts are not permitted.")
    if amount >= APPROVAL_THRESHOLD:
        return PolicyDecision(True, True, f"Invoice amount {invoice.get('currency', 'INR')} {amount:.2f} meets or exceeds approval threshold {APPROVAL_THRESHOLD:.2f}.")
    return PolicyDecision(True, False, "Invoice write is permitted by the configured sandbox policy.")
