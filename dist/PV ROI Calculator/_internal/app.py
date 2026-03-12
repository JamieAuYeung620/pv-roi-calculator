from __future__ import annotations

import json
import sys
from pathlib import Path
from math import floor, log10

import streamlit as st
import pandas as pd

# --- Make src importable ---
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_schema import PVROIRunConfig, validate_config  # noqa: E402
from pipeline_runner import (  # noqa: E402
    run_pipeline,
    plot_monthly_pv_vs_load,
    plot_monthly_bill_benefit,
    plot_energy_split,
    plot_week_timeseries,
)
from run_manager import slugify  # noqa: E402
from run_history import list_recent_runs, format_run_label  # noqa: E402
from report_generator import generate_run_report  # noqa: E402


# ---------------------------
# Helpers
# ---------------------------
def load_presets() -> dict:
    p = ROOT / "presets.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def init_state(defaults: dict) -> None:
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def ensure_sensible_input_defaults(defaults: dict) -> None:
    """
    Guard against zeroed UI state values in new sessions.
    Only restores keys where default is non-zero/non-empty.
    """
    guarded_keys = [
        "lat", "lon", "year", "year_pending",
        "system_kw", "annual_load_kwh",
        "tariffA_import", "tariffA_export", "tariffB_peak", "tariffB_offpeak", "tariffB_export", "tariffC_export",
        "capex", "discount_rate_pct", "lifetime_years", "degradation", "om_frac_pct",
        "orientation", "profile", "location_name", "location_preset", "tariff_mode",
    ]
    for k in guarded_keys:
        if k not in defaults:
            continue
        dv = defaults[k]
        if isinstance(dv, str):
            if st.session_state.get(k, "") == "":
                st.session_state[k] = dv
            continue
        if isinstance(dv, (int, float)):
            if float(dv) != 0.0:
                try:
                    cur = float(st.session_state.get(k, 0.0))
                except Exception:
                    cur = 0.0
                if cur == 0.0:
                    st.session_state[k] = dv


def reset_all_input_defaults(defaults: dict) -> None:
    """
    Restore all calculator input defaults from the defaults dict.
    Keeps non-input UI routing keys intact.
    """
    skip_keys = {"ui_screen", "status_msg", "last_run_dir", "selected_run_dir", "has_run_once"}
    for k, v in defaults.items():
        if k in skip_keys:
            continue
        st.session_state[k] = v


def apply_preset(preset: dict) -> None:
    for k, v in preset.items():
        st.session_state[k] = v
    if "loss_frac_pct" in preset:
        st.session_state["loss_frac"] = float(st.session_state["loss_frac_pct"]) / 100.0
    elif "loss_frac" in preset:
        st.session_state["loss_frac_pct"] = int(round(float(st.session_state["loss_frac"]) * 100))
    st.session_state["status_msg"] = f"Preset loaded: {st.session_state.get('preset_name','(preset)')}"
    st.rerun()


LOCATION_PRESETS = {
    "Warwick (University of Warwick)": {"name": "warwick_campus", "lat": 52.3840, "lon": -1.5615},
    "London": {"name": "london", "lat": 51.5074, "lon": -0.1278},
    "Manchester": {"name": "manchester", "lat": 53.4808, "lon": -2.2426},
    "Birmingham": {"name": "birmingham", "lat": 52.4862, "lon": -1.8904},
    "Leeds": {"name": "leeds", "lat": 53.8008, "lon": -1.5491},
    "Glasgow": {"name": "glasgow", "lat": 55.8642, "lon": -4.2518},
    "Edinburgh": {"name": "edinburgh", "lat": 55.9533, "lon": -3.1883},
    "Cardiff": {"name": "cardiff", "lat": 51.4816, "lon": -3.1791},
    "Bristol": {"name": "bristol", "lat": 51.4545, "lon": -2.5879},
    "Belfast": {"name": "belfast", "lat": 54.5973, "lon": -5.9301},
}


ORIENTATION_OPTIONS = {
    "South (best in UK)": 180.0,
    "South-West": 225.0,
    "South-East": 135.0,
}

TARIFF_MODE_LABELS = {
    "compare": "Compare (A vs B)",
    "compare_all": "Compare all (A vs B vs C)",
    "A": "Tariff A only (flat import + export payment)",
    "B": "Tariff B only (peak/off‑peak import + export payment)",
    "C": "Tariff C only (minimum export payment — worst‑case)",
}


def apply_location_preset() -> None:
    preset = LOCATION_PRESETS[st.session_state["location_preset"]]
    st.session_state["location_name"] = preset["name"]
    if not st.session_state.get("use_custom_coords", False):
        st.session_state["lat"] = float(preset["lat"])
        st.session_state["lon"] = float(preset["lon"])


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    try:
        if path.exists():
            df = pd.read_csv(path)
            return df
    except Exception:
        return None
    return None


def _fmt_sig(x: float, sf: int = 3) -> str:
    if x == 0:
        return "0"
    abs_x = abs(x)
    decimals = max(0, sf - 1 - int(floor(log10(abs_x))))
    rounded = round(x, decimals)
    if decimals == 0:
        return f"{rounded:,.0f}"
    return f"{rounded:,.{decimals}f}".rstrip("0").rstrip(".")


def _fmt_gbp(x) -> str:
    try:
        v = float(x)
        if pd.isna(v):
            return "—"
        return f"£{_fmt_sig(v)}"
    except Exception:
        return "—"


def _fmt_kwh(x) -> str:
    try:
        v = float(x)
        if pd.isna(v):
            return "—"
        return _fmt_sig(v)
    except Exception:
        return "—"


def _fmt_years(x) -> str:
    try:
        v = float(x)
        if pd.isna(v):
            return "Not reached"
        return f"{_fmt_sig(v)} years"
    except Exception:
        return "—"


def _round_sig_value(x, sf: int = 3):
    try:
        v = float(x)
        if pd.isna(v):
            return x
        if v == 0.0:
            return 0.0
        decimals = max(0, sf - 1 - int(floor(log10(abs(v)))))
        return round(v, decimals)
    except Exception:
        return x


def _display_df(df: pd.DataFrame, sf: int = 3) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = out.select_dtypes(include=["number"]).columns
    for col in numeric_cols:
        out[col] = out[col].map(lambda v: _round_sig_value(v, sf=sf))
    return out


def required_label(text: str) -> None:
    st.markdown(f"{text} <span style='color:#d00'>*</span>", unsafe_allow_html=True)


def effective_azimuth_from_state() -> float:
    azimuth = ORIENTATION_OPTIONS[st.session_state["orientation"]]
    if st.session_state.get("southern_hemisphere", False):
        # Mirror north/south-facing convention for southern hemisphere users.
        azimuth = (azimuth + 180.0) % 360.0
    return azimuth


