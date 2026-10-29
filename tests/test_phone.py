"""Phone access tests: other devices need the PIN, this computer never does."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_with_phone(tmp_path, monkeypatch):
    from app import auth, config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "SECRET_PATH", tmp_path / ".secret")
    monkeypatch.setattr(config, "PHONE_ACCESS", True)
    monkeypatch.setattr(config, "PIN", "482913")
    auth._failures.clear()
    from app.main import app
    return app


def phone(app):
    # A device on the home network: not this computer's own address
    return TestClient(app, client=("192.168.1.50", 50000))


def test_this_computer_needs_no_pin(app_with_phone):
    with TestClient(app_with_phone) as c:
        assert c.get("/api/notes").status_code == 200
        assert c.get("/").status_code == 200


def test_phone_is_locked_until_pin(app_with_phone):
    with phone(app_with_phone) as p:
        assert p.get("/api/notes").status_code == 401
        r = p.get("/notes/new", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/unlock?next=/notes/new"
        assert p.get("/unlock").status_code == 200
        assert p.get("/static/css/base.css").status_code == 200  # page styles load before unlocking

        bad = p.post("/api/unlock", json={"pin": "000000"})
        assert bad.status_code == 401 and bad.json()["detail"] == "Wrong PIN."
        good = p.post("/api/unlock", json={"pin": "482913"})
        assert good.status_code == 200
        cookie = good.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert p.get("/api/notes").status_code == 200  # cookie works

        # Only this computer may sign phones out
        assert p.post("/api/phone/sign-out-all").status_code == 403


def test_sign_out_all_phones(app_with_phone):
    with phone(app_with_phone) as p, TestClient(app_with_phone) as laptop:
        p.post("/api/unlock", json={"pin": "482913"})
        assert p.get("/api/notes").status_code == 200
        assert laptop.post("/api/phone/sign-out-all").status_code == 200
        assert p.get("/api/notes").status_code == 401


def test_lockout_after_wrong_pins(app_with_phone):
    with phone(app_with_phone) as p:
        for _ in range(4):
            assert p.post("/api/unlock", json={"pin": "1111"}).json()["detail"] == "Wrong PIN."
        assert "Too many wrong PINs" in p.post("/api/unlock", json={"pin": "1111"}).json()["detail"]
        # even the right PIN is refused while locked out
        assert "Too many wrong PINs" in p.post("/api/unlock", json={"pin": "482913"}).json()["detail"]


def test_forged_cookie_rejected(app_with_phone):
    from app import auth
    with phone(app_with_phone) as p:
        p.cookies.set(auth.COOKIE, "9999999999.deadbeef")
        assert p.get("/api/notes").status_code == 401


def test_phone_access_off_by_default(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "PHONE_ACCESS", False)
    from app.main import app
    with phone(app) as p:
        assert p.get("/api/notes").status_code == 401
        assert p.post("/api/unlock", json={"pin": "anything"}).status_code == 403
