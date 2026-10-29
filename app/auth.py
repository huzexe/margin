"""Phone access: other devices on the home network must enter the PIN; this computer never does.

A device that enters the right PIN gets a signed cookie (valid 30 days). "Sign out all phones"
replaces the signing secret, which makes every existing cookie invalid.
"""

import hashlib
import hmac
import ipaddress
import secrets
import socket
import time

from fastapi import Request

from . import config

COOKIE = "margin_session"
COOKIE_DAYS = 30
MAX_FAILURES = 5
LOCKOUT_SECONDS = 300

_failures: dict[str, tuple[int, float]] = {}  # device address -> (failed tries, locked until)


def lan_address() -> str | None:
    """This computer's address on the home network (no data is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # reserved test address; only picks the outgoing interface
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def allowed_hosts() -> list[str]:
    hosts = ["127.0.0.1", "localhost", "testserver"]
    if config.PHONE_ACCESS:
        ip = lan_address()
        if ip:
            hosts.append(ip)
        hosts.append(f"{socket.gethostname()}.local")
    return hosts


def is_this_computer(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "testclient"  # FastAPI's test client


def _secret() -> bytes:
    path = config.SECRET_PATH
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return bytes.fromhex(path.read_text().strip())


def rotate_secret() -> None:
    path = config.SECRET_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secrets.token_hex(32))
    path.chmod(0o600)


def make_cookie() -> str:
    expires = int(time.time()) + COOKIE_DAYS * 86400
    sig = hmac.new(_secret(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def cookie_valid(value: str | None) -> bool:
    if not value or "." not in value:
        return False
    expires, sig = value.split(".", 1)
    if not expires.isdigit() or int(expires) < time.time():
        return False
    good = hmac.new(_secret(), expires.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good)


def is_allowed(request: Request) -> bool:
    return is_this_computer(request) or cookie_valid(request.cookies.get(COOKIE))


def check_pin(device: str, pin: str) -> tuple[bool, str | None]:
    """Returns (ok, error message). Locks a device out after repeated wrong PINs."""
    tries, locked_until = _failures.get(device, (0, 0.0))
    if locked_until > time.time():
        minutes = max(1, round((locked_until - time.time()) / 60))
        return False, f"Too many wrong PINs. Try again in {minutes} minute{'s' if minutes > 1 else ''}."
    if config.PIN and hmac.compare_digest(pin.encode(), config.PIN.encode()):
        _failures.pop(device, None)
        return True, None
    tries += 1
    if tries >= MAX_FAILURES:
        _failures[device] = (0, time.time() + LOCKOUT_SECONDS)
        return False, "Too many wrong PINs. Try again in 5 minutes."
    _failures[device] = (tries, 0.0)
    return False, "Wrong PIN."
