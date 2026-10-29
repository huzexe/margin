"""Settings, backup and restore tests."""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_default_options(client):
    assert client.get("/api/settings").json()["default_options"]["detail"] == "standard"
    body = {"default_options": {"diagrams": True, "flashcards": True, "detail": "detailed"}}
    assert client.put("/api/settings", json=body).status_code == 200
    saved = client.get("/api/settings").json()["default_options"]
    assert saved["diagrams"] and saved["flashcards"] and saved["detail"] == "detailed" and not saved["simplify"]
    assert client.put("/api/settings", json={"default_options": {"detail": "huge"}}).status_code == 422


def make_library(client):
    phys = client.post("/api/subjects", json={"name": "Physics"}).json()
    content = {"blocks": [{"type": "paragraph", "data": {"text": "Inertia explained"}}]}
    n1 = client.post("/api/notes", json={"title": "Newton", "subject_id": phys["id"], "rough_text": "F = ma"}).json()
    client.patch(f"/api/notes/{n1['id']}", json={"content": content, "options": {"diagrams": True}})
    client.post("/api/notes", json={"title": "Loose note", "rough_text": "no subject"})
    return phys


def test_backup_and_restore_roundtrip(client):
    make_library(client)
    r = client.get("/api/backup")
    assert r.status_code == 200 and "margin-backup-" in r.headers["content-disposition"]
    backup = r.json()
    assert backup["app"] == "margin" and len(backup["notes"]) == 2 and backup["subjects"][0]["name"] == "Physics"

    # merge: notes are added, the existing subject is reused (not duplicated)
    res = client.post("/api/restore?mode=merge", content=json.dumps(backup)).json()
    assert res == {"notes": 2, "subjects_created": 0}
    assert len(client.get("/api/notes").json()) == 4
    assert [s["note_count"] for s in client.get("/api/subjects").json()] == [2]

    # replace: library becomes exactly the backup
    res = client.post("/api/restore?mode=replace", content=json.dumps(backup)).json()
    assert res == {"notes": 2, "subjects_created": 1}
    notes = client.get("/api/notes", params={"sort": "title"}).json()
    assert [n["title"] for n in notes] == ["Loose note", "Newton"]
    newton = client.get(f"/api/notes/{notes[1]['id']}").json()
    assert newton["subject_name"] == "Physics" and newton["content"]["blocks"][0]["data"]["text"] == "Inertia explained"
    assert newton["options"]["diagrams"] is True
    # restored notes are searchable
    assert len(client.get("/api/notes", params={"q": "inertia"}).json()) == 1


def test_restore_rejects_bad_files(client):
    make_library(client)
    for bad in ["not json", json.dumps({"hello": 1}), json.dumps({"app": "margin", "version": 99})]:
        r = client.post("/api/restore?mode=replace", content=bad)
        assert r.status_code == 422, bad
    bad_content = {"app": "margin", "version": 1, "notes": [
        {"title": "x", "content": {"blocks": [{"type": "script", "data": {}}]}, "created_at": "t", "updated_at": "t"}]}
    assert client.post("/api/restore?mode=replace", content=json.dumps(bad_content)).status_code == 422
    # nothing was deleted by the failed replace attempts
    assert len(client.get("/api/notes").json()) == 2
