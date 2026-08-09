import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, DBAdapter

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    DBAdapter.reset_candidate_data("medharirakeshavs@gmail.com")
    DBAdapter.reset_candidate_data("priya.sharma@gmail.com")
    yield

def test_get_users():
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert "team" in data
    assert len(data["team"]) == 6
    user_ids = [u["user_id"] for u in data["team"]]
    assert "u_aarti" in user_ids
    assert "u_triage" in user_ids

def test_create_task_strict_enum_validation():
    # Valid Task creation
    valid_payload = {
        "candidate_id": "medharirakeshavs@gmail.com",
        "source_email_id": "em_test_001",
        "thread_id": "th_test_001",
        "title": "RFP Meridian Steel",
        "description": "Enterprise RFP test",
        "assignee_id": "u_aarti",
        "category": "enterprise_rfp",
        "priority": "high",
        "due_date": "2026-08-12",
        "deal_value_inr": 2500000,
        "company_name": "Meridian Steel",
        "confidence": 0.95
    }
    resp = client.post("/tasks", json=valid_payload)
    assert resp.status_code == 201
    res_data = resp.json()
    assert "task_id" in res_data
    assert res_data["candidate_id"] == "medharirakeshavs@gmail.com"

    # Test Invalid Enum assignee_id -> Expect exact 400 shape per spec §5.1
    invalid_assignee = valid_payload.copy()
    invalid_assignee["source_email_id"] = "em_test_002"
    invalid_assignee["assignee_id"] = "Aarti" # Wrong enum string!
    resp_err = client.post("/tasks", json=invalid_assignee)
    assert resp_err.status_code == 400
    err_data = resp_err.json()
    assert err_data["error"] == "invalid_enum_value"
    assert err_data["field"] == "assignee_id"
    assert err_data["received"] == "Aarti"
    assert "u_aarti" in err_data["allowed"]

def test_ingest_idempotency_and_thread_reconciliation():
    cand = "medharirakeshavs@gmail.com"
    email_1 = {
        "email_id": "em_00101",
        "thread_id": "th_00101",
        "message_index": 0,
        "from_name": "Suresh Kulkarni",
        "from_email": "s.kulkarni@meridiansteel.co.in",
        "subject": "RFP - Enterprise DMS",
        "body": "Meridian Steel invites proposals for an enterprise DMS. Budget Rs. 25 lakhs. Due by 12th August 2026.",
        "received_at": "2026-08-01T09:14:22+05:30",
        "is_reply": False
    }

    # Run 1: Ingest batch
    resp1 = client.post("/ingest", json={"candidate_id": cand, "emails": [email_1]})
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["tasks_created"] == 1
    assert res1["tasks_updated"] == 0

    # Run 2: Ingest IDENTICAL batch -> Tasks created must be 0 (Idempotency!)
    resp2 = client.post("/ingest", json={"candidate_id": cand, "emails": [email_1]})
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["tasks_created"] == 0
    assert res2["tasks_updated"] == 0

    # Run 3: Ingest reply to existing thread -> Tasks created must be 0, tasks_updated must be 1
    reply_email = {
        "email_id": "em_00102",
        "thread_id": "th_00101", # Same thread!
        "message_index": 1,
        "from_name": "Suresh Kulkarni",
        "from_email": "s.kulkarni@meridiansteel.co.in",
        "subject": "Re: RFP - Enterprise DMS",
        "body": "Correction: board approved budget Rs. 32 lakhs, deadline 11th August.",
        "received_at": "2026-08-09T10:00:00+05:30",
        "is_reply": True
    }
    resp3 = client.post("/ingest", json={"candidate_id": cand, "emails": [reply_email]})
    assert resp3.status_code == 200
    res3 = resp3.json()
    assert res3["tasks_created"] == 0
    assert res3["tasks_updated"] == 1

def test_grounded_chat_zero_count_trap():
    cand = "priya.sharma@gmail.com"
    # Query for GST refunds (zero match category trap test)
    chat_resp = client.post("/api/chat", json={"candidate_id": cand, "query": "How many emails were about GST refunds?"})
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "zero" in chat_data["answer"].lower() or "0" in chat_data["answer"]
    assert chat_data["supporting_data"].get("gst_refund_count") == 0
