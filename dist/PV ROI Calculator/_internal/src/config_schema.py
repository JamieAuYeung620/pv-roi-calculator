# src/config_schema.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional, Literal
import json
from datetime import datetime


TariffMode = Literal["compare", "compare_all", "A", "B", "C"]
AnalysisWindowMode = Literal["full_year", "custom"]


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
    force_download: bool = True  # if True, attempt fresh PVGIS fetch


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
    surface_tilt_deg: float = 30.0
    surface_azimuth_deg: float = 180.0
    inverter_ac_kw: Optional[float] = None  # None => equals system_kw in core script


@dataclass
class LoadConfig:
    """
    Household load settings (match roi_calculator_core.py CLI flags).
    """
    annual_load_kwh: float = 3200.0
    profile: str = "away_daytime"  # "home_daytime" or "away_daytime"
    seasonal_variance_pct: int = 30

    # Used for week plot (pipeline will generate a week plot from selected window)
    week_start: Optional[str] = None  # "YYYY-MM-DD" or None to auto-pick
    week_days: int = 7


@dataclass
class TariffConfig:
    """
    Tariff settings.
    We keep all tariff prices here; tariff_mode selection is stored at top-level.
    """
    # Tariff A (flat)
    tariffA_import: float = 0.28
    tariffA_export: float = 0.15

    # Tariff B (TOU import + flat export)
    tariffB_peak: float = 0.35
    tariffB_offpeak: float = 0.22
    tariffB_export: float = 0.15
    tariffC_export: float = 0.05

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
    lifetime_years: int = 15
    degradation: float = 0.005
    om_frac: float = 0.01
    salvage_value_gbp: float = 0.0


@dataclass
class AnalysisWindowConfig:
    """
    Controls date filtering for:
      - plots
      - exported timescale CSVs (hourly/daily/monthly)
    IMPORTANT:
      - The lifetime ROI finance step is still computed on the full dataset (baseline).
      - This window is mainly for "what you show/export" in the demo.
    """
    mode: AnalysisWindowMode = "full_year"

    # Only used when mode == "custom"
    start: str = "2021-06-01"  # YYYY-MM-DD
    end: str = "2021-06-30"    # YYYY-MM-DD (inclusive)


@dataclass
class OutputConfig:
    """
    Output toggles (time-scale exports).
    """
    export_hourly: bool = True
    export_daily: bool = False
    export_monthly: bool = True
    enable_variability: bool = False
    variability_year_start: int = 2010
    variability_year_end: int = 2020
    enable_verification_checks: bool = True
    enable_pvgis_crosscheck: bool = False


@dataclass
class PlotFlags:
    """
    Plot selection toggles.
    If a plot is False, it should NOT be generated inside the run folder.
    """
    monthly_pv_vs_load: bool = True
    week_timeseries: bool = True
    energy_split: bool = True
    cumulative_cashflow: bool = True
    annual_cashflow_bars: bool = True


@dataclass
class PVROIRunConfig:
    """
    One config object that drives the entire pipeline.
    """
    version: str = "2.0"
    meta: RunMeta = field(default_factory=RunMeta)

    # NEW: tariff mode selection (A/B/compare)
    tariff_mode: TariffMode = "compare"

    # NEW: analysis window selection
    analysis_window: AnalysisWindowConfig = field(default_factory=AnalysisWindowConfig)

    location: LocationConfig = field(default_factory=LocationConfig)
    pv: PVModelConfig = field(default_factory=PVModelConfig)
    load: LoadConfig = field(default_factory=LoadConfig)
    tariffs: TariffConfig = field(default_factory=TariffConfig)
    finance: FinanceConfig = field(default_factory=FinanceConfig)

    # NEW: explicit export toggles
    outputs: OutputConfig = field(default_factory=OutputConfig)

    # NEW: plot selection toggles
    plot_flags: PlotFlags = field(default_factory=PlotFlags)

    def to_dict(self) -> Dict[str, Any]:
        # Normalize through JSON for deterministic primitive-only serialization.
        return json.loads(json.dumps(asdict(self), sort_keys=True))

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
        pv_data = dict(data.get("pv", {}) or {})
        # Backwards compatibility for older config keys.
        if "surface_tilt_deg" not in pv_data and "surface_tilt" in pv_data:
            pv_data["surface_tilt_deg"] = pv_data["surface_tilt"]
        if "surface_azimuth_deg" not in pv_data and "surface_azimuth" in pv_data:
            pv_data["surface_azimuth_deg"] = pv_data["surface_azimuth"]
        pv = PVModelConfig(**cls._filtered_kwargs(PVModelConfig, pv_data))
        load = LoadConfig(**cls._filtered_kwargs(LoadConfig, data.get("load", {}) or {}))
        tariffs = TariffConfig(**cls._filtered_kwargs(TariffConfig, data.get("tariffs", {}) or {}))
        finance = FinanceConfig(**cls._filtered_kwargs(FinanceConfig, data.get("finance", {}) or {}))
        outputs = OutputConfig(**cls._filtered_kwargs(OutputConfig, data.get("outputs", {}) or {}))
        plot_flags = PlotFlags(**cls._filtered_kwargs(PlotFlags, data.get("plot_flags", {}) or {}))
        analysis_window = AnalysisWindowConfig(**cls._filtered_kwargs(AnalysisWindowConfig, data.get("analysis_window", {}) or {}))

        version = str(data.get("version", "2.0"))
        tariff_mode = str(data.get("tariff_mode", "compare"))

        # Backwards compatibility: if someone stored tariff selection inside "tariffs.mode"
        # we allow it as a fallback IF top-level tariff_mode is missing.
        # (Old configs won't have "tariffs.mode" with this schema, but this helps if you had it before.)
        if "tariff_mode" not in data:
            maybe_tariffs = data.get("tariffs", {}) or {}
            maybe_mode = maybe_tariffs.get("mode")
            if maybe_mode in {"compare", "A", "B"}:
                tariff_mode = maybe_mode

        return cls(
            version=version,
            meta=meta,
            tariff_mode=tariff_mode,  # type: ignore
            analysis_window=analysis_window,
            location=location,
            pv=pv,
            load=load,
            tariffs=tariffs,
            finance=finance,
            outputs=outputs,
            plot_flags=plot_flags,
        )


