"""
Tie-Breaker Analysis: 118th U.S. Congress
CSC240 Final Project – Aiden Hughes, Mahathir Khan, Shafayet Fahim

Generates 10 visualizations from Voteview HS118 data files.
Run from any directory; set DATA_DIR below to point at your CSVs.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore")
matplotlib.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight"})

# ─────────────────────────── CONFIG ────────────────────────────────────────
DATA_DIR   = "C:/Users/mahat/OneDrive/Desktop/Csc240_Proj/Data"          # path to CSV files
OUT_DIR    = "C:/Users/mahat/OneDrive/Desktop/Csc240_Proj/Data/Outputs"          # where PNGs are saved
CHAMBER    = "House"                           # "House" or "Senate" – avoids
                                               # cross-contamination by shared
                                               # roll-numbers across chambers
CLOSE_PCT  = 10                                # bottom N-th percentile = close vote
PARTY_LINE = 0.90                              # fraction voting together → party-line

PARTY_COLORS  = {100: "#3b6dbf", 200: "#c0392b", "Other": "#7f8c8d"}
PARTY_LABELS  = {100: "Democrat", 200: "Republican"}
BLUE, RED     = PARTY_COLORS[100], PARTY_COLORS[200]

os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────── 1. LOAD DATA ──────────────────────────────────
print("Loading CSVs …")
members   = pd.read_csv(os.path.join(DATA_DIR, "HS118_members.csv"))
rollcalls = pd.read_csv(os.path.join(DATA_DIR, "HS118_rollcalls.csv"))
votes_raw = pd.read_csv(os.path.join(DATA_DIR, "HS118_votes.csv"))

# Filter to chosen chamber so roll-numbers are unambiguous
members_ch   = members[members["chamber"]   == CHAMBER].copy()
rollcalls_ch = rollcalls[rollcalls["chamber"] == CHAMBER].copy()
votes_raw_ch = votes_raw[votes_raw["chamber"]  == CHAMBER].copy()

# ─────────────────────────── 2. MERGE ──────────────────────────────────────
print("Merging …")
# Keep only Yea (1) and Nay (6) – skip absences, present, etc.
votes_yn = votes_raw_ch[votes_raw_ch["cast_code"].isin([1, 6])].copy()

df = (votes_yn
      .merge(members_ch[["icpsr", "bioname", "party_code",
                          "state_abbrev", "nominate_dim1"]],
             on="icpsr", how="inner")
      .merge(rollcalls_ch[["rollnumber", "yea_count", "nay_count",
                            "vote_result", "vote_question", "date"]],
             on="rollnumber", how="inner"))

df["date"] = pd.to_datetime(df["date"], errors="coerce")

# ─────────────────────────── 3. FEATURE ENGINEERING ───────────────────────
print("Engineering features …")

# --- Margin & close-vote flag ---
rollcalls_ch["margin"] = (rollcalls_ch["yea_count"] - rollcalls_ch["nay_count"]).abs()
close_threshold = np.percentile(rollcalls_ch["margin"].dropna(), CLOSE_PCT)
close_rolls = set(
    rollcalls_ch.loc[rollcalls_ch["margin"] <= close_threshold, "rollnumber"]
)
# Blowout = top 50 % margin
blowout_threshold = np.percentile(rollcalls_ch["margin"].dropna(), 50)
blowout_rolls = set(
    rollcalls_ch.loc[rollcalls_ch["margin"] >= blowout_threshold, "rollnumber"]
)

df["is_close"]   = df["rollnumber"].isin(close_rolls)
df["is_blowout"] = df["rollnumber"].isin(blowout_rolls)

# --- Party majority per roll call ---
party_majority = (
    df[df["party_code"].isin([100, 200])]
    .groupby(["rollnumber", "party_code"])["cast_code"]
    .agg(lambda x: 1 if (x == 1).mean() >= 0.5 else 6)
    .reset_index()
    .rename(columns={"cast_code": "party_majority_vote"})
)
df = df.merge(party_majority, on=["rollnumber", "party_code"], how="left")

# --- Defection flag (vote against party majority) ---
df["defected"] = df["cast_code"] != df["party_majority_vote"]

# --- Per-member loyalty stats ---
mem_stats = (
    df[df["party_code"].isin([100, 200])]
    .groupby(["icpsr", "bioname", "party_code", "state_abbrev", "nominate_dim1"])
    .agg(
        total_votes      = ("rollnumber", "count"),
        defections       = ("defected",   "sum"),
        close_votes      = ("is_close",   "sum"),
        close_defections = ("defected",   lambda x: x[df.loc[x.index, "is_close"]].sum()),
        blowout_defections = ("defected", lambda x: x[df.loc[x.index, "is_blowout"]].sum()),
        blowout_votes    = ("is_blowout", "sum"),
    )
    .reset_index()
)
mem_stats["loyalty_pct"]         = 1 - mem_stats["defections"]        / mem_stats["total_votes"]
mem_stats["close_defect_pct"]    = mem_stats["close_defections"]       / mem_stats["close_votes"].clip(lower=1)
mem_stats["blowout_loyalty_pct"] = 1 - mem_stats["blowout_defections"] / mem_stats["blowout_votes"].clip(lower=1)

# Tie-breaker score = fraction of close votes where member defected
# (require at least 5 close votes to qualify)
tiebreakers = mem_stats[mem_stats["close_votes"] >= 5].copy()
tiebreakers = tiebreakers.sort_values("close_defect_pct", ascending=False)
top15 = tiebreakers.head(15)
top10 = tiebreakers.head(10)

# --- Party-line roll calls ---
# A roll call is "party-line" if ≥ PARTY_LINE of each major party voted together
party_unity_rc = (
    df[df["party_code"].isin([100, 200])]
    .groupby(["rollnumber", "party_code"])["cast_code"]
    .agg(lambda x: max((x == 1).mean(), (x == 6).mean()))
    .reset_index()
    .rename(columns={"cast_code": "unity"})
)
party_unity_rc = party_unity_rc.groupby("rollnumber")["unity"].min().reset_index()
party_unity_rc["party_line"] = party_unity_rc["unity"] >= PARTY_LINE
party_unity_rc = party_unity_rc.merge(
    rollcalls_ch[["rollnumber"]].assign(order=lambda x: x["rollnumber"]),
    on="rollnumber"
)

# Rolling 50-vote window party-line %
party_unity_rc = party_unity_rc.sort_values("rollnumber")
party_unity_rc["rolling_pl"] = (
    party_unity_rc["party_line"].rolling(50, min_periods=10).mean() * 100
)

# --- Win side flag ---
df["won"] = df["vote_result"].str.lower().isin(["passed", "agreed to", "amendment agreed to"])
df["on_winning_side"] = (
    ((df["cast_code"] == 1) &  df["won"]) |
    ((df["cast_code"] == 6) & ~df["won"])
)

# Success rate among close defectors (top 15)
top15_icpsr = set(top15["icpsr"])
close_defect_df = df[(df["is_close"]) & (df["icpsr"].isin(top15_icpsr)) & df["defected"]]
success_rate = (
    close_defect_df.groupby("icpsr")["on_winning_side"].mean().reset_index()
    .merge(mem_stats[["icpsr", "bioname"]], on="icpsr")
    .sort_values("on_winning_side", ascending=False)
)

# Last-name label helper
def short_name(n):
    parts = str(n).split(",")
    return parts[0].title() if parts else str(n)

# ─────────────────────────── 4. PLOTS ──────────────────────────────────────

# ── Plot 1: Vote Margin Distribution ────────────────────────────────────────
print("Plot 1 …")
fig, ax = plt.subplots(figsize=(10, 5))
margins = rollcalls_ch["margin"].dropna()
ax.hist(margins, bins=60, color="#4a90d9", edgecolor="white", linewidth=0.4, alpha=0.85)
ax.axvline(close_threshold, color="crimson", linewidth=2,
           linestyle="--", label=f"Close-vote threshold (≤{close_threshold:.0f})")
ax.set_xlabel("Absolute Margin (|Yea – Nay|)", fontsize=12)
ax.set_ylabel("Number of Roll Calls", fontsize=12)
ax.set_title(f"Plot 1 · Vote Margin Distribution\n{CHAMBER}, 118th Congress", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot1_margin_distribution.png"))
plt.close()

# ── Plot 2: Party Loyalty vs. DW-NOMINATE Ideology ─────────────────────────
print("Plot 2 …")
fig, ax = plt.subplots(figsize=(10, 6))
for code, grp in mem_stats[mem_stats["party_code"].isin([100, 200])].groupby("party_code"):
    ax.scatter(grp["nominate_dim1"], grp["loyalty_pct"] * 100,
               color=PARTY_COLORS[code], alpha=0.55, s=28,
               label=PARTY_LABELS[code], edgecolors="none")
ax.axhline(90, color="grey", linestyle=":", linewidth=1.2, label="90 % loyalty line")
ax.set_xlabel("DW-NOMINATE Dimension 1\n(← Liberal  |  Conservative →)", fontsize=11)
ax.set_ylabel("Party Loyalty (%)", fontsize=11)
ax.set_title("Plot 2 · Party Loyalty vs. Ideological Position", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot2_loyalty_vs_ideology.png"))
plt.close()

# ── Plot 3: Top 15 Tie-Breakers ─────────────────────────────────────────────
print("Plot 3 …")
fig, ax = plt.subplots(figsize=(11, 6))
colors3 = [PARTY_COLORS[p] for p in top15["party_code"]]
bars = ax.barh(
    [short_name(n) for n in top15["bioname"]],
    top15["close_defect_pct"] * 100,
    color=colors3, edgecolor="white", linewidth=0.5
)
ax.invert_yaxis()
ax.set_xlabel("Cross-Party Vote Rate in Close Votes (%)", fontsize=11)
ax.set_title("Plot 3 · Top 15 Tie-Breakers\n(Highest % of Close Votes Cast Against Party Majority)",
             fontsize=13, fontweight="bold")
legend_els = [Line2D([0], [0], marker="s", color="w", markerfacecolor=BLUE, markersize=10, label="Democrat"),
              Line2D([0], [0], marker="s", color="w", markerfacecolor=RED,  markersize=10, label="Republican")]
ax.legend(handles=legend_els, fontsize=9)
for bar, val in zip(bars, top15["close_defect_pct"]):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            f"{val*100:.1f}%", va="center", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot3_top15_tiebreakers.png"))
plt.close()

# ── Plot 4: Party Unity Over Roll-Call Sequence ─────────────────────────────
print("Plot 4 …")
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(party_unity_rc["rollnumber"], party_unity_rc["rolling_pl"],
        color="#2c3e50", linewidth=1.8, label="Rolling 50-vote window")
ax.fill_between(party_unity_rc["rollnumber"], party_unity_rc["rolling_pl"],
                alpha=0.15, color="#2c3e50")
ax.set_ylim(0, 105)
ax.set_xlabel("Roll-Call Number (chronological proxy)", fontsize=11)
ax.set_ylabel("Party-Line Vote Rate (%)", fontsize=11)
ax.set_title("Plot 4 · Party Unity Over Time\n(Rolling % of votes where ≥90 % of each party agreed)",
             fontsize=13, fontweight="bold")
ax.axhline(50, color="grey", linestyle=":", linewidth=1, label="50 % reference")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot4_party_unity_over_time.png"))
plt.close()

# ── Plot 5: Tie-Breaker Voting-Similarity Heatmap ───────────────────────────
print("Plot 5 …")
top10_icpsr = list(top10["icpsr"])
top10_names = {r["icpsr"]: short_name(r["bioname"]) for _, r in top10.iterrows()}

pivot = (
    df[(df["icpsr"].isin(top10_icpsr)) & df["is_close"]]
    [["icpsr", "rollnumber", "cast_code"]]
    .pivot_table(index="rollnumber", columns="icpsr", values="cast_code", aggfunc="first")
)
# Agreement matrix: fraction of shared votes where both voted the same
agree_data = {}
for a in top10_icpsr:
    agree_data[a] = {}
    for b in top10_icpsr:
        if a in pivot.columns and b in pivot.columns:
            shared = pivot[[a, b]].dropna()
            if len(shared) > 0:
                eq = shared.iloc[:, 0] == shared.iloc[:, 1]  # avoid integer label ambiguity
                agree_data[a][b] = float(eq.mean())
            else:
                agree_data[a][b] = np.nan
        else:
            agree_data[a][b] = np.nan

agree = pd.DataFrame(agree_data, dtype=float)
agree.index   = [top10_names[i] for i in top10_icpsr]
agree.columns = [top10_names[i] for i in top10_icpsr]

fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(agree.astype(float), annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=0, vmax=1, linewidths=0.5, ax=ax,
            cbar_kws={"label": "Vote Agreement Rate"})
ax.set_title("Plot 5 · Voting Similarity Heatmap\nTop 10 Tie-Breakers on Close Votes",
             fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot5_tiebreaker_heatmap.png"))
plt.close()

# ── Plot 6: Ideological KDE (NOMINATE Dim 1) ────────────────────────────────
print("Plot 6 …")
fig, ax = plt.subplots(figsize=(10, 5))
for code in [100, 200]:
    subset = mem_stats[mem_stats["party_code"] == code]["nominate_dim1"].dropna()
    sns.kdeplot(subset, ax=ax, color=PARTY_COLORS[code],
                fill=True, alpha=0.35, linewidth=2, label=PARTY_LABELS[code])

# Mark tie-breakers on axis
for _, row in top15.iterrows():
    if pd.notna(row["nominate_dim1"]):
        ax.axvline(row["nominate_dim1"], color=PARTY_COLORS.get(row["party_code"], "grey"),
                   alpha=0.6, linewidth=1, linestyle=":")

ax.set_xlabel("DW-NOMINATE Dimension 1\n(← Liberal  |  Conservative →)", fontsize=11)
ax.set_ylabel("Density", fontsize=11)
ax.set_title("Plot 6 · Ideological Distribution (KDE)\nBoth Parties – Dotted Lines = Tie-Breakers",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot6_ideological_kde.png"))
plt.close()

# ── Plot 7: Tie-Breaker Success Rate ────────────────────────────────────────
print("Plot 7 …")
fig, ax = plt.subplots(figsize=(11, 5))
sr_top = success_rate.head(15).copy()
colors7 = [
    PARTY_COLORS.get(
        mem_stats.loc[mem_stats["icpsr"] == i, "party_code"].values[0], "grey"
    )
    for i in sr_top["icpsr"]
]
bars7 = ax.bar(
    [short_name(n) for n in sr_top["bioname"]],
    sr_top["on_winning_side"] * 100,
    color=colors7, edgecolor="white"
)
ax.set_xlabel("Representative", fontsize=11)
ax.set_ylabel("Win Rate (%)", fontsize=11)
ax.set_title("Plot 7 · Tie-Breaker Win Rate\n(% of Cross-Party Close Votes Where Member Was on the Winning Side)",
             fontsize=13, fontweight="bold")
ax.axhline(50, color="black", linestyle="--", linewidth=1, label="50 % baseline")
plt.xticks(rotation=45, ha="right", fontsize=8)
ax.legend(handles=legend_els + [Line2D([0],[0], color='black', linestyle='--', label='50% baseline')], fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot7_tiebreaker_success.png"))
plt.close()

# ── Plot 8: Average Margin by Vote Question Type ────────────────────────────
print("Plot 8 …")
vq_margin = (
    rollcalls_ch
    .dropna(subset=["vote_question", "margin"])
    .groupby("vote_question")["margin"]
    .agg(mean_margin="mean", count="count")
    .reset_index()
)
# Keep question types with at least 10 votes
vq_margin = vq_margin[vq_margin["count"] >= 10].sort_values("mean_margin", ascending=False)

fig, ax = plt.subplots(figsize=(12, 5))
bars8 = ax.bar(vq_margin["vote_question"], vq_margin["mean_margin"],
               color="#5b8dd9", edgecolor="white")
ax.set_xlabel("Vote Question Type", fontsize=11)
ax.set_ylabel("Average Absolute Margin", fontsize=11)
ax.set_title("Plot 8 · Average Vote Margin by Question Type\n(Higher margin = less contentious)",
             fontsize=13, fontweight="bold")
plt.xticks(rotation=40, ha="right", fontsize=9)
for bar, n in zip(bars8, vq_margin["count"]):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f"n={n}", ha="center", fontsize=7, color="grey")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot8_margin_by_question_type.png"))
plt.close()

# ── Plot 9: Geographic Concentration of Tie-Breakers ───────────────────────
print("Plot 9 …")
geo = (
    top15
    .groupby("state_abbrev")
    .agg(count=("icpsr", "count"))
    .reset_index()
    .sort_values("count", ascending=False)
)

fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(geo["state_abbrev"], geo["count"], color="#e67e22", edgecolor="white")
ax.set_xlabel("State", fontsize=11)
ax.set_ylabel("Number of Top-15 Tie-Breakers", fontsize=11)
ax.set_title("Plot 9 · Geographic Concentration of Tie-Breakers\n(Home states of the Top 15)",
             fontsize=13, fontweight="bold")
ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot9_geographic_concentration.png"))
plt.close()

# ── Plot 10: "Clutch" Factor – Blowout Loyalty vs. Close-Vote Loyalty ───────
print("Plot 10 …")
clutch = mem_stats[
    (mem_stats["party_code"].isin([100, 200])) &
    (mem_stats["close_votes"]   >= 5) &
    (mem_stats["blowout_votes"] >= 5)
].copy()

fig, ax = plt.subplots(figsize=(9, 7))
for code, grp in clutch.groupby("party_code"):
    ax.scatter(grp["blowout_loyalty_pct"] * 100, grp["loyalty_pct"] * 100,
               color=PARTY_COLORS[code], alpha=0.4, s=25,
               label=PARTY_LABELS[code], edgecolors="none")

# Highlight top 15 tie-breakers
for _, row in top15.iterrows():
    r = clutch[clutch["icpsr"] == row["icpsr"]]
    if not r.empty:
        ax.scatter(r["blowout_loyalty_pct"].values[0] * 100,
                   r["loyalty_pct"].values[0] * 100,
                   color=PARTY_COLORS.get(row["party_code"], "grey"),
                   s=90, edgecolors="black", linewidths=0.8, zorder=5)
        ax.annotate(short_name(row["bioname"]),
                    (r["blowout_loyalty_pct"].values[0] * 100,
                     r["loyalty_pct"].values[0] * 100),
                    fontsize=6.5, xytext=(3, 3), textcoords="offset points")

ax.plot([0, 100], [0, 100], "k--", linewidth=0.8, alpha=0.5, label="x = y (equal loyalty)")
ax.set_xlabel("Party Loyalty in Blowout Votes (%)", fontsize=11)
ax.set_ylabel("Overall Party Loyalty (%)", fontsize=11)
ax.set_title('Plot 10 · "Clutch" Factor\nBlowout Loyalty vs. Overall Loyalty'
             '\n(Annotated = Top-15 Tie-Breakers)',
             fontsize=13, fontweight="bold")
legend_els10 = [
    Line2D([0],[0], marker="o", color="w", markerfacecolor=BLUE, markersize=8, label="Democrat"),
    Line2D([0],[0], marker="o", color="w", markerfacecolor=RED,  markersize=8, label="Republican"),
    Line2D([0],[0], marker="o", color="w", markerfacecolor="grey", markersize=8,
           markeredgecolor="black", markeredgewidth=0.8, label="Top-15 Tie-Breaker"),
    Line2D([0],[0], color="black", linestyle="--", label="x = y"),
]
ax.legend(handles=legend_els10, fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "plot10_clutch_factor.png"))
plt.close()

print("\n✅  All 10 plots saved to:", OUT_DIR)
print(f"\nClose-vote threshold (bottom {CLOSE_PCT}th pct): margin ≤ {close_threshold:.0f} votes")
print(f"Number of close roll calls: {len(close_rolls)}")
print(f"\nTop 5 Tie-Breakers:")
print(top15[["bioname","party_code","close_votes","close_defect_pct"]].head().to_string(index=False))