#!/usr/bin/env python3
"""Margin launcher for Windows, Linux and macOS (uses only Python's standard library).

    python start.py              set up on first use, then run Margin here (Ctrl+C stops it)
    python start.py --app        open Margin in its own app window (starts it in the background if needed)
    python start.py --install    set up, then add Margin to the app menu (Linux) or Start Menu + Desktop (Windows)
    python start.py --uninstall  remove those shortcuts again (your notes are kept)
    python start.py --quit       stop Margin

On Windows, "python" may be "py" instead. run.sh (Linux/macOS) and run.bat (Windows) run the first form.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
# The log sits next to the notes database (data/ unless MARGIN_DB_PATH points elsewhere)
LOG = Path(os.environ.get("MARGIN_DB_PATH") or ROOT / "data" / "margin.db").parent / "margin.log"
WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
MIN_PYTHON = (3, 11)


# ---------- Small helpers ----------

def say(message: str) -> None:
    if sys.stdout:  # pythonw (Windows shortcut) has no console
        print(message, flush=True)


def read_env(path: Path = ROOT / ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def port() -> int:
    return int(os.environ.get("MARGIN_PORT") or read_env().get("MARGIN_PORT") or 8000)


def url() -> str:
    return f"http://127.0.0.1:{port()}"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(url() + "/static/favicon.svg", timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def venv_python(windowless: bool = False) -> Path:
    if WINDOWS:
        return VENV / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
    return VENV / "bin" / "python"


def system_python(windowless: bool = False) -> Path:
    """The Python that was installed on the computer (not the project's private copy)."""
    base = Path(sys.base_prefix if sys.prefix != sys.base_prefix else sys.exec_prefix)
    if WINDOWS:
        exe = base / ("pythonw.exe" if windowless else "python.exe")
        return exe if exe.exists() else Path(sys.executable)
    found = shutil.which("python3")
    return Path(found) if found else Path(sys.executable)


def notify(message: str) -> None:
    """Small desktop notification where available (used while starting in the background)."""
    try:
        if MAC:
            subprocess.run(["osascript", "-e", f'display notification "{message}" with title "Margin"'], timeout=5)
        elif not WINDOWS and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "Margin", "-i", "margin", "Margin", message], timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


def error_box(message: str) -> None:
    """Show an error even when there is no terminal window."""
    say(message)
    try:
        if WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Margin", 0x10)
        elif MAC:
            subprocess.run(["osascript", "-e", f'display alert "Margin" message "{message}"'], timeout=60)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", "critical", "-a", "Margin", "Margin", message], timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


# ---------- Setup ----------

def needs_setup() -> bool:
    marker = VENV / ".installed"
    req = ROOT / "requirements.txt"
    return not venv_python().exists() or not marker.exists() or req.stat().st_mtime > marker.stat().st_mtime


def setup(quiet: bool = False) -> None:
    """Create the private Python environment and install what Margin needs (only when required)."""
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"Margin needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; this is {sys.version.split()[0]}.\n"
            "Windows: install it from https://www.python.org/downloads/  ·  Fedora: sudo dnf install python3"
        )
    env_file = ROOT / ".env"
    if not env_file.exists() and (ROOT / ".env.example").exists():
        shutil.copy(ROOT / ".env.example", env_file)
        if not WINDOWS:
            env_file.chmod(0o600)
        say("Created .env. Add your Gemini API key to it (see README) to use Enhance notes.")
    if not needs_setup():
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    out = open(LOG, "ab") if quiet else None

    def run(args: list, what: str) -> None:
        say(what)
        result = subprocess.run([str(a) for a in args], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT if out else None)
        if result.returncode != 0:
            raise SystemExit(f"Setup failed while: {what.rstrip('.… ')}. Details are above" +
                             (f" and in {LOG}" if out else "") + ".")

    try:
        if not venv_python().exists():
            run([sys.executable, "-m", "venv", VENV], "Creating Margin's private Python environment (.venv) …")
        pip = [venv_python(), "-m", "pip", "install", "--disable-pip-version-check"]
        run([*pip, "--quiet", "--upgrade", "pip"], "Updating the package installer …")
        run([*pip, "--quiet", "-r", ROOT / "requirements.txt"], "Installing Margin's packages (a few minutes the first time) …")
        # No browser download: PDFs are made with the Chrome, Edge or Chromium already installed
        (VENV / ".installed").touch()
    finally:
        if out:
            out.close()


