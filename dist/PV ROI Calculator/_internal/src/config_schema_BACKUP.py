# src/config_schema.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional, Literal
import json


TariffMode = Literal["compare", "A", "B"]
TimeScale = Literal["hourly", "daily", "monthly"]


@dataclass
class RunMeta:
    """
    Metadata filled at runtime (run_id, created timestamp).
    """
    run_id: Optional[str] = None
    created_at_local: Optional[str] = None
    notes: str = ""


@dataclass
class LocationConfig:
    """
    PVGIS location + year.
    name: user-friendly label (will be slugified for filenames)
    """
    name: str = "warwick_campus"
    lat: float = 52.3840
    lon: float = -1.5615
    year: int = 2021
    force_download: bool = False  # if True, attempt fresh PVGIS fetch


@dataclass
class PVModelConfig:
    """
    PV model parameters (match roi_calculator_core.py CLI flags).
    """
    system_kw: float = 4.0
    temp_coeff: float = -0.004
    loss_frac: float = 0.14
    inverter_eff: float = 0.96
    noct: float = 45.0
    inverter_ac_kw: Optional[float] = None  # None => equals system_kw in core script


@dataclass
class LoadConfig:
    """
    Household load settings (match roi_calculator_core.py CLI flags).
    """
    annual_load_kwh: float = 3200.0
    profile: str = "away_daytime"  # "home_daytime" or "away_daytime"
    week_start: Optional[str] = None  # e.g. "2021-06-01" (used for week plot)
    week_days: int = 7


@dataclass
class TariffConfig:
    """
    Tariff settings (core uses Tariff A; finance compares A vs B).
    mode is kept for future GUI toggles; pipeline backbone runs both steps for demo stability.
    """
    mode: TariffMode = "compare"

    # Tariff A (flat)
    tariffA_import: float = 0.28
    tariffA_export: float = 0.15

    # Tariff B (TOU import + flat export)
    tariffB_peak: float = 0.35
    tariffB_offpeak: float = 0.22
    tariffB_export: float = 0.15

    # Peak window (UTC hour)
    peak_start: int = 16
    peak_end: int = 19


@dataclass
class FinanceConfig:
    """
    Lifetime finance model settings (match roi_calculator_finance.py CLI flags).
    """
    capex: float = 6000.0
    discount_rate: float = 0.05
    lifetime_years: int = 25
    degradation: float = 0.005
    om_frac: float = 0.01


@dataclass
class OutputConfig:
    """
    Output toggles for later GUI (time_scale/date_range not wired yet in backbone).
    """
    time_scale: TimeScale = "hourly"
    date_range: str = "full_year"
    generate_plots: bool = True


@dataclass
class PVROIRunConfig:
    """
    One config object that drives the entire pipeline.
    """
    version: str = "1.0"
    meta: RunMeta = field(default_factory=RunMeta)

    location: LocationConfig = field(default_factory=LocationConfig)
    pv: PVModelConfig = field(default_factory=PVModelConfig)
    load: LoadConfig = field(default_factory=LoadConfig)
    tariffs: TariffConfig = field(default_factory=TariffConfig)
    finance: FinanceConfig = field(default_factory=FinanceConfig)
    outputs: OutputConfig = field(default_factory=OutputConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _filtered_kwargs(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ignore unknown keys so configs remain forwards/backwards compatible.
        """
        allowed = {f.name for f in fields(cls)}
        return {k: v for k, v in data.items() if k in allowed}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PVROIRunConfig":
        meta = RunMeta(**cls._filtered_kwargs(RunMeta, data.get("meta", {}) or {}))
        location = LocationConfig(**cls._filtered_kwargs(LocationConfig, data.get("location", {}) or {}))
        pv = PVModelConfig(**cls._filtered_kwargs(PVModelConfig, data.get("pv", {}) or {}))
        load = LoadConfig(**cls._filtered_kwargs(LoadConfig, data.get("load", {}) or {}))
        tariffs = TariffConfig(**cls._filtered_kwargs(TariffConfig, data.get("tariffs", {}) or {}))
        finance = FinanceConfig(**cls._filtered_kwargs(FinanceConfig, data.get("finance", {}) or {}))
        outputs = OutputConfig(**cls._filtered_kwargs(OutputConfig, data.get("outputs", {}) or {}))

        version = str(data.get("version", "1.0"))

        return cls(
            version=version,
            meta=meta,
            location=location,
            pv=pv,
            load=load,
            tariffs=tariffs,
            finance=finance,
            outputs=outputs,
        )


def validate_config(cfg: PVROIRunConfig) -> None:
    """
    Beginner-friendly validation. Raises ValueError with a readable message.
    """
    errors = []

    # Location
    if not (-90 <= cfg.location.lat <= 90):
        errors.append("location.lat must be between -90 and 90.")
    if not (-180 <= cfg.location.lon <= 180):
        errors.append("location.lon must be between -180 and 180.")
    if not (1990 <= cfg.location.year <= 2100):
        errors.append("location.year must be between 1990 and 2100.")

    # PV / load
    if cfg.pv.system_kw <= 0:
        errors.append("pv.system_kw must be > 0.")
    if cfg.load.annual_load_kwh <= 0:
        errors.append("load.annual_load_kwh must be > 0.")
    if cfg.load.profile not in {"home_daytime", "away_daytime"}:
        errors.append("load.profile must be 'home_daytime' or 'away_daytime'.")

    # Tariffs
    for name, val in [
        ("tariffs.tariffA_import", cfg.tariffs.tariffA_import),
        ("tariffs.tariffA_export", cfg.tariffs.tariffA_export),
        ("tariffs.tariffB_peak", cfg.tariffs.tariffB_peak),
        ("tariffs.tariffB_offpeak", cfg.tariffs.tariffB_offpeak),
        ("tariffs.tariffB_export", cfg.tariffs.tariffB_export),
    ]:
        if val < 0:
            errors.append(f"{name} must be >= 0.")

    if not (0 <= cfg.tariffs.peak_start <= 23):
        errors.append("tariffs.peak_start must be 0..23.")
    if not (1 <= cfg.tariffs.peak_end <= 24):
        errors.append("tariffs.peak_end must be 1..24.")
    if cfg.tariffs.peak_start == cfg.tariffs.peak_end:
        errors.append("tariffs.peak_start and tariffs.peak_end cannot be the same (empty window).")

    # Finance
    if cfg.finance.capex <= 0:
        errors.append("finance.capex must be > 0.")
    if cfg.finance.lifetime_years < 1:
        errors.append("finance.lifetime_years must be >= 1.")
    if cfg.finance.discount_rate < 0:
        errors.append("finance.discount_rate must be >= 0.")
    if not (0.0 <= cfg.finance.degradation <= 0.03):
        errors.append("finance.degradation must be between 0 and 0.03 (e.g., 0.005).")
    if not (0.0 <= cfg.finance.om_frac <= 0.05):
        errors.append("finance.om_frac must be between 0 and 0.05 (e.g., 0.01).")

    if errors:
        raise ValueError("Invalid config:\n- " + "\n- ".join(errors))


def save_config_json(cfg: PVROIRunConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, sort_keys=True)


def load_config_json(path: Path) -> PVROIRunConfig:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return PVROIRunConfig.from_dict(data)


def make_default_config() -> PVROIRunConfig:
    """
    Convenience for quickly running the demo without writing JSON first.
    """
    return PVROIRunConfig()
