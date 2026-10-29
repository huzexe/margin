"""Tests for start.py (the launcher). Windows and macOS paths are simulated."""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

import start


def test_read_env_and_port(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nGEMINI_API_KEY="abc"\n MARGIN_PORT = 8123 \nBROKEN LINE\n', encoding="utf-8")
    assert start.read_env(env) == {"GEMINI_API_KEY": "abc", "MARGIN_PORT": "8123"}
    monkeypatch.setattr(start, "read_env", lambda path=None: {"MARGIN_PORT": "8123"})
    monkeypatch.delenv("MARGIN_PORT", raising=False)
    assert start.port() == 8123 and start.url() == "http://127.0.0.1:8123"
    monkeypatch.setenv("MARGIN_PORT", "9000")  # the environment wins over .env
    assert start.port() == 9000


def test_find_browser_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "WINDOWS", True)
    monkeypatch.delenv("MARGIN_APP_BROWSER", raising=False)
    pf, local = tmp_path / "Program Files", tmp_path / "Local"
    monkeypatch.setenv("ProgramFiles", str(pf))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert start.find_browser() is None
    edge = pf / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()
    assert start.find_browser() == [str(edge)]  # every Windows PC has Edge
    chrome = local / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()
    assert start.find_browser() == [str(chrome)]  # Chrome is preferred when installed (even per-user)


def test_profile_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(start, "WINDOWS", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert start.profile_dir() == tmp_path / "Margin" / "window"
    monkeypatch.setattr(start, "WINDOWS", False)
    monkeypatch.setattr(start, "MAC", True)
    assert start.profile_dir() == Path.home() / "Library" / "Application Support" / "Margin" / "window"
    monkeypatch.setattr(start, "MAC", False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert start.profile_dir() == tmp_path / "margin" / "window"


def test_windows_shortcut_script_escapes_paths(monkeypatch):
    monkeypatch.setattr(start, "ROOT", Path(r"C:\Users\O'Brien\Margin"))
    script = start.windows_shortcut_script(Path(r"C:\Python313\pythonw.exe"))
    assert r"$link.TargetPath = 'C:\Python313\pythonw.exe'" in script
    assert r"C:\Users\O''Brien\Margin" in script and "O'Brien" not in script.replace("O''Brien", "")
    assert "GetFolderPath('Programs')" in script and "GetFolderPath('Desktop')" in script
    assert "app-icon.ico,0" in script and "--app'" in script and "'Quit Margin.lnk'" in script


def test_linux_desktop_entry(tmp_path):
    entry = start.linux_desktop_entry(Path("/usr/bin/python3"))
    assert f'Exec="/usr/bin/python3" "{start.ROOT / "start.py"}" --app' in entry
    assert "[Desktop Action quit]" in entry and "--quit" in entry
    if shutil.which("desktop-file-validate"):
        f = tmp_path / "margin.desktop"
        f.write_text(entry)
        result = subprocess.run(["desktop-file-validate", str(f)], capture_output=True, text=True)
        assert result.returncode == 0 and "error" not in result.stdout.lower(), result.stdout


def _up(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/static/favicon.svg", timeout=1)
        return True
    except OSError:
        return False


@pytest.mark.skipif(not start.venv_python().exists(), reason="needs the project's .venv")
def test_app_mode_starts_opens_and_stops(tmp_path):
    """start.py --app: starts Margin in the background, opens the window, Margin stops when idle; --quit stops it."""
    port = 8768
    calls = tmp_path / "browser-calls.txt"
    fake = tmp_path / "fake-browser.py"
    fake.write_text(f"import sys; open(r'{calls}', 'a').write(' '.join(sys.argv[1:]) + '\\n')\n")
    fake_cmd = tmp_path / "fake-browser"
    fake_cmd.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{fake}' \"$@\"\n")
    fake_cmd.chmod(0o755)
    env = {**os.environ, "MARGIN_PORT": str(port), "MARGIN_DB_PATH": str(tmp_path / "t.db"),
           "MARGIN_APP_BROWSER": str(fake_cmd), "MARGIN_AUTO_STOP_SECONDS": "3"}
    assert not _up(port)

    t = time.time()
    assert subprocess.run([sys.executable, str(start.ROOT / "start.py"), "--app"], env=env, timeout=120).returncode == 0
    assert _up(port), "Margin should be running after --app"
    args = calls.read_text()
    assert f"--app=http://127.0.0.1:{port}" in args and "--user-data-dir=" in args
    # No page is open (the stand-in browser loads nothing), so Margin stops by itself after ~3 s
    deadline = time.time() + 20
    while _up(port) and time.time() < deadline:
        time.sleep(0.5)
    assert not _up(port), "Margin should stop by itself when no window is open"

    # --quit stops a running Margin straight away
    subprocess.run([sys.executable, str(start.ROOT / "start.py"), "--app"], env={**env, "MARGIN_AUTO_STOP_SECONDS": "600"}, timeout=120)
    assert _up(port)
    subprocess.run([sys.executable, str(start.ROOT / "start.py"), "--quit"], env=env, timeout=30)
    deadline = time.time() + 10
    while _up(port) and time.time() < deadline:
        time.sleep(0.3)
    assert not _up(port), "--quit should stop Margin"
    assert time.time() - t < 90
