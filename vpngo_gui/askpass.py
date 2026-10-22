"""Answer sudo's password requests from vpngo with this app's own dialog.

vpngo runs without a terminal, so sudo starts the program named in
SUDO_ASKPASS. That program is a tiny script that runs `python -m vpngo_gui
--askpass`, which asks the running interface over a private Unix socket. The
interface knows which action is running, asks once, checks the password with
sudo itself, and answers every request of that action with it. When the action
ends the password is forgotten.
"""

import json
import os
import secrets
import shlex
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


SOCKET_ENV = "VPNGO_GUI_ASKPASS"
TOKEN_ENV = "VPNGO_GUI_TOKEN"


def client(prompt):
    """The SUDO_ASKPASS side: print the password and exit 0, or exit 1 to cancel."""
    path, token = os.environ.get(SOCKET_ENV), os.environ.get(TOKEN_ENV)
    if not path or not token:
        return 1
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(path)
            connection.sendall(json.dumps({"token": token, "prompt": prompt}).encode() + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data += chunk
        answer = json.loads(data or b"{}")
    except (OSError, ValueError):
        return 1
    password = answer.get("password")
    if not isinstance(password, str):
        return 1
    sys.stdout.write(password + "\n")
    return 0


def password_valid(password):
    """Ask sudo itself; -k ignores any cached credential so the check is real."""
    try:
        result = subprocess.run(["sudo", "-S", "-k", "-v", "-p", ""], input=password + "\n", text=True,
                                capture_output=True, timeout=30, start_new_session=True, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


class Broker:
    """Owns the socket, the helper script, and the per-action tokens (GUI thread only)."""

    def __init__(self, ask):
        from PySide6.QtNetwork import QLocalServer
        self.ask = ask  # ask(action_text) -> password or None, shown in the GUI thread
        self.directory = Path(tempfile.mkdtemp(prefix="vpngo-gui-"))
        os.chmod(self.directory, 0o700)
        self.socket_path = self.directory / "askpass.sock"
        self.script = self.directory / "askpass"
        package_root = Path(__file__).resolve().parent.parent
        self.script.write_text(
            f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(package_root / 'run.py'))} "
            "--askpass \"$@\"\n", encoding="utf-8")
        self.script.chmod(0o700)
        self.actions = {}
        self.queue = []
        self.answering = False
        self.server = QLocalServer()
        self.server.listen(str(self.socket_path))
        self.server.newConnection.connect(self._accept)

    def begin(self, action_text):
        """Environment for one action's vpngo commands; pass the token to end() afterwards."""
        token = secrets.token_urlsafe(24)
        self.actions[token] = {"text": action_text, "password": None}
        return token, {"SUDO_ASKPASS": str(self.script), SOCKET_ENV: str(self.socket_path), TOKEN_ENV: token}

    def end(self, token):
        """Forget the action's password; True when the user cancelled the password dialog."""
        return bool((self.actions.pop(token, None) or {}).get("cancelled"))

    def close(self):
        self.server.close()
        self.server.deleteLater()
        for path in (self.socket_path, self.script):
            path.unlink(missing_ok=True)
        try:
            self.directory.rmdir()
        except OSError:
            pass

    def _accept(self):
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            connection.readyRead.connect(lambda c=connection: self._read(c))

    def _read(self, connection):
        if not connection.canReadLine():
            return
        try:
            request = json.loads(bytes(connection.readLine()).decode())
        except ValueError:
            request = {}
        self.queue.append((connection, request.get("token")))
        self._next()

    def _next(self):
        # One dialog at a time; requests that arrive meanwhile reuse its answer.
        if self.answering or not self.queue:
            return
        self.answering = True
        connection, token = self.queue.pop(0)
        action = self.actions.get(token)
        password = None
        if action is not None and not action.get("cancelled"):
            if action["password"] is None:
                action["password"] = self.ask(action["text"])
                # A cancelled dialog cancels the whole action instead of reopening per retry.
                action["cancelled"] = action["password"] is None
            password = action["password"]
        reply = {"password": password} if password is not None else {"cancel": True}
        connection.write(json.dumps(reply).encode() + b"\n")
        connection.flush()
        connection.disconnectFromServer()
        self.answering = False
        self._next()
