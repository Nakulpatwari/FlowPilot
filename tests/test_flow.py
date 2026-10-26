def test_high_value_invoice_requires_approval_then_verifies(client):
    r = client.post("/api/tasks", json={"request":"Process the latest invoice from Acme Supplies"})
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["status"] == "awaiting_approval"
    assert task["extracted"]["invoice_number"] == "ACME-2026-1042"
    assert client.get("/api/invoices").json() == []

    approved = client.post(f"/api/tasks/{task['id']}/approve", json={"approved_by":"tester","note":"test approval"})
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result["status"] == "completed"
    assert result["result"]["verification"]["verified"] is True
    assert result["result"]["verification"]["method"] == "independent_database_readback"
    assert len(client.get("/api/invoices").json()) == 1

def test_duplicate_is_not_created_twice(client):
    first = client.post("/api/tasks", json={"request":"Process the invoice from Bright Office"})
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "completed"
    second = client.post("/api/tasks", json={"request":"Process the invoice from Bright Office"})
    assert second.status_code == 201, second.text
    assert second.json()["status"] == "completed"
    assert second.json()["result"]["verification"]["duplicate"] is True
    assert len(client.get("/api/invoices").json()) == 1

def test_rejection_does_not_write_invoice(client):
    task = client.post("/api/tasks", json={"request":"Process the latest invoice from Acme Supplies"}).json()
    rejected = client.post(f"/api/tasks/{task['id']}/reject", json={"rejected_by":"tester","reason":"Check vendor details"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/api/invoices").json() == []

def test_missing_vendor_requests_clarification(client):
    r = client.post("/api/tasks", json={"request":"Process the latest invoice"})
    assert r.status_code == 400
    assert "specify a vendor" in r.json()["detail"].lower()

def test_audit_trail_is_persisted(client):
    task = client.post("/api/tasks", json={"request":"Process the invoice from Bright Office"}).json()
    events = client.get(f"/api/tasks/{task['id']}/events").json()
    types = [e["type"] for e in events]
    assert "invoice_extracted" in types
    assert "verification_passed" in types
    assert "task_completed" in types
