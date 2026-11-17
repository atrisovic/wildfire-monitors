"""Figure 1: wildfire smoke exposure vs. the USEPA PM2.5 monitoring network.

A  Average annual smoke days, with regulatory (88101) and AQI-only (88502) sites
B  Average annual high-pollution days, same sites
C  Priority score (mean wildfire PM2.5 x share of regional population x distance
   to the nearest regulatory or AQI-only site), top-10 tracts outlined and ranked
D  Share of smoke person-days, non-smoke high-pollution person-days (definition b),
   and residents
   beyond each distance from the nearest regulatory site
E  Share of smoke person-days >25 km from the nearest regulatory site (filled)
   and from the nearest regulatory or AQI-only site (open), by state

Network definitions and the site rule live in load.py; all metrics come from analysis.py.
Run via run_all.py, or directly: python figure1.py
"""
import os

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize, PowerNorm
from matplotlib.lines import Line2D

from config import CACHE_DIR, FIGURE_DIR, STATES_SHP_PATH
from analysis import build, share_beyond, state_share_beyond
from load import STATES

OUT = os.path.join(FIGURE_DIR, "figure1")
THRESHOLDS = [10, 25, 50]

plt.rcParams.update({
    "font.family": "Times New Roman",
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 1.5,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
})
FIG_W = 7.0          # EHP full-page width, inches; layout below is in absolute inches
MIN_PT = 8           # smallest allowed text size at final size
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
AQI_C = "#c2185b"
SMOKE_C, HIGHPM_C, RES_C = "#2a78d6", "#eb6834", "#6b6a66"
# single-hue green, capped at a medium tone so black/magenta site markers stay visible
DAYS_RAMP = LinearSegmentedColormap.from_list("green", [
    "#f5faf2", "#dcefd4", "#b9e0ad", "#8ccb85", "#5fb26a", "#3a9459", "#237a4b"])
ORANGE_RAMP = LinearSegmentedColormap.from_list("orange", [
    "#fdf1ea", "#fbd3bd", "#f6a77f", "#eb6834", "#c24c1b", "#8a3210"])

# --------------------------------------------------------------------- data
tracts, sites = build()
reg_sites, aqi_sites = sites[sites.regulatory], sites[~sites.regulatory]
# plotting copy with outlines simplified to 300 m (1 pt at print size is ~12 km),
# which keeps the PDF fully vector at a manageable size; analysis uses full geometry
map_tracts = tracts.copy()
map_tracts["geometry"] = tracts.geometry.simplify(300, preserve_topology=True)

states = gpd.read_file(STATES_SHP_PATH)
states = states[states["STUSPS"].isin(STATES)].to_crs(tracts.crs)
STATE_NAMES = dict(zip(states["STUSPS"], states["NAME"]))

xs = np.linspace(0, 100, 401)
MEASURES = {
    "Smoke person-days": ("smoke_pd", SMOKE_C),
    "Residents": ("POPULATION", RES_C),
    "Non-smoke high-pollution person-days": ("nonsmoke_b_pd", HIGHPM_C),
}

# Panel C: top-10 priority tracts (distance to nearest regulatory or AQI-only site)
top10 = tracts.sort_values("priority_all", ascending=False).head(10).copy()
top10["rank"] = range(1, 11)
top10["county"] = top10.index.str[:5]

# Panel E: share of each state's smoke person-days >25 km from a site (same function as table1)
by_state = state_share_beyond(tracts).rename(columns={
    "smoke_pd_beyond_25km_reg_pct": "reg", "smoke_pd_beyond_25km_all_pct": "all"}).sort_values("reg")

print(f"sites: {len(reg_sites)} regulatory + {len(aqi_sites)} AQI-only = {len(sites)}")
for t in THRESHOLDS:
    v = {k: share_beyond(tracts, c, "dist_reg", t) for k, (c, _) in MEASURES.items()}
    print(f"regulatory >{t} km: smoke {v['Smoke person-days']:.1f}% | "
          f"non-smoke high-pollution (b) {v['Non-smoke high-pollution person-days']:.1f}% | "
          f"residents {v['Residents']:.1f}%")
