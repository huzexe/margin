"""Enhance tests. Gemini is replaced by a stand-in, so these never use the real service."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.services import llm
from app.services.enhance import Block, EnhancedNotes, Section, inline, to_editor

SAMPLE = EnhancedNotes(
    sections=[Section(heading="What is **binary** search?", blocks=[
        Block(type="paragraph", text="Works on a **sorted** array. Uses `mid`."),
        Block(type="definition", term="Search space", text="the part still left to check"),
        Block(type="definition", term="Orphan term", text=""),  # no meaning: dropped
        Block(type="steps", text="", items=["Compare with middle", "Go left or right"]),
        Block(type="formula", text="n is the array size", latex="$T(n) = O(\\log n)$"),
        Block(type="verify", text="Your notes say X; check the slides."),
        Block(type="paragraph", text=""),  # empty: dropped
    ])],
    key_takeaways=["Needs sorted data"],
    flashcards=[{"question": "Time?", "answer": "O(log n)"}],
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_llm(monkeypatch):
    calls = []

    def fake(system, prompt, schema, **kw):
        calls.append(prompt)
        return SAMPLE

    monkeypatch.setattr(llm, "generate_json", fake)
    return calls


def test_inline_escapes_html():
    assert inline("<script>alert(1)</script> **bold**") == "&lt;script&gt;alert(1)&lt;/script&gt; <b>bold</b>"
    assert inline("`a < b` and *it*") == '<code class="inline-code">a &lt; b</code> and <i>it</i>'
    assert inline("2 * 3 * 4") == "2 * 3 * 4"  # lone asterisks are not italics


def test_to_editor_blocks():
    blocks = to_editor(SAMPLE)["blocks"]
    kinds = [b["type"] + ("/" + b["data"]["kind"] if b["type"] == "callout" else "") for b in blocks]
    assert kinds == [
        "header", "paragraph", "callout/definition", "list", "formula", "callout/verify",
        "header", "callout/takeaway", "header", "flashcards",
    ]
    assert blocks[0]["data"] == {"text": "What is binary search?", "level": 2}
    assert blocks[4]["data"]["latex"] == "T(n) = O(\\log n)"  # $ signs removed
    assert blocks[3]["data"]["style"] == "ordered"


def test_enhance_flow(client, fake_llm):
    subj = client.post("/api/subjects", json={"name": "Algorithms"}).json()
    note = client.post("/api/notes", json={"title": "Binary search", "subject_id": subj["id"],
                                           "rough_text": "sorted array\nO(log n)"}).json()

    r = client.post(f"/api/notes/{note['id']}/enhance", json={"options": {"flashcards": True, "detail": "concise"}})
    assert r.status_code == 200, r.text
    result = r.json()
    assert "CONCISE" in fake_llm[0] and "Flashcards:" in fake_llm[0] and "Subject: Algorithms" in fake_llm[0]

    # the page saves the result
    saved = client.patch(f"/api/notes/{note['id']}", json={
        "content": result["content"], "options": result["options"],
        "source_hash": result["source_hash"], "content_edited": False,
    }).json()
    assert saved["content"]["blocks"][0]["type"] == "header"
    assert saved["options"]["detail"] == "concise"

    # enhanced text is searchable
    assert [n["id"] for n in client.get("/api/notes", params={"q": "left to check"}).json()] == [note["id"]]

    # same notes and options again: asks first
    again = client.post(f"/api/notes/{note['id']}/enhance", json={"options": {"flashcards": True, "detail": "concise"}})
    assert again.status_code == 409
    forced = client.post(f"/api/notes/{note['id']}/enhance",
                         json={"options": {"flashcards": True, "detail": "concise"}, "force": True})
    assert forced.status_code == 200
    # different options: no question
    assert client.post(f"/api/notes/{note['id']}/enhance", json={"options": {}}).status_code == 200


def test_enhance_needs_rough_notes(client, fake_llm):
    note = client.post("/api/notes", json={"title": "Empty"}).json()
    r = client.post(f"/api/notes/{note['id']}/enhance", json={})
    assert r.status_code == 422 and r.json()["detail"] == "Write some rough notes first."
    assert fake_llm == []


def test_service_errors_are_friendly(client, monkeypatch):
    def busy(*a, **kw):
        raise llm.LLMError(llm.MSG_BUSY, status=429, retry_after=60)

    monkeypatch.setattr(llm, "generate_json", busy)
    note = client.post("/api/notes", json={"rough_text": "x"}).json()
    r = client.post(f"/api/notes/{note['id']}/enhance", json={})
    assert r.status_code == 429
    assert r.json()["detail"] == "Service is busy. Please try again in a minute."
    assert r.headers["retry-after"] == "60"


def test_content_validation(client):
    note = client.post("/api/notes", json={"title": "x"}).json()
    bad = client.patch(f"/api/notes/{note['id']}", json={"content": {"blocks": [{"type": "script", "data": {}}]}})
    assert bad.status_code == 422
    huge = {"blocks": [{"type": "paragraph", "data": {"text": "x" * 1_100_000}}]}
    assert client.patch(f"/api/notes/{note['id']}", json={"content": huge}).status_code == 422
    cleared = client.patch(f"/api/notes/{note['id']}", json={"content": None}).json()
    assert cleared["content"] is None


def test_old_database_is_upgraded(tmp_path, monkeypatch):
    from app import config, db

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE notes (id INTEGER PRIMARY KEY, subject_id INTEGER, title TEXT NOT NULL DEFAULT '',
        topic TEXT NOT NULL DEFAULT '', rough_text TEXT NOT NULL DEFAULT '', content_json TEXT,
        content_text TEXT NOT NULL DEFAULT '', options_json TEXT, source_hash TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    conn.close()
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init()
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(notes)")}
    assert "content_edited" in cols


def test_diagram_block_and_labels():
    from app.services.enhance import content_text, diagram_labels
    doc = EnhancedNotes(sections=[Section(heading="Flow", blocks=[
        Block(type="diagram", text="How **it** works", mermaid='```mermaid\nflowchart TD\n  A["Start here"] --> B{"Done?"}\n```'),
        Block(type="diagram", text="empty", mermaid="  "),  # no code: dropped
    ])], key_takeaways=[])
    blocks = to_editor(doc)["blocks"]
    assert [b["type"] for b in blocks] == ["header", "diagram"]
    assert blocks[1]["data"] == {"code": 'flowchart TD\n  A["Start here"] --> B{"Done?"}', "caption": "How it works"}
    assert diagram_labels(blocks[1]["data"]["code"]) == ["Start here", "Done?"]
    assert "Start here" in content_text({"blocks": blocks})


def test_diagrams_option_in_prompt():
    from app.services import prompts
    from app.services.enhance import EnhanceOptions
    with_d = prompts.build_prompt(title="t", subject=None, topic="", rough_text="x", options=EnhanceOptions(diagrams=True))
    without = prompts.build_prompt(title="t", subject=None, topic="", rough_text="x", options=EnhanceOptions())
    assert "Mermaid" in with_d and "Do not add diagram blocks." not in with_d
    assert "Do not add diagram blocks." in without


def test_regenerate_section(client, monkeypatch):
    seen = {}

    def fake(system, prompt, schema, **kw):
        seen["prompt"], seen["schema"] = prompt, schema
        return Section(heading="Basics", blocks=[Block(type="paragraph", text="New **text**")])

    monkeypatch.setattr(llm, "generate_json", fake)
    note = client.post("/api/notes", json={"title": "BS", "rough_text": "sorted array"}).json()
    section = [
        {"id": "h1", "type": "header", "data": {"text": "Basics", "level": 2}},
        {"id": "p1", "type": "paragraph", "data": {"text": "Old <b>text</b>"}},
        {"id": "l1", "type": "list", "data": {"style": "unordered", "items": [{"content": "one", "items": []}]}},
    ]
    r = client.post(f"/api/notes/{note['id']}/regenerate-section",
                    json={"blocks": section, "instruction": "Simpler", "options": {"detail": "concise"}})
    assert r.status_code == 200, r.text
    assert r.json()["blocks"] == [
        {"type": "header", "data": {"text": "Basics", "level": 2}},
        {"type": "paragraph", "data": {"text": "New <b>text</b>"}},
    ]
    assert seen["schema"] is Section
    assert "## Basics" in seen["prompt"] and "Old text" in seen["prompt"] and "- one" in seen["prompt"]
    assert "Simpler" in seen["prompt"] and "CONCISE" in seen["prompt"] and "sorted array" in seen["prompt"]

    bad = client.post(f"/api/notes/{note['id']}/regenerate-section", json={"blocks": [{"type": "evil", "data": {}}]})
    assert bad.status_code == 422


def test_fix_diagram(client, monkeypatch):
    from app.services.enhance import DiagramFix

    def fake(system, prompt, schema, **kw):
        assert "Parse error on line 2" in prompt and "A[Start(here)]" in prompt
        return DiagramFix(mermaid='```mermaid\nflowchart TD\n  A["Start (here)"]\n```')

    monkeypatch.setattr(llm, "generate_json", fake)
    r = client.post("/api/notes/diagrams/fix", json={"code": "flowchart TD\n  A[Start(here)]", "error": "Parse error on line 2"})
    assert r.status_code == 200
    assert r.json()["code"] == 'flowchart TD\n  A["Start (here)"]'
    assert client.post("/api/notes/diagrams/fix", json={"code": ""}).status_code == 422


def test_regenerate_mentions_other_sections(client, monkeypatch):
    seen = {}

    def fake(system, prompt, schema, **kw):
        seen["prompt"] = prompt
        return Section(heading="Why", blocks=[Block(type="paragraph", text="x")])

    monkeypatch.setattr(llm, "generate_json", fake)
    note = client.post("/api/notes", json={"rough_text": "tcp"}).json()
    content = {"blocks": [
        {"type": "header", "data": {"text": "Handshake", "level": 2}},
        {"type": "diagram", "data": {"code": "sequenceDiagram\n A->>B: SYN", "caption": "SYN, SYN-ACK, ACK"}},
        {"type": "header", "data": {"text": "Why", "level": 2}},
        {"type": "diagram", "data": {"code": "flowchart TD\n A-->B", "caption": "Own diagram"}},
        {"type": "header", "data": {"text": "Key takeaways", "level": 2}},
    ]}
    client.patch(f"/api/notes/{note['id']}", json={"content": content})
    r = client.post(f"/api/notes/{note['id']}/regenerate-section", json={"blocks": content["blocks"][2:4]})
    assert r.status_code == 200
    assert "- Section: Handshake" in seen["prompt"] and "- Diagram: SYN, SYN-ACK, ACK" in seen["prompt"]
    assert "Diagram: Own diagram" not in seen["prompt"] and "Section: Key takeaways" not in seen["prompt"]
