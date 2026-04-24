import os
import requests
import pandas as pd
import time
from tqdm import tqdm

# ── Configuration ────────────────────────────────────────────────────────────
import config  # expects config.API_KEY

API_KEY    = config.API_KEY
BASE_URL   = "https://api.congress.gov/v3"
HEADERS    = {"x-api-key": API_KEY, "Content-Type": "application/json"}
OUTPUT_DIR = "outputs"

# 118th Congress = 2023-2024, 119th = 2025-2026
TARGET_CONGRESSES = [118, 119]

# ── Helpers ──────────────────────────────────────────────────────────────────

def api_get(url, retries=3, backoff=10):
    """GET with retry/backoff on non-200 responses."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:           # rate limited
                wait = backoff * (attempt + 1)
                print(f"\n  [429 Rate Limited] Waiting {wait}s …")
                time.sleep(wait)
            else:
                print(f"\n  [HTTP {r.status_code}] {url}")
                return None
        except requests.RequestException as e:
            print(f"\n  [Network error] {e}")
            time.sleep(backoff)
    return None


def paginate(endpoint_path, result_key, max_records=None):
    """
    Generic paginator. Yields items from any list-level endpoint.
    endpoint_path should NOT include ?limit=... or &offset=...
    """
    offset    = 0
    page_size = 250
    collected = 0

    while True:
        sep = "&" if "?" in endpoint_path else "?"
        url = f"{BASE_URL}{endpoint_path}{sep}limit={page_size}&offset={offset}&format=json"
        data = api_get(url)
        if data is None:
            break
        items = data.get(result_key, [])
        if not items:
            break
        for item in items:
            yield item
            collected += 1
            if max_records and collected >= max_records:
                return
        if len(items) < page_size:
            break                               # last page
        offset += page_size
        time.sleep(0.8)                         # ~1 req/s, well under rate limit


# ── Bill fetching ─────────────────────────────────────────────────────────────

BILL_TYPES = ["hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"]

def get_bills_for_congress(congress, max_per_congress=5000):
    """Fetch bills across all bill types for a given congress."""
    bills = []
    for btype in BILL_TYPES:
        path = f"/bill/{congress}/{btype}"
        for bill in paginate(path, "bills", max_records=max_per_congress):
            bill["_congress"] = congress
            bill["_billType"] = btype.upper()
            bills.append(bill)
            if len(bills) >= max_per_congress:
                return bills
    return bills


def get_bill_actions(congress, bill_type, bill_number):
    """Return list of actions for a single bill."""
    path = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/actions"
    data = api_get(f"{BASE_URL}{path}?limit=250&format=json")
    if data:
        return data.get("actions", [])
    return []


def determine_passed(actions):
    """
    Heuristic: check latest action text for passage language.
    Returns 'Yes', 'No', or 'Unknown'.
    """
    passage_keywords = [
        "became public law", "signed by president", "passed senate",
        "passed house", "agreed to in senate", "agreed to in house",
        "presented to president",
    ]
    veto_keywords = ["vetoed", "pocket vetoed"]
    for action in reversed(actions):          # most-recent first
        text = action.get("text", "").lower()
        if any(k in text for k in passage_keywords):
            return "Yes"
        if any(k in text for k in veto_keywords):
            return "No"
    return "Unknown"


def get_roll_call_votes(congress, bill_number, bill_type, actions):
    """
    Look for roll-call vote links in the bill's actions.
    Returns a list of dicts with yes/no/present/not_voting counts + member votes.
    The beta House Roll Call endpoint format:
      /house-vote/{congress}/{session}/{rollCallNumber}/members
    """
    vote_records = []
    for action in actions:
        # Actions with a roll-call reference have a recordedVotes list
        for rv in action.get("recordedVotes", []):
            chamber     = rv.get("chamber", "")
            roll_number = rv.get("rollNumber")
            session_val = rv.get("sessionNumber") or action.get("actionDate", "")[:4]
            # Normalize session to 1 or 2
            year = int(str(session_val)[:4]) if str(session_val).isdigit() else None
            if year:
                session = 1 if year % 2 == 1 else 2   # odd year = session 1
            else:
                session = 1

            if chamber.lower() == "house" and roll_number:
                url = (f"{BASE_URL}/house-vote/{congress}/{session}"
                       f"/{roll_number}/members?format=json")
                data = api_get(url)
                if data:
                    members_votes = data.get("members", [])
                    vote_records.append({
                        "chamber": "House",
                        "roll_number": roll_number,
                        "session": session,
                        "members_votes": members_votes,
                    })
                time.sleep(0.5)
    return vote_records


def format_vote_summary(vote_records):
    """Flatten vote records to simple string columns."""
    if not vote_records:
        return "", "", ""

    yeas_list, nays_list = [], []
    for vr in vote_records:
        for m in vr["members_votes"]:
            name = m.get("fullName", m.get("name", ""))
            vote = m.get("votePosition", m.get("vote", ""))
            if vote and vote.lower() in ("yea", "aye", "yes"):
                yeas_list.append(name)
            elif vote and vote.lower() in ("nay", "no"):
                nays_list.append(name)

    roll_nums = "; ".join(str(vr["roll_number"]) for vr in vote_records)
    return roll_nums, "; ".join(yeas_list), "; ".join(nays_list)


# ── Member fetching ───────────────────────────────────────────────────────────

def get_all_members():
    """
    Fetch every member from /member (current + historical).
    Available fields: bioguideId, name, party, state, district, chamber, terms.
    NOTE: The Congress.gov API does NOT provide race/ethnicity or gender.
          Those demographics are available via the unitedstates/congress-legislators
          GitHub dataset — we join that below.
    """
    members = list(paginate("/member", "members"))
    return members


def get_legislators_demographics():
    """
    Pull the open-data legislators CSV from the unitedstates project on GitHub.
    Provides gender, birthday, and other bioguide-matched fields.
    Race/ethnicity is NOT in this dataset either (no authoritative public API).
    """
    url = ("https://raw.githubusercontent.com/unitedstates/congress-legislators"
           "/main/legislators-current.csv")
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        print(f"  [Warning] Could not load demographics supplement: {e}")
        return pd.DataFrame()


# ── Main extraction ───────────────────────────────────────────────────────────

def run_extraction():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── CSV 1: Bills ──────────────────────────────────────────────────────────
    print("=" * 60)
    print("STEP 1 — Fetching bills (118th + 119th Congress, target: 10,000)")
    print("=" * 60)

    all_bills_raw = []
    for congress in TARGET_CONGRESSES:
        remaining = 10_000 - len(all_bills_raw)
        if remaining <= 0:
            break
        print(f"\n  Fetching bills for {congress}th Congress …")
        bills = get_bills_for_congress(congress, max_per_congress=remaining)
        all_bills_raw.extend(bills)
        print(f"  → {len(bills)} bills collected (total so far: {len(all_bills_raw)})")

    print(f"\nTotal bills fetched: {len(all_bills_raw)}")
    print("\nSTEP 2 — Enriching bills with actions & vote data …")

    bill_rows = []
    for bill in tqdm(all_bills_raw, desc="Processing bills"):
        congress    = bill.get("_congress") or bill.get("congress")
        bill_type   = bill.get("_billType") or bill.get("type", "")
        bill_number = bill.get("number", "")
        title       = bill.get("title", "")
        intro_date  = bill.get("introducedDate", "")
        latest_act  = bill.get("latestAction", {})
        latest_date = latest_act.get("actionDate", "")
        latest_text = latest_act.get("text", "")

        # Sponsor
        sponsors    = bill.get("sponsors", [])
        sponsor_name = sponsors[0].get("fullName", "") if sponsors else ""

        # Sub-level actions
        actions     = get_bill_actions(congress, bill_type, bill_number)
        passed      = determine_passed(actions)

        # Vote details
        vote_records = get_roll_call_votes(congress, bill_number, bill_type, actions)
        roll_nums, voted_yea, voted_nay = format_vote_summary(vote_records)

        bill_rows.append({
            "congress":          congress,
            "bill_type":         bill_type,
            "bill_number":       bill_number,
            "title":             title,
            "introduced_date":   intro_date,
            "latest_action_date": latest_date,
            "latest_action_text": latest_text,
            "sponsor":           sponsor_name,
            "passed":            passed,
            "roll_call_numbers": roll_nums,
            "voted_yea":         voted_yea,
            "voted_nay":         voted_nay,
        })
        time.sleep(0.5)

    df_bills = pd.DataFrame(bill_rows)
    bills_path = os.path.join(OUTPUT_DIR, "bills_2023_2025.csv")
    df_bills.to_csv(bills_path, index=False)
    print(f"\n✅ Bills CSV saved → {bills_path}  ({len(df_bills)} rows)")

    # ── CSV 2: Members ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3 — Fetching member roster …")
    print("=" * 60)

    members_raw = get_all_members()
    print(f"  Retrieved {len(members_raw)} members from API")

    member_rows = []
    for m in members_raw:
        terms = m.get("terms", {}).get("item", [])
        if isinstance(terms, dict):         # single-term edge case
            terms = [terms]
        latest_term   = terms[-1] if terms else {}
        chamber       = latest_term.get("chamber", m.get("chamber", ""))
        congress_nums = ", ".join(str(t.get("congress", "")) for t in terms)

        member_rows.append({
            "bioguide_id":     m.get("bioguideId", ""),
            "full_name":       m.get("name", ""),
            "first_name":      m.get("firstName", m.get("directOrderName", "").split(",")[-1].strip()),
            "last_name":       m.get("lastName", m.get("invertedOrderName", "").split(",")[0].strip()),
            "party":           m.get("partyName", m.get("party", "")),
            "state":           m.get("state", ""),
            "district":        m.get("district", ""),
            "chamber":         chamber,
            "congresses_served": congress_nums,
            "current_member":  m.get("currentMember", ""),
            "official_url":    m.get("officialWebsiteUrl", ""),
        })

    df_members = pd.DataFrame(member_rows)

    # Supplement with demographics (gender, birthday) from open-data repo
    print("  Loading demographics supplement (unitedstates/congress-legislators) …")
    df_demo = get_legislators_demographics()
    if not df_demo.empty and "bioguide_id" in df_demo.columns:
        keep_cols = [c for c in ["bioguide_id", "birthday", "gender"] if c in df_demo.columns]
        df_members = df_members.merge(df_demo[keep_cols], on="bioguide_id", how="left")

    members_path = os.path.join(OUTPUT_DIR, "members.csv")
    df_members.to_csv(members_path, index=False)
    print(f"✅ Members CSV saved → {members_path}  ({len(df_members)} rows)")

    print("\nAll done!")


if __name__ == "__main__":
    run_extraction()
