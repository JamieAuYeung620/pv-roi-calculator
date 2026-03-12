# src/run_history.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from run_manager import repo_root


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    run_dir: Path
    created_at_local: str
    location: str
    system_kw: float
    annual_load_kwh: float


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_dt(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def read_run_info(run_dir: Path) -> Optional[RunInfo]:
    run_dir = Path(run_dir)
    cfg_path = run_dir / "config.json"
    if not cfg_path.exists():
        return None

    try:
        cfg = _read_json(cfg_path)
        meta = cfg.get("meta") or {}
        loc = cfg.get("location") or {}
        pv = cfg.get("pv") or {}
        load = cfg.get("load") or {}

        run_id = str(meta.get("run_id") or run_dir.name)
        created = str(meta.get("created_at_local") or "")
        location = str(loc.get("name") or "unknown_location")
        system_kw = float(pv.get("system_kw") or 0.0)
        annual_load = float(load.get("annual_load_kwh") or 0.0)

        return RunInfo(
            run_id=run_id,
            run_dir=run_dir,
            created_at_local=created,
            location=location,
            system_kw=system_kw,
            annual_load_kwh=annual_load,
        )
    except Exception:
        return None


def list_recent_runs(limit: int = 10) -> List[RunInfo]:
    runs_dir = repo_root() / "runs"
    if not runs_dir.exists():
        return []

    infos: List[RunInfo] = []
    for d in runs_dir.iterdir():
        if not d.is_dir():
            continue
        if d.name == "archive_runs":
            continue
        info = read_run_info(d)
        if info:
            infos.append(info)

    # Sort newest-first using created_at_local if possible; fallback to folder name
    def sort_key(x: RunInfo):
        dt = _parse_dt(x.created_at_local)
        return dt or datetime.min

    infos.sort(key=sort_key, reverse=True)
    return infos[: int(limit)]


def format_run_label(info: RunInfo) -> str:
    # Example: "2026-02-16_1633 | warwick_campus | 4.0 kW | 3200 kWh"
    created = info.created_at_local.replace("T", " ") if info.created_at_local else info.run_id
    return f"{created} | {info.location} | {info.system_kw:.1f} kW | {info.annual_load_kwh:.0f} kWh"
