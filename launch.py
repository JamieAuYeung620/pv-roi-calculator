import os
import sys
import time
import atexit
import socket
import threading
import webbrowser
import signal
from urllib.request import urlopen
from urllib.error import URLError
from streamlit.web import bootstrap

if getattr(sys, "frozen", False):
    # PyInstaller bundle path
    ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))

APP = os.path.join(ROOT, "app.py")
LOCKFILE = "/tmp/pv_roi_calculator.lock"
LOGFILE = os.path.expanduser("~/Desktop/pv_roi_launcher.log")
DEFAULT_PORT = 8501


def _url_for_port(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/_stcore/health"


def _wait_for_port(host: str, port: int, timeout_s: float = 25.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _is_streamlit_healthy(port: int) -> bool:
    try:
        with urlopen(_health_url(port), timeout=1.5) as r:
            return 200 <= int(r.status) < 300
    except URLError:
        return False
    except Exception:
        return False


def _read_lock() -> tuple[int, int] | None:
    if not os.path.exists(LOCKFILE):
        return None
    try:
        raw = open(LOCKFILE, "r", encoding="utf-8").read().strip()
        pid_str, port_str = raw.split(",", 1)
        return int(pid_str), int(port_str)
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _remove_lock() -> None:
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
    except OSError:
        pass


def _claim_or_focus_existing() -> int:
    lock = _read_lock()
    if lock is not None:
        pid, port = lock
        if _pid_alive(pid) and _is_streamlit_healthy(port):
            webbrowser.open(_url_for_port(port), new=0)
            raise SystemExit(0)
        # Lock is stale or process is unhealthy.
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            time.sleep(0.5)
        _remove_lock()

    # If a healthy server already exists without lock file, reuse it.
    if _is_streamlit_healthy(DEFAULT_PORT):
        webbrowser.open(_url_for_port(DEFAULT_PORT), new=0)
        raise SystemExit(0)

    # Pick an available local port.
    chosen_port = DEFAULT_PORT
    if _is_port_open(chosen_port):
        for port in range(DEFAULT_PORT + 1, DEFAULT_PORT + 50):
            if not _is_port_open(port):
                chosen_port = port
                break

    with open(LOCKFILE, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()},{chosen_port}")

    def _cleanup() -> None:
        _remove_lock()

    atexit.register(_cleanup)
    return chosen_port

PORT = _claim_or_focus_existing()

def _open_browser_once() -> None:
    if _wait_for_port("127.0.0.1", PORT, timeout_s=45.0) and _is_streamlit_healthy(PORT):
        webbrowser.open(_url_for_port(PORT), new=0)

threading.Thread(target=_open_browser_once, daemon=True).start()

try:
    if not os.path.exists(APP):
        raise FileNotFoundError(f"Could not find bundled app.py at: {APP}")

    os.chdir(ROOT)
    bootstrap.run(
        APP,
        False,
        [],
        flag_options={
            "server.headless": True,
            "server.fileWatcherType": "none",
            "browser.gatherUsageStats": False,
            "server.address": "127.0.0.1",
            "server.port": PORT,
        },
    )
except Exception as exc:
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Launcher error: {repr(exc)}\n")
        f.write(f"ROOT={ROOT}\nAPP={APP}\n")
    raise
