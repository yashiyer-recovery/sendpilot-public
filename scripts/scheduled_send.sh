#!/bin/bash
# Weekday drip: 30 emails/day from yash@zorbe.ai until the scheduled pool is exhausted.
#
# Driven by the LaunchAgent com.zorbe.sendpilot.scheduled-send (weekdays 10:00 America/Los_Angeles).
# Org-wide dedup means each run picks up the next 30 never-emailed recipients; once the
# pool is exhausted the run is a harmless no-op ("Nothing new to send").
#
# Reads its OWN pool (_scheduled_zorbe.json) so ad-hoc batches staged into _batch.json
# can never hijack the schedule.
#
#   DRY_RUN=1 scripts/scheduled_send.sh    # test the plumbing without sending

set -uo pipefail

# LaunchAgents run with a minimal PATH — docker (OrbStack) needs an absolute path.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

REPO="/Users/yashiyer/Documents/sendpilot"
LOG="$REPO/scheduled_send.log"

cd "$REPO" || { echo "$(date '+%F %T %Z') FATAL: repo not found at $REPO" >>"$LOG"; exit 1; }

{
  echo "===== $(date '+%F %T %Z') — scheduled send starting ====="

  # Ensure the docker daemon (OrbStack) is up — after a reboot it may not be.
  if ! docker info >/dev/null 2>&1; then
    echo "docker daemon down — starting OrbStack..."
    open -a OrbStack >/dev/null 2>&1
    for _ in $(seq 1 45); do
      sleep 2
      docker info >/dev/null 2>&1 && break
    done
  fi
  docker info >/dev/null 2>&1 || {
    echo "ERROR: docker daemon still down after waiting — cannot send this run."
    echo "(Leads are NOT lost: dedup means the next weekday run picks them up.)"
    echo "===== $(date '+%F %T %Z') — aborted ====="
    exit 1
  }

  # Make sure the stack is up (idempotent; covers a reboot).
  docker compose up -d db redis api worker >/dev/null 2>&1 || {
    echo "ERROR: could not start containers"
    echo "===== $(date '+%F %T %Z') — aborted ====="
    exit 1
  }

  docker compose exec -T \
    -e ACCOUNTS='yash@zorbe.ai' \
    -e OUTBOUND_JSON=/app/tests/_scheduled_zorbe.json \
    -e LIMIT=30 \
    -e DRY_RUN="${DRY_RUN:-}" \
    api python tests/send_batch.py
  rc=$?

  echo "----- send_batch exit: $rc -----"
  echo "===== $(date '+%F %T %Z') — scheduled send finished ====="
  echo ""
} >>"$LOG" 2>&1
