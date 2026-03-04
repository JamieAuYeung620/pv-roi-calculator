# src/run_manager.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple


def repo_root() -> Path:
    """
    repo_root/
      src/run_manager.py  -> parent.parent is repo root
    """
    return Path(__file__).resolve().parent.parent


def slugify(text: str) -> str:
    """
    Make safe folder/file slugs.
    Example: "Warwick Campus" -> "warwick_campus"
    """
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown_location"


def float_to_slug(x: float) -> str:
    """
    4.0 -> "4"
    4.5 -> "4p5"
    -1.5615 -> "m1p5615"
    """
    if x is None:
        return "na"
    sign = "m" if x < 0 else ""
    s = f"{abs(float(x)):.6f}".rstrip("0").rstrip(".")
    s = s.replace(".", "p")
    return f"{sign}{s}"


def number_to_short_slug(x: float) -> str:
    """
    Shorter for display in run_id:
    4.0 -> "4"
    4.25 -> "4p25"
    """
    if x is None:
        return "na"
    s = f"{float(x):.4f}".rstrip("0").rstrip(".")
    return s.replace(".", "p")


def build_run_id(config: Dict[str, Any]) -> str:
    """
    Build a readable run_id, e.g.
    2026-02-15_1530_warwick_campus_system4kw_load3200
    """
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M")

    location_name = (config.get("location", {}) or {}).get("name", "unknown_location")
    location_slug = slugify(str(location_name))

    system_kw = float((config.get("pv", {}) or {}).get("system_kw", 0.0) or 0.0)
    annual_load = float((config.get("load", {}) or {}).get("annual_load_kwh", 0.0) or 0.0)

    system_part = f"system{number_to_short_slug(system_kw)}kw"
    load_part = f"load{int(round(annual_load))}"

    return f"{stamp}_{location_slug}_{system_part}_{load_part}"


def create_run_folder(run_id: str, base_dir: Optional[Path] = None) -> Path:
    """
    Creates:
    runs/<run_id>/
      config.json
      logs.txt
      summary.md
      data/
      outputs/
        plots/
      report/
    """
    root = repo_root()
    base = base_dir or (root / "runs")
    base.mkdir(parents=True, exist_ok=True)

    run_dir = base / run_id
    if run_dir.exists():
        # Avoid overwriting: add suffix _v2, _v3, ...
        i = 2
        while (base / f"{run_id}_v{i}").exists():
            i += 1
        run_dir = base / f"{run_id}_v{i}"

    # Make required folders
    (run_dir / "data").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "plots").mkdir(parents=True, exist_ok=True)
    (run_dir / "report").mkdir(parents=True, exist_ok=True)

    return run_dir


def save_config_dict(config: Dict[str, Any], run_dir: Path) -> Path:
    """
    Save config.json inside the run folder.
    """
    path = run_dir / "config.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def setup_logger(run_dir: Path, logger_name: str) -> logging.Logger:
    """
    Create a logger that writes to runs/<run_id>/logs.txt and prints to console.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Clear old handlers if re-running in the same interpreter session
    if logger.handlers:
        logger.handlers.clear()

    log_path = run_dir / "logs.txt"

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging started: %s", log_path)
    return logger


def init_run(config: Dict[str, Any]) -> Tuple[Path, logging.Logger, Dict[str, Any]]:
    """
    One-call setup:
    - create unique run folder
    - fill config.meta.run_id + created_at_local
    - save config.json
    - setup logs.txt
    """
    run_id = build_run_id(config)
    run_dir = create_run_folder(run_id=run_id)

    created_at_local = datetime.now().isoformat(timespec="seconds")

    # Ensure meta exists
    meta = config.get("meta") or {}
    meta["run_id"] = run_dir.name
    meta["created_at_local"] = created_at_local
    config["meta"] = meta

    save_config_dict(config, run_dir)

    logger = setup_logger(run_dir, logger_name=f"pv_roi.{run_dir.name}")
    logger.info("Run folder created: %s", run_dir)

    return run_dir, logger, config
