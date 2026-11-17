import io
import json
import docx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.models import Comment, Video


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_sample_docx_comments():
    doc = docx.Document()
    doc.add_heading("Customer Feedback Comments", level=1)
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Author"
    hdr_cells[1].text = "Comment Text"

    sample_rows = [
        ("DevAlex", "What python version is required for this setup?"),
        ("SaraConnor", "Awesome tutorial! Thank you so much, saved me hours."),
        ("AngryUser", "The audio was completely broken and out of sync! Fix it!"),
        ("SponsorRep", "Hi, we love your content and want to sponsor your next video. Contact partnerships@sponsor.com"),
        ("CryptoBot", "Double your bitcoin fast at t.me/fastmoney now!"),
    ]

    for author, text in sample_rows:
        row_cells = table.add_row().cells
        row_cells[0].text = author
        row_cells[1].text = text

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def create_sample_reference_txt():
    content = """
[Page 1]
Introduction to the setup. Python version 3.10 or higher is required for this project.

[Page 2]
Database configuration: pgvector docker image must be started with CREATE EXTENSION vector.
"""
    return content.encode("utf-8")


def test_preferences_api(client):
    # GET preferences
    res = client.get("/api/preferences")
    assert res.status_code == 200
    data = res.json()
    assert "categories" in data
    assert "tone" in data

    # POST updated preferences
    payload = {
        "categories": [
            {"name": "question", "description": "Questions", "action": "DRAFT"},
            {"name": "praise", "description": "Praise", "action": "AUTO"},
            {"name": "complaint", "description": "Complaints", "action": "ESCALATE"},
            {"name": "sponsor_outreach", "description": "Sponsors and partnerships", "action": "ESCALATE"},
        ],
        "tone": "warm_empathetic",
        "custom_instructions": "Always be polite and helpful.",
    }
    res = client.post("/api/preferences", json=payload)
    assert res.status_code == 200
    assert res.json()["preferences"]["tone"] == "warm_empathetic"


def test_batch_upload_with_docx_and_reference(client, db_session):
    docx_bytes = create_sample_docx_comments()
    ref_bytes = create_sample_reference_txt()

    files = {
        "comments_file": ("uploaded_feedback.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "reference_file": ("guide.txt", ref_bytes, "text/plain"),
    }
    prefs = {
        "categories": [
            {"name": "question", "description": "User questions", "action": "DRAFT"},
            {"name": "praise", "description": "Positive feedback", "action": "AUTO"},
            {"name": "complaint", "description": "Complaints", "action": "ESCALATE"},
            {"name": "business_collab", "description": "Sponsorships and collabs", "action": "ESCALATE"},
            {"name": "spam", "description": "Promotional spam", "action": "ESCALATE"},
        ],
        "tone": "helpful_concise",
        "custom_instructions": "Be brief and direct.",
    }
    data = {
        "preferences_json": json.dumps(prefs),
    }

    res = client.post("/api/upload/batch", files=files, data=data)
    assert res.status_code == 200, res.text
    resp_data = res.json()
    assert resp_data["status"] == "success"
    assert resp_data["total_parsed"] == 5
    assert resp_data["reference_chunks_indexed"] >= 1
    assert "categories_breakdown" in resp_data
    assert len(resp_data["comments"]) == 5
