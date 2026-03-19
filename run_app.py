#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import textwrap
import venv


REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
APP_PATH = REPO_ROOT / "app.py"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
ESSENTIAL_FILES = [
    APP_PATH,
    REPO_ROOT / "src" / "pipeline_runner.py",
    REPO_ROOT / "src" / "load_model.py",
    REPO_ROOT / "data" / "load_archetypes_uk_v1.json",
]
REQUIRED_IMPORTS = [
    "streamlit",
    "pandas",
    "numpy",
    "matplotlib",
    "requests",
    "pvlib",
]


def info(message: str) -> None:
    print(f"[pv-roi] {message}")


def fail(message: str, exit_code: int = 1) -> int:
    print(f"[pv-roi] ERROR: {message}", file=sys.stderr)
    return exit_code


def venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def build_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    mpl_dir = REPO_ROOT / ".mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    env["MPLCONFIGDIR"] = str(mpl_dir)
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    return env


def ensure_runtime_dirs() -> None:
    (REPO_ROOT / "outputs").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "runs").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / ".mplconfig").mkdir(parents=True, exist_ok=True)
    data_dir = REPO_ROOT / "data"
    if data_dir.exists():
        (data_dir / "cache").mkdir(parents=True, exist_ok=True)


def create_virtualenv() -> None:
    info(f"Creating virtual environment at {VENV_DIR}")
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(str(VENV_DIR))


def ensure_virtualenv() -> Path:
    python_path = venv_python_path()
    if python_path.exists():
        return python_path

    try:
        create_virtualenv()
    except Exception as exc:  # pragma: no cover - defensive failure path
        raise RuntimeError(
            "Could not create .venv automatically. "
            "Please make sure Python includes the standard 'venv' module."
        ) from exc

    if not python_path.exists():
        raise RuntimeError(f"Virtual environment was created, but Python was not found at {python_path}")
    return python_path


def run_command(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=capture_output,
        check=check,
    )


def python_version(python_path: Path, env: dict[str, str]) -> str:
    result = run_command(
        [str(python_path), "-c", "import platform; print(platform.python_version())"],
        env=env,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def missing_required_files() -> list[Path]:
    return [path for path in ESSENTIAL_FILES if not path.exists()]


def dependencies_installed(python_path: Path, env: dict[str, str]) -> tuple[bool, str]:
    probe = (
        "missing = []\n"
        "for name in " + repr(REQUIRED_IMPORTS) + ":\n"
        "    try:\n"
        "        __import__(name)\n"
        "    except Exception:\n"
        "        missing.append(name)\n"
        "print(','.join(missing))\n"
    )
    result = run_command([str(python_path), "-c", probe], env=env, capture_output=True)
    missing = result.stdout.strip()
    return result.returncode == 0 and missing == "", missing


def install_dependencies(python_path: Path, env: dict[str, str]) -> None:
    if not REQUIREMENTS_PATH.exists():
        raise RuntimeError(f"requirements.txt was not found at {REQUIREMENTS_PATH}")

    info("Installing Python dependencies from requirements.txt")
    result = run_command(
        [str(python_path), "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Dependency installation failed. "
            "Please review the pip output above and try again."
        )


def pick_port(preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free local port starting at {preferred_port}")


def run_preflight(*, check_only: bool, skip_install: bool) -> tuple[int, Path | None, int | None]:
    ensure_runtime_dirs()

    missing_files = missing_required_files()
    if missing_files:
        message = "Essential repository files are missing:\n" + "\n".join(f"  - {path.relative_to(REPO_ROOT)}" for path in missing_files)
        message += "\nPlease re-download or re-clone the full repository."
        return fail(message), None, None

    try:
        python_path = ensure_virtualenv()
    except RuntimeError as exc:
        return fail(str(exc)), None, None

    env = build_runtime_env()
    version = python_version(python_path, env)
    info(f"Repository root: {REPO_ROOT}")
    info(f"Using virtual environment: {python_path}")
    info(f"Python version: {version}")

    deps_ok, missing_imports = dependencies_installed(python_path, env)
    if not deps_ok and check_only:
        return (
            fail(
                "Preflight check failed because required packages are missing from .venv.\n"
                "Run `python run_app.py` (or the OS launcher script) once to install them."
                + (f"\nMissing imports: {missing_imports}" if missing_imports else "")
            ),
            python_path,
            None,
        )

    if not deps_ok:
        if skip_install:
            return (
                fail(
                    "Required packages are missing and `--skip-install` was used."
                    + (f"\nMissing imports: {missing_imports}" if missing_imports else "")
                ),
                python_path,
                None,
            )
        try:
            install_dependencies(python_path, env)
        except RuntimeError as exc:
            return fail(str(exc)), python_path, None

        deps_ok, missing_imports = dependencies_installed(python_path, env)
        if not deps_ok:
            return (
                fail(
                    "Dependencies still look incomplete after installation."
                    + (f"\nMissing imports: {missing_imports}" if missing_imports else "")
                ),
                python_path,
                None,
            )

    info("Preflight check passed: files, virtual environment, and Python packages look ready.")
    return 0, python_path, None


def launch_streamlit(python_path: Path, port: int) -> int:
    env = build_runtime_env()
    url = f"http://127.0.0.1:{port}"
    info("Launching the Streamlit app.")
    info("A browser tab should open automatically.")
    info(f"If it does not, open this URL manually: {url}")

    cmd = [
        str(python_path),
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
    ]
    try:
        completed = run_command(cmd, env=env)
    except KeyboardInterrupt:
        info("Streamlit stopped.")
        return 130
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a local virtual environment if needed, verify setup, and launch the PV ROI Streamlit app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python run_app.py
              python run_app.py --check-only
              python run_app.py --port 8502
            """
        ),
    )
    parser.add_argument("--check-only", action="store_true", help="Run a quick preflight check and exit without launching Streamlit.")
    parser.add_argument("--skip-install", action="store_true", help="Do not install missing packages automatically.")
    parser.add_argument("--port", type=int, default=8501, help="Preferred local port for Streamlit (default: 8501).")
    return parser.parse_args()


def main() -> int:
    if sys.version_info < (3, 9):
        return fail("Python 3.9 or newer is required to run this repository.")

    args = parse_args()

    rc, python_path, _ = run_preflight(check_only=args.check_only, skip_install=args.skip_install)
    if rc != 0:
        return rc
    if python_path is None:
        return fail("No Python runtime was available after preflight.")

    if args.check_only:
        return 0

    try:
        chosen_port = pick_port(args.port)
    except RuntimeError as exc:
        return fail(str(exc))

    if chosen_port != args.port:
        info(f"Port {args.port} is busy, so the app will use port {chosen_port} instead.")

    return launch_streamlit(python_path, chosen_port)


if __name__ == "__main__":
    raise SystemExit(main())
