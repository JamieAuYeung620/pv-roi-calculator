# src/report_generator.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import html
import base64
from typing import Any, Dict, List, Tuple

import pandas as pd


PLOT_LABELS = {
    "monthly_pv_vs_load.png": "Monthly PV vs Load",
    "monthly_bill_benefit.png": "Monthly bill benefit",
    "week_timeseries.png": "Week timeseries",
    "energy_split.png": "Energy split",
    "cumulative_cashflow.png": "Cumulative cashflow",
    "annual_cashflow_bars.png": "Annual cashflow bars",
}


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_read_first_row_csv(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
        if df.empty:
            return {}
        return df.iloc[0].to_dict()
    except Exception:
        return {}


def _flatten(obj: Any, prefix: str = "") -> List[Tuple[str, str]]:
    """
    Flatten nested dict/list into [("a.b.c", "value"), ...]
    """
    rows: List[Tuple[str, str]] = []

    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            v = obj[k]
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            rows.extend(_flatten(v, new_prefix))
        return rows

    if isinstance(obj, list):
        for i, v in enumerate(obj):
            new_prefix = f"{prefix}[{i}]"
            rows.extend(_flatten(v, new_prefix))
        return rows

    # Base value
    if obj is None:
        s = "null"
    else:
        s = str(obj)
    rows.append((prefix, s))
    return rows


def _to_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        val = float(x)
        if pd.isna(val):
            return None
        return val
    except Exception:
        return None


def _money(x: Any) -> str:
    v = _to_float(x)
    if v is None:
        return "—"
    return f"£{v:,.2f}"


def _kwh(x: Any) -> str:
    v = _to_float(x)
    if v is None:
        return "—"
    return f"{v:,.0f} kWh"


def _pct(n: Any, d: Any) -> str:
    nn = _to_float(n)
    dd = _to_float(d)
    if nn is None or dd is None or dd <= 0:
        return "—"
    return f"{100.0 * nn / dd:.1f}%"


def _image_data_uri(path: Path) -> str | None:
    try:
        b = path.read_bytes()
        if not b:
            return None
        return f"data:image/png;base64,{base64.b64encode(b).decode('ascii')}"
    except Exception:
        return None


def _compute_kpi_rows(fin: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Build a KPI table using whatever columns exist in financial_summary.csv.
    Works for tariff_mode compare or single-mode.
    """
    rows: List[Tuple[str, str]] = []

    annual_pv = fin.get("annual_pv_kwh")
    annual_load = fin.get("annual_load_kwh")
    self_kwh = fin.get("annual_self_consumed_kwh")
    export_kwh = fin.get("annual_exported_kwh")
    import_kwh = fin.get("annual_grid_import_kwh") or fin.get("annual_import_kwh")  # if present

    rows.append(("Annual PV generation", _kwh(annual_pv)))
    rows.append(("Annual load", _kwh(annual_load)))
    rows.append(("Solar energy used in the home", _kwh(self_kwh)))
    rows.append(("Energy sent to grid", _kwh(export_kwh)))
    if import_kwh is not None:
        rows.append(("Energy bought from grid", _kwh(import_kwh)))

    rows.append(("% of solar used in the home", _pct(self_kwh, annual_pv)))
    rows.append(("Self-sufficiency (% of load met by PV)", _pct(self_kwh, annual_load)))

    tariff_mode = str(fin.get("tariff_mode") or "").strip().lower()

    # Compare mode: show A and B side-by-side if available
    if tariff_mode == "compare" or ("annual_savings_tariffA_gbp" in fin and "annual_savings_tariffB_gbp" in fin):
        rows.append(("Annual savings (Tariff A)", _money(fin.get("annual_savings_tariffA_gbp"))))
        rows.append(("Annual savings (Tariff B)", _money(fin.get("annual_savings_tariffB_gbp"))))
        rows.append(("Payback (Tariff A)", str(fin.get("payback_year_tariffA") or "—")))
        rows.append(("Payback (Tariff B)", str(fin.get("payback_year_tariffB") or "—")))
        rows.append(("Lifetime value (discounted) (Tariff A)", _money(fin.get("npv_tariffA"))))
        rows.append(("Lifetime value (discounted) (Tariff B)", _money(fin.get("npv_tariffB"))))
        include_tariff_c = tariff_mode == "compare_all" or any(
            k in fin for k in ("annual_savings_tariffC_gbp", "payback_year_tariffC", "npv_tariffC")
        )
        if include_tariff_c:
            rows.append(("Annual savings (Tariff C)", _money(fin.get("annual_savings_tariffC_gbp"))))
            rows.append(("Payback (Tariff C)", str(fin.get("payback_year_tariffC") or "—")))
            rows.append(("Lifetime value (discounted) (Tariff C)", _money(fin.get("npv_tariffC"))))
        return rows

    # Single mode: generic columns if present
    if "annual_savings_gbp" in fin:
        rows.append(("Annual savings", _money(fin.get("annual_savings_gbp"))))
    if "payback_year" in fin:
        rows.append(("Payback", str(fin.get("payback_year") or "—")))
    if "npv" in fin:
        rows.append(("Lifetime value (discounted)", _money(fin.get("npv"))))
    if "roi" in fin:
        v = _to_float(fin.get("roi"))
        rows.append(("ROI", f"{100.0 * v:.1f}%" if v is not None else "—"))

    return rows


def generate_run_report(run_dir: Path) -> Path:
    """
    Generate runs/<run_id>/summary.html (standalone).
    Uses relative links so it works when the run folder is shared.
    """
    run_dir = Path(run_dir)
    config_path = run_dir / "config.json"
    fin_path = run_dir / "outputs" / "financial_summary.csv"
    plots_dir = run_dir / "outputs" / "plots"
    prov_path = run_dir / "data" / "pvgis_request.txt"

    if not config_path.exists():
        raise FileNotFoundError(f"Missing config.json in run folder: {config_path}")

    cfg = _read_json(config_path)
    fin = _safe_read_first_row_csv(fin_path)

    run_id = (cfg.get("meta") or {}).get("run_id") or run_dir.name
    created = (cfg.get("meta") or {}).get("created_at_local") or "—"
    generated_at = datetime.now().isoformat(timespec="seconds")

    # Inputs table (flattened)
    inputs_rows = _flatten(cfg)
    inputs_rows = [(k, v) for (k, v) in inputs_rows if k]  # drop empty keys

    # KPI table
    kpi_rows = _compute_kpi_rows(fin) if fin else [("KPIs", "financial_summary.csv missing or empty")]

    # File list (relative paths)
    all_files: List[str] = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(run_dir).as_posix()
            all_files.append(rel)

    # Plot list (embed existing)
    plot_blocks: List[str] = []
    if plots_dir.exists():
        for name, label in PLOT_LABELS.items():
            p = plots_dir / name
            if p.exists():
                rel = p.relative_to(run_dir).as_posix()
                img_src = _image_data_uri(p) or rel
                plot_blocks.append(
                    f"""
                    <h3>{html.escape(label)}</h3>
                    <p><a href="{html.escape(rel)}">{html.escape(rel)}</a></p>
                    <img src="{html.escape(img_src)}" alt="{html.escape(label)}" style="max-width: 100%; height: auto; border: 1px solid #ddd;"/>
                    """
                )

    if not plot_blocks:
        plot_blocks.append("<p><em>No plots found in outputs/plots (maybe disabled by plot flags).</em></p>")

    # Provenance section
    prov_html = ""
    if prov_path.exists():
        prov_rel = prov_path.relative_to(run_dir).as_posix()
        try:
            txt = prov_path.read_text(encoding="utf-8")
            preview = "\n".join(txt.splitlines()[:25])
        except Exception:
            preview = "(could not read file)"
        prov_html = f"""
        <p>PV data is sourced from <strong>PVGIS (European Commission JRC)</strong>.</p>
        <p>Data source file: <a href="{html.escape(prov_rel)}">{html.escape(prov_rel)}</a></p>
        <pre style="white-space: pre-wrap; background: #f6f8fa; padding: 10px; border: 1px solid #ddd;">{html.escape(preview)}</pre>
        """
    else:
        # Still show minimal provenance info from config
        loc = cfg.get("location") or {}
        prov_html = f"""
        <p>PV data is sourced from <strong>PVGIS (European Commission JRC)</strong>.</p>
        <p><em>Provenance file data/pvgis_request.txt not found in this run.</em></p>
        <p>Location: lat={html.escape(str(loc.get("lat")))} lon={html.escape(str(loc.get("lon")))} year={html.escape(str(loc.get("year")))}.</p>
        """

    def render_table(rows: List[Tuple[str, str]], col1: str, col2: str) -> str:
        tr = "\n".join(
            f"<tr><td><code>{html.escape(k)}</code></td><td>{html.escape(v)}</td></tr>"
            for k, v in rows
        )
        return f"""
        <table>
          <thead><tr><th>{html.escape(col1)}</th><th>{html.escape(col2)}</th></tr></thead>
          <tbody>
            {tr}
          </tbody>
        </table>
        """

    inputs_table = render_table(inputs_rows, "Config key", "Value")
    kpi_table = render_table(kpi_rows, "Metric", "Value")

    confidence_blocks: List[str] = []

    ver_path = run_dir / "outputs" / "verification_checks.csv"
    if ver_path.exists():
        try:
            ver_df = pd.read_csv(ver_path).head(20)
            ver_rel = ver_path.relative_to(run_dir).as_posix()
            confidence_blocks.append(
                "<h3>Verification checks</h3>"
                f"<p><a href=\"{html.escape(ver_rel)}\">{html.escape(ver_rel)}</a></p>"
                + ver_df.to_html(index=False, border=0, escape=True)
            )
        except Exception:
            confidence_blocks.append("<p><strong>Verification checks:</strong> present but unreadable.</p>")

    cross_summary = run_dir / "outputs" / "pvgis_crosscheck_summary.csv"
    cross_monthly_plot = run_dir / "outputs" / "plots" / "pvgis_crosscheck_monthly.png"
    cross_status = run_dir / "outputs" / "pvgis_crosscheck_status.txt"
    if cross_summary.exists():
        try:
            cs_df = pd.read_csv(cross_summary)
            cs_rel = cross_summary.relative_to(run_dir).as_posix()
            block = "<h3>PVGIS cross-check</h3>"
            block += f"<p><a href=\"{html.escape(cs_rel)}\">{html.escape(cs_rel)}</a></p>"
            block += cs_df.to_html(index=False, border=0, escape=True)
            if cross_monthly_plot.exists():
                plot_rel = cross_monthly_plot.relative_to(run_dir).as_posix()
                img_src = _image_data_uri(cross_monthly_plot) or plot_rel
                block += f"<p><a href=\"{html.escape(plot_rel)}\">{html.escape(plot_rel)}</a></p>"
                block += f'<img src="{html.escape(img_src)}" alt="PVGIS cross-check monthly" style="max-width: 100%; height: auto; border: 1px solid #ddd;"/>'
            confidence_blocks.append(block)
        except Exception:
            confidence_blocks.append("<p><strong>PVGIS cross-check:</strong> present but unreadable.</p>")
    elif cross_status.exists():
        try:
            msg = cross_status.read_text(encoding="utf-8")
        except Exception:
            msg = "(could not read status)"
        confidence_blocks.append(f"<p><strong>PVGIS cross-check warning:</strong> {html.escape(msg)}</p>")

    var_summary = run_dir / "outputs" / "variability_summary.csv"
    var_line = run_dir / "outputs" / "variability_annual_savings_vs_year.png"
    var_hist = run_dir / "outputs" / "variability_annual_savings_hist.png"
    var_status = run_dir / "outputs" / "variability_status.txt"
    if var_summary.exists():
        try:
            vs_df = pd.read_csv(var_summary)
            vs_rel = var_summary.relative_to(run_dir).as_posix()
            block = "<h3>Historical variability</h3>"
            block += f"<p><a href=\"{html.escape(vs_rel)}\">{html.escape(vs_rel)}</a></p>"
            block += vs_df.to_html(index=False, border=0, escape=True)
            for img_path in [var_line, var_hist]:
                if img_path.exists():
                    rel = img_path.relative_to(run_dir).as_posix()
                    img_src = _image_data_uri(img_path) or rel
                    block += f"<p><a href=\"{html.escape(rel)}\">{html.escape(rel)}</a></p>"
                    block += f'<img src="{html.escape(img_src)}" alt="{html.escape(img_path.name)}" style="max-width: 100%; height: auto; border: 1px solid #ddd;"/>'
            confidence_blocks.append(block)
        except Exception:
            confidence_blocks.append("<p><strong>Historical variability:</strong> present but unreadable.</p>")
    elif var_status.exists():
        try:
            msg = var_status.read_text(encoding="utf-8")
        except Exception:
            msg = "(could not read status)"
        confidence_blocks.append(f"<p><strong>Historical variability warning:</strong> {html.escape(msg)}</p>")

    if not confidence_blocks:
        confidence_blocks.append("<p><em>No Step 3 confidence artifacts found for this run.</em></p>")

    files_list_items = "\n".join(
        f'<li><a href="{html.escape(rel)}">{html.escape(rel)}</a></li>'
        for rel in all_files
    )

    # Standalone HTML (no external deps)
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>PV ROI Demo Pack — {html.escape(str(run_id))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; line-height: 1.4; }}
    h1, h2 {{ margin-bottom: 0.2rem; }}
    .meta {{ color: #444; margin-top: 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 20px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background: #f3f3f3; text-align: left; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
    .section {{ margin-top: 28px; }}
    .small {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>PV ROI Demo Pack</h1>
  <p class="meta"><strong>Run ID:</strong> <code>{html.escape(str(run_id))}</code></p>
  <p class="meta"><strong>Created (local):</strong> <code>{html.escape(str(created))}</code></p>
  <p class="meta"><strong>Report generated at:</strong> <code>{html.escape(str(generated_at))}</code></p>

  <p class="small">
    This report is standalone inside the run folder. Links and images use <strong>relative paths</strong>.
  </p>

  <div class="section">
    <h2>Key outcomes</h2>
    {kpi_table}
  </div>

  <div class="section">
    <h2>Confidence checks (Step 3 substitutes)</h2>
    {''.join(confidence_blocks)}
  </div>

  <div class="section">
    <h2>Plots</h2>
    {''.join(plot_blocks)}
  </div>

  <div class="section">
    <h2>Inputs (full config used)</h2>
    {inputs_table}
  </div>

  <div class="section">
    <h2>Generated files</h2>
    <p>All files in this run folder (relative paths):</p>
    <ul>
      {files_list_items}
    </ul>
  </div>

  <div class="section">
    <h2>Data source details</h2>
    {prov_html}
  </div>

  <div class="section">
    <h2>Notes</h2>
    <p>If present, see <a href="summary.md">summary.md</a> (and legacy <a href="report/summary.md">report/summary.md</a>) plus <a href="logs.txt">logs.txt</a> for detailed logs.</p>
  </div>
</body>
</html>
"""

    out_path = run_dir / "summary.html"
    out_path.write_text(html_out, encoding="utf-8")
    return out_path