print("Smoke person-days >25 km, % by state (regulatory / regulatory + AQI-only):")
print(by_state[["reg", "all"]].round(1).sort_values("reg", ascending=False).to_string())


# --------------------------------------------------------------------- plot
def style_cbar(cb, label):
    cb.set_label(label, color=INK_2)
    cb.outline.set_linewidth(0.3)
    cb.ax.tick_params(width=0.3, length=2, colors=INK_2)


def draw_map(ax, col, cmap, norm, title):
    map_tracts.plot(column=col, ax=ax, cmap=cmap, norm=norm, linewidth=0)
    states.boundary.plot(ax=ax, linewidth=0.35, color=MUTED)
    # baseline of the title's last line sits 2 pt above the map (set_title would add the
    # PM2.5 subscript's descent as extra white space)
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 2),
                textcoords="offset points", ha="left", va="baseline",
                fontsize=plt.rcParams["axes.titlesize"], fontweight="bold")
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)


def add_sites(ax):
    reg_sites.plot(ax=ax, marker="^", facecolor="none", edgecolor=INK,
                   markersize=7, linewidth=0.45, zorder=3)
    aqi_sites.plot(ax=ax, marker="o", facecolor="none", edgecolor=AQI_C,
                   markersize=7, linewidth=0.55, zorder=3)


def style_axes(ax, grid_axis):
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_linewidth(0.4)
        ax.spines[sp].set_color(MUTED)
    ax.tick_params(width=0.4, length=2, colors=INK_2)
    ax.grid(axis=grid_axis, linewidth=0.3, color="#e6e5e0")
    ax.set_axisbelow(True)


# ---- layout in inches (x from left, y from bottom) so text sizes are final sizes
x0b, y0b, x1b, y1b = states.total_bounds
padb = 0.01 * (x1b - x0b)
bx0, bx1, by0, by1 = x0b - padb, x1b + padb, y0b - padb, y1b + padb
aspect = (by1 - by0) / (bx1 - bx0)

L, R, GAP = 0.04, 0.04, 0.06
W_MAP = (FIG_W - L - R - 2 * GAP) / 3
H_MAP = W_MAP * aspect
H_BOT = 1.84                     # D/E height (20% shorter than before)
B_MARGIN, BOT_TITLE, MID_GAP = 0.42, 0.30, 0.10
CB_BLOCK, LEG_ROW, CB_H = 0.40, 0.20, 0.08
TOP_TITLE = 0.33   # two 9-pt title lines above the baseline
y_bot = B_MARGIN
y_cb = y_bot + H_BOT + BOT_TITLE + MID_GAP + CB_BLOCK
y_map = y_cb + CB_H + LEG_ROW
FIG_H = y_map + H_MAP + TOP_TITLE

fig = plt.figure(figsize=(FIG_W, FIG_H))


def ax_in(x, y, w, h):
    return fig.add_axes([x / FIG_W, y / FIG_H, w / FIG_W, h / FIG_H])


axA = ax_in(L, y_map, W_MAP, H_MAP)
axB = ax_in(L + W_MAP + GAP, y_map, W_MAP, H_MAP)
axP = ax_in(L + 2 * (W_MAP + GAP), y_map, W_MAP, H_MAP)
cax_AB = ax_in(L + 0.45 * W_MAP, y_cb, 1.1 * W_MAP + GAP, CB_H)
cax_P = ax_in(L + 2 * (W_MAP + GAP) + 0.12 * W_MAP, y_cb, 0.76 * W_MAP, CB_H)
D_X, D_W = 0.48, 2.72
E_X = 4.28
axC = ax_in(D_X, y_bot, D_W, H_BOT)
axD = ax_in(E_X, y_bot, FIG_W - E_X - 0.08, H_BOT)

# A, B: identical ramp and scale (square-root, 0-25 days/yr), one shared colorbar
days_norm = PowerNorm(gamma=0.5, vmin=0, vmax=25)
draw_map(axA, "smoke_days_per_year", DAYS_RAMP, days_norm,
         "A  Smoke days\n(wildfire PM$_{2.5}$ ≥5 µg/m³)")
draw_map(axB, "highpm_days_per_year", DAYS_RAMP, days_norm,
         "B  High-pollution days\n(all-source PM$_{2.5}$ ≥35 µg/m³)")
