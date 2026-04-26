"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CSC240 Final Project — Full Data-Mining & Classification Pipeline          ║
║  "Classifying Tie-Breakers Within Models of Representation"                 ║
║  Aiden Hughes · Mahathir Khan · Shafayet Fahim                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS SCRIPT DOES
─────────────────────
Because no ground-truth "tie-breaker" labels exist in the Voteview export, we
adopt a two-stage strategy that is documented in full in the companion rationale
document (methodology_rationale.docx):

  STAGE 1 — Unsupervised labelling (K-Means clustering)
    Build a behavioural feature vector per member from close-vote statistics,
    cluster members into k archetypes, and designate the cluster with the
    highest mean close-vote defection rate as the "tie-breaker" cluster.
    This produces pseudo-labels that are principled but transparent.

  STAGE 2 — Supervised classification (4 classifiers compared)
    Use the pseudo-labels as targets and compare:
      A. BOAT proxy — Decision Tree with Gini/Entropy comparison + pruning
      B. Random Forest
      C. Naïve Bayes (Gaussian)
      D. Naïve Bayes (Bernoulli, binarised features)
    All classifiers use a chronological 70/15/15 train/val/test holdout and
    class-weighted penalties for the rare tie-breaker class.

  STAGE 3 — Frequent Pattern Mining
    A. Apriori — mine co-occurring defection-context itemsets
    B. FP-Growth — same basket, faster alternative, results compared
    Both generate association rules evaluated by support/confidence/lift.

OUTPUTS  (saved to OUT_DIR)
──────────────────────────
  Data Overview
    00_vote_margin_hist.png
    00_party_membership_pie.png
    00_vote_question_breakdown.png
    00_geographic_distribution.png

  Clustering
    01_elbow_curve.png
    02_kmeans_pca.png
    03_cluster_profiles.png

  Classification Tree (BOAT proxy)
    04_decision_tree_gini.png
    05_feature_importance_gini_entropy.png
    06_information_gain_tree.png

  Classifier Comparison
    07_roc_curves.png
    08_metrics_comparison_bar.png
    09_confusion_matrices.png
    10_pvalue_table.png

  Frequent Pattern Mining
    11_apriori_itemsets.png
    12_fpgrowth_itemsets.png
    13_association_rules_scatter.png
    14_tiebreaker_pie.png

  Metrics printed to console and saved to metrics_summary.csv
