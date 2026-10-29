"""Tag tests."""

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


def test_tags_set_filter_search_cleanup(client):
    a = client.post("/api/notes", json={"title": "Acids", "tags": ["#Exam", " chapter  3 ", "exam", ""]}).json()
    assert a["tags"] == ["chapter 3", "Exam"]  # cleaned, duplicates (any case) dropped, sorted
    b = client.post("/api/notes", json={"title": "Bases"}).json()
    r = client.patch(f"/api/notes/{b['id']}", json={"tags": ["exam", "revise"]}).json()
    assert r["tags"] == ["Exam", "revise"]  # existing tag reused with its original spelling

    assert client.get("/api/tags").json() == [
        {"name": "chapter 3", "note_count": 1}, {"name": "Exam", "note_count": 2}, {"name": "revise", "note_count": 1}]
    titles = lambda **p: sorted(n["title"] for n in client.get("/api/notes", params=p).json())
    assert titles(tag="exam") == ["Acids", "Bases"]
    assert titles(tag="revise") == ["Bases"]
    assert titles(q="#rev") == ["Bases"] and titles(q="chap") == ["Acids"]
    assert client.get("/api/notes").json()[0]["tags"]  # list rows carry tags

    client.patch(f"/api/notes/{b['id']}", json={"tags": []})
    client.delete(f"/api/notes/{a['id']}")
    assert client.get("/api/tags").json() == []  # unused tags disappear


def test_tag_limits(client):
    assert client.post("/api/notes", json={"tags": ["x" * 31]}).status_code == 422
    r = client.post("/api/notes", json={"tags": [f"t{i}" for i in range(21)]})
    assert r.status_code == 422 and "at most 20 tags" in r.json()["detail"]


def test_backup_keeps_tags(client):
    client.post("/api/notes", json={"title": "Tagged", "tags": ["exam"]})
    backup = client.get("/api/backup").json()
    assert backup["notes"][0]["tags"] == ["exam"]
    client.post("/api/restore?mode=replace", content=json.dumps(backup))
    assert client.get("/api/notes").json()[0]["tags"] == ["exam"]
    del backup["notes"][0]["tags"]  # backups made before tags existed still restore
    assert client.post("/api/restore?mode=replace", content=json.dumps(backup)).status_code == 200