for ax in (axA, axB):
    add_sites(ax)
site_handles = [
    Line2D([], [], marker="^", ls="none", mfc="none", mec=INK, ms=4.5, mew=0.6,
           label="Regulatory (88101)"),
    Line2D([], [], marker="o", ls="none", mfc="none", mec=AQI_C, ms=4.5, mew=0.6,
           label="AQI-only (88502)"),
]
fig.legend(handles=site_handles, loc="lower center", ncol=2, frameon=False,
           bbox_to_anchor=((L + W_MAP + GAP / 2) / FIG_W, (y_cb + CB_H + 0.02) / FIG_H),
           handletextpad=0.2, columnspacing=1.2, borderaxespad=0)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=days_norm, cmap=DAYS_RAMP), cax=cax_AB,
                  orientation="horizontal", extend="max", ticks=[0, 1, 2, 5, 10, 15, 20, 25])
style_cbar(cb, "Average days per year, 2006–2020 (A and B)")

# C: priority score (all sites), top-10 tracts outlined; one label per county
prio_norm = Normalize(vmin=0, vmax=tracts["priority_all"].quantile(0.99))
draw_map(axP, "priority_all", ORANGE_RAMP, prio_norm, "C  Monitoring priority\n ")
add_sites(axP)
top10.boundary.plot(ax=axP, color=INK, linewidth=0.7, zorder=4)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=prio_norm, cmap=ORANGE_RAMP), cax=cax_P,
                  orientation="horizontal", extend="max")
style_cbar(cb, r"Priority score ($\times10^{-3}$)")
COUNTY_OFFSET = {"32013": (4, 14), "32027": (-2, -15), "32007": (15, 8), "06093": (-14, 9),
                 "06105": (-15, -6), "06035": (-4, -15), "30031": (13, 8)}
for county, grp in top10.groupby("county", sort=False):
    pt = grp.geometry.unary_union.representative_point()
    axP.annotate(", ".join(str(r) for r in sorted(grp["rank"])), (pt.x, pt.y),
                 xytext=COUNTY_OFFSET.get(county, (10, 6)), textcoords="offset points",
                 fontsize=MIN_PT, color=INK, fontweight="bold", ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.85),
                 arrowprops=dict(arrowstyle="-", lw=0.5, color=INK, shrinkA=0, shrinkB=0))

# D: share beyond each distance from the nearest regulatory site.
#    25 km values sit left of the 25 km line, right-aligned. Each label goes to the nearest
#    spot that touches no curve, searching above (smoke, non-smoke) or below (residents)
#    its own curve so the labels keep the curves' top-to-bottom order; a thin leader joins
#    label and dot when the label had to move.
curves = {k: share_beyond(tracts, col, "dist_reg", xs) for k, (col, _) in MEASURES.items()}
for label, (col, color) in MEASURES.items():
    axC.plot(xs, curves[label], color=color, linewidth=1.5, solid_capstyle="round")
for t in THRESHOLDS:
    axC.axvline(t, color=MUTED, linewidth=0.6, linestyle=(0, (2, 2)), zorder=0)
    axC.text(t + 1, 99, f"{t} km", color=INK_2, va="top")
axC.set_xlim(0, 100)
axC.set_ylim(0, 100)
renderer = fig.canvas.get_renderer()
LABEL_X, PAD = 24.0, 0.8
SEARCH_DIR = {"Smoke person-days": +1, "Residents": -1, "Non-smoke high-pollution person-days": +1}
placed = []
for label, (col, color) in MEASURES.items():
    v = share_beyond(tracts, col, "dist_reg", 25)
    axC.plot(25, v, "o", ms=3.5, mfc=color, mec="white", mew=0.6, zorder=4)
    txt = axC.text(LABEL_X, v, f"{v:.0f}%", ha="right", va="center", color=INK)
    bb = txt.get_window_extent(renderer).transformed(axC.transData.inverted())
    w, h = bb.width, bb.height
    x_box = xs[(xs >= LABEL_X - w) & (xs <= LABEL_X)]

    def clear(y):
        lo, hi = y - h / 2 - PAD, y + h / 2 + PAD
        if lo < 0 or hi > 100:
            return False
        if any(((np.interp(x_box, xs, c) >= lo) & (np.interp(x_box, xs, c) <= hi)).any()
               for c in curves.values()):
            return False
        return all(hi < plo or lo > phi for plo, phi in placed)

    step = 0.25 * SEARCH_DIR[label]
    y = next(yy for yy in np.arange(v, 50 + 50 * SEARCH_DIR[label], step) if clear(yy))
    txt.set_y(y)
    placed.append((y - h / 2, y + h / 2))
    if abs(y - v) > h / 2:
        axC.plot([LABEL_X + 0.3, 25], [y, v], color=color, linewidth=0.6, zorder=3)
