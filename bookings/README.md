# bookings/ — the calendar-fill pipeline

Turns the VC-portfolio dossiers into **booked, qualified meetings** on
`calendly.com/d/dv5f-2jy-ttx/22min-meeting-with-zorbe` (change in `config.json`).

Every send goes through the existing SendPilot rails — org-wide dedup, per-inbox
caps, warmup awareness, CC pranay — nothing here sends directly.

```
qualified companies (leads.json, scored 0-100, tiers 1-4)
        │  pipeline.py worksheet → contact_worksheet.csv
        ▼
you pull people from Apollo → data/contacts.csv  (company,first_name,last_name,email,title)
        │  pipeline.py stage          → _booking_pool.json      → tests/send_batch.py
        │  pipeline.py followups (D+3, D+7 threaded replies)    → container/send_followups.py
        ▼
replies / bookings
        │  pipeline.py sync   (Calendly API → auto-mark booked, kill follow-ups)
        │  pipeline.py mark replied <email>   (until Gmail read scope exists)
        ▼
pipeline.py report   →  staged → replied → BOOKED funnel
```

## Daily runbook (~10 min)

```bash
cd ~/Documents/sendpilot/bookings
export CALENDLY_PAT=...        # once; calendly.com → Integrations → API & webhooks

python3 pipeline.py sync       # pull new bookings, auto-suppress booked leads
python3 pipeline.py followups  # stage due D+3/D+7 threaded follow-ups
#   → send them:  docker compose exec -e DRY=1 api python /app/bookings_send_followups.py  (then without DRY=1)
python3 pipeline.py stage --tier 2 --limit 30   # stage next touch-1 batch
#   → send it:    (command is printed; always DRY_RUN=1 first)
python3 pipeline.py report
```

Mark replies as they arrive (stops that person's sequence):
```bash
python3 pipeline.py mark replied person@company.com
```

## One-time setup

1. **DNS_FIX.md** — do this first. Spam folder = zero bookings.
2. Mount the follow-up sender into the api container (docker-compose.yml, api service):
   `- ./bookings/container/send_followups.py:/app/bookings_send_followups.py`
3. **Calendly screening questions** (Event → Invitee Questions) so every booking
   self-qualifies — sync prints the answers with each booking:
   - "What does your company build, and roughly how many people are you?"
   - "Which models are in production, and roughly what's your monthly inference spend?" *(required)*
   - "What's the highest-volume AI task in your product?"
4. Contacts: export from Apollo using `contact_worksheet.csv` (it lists exact
   titles per company, best-first) into `data/contacts.csv`.

## Design notes / guardrails

- `stage` only emails contacts whose company has a **verified sequence** and a
  qualification score — cold spray is structurally impossible.
- Org-wide dedup still applies at send time (send_batch checks the DB), so a
  contact emailed by any past campaign is silently skipped there.
- Follow-ups are **threaded replies** with a campaign-independent idempotency
  key: re-running the sender can never double-send a step, and anyone whose
  touch-1 never actually sent is skipped automatically.
- `sync`/`mark` write `data/suppress.txt`; suppressed people never get another touch.
- Keep respecting inbox ceilings: zorbeai.com ≤ 40/day, tryzorbe.com warmup-low,
  zorbe.ai is the workhorse. The scheduled 10:00 drip
  (`_scheduled_zorbe.json`) shares those caps — count it in.
- The scheduled drip pool is separate from this pipeline by design; don't point
  both at the same pool file.
