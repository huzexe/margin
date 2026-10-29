"""API tests. Run with: .venv/bin/pytest"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_starts_with_no_subjects(client):
    assert client.get("/api/subjects").json() == []


def test_subject_add_rename_delete(client):
    r = client.post("/api/subjects", json={"name": "  Data   Structures "})
    assert r.status_code == 201
    subject = r.json()
    assert subject["name"] == "Data Structures"

    dup = client.post("/api/subjects", json={"name": "data structures"})
    assert dup.status_code == 409
    assert dup.json()["detail"] == "This subject already exists."

    blank = client.post("/api/subjects", json={"name": "   "})
    assert blank.status_code == 422
    assert blank.json()["detail"] == "Enter a subject name."

    r = client.patch(f"/api/subjects/{subject['id']}", json={"name": "Algorithms"})
    assert r.json()["name"] == "Algorithms"

    note = client.post("/api/notes", json={"title": "Sorting", "subject_id": subject["id"]}).json()
    assert client.get("/api/subjects").json()[0]["note_count"] == 1

    assert client.delete(f"/api/subjects/{subject['id']}").status_code == 204
    kept = client.get(f"/api/notes/{note['id']}").json()
    assert kept["subject_id"] is None  # note survives as "No subject"


def test_note_crud_and_autosave(client):
    note = client.post("/api/notes", json={"title": "Binary Search"}).json()
    assert note["rough_text"] == ""

    r = client.patch(f"/api/notes/{note['id']}", json={"rough_text": "- sorted array\n- O(log n)"})
    assert r.json()["rough_text"] == "- sorted array\n- O(log n)"
    assert r.json()["title"] == "Binary Search"  # untouched fields stay

    assert client.patch(f"/api/notes/{note['id']}", json={"subject_id": 999}).status_code == 422
    assert client.patch(f"/api/notes/{note['id']}", json={"bogus": 1}).status_code == 422

    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert client.get(f"/api/notes/{note['id']}").status_code == 404


def test_limits(client):
    r = client.post("/api/notes", json={"rough_text": "x" * 20_001})
    assert r.status_code == 422
    assert r.json()["detail"] == "Rough text is too long."


def test_search_filter_sort(client):
    phys = client.post("/api/subjects", json={"name": "Physics"}).json()
    client.post("/api/notes", json={"title": "Newton laws", "rough_text": "inertia, F = ma", "subject_id": phys["id"]})
    client.post("/api/notes", json={"title": "Binary search", "rough_text": "halves the search space"})

    titles = lambda **p: [n["title"] for n in client.get("/api/notes", params=p).json()]
    assert titles(q="inert") == ["Newton laws"]          # prefix match in rough notes
    assert titles(q="SEARCH") == ["Binary search"]       # case-insensitive
    assert titles(q='"; DROP TABLE notes; --') == []     # odd input is harmless
    assert titles(subject_id=phys["id"]) == ["Newton laws"]
    assert titles(sort="title") == ["Binary search", "Newton laws"]
    assert len(titles()) == 2


def test_pages_and_headers(client):
    for path in ["/", "/notes/new", "/notes/1"]:
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "default-src 'self'" in client.get("/").headers["content-security-policy"]
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