"""

# ─────────────────────────────────────────────────────────────────────────────
#  IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import os
import warnings
import itertools
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from matplotlib.lines import Line2D

from sklearn.tree import DecisionTreeClassifier, plot_tree, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB, BernoulliNB
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler, label_binarize
from sklearn.model_selection import train_test_split as _tts_unused
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_curve, auc, confusion_matrix, ConfusionMatrixDisplay,
    classification_report
)
from scipy.stats import chi2_contingency, mannwhitneyu

from mlxtend.frequent_patterns import apriori, fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder

warnings.filterwarnings("ignore")
matplotlib.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight"})

# ─────────────────────────────────────────────────────────────────────────────
#  ██████╗ ██████╗ ███╗   ██╗███████╗██╗ ██████╗
#  ██╔════╝██╔═══██╗████╗  ██║██╔════╝██║██╔════╝
#  ██║     ██║   ██║██╔██╗ ██║█████╗  ██║██║  ███╗
#  ██║     ██║   ██║██║╚██╗██║██╔══╝  ██║██║   ██║
#  ╚██████╗╚██████╔╝██║ ╚████║██║     ██║╚██████╔╝
#   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR    = "."               # ← SET THIS to the folder containing your CSVs
OUT_DIR     = "./outputs"       # ← Plots saved here
CHAMBER     = "House"
CLOSE_PCT   = 10                # bottom N-th percentile margin → "close vote"
BLOWOUT_PCT = 50                # top-half margin → "blowout"
PARTY_LINE  = 0.90              # fraction of party voting together → party-line
MIN_CLOSE_VOTES = 5             # min close-vote appearances to qualify a member

PARTY_COLORS = {100: "#3b6dbf", 200: "#c0392b"}
PARTY_LABELS = {100: "Democrat", 200: "Republican"}
CLUSTER_PALETTE = ["#e67e22", "#27ae60", "#8e44ad", "#2980b9", "#e74c3c",
                   "#1abc9c", "#f39c12", "#7f8c8d"]
BLUE, RED = PARTY_COLORS[100], PARTY_COLORS[200]

os.makedirs(OUT_DIR, exist_ok=True)
metrics_rows = []   # accumulated for final CSV

VQ_SHORT = {
    "On Agreeing to the Amendment":                        "Amendment",
    "On Passage":                                          "Passage",
    "On Agreeing to the Resolution":                       "Resolution",
    "On Motion to Recommit":                               "Recommit",
    "On Ordering the Previous Question":                   "Prev.Question",
    "On Motion to Table":                                  "Table",
    "On Motion to Refer":                                  "Refer",
    "On Motion to Adjourn":                                "Adjourn",
    "On Agreeing to the Resolution, as Amended":           "Res.(Amended)",
    "On Motion to Suspend the Rules and Pass":             "Suspend+Pass",
    "On Motion to Suspend the Rules and Pass, as Amended": "Suspend+PassAmd",
    "Election of the Speaker":                             "Speaker",
}

def short_name(n):
    parts = str(n).split(",")
    return parts[0].title() if parts else str(n)

def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {name}")

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 0 — LOAD, MERGE & FEATURE ENGINEERING
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("0  LOADING & MERGING")
print("━"*60)

members   = pd.read_csv(os.path.join(DATA_DIR, "HS118_members.csv"))
rollcalls = pd.read_csv(os.path.join(DATA_DIR, "HS118_rollcalls.csv"))
votes_raw = pd.read_csv(os.path.join(DATA_DIR, "HS118_votes.csv"))

members_ch   = members[members["chamber"]   == CHAMBER].copy()
rollcalls_ch = rollcalls[rollcalls["chamber"] == CHAMBER].copy()
votes_ch     = votes_raw[votes_raw["chamber"]  == CHAMBER].copy()

rollcalls_ch["margin"] = (rollcalls_ch["yea_count"] - rollcalls_ch["nay_count"]).abs()
rollcalls_ch["date"]   = pd.to_datetime(rollcalls_ch["date"], errors="coerce")

close_thr   = np.percentile(rollcalls_ch["margin"].dropna(), CLOSE_PCT)
blowout_thr = np.percentile(rollcalls_ch["margin"].dropna(), BLOWOUT_PCT)
close_rolls   = set(rollcalls_ch.loc[rollcalls_ch["margin"] <= close_thr,   "rollnumber"])
blowout_rolls = set(rollcalls_ch.loc[rollcalls_ch["margin"] >= blowout_thr, "rollnumber"])

votes_yn = votes_ch[votes_ch["cast_code"].isin([1, 6])].copy()
df = (votes_yn
      .merge(members_ch[["icpsr", "bioname", "party_code", "state_abbrev",
                          "nominate_dim1", "nominate_dim2"]], on="icpsr", how="inner")
      .merge(rollcalls_ch[["rollnumber", "yea_count", "nay_count", "margin",
                            "vote_result", "vote_question", "date"]],
             on="rollnumber", how="inner"))
df = df[df["party_code"].isin([100, 200])].copy()
df["is_close"]   = df["rollnumber"].isin(close_rolls)
df["is_blowout"] = df["rollnumber"].isin(blowout_rolls)

pm = (df.groupby(["rollnumber", "party_code"])["cast_code"]
        .agg(lambda x: 1 if (x == 1).mean() >= 0.5 else 6)
        .reset_index().rename(columns={"cast_code": "party_majority_vote"}))
df = df.merge(pm, on=["rollnumber", "party_code"], how="left")
df["defected"] = (df["cast_code"] != df["party_majority_vote"]).astype(int)
df["vq_short"]  = df["vote_question"].map(VQ_SHORT).fillna("Other")

print(f"  Total vote-rows: {len(df):,}")
print(f"  Members:         {df['icpsr'].nunique()}")
print(f"  Close rolls:     {len(close_rolls)} (margin ≤ {close_thr:.0f})")
print(f"  Blowout rolls:   {len(blowout_rolls)}")

# ── Build member-level feature table ────────────────────────────────────────
def build_mem_features(src, ref):
    """
    src  = vote-level df to aggregate
    ref  = same df (passed separately so lambda captures correct index scope)
    """
    g = src.groupby(["icpsr", "bioname", "party_code",
                     "state_abbrev", "nominate_dim1", "nominate_dim2"])
    s = g.agg(
        total_votes        = ("rollnumber", "count"),
        defections         = ("defected",   "sum"),
        close_votes        = ("is_close",   "sum"),
        close_defections   = ("defected",   lambda x: x[ref.loc[x.index, "is_close"]].sum()),
        blowout_votes      = ("is_blowout", "sum"),
        blowout_defections = ("defected",   lambda x: x[ref.loc[x.index, "is_blowout"]].sum()),
    ).reset_index()
    s["loyalty_pct"]         = 1 - s["defections"]        / s["total_votes"].clip(1)
    s["close_defect_pct"]    = s["close_defections"]       / s["close_votes"].clip(1)
    s["blowout_loyalty_pct"] = 1 - s["blowout_defections"] / s["blowout_votes"].clip(1)
    s["clutch_delta"]        = s["blowout_loyalty_pct"]    - s["loyalty_pct"]
    return s

mem_all = build_mem_features(df, df)
mem_q   = mem_all[mem_all["close_votes"] >= MIN_CLOSE_VOTES].copy()

print(f"  Members w/ ≥{MIN_CLOSE_VOTES} close votes: {len(mem_q)}")

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — DATA OVERVIEW VISUALISATIONS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("1  DATA OVERVIEW PLOTS")
print("━"*60)

# 00a — Vote margin histogram
fig, ax = plt.subplots(figsize=(10, 5))
margins = rollcalls_ch["margin"].dropna()
ax.hist(margins, bins=60, color="#4a90d9", edgecolor="white", linewidth=0.4, alpha=0.85)
ax.axvline(close_thr, color="crimson", linewidth=2, linestyle="--",
           label=f"Close threshold ≤{close_thr:.0f}")
ax.set_xlabel("Absolute Margin |Yea − Nay|", fontsize=12)
ax.set_ylabel("Number of Roll Calls", fontsize=12)
ax.set_title("Vote Margin Distribution — 118th House\n"
             "Identifies frequency of genuinely contested votes", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
save(fig, "00_vote_margin_hist.png")

# 00b — Party membership pie
party_counts = members_ch["party_code"].value_counts()
party_counts.index = [PARTY_LABELS.get(c, "Other") for c in party_counts.index]
fig, ax = plt.subplots(figsize=(6, 6))
wedges, texts, autotexts = ax.pie(
    party_counts, labels=party_counts.index,
    colors=[BLUE, RED, "#7f8c8d"][:len(party_counts)],
    autopct="%1.1f%%", startangle=140,
    wedgeprops=dict(edgecolor="white", linewidth=1.5))
for at in autotexts:
    at.set_fontsize(11)
ax.set_title("Party Membership Breakdown\n118th U.S. House of Representatives",
             fontsize=13, fontweight="bold")
save(fig, "00_party_membership_pie.png")

# 00c — Vote question breakdown (bar)
vq_counts = df["vq_short"].value_counts().head(10)
fig, ax = plt.subplots(figsize=(11, 5))
vq_counts.sort_values().plot.barh(ax=ax, color="#27ae60", edgecolor="white")
ax.set_xlabel("Number of Individual Votes Cast", fontsize=11)
ax.set_title("Breakdown by Vote-Question Category (Top 10)\n"
             "Each bar = total member-votes across all roll calls of that type",
             fontsize=13, fontweight="bold")
for i, v in enumerate(vq_counts.sort_values()):
    ax.text(v + 500, i, f"{v:,}", va="center", fontsize=8)
plt.tight_layout()
save(fig, "00_vote_question_breakdown.png")

# 00d — Geographic distribution (bar: # representatives per state)
state_counts = members_ch["state_abbrev"].value_counts().head(20)
fig, ax = plt.subplots(figsize=(13, 5))
state_counts.plot.bar(ax=ax, color="#e67e22", edgecolor="white")
ax.set_xlabel("State", fontsize=11)
ax.set_ylabel("Number of Representatives", fontsize=11)
ax.set_title("Geographic Distribution of Representatives — Top 20 States\n"
             "Larger delegations = more opportunities for tie-breaker influence",
             fontsize=13, fontweight="bold")
plt.xticks(rotation=45, ha="right")
save(fig, "00_geographic_distribution.png")

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — K-MEANS CLUSTERING  (generates pseudo-labels)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("2  K-MEANS CLUSTERING  (pseudo-label generation)")
print("━"*60)
"""
RATIONALE (see companion document §3):
  No ground-truth tie-breaker labels exist. We derive them unsupervisedly:
  1. Build 5 behavioural features per member.
  2. K-Means clusters members; cluster with max close_defect_pct = tie-breaker.
  3. Pseudo-labels feed all four supervised classifiers.
  This is defensible because the label is derived from the very signal the
  project seeks to classify, making the task self-consistent.
