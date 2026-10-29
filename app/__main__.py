"""Start Margin with: python -m app   (start.py does this for you)"""

import socket
import sys

import uvicorn

from . import auth, config, lifecycle


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    local = f"http://127.0.0.1:{config.PORT}"
    if not port_is_free(config.PORT):
        sys.exit(
            f"Port {config.PORT} is already in use. Margin may already be running: open {local}\n"
            f"To use another port, set MARGIN_PORT=8001 in the .env file."
        )

    lines = [f"Margin is running at {local}"]
    if config.PHONE_ACCESS:
        if len(config.PIN) < 4:
            sys.exit(
                "Phone access is on (MARGIN_PHONE_ACCESS in .env) but MARGIN_PIN is missing or shorter than "
                "4 characters.\nAdd a line like MARGIN_PIN=482913 to .env, or turn phone access off."
            )
        ip = auth.lan_address()
        if ip:
            lines.append(f"On your phone (same Wi-Fi), open http://{ip}:{config.PORT} and enter your PIN.")
            if sys.platform.startswith("linux"):
                lines.append(f"If the phone can't connect, allow the port once: sudo firewall-cmd --add-port={config.PORT}/tcp")
            elif sys.platform == "win32":
                lines.append("If Windows asks whether to allow Python on private networks, choose Allow.")
        else:
            lines.append("Phone access is on, but this computer doesn't seem to be on a network.")
    if config.AUTO_STOP:
        lines.append("Started by the Margin app: it stops by itself a few minutes after its last window closes.")
    else:
        lines.append("Press Ctrl+C to stop.")
    print("\n" + "\n".join(f"  {line}" for line in lines) + "\n", flush=True)

    from .main import app

    server = uvicorn.Server(uvicorn.Config(app, host=config.HOST, port=config.PORT, log_level="warning"))
    lifecycle.server = server  # lets "Quit Margin" and the auto-stop end the server cleanly
    server.run()
