"""Keeping Margin running only while it's being used.

Every open Margin page sends a small "still here" signal (POST /api/heartbeat) every 30 seconds.
When Margin was started by the app launcher (MARGIN_AUTO_STOP=1), it stops by itself once no
page has checked in for a while, i.e. after the last window is closed. Started from a
terminal, it keeps running until Ctrl+C.
"""

import asyncio
import time

from . import config

server = None  # the running uvicorn.Server, set by app/__main__.py
_last_seen = time.monotonic()


def touch() -> None:
    global _last_seen
    _last_seen = time.monotonic()


def idle_seconds() -> float:
    return time.monotonic() - _last_seen


def request_exit() -> None:
    """Ask the server to finish open requests and stop."""
    if server is not None:
        server.should_exit = True


async def watchdog() -> None:
    touch()  # the startup counts as activity; the window opens a few seconds later
    while True:
        await asyncio.sleep(min(15, config.AUTO_STOP_SECONDS / 3))
        if idle_seconds() > config.AUTO_STOP_SECONDS:
            request_exit()
            return