def build_cfg_from_state() -> PVROIRunConfig:
    # Convert inverter_ac_kw UI value: 0.0 -> None
    inverter_ac_kw = None if float(st.session_state["inverter_ac_kw"]) == 0.0 else float(st.session_state["inverter_ac_kw"])

    cfg_dict = {
        "version": "2.0",
        "meta": {"notes": st.session_state.get("run_notes", "")},
        "tariff_mode": st.session_state["tariff_mode"],
        "analysis_window": {
            "mode": "full_year",
            "start": f"{int(st.session_state['year'])}-01-01",
            "end": f"{int(st.session_state['year'])}-12-31",
        },
        "location": {
            "name": slugify(st.session_state["location_name"]),
            "lat": float(st.session_state["lat"]),
            "lon": float(st.session_state["lon"]),
            "year": int(st.session_state["year"]),
            "force_download": bool(st.session_state["force_download"]),
        },
        "pv": {
            "system_kw": float(st.session_state["system_kw"]),
            "temp_coeff": float(st.session_state["temp_coeff"]),
            "loss_frac": float(st.session_state["loss_frac"]),
            "inverter_eff": 1.0,
            "noct": float(st.session_state["noct"]),
            "surface_tilt_deg": float(st.session_state["surface_tilt"]),
            "surface_azimuth_deg": float(effective_azimuth_from_state()),
            "inverter_ac_kw": inverter_ac_kw,
        },
        "load": {
            "annual_load_kwh": float(st.session_state["annual_load_kwh"]),
            "profile": st.session_state["profile"],
            "seasonal_variance_pct": int(st.session_state["seasonal_variance_pct"]),
            "week_start": None,
            "week_days": 7,
        },
        "tariffs": {
            "tariffA_import": float(st.session_state["tariffA_import"]),
            "tariffA_export": float(st.session_state["tariffA_export"]),
            "tariffB_peak": float(st.session_state["tariffB_peak"]),
            "tariffB_offpeak": float(st.session_state["tariffB_offpeak"]),
            "tariffB_export": float(st.session_state["tariffB_export"]),
            "tariffC_export": float(st.session_state["tariffC_export"]),
            "peak_start": int(st.session_state["peak_start"]),
            "peak_end": int(st.session_state["peak_end"]),
        },
        "finance": {
            "capex": float(st.session_state["capex"]),
            "discount_rate": float(st.session_state["discount_rate"]),
            "lifetime_years": int(st.session_state["lifetime_years"]),
            "degradation": float(st.session_state["degradation"]),
            "om_frac": float(st.session_state["om_frac"]),
            "salvage_value_gbp": float(st.session_state["salvage_value_gbp"]),
        },
        "outputs": {
            "export_hourly": bool(st.session_state["export_hourly"]),
            "export_daily": bool(st.session_state["export_daily"]),
            "export_monthly": bool(st.session_state["export_monthly"]),
            "enable_variability": bool(st.session_state["enable_variability"]),
            "variability_year_start": int(st.session_state["variability_year_start"]),
            "variability_year_end": int(st.session_state["variability_year_end"]),
            "enable_verification_checks": bool(st.session_state["enable_verification_checks"]),
            "enable_pvgis_crosscheck": bool(st.session_state["enable_pvgis_crosscheck"]),
        },
        "plot_flags": {
            "monthly_pv_vs_load": bool(st.session_state.get("chart_show_monthly_pv", st.session_state.get("plot_monthly", True))),
            "week_timeseries": bool(st.session_state.get("chart_show_week", st.session_state.get("plot_week", True))),
            "energy_split": bool(st.session_state.get("chart_show_split", st.session_state.get("plot_split", False))),
            "cumulative_cashflow": bool(st.session_state.get("chart_show_cumulative", st.session_state.get("plot_cum", True))),
            "annual_cashflow_bars": bool(st.session_state.get("chart_show_annual_bars", st.session_state.get("plot_bars", False))),
        },
    }
    return PVROIRunConfig.from_dict(cfg_dict)


def validate_ui_inputs() -> list[str]:
    errs = []

    lat = float(st.session_state["lat"])
    lon = float(st.session_state["lon"])
    if not (-90.0 <= lat <= 90.0):
        errs.append("Latitude must be between -90 and 90.")
    if not (-180.0 <= lon <= 180.0):
        errs.append("Longitude must be between -180 and 180.")
    if not (2005 <= int(st.session_state["year"]) <= 2023):
        errs.append("Year must be between 2005 and 2023 (PVGIS 5.3 data range).")
    if bool(st.session_state.get("enable_variability", False)):
        vy_start = int(st.session_state["variability_year_start"])
        vy_end = int(st.session_state["variability_year_end"])
        if not (2005 <= vy_start <= 2023):
            errs.append("Start year must be between 2005 and 2023.")
        if not (2005 <= vy_end <= 2023):
            errs.append("End year must be between 2005 and 2023.")
        if vy_end < vy_start:
            errs.append("End year must be greater than or equal to start year.")

    if float(st.session_state["system_kw"]) <= 0:
        errs.append("PV system size (kWp) must be > 0.")
    if not (0.0 <= float(st.session_state["surface_tilt"]) <= 90.0):
        errs.append("Panel tilt (°) must be between 0 and 90.")
    azimuth_deg = float(effective_azimuth_from_state())
    if not (0.0 <= azimuth_deg <= 360.0):
        errs.append("Panel azimuth (°) must be between 0 and 360.")
    if float(st.session_state["annual_load_kwh"]) <= 0:
        errs.append("Annual load must be > 0 kWh/year.")
    if not (20 <= int(st.session_state["seasonal_variance_pct"]) <= 40):
        errs.append("Seasonal demand swing must be between 20 and 40%.")

    # Peak window sanity (allow wrap-around, but warn if equal)
    ps = int(st.session_state["peak_start"])
    pe = int(st.session_state["peak_end"])
    if ps == pe:
        errs.append("Peak start equals peak end — this means ALL hours are treated as peak. Change it if unintended.")

    return errs


# ---------------------------
# Page config
# ---------------------------
st.set_page_config(page_title="Solar ROI Calculator", layout="wide")
st.title("Solar ROI Calculator")
st.caption("Estimate your solar savings and payback. Data source: PVGIS (European Commission JRC).")

# ---------------------------
# Defaults (session state)
# ---------------------------
defaults = {
    "ui_screen": "intro",
    "location_preset": "Warwick (University of Warwick)",
    "use_custom_coords": False,
    "location_name": "warwick_campus",
    "lat": 52.3840,
    "lon": -1.5615,
    "year": 2020,
    "year_pending": 2020,
    "force_download": True,

    "system_kw": 4.0,
    "orientation": "South (best in UK)",
    "southern_hemisphere": False,
    "loss_frac_pct": 14,
    "loss_frac": 0.14,
    "surface_tilt": 0.0,
    "noct": 40.0,
    "temp_coeff": -0.004,
    "inverter_ac_kw": 0.0,

    "annual_load_kwh": 3200.0,
    "profile": "away_daytime",
    "seasonal_variance_pct": 30,
    "week_days": 7,
    "chart_monthly_month_range": (1, 12),
    "chart_bill_month_range": (1, 12),
    "chart_week_start_day": 152,
    "chart_week_days": 7,
    "chart_split_month_range": (1, 12),
    "chart_show_monthly_pv": True,
    "chart_show_monthly_bill": True,
    "chart_show_week": True,
    "chart_show_split": True,
    "chart_show_cumulative": True,
    "chart_show_annual_bars": True,

    "tariff_mode": "compare",
    "tariffA_import": 0.28,
    "tariffA_export": 0.15,
    "tariffB_peak": 0.35,
    "tariffB_offpeak": 0.22,
    "tariffB_export": 0.15,
    "tariffC_export": 0.05,
    "peak_start": 16,
    "peak_end": 19,

    "capex": 6000.0,
    "discount_rate": 0.05,
    "discount_rate_pct": 5.0,
    "lifetime_years": 15,
    "degradation": 0.005,
    "om_frac": 0.01,
    "om_frac_pct": 1.0,
    "salvage_value_gbp": 0.0,

    "export_hourly": False,
    "export_daily": False,
    "export_monthly": True,
    "enable_variability": False,
    "variability_year_start": 2022,
    "variability_year_end": 2023,
    "enable_verification_checks": True,
    "enable_pvgis_crosscheck": False,

    "plot_monthly": True,
    "plot_week": True,
    "plot_split": False,
    "plot_cum": True,
    "plot_bars": False,

    "run_notes": "",
    "debug_mode": False,

    "last_run_dir": "",
    "selected_run_dir": "",
    "status_msg": "",
    "has_run_once": False,
    "compact_sidebar_sections": True,
}
init_state(defaults)
if "loss_frac_pct" not in st.session_state:
    st.session_state["loss_frac_pct"] = int(round(float(st.session_state["loss_frac"]) * 100))
st.session_state["loss_frac"] = float(st.session_state["loss_frac_pct"]) / 100.0
if "discount_rate_pct" not in st.session_state and "discount_rate" in st.session_state:
    st.session_state["discount_rate_pct"] = float(st.session_state["discount_rate"]) * 100.0
if "om_frac_pct" not in st.session_state and "om_frac" in st.session_state:
    st.session_state["om_frac_pct"] = float(st.session_state["om_frac"]) * 100.0
st.session_state["discount_rate"] = float(st.session_state["discount_rate_pct"]) / 100.0
st.session_state["om_frac"] = float(st.session_state["om_frac_pct"]) / 100.0
st.session_state["force_download"] = True
if "year_pending" not in st.session_state:
    st.session_state["year_pending"] = int(st.session_state["year"])

if st.session_state.get("ui_screen") not in {"intro", "calculator"}:
    st.session_state["ui_screen"] = "intro"

