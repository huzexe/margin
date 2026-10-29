"""PDF helper tests (the full PDF flow is checked in the browser tests)."""

from app.services.pdf import PdfSettings, _norm, filename


def test_filename():
    assert filename("Binary Search: Lecture 4!") == "Binary-Search-Lecture-4.pdf"
    assert filename("Newton's Laws of Motion") == "Newtons-Laws-of-Motion.pdf"
    assert filename("   ") == "Margin-note.pdf"
    assert filename("Ünïcode Notes") == "Ünïcode-Notes.pdf"


def test_settings_query_and_validation():
    s = PdfSettings(toc=False, size="large")
    assert s.query() == "toc=0&flashcards=1&rough=0&size=large&margins=normal"


def test_heading_normalization_ignores_ligatures_and_spacing():
    assert _norm("Eﬃcient  Search—Basics") == _norm("efficient search basics")


def test_pdf_rejects_bad_settings(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from app.main import app

    with TestClient(app) as c:
        note = c.post("/api/notes", json={"title": "x"}).json()
        assert c.get(f"/api/notes/{note['id']}/pdf", params={"size": "huge"}).status_code == 422
        assert c.get("/api/notes/999/pdf").status_code == 404
        for path in [f"/notes/{note['id']}/export", f"/notes/{note['id']}/print"]:
            assert c.get(path).status_code == 200


def test_pdf_uses_installed_browsers_first(monkeypatch):
    from app.services import pdf

    monkeypatch.delenv("MARGIN_PDF_BROWSER", raising=False)
    monkeypatch.setattr(pdf.shutil, "which", lambda name: "/usr/bin/chromium" if name == "chromium" else None)
    opts = pdf.launch_options()
    assert opts[:3] == [{"channel": "chrome"}, {"channel": "msedge"}, {"executable_path": "/usr/bin/chromium"}]
    assert opts[-1] == {}  # Playwright's own engine is only the last resort
    monkeypatch.setenv("MARGIN_PDF_BROWSER", "/opt/mybrowser/chrome")
    assert pdf.launch_options()[0] == {"executable_path": "/opt/mybrowser/chrome"}


def test_pdf_reports_missing_browser(monkeypatch):
    import asyncio
    from app.services import pdf

    async def fail(**kwargs):
        from playwright.async_api import Error
        raise Error("not installed")

    class FakePlaywright:
        class chromium:
            launch = staticmethod(fail)

    monkeypatch.setattr(pdf, "_browser", None)
    monkeypatch.setattr(pdf, "_playwright", FakePlaywright())
    try:
        asyncio.run(pdf._get_browser())
        raise AssertionError("expected PdfError")
    except pdf.PdfError as e:
        assert "Google Chrome, Microsoft Edge or Chromium" in e.message