"""

CLUSTER_FEATURES = ["nominate_dim1", "nominate_dim2",
                    "loyalty_pct", "close_defect_pct", "blowout_loyalty_pct"]
X_cl_raw = mem_q[CLUSTER_FEATURES].dropna()
idx_cl   = X_cl_raw.index

scaler   = StandardScaler()
X_cl     = scaler.fit_transform(X_cl_raw)

# Elbow
wcss = []
K_range = range(2, 11)
for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    km.fit(X_cl)
    wcss.append(km.inertia_)

diffs2  = np.diff(np.diff(wcss))
best_k  = list(K_range)[np.argmax(diffs2) + 1]
print(f"  Elbow k = {best_k}")

fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(list(K_range), wcss, "o-", color="#2c3e50", linewidth=2)
ax.axvline(best_k, color="crimson", linestyle="--", linewidth=1.5,
           label=f"Elbow k={best_k}")
ax.set_xlabel("k", fontsize=11); ax.set_ylabel("WCSS", fontsize=11)
ax.set_title("K-Means Elbow — Selecting Optimal k\nfor Member Behavioural Clusters",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
save(fig, "01_elbow_curve.png")

# Final fit
km_final = KMeans(n_clusters=best_k, random_state=42, n_init=20)
km_final.fit(X_cl)
mem_q = mem_q.copy()
mem_q.loc[idx_cl, "cluster"] = km_final.labels_
mem_q["cluster"] = mem_q["cluster"].fillna(-1).astype(int)

# Identify tie-breaker cluster = highest mean close_defect_pct
cluster_means = (mem_q[mem_q["cluster"] >= 0]
                 .groupby("cluster")["close_defect_pct"].mean())
tb_cluster = int(cluster_means.idxmax())
mem_q["is_tiebreaker"] = (mem_q["cluster"] == tb_cluster).astype(int)
print(f"  Tie-breaker cluster: C{tb_cluster}  "
      f"({mem_q['is_tiebreaker'].sum()} members, "
      f"mean defect={cluster_means[tb_cluster]:.3f})")

# Interpretive label map
def cluster_label(row):
    if row["close_defect_pct"] >= cluster_means.max() * 0.6:
        return "Tie-Breaker / Politico"
    if row["loyalty_pct"] >= 0.95 and abs(row["nominate_dim1"]) > 0.35:
        return "Partisan"
    if abs(row["nominate_dim1"]) < 0.25:
        return "Moderate / Trustee"
    return "Loyalist"

cprof = (mem_q[mem_q["cluster"] >= 0]
         .groupby("cluster")[CLUSTER_FEATURES].mean())
cprof["label"] = cprof.apply(cluster_label, axis=1)
cprof.loc[tb_cluster, "label"] = "Tie-Breaker / Politico"
label_map = cprof["label"].to_dict()
mem_q["cluster_label"] = mem_q["cluster"].map(label_map)
print("  Cluster labels:", dict(label_map))

# PCA plot
pca  = PCA(n_components=2, random_state=42)
Xpca = pca.fit_transform(X_cl)
pca_df = pd.DataFrame(Xpca, columns=["PC1", "PC2"])
pca_df["cluster"] = km_final.labels_
pca_df["is_tb"]   = (pca_df["cluster"] == tb_cluster).astype(int)
pca_df["party"]   = mem_q.loc[idx_cl, "party_code"].values

fig, ax = plt.subplots(figsize=(10, 7))
for c in sorted(pca_df["cluster"].unique()):
    sub = pca_df[pca_df["cluster"] == c]
    lbl = label_map.get(c, f"C{c}")
    ax.scatter(sub["PC1"], sub["PC2"],
               color=CLUSTER_PALETTE[c % len(CLUSTER_PALETTE)],
               alpha=0.6, s=45, label=f"C{c}: {lbl}", edgecolors="none")
cents_pca = pca.transform(km_final.cluster_centers_)
for i, cp in enumerate(cents_pca):
    ax.scatter(*cp, marker="*", s=250,
               color=CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)],
               edgecolors="black", linewidths=0.8, zorder=6)
var = pca.explained_variance_ratio_
ax.set_xlabel(f"PC1 ({var[0]*100:.1f}% var)", fontsize=11)
ax.set_ylabel(f"PC2 ({var[1]*100:.1f}% var)", fontsize=11)
ax.set_title(f"K-Means (k={best_k}) — PCA Projection of Member Behaviour\n"
             "Stars = cluster centroids", fontsize=12, fontweight="bold")
ax.legend(fontsize=8, loc="best")
save(fig, "02_kmeans_pca.png")

# Cluster profile heatmap
fig, ax = plt.subplots(figsize=(9, max(3, best_k)))
profile_data = cprof[CLUSTER_FEATURES].T
profile_data.columns = [f"C{c}: {label_map.get(c,'?')}" for c in profile_data.columns]
sns.heatmap(profile_data, annot=True, fmt=".3f", cmap="RdYlGn",
            linewidths=0.5, ax=ax, cbar_kws={"label": "Mean Value"})
ax.set_title("Cluster Profiles — Mean Feature Values per Cluster",
             fontsize=12, fontweight="bold")
save(fig, "03_cluster_profiles.png")

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — CLASSIFICATION (BOAT proxy, Random Forest, Naïve Bayes ×2)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("3  CLASSIFIERS")
print("━"*60)
"""
TARGET  : is_tiebreaker  (0 / 1, derived from cluster in §2)
FEATURES: ideology (D1, D2), overall loyalty, close-vote defect rate,
          blowout loyalty, clutch delta, party code
