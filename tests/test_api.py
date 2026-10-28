"""
Tests for FastAPI application endpoints (src/api/).
Validates chat endpoint, health check, lead capture, and content gaps retrieval.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "PlacidWay" in data["service"]


def test_chat_endpoint_greeting():
    payload = {
        "message": "Hello!",
        "session_id": "test_api_session",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_used"] == "pydantic_ai"
    assert data["intent"] == "greeting"
    assert len(data["answer"]) > 0


def test_chat_endpoint_medical_refusal():
    payload = {
        "message": "Do I have cancer? Please prescribe medication.",
        "session_id": "test_api_session_refusal",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_used"] == "pydantic_ai"
    assert data["intent"] == "medical_advice_refusal"
    assert data["show_medical_disclaimer"] is True


def test_lead_capture_endpoints():
    lead_payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0199",
        "country": "USA",
        "treatment_interest": "Alternative Adenocarcinoma Package",
        "notes": "Interested in 3-week Out-Patient Program",
    }
    # POST /api/leads
    post_resp = client.post("/api/leads", json=lead_payload)
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["status"] == "success"
    assert "lead_id" in post_data

    # GET /api/leads
    get_resp = client.get("/api/leads")
    assert get_resp.status_code == 200
    leads_list = get_resp.json()
    assert isinstance(leads_list, list)
    matching = [l for l in leads_list if l.get("name") == "Jane Doe"]
    assert len(matching) > 0


def test_content_gaps_endpoint():
    resp = client.get("/api/content-gaps")
    assert resp.status_code == 200
    gaps_list = resp.json()
    assert isinstance(gaps_list, list)


def test_static_frontend_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "PlacidWay" in resp.text
    assert "Immunity Therapy Center" in resp.text


def test_chat_stream_endpoint():
    payload = {
        "message": "Hello!",
        "session_id": "test_api_stream_session",
    }
    with client.stream("POST", "/api/chat/stream", json=payload) as stream_resp:
        assert stream_resp.status_code == 200
        events = []
        for line in stream_resp.iter_lines():
            if line.startswith("event:"):
                events.append(line.replace("event:", "").strip())
        assert "delta" in events
        assert "done" in events