axC.legend(handles=[Line2D([], [], color=c, lw=1.6, label=k) for k, (_, c) in MEASURES.items()],
           loc="upper right", bbox_to_anchor=(1, 0.88), frameon=False, handlelength=2.0)
axC.set_xlabel("Distance to nearest regulatory site (km)", color=INK_2)
axC.set_ylabel("Share beyond this distance (%)", color=INK_2)
axC.set_title("D  Exposure beyond the nearest regulatory site")
style_axes(axC, "y")

# E: by-state share of smoke person-days >25 km; filled = regulatory, open = regulatory + AQI-only
west_reg = share_beyond(tracts, "smoke_pd", "dist_reg", 25)
west_all = share_beyond(tracts, "smoke_pd", "dist_all", 25)
y = np.arange(len(by_state))
axD.axvline(west_reg, color=SMOKE_C, alpha=0.35, linewidth=0.9, zorder=0)
axD.axvline(west_all, color=SMOKE_C, alpha=0.35, linewidth=0.9, linestyle=(0, (2, 1.5)), zorder=0)
axD.hlines(y, by_state["all"], by_state["reg"], color="#b7d3f6", linewidth=2, zorder=1)
# open ring is larger and drawn first, so equal values show a filled dot inside the ring
axD.plot(by_state["all"], y, "o", ms=6.5, mfc="white", mec=SMOKE_C, mew=1.0, zorder=3)
axD.plot(by_state["reg"], y, "o", ms=4.2, mfc=SMOKE_C, mec=SMOKE_C, mew=0.8, zorder=4)
axD.set_yticks(y)
axD.set_yticklabels([STATE_NAMES[st] for st in by_state.index], color=INK)
axD.set_xlim(0, max(60, np.ceil(by_state["reg"].max() / 10) * 10))
axD.set_ylim(-0.6, len(by_state) + 0.25)   # headroom for the West-wide labels
axD.text(west_all - 0.6, len(by_state) - 0.05, f"West-wide {west_all:.0f}%", ha="right",
         va="center", color=INK_2)
axD.text(west_reg + 0.6, len(by_state) - 0.05, f"{west_reg:.0f}%", ha="left",
         va="center", color=INK_2)
axD.set_xlabel("Smoke person-days >25 km from nearest site (%)", color=INK_2)
axD.set_title("E  Smoke person-days >25 km from a site, by state")
e_handles = [
    Line2D([], [], marker="o", ls="none", ms=4.2, mfc=SMOKE_C, mec=SMOKE_C, label="Regulatory sites"),
    Line2D([], [], marker="o", ls="none", ms=6.5, mfc="white", mec=SMOKE_C, mew=1.0,
           label="Regulatory or AQI-only sites"),
]
axD.legend(handles=e_handles, loc="lower right", frameon=True, framealpha=1, edgecolor="none",
           borderpad=0.3, handletextpad=0.4)
style_axes(axD, "x")
axD.tick_params(axis="y", length=0)

# ---- check final text sizes
sizes = [t.get_fontsize() for t in fig.findobj(plt.Text) if t.get_text().strip()]
print(f"figure {FIG_W:.2f} x {FIG_H:.2f} in | smallest text {min(sizes):.1f} pt")
assert min(sizes) >= MIN_PT, "text below minimum size"

os.makedirs(FIGURE_DIR, exist_ok=True)
fig.savefig(OUT + ".pdf")                                                  # vector
fig.savefig(OUT + ".tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
fig.savefig(os.path.join(CACHE_DIR, "figure1_preview.png"), dpi=150)      # not committed
print("saved", OUT + ".pdf and", OUT + ".tiff")
