from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

csv_path = Path("runs/2026-03-01_1930_warwick_campus_system4kw_load3500_v2/outputs/hourly.csv")
load_col = "load_kwh"

df = pd.read_csv(csv_path).copy()

df["hour_of_day"] = [i % 24 for i in range(len(df))]
mean_profile = df.groupby("hour_of_day")[load_col].mean()

plt.figure(figsize=(7.2, 4.2))
plt.plot(mean_profile.index, mean_profile.values, linewidth=2)
plt.xlabel("Hour of day")
plt.ylabel("Household demand (kWh per hour)")
plt.xticks(range(0, 24, 2))
plt.xlim(0, 23)
plt.tight_layout()

out_path = Path("synthetic_load_shape_24h_main_case.png")
plt.savefig(out_path, dpi=300, bbox_inches="tight")
print(f"Saved: {out_path}")