if st.session_state.get("ui_screen") == "intro":
    st.subheader("Estimate your solar savings and payback (UK-focused).")

    c_intro_left, c_intro_right = st.columns([1.25, 1.0], gap="large")
    with c_intro_left:
        st.markdown("### How it works")
        st.markdown(
            "\n".join(
                [
                    "1. **Enter your home + electricity use**",
                    "- Pick location and year, then add annual household electricity use (kWh/year).",
                    "2. **Enter your solar system**",
                    "- Add PV size (kWp), roof orientation/tilt, and system assumptions.",
                    "3. **Choose tariffs and costs**",
                    "- Add import/export rates and upfront cost, then view savings, payback, and confidence outputs.",
                ]
            )
        )
        st.markdown(
            """
<div style="border:1px solid #d9dee5;border-radius:10px;padding:12px 14px;margin-top:8px;">
  <strong>What you'll need</strong>
  <ul style="margin:8px 0 0 18px;">
    <li>Approx annual electricity use (from your bill)</li>
    <li>Rough system size (kWp) or installer quote</li>
    <li>Your import/export tariff rates (if known)</li>
  </ul>
</div>
            """,
            unsafe_allow_html=True,
        )
    with c_intro_right:
        st.markdown(
            """
<div style="border:1px solid #d9dee5;border-radius:10px;padding:12px 14px;">
  <strong>What you'll get</strong>
  <ul style="margin:8px 0 0 18px;">
    <li>Estimated annual savings</li>
    <li>Estimated payback time</li>
    <li>A confidence view showing how results change across sunnier vs cloudier years (historical weather)</li>
  </ul>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "This is an estimate tool; results depend on weather, household usage patterns, and tariffs. "
            "It does not use your smart meter data."
        )
        if st.checkbox("Don't show this again (this session)", key="skip_intro_session"):
            reset_all_input_defaults(defaults)
            st.session_state["ui_screen"] = "calculator"
            st.rerun()
        if st.button("Start calculator", type="primary", use_container_width=True):
            reset_all_input_defaults(defaults)
            st.session_state["ui_screen"] = "calculator"
            st.rerun()

    st.stop()

# ---------------------------
# Sidebar: presets + run history + inputs
# ---------------------------
presets = load_presets()
run_clicked = False
controls_in_sidebar = bool(st.session_state.get("has_run_once", False))
controls_area = st.sidebar if controls_in_sidebar else st.container()
if not controls_in_sidebar:
    st.session_state["year_pending"] = int(st.session_state["year"])

with st.sidebar:
    if st.button("ℹ️ Guide / How to use", use_container_width=True):
        st.session_state["ui_screen"] = "intro"
        st.rerun()
    st.checkbox(
        "Use compact sidebar sections (recommended)",
        key="compact_sidebar_sections",
        help="Collapses inputs into a few sections to reduce scrolling after you run a calculation.",
    )


def render_location_selector_block() -> None:
    st.selectbox(
        "Location preset",
        options=list(LOCATION_PRESETS.keys()),
        key="location_preset",
        on_change=apply_location_preset,
    )
    st.checkbox("Use custom coordinates (advanced)", key="use_custom_coords", on_change=apply_location_preset)
    if st.session_state["use_custom_coords"]:
        required_label("Latitude")
        st.number_input("Latitude", min_value=-90.0, max_value=90.0, step=0.0001, format="%.6f", key="lat", label_visibility="collapsed")
        required_label("Longitude")
        st.number_input("Longitude", min_value=-180.0, max_value=180.0, step=0.0001, format="%.6f", key="lon", label_visibility="collapsed")
    else:
        p = LOCATION_PRESETS[st.session_state["location_preset"]]
        st.caption(f"Preset coordinates: lat {p['lat']:.4f}, lon {p['lon']:.4f}")


def render_chart_settings_block(show_heading: bool = True) -> None:
    if show_heading:
        st.markdown("### Chart Settings")
        st.caption("Use these controls to choose which charts are shown and what date range they display.")
    with st.expander("Open Chart Settings (display controls)", expanded=False):
        st.caption("Adjust how much data is shown in charts (calculations stay unchanged).")
        st.checkbox("Show: Monthly PV vs Load", key="chart_show_monthly_pv")
        st.slider("Monthly PV vs Load (month range)", min_value=1, max_value=12, value=st.session_state["chart_monthly_month_range"], step=1, key="chart_monthly_month_range")
        st.checkbox("Show: Monthly bill benefit", key="chart_show_monthly_bill")
        st.slider("Monthly bill benefit (month range)", min_value=1, max_value=12, value=st.session_state["chart_bill_month_range"], step=1, key="chart_bill_month_range")
        st.checkbox("Show: Week timeseries", key="chart_show_week")
        st.slider("Week timeseries (start day-of-year)", min_value=1, max_value=366, step=1, key="chart_week_start_day")
        st.slider("Week timeseries (duration in days)", min_value=1, max_value=31, step=1, key="chart_week_days")
        st.checkbox("Show: Energy split", key="chart_show_split")
        st.slider("Energy split (month range)", min_value=1, max_value=12, value=st.session_state["chart_split_month_range"], step=1, key="chart_split_month_range")
        st.checkbox("Show: Cumulative cashflow", key="chart_show_cumulative")
        st.checkbox("Show: Annual cashflow bars", key="chart_show_annual_bars")


# === ORIGINAL SIDEBAR LAYOUT (BEGIN) ===
def render_sidebar_inputs_original() -> None:
    st.subheader("Inputs")
    st.caption("* Required fields are marked with a red star.")
    render_location_selector_block()

    required_label("Location name (for filenames)")
    st.text_input("Location name (for filenames)", key="location_name", label_visibility="collapsed")
    st.number_input("Year", min_value=2005, max_value=2023, step=1, key="year_pending")
    st.caption("Available range: 2005–2023 (PVGIS 5.3 model).")

    st.divider()
    required_label("PV system size (kWp)")
    st.number_input("PV system size (kWp)", min_value=0.1, max_value=50.0, step=0.1, key="system_kw", label_visibility="collapsed")
    st.caption("kWp = panel peak rating (what installers quote).")
    st.selectbox("Roof orientation", options=list(ORIENTATION_OPTIONS.keys()), key="orientation")
    st.checkbox("I live in the southern hemisphere (advanced)", key="southern_hemisphere")
    st.caption(f"Effective azimuth used: {effective_azimuth_from_state():.0f}°")

    with st.expander("Advanced PV parameters", expanded=False):
        st.slider("System losses (%)", min_value=8, max_value=20, step=1, key="loss_frac_pct")
        st.session_state["loss_frac"] = float(st.session_state["loss_frac_pct"]) / 100.0
        st.number_input("Panel tilt (°)", min_value=0.0, max_value=90.0, step=1.0, key="surface_tilt")
        st.number_input("Cell temperature assumption (NOCT, °C)", min_value=20.0, max_value=70.0, value=40.0, step=1.0, key="noct")
        st.caption("NOCT = Nominal Operating Cell Temperature; default is 40°C.")
        st.caption("Orientation (azimuth) is applied in PVGIS; with tilt at 0°, azimuth has minimal effect.")
        st.number_input("Temp coefficient (/°C)", step=0.001, format="%.4f", key="temp_coeff")
        st.number_input(
            "Inverter AC limit (kW) — optional (0.0 means none)",
            min_value=0.0, max_value=50.0, step=0.1, key="inverter_ac_kw"
        )

    st.divider()
    required_label("Annual household electricity use (kWh/year)")
    st.number_input("Annual household electricity use (kWh/year)", min_value=100.0, max_value=30000.0, step=100.0, key="annual_load_kwh", label_visibility="collapsed")
    st.selectbox("Load profile", options=["away_daytime", "home_daytime"], key="profile")
    st.slider(
        "Seasonal demand swing (Dec vs Jun) (%)",
        min_value=20,
        max_value=40,
        value=30,
        step=1,
        key="seasonal_variance_pct",
    )
    st.caption("Week plot length is fixed at 7 days.")

    st.divider()
    st.radio(
        "Tariff mode",
        options=["compare", "compare_all", "A", "B", "C"],
        horizontal=True,
        key="tariff_mode",
        format_func=lambda x: TARIFF_MODE_LABELS.get(x, x),
    )
    st.caption("Tariff A = flat import price + flat export payment. Tariff B = time-of-use import prices + flat export payment. Compare = show both. Tariff C is a worst-case export payment scenario (very low export rate).")

    st.number_input("Tariff A — flat import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_import")
    st.number_input("Tariff A — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_export")
    st.number_input("Tariff B — peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_peak")
    st.number_input("Tariff B — off‑peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_offpeak")
    st.number_input("Tariff B — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_export")
    if st.session_state["tariff_mode"] in {"C", "compare_all"}:
        st.number_input("Tariff C — minimum export payment (worst‑case) (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffC_export")
        st.caption("Example: 0.05 = 5p per kWh exported")
    st.number_input("Peak start hour (0–23)", min_value=0, max_value=23, step=1, key="peak_start")
    st.number_input("Peak end hour (1–24)", min_value=1, max_value=24, step=1, key="peak_end")

    st.divider()
    required_label("Upfront system cost (£)")
    st.number_input("Upfront system cost (£)", min_value=0.0, max_value=200000.0, step=100.0, key="capex", label_visibility="collapsed")
    st.number_input("Discount rate (used to value future savings) (%)", min_value=0.0, max_value=20.0, step=0.1, format="%.2f", key="discount_rate_pct")
    st.number_input("Lifetime (years)", min_value=1, max_value=50, step=1, key="lifetime_years")
    st.number_input("Degradation per year", min_value=0.0, max_value=0.03, step=0.001, format="%.4f", key="degradation")
    st.number_input("Yearly maintenance (% of upfront cost)", min_value=0.0, max_value=5.0, step=0.1, format="%.2f", key="om_frac_pct")
    st.number_input("End-of-life salvage / disposal value (£)", min_value=-200000.0, max_value=200000.0, step=50.0, key="salvage_value_gbp")
    st.caption("Positive = salvage value recovered. Negative = disposal cost at end of life.")
    st.caption("This is an estimate over 15 years.")

    st.checkbox("Export hourly CSV", key="export_hourly")
    st.checkbox("Export daily CSV", key="export_daily")
    st.checkbox("Export monthly CSV", key="export_monthly")
    st.markdown("### Comparative analysis (recommended)")
    st.checkbox(
        "Run model sanity checks (recommended)",
        key="enable_verification_checks",
        help="Checks the energy accounting adds up (no negative kWh, PV splits correctly, etc.).",
    )
    st.checkbox(
        "Compare against PVGIS reference PV output (optional, slower)",
        key="enable_pvgis_crosscheck",
        help="Cross-checks monthly PV output against PVGIS’s built-in PV calculation.",
    )
    st.divider()
    st.checkbox("Enable historical variability (multi-year)", key="enable_variability")
    vcols = st.columns(2)
    with vcols[0]:
        st.number_input(
            "Start year",
            min_value=2005,
            max_value=2023,
            step=1,
            key="variability_year_start",
        )
    with vcols[1]:
        st.number_input(
            "End year",
            min_value=2005,
            max_value=2023,
            step=1,
            key="variability_year_end",
        )
    st.text_input("Run notes (optional)", key="run_notes")
# === ORIGINAL SIDEBAR LAYOUT (END) ===


# === COMPACT SIDEBAR LAYOUT (BEGIN) ===
def render_sidebar_inputs_compact() -> None:
    st.subheader("Inputs")
    st.caption("* Required fields are marked with a red star.")

    with st.expander("Location & time", expanded=False):
        render_location_selector_block()
        required_label("Location name (for filenames)")
        st.text_input("Location name (for filenames)", key="location_name", label_visibility="collapsed")
        st.number_input("Year", min_value=2005, max_value=2023, step=1, key="year_pending")
        st.caption("Available range: 2005–2023 (PVGIS 5.3 model).")

    with st.expander("Solar system (PV)", expanded=False):
        required_label("PV system size (kWp)")
        st.number_input("PV system size (kWp)", min_value=0.1, max_value=50.0, step=0.1, key="system_kw", label_visibility="collapsed")
        st.caption("kWp = panel peak rating (what installers quote).")
        st.selectbox("Roof orientation", options=list(ORIENTATION_OPTIONS.keys()), key="orientation")
        st.checkbox("I live in the southern hemisphere (advanced)", key="southern_hemisphere")
        st.caption(f"Effective azimuth used: {effective_azimuth_from_state():.0f}°")
        with st.expander("Advanced PV parameters", expanded=False):
            st.slider("System losses (%)", min_value=8, max_value=20, step=1, key="loss_frac_pct")
            st.session_state["loss_frac"] = float(st.session_state["loss_frac_pct"]) / 100.0
            st.number_input("Panel tilt (°)", min_value=0.0, max_value=90.0, step=1.0, key="surface_tilt")
            st.number_input("Cell temperature assumption (NOCT, °C)", min_value=20.0, max_value=70.0, value=40.0, step=1.0, key="noct")
            st.caption("NOCT = Nominal Operating Cell Temperature; default is 40°C.")
            st.caption("Orientation (azimuth) is applied in PVGIS; with tilt at 0°, azimuth has minimal effect.")
            st.number_input("Temp coefficient (/°C)", step=0.001, format="%.4f", key="temp_coeff")
            st.number_input(
                "Inverter AC limit (kW) — optional (0.0 means none)",
                min_value=0.0, max_value=50.0, step=0.1, key="inverter_ac_kw"
            )

    with st.expander("Home electricity use", expanded=False):
        required_label("Annual household electricity use (kWh/year)")
        st.number_input("Annual household electricity use (kWh/year)", min_value=100.0, max_value=30000.0, step=100.0, key="annual_load_kwh", label_visibility="collapsed")
        st.selectbox("Load profile", options=["away_daytime", "home_daytime"], key="profile")
        st.slider(
            "Seasonal demand swing (Dec vs Jun) (%)",
            min_value=20,
            max_value=40,
            value=30,
            step=1,
            key="seasonal_variance_pct",
        )
        st.caption("Week plot length is fixed at 7 days.")

    with st.expander("Tariffs", expanded=False):
        st.radio(
            "Tariff mode",
            options=["compare", "compare_all", "A", "B", "C"],
            horizontal=True,
            key="tariff_mode",
            format_func=lambda x: TARIFF_MODE_LABELS.get(x, x),
        )
        st.caption("Tariff A = flat import price + flat export payment. Tariff B = time-of-use import prices + flat export payment. Compare = show both. Tariff C is a worst-case export payment scenario (very low export rate).")
        st.number_input("Tariff A — flat import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_import")
        st.number_input("Tariff A — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_export")
        st.number_input("Tariff B — peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_peak")
        st.number_input("Tariff B — off‑peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_offpeak")
        st.number_input("Tariff B — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_export")
        if st.session_state["tariff_mode"] in {"C", "compare_all"}:
            st.number_input("Tariff C — minimum export payment (worst‑case) (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffC_export")
            st.caption("Example: 0.05 = 5p per kWh exported")
        st.number_input("Peak start hour (0–23)", min_value=0, max_value=23, step=1, key="peak_start")
        st.number_input("Peak end hour (1–24)", min_value=1, max_value=24, step=1, key="peak_end")

    with st.expander("Costs & outputs", expanded=False):
        required_label("Upfront system cost (£)")
        st.number_input("Upfront system cost (£)", min_value=0.0, max_value=200000.0, step=100.0, key="capex", label_visibility="collapsed")
        st.number_input("Discount rate (used to value future savings) (%)", min_value=0.0, max_value=20.0, step=0.1, format="%.2f", key="discount_rate_pct")
        st.number_input("Lifetime (years)", min_value=1, max_value=50, step=1, key="lifetime_years")
        st.number_input("Degradation per year", min_value=0.0, max_value=0.03, step=0.001, format="%.4f", key="degradation")
        st.number_input("Yearly maintenance (% of upfront cost)", min_value=0.0, max_value=5.0, step=0.1, format="%.2f", key="om_frac_pct")
        st.number_input("End-of-life salvage / disposal value (£)", min_value=-200000.0, max_value=200000.0, step=50.0, key="salvage_value_gbp")
        st.caption("Positive = salvage value recovered. Negative = disposal cost at end of life.")
        st.caption("This is an estimate over 15 years.")
        st.checkbox("Export hourly CSV", key="export_hourly")
        st.checkbox("Export daily CSV", key="export_daily")
        st.checkbox("Export monthly CSV", key="export_monthly")

    with st.expander("Comparative analysis (recommended)", expanded=False):
        st.checkbox(
            "Run model sanity checks (recommended)",
            key="enable_verification_checks",
            help="Checks the energy accounting adds up (no negative kWh, PV splits correctly, etc.).",
        )
        st.checkbox(
            "Compare against PVGIS reference PV output (optional, slower)",
            key="enable_pvgis_crosscheck",
            help="Cross-checks monthly PV output against PVGIS’s built-in PV calculation.",
        )
        st.checkbox("Enable historical variability (multi-year)", key="enable_variability")
        vcols = st.columns(2)
        with vcols[0]:
            st.number_input(
                "Start year",
                min_value=2005,
                max_value=2023,
                step=1,
                key="variability_year_start",
            )
        with vcols[1]:
            st.number_input(
                "End year",
                min_value=2005,
                max_value=2023,
                step=1,
                key="variability_year_end",
            )
        st.text_input("Run notes (optional)", key="run_notes")
# === COMPACT SIDEBAR LAYOUT (END) ===

with controls_area:
    if controls_in_sidebar:
        if st.button("← Back to full-screen inputs", use_container_width=True):
            st.session_state["has_run_once"] = False
            st.session_state["selected_run_dir"] = ""
            st.rerun()
        st.header("Quick Controls")
    else:
        st.header("Project Setup")
        st.caption("Set your assumptions and press Calculate to run the model.")

    if st.session_state.get("status_msg"):
        st.info(st.session_state["status_msg"])

    st.divider()

    runs = list_recent_runs(limit=10)
    if controls_in_sidebar:
        st.info("Edit parameters in this left panel, then press **↻ Recalculate** on the right to update outputs.")
    else:
        render_location_selector_block()

    st.divider()

    if controls_in_sidebar:
        st.markdown("### **Chart Settings**")
        render_chart_settings_block(show_heading=False)
        st.divider()
        if st.session_state.get("compact_sidebar_sections", True):
            render_sidebar_inputs_compact()
        else:
            render_sidebar_inputs_original()
    else:
        st.subheader("Inputs")
        st.caption("* Required fields are marked with a red star.")
        with st.form("inputs_form"):
            with st.expander("Location & time", expanded=False):
                required_label("Location name (for filenames)")
                st.text_input("Location name (for filenames)", key="location_name", label_visibility="collapsed")
                st.number_input("Year", min_value=2005, max_value=2023, step=1, key="year")
                st.caption("Available range: 2005–2023 (PVGIS 5.3 model).")

            with st.expander("Solar system (PV)", expanded=False):
                required_label("PV system size (kWp)")
                st.number_input("PV system size (kWp)", min_value=0.1, max_value=50.0, step=0.1, key="system_kw", label_visibility="collapsed")
                st.caption("kWp = panel peak rating (what installers quote).")
                st.selectbox("Roof orientation", options=list(ORIENTATION_OPTIONS.keys()), key="orientation")
                st.checkbox("I live in the southern hemisphere (advanced)", key="southern_hemisphere")
                st.caption(f"Effective azimuth used: {effective_azimuth_from_state():.0f}°")
                with st.expander("Advanced PV parameters", expanded=False):
                    st.slider("System losses (%)", min_value=8, max_value=20, step=1, key="loss_frac_pct")
                    st.session_state["loss_frac"] = float(st.session_state["loss_frac_pct"]) / 100.0
                    st.number_input("Panel tilt (°)", min_value=0.0, max_value=90.0, step=1.0, key="surface_tilt")
                    st.number_input("Cell temperature assumption (NOCT, °C)", min_value=20.0, max_value=70.0, value=40.0, step=1.0, key="noct")
                    st.caption("NOCT = Nominal Operating Cell Temperature; default is 40°C.")
                    st.caption("Orientation (azimuth) is applied in PVGIS; with tilt at 0°, azimuth has minimal effect.")
                    st.number_input("Temp coefficient (/°C)", step=0.001, format="%.4f", key="temp_coeff")
                    st.number_input(
                        "Inverter AC limit (kW) — optional (0.0 means none)",
                        min_value=0.0, max_value=50.0, step=0.1, key="inverter_ac_kw"
                    )

            with st.expander("Home electricity use", expanded=False):
                required_label("Annual household electricity use (kWh/year)")
                st.number_input("Annual household electricity use (kWh/year)", min_value=100.0, max_value=30000.0, step=100.0, key="annual_load_kwh", label_visibility="collapsed")
                st.selectbox("Load profile", options=["away_daytime", "home_daytime"], key="profile")
                st.slider(
                    "Seasonal demand swing (Dec vs Jun) (%)",
                    min_value=20,
                    max_value=40,
                    value=30,
                    step=1,
                    key="seasonal_variance_pct",
                )
                st.caption("Week plot length is fixed at 7 days.")

            with st.expander("Tariffs", expanded=False):
                st.radio(
                    "Tariff mode",
                    options=["compare", "compare_all", "A", "B", "C"],
                    horizontal=True,
                    key="tariff_mode",
                    format_func=lambda x: TARIFF_MODE_LABELS.get(x, x),
                )
                st.caption("Tariff A = flat import price + flat export payment. Tariff B = time-of-use import prices + flat export payment. Compare = show both. Tariff C is a worst-case export payment scenario (very low export rate).")
                st.number_input("Tariff A — flat import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_import")
                st.number_input("Tariff A — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffA_export")
                st.number_input("Tariff B — peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_peak")
                st.number_input("Tariff B — off‑peak import price (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_offpeak")
                st.number_input("Tariff B — export payment (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffB_export")
                if st.session_state["tariff_mode"] in {"C", "compare_all"}:
                    st.number_input("Tariff C — minimum export payment (worst‑case) (£/kWh)", min_value=0.0, max_value=3.0, step=0.01, format="%.3f", key="tariffC_export")
                    st.caption("Example: 0.05 = 5p per kWh exported")
                st.number_input("Peak start hour (0–23)", min_value=0, max_value=23, step=1, key="peak_start")
                st.number_input("Peak end hour (1–24)", min_value=1, max_value=24, step=1, key="peak_end")

            with st.expander("Costs & outputs", expanded=False):
                required_label("Upfront system cost (£)")
                st.number_input("Upfront system cost (£)", min_value=0.0, max_value=200000.0, step=100.0, key="capex", label_visibility="collapsed")
                st.number_input("Discount rate (used to value future savings) (%)", min_value=0.0, max_value=20.0, step=0.1, format="%.2f", key="discount_rate_pct")
                st.number_input("Lifetime (years)", min_value=1, max_value=50, step=1, key="lifetime_years")
                st.number_input("Degradation per year", min_value=0.0, max_value=0.03, step=0.001, format="%.4f", key="degradation")
                st.number_input("Yearly maintenance (% of upfront cost)", min_value=0.0, max_value=5.0, step=0.1, format="%.2f", key="om_frac_pct")
                st.number_input("End-of-life salvage / disposal value (£)", min_value=-200000.0, max_value=200000.0, step=50.0, key="salvage_value_gbp")
                st.caption("Positive = salvage value recovered. Negative = disposal cost at end of life.")
                st.caption("This is an estimate over 15 years.")
                st.checkbox("Export hourly CSV", key="export_hourly")
                st.checkbox("Export daily CSV", key="export_daily")
                st.checkbox("Export monthly CSV", key="export_monthly")

            with st.expander("Comparative analysis (recommended)", expanded=False):
                st.checkbox(
                    "Run model sanity checks (recommended)",
                    key="enable_verification_checks",
                    help="Checks the energy accounting adds up (no negative kWh, PV splits correctly, etc.).",
                )
                st.checkbox(
                    "Compare against PVGIS reference PV output (optional, slower)",
                    key="enable_pvgis_crosscheck",
                    help="Cross-checks monthly PV output against PVGIS’s built-in PV calculation.",
                )
                st.checkbox("Enable historical variability (multi-year)", key="enable_variability")
                vcols = st.columns(2)
                with vcols[0]:
                    st.number_input(
                        "Start year",
                        min_value=2005,
                        max_value=2023,
                        step=1,
                        key="variability_year_start",
                    )
                with vcols[1]:
                    st.number_input(
                        "End year",
                        min_value=2005,
                        max_value=2023,
                        step=1,
                        key="variability_year_end",
                    )
            st.text_input("Run notes (optional)", key="run_notes")
            render_chart_settings_block(show_heading=True)
            run_clicked = st.form_submit_button("▶ Calculate", use_container_width=True)

# ---------------------------
# Run action
# ---------------------------
if controls_in_sidebar:
    st.markdown(
        """
        <style>
        div.st-key-floating_recalculate {
            position: fixed;
            right: 0.35rem;
            top: 45%;
            transform: translateY(-50%);
            z-index: 9999;
        }
        div.st-key-floating_recalculate button {
            border-radius: 8px 0 0 8px;
            min-width: 54px;
            min-height: 170px;
            padding: 14px 10px;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            letter-spacing: 0.6px;
            font-weight: 700;
            font-size: 0.95rem;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.20);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("↻ Recalculate", key="floating_recalculate"):
        run_clicked = True

if run_clicked:
    if controls_in_sidebar:
        st.session_state["year"] = int(st.session_state.get("year_pending", st.session_state["year"]))
    errs = validate_ui_inputs()
    if errs:
        st.error("Please fix these input issues:")
        for e in errs:
            st.write(f"- {e}")
        st.stop()

    try:
        cfg = build_cfg_from_state()
        validate_config(cfg)
    except Exception as e:
        st.error("Config validation failed. Fix the inputs and try again.")
        if st.session_state["debug_mode"]:
            st.exception(e)
        else:
            st.code(str(e))
        st.stop()

    with st.spinner("Running pipeline…"):
        try:
            run_dir = run_pipeline(cfg)
            st.session_state["last_run_dir"] = str(run_dir)
            st.session_state["selected_run_dir"] = str(run_dir)
            st.session_state["has_run_once"] = True
            st.session_state["status_msg"] = "Run complete."
            st.rerun()
        except Exception as e:
            msg = str(e)

            # Friendly PVGIS messaging
            if "PVGIS fetch failed" in msg or "no cache is available" in msg.lower():
                st.error("PVGIS data fetch failed (and cache is missing).")
                st.write("Try one of these:")
                st.write("- Turn OFF **Force PVGIS refresh** to use cache (if you have it).")
                st.write("- Use the **Warwick demo (cached, reliable)** preset.")
                st.write("- Select a **previous run** from Run history (works offline).")
                st.write("- If you need new data: run once when internet/VPN allows PVGIS, to build cache.")
            else:
                st.error("Pipeline failed.")

            if st.session_state["debug_mode"]:
                st.exception(e)
            else:
                st.code(msg)

            st.stop()

# ---------------------------
# Main display: tabs
# ---------------------------
selected = st.session_state.get("selected_run_dir", "").strip()
if not selected:
    st.info("Choose a preset or fill inputs and click **Calculate**. You can also view a previous run using Run history.")
    st.stop()

run_dir = Path(selected)
if not run_dir.exists():
    st.error(f"Selected run folder does not exist:\n{run_dir}")
    st.stop()

# Ensure report exists for older runs
summary_html = run_dir / "summary.html"
if not summary_html.exists():
    # Try to generate it (safe)
    try:
        generate_run_report(run_dir)
    except Exception:
        pass

st.subheader("Run Folder Path (Advanced)")
st.text_input("Copy path", value=str(run_dir), disabled=False)

tabs = st.tabs(["Overview", "Comparative analysis", "Charts", "Data Tables", "Run Files"])

with tabs[0]:
    st.subheader("Key Performance Indicators")

    fin_df = safe_read_csv(run_dir / "outputs" / "financial_summary.csv")
    if fin_df is None or fin_df.empty:
        st.warning("financial_summary.csv missing or empty.")
    else:
        fin = fin_df.iloc[0].to_dict()
        annual_pv = fin.get("annual_pv_kwh")
        annual_load = fin.get("annual_load_kwh")
        annual_self = fin.get("annual_self_consumed_kwh")
        export_kwh = fin.get("annual_exported_kwh")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Solar production (kWh/year)", _fmt_kwh(annual_pv))
        c2.metric("Household use (kWh/year)", _fmt_kwh(annual_load))
        c3.metric("Used in home (kWh/year)", _fmt_kwh(annual_self))
        c4.metric("Energy sent to grid (kWh/year)", _fmt_kwh(export_kwh))

        has_tariff_c = fin.get("tariff_mode") == "compare_all"
        c5, c6 = st.columns(2)

        if has_tariff_c:
            c5, c6, c7 = st.columns(3)
            c5.metric("Yearly bill savings (Tariff A)", _fmt_gbp(fin.get("annual_savings_tariffA_gbp")))
            c6.metric("Yearly bill savings (Tariff B)", _fmt_gbp(fin.get("annual_savings_tariffB_gbp")))
            c7.metric("Yearly bill savings (Tariff C)", _fmt_gbp(fin.get("annual_savings_tariffC_gbp")))
            st.write(
                f"Payback time A: **{_fmt_years(fin.get('payback_year_tariffA'))}**, Lifetime value (discounted) A: **{_fmt_gbp(fin.get('npv_tariffA'))}**  \n"
                f"Payback time B: **{_fmt_years(fin.get('payback_year_tariffB'))}**, Lifetime value (discounted) B: **{_fmt_gbp(fin.get('npv_tariffB'))}**  \n"
                f"Payback time C: **{_fmt_years(fin.get('payback_year_tariffC'))}**, Lifetime value (discounted) C: **{_fmt_gbp(fin.get('npv_tariffC'))}**"
            )
            st.caption('"Discounted" uses the discount rate assumption over the chosen lifetime (estimate, not guaranteed).')
        elif fin.get("tariff_mode") == "compare" or ("annual_savings_tariffA_gbp" in fin and "annual_savings_tariffB_gbp" in fin):
            c5.metric("Yearly bill savings (Tariff A)", _fmt_gbp(fin.get("annual_savings_tariffA_gbp")))
            c6.metric("Yearly bill savings (Tariff B)", _fmt_gbp(fin.get("annual_savings_tariffB_gbp")))
            st.write(
                f"Payback time A: **{_fmt_years(fin.get('payback_year_tariffA'))}**, Lifetime value (discounted) A: **{_fmt_gbp(fin.get('npv_tariffA'))}**  \n"
                f"Payback time B: **{_fmt_years(fin.get('payback_year_tariffB'))}**, Lifetime value (discounted) B: **{_fmt_gbp(fin.get('npv_tariffB'))}**"
            )
            st.caption('"Discounted" uses the discount rate assumption over the chosen lifetime (estimate, not guaranteed).')
        else:
            c5.metric("Yearly bill savings", _fmt_gbp(fin.get("annual_savings_gbp")))
            c6.metric("Lifetime value (discounted)", _fmt_gbp(fin.get("npv")))
            st.caption('"Discounted" uses the discount rate assumption over the chosen lifetime (estimate, not guaranteed).')
            st.write(f"Payback time: **{_fmt_years(fin.get('payback_year'))}**")

    run_cfg = {}
    try:
        run_cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    except Exception:
        run_cfg = {}
    variability_enabled = bool(((run_cfg.get("outputs") or {}).get("enable_variability", False)))
    if variability_enabled:
        st.subheader("Historical variability (multi-year)")
        variability_csv = run_dir / "outputs" / "variability_summary.csv"
        variability_png = run_dir / "outputs" / "variability_annual_savings_vs_year.png"
        found_any = False

        variability_df = safe_read_csv(variability_csv)
        if variability_df is not None and not variability_df.empty:
            found_any = True
            st.write("**variability_summary.csv**")
            st.dataframe(_display_df(variability_df), use_container_width=True)

        if variability_png.exists():
            found_any = True
            st.image(str(variability_png), use_container_width=True)

        if not found_any:
            st.info(f"Historical variability is enabled for this run, but outputs are missing in: {run_dir / 'outputs'}")

    st.subheader("Shareable Report")
    if summary_html.exists():
        st.download_button(
            "Download report (HTML)",
            data=summary_html.read_bytes(),
            file_name="summary.html",
            mime="text/html",
            use_container_width=True,
        )
        st.write("Standalone report file:")
        st.code(str(summary_html))
    else:
        if st.button("Generate report (HTML)"):
            try:
                p = generate_run_report(run_dir)
                st.success(f"Generated: {p}")
                st.download_button(
                    "Download report (HTML)",
                    data=p.read_bytes(),
                    file_name="summary.html",
                    mime="text/html",
                    use_container_width=True,
                )
                st.write("Standalone report file:")
                st.code(str(p))
            except Exception as e:
                st.error(f"Failed to generate report (HTML): {e}")

    st.subheader("Data Source Details")
    st.markdown(
        """
**Where this data comes from (plain English):**

- This calculator uses **PVGIS 5.3** weather/solar data from the European Commission JRC.
- PVGIS provides historical sunlight and temperature data for your selected location and year (**2005–2023**).
- The model then combines that with your inputs (system size, orientation, tariffs, and household use) to estimate savings.

**Important to know:**

- This is a **planning estimate**, not a bill guarantee.
- It does **not** use your smart-meter half-hourly readings unless you separately input equivalent assumptions.
- Real outcomes can differ due to weather, usage habits, shading, equipment, and tariff changes.

**About the file below:**

- The data-source details file records the exact PVGIS request/settings used for this run, so results are traceable.
        """
    )
    prov = run_dir / "data" / "pvgis_request.txt"
    if prov.exists():
        st.write("PVGIS data-source details file:")
        st.code(str(prov))
        with st.expander("Show data-source details", expanded=False):
            st.code(prov.read_text(encoding="utf-8"))
    else:
        st.warning("pvgis_request.txt not found in this run (new runs should include it).")

    md = run_dir / "report" / "summary.md"
    if md.exists():
        with st.expander("Show report/summary.md", expanded=False):
            st.markdown(md.read_text(encoding="utf-8"))
    else:
        st.info("report/summary.md not found.")

with tabs[1]:
    st.subheader("Comparative analysis")
    run_cfg = {}
    try:
        run_cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    except Exception:
        run_cfg = {}
    outputs_cfg = run_cfg.get("outputs") or {}

    ver_path = run_dir / "outputs" / "verification_checks.csv"
    ver_df = safe_read_csv(ver_path)

    cross_summary_path = run_dir / "outputs" / "pvgis_crosscheck_summary.csv"
    cross_monthly_path = run_dir / "outputs" / "pvgis_crosscheck_monthly.csv"
    cross_plot = run_dir / "outputs" / "plots" / "pvgis_crosscheck_monthly.png"
    cross_status = run_dir / "outputs" / "pvgis_crosscheck_status.txt"
    cross_summary = safe_read_csv(cross_summary_path)

    var_summary_path = run_dir / "outputs" / "variability_summary.csv"
    var_yearly_path = run_dir / "outputs" / "variability_yearly.csv"
    var_plot_line = run_dir / "outputs" / "variability_annual_savings_vs_year.png"
    var_plot_hist = run_dir / "outputs" / "variability_annual_savings_hist.png"
    var_status = run_dir / "outputs" / "variability_status.txt"
    var_summary = safe_read_csv(var_summary_path)

    selected_var_row = None
    if var_summary is not None and not var_summary.empty and "metric" in var_summary.columns:
        for metric in [
            "annual_savings_gbp",
            "annual_savings_tariffA_gbp",
            "annual_savings_tariffB_gbp",
            "annual_savings_tariffC_gbp",
        ]:
            sub = var_summary[var_summary["metric"] == metric]
            if not sub.empty:
                selected_var_row = sub.iloc[0]
                break

    card1, card2, card3 = st.columns(3, gap="large")

    with card1:
        st.markdown("### 🌤️ Weather uncertainty (most important)")
        if selected_var_row is not None:
            p10 = selected_var_row.get("p10")
            p50 = selected_var_row.get("p50")
            p90 = selected_var_row.get("p90")
            st.markdown(f"**Most years: {_fmt_gbp(p10)} – {_fmt_gbp(p90)} savings**")
            st.markdown(f"**Typical year: {_fmt_gbp(p50)} savings**")
            st.caption("10th percentile (cloudier year)")
            st.caption("50th percentile (typical year)")
            st.caption("90th percentile (very sunny year)")
            st.caption("These numbers come from running the same system across many historical weather years.")
        elif var_status.exists():
            st.warning(var_status.read_text(encoding="utf-8"))
        else:
            if bool(outputs_cfg.get("enable_variability", False)):
                st.info("Historical variability outputs were expected, but are not available for this run.")
            else:
                st.info("Turn on 'Historical variability' to see how results change in sunnier vs cloudier years.")

    with card2:
        st.markdown("### 🧭 Consistency with PVGIS reference")
        if cross_summary is not None and not cross_summary.empty:
            crow = cross_summary.iloc[0].to_dict()
            monthly_mape = float(crow.get("monthly_mape_pct", float("nan")))
            annual_diff = float(crow.get("annual_pct_error", float("nan")))
            st.markdown(f"**Average monthly difference vs PVGIS: ~{monthly_mape:.0f}%**")
            st.markdown(f"**Annual difference vs PVGIS: {annual_diff:.1f}%**")
            st.caption("This is NOT smart-meter validation. It's a consistency check against PVGIS's built-in PV model for the same location and system.")
        elif cross_status.exists():
            st.warning("PVGIS cross-check couldn't run this time (network/API). Your main results are still valid.")
        else:
            if bool(outputs_cfg.get("enable_pvgis_crosscheck", False)):
                st.info("PVGIS cross-check outputs were expected, but are not available for this run.")
            else:
                st.info("Turn on 'PVGIS cross-check' to compare against PVGIS reference output.")

    with card3:
        st.markdown("### 🧱 Model integrity checks")
        if ver_df is not None and not ver_df.empty and "status" in ver_df.columns:
            fail_n = int((ver_df["status"] == "FAIL").sum())
            st.markdown("**Passed**" if fail_n == 0 else "**Needs attention**")
            st.caption("These checks make sure the energy accounting adds up (no impossible values).")
            if fail_n > 0:
                st.error("Some checks failed. See Advanced / technical details.")
        else:
            if bool(outputs_cfg.get("enable_verification_checks", False)):
                st.info("Verification checks were expected, but are not available for this run.")
            else:
                st.info("Turn on 'Model sanity checks' to confirm the energy accounting is consistent.")

    st.markdown("### How to read this")
    st.markdown("- Typical year = middle of historical years")
    st.markdown("- 10th percentile = only 10% of years were worse (cloudier)")
    st.markdown("- 90th percentile = only 10% of years were better (sunnier)")
    st.markdown("- PVGIS check = comparison to PVGIS model, not your household meter")

    with st.expander("What do 10th/50th/90th percentile values mean?", expanded=False):
        st.write(
            "10th percentile means a cloudier, lower-savings year. "
            "50th percentile means a typical middle year. "
            "90th percentile means a sunnier, higher-savings year."
        )

    if cross_summary is not None and not cross_summary.empty:
        with st.expander("What does MAPE mean?", expanded=False):
            st.write(
                "MAPE = average monthly percentage difference between this tool's PV output and PVGIS's PV output. "
                "Lower is better. This is a consistency check (two models), not measured data."
            )
        with st.expander("What does annual % difference mean?", expanded=False):
            st.write(
                "Annual % difference compares total yearly PV output from this tool against PVGIS reference output "
                "for the same location and system settings."
            )

    if selected_var_row is not None:
        st.markdown("### Historical weather view")
        v1, v2, v3 = st.columns(3)
        v1.metric("Cloudier-year savings (10th percentile)", _fmt_gbp(selected_var_row.get("p10")))
        v2.metric("Typical-year savings (50th percentile)", _fmt_gbp(selected_var_row.get("p50")))
        v3.metric("Sunny-year savings (90th percentile)", _fmt_gbp(selected_var_row.get("p90")))

        if var_plot_line.exists():
            st.image(str(var_plot_line), use_container_width=True)
            st.caption("Savings across historical years (shows how weather alone changes results).")
        if var_plot_hist.exists():
            st.image(str(var_plot_hist), use_container_width=True)
            st.caption("Distribution of savings across years. The markers show the 10th/50th/90th percentiles.")

    with st.expander("Advanced / technical details (for engineers & report)", expanded=False):
        st.write("**Verification checks table (raw)**")
        if ver_df is not None and not ver_df.empty:
            st.dataframe(_display_df(ver_df), use_container_width=True)
        else:
            st.caption("verification_checks.csv not available.")

        st.write("**PVGIS monthly cross-check table (raw)**")
        cross_monthly_df = safe_read_csv(cross_monthly_path)
        if cross_monthly_df is not None and not cross_monthly_df.empty:
            st.dataframe(_display_df(cross_monthly_df), use_container_width=True)
        else:
            st.caption("pvgis_crosscheck_monthly.csv not available.")

        st.write("**Variability summary table (raw)**")
        if var_summary is not None and not var_summary.empty:
            st.dataframe(_display_df(var_summary), use_container_width=True)
        else:
            st.caption("variability_summary.csv not available.")

        st.write("**Variability yearly table (raw)**")
        var_yearly_df = safe_read_csv(var_yearly_path)
        if var_yearly_df is not None and not var_yearly_df.empty:
            st.dataframe(_display_df(var_yearly_df), use_container_width=True)
        else:
            st.caption("variability_yearly.csv not available.")

        if cross_status.exists():
            st.write("**PVGIS cross-check status**")
            st.code(cross_status.read_text(encoding="utf-8"))
        if var_status.exists():
            st.write("**Variability status**")
            st.code(var_status.read_text(encoding="utf-8"))

with tabs[2]:
    st.subheader("Charts")
    st.info("To change chart visibility or duration, use **Chart Settings** in the left input panel.")
    plot_dir = run_dir / "outputs" / "plots"
    outputs_dir = run_dir / "outputs"
    shown = False

    def _png_download(path: Path, key: str) -> None:
        if path.exists():
            st.download_button(
                "Download PNG",
                data=path.read_bytes(),
                file_name=path.name,
                mime="image/png",
                key=key,
                use_container_width=False,
            )

    cfg_data = {}
    try:
        cfg_data = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    except Exception:
        cfg_data = {}
    location_slug = slugify(str((cfg_data.get("location") or {}).get("name", run_dir.name)))
    data_year = int((cfg_data.get("location") or {}).get("year", 2020))

    hourly_path = None
    for p in [
        outputs_dir / "hourly.csv",
        outputs_dir / "hourly_energy.csv",
        ROOT / "outputs" / f"hourly_energy_{location_slug}.csv",
    ]:
        if p.exists():
            hourly_path = p
            break
    hourly_df = safe_read_csv(hourly_path) if hourly_path else None
    if hourly_df is not None and not hourly_df.empty and "timestamp" in hourly_df.columns:
        hourly_df["timestamp"] = pd.to_datetime(hourly_df["timestamp"], utc=True, errors="coerce")
        hourly_df = hourly_df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()

    if hourly_df is not None and not hourly_df.empty:
        monthly_full = hourly_df[["pv_kwh", "load_kwh"]].resample("MS").sum()
        monthly_full.insert(0, "month", monthly_full.index.strftime("%Y-%m"))
        monthly_full = monthly_full.reset_index(drop=True)
        monthly_full["month_num"] = pd.to_datetime(monthly_full["month"] + "-01", errors="coerce").dt.month
    else:
        monthly_full = None

    monthly_fin_path = None
    for p in [outputs_dir / "financial_monthly.csv", outputs_dir / "monthly_fdinancial_summary.csv"]:
        if p.exists():
            monthly_fin_path = p
            break
    monthly_fin_df = safe_read_csv(monthly_fin_path) if monthly_fin_path else None

    if st.session_state.get("chart_show_monthly_pv", True) and monthly_full is not None and not monthly_full.empty:
        shown = True
        st.write("**Monthly PV vs Load**")
        m_start, m_end = st.session_state["chart_monthly_month_range"]
        monthly_view = monthly_full[(monthly_full["month_num"] >= int(m_start)) & (monthly_full["month_num"] <= int(m_end))].copy()
        if monthly_view.empty:
            monthly_view = monthly_full.copy()
        window_label = f"Months {int(m_start)} to {int(m_end)}"
        p = plot_dir / "monthly_pv_vs_load_view.png"
        plot_monthly_pv_vs_load(monthly_view, p, location_slug, window_label, data_year)
        st.image(str(p), use_container_width=True)
        _png_download(p, "dl_png_monthly_pv_view")
    elif st.session_state.get("chart_show_monthly_pv", True) and (plot_dir / "monthly_pv_vs_load.png").exists():
        shown = True
        st.write("**Monthly PV vs Load**")
        base = plot_dir / "monthly_pv_vs_load.png"
        st.image(str(base), use_container_width=True)
        _png_download(base, "dl_png_monthly_pv_base")

    if st.session_state.get("chart_show_monthly_bill", True) and monthly_fin_df is not None and not monthly_fin_df.empty:
        shown = True
        st.write("**Monthly bill benefit**")
        bill_view = monthly_fin_df.copy()
        if "month" in bill_view.columns:
            bill_view["month_num"] = pd.to_datetime(bill_view["month"] + "-01", errors="coerce").dt.month
            m_start, m_end = st.session_state["chart_bill_month_range"]
            bill_view = bill_view[(bill_view["month_num"] >= int(m_start)) & (bill_view["month_num"] <= int(m_end))].copy()
            if bill_view.empty:
                bill_view = monthly_fin_df.copy()
        if "month" in bill_view.columns:
            m_start, m_end = st.session_state["chart_bill_month_range"]
            window_label = f"Months {int(m_start)} to {int(m_end)}"
        else:
            window_label = ""
        p = plot_dir / "monthly_bill_benefit_view.png"
        tariff_mode = st.session_state.get("tariff_mode", "compare")
        fin_summary_df = safe_read_csv(outputs_dir / "financial_summary.csv")
        if fin_summary_df is not None and not fin_summary_df.empty:
            tariff_mode = str(fin_summary_df.iloc[0].get("tariff_mode", tariff_mode))
        plot_monthly_bill_benefit(bill_view, p, location_slug, window_label, tariff_mode, data_year)
        st.image(str(p), use_container_width=True)
        _png_download(p, "dl_png_monthly_bill_view")
    elif st.session_state.get("chart_show_monthly_bill", True) and (plot_dir / "monthly_bill_benefit.png").exists():
        shown = True
        st.write("**Monthly bill benefit**")
        base = plot_dir / "monthly_bill_benefit.png"
        st.image(str(base), use_container_width=True)
        _png_download(base, "dl_png_monthly_bill_base")

    if st.session_state.get("chart_show_week", True) and hourly_df is not None and not hourly_df.empty:
        shown = True
        st.write("**Week timeseries**")
        start_year = pd.Timestamp(f"{data_year}-01-01", tz="UTC")
        start_ts = start_year + pd.Timedelta(days=int(st.session_state["chart_week_start_day"]) - 1)
        end_data = hourly_df.index.max()
        if start_ts > end_data:
            start_ts = hourly_df.index.min()
        days = int(st.session_state["chart_week_days"])
        p = plot_dir / "week_timeseries_view.png"
        plot_week_timeseries(hourly_df, p, location_slug, start_ts, days, f"{start_ts.date()} + {days}d", data_year)
        st.image(str(p), use_container_width=True)
        _png_download(p, "dl_png_week_view")
    elif st.session_state.get("chart_show_week", True) and (plot_dir / "week_timeseries.png").exists():
        shown = True
        st.write("**Week timeseries**")
        base = plot_dir / "week_timeseries.png"
        st.image(str(base), use_container_width=True)
        _png_download(base, "dl_png_week_base")

    if st.session_state.get("chart_show_split", True) and hourly_df is not None and not hourly_df.empty:
        shown = True
        st.write("**Energy split**")
        m_start, m_end = st.session_state["chart_split_month_range"]
        split_view = hourly_df[(hourly_df.index.month >= int(m_start)) & (hourly_df.index.month <= int(m_end))].copy()
        if split_view.empty:
            split_view = hourly_df.copy()
        p = plot_dir / "energy_split_view.png"
        plot_energy_split(split_view, p, location_slug, f"Months {int(m_start)} to {int(m_end)}", data_year)
        st.image(str(p), use_container_width=True)
        _png_download(p, "dl_png_split_view")
    elif st.session_state.get("chart_show_split", True) and (plot_dir / "energy_split.png").exists():
        shown = True
        st.write("**Energy split**")
        base = plot_dir / "energy_split.png"
        st.image(str(base), use_container_width=True)
        _png_download(base, "dl_png_split_base")

    if st.session_state.get("chart_show_cumulative", True):
        p = plot_dir / "cumulative_cashflow.png"
        if p.exists():
            shown = True
            st.write("**Cumulative cashflow**")
            st.image(str(p), use_container_width=True)
            _png_download(p, "dl_png_cumulative")

    if st.session_state.get("chart_show_annual_bars", True):
        p = plot_dir / "annual_cashflow_bars.png"
        if p.exists():
            shown = True
            st.write("**Annual cashflow bars**")
            st.image(str(p), use_container_width=True)
            _png_download(p, "dl_png_annual_bars")

    if not shown:
        st.info("No plots found for this run (maybe disabled by plot flags).")

with tabs[3]:
    st.subheader("Data Tables")
    table_files = [
        (("monthly.csv", "monthly_summary.csv"), "monthly.csv (monthly energy)"),
        (("financial_monthly.csv", "monthly_fdinancial_summary.csv"), "financial_monthly.csv (monthly money)"),
        (("daily.csv", "daily_energy.csv"), "daily.csv"),
        ("financial_summary.csv", "financial_summary.csv"),
    ]
    for name, label in table_files:
        if isinstance(name, tuple):
            p = None
            for candidate in name:
                cp = run_dir / "outputs" / candidate
                if cp.exists():
                    p = cp
                    break
            if p is None:
                p = run_dir / "outputs" / name[0]
        else:
            p = run_dir / "outputs" / name
        df = safe_read_csv(p)
        if df is not None and not df.empty:
            st.write(f"**{label}**")
            st.download_button(
                "Download CSV",
                data=p.read_bytes(),
                file_name=p.name,
                mime="text/csv",
                key=f"dl_csv_{p.name}",
                use_container_width=False,
            )
            st.dataframe(_display_df(df.head(50)), use_container_width=True)
        else:
            st.caption(f"{label}: not available")

    st.subheader("Details")
    hourly_path = run_dir / "outputs" / "hourly.csv"
    if not hourly_path.exists():
        hourly_path = run_dir / "outputs" / "hourly_energy.csv"
    hourly_df = safe_read_csv(hourly_path)
    if hourly_df is not None and not hourly_df.empty:
        with st.expander("Hourly data (large)", expanded=False):
            st.download_button(
                "Download hourly energy",
                data=hourly_path.read_bytes(),
                file_name=hourly_path.name,
                mime="text/csv",
                use_container_width=True,
            )
            st.dataframe(_display_df(hourly_df.head(50)), use_container_width=True)
    else:
        st.caption("hourly_energy.csv: not available")

with tabs[4]:
    st.subheader("Files in This Run Folder")
    paths = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            paths.append(str(p.relative_to(run_dir)))
    st.code("\n".join(paths[:400]) + ("\n…(truncated)" if len(paths) > 400 else ""))