def _parse_date_yyyy_mm_dd(date_str: str) -> None:
    """
    Validate 'YYYY-MM-DD' format (raises ValueError if invalid).
    """
    datetime.strptime(date_str, "%Y-%m-%d")


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
    if not (2005 <= cfg.location.year <= 2023):
        errors.append("location.year must be between 2005 and 2023.")

    # PV / load
    if cfg.pv.system_kw <= 0:
        errors.append("pv.system_kw must be > 0.")
    if not (0 <= cfg.pv.surface_tilt_deg <= 90):
        errors.append("pv.surface_tilt_deg must be between 0 and 90.")
    if not (0 <= cfg.pv.surface_azimuth_deg <= 360):
        errors.append("pv.surface_azimuth_deg must be between 0 and 360.")
    if cfg.load.annual_load_kwh <= 0:
        errors.append("load.annual_load_kwh must be > 0.")
    if cfg.load.profile not in {"home_daytime", "away_daytime"}:
        errors.append("load.profile must be 'home_daytime' or 'away_daytime'.")
    if cfg.load.seasonal_variance_pct < 20 or cfg.load.seasonal_variance_pct > 40:
        errors.append("load.seasonal_variance_pct must be between 20 and 40.")
    if cfg.load.week_days < 1 or cfg.load.week_days > 31:
        errors.append("load.week_days must be between 1 and 31.")

    # Variability mode
    if cfg.outputs.enable_variability:
        if not (2005 <= cfg.outputs.variability_year_start <= 2023):
            errors.append("outputs.variability_year_start must be between 2005 and 2023.")
        if not (2005 <= cfg.outputs.variability_year_end <= 2023):
            errors.append("outputs.variability_year_end must be between 2005 and 2023.")
        if cfg.outputs.variability_year_end < cfg.outputs.variability_year_start:
            errors.append("outputs.variability_year_end must be >= outputs.variability_year_start.")

    # Tariff mode
    if cfg.tariff_mode not in {"compare", "compare_all", "A", "B", "C"}:
        errors.append("tariff_mode must be one of: 'compare', 'compare_all', 'A', 'B', 'C'.")

    # Tariffs
    for name, val in [
        ("tariffs.tariffA_import", cfg.tariffs.tariffA_import),
        ("tariffs.tariffA_export", cfg.tariffs.tariffA_export),
        ("tariffs.tariffB_peak", cfg.tariffs.tariffB_peak),
        ("tariffs.tariffB_offpeak", cfg.tariffs.tariffB_offpeak),
        ("tariffs.tariffB_export", cfg.tariffs.tariffB_export),
        ("tariffs.tariffC_export", cfg.tariffs.tariffC_export),
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

    # Analysis window
    if cfg.analysis_window.mode not in {"full_year", "custom"}:
        errors.append("analysis_window.mode must be 'full_year' or 'custom'.")

    if cfg.analysis_window.mode == "custom":
        try:
            _parse_date_yyyy_mm_dd(cfg.analysis_window.start)
        except Exception:
            errors.append("analysis_window.start must be in YYYY-MM-DD format.")
        try:
            _parse_date_yyyy_mm_dd(cfg.analysis_window.end)
        except Exception:
            errors.append("analysis_window.end must be in YYYY-MM-DD format.")

        # Only compare if both parsed OK
        try:
            start_dt = datetime.strptime(cfg.analysis_window.start, "%Y-%m-%d")
            end_dt = datetime.strptime(cfg.analysis_window.end, "%Y-%m-%d")
            if end_dt < start_dt:
                errors.append("analysis_window.end must be >= analysis_window.start.")
        except Exception:
            pass

    if errors:
        raise ValueError("Invalid config:\n- " + "\n- ".join(errors))


def save_config_json(cfg: PVROIRunConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


def load_config_json(path: Path) -> PVROIRunConfig:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return PVROIRunConfig.from_dict(data)


def make_default_config() -> PVROIRunConfig:
    """
    Convenience for quickly running the demo without writing JSON first.
    """
    return PVROIRunConfig()