# ---------- Running ----------

def run_here() -> int:
    """Run Margin in this terminal until Ctrl+C (or until the terminal is closed)."""
    setup()
    proc = subprocess.Popen([str(venv_python()), "-m", "app"], cwd=ROOT)
    if not WINDOWS:
        import signal

        # If this launcher is stopped or its terminal closes, stop Margin too (no leftover server)
        def stop(signum, frame):
            proc.terminate()
        for sig in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, stop)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        return proc.wait()  # Ctrl+C also reached Margin, which is shutting down


def start_background() -> subprocess.Popen:
    """Start Margin without a window; it stops by itself after its last page is closed."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "ab")
    env = {**os.environ, "MARGIN_AUTO_STOP": "1"}
    extra = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
             if WINDOWS else {"start_new_session": True})
    return subprocess.Popen([str(venv_python()), "-m", "app"], cwd=ROOT, env=env,
                            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **extra)


def profile_dir() -> Path:
    """Separate browser profile for the Margin window (keeps it apart from your normal browsing)."""
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Margin" / "window"
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Margin" / "window"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "margin" / "window"


def find_browser() -> list[str] | None:
    """A Chromium-based browser that can open Margin as an app window: Chrome, Chromium or Edge."""
    if os.environ.get("MARGIN_APP_BROWSER"):  # used by the tests
        return [os.environ["MARGIN_APP_BROWSER"]]
    if WINDOWS:
        bases = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        for parts in (("Google", "Chrome", "Application", "chrome.exe"),
                      ("Microsoft", "Edge", "Application", "msedge.exe")):
            for base in filter(None, bases):
                exe = Path(base, *parts)
                if exe.exists():
                    return [str(exe)]
        return None
    if MAC:
        for app in ("Google Chrome", "Microsoft Edge", "Chromium"):
            exe = Path(f"/Applications/{app}.app/Contents/MacOS/{app}")
            if exe.exists():
                return [str(exe)]
        return None
    for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium",
                 "microsoft-edge", "microsoft-edge-stable"):
        if shutil.which(name):
            return [name]
    return None


def open_window() -> None:
    browser = find_browser()
    if not browser:
        webbrowser.open(url())  # no Chrome/Edge: a normal browser tab works too
        return
    profile = profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    args = [*browser, f"--app={url()}", f"--user-data-dir={profile}", "--class=Margin",
            "--no-first-run", "--no-default-browser-check", "--window-size=1400,900"]
    extra = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
             if WINDOWS else {"start_new_session": True})
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra)


def app_mode() -> int:
    try:
        if needs_setup():
            notify("Updating… this can take a few minutes.")
        setup(quiet=True)
    except SystemExit as e:
        error_box(str(e))
        return 1
    if not server_up():
        notify("Starting…")
        proc = start_background()
        deadline = time.time() + 120
        while not server_up():
            if proc.poll() is not None:
                error_box(f"Margin couldn't start. Details are in {LOG}")
                return 1
            if time.time() > deadline:
                error_box(f"Margin is taking too long to start. Details are in {LOG}")
                return 1
            time.sleep(0.4)
    open_window()
    return 0


def quit_app() -> int:
    """Stop Margin and close its app windows."""
    request = urllib.request.Request(url() + "/api/shutdown", data=b'{"stop": true}', method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=5)
        say("Margin is stopping.")
    except (urllib.error.URLError, OSError):
        say("Margin isn't running.")
    close_windows()
    return 0


def close_windows() -> None:
    profile = str(profile_dir())
    try:
        if WINDOWS:
            match = profile.replace("'", "''")
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
                            f"'*--user-data-dir={match}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                           timeout=20, capture_output=True)
        elif shutil.which("pkill"):
            subprocess.run(["pkill", "-f", f"--user-data-dir={profile}"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


# ---------- Shortcuts ----------

def linux_desktop_entry(python: Path) -> str:
    start = ROOT / "start.py"
    return f"""[Desktop Entry]
