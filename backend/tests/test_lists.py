import json
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.models import Video, Comment
from backend.app.db.session import get_db
from backend.tests.test_upload_batch import create_sample_docx_comments, create_sample_reference_txt


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_create_and_get_lists(client, db_session):
    # 1. Create a new list
    payload = {
        "title": "Video 1: FastAPI Masterclass",
        "description": "Backend API development tutorial",
    }
    res = client.post("/api/lists", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["list"]["title"] == "Video 1: FastAPI Masterclass"
    created_id = data["list"]["id"]

    # 2. Get lists
    res = client.get("/api/lists")
    assert res.status_code == 200
    lists = res.json()
    assert any(l["id"] == created_id and l["title"] == "Video 1: FastAPI Masterclass" for l in lists)


def test_upload_to_new_and_existing_lists(client, db_session):
    docx_bytes = create_sample_docx_comments()
    ref_bytes = create_sample_reference_txt()

    # 1. Upload to a NEW list using list_name
    files = {
        "comments_file": ("feedback_batch_1.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "reference_file": ("ref_guide.txt", ref_bytes, "text/plain"),
    }
    form_data = {
        "list_name": "Video 101: Python Basics",
        "list_description": "First introduction video",
    }
    res = client.post("/api/upload/batch", files=files, data=form_data)
    assert res.status_code == 200, res.text
    resp1 = res.json()
    list_id_1 = resp1["list_id"]
    assert resp1["list_title"] == "Video 101: Python Basics"
    assert resp1["total_parsed"] == 5
    assert resp1["reference_chunks_indexed"] >= 1

    # Verify queue filtered by list_id_1
    q_res = client.get(f"/api/queue?list_id={list_id_1}")
    assert q_res.status_code == 200
    q_items = q_res.json()
    assert len(q_items) == 5
    assert all(item["video_id"] == list_id_1 for item in q_items)

    # 2. Upload additional comments to the EXISTING list (without re-uploading reference file)
    files2 = {
        "comments_file": ("feedback_batch_2.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    form_data2 = {
        "list_id": str(list_id_1),
    }
    res2 = client.post("/api/upload/batch", files=files2, data=form_data2)
    assert res2.status_code == 200, res2.text
    resp2 = res2.json()
    assert resp2["list_id"] == list_id_1
    assert resp2["list_title"] == "Video 101: Python Basics"
    assert resp2["reference_chunks_indexed"] >= 1  # Reused existing reference chunks!

    # Verify stats filtered by list_id_1
    stats_res = client.get(f"/api/stats?list_id={list_id_1}")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_comments"] == 10
