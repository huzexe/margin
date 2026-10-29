"""Heartbeat, auto-stop and the Quit endpoint."""

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config, lifecycle

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")

    class FakeServer:
        should_exit = False

    monkeypatch.setattr(lifecycle, "server", FakeServer())
    from app.main import app

    with TestClient(app) as c:
        yield c, lifecycle


def test_heartbeat_resets_idle_time(client):
    c, lifecycle = client
    lifecycle._last_seen -= 500
    assert lifecycle.idle_seconds() > 400
    assert c.post("/api/heartbeat").status_code == 204
    assert lifecycle.idle_seconds() < 5


def test_quit_needs_json_and_this_computer(client):
    c, lifecycle = client
    # A plain form/text post (what another website could send) is rejected
    assert c.post("/api/shutdown", content="stop=true",
                  headers={"Content-Type": "text/plain"}).status_code == 422
    assert lifecycle.server.should_exit is False
    phone = TestClient(c.app, client=("192.168.1.9", 5000))
    assert phone.post("/api/shutdown", json={"stop": True}).status_code in (401, 403)
    assert lifecycle.server.should_exit is False
    assert c.post("/api/shutdown", json={"stop": True}).json() == {"ok": True}
    assert lifecycle.server.should_exit is True


def test_watchdog_stops_when_idle(monkeypatch):
    from app import config, lifecycle

    class FakeServer:
        should_exit = False

    monkeypatch.setattr(lifecycle, "server", FakeServer())
    monkeypatch.setattr(config, "AUTO_STOP_SECONDS", 0.3)
    asyncio.run(asyncio.wait_for(lifecycle.watchdog(), timeout=5))
    assert lifecycle.server.should_exit is True
