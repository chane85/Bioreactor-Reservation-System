"""
Auto-starts the sandbox FastAPI backend as a child process.
Import this from any Streamlit page that needs the backend running.
Python's module cache ensures the process is only spawned once per session.
"""
import atexit
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

_THIS_DIR         = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR      = os.path.normpath(os.path.join(_THIS_DIR, '..', 'sandbox_v2', 'backend'))
_BACKEND_PORT     = 8561
_REQUIRED_VERSION = 10  # must match _API_VERSION in main.py

_proc = None  # module-level — persists across Streamlit reruns


def _port_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', _BACKEND_PORT)) == 0


def _backend_version() -> int:
    """Return the running backend's API version, or 0 on any error."""
    try:
        res = urllib.request.urlopen(
            f'http://127.0.0.1:{_BACKEND_PORT}/api/version', timeout=2
        )
        return json.loads(res.read()).get('version', 0)
    except Exception:
        return 0


def _force_kill_port():
    """Force-kill whatever process holds the port (fallback for old backends)."""
    if sys.platform != 'win32':
        return
    try:
        out = subprocess.check_output(
            ['netstat', '-ano'], text=True, timeout=5, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if f':{_BACKEND_PORT} ' in line and 'LISTENING' in line:
                pid = line.split()[-1]
                subprocess.run(
                    ['taskkill', '/F', '/PID', pid],
                    capture_output=True, timeout=5
                )
                time.sleep(0.5)
                break
    except Exception:
        pass


def _shutdown_old_backend():
    """Shut down whatever is running on the backend port."""
    if not _port_open():
        return

    # Try graceful HTTP shutdown first
    try:
        req = urllib.request.Request(
            f'http://127.0.0.1:{_BACKEND_PORT}/admin/shutdown',
            data=b'', method='POST'
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # expected: connection drops when backend exits

    # Wait up to 3 s for the port to free
    for _ in range(12):
        time.sleep(0.25)
        if not _port_open():
            return

    # HTTP shutdown didn't work (old backend without /admin/shutdown) — force-kill
    _force_kill_port()
    for _ in range(8):
        time.sleep(0.25)
        if not _port_open():
            break


def _wait_ready(timeout=8.0):
    """Wait until the backend is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open():
            return
        time.sleep(0.25)


def _cleanup():
    if _proc and _proc.poll() is None:
        _proc.terminate()


def ensure_running():
    global _proc
    if _proc is not None and _proc.poll() is None:
        # We own this process — check if it's current
        if _backend_version() >= _REQUIRED_VERSION:
            return
        # Stale code: terminate our own process and restart
        _proc.terminate()
        try:
            _proc.wait(timeout=3)
        except Exception:
            pass
        _proc = None

    _shutdown_old_backend()

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    _proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app',
         '--host', '0.0.0.0', '--port', str(_BACKEND_PORT)],
        cwd=_BACKEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    atexit.register(_cleanup)
    _wait_ready()  # block until uvicorn is accepting connections


ensure_running()  # run immediately on first import