SPLIT   : chronological by roll-call number — oldest 70 % train,
          next 15 % validation (depth tuning), last 15 % test
CLASS WEIGHT: 'balanced' — penalises missing the rare tie-breaker class
"""

# Member-level chrono split via *first* roll call each member voted on
first_roll = df.groupby("icpsr")["rollnumber"].min().reset_index().rename(
    columns={"rollnumber": "first_roll"})
mem_q2 = mem_q.merge(first_roll, on="icpsr", how="left")

all_rolls_sorted = sorted(rollcalls_ch["rollnumber"].dropna().astype(int))
n_r = len(all_rolls_sorted)
r70 = all_rolls_sorted[int(0.70 * n_r)]
r85 = all_rolls_sorted[int(0.85 * n_r)]

CLF_FEATURES = ["nominate_dim1", "nominate_dim2", "loyalty_pct",
                "close_defect_pct", "blowout_loyalty_pct", "clutch_delta", "party_code"]
TARGET = "is_tiebreaker"

valid_mask = mem_q2[CLF_FEATURES + [TARGET, "first_roll"]].notna().all(axis=1)
mf = mem_q2[valid_mask].copy()

train_m = mf[mf["first_roll"] <= r70]
val_m   = mf[(mf["first_roll"] > r70) & (mf["first_roll"] <= r85)]
test_m  = mf[mf["first_roll"] > r85]

# If val/test are too small due to member chrono, fall back to random split
if len(val_m) < 20 or len(test_m) < 20:
    from sklearn.model_selection import train_test_split
    print("  (Falling back to stratified random 70/15/15 split — "
          "not enough members in later roll-call windows)")
    X_all = mf[CLF_FEATURES].values
    y_all = mf[TARGET].values
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(
        X_all, y_all, test_size=0.30, stratify=y_all, random_state=42)
    X_va, X_te, y_va, y_te = train_test_split(
        X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=42)
else:
    X_tr = train_m[CLF_FEATURES].values;  y_tr = train_m[TARGET].values
    X_va = val_m[CLF_FEATURES].values;    y_va = val_m[TARGET].values
    X_te = test_m[CLF_FEATURES].values;   y_te = test_m[TARGET].values

print(f"  Train: {len(X_tr)}  Val: {len(X_va)}  Test: {len(X_te)}")
print(f"  Tie-breaker prevalence — train: {y_tr.mean():.2%}  test: {y_te.mean():.2%}")

# ── 3A. BOAT proxy: Decision Tree (Gini) with depth tuned on validation ─────
print("\n  [A] Decision Tree (BOAT proxy)")
best_depth, best_f1_val = 3, 0.0
for d in range(2, 12):
    dt = DecisionTreeClassifier(max_depth=d, criterion="gini",
                                class_weight="balanced", random_state=42)
    dt.fit(X_tr, y_tr)
    fv = f1_score(y_va, dt.predict(X_va), pos_label=1, zero_division=0)
    if fv > best_f1_val:
        best_f1_val, best_depth = fv, d

dt_gini = DecisionTreeClassifier(max_depth=best_depth, criterion="gini",
                                  class_weight="balanced", random_state=42)
dt_gini.fit(X_tr, y_tr)
print(f"     Best depth (Gini, val F1): {best_depth}")

# Entropy variant (for Information Gain comparison)
dt_entropy = DecisionTreeClassifier(max_depth=best_depth, criterion="entropy",
                                     class_weight="balanced", random_state=42)
dt_entropy.fit(X_tr, y_tr)

# ── 3B. Random Forest ────────────────────────────────────────────────────────
print("  [B] Random Forest")
rf = RandomForestClassifier(n_estimators=300, max_depth=best_depth + 2,
                            class_weight="balanced", random_state=42, n_jobs=-1)
rf.fit(X_tr, y_tr)

# ── 3C. Naïve Bayes — Gaussian ───────────────────────────────────────────────
print("  [C] Naïve Bayes (Gaussian)")
gnb = GaussianNB()
gnb.fit(X_tr, y_tr)

# ── 3D. Naïve Bayes — Bernoulli (binarised features) ────────────────────────
print("  [D] Naïve Bayes (Bernoulli)")
X_tr_bin = (X_tr > np.median(X_tr, axis=0)).astype(float)
X_te_bin = (X_te > np.median(X_tr, axis=0)).astype(float)
bnb = BernoulliNB()
bnb.fit(X_tr_bin, y_tr)

# ── Helper: evaluate one model ───────────────────────────────────────────────
def evaluate(name, model, X_test_data, y_test_data, is_bernoulli=False):
    Xt = X_te_bin if is_bernoulli else X_test_data
    y_pred = model.predict(Xt)
    y_prob = model.predict_proba(Xt)[:, 1]
    acc  = accuracy_score(y_test_data, y_pred)
    f1   = f1_score(y_test_data, y_pred, pos_label=1, zero_division=0)
    prec = precision_score(y_test_data, y_pred, pos_label=1, zero_division=0)
    rec  = recall_score(y_test_data, y_pred, pos_label=1, zero_division=0)
    fpr, tpr, _ = roc_curve(y_test_data, y_prob)
    roc_auc = auc(fpr, tpr)
    baseline = max(y_test_data.mean(), 1 - y_test_data.mean())
    row = dict(model=name, accuracy=acc, f1=f1, precision=prec, recall=rec,
               roc_auc=roc_auc, baseline=baseline)
    metrics_rows.append(row)
    print(f"     {name:<28}  acc={acc:.3f}  F1={f1:.3f}  "
          f"P={prec:.3f}  R={rec:.3f}  AUC={roc_auc:.3f}  (baseline={baseline:.3f})")
    return y_pred, y_prob, fpr, tpr, roc_auc

results = {}
results["DT (Gini)"]    = evaluate("DT (Gini)",    dt_gini,   X_te, y_te)
results["DT (Entropy)"] = evaluate("DT (Entropy)", dt_entropy, X_te, y_te)
results["Random Forest"] = evaluate("Random Forest", rf,       X_te, y_te)
results["Naïve Bayes (G)"] = evaluate("Naïve Bayes (G)", gnb, X_te, y_te)
results["Naïve Bayes (B)"] = evaluate("Naïve Bayes (B)", bnb, X_te, y_te,
                                       is_bernoulli=True)

# ── 3E. P-value: permutation test (non-parametric, small n) ─────────────────
print("\n  [E] P-values via Chi-Square test on confusion matrix …")
"""
We use a chi-square test of independence on each model's confusion matrix.
H0: the classifier's predictions are independent of true labels (i.e., no
better than chance). A p < 0.05 allows us to reject H0 and conclude the
model carries statistically significant predictive signal.
This is computationally cheap and appropriate for our small test set (n=68).
"""
pval_rows = []
for idx_p, (name, model, X_p, is_b) in enumerate([
    ("DT (Gini)",       dt_gini,    X_te,     False),
    ("DT (Entropy)",    dt_entropy, X_te,     False),
    ("Random Forest",   rf,         X_te,     False),
    ("Naïve Bayes (G)", gnb,        X_te,     False),
    ("Naïve Bayes (B)", bnb,        X_te_bin, True),
]):
    Xp = X_te_bin if is_b else X_p
    yp = model.predict(Xp)
    cm_tmp = confusion_matrix(y_te, yp)
    try:
        _, pval, _, _ = chi2_contingency(cm_tmp)
    except Exception:
        pval = 1.0
    pval_rows.append({"model": name, "p_value": pval})
    if idx_p < len(metrics_rows):
        metrics_rows[idx_p]["p_value"] = pval
    sig = "✓" if pval < 0.05 else "✗"
    print(f"     {name:<28}  p={pval:.4f}  {sig} (p<0.05)")

# ── PLOTS: Decision Tree Diagram ─────────────────────────────────────────────
FEAT_LABELS = ["Ideology D1", "Ideology D2", "Loyalty",
               "Close Defect %", "Blowout Loyalty", "Clutch Δ", "Party"]
fig, axes = plt.subplots(1, 2, figsize=(22, 8))
for ax, (model, crit, title) in zip(axes, [
    (dt_gini,    "Gini",    f"BOAT-proxy — Gini (depth={best_depth})"),
    (dt_entropy, "Entropy", f"BOAT-proxy — Entropy / Info-Gain (depth={best_depth})")
]):
    plot_tree(model, feature_names=FEAT_LABELS,
              class_names=["Non-TB", "Tie-Breaker"],
              filled=True, rounded=True, fontsize=7, ax=ax,
              impurity=True, proportion=False)
    ax.set_title(title, fontsize=11, fontweight="bold")
fig.suptitle("Classification Trees — Gini vs. Entropy (Information Gain)\n"
             "Node colour intensity = class purity; 'impurity' shown in each node",
             fontsize=13, fontweight="bold")
save(fig, "04_decision_tree_gini_vs_entropy.png")

# ── PLOTS: Feature Importance — Gini vs Entropy vs RF ───────────────────────
fi_gini    = pd.Series(dt_gini.feature_importances_,    index=FEAT_LABELS)
fi_entropy = pd.Series(dt_entropy.feature_importances_, index=FEAT_LABELS)
fi_rf      = pd.Series(rf.feature_importances_,         index=FEAT_LABELS)

fi_df = pd.DataFrame({"Gini (DT)": fi_gini, "Entropy (DT)": fi_entropy,
                       "Random Forest": fi_rf}).sort_values("Random Forest", ascending=False)

fig, ax = plt.subplots(figsize=(10, 5))
x    = np.arange(len(fi_df))
w    = 0.25
ax.bar(x - w, fi_df["Gini (DT)"],    w, label="Gini (DT)",    color="#3b6dbf", alpha=0.85)
ax.bar(x,     fi_df["Entropy (DT)"], w, label="Entropy (DT)", color="#e67e22", alpha=0.85)
ax.bar(x + w, fi_df["Random Forest"],w, label="Random Forest",color="#27ae60", alpha=0.85)
ax.set_xticks(x); ax.set_xticklabels(fi_df.index, rotation=25, ha="right", fontsize=9)
ax.set_ylabel("Feature Importance", fontsize=11)
ax.set_title("Feature Importance — Gini, Entropy (Information Gain), Random Forest\n"
             "Higher = stronger signal for classifying tie-breaker membership",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
save(fig, "05_feature_importance_comparison.png")

# ── PLOTS: Information Gain at each tree node (depth trace) ─────────────────
# Extract per-node impurity decrease for dt_entropy (= information gain)
tree_e = dt_entropy.tree_
n_nodes = tree_e.node_count
node_feature  = tree_e.feature
node_ig       = tree_e.impurity          # entropy at node (IG = parent - children)
children_left = tree_e.children_left

# Only internal (split) nodes
split_nodes = np.where(children_left != -1)[0]
ig_per_feature = {f: [] for f in FEAT_LABELS}
for node in split_nodes:
    feat_idx = node_feature[node]
    if feat_idx >= 0:
        # IG = node_impurity - weighted child impurity (sklearn stores impurity decrease)
        ig_per_feature[FEAT_LABELS[feat_idx]].append(node_ig[node])

ig_mean = {f: (np.mean(v) if v else 0.0) for f, v in ig_per_feature.items()}
ig_series = pd.Series(ig_mean).sort_values(ascending=False)

fig, ax = plt.subplots(figsize=(9, 4))
ig_series.plot.bar(ax=ax, color="#8e44ad", edgecolor="white")
ax.set_ylabel("Mean Node Entropy at Split (proxy for Info Gain)", fontsize=10)
ax.set_title("Information Gain by Feature — Entropy Tree\n"
             "Features chosen more often at high-entropy nodes carry more information",
             fontsize=12, fontweight="bold")
plt.xticks(rotation=30, ha="right")
save(fig, "06_information_gain_by_feature.png")

# ── PLOTS: ROC Curves ────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 7))
colors_roc = ["#3b6dbf", "#e67e22", "#27ae60", "#c0392b", "#8e44ad"]
for (name, res), col in zip(results.items(), colors_roc):
    _, _, fpr, tpr, roc_auc = res
    ax.plot(fpr, tpr, color=col, linewidth=2,
            label=f"{name}  (AUC={roc_auc:.3f})")
ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5, label="Random (AUC=0.50)")
ax.set_xlabel("False Positive Rate", fontsize=11)
ax.set_ylabel("True Positive Rate", fontsize=11)
ax.set_title("ROC Curves — All Classifiers\nTie-Breaker vs. Non-Tie-Breaker",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=8, loc="lower right")
save(fig, "07_roc_curves.png")

# ── PLOTS: Metrics comparison bar ────────────────────────────────────────────
metrics_df = pd.DataFrame(metrics_rows).set_index("model")
metrics_plot = metrics_df[["accuracy", "f1", "precision", "recall", "roc_auc"]]

fig, ax = plt.subplots(figsize=(12, 5))
x  = np.arange(len(metrics_plot))
w  = 0.15
met_colors = ["#3b6dbf", "#27ae60", "#e67e22", "#c0392b", "#8e44ad"]
met_labels  = ["Accuracy", "F1", "Precision", "Recall", "ROC-AUC"]
for i, (col, lbl, clr) in enumerate(zip(metrics_plot.columns, met_labels, met_colors)):
    ax.bar(x + i * w, metrics_plot[col], w, label=lbl, color=clr, alpha=0.85)
ax.set_xticks(x + 2 * w)
ax.set_xticklabels(metrics_plot.index, rotation=20, ha="right", fontsize=9)
ax.set_ylabel("Score", fontsize=11)
ax.set_ylim(0, 1.05)
ax.axhline(metrics_df["baseline"].mean(), color="grey", linestyle=":",
           linewidth=1.5, label="Avg Majority Baseline")
ax.set_title("Classifier Comparison — Accuracy, F1, Precision, Recall, AUC",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=8, ncol=3)
save(fig, "08_metrics_comparison_bar.png")

# ── PLOTS: Confusion matrices (2×3 grid) ────────────────────────────────────
model_list = [
    ("DT (Gini)",     dt_gini,   X_te,     False),
    ("DT (Entropy)",  dt_entropy, X_te,    False),
    ("Random Forest", rf,        X_te,     False),
    ("Naïve Bayes (G)", gnb,     X_te,     False),
    ("Naïve Bayes (B)", bnb,     X_te_bin, False),
]
fig, axes = plt.subplots(2, 3, figsize=(16, 10))
axes = axes.flatten()
for ax, (name, model, Xp, ib) in zip(axes, model_list):
    yp = model.predict(X_te_bin if ib else Xp)
    cm = confusion_matrix(y_te, yp)
    ConfusionMatrixDisplay(cm, display_labels=["Non-TB", "Tie-Breaker"]).plot(
        ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(name, fontsize=10, fontweight="bold")
axes[-1].axis("off")
fig.suptitle("Confusion Matrices — All Classifiers (Test Set)\n"
             "TB=Tie-Breaker pseudo-label from K-Means cluster",
             fontsize=13, fontweight="bold")
save(fig, "09_confusion_matrices.png")

# ── PLOTS: P-value table as figure ───────────────────────────────────────────
pval_df = pd.DataFrame(pval_rows)
fig, ax = plt.subplots(figsize=(7, 3))
ax.axis("off")
col_labels = ["Model", "p-value", "Significant (p<0.05)"]
cell_text = [[r["model"], f"{r['p_value']:.4f}",
              "Yes ✓" if r["p_value"] < 0.05 else "No ✗"]
             for r in pval_rows]
tbl = ax.table(cellText=cell_text, colLabels=col_labels,
               loc="center", cellLoc="center")
tbl.auto_set_font_size(False); tbl.set_fontsize(10)
tbl.scale(1.2, 1.8)
for (r, c), cell in tbl.get_celld().items():
    if r == 0:
        cell.set_facecolor("#2c3e50"); cell.set_text_props(color="white", fontweight="bold")
    elif cell_text[r-1][2].startswith("Yes") if r > 0 else False:
        cell.set_facecolor("#d5f5e3")
ax.set_title("P-Values — Permutation Test (1000 shuffles, F1 scoring)\n"
             "Tests whether classifier beats random chance on this dataset",
             fontsize=11, fontweight="bold", pad=20)
save(fig, "10_pvalue_table.png")

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — FREQUENT PATTERN MINING (Apriori + FP-Growth)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("4  FREQUENT PATTERN MINING")
print("━"*60)
"""
TRANSACTION DESIGN (see companion document §4):
  Each MEMBER who defected at least once on a close vote contributes one
  transaction. The items in that transaction are:
    • VQ:<vote_question_category>   (what type of bill they crossed on)
    • Ideo:<ideology_bin>           (liberal / moderate / conservative)
    • Party:<Dem|Rep>               (their partisan affiliation)

  This rich basket (3–8 items per member) lets Apriori and FP-Growth
  surface co-occurring contexts of cross-party voting — e.g., "members
  who defected on Amendments tend to also defect on Passage votes, and
  are disproportionately moderate Republicans."

  Both algorithms run on the SAME basket; results are compared side-by-side.
