from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roi_calculator_core import compute_energy_flows, compute_pv_ac_power_kw_pvwatts  # noqa: E402
from roi_calculator_finance import compute_npv, compute_yearly_cashflows_with_degradation  # noqa: E402


def check_pv_generation_non_negative() -> None:
    irradiance = np.array([0.0, 120.0, 650.0, 980.0, 300.0], dtype=float)
    temp_air = np.array([-5.0, 5.0, 15.0, 30.0, 42.0], dtype=float)
    p_ac_kw = compute_pv_ac_power_kw_pvwatts(
        irradiance_w_per_m2=irradiance,
        temp_air_c=temp_air,
        system_kw_dc=4.0,
        temp_coeff_per_c=-0.004,
        loss_frac=0.14,
        inverter_eff=0.96,
        inverter_ac_kw=4.0,
        noct_c=40.0,
    )
    assert np.all(np.isfinite(p_ac_kw)), "PV output contains non-finite values."
    assert np.all(p_ac_kw >= 0.0), "PV output contains negative values."


def check_energy_balance_identity() -> None:
    # kWh per timestep synthetic series
    pv_kwh = np.array([0.0, 0.8, 2.0, 1.0, 0.1], dtype=float)
    load_kwh = np.array([0.6, 0.5, 1.3, 1.2, 0.2], dtype=float)
    flows = compute_energy_flows(pv_kwh=pv_kwh, load_kwh=load_kwh)

    pv_used = np.asarray(flows["self_consumed_kwh"], dtype=float)
    exported = np.asarray(flows["exported_kwh"], dtype=float)
    imported = np.asarray(flows["grid_import_kwh"], dtype=float)

    tol = 1e-9
    assert float(np.sum(pv_used + exported)) <= float(np.sum(pv_kwh)) + tol, "PV usage+export exceeds generation."
    assert abs(float(np.sum(imported + pv_used)) - float(np.sum(load_kwh))) <= tol, "Load balance identity failed."


def _npv_with_salvage(salvage_value_gbp: float) -> float:
    idx = pd.date_range("2020-01-01", periods=24, freq="h", tz="UTC")
    hourly = pd.DataFrame(
        {
            "load_kwh": np.full(len(idx), 1.0, dtype=float),
            "pv_kwh": np.full(len(idx), 0.6, dtype=float),
        },
        index=idx,
    )
    peak_mask = np.zeros(len(idx), dtype=bool)

    cashflows = compute_yearly_cashflows_with_degradation(
        hourly=hourly,
        lifetime_years=5,
        degradation_per_year=0.005,
        om_cost_gbp_per_year=20.0,
        salvage_value_gbp=float(salvage_value_gbp),
        discount_rate=0.05,
        tariffA_import=0.30,
        tariffA_export=0.10,
        tariffB_peak=0.35,
        tariffB_offpeak=0.22,
        tariffB_export=0.10,
        tariffC_export=0.05,
        peak_mask=peak_mask,
    )
    cf_a = np.asarray(cashflows["tariffA"]["net_cashflow_gbp"], dtype=float)
    df = np.asarray(cashflows["tariffA"]["discount_factors"], dtype=float)
    return compute_npv(cf_a, df)


def check_finance_sensitivity_salvage() -> None:
    npv_no_salvage = _npv_with_salvage(0.0)
    npv_negative_salvage = _npv_with_salvage(-500.0)
    npv_positive_salvage = _npv_with_salvage(500.0)

    assert npv_negative_salvage < npv_no_salvage, "NPV should decrease when salvage/disposal is more negative."
    assert npv_positive_salvage > npv_no_salvage, "NPV should increase when salvage value is more positive."


def main() -> int:
    checks = [
        ("PV generation is non-negative", check_pv_generation_non_negative),
        ("Energy balance identity holds", check_energy_balance_identity),
        ("Finance sensitivity to salvage affects NPV direction", check_finance_sensitivity_salvage),
    ]

    for name, fn in checks:
        fn()
        print(f"[OK] {name}")

    print("All sanity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
