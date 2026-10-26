from app.tooling import ToolRegistry, ToolSpec, ToolError
from app.policy import evaluate_invoice_write

def test_registry_requires_permission_and_arguments():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "test", ("value",), "test:run", lambda value: value))
    try:
        registry.execute("echo", {"value": "ok"}, set())
        assert False, "Expected permission error"
    except PermissionError:
        pass
    try:
        registry.execute("echo", {}, {"test:run"})
        assert False, "Expected missing argument error"
    except ToolError:
        pass
    assert registry.execute("echo", {"value": "ok", "ignored": "x"}, {"test:run"}) == "ok"

def test_policy_requires_approval_for_high_value_invoice():
    decision = evaluate_invoice_write({"amount": 1480.5, "currency": "INR"})
    assert decision.allowed is True
    assert decision.requires_approval is True

def test_policy_denies_without_write_permission():
    decision = evaluate_invoice_write({"amount": 10}, permissions={"invoices:read"})
    assert decision.allowed is False


def test_tools_endpoint_exposes_registered_capabilities(client):
    response = client.get("/api/tools")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "documents.read" in names
    assert "invoices.extract" in names
    assert "browser.inspect_local_page" in names
