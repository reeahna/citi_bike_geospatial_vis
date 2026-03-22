"""
Citi Bike Geospatial Visualization — Individual Panel Exports
=============================================================
Saves 5 separate PNG files:
  fig1_station_demand.png       – Station demand bubble + hexbin map
  fig2_flow_corridors.png       – Cross-neighborhood flow arc map
  fig3_rideable_type_mix.png    – Classic vs electric bar chart
  fig4_heatmap.png              – Day-of-week × hour heatmap
  fig5_summary_stats.png        – Key descriptive statistics panel

INSTRUCTIONS: Update the three FILE paths below to point to your CSV files.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings("ignore")

# ── Colorblind-safe palette (Okabe-Ito) ──────────────────────────────────────
MEMBER_COLOR  = "#0072B2"
CASUAL_COLOR  = "#E69F00"
CLASSIC_COLOR = "#009E73"
ELEC_COLOR    = "#CC79A7"
FLOW_COLOR    = "#56B4E9"
BG_COLOR      = "#F7F7F7"
MAP_BG        = "#E8EEF4"

# =============================================================================
# DATA LOADING  ← swap these paths for your real monthly files
# =============================================================================
FILE_1 = r"C:\Users\reeah\OneDrive\Senior Year - 2025-2026\Information Visualization\Citi Bike\citi_bike\202501-citibike-tripdata\202501-citibike-tripdata_1.csv"
FILE_2 = r"C:\Users\reeah\OneDrive\Senior Year - 2025-2026\Information Visualization\Citi Bike\citi_bike\202501-citibike-tripdata\202501-citibike-tripdata_2.csv"
FILE_3 = r"C:\Users\reeah\OneDrive\Senior Year - 2025-2026\Information Visualization\Citi Bike\citi_bike\202501-citibike-tripdata\202501-citibike-tripdata_3.csv"

def load_file(path):
    if path is None:
        return None
    if path.endswith(".xlsx") or path.endswith(".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)

frames = [load_file(p) for p in [FILE_1, FILE_2, FILE_3] if p is not None]
df = pd.concat(frames, ignore_index=True)

# =============================================================================
# DATA PREPARATION
# =============================================================================
df["started_at"]   = pd.to_datetime(df["started_at"])
df["ended_at"]     = pd.to_datetime(df["ended_at"])
df["duration_min"] = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60
df["hour"]         = df["started_at"].dt.hour
df["dow"]          = df["started_at"].dt.dayofweek

df = df.dropna(subset=["start_lat","start_lng","end_lat","end_lng",
                        "start_station_name","end_station_name"])
df = df[(df["duration_min"] >= 1) & (df["duration_min"] <= 180)]

# NYC bounding box
df = df[
    df["start_lat"].between(40.49, 40.92) & df["start_lng"].between(-74.26, -73.68) &
    df["end_lat"].between(40.49, 40.92)   & df["end_lng"].between(-74.26, -73.68)
]

# Station-level aggregations
station_df = (
    df.groupby("start_station_name")
    .agg(
        lat     = ("start_lat",  "mean"),
        lng     = ("start_lng",  "mean"),
        total   = ("ride_id",    "count"),
        members = ("member_casual", lambda x: (x == "member").sum()),
        casual  = ("member_casual", lambda x: (x == "casual").sum()),
        electric= ("rideable_type", lambda x: (x == "electric_bike").sum()),
        classic = ("rideable_type", lambda x: (x == "classic_bike").sum()),
    ).reset_index()
)
station_df["member_frac"]   = station_df["members"] / station_df["total"]
station_df["electric_frac"] = station_df["electric"] / station_df["total"]

# Neighborhood-cluster OD flows
df["start_cell_lat"] = (df["start_lat"] / 0.025).round() * 0.025
df["start_cell_lng"] = (df["start_lng"] / 0.025).round() * 0.025
df["end_cell_lat"]   = (df["end_lat"]   / 0.025).round() * 0.025
df["end_cell_lng"]   = (df["end_lng"]   / 0.025).round() * 0.025

od_cells = (
    df.groupby(["start_cell_lat","start_cell_lng","end_cell_lat","end_cell_lng"])
    .agg(trips=("ride_id","count")).reset_index()
)
od_cells = od_cells[
    (od_cells["start_cell_lat"] != od_cells["end_cell_lat"]) |
    (od_cells["start_cell_lng"] != od_cells["end_cell_lng"])
]
od_cells["dist"] = np.sqrt(
    (od_cells["end_cell_lat"] - od_cells["start_cell_lat"])**2 +
    (od_cells["end_cell_lng"] - od_cells["start_cell_lng"])**2
)
od = od_cells[od_cells["dist"] >= 0.05].nlargest(20, "trips").copy()
od = od.rename(columns={
    "start_cell_lat":"start_lat","start_cell_lng":"start_lng",
    "end_cell_lat":"end_lat",   "end_cell_lng":"end_lng"
})

# Heatmap data
dow_order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
heat = df.groupby(["dow","hour"])["ride_id"].count().reset_index(name="rides")
pivot = heat.pivot(index="dow", columns="hour", values="rides").fillna(0)
for h in range(24):
    if h not in pivot.columns:
        pivot[h] = 0
pivot = pivot[sorted(pivot.columns)]
pivot.index = [dow_order[i] for i in pivot.index]

# Shared map bounds (tight to data)
PAD = 0.008
MAP_LNG_MIN = df["start_lng"].quantile(0.001) - PAD
MAP_LNG_MAX = df["start_lng"].quantile(0.999) + PAD
MAP_LAT_MIN = df["start_lat"].quantile(0.001) - PAD
MAP_LAT_MAX = df["start_lat"].quantile(0.999) + PAD

# =============================================================================
# HELPER: shared figure setup
# =============================================================================
def new_fig(w=10, h=8):
    fig, ax = plt.subplots(figsize=(w, h), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    for sp in ax.spines.values():
        sp.set_edgecolor("#CCCCCC")
    return fig, ax

def save(fig, name):
    fig.savefig(name, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    print(f"Saved → {name}")
    plt.close(fig)

# =============================================================================
# FIG 1 – Station Demand Map
# =============================================================================
fig, ax = new_fig(10, 9)
ax.set_facecolor(MAP_BG)

ax.set_title("Station Demand — Top Stations by Ride Volume\n"
             "(hexbin = all ride density · bubbles = top 60 stations · color = casual share)",
             fontsize=13, fontweight="bold", pad=10)
ax.set_xlim(MAP_LNG_MIN, MAP_LNG_MAX)
ax.set_ylim(MAP_LAT_MIN, MAP_LAT_MAX)

# Hexbin background
ax.hexbin(df["start_lng"], df["start_lat"],
          gridsize=50, cmap="YlOrRd", mincnt=1,
          extent=(MAP_LNG_MIN, MAP_LNG_MAX, MAP_LAT_MIN, MAP_LAT_MAX),
          alpha=0.40, linewidths=0, zorder=1)

# Top 60 bubble layer
top60 = station_df.nlargest(60, "total")
cmap_mc = LinearSegmentedColormap.from_list("mc", [MEMBER_COLOR, CASUAL_COLOR])
sizes60 = (top60["total"] / station_df["total"].max()) * 320 + 20
sc = ax.scatter(top60["lng"], top60["lat"], s=sizes60,
                c=top60["casual"] / top60["total"],
                cmap=cmap_mc, vmin=0, vmax=0.5,
                alpha=0.90, linewidths=0.6, edgecolors="#ffffff", zorder=3)

cbar = plt.colorbar(sc, ax=ax, shrink=0.6, pad=0.02, aspect=22)
cbar.set_label("Member  ←→  Casual rider share", fontsize=9)
cbar.set_ticks([0, 0.25, 0.5])
cbar.set_ticklabels(["0% (all member)", "25%", "50%+ casual"])
cbar.ax.tick_params(labelsize=8)

# Top 10 labels
for _, row in station_df.nlargest(10, "total").iterrows():
    short = row["start_station_name"].split("&")[0].strip()[:18]
    ax.annotate(short, xy=(row["lng"], row["lat"]),
                xytext=(6, 4), textcoords="offset points",
                fontsize=7, color="#111111", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.18", fc="white", alpha=0.85, lw=0), zorder=5)

# Size legend
for vol, lbl in [(station_df["total"].max(), "High vol."),
                 (int(station_df["total"].quantile(0.75)), "Med vol.")]:
    ax.scatter([], [], s=(vol/station_df["total"].max())*320+20,
               c="#888888", alpha=0.7, label=lbl)
ax.legend(fontsize=8, loc="lower left", framealpha=0.9,
          title="Station volume", title_fontsize=8)

ax.set_xlabel("Longitude", fontsize=10)
ax.set_ylabel("Latitude",  fontsize=10)
ax.tick_params(labelsize=9)
fig.text(0.5, 0.01, "Data: Citi Bike System Data (Jan 2025) · Colorblind-safe Okabe-Ito palette",
         ha="center", fontsize=8, color="#999999")
save(fig, "fig1_station_demand.png")

# =============================================================================
# FIG 2 – Cross-Neighborhood Flow Map
# =============================================================================
fig, ax = new_fig(10, 9)
ax.set_facecolor(MAP_BG)

ax.set_title("Top 20 Cross-Neighborhood Corridors\n"
             "(arc weight = trip volume · neighborhood cells ≈ 1.5km²)",
             fontsize=13, fontweight="bold", pad=10)
ax.set_xlim(MAP_LNG_MIN, MAP_LNG_MAX)
ax.set_ylim(MAP_LAT_MIN, MAP_LAT_MAX)

# Background station dots
ax.scatter(station_df["lng"], station_df["lat"],
           s=2, color="#AACBE8", alpha=0.25, zorder=1, linewidths=0)

max_trips = od["trips"].max() if len(od) > 0 else 1
for _, row in od.iterrows():
    t_norm = row["trips"] / max_trips
    lw     = 1.0 + t_norm * 7
    alpha  = 0.45 + t_norm * 0.50
    x0, y0 = row["start_lng"], row["start_lat"]
    x1, y1 = row["end_lng"],   row["end_lat"]
    dx, dy  = x1 - x0, y1 - y0
    mx = (x0 + x1) / 2 - dy * 0.3
    my = (y0 + y1) / 2 + dx * 0.3
    t_v = np.linspace(0, 1, 60)
    bx = (1-t_v)**2*x0 + 2*(1-t_v)*t_v*mx + t_v**2*x1
    by = (1-t_v)**2*y0 + 2*(1-t_v)*t_v*my + t_v**2*y1
    ax.plot(bx, by, color=FLOW_COLOR, lw=lw, alpha=alpha, solid_capstyle="round", zorder=2)
    ax.scatter(x0, y0, s=50, color=MEMBER_COLOR, zorder=4, alpha=0.95, linewidths=0)
    ax.scatter(x1, y1, s=50, color=CASUAL_COLOR,  zorder=4, alpha=0.95, linewidths=0)

ax.legend(handles=[
    mlines.Line2D([], [], color=MEMBER_COLOR, marker='o', linestyle='None', markersize=7, label="Origin cell"),
    mlines.Line2D([], [], color=CASUAL_COLOR, marker='o', linestyle='None', markersize=7, label="Destination cell"),
    mlines.Line2D([], [], color=FLOW_COLOR, linewidth=3, label="Flow arc (width = volume)"),
], fontsize=9, loc="lower right", framealpha=0.9)

ax.set_xlabel("Longitude", fontsize=10)
ax.set_ylabel("Latitude",  fontsize=10)
ax.tick_params(labelsize=9)
fig.text(0.5, 0.01, "Data: Citi Bike System Data (Jan 2025) · Colorblind-safe Okabe-Ito palette",
         ha="center", fontsize=8, color="#999999")
save(fig, "fig2_flow_corridors.png")

# =============================================================================
# FIG 3 – Rideable Type Mix
# =============================================================================
fig, ax = new_fig(10, 7)

ax.set_title("Rideable Type Mix — Top 15 Stations by Volume\n(classic vs electric bikes)",
             fontsize=13, fontweight="bold", pad=10)

top15 = station_df.nlargest(15, "total").sort_values("total")
labels = [n[:30] for n in top15["start_station_name"]]
y = np.arange(len(labels))

ax.barh(y, top15["classic"],  color=CLASSIC_COLOR, alpha=0.85, label="Classic bike")
ax.barh(y, top15["electric"], left=top15["classic"],
        color=ELEC_COLOR, alpha=0.85, label="Electric bike")

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Number of rides", fontsize=10)
ax.legend(fontsize=10, loc="lower right")
ax.tick_params(axis="x", labelsize=9)
ax.xaxis.grid(True, color="#DDDDDD", linewidth=0.6)
ax.set_axisbelow(True)
fig.text(0.5, 0.01, "Data: Citi Bike System Data (Jan 2025) · Colorblind-safe Okabe-Ito palette",
         ha="center", fontsize=8, color="#999999")
fig.tight_layout(rect=[0, 0.03, 1, 1])
save(fig, "fig3_rideable_type_mix.png")

# =============================================================================
# FIG 4 – Day × Hour Heatmap
# =============================================================================
fig, ax = new_fig(10, 6)

ax.set_title("Ride Volume Heatmap\n(day of week × hour of day)",
             fontsize=13, fontweight="bold", pad=10)

heat_cmap = LinearSegmentedColormap.from_list(
    "heat", ["#FFFFFF", "#FFF3CD", "#FFB347", MEMBER_COLOR])

avail_days  = [d for d in dow_order if d in pivot.index]
heat_matrix = pivot.loc[avail_days].values if avail_days else pivot.values
display_days= avail_days if avail_days else list(pivot.index)

im = ax.imshow(heat_matrix, aspect="auto", cmap=heat_cmap, interpolation="nearest")
ax.set_yticks(range(len(display_days)))
ax.set_yticklabels(display_days, fontsize=10)
ax.set_xticks(range(0, 24, 3))
ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 3)], fontsize=9, rotation=30)
ax.set_xlabel("Hour of Day", fontsize=10)

for x_start, x_end, label in [(7, 10, "AM\nPeak"), (16, 19, "PM\nPeak")]:
    ax.axvline(x=x_start - 0.5, color="#CC0000", lw=1.2, linestyle="--", alpha=0.7)
    ax.axvline(x=x_end   - 0.5, color="#CC0000", lw=1.2, linestyle="--", alpha=0.7)
    ax.text((x_start + x_end) / 2 - 0.5, -0.8, label,
            ha="center", va="top", fontsize=8, color="#CC0000")

cbar = plt.colorbar(im, ax=ax, shrink=0.9, pad=0.02)
cbar.set_label("Ride count", fontsize=9)
cbar.ax.tick_params(labelsize=8)

fig.text(0.5, 0.01, "Data: Citi Bike System Data (Jan 2025) · Colorblind-safe Okabe-Ito palette",
         ha="center", fontsize=8, color="#999999")
fig.tight_layout(rect=[0, 0.03, 1, 1])
save(fig, "fig4_heatmap.png")

# =============================================================================
# FIG 5 – Summary Statistics
# =============================================================================
fig, ax = new_fig(14, 4)
ax.set_title("Dataset Summary & Key Descriptive Statistics",
             fontsize=14, fontweight="bold", pad=10)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

total_rides = len(df)
member_pct  = (df["member_casual"] == "member").mean() * 100
casual_pct  = 100 - member_pct
elec_pct    = (df["rideable_type"] == "electric_bike").mean() * 100
classic_pct = 100 - elec_pct
med_dur     = df["duration_min"].median()
n_stations  = df["start_station_name"].nunique()
peak_hour   = int(df["hour"].value_counts().idxmax())
busiest_sta = df["start_station_name"].value_counts().idxmax()

stats = [
    ("Total Rides",     f"{total_rides:,}"),
    ("Unique Stations", f"{n_stations:,}"),
    ("Member Rides",    f"{member_pct:.0f}%"),
    ("Casual Rides",    f"{casual_pct:.0f}%"),
    ("Electric Bikes",  f"{elec_pct:.0f}%"),
    ("Classic Bikes",   f"{classic_pct:.0f}%"),
    ("Median Duration", f"{med_dur:.1f} min"),
    ("Peak Hour",       f"{peak_hour:02d}:00"),
    ("Busiest Station", busiest_sta[:20]),
]

n  = len(stats)
xs = np.linspace(0.05, 0.95, n)

for i in range(n - 1):
    mid = (xs[i] + xs[i+1]) / 2
    ax.plot([mid, mid], [0.15, 0.90], color="#DDDDDD", lw=1.2,
            transform=ax.transAxes)

for i, (label, val) in enumerate(stats):
    ax.text(xs[i], 0.72, val,   ha="center", va="bottom", fontsize=16,
            fontweight="bold", color=MEMBER_COLOR, transform=ax.transAxes)
    ax.text(xs[i], 0.38, label, ha="center", va="bottom", fontsize=10,
            color="#555555", transform=ax.transAxes)

ax.text(0.5, 0.04,
    "Data: Citi Bike System Data (tripdata.s3.amazonaws.com)  ·  "
    "Jan 2025 · 3 monthly files · ~2.1M rides  ·  Colorblind-safe Okabe-Ito palette",
    ha="center", va="bottom", fontsize=8.5, color="#999999", transform=ax.transAxes)

fig.tight_layout(rect=[0, 0, 1, 1])
save(fig, "fig5_summary_stats.png")

print("\n✓ All 5 figures saved in the current directory.")