#!/usr/bin/env python3
"""Calendar-fill pipeline: qualified leads -> personalized sequences -> booked meetings.

Runs on the HOST (stdlib only). It stages pool files that the existing in-container
machinery sends (tests/send_batch.py for touch 1, bookings/container/send_followups.py
for touches 2-3), so every send inherits org-wide dedup, per-inbox caps, and CC rules.

  python3 pipeline.py worksheet            # contact_worksheet.csv - who to pull from Apollo
  python3 pipeline.py stage [--limit N] [--tier T] [--dry]
  python3 pipeline.py followups [--dry]    # stage due touch-2/3 threaded replies
  python3 pipeline.py sync                 # poll Calendly -> mark booked, suppress
  python3 pipeline.py mark booked|replied <email>
  python3 pipeline.py report               # funnel: staged -> replied -> booked

Data lives in bookings/data/:
  leads.json       scored company cards (generated)
  sequences.json   3-touch sequences per company (generated)
  contacts.csv     YOU provide: company,first_name,last_name,email,title
  state.json       per-recipient touch/reply/booked state
  suppress.txt     never email again (booked, replied, opted out)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = json.load(open(os.path.join(HERE, "config.json")))

LEADS_F = os.path.join(DATA, "leads.json")
SEQS_F = os.path.join(DATA, "sequences.json")
CONTACTS_F = os.path.join(DATA, "contacts.csv")
STATE_F = os.path.join(DATA, "state.json")
SUPPRESS_F = os.path.join(DATA, "suppress.txt")
WORKSHEET_F = os.path.join(DATA, "contact_worksheet.csv")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def today() -> str:
    return dt.date.today().isoformat()


def load_json(path, default):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1)


def load_suppress() -> set[str]:
    try:
        return {l.strip().lower() for l in open(SUPPRESS_F) if l.strip()}
    except FileNotFoundError:
        return set()


def suppress(email: str) -> None:
    s = load_suppress()
    if email.lower() not in s:
        with open(SUPPRESS_F, "a") as f:
            f.write(email.lower() + "\n")


def load_contacts() -> list[dict]:
    if not os.path.exists(CONTACTS_F):
        return []
    with open(CONTACTS_F, newline="") as f:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    out = []
    for r in rows:
        email = (r.get("email") or "").lower()
        if "@" not in email:
            continue
        out.append(
            {
                "company": r.get("company", ""),
                "first_name": r.get("first_name") or r.get("first", ""),
                "email": email,
                "title": r.get("title", ""),
            }
        )
    return out


def seq_index() -> dict[str, dict]:
    """normalized company name -> sequence entry"""
    seqs = load_json(SEQS_F, [])
    return {norm(s["company"]): s for s in seqs}


def match_sequence(company: str, idx: dict[str, dict]) -> dict | None:
    k = norm(company)
    if k in idx:
        return idx[k]
    for sk, s in idx.items():  # substring fallback: "Quizizz" vs "Wayground (Quizizz)"
        if len(k) >= 4 and (k in sk or sk in k):
            return s
    return None


def personalize(text: str, first: str) -> str:
    return text.replace("{{first_name}}", (first or "there").split()[0].capitalize())


# ---------------------------------------------------------------- commands


def cmd_worksheet(_args) -> None:
    leads = load_json(LEADS_F, [])
    if not leads:
        sys.exit("no leads.json yet - run the lead consolidation first")
    idx = seq_index()
    os.makedirs(DATA, exist_ok=True)
    with open(WORKSHEET_F, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company", "tier", "score", "angle", "has_sequence", "titles_to_find", "known_contacts", "caveats"])
        for l in leads:
            if l["tier"] >= 4:
                continue
            w.writerow(
                [
                    l["company"],
                    l["tier"],
                    l["score"],
                    l["angle"],
                    "yes" if match_sequence(l["company"], idx) else "",
                    "; ".join(l.get("contact_titles", [])),
                    "; ".join(l.get("known_contacts", []) or []),
                    l.get("caveats", ""),
                ]
            )
    n = sum(1 for l in leads if l["tier"] < 4)
    print(f"wrote {WORKSHEET_F} ({n} companies, tiers 1-3)")
    print("Pull these people from Apollo/LinkedIn into data/contacts.csv with columns:")
    print("  company,first_name,last_name,email,title")


def cmd_stage(args) -> None:
    idx = seq_index()
    if not idx:
        sys.exit("no sequences.json yet")
    leads_by_norm = {norm(l["company"]): l for l in load_json(LEADS_F, [])}
    contacts = load_contacts()
    if not contacts:
        sys.exit(f"no contacts yet - fill {CONTACTS_F} (see: pipeline.py worksheet)")
    state = load_json(STATE_F, {})
    sup = load_suppress()

    rows, skipped = [], {"already": 0, "suppressed": 0, "no_sequence": 0, "tier": 0}
    for c in contacts:
        if c["email"] in state:
            skipped["already"] += 1
            continue
        if c["email"] in sup:
            skipped["suppressed"] += 1
            continue
        seq = match_sequence(c["company"], idx)
        if not seq:
            skipped["no_sequence"] += 1
            continue
        lead = leads_by_norm.get(norm(seq["company"]), {})
        if args.tier and int(lead.get("tier", 9)) > args.tier:
            skipped["tier"] += 1
            continue
        t1 = next((t for t in seq["touches"] if t["step"] == 1), None)
        if not t1:
            continue
        rows.append(
            {
                "email": c["email"],
                "subject": t1["subject"],
                "body": personalize(t1["body"], c["first_name"]),
                "_company": seq["company"],
                "_first": c["first_name"],
            }
        )
        if args.limit and len(rows) >= args.limit:
            break

    print(f"stageable: {len(rows)} | skipped: {skipped}")
    if not rows:
        return
    if args.dry:
        for r in rows[:3]:
            print(f"\n--- {r['email']} ({r['_company']}) ---\nSubject: {r['subject']}\n{r['body'][:400]}...")
        print("\nDRY - nothing written.")
        return

    pool_path = os.path.abspath(os.path.join(HERE, CONFIG["pool_file"]))
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows], open(pool_path, "w"), indent=1)
    for r in rows:
        state[r["email"]] = {"company": r["_company"], "first_name": r["_first"], "touches": {"1": today()}, "replied": False, "booked": False}
    save_json(STATE_F, state)
    print(f"wrote {len(rows)} touch-1 emails -> {pool_path}")
    print("\nSend (dry-run first, then drop DRY_RUN):")
    print(f"  docker compose exec -e OUTBOUND_JSON=/app/tests/{os.path.basename(pool_path)} \\")
    print(f"    -e ACCOUNTS={','.join(CONFIG['accounts'])} -e DRY_RUN=1 api python tests/send_batch.py")


def cmd_followups(args) -> None:
    idx = seq_index()
    state = load_json(STATE_F, {})
    sup = load_suppress()
    offsets = {int(k): v for k, v in CONFIG["followup_offsets_days"].items()}
    t0 = dt.date.today()

    due = []
    for email, st in state.items():
        if st.get("replied") or st.get("booked") or email in sup:
            continue
        touches = st.get("touches", {})
        if "1" not in touches:
            continue
        d1 = dt.date.fromisoformat(touches["1"])
        seq = match_sequence(st["company"], idx)
        if not seq:
            continue
        for step in (2, 3):
            if str(step) in touches or str(step) in [x["step"] for x in due if x["email"] == email]:
                continue
            if (t0 - d1).days >= offsets[step]:
                t = next((t for t in seq["touches"] if t["step"] == step), None)
                if t:
                    due.append({"email": email, "step": step, "subject": t["subject"], "body": personalize(t["body"], st.get("first_name", ""))})
                break  # at most one follow-up per contact per run

    print(f"due follow-ups: {len(due)} (step2: {sum(1 for d in due if d['step']==2)}, step3: {sum(1 for d in due if d['step']==3)})")
    if not due:
        return
    if args.dry:
        for d in due[:3]:
            print(f"\n--- {d['email']} step {d['step']} ---\n{d['body'][:300]}")
        print("\nDRY - nothing written.")
        return

    fpath = os.path.abspath(os.path.join(HERE, CONFIG["followup_file"]))
    json.dump(due, open(fpath, "w"), indent=1)
    for d in due:
        state[d["email"]]["touches"][str(d["step"])] = today()
    save_json(STATE_F, state)
    print(f"wrote {len(due)} follow-ups -> {fpath}")
    print("\nSend (dry first):")
    print("  docker compose exec -e DRY=1 api python /app/bookings_send_followups.py")
    print("(mount or copy bookings/container/send_followups.py into the api container;")
    print(" it threads each follow-up into the original conversation and skips anyone")
    print(" whose touch-1 never actually sent, so state drift is safe)")


def _calendly_get(url: str, pat: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {pat}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cmd_sync(_args) -> None:
    pat = os.environ.get(CONFIG["calendly_pat_env"], "")
    if not pat:
        sys.exit(
            f"set {CONFIG['calendly_pat_env']} first.\n"
            "Get a (free) personal access token: calendly.com -> Integrations -> API & webhooks."
        )
    me = _calendly_get("https://api.calendly.com/users/me", pat)["resource"]
    org = me["current_organization"]
    min_start = (dt.datetime.now(dt.UTC) - dt.timedelta(days=CONFIG["lookback_days_for_bookings"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://api.calendly.com/scheduled_events?" + urllib.parse.urlencode(
        {"organization": org, "min_start_time": min_start, "count": 100}
    )
    events = []
    while url:
        page = _calendly_get(url, pat)
        events += page["collection"]
        url = page.get("pagination", {}).get("next_page")

    state = load_json(STATE_F, {})
    matched, outside = [], []
    for ev in events:
        if ev.get("status") == "canceled":
            continue
        inv_url = ev["uri"] + "/invitees"
        for inv in _calendly_get(inv_url, pat)["collection"]:
            email = (inv.get("email") or "").lower()
            when = ev.get("start_time", "?")
            qa = {q.get("question"): q.get("answer") for q in inv.get("questions_and_answers", [])}
            if email in state:
                if not state[email].get("booked"):
                    state[email]["booked"] = True
                    state[email]["booked_at"] = when
                    suppress(email)
                    matched.append((email, state[email]["company"], when, qa))
            else:
                outside.append((email, when, qa))
    save_json(STATE_F, state)

    print(f"calendly events scanned: {len(events)}")
    if matched:
        print(f"\nNEW BOOKINGS from the pipeline ({len(matched)}) - follow-ups auto-stopped:")
        for e, co, w, qa in matched:
            print(f"  {e} ({co}) at {w}" + (f"  answers: {qa}" if qa else ""))
    booked_total = sum(1 for s in state.values() if s.get("booked"))
    print(f"\npipeline bookings total: {booked_total} | bookings outside pipeline: {len(outside)}")
    for e, w, _ in outside[:10]:
        print(f"  (outside) {e} at {w}")


def cmd_mark(args) -> None:
    email = args.email.lower()
    state = load_json(STATE_F, {})
    if email not in state:
        state[email] = {"company": "?", "first_name": "", "touches": {}, "replied": False, "booked": False}
    state[email][args.what] = True
    suppress(email)
    save_json(STATE_F, state)
    print(f"{email}: {args.what}=True, suppressed (no more touches)")


def cmd_report(_args) -> None:
    leads = load_json(LEADS_F, [])
    seqs = load_json(SEQS_F, [])
    state = load_json(STATE_F, {})
    contacts = load_contacts()
    tiers = {}
    for l in leads:
        tiers[l["tier"]] = tiers.get(l["tier"], 0) + 1
    t1 = sum(1 for s in state.values() if "1" in s.get("touches", {}))
    t2 = sum(1 for s in state.values() if "2" in s.get("touches", {}))
    t3 = sum(1 for s in state.values() if "3" in s.get("touches", {}))
    replied = sum(1 for s in state.values() if s.get("replied"))
    booked = sum(1 for s in state.values() if s.get("booked"))
    print("=== calendar-fill funnel ===")
    print(f"companies scored: {len(leads)}  (by tier: {dict(sorted(tiers.items()))})")
    print(f"sequences ready:  {len(seqs)}")
    print(f"contacts loaded:  {len(contacts)}")
    print(f"touch 1 staged:   {t1}")
    print(f"touch 2 staged:   {t2}")
    print(f"touch 3 staged:   {t3}")
    print(f"replied:          {replied}")
    print(f"BOOKED:           {booked}")
    if booked:
        for e, s in state.items():
            if s.get("booked"):
                print(f"   {e} ({s['company']}) at {s.get('booked_at', '?')}")
    if t1:
        print(f"\nbook rate so far: {booked}/{t1} = {booked / t1:.1%} of touched leads")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("worksheet")
    st = sub.add_parser("stage")
    st.add_argument("--limit", type=int, default=None)
    st.add_argument("--tier", type=int, default=None, help="only stage companies at this tier or better")
    st.add_argument("--dry", action="store_true")
    fu = sub.add_parser("followups")
    fu.add_argument("--dry", action="store_true")
    sub.add_parser("sync")
    mk = sub.add_parser("mark")
    mk.add_argument("what", choices=["booked", "replied"])
    mk.add_argument("email")
    sub.add_parser("report")
    args = p.parse_args()
    {"worksheet": cmd_worksheet, "stage": cmd_stage, "followups": cmd_followups, "sync": cmd_sync, "mark": cmd_mark, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
