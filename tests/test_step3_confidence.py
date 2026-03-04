from __future__ import annotations

import pandas as pd

from src.step3_confidence import compute_verification_checks


def _base_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pv_kwh": [1.0, 2.0, 0.5],
            "load_kwh": [1.2, 2.1, 0.6],
            "self_consumed_kwh": [0.8, 1.7, 0.4],
            "exported_kwh": [0.2, 0.3, 0.1],
            "grid_import_kwh": [0.4, 0.4, 0.2],
        }
    )


def test_verification_checks_all_pass():
    df = _base_df()
    checks = compute_verification_checks(df, system_kw=4.0)

    status = dict(zip(checks["check_id"], checks["status"]))
    assert status["non_negative"] == "PASS"
    assert status["pv_split"] == "PASS"
    assert status["load_balance"] == "PASS"
    assert status["capacity_factor"] == "PASS"


def test_verification_checks_pv_split_fail():
    df = _base_df()
    df.loc[0, "exported_kwh"] = 1.0  # self + export > pv

    checks = compute_verification_checks(df, system_kw=4.0)
    status = dict(zip(checks["check_id"], checks["status"]))
    assert status["pv_split"] == "FAIL"