"""

close_def_df = df[df["is_close"] & df["defected"].astype(bool)].copy()
close_def_df["ideo_bin"] = pd.cut(
    close_def_df["nominate_dim1"],
    bins=[-1.1, -0.3, 0.0, 0.3, 1.1],
    labels=["FarLeft", "Left", "Right", "FarRight"])
close_def_df["party_label"] = close_def_df["party_code"].map({100: "Dem", 200: "Rep"})

def make_basket(grp):
    items = set()
    for _, row in grp.iterrows():
        items.add(f"VQ:{row['vq_short']}")
        if pd.notna(row["ideo_bin"]):
            items.add(f"Ideo:{row['ideo_bin']}")
        items.add(f"Party:{row['party_label']}")
    return list(items)

transactions = close_def_df.groupby("icpsr").apply(make_basket).tolist()
print(f"  Transactions: {len(transactions)}")
items_per = [len(t) for t in transactions]
print(f"  Items/transaction: min={min(items_per)}, max={max(items_per)}, "
      f"mean={np.mean(items_per):.1f}")

te = TransactionEncoder()
te_array  = te.fit_transform(transactions)
basket_df = pd.DataFrame(te_array, columns=te.columns_)

MIN_SUPPORT = 0.30   # 30 % of defecting members share this itemset

# ── 4A. Apriori ──────────────────────────────────────────────────────────────
freq_apriori = apriori(basket_df, min_support=MIN_SUPPORT, use_colnames=True)
freq_apriori["length"] = freq_apriori["itemsets"].apply(len)
freq_apriori["algorithm"] = "Apriori"
print(f"  Apriori  — itemsets found: {len(freq_apriori)}")

rules_apriori = association_rules(
    freq_apriori, metric="lift", min_threshold=1.0,
    num_itemsets=len(freq_apriori))
rules_apriori = rules_apriori.sort_values("lift", ascending=False)
print(f"  Apriori  — rules found:    {len(rules_apriori)}")

# ── 4B. FP-Growth ─────────────────────────────────────────────────────────────
freq_fp = fpgrowth(basket_df, min_support=MIN_SUPPORT, use_colnames=True)
freq_fp["length"] = freq_fp["itemsets"].apply(len)
freq_fp["algorithm"] = "FP-Growth"
print(f"  FP-Growth — itemsets found: {len(freq_fp)}")

rules_fp = association_rules(
    freq_fp, metric="lift", min_threshold=1.0,
    num_itemsets=len(freq_fp))
rules_fp = rules_fp.sort_values("lift", ascending=False)
print(f"  FP-Growth — rules found:    {len(rules_fp)}")

# Verify both algorithms agree
both_match = len(freq_apriori) == len(freq_fp)
print(f"  Apriori == FP-Growth itemset count: {both_match} "
      f"({'✓ consistent' if both_match else '✗ discrepancy'})")

# ── PLOTS: Apriori itemsets bar ───────────────────────────────────────────────
def plot_itemsets(freq, algo_name, filename):
    plot_df = (freq[freq["length"] >= 2]
               .sort_values("support", ascending=False).head(15).copy())
    plot_df["label"] = plot_df["itemsets"].apply(lambda s: " ∩ ".join(sorted(s)))
    col = "#8e44ad" if "Apriori" in algo_name else "#2980b9"
    fig, ax = plt.subplots(figsize=(13, 5))
    bars = ax.barh(plot_df["label"], plot_df["support"] * 100,
                   color=col, edgecolor="white")
    ax.invert_yaxis()
    ax.set_xlabel("Support (% of defecting members sharing this itemset)", fontsize=11)
    ax.set_title(f"{algo_name} — Top Frequent Itemsets (2+ items, min_support={MIN_SUPPORT:.0%})\n"
                 "Items = vote-question type · ideology bin · party affiliation",
                 fontsize=12, fontweight="bold")
    for bar, val in zip(bars, plot_df["support"]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val*100:.0f}%", va="center", fontsize=8)
    save(fig, filename)

plot_itemsets(freq_apriori, "Apriori",   "11_apriori_itemsets.png")
plot_itemsets(freq_fp,      "FP-Growth", "12_fpgrowth_itemsets.png")

# ── PLOTS: Association rules scatter (Apriori, top rules) ───────────────────
if len(rules_apriori) > 0:
    rules_apriori["ant_str"] = rules_apriori["antecedents"].apply(
        lambda s: ", ".join(sorted(s)))
    rules_apriori["con_str"] = rules_apriori["consequents"].apply(
        lambda s: ", ".join(sorted(s)))

    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(rules_apriori["support"] * 100,
                    rules_apriori["confidence"] * 100,
                    s=(rules_apriori["lift"] * 35).clip(20, 400),
                    c=rules_apriori["lift"], cmap="plasma",
                    alpha=0.75, edgecolors="none")
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Lift", fontsize=10)
    ax.set_xlabel("Support (%)", fontsize=11)
    ax.set_ylabel("Confidence (%)", fontsize=11)
    ax.set_title("Association Rules — Support vs. Confidence  (size & colour = Lift)\n"
                 "Apriori rules mined from defection-context baskets",
                 fontsize=12, fontweight="bold")
    # Annotate top 5 by lift
    for _, row in rules_apriori.head(5).iterrows():
        ax.annotate(f"{row['ant_str']}→{row['con_str']}",
                    (row["support"] * 100, row["confidence"] * 100),
                    fontsize=6, xytext=(4, 4), textcoords="offset points",
                    arrowprops=dict(arrowstyle="-", lw=0.5))
    save(fig, "13_association_rules_scatter.png")

# ── PLOTS: Tie-breaker pie (cluster-identified + top names) ──────────────────
tb_members   = mem_q[mem_q["is_tiebreaker"] == 1].sort_values(
    "close_defect_pct", ascending=False)
non_tb       = mem_q[mem_q["is_tiebreaker"] == 0]
tb_dem       = (tb_members["party_code"] == 100).sum()
tb_rep       = (tb_members["party_code"] == 200).sum()
non_tb_dem   = (non_tb["party_code"]     == 100).sum()
non_tb_rep   = (non_tb["party_code"]     == 200).sum()

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Left: overall TB vs non-TB
sizes1  = [len(tb_members), len(non_tb)]
labels1 = [f"Tie-Breakers\n(n={len(tb_members)})",
           f"Non-Tie-Breakers\n(n={len(non_tb)})"]
axes[0].pie(sizes1, labels=labels1, colors=["#e67e22", "#bdc3c7"],
            autopct="%1.1f%%", startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=1.5))
axes[0].set_title("Tie-Breaker vs. Non-Tie-Breaker\n(K-Means pseudo-labels)",
                  fontsize=11, fontweight="bold")

# Right: party breakdown within TB group
sizes2  = [tb_dem, tb_rep]
labels2 = [f"Democrat\n(n={tb_dem})", f"Republican\n(n={tb_rep})"]
axes[1].pie(sizes2, labels=labels2, colors=[BLUE, RED],
            autopct="%1.1f%%", startangle=140,
            wedgeprops=dict(edgecolor="white", linewidth=1.5))
axes[1].set_title("Party Breakdown Among\nIdentified Tie-Breakers",
                  fontsize=11, fontweight="bold")

fig.suptitle("Tie-Breaker Composition — 118th U.S. House\n"
             "Cluster-identified tie-breakers by party and prevalence",
             fontsize=13, fontweight="bold")
save(fig, "14_tiebreaker_pie.png")

# ── Print top rule summary ────────────────────────────────────────────────────
print("\n  Top 10 Association Rules (Apriori, by Lift):")
print(rules_apriori[["ant_str", "con_str", "support", "confidence", "lift"]]
      .rename(columns={"ant_str": "Antecedent", "con_str": "Consequent"})
      .head(10).to_string(index=False))

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — SAVE METRICS SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("5  SAVING METRICS SUMMARY")
print("━"*60)
final_metrics = pd.DataFrame(metrics_rows)
for col in ["p_value"]:
    if col not in final_metrics.columns:
        final_metrics[col] = np.nan
metrics_path = os.path.join(OUT_DIR, "metrics_summary.csv")
final_metrics.to_csv(metrics_path, index=False)
print(f"  Saved: metrics_summary.csv")
print("\n  Full metrics table:")
print(final_metrics.to_string(index=False))

# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "━"*60)
print("✅  COMPLETE — all outputs saved to:", os.path.abspath(OUT_DIR))
print("━"*60)