Type=Application
Version=1.5
Name=Margin
GenericName=Study Notes
Comment=Turn rough lecture notes into clear study notes
Exec="{python}" "{start}" --app
Icon=margin
Terminal=false
Categories=Education;
Keywords=notes;study;lecture;revision;pdf;
StartupNotify=true
StartupWMClass=chrome-127.0.0.1__-Default
Actions=quit;

[Desktop Action quit]
Name=Quit Margin
Exec="{python}" "{start}" --quit
"""


def windows_shortcut_script(pythonw: Path) -> str:
    """PowerShell that creates Start Menu and Desktop shortcuts (single quotes are doubled for PowerShell)."""
    q = lambda p: str(p).replace("'", "''")
    start, icon = ROOT / "start.py", ROOT / "static" / "app-icon.ico"
    return (
        "$shell = New-Object -ComObject WScript.Shell\n"
        "function Make($dir, $name, $arguments) {\n"
        "  $link = $shell.CreateShortcut((Join-Path $dir $name))\n"
        f"  $link.TargetPath = '{q(pythonw)}'\n"
        "  $link.Arguments = $arguments\n"
        f"  $link.WorkingDirectory = '{q(ROOT)}'\n"
        f"  $link.IconLocation = '{q(icon)},0'\n"
        "  $link.Description = 'Margin study notes'\n"
        "  $link.Save()\n"
        "}\n"
        "$programs = [Environment]::GetFolderPath('Programs')\n"
        "$desktop = [Environment]::GetFolderPath('Desktop')\n"
        f"Make $programs 'Margin.lnk' '\"{q(start)}\" --app'\n"
        f"Make $desktop 'Margin.lnk' '\"{q(start)}\" --app'\n"
        f"Make $programs 'Quit Margin.lnk' '\"{q(start)}\" --quit'\n"
    )


def install() -> int:
    setup()
    if WINDOWS:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                                 windows_shortcut_script(system_python(windowless=True))])
        if result.returncode != 0:
            raise SystemExit("Couldn't create the shortcuts. You can still start Margin with run.bat.")
        say("Margin is in your Start Menu and on your Desktop. Click it to open Margin.")
    elif MAC:
        say("Shortcuts aren't created on macOS. Open Margin with:  python3 start.py --app")
    else:
        apps = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications"
        icons = apps.parent / "icons" / "hicolor" / "scalable" / "apps"
        apps.mkdir(parents=True, exist_ok=True)
        icons.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "static" / "app-icon.svg", icons / "margin.svg")
        (apps / "margin.desktop").write_text(linux_desktop_entry(system_python()), encoding="utf-8")
        for cmd in (["update-desktop-database", apps], ["gtk-update-icon-cache", "-q", "-f", "-t", icons.parents[2]]):
            if shutil.which(cmd[0]):
                subprocess.run([str(c) for c in cmd], capture_output=True)
        say("Margin is in your app menu: press the Super (Windows) key and type Margin.")
        say("To keep it in the dock: open it, right-click its icon, choose 'Pin to Dash'.")
    return 0


def uninstall() -> int:
    if WINDOWS:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "foreach ($d in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) "
                        "{ Remove-Item -ErrorAction SilentlyContinue (Join-Path $d 'Margin.lnk'), (Join-Path $d 'Quit Margin.lnk') }"])
    elif not MAC:
        share = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        for f in (share / "applications" / "margin.desktop", share / "icons" / "hicolor" / "scalable" / "apps" / "margin.svg"):
            f.unlink(missing_ok=True)
    shutil.rmtree(profile_dir(), ignore_errors=True)  # the app window's browser profile; no notes are stored there
    say("Margin's shortcuts were removed. Your notes are still in the data folder.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start or install Margin.")
    group = parser.add_mutually_exclusive_group()
    for flag, text in [("--app", "open Margin in its own window"), ("--install", "add Margin to the app menu / Start Menu"),
                       ("--uninstall", "remove Margin's shortcuts"), ("--quit", "stop Margin")]:
        group.add_argument(flag, action="store_true", help=text)
    args = parser.parse_args()
    try:
        if args.app:
            return app_mode()
        if args.install:
            return install()
        if args.uninstall:
            return uninstall()
        if args.quit:
            return quit_app()
        return run_here()
    except SystemExit as e:
        if isinstance(e.code, str):
            say(e.code)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
