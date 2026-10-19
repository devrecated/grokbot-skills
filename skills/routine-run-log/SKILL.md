---
name: routine-run-log
description: Give the user one cheap, always-current local page of every Grok Bot routine across all their bots and each run's time, status and one-line summary, using a shared log folder on the box instead of asking every bot each time.
---

# Routine run log

Routines live on Grok Bot's servers and each bot can only see its own, so there is no single
place to list them all. This skill sets up a shared folder on the box (one machine shared by all
of the user's bots) that every routine writes to, plus a static page that reads it.

## Setup (once)

1. Create the log folder, e.g. `<LOG_DIR>` = `/workspace/routine-log`, and copy in
   `scripts/log-run.sh`, `scripts/register.sh`, `scripts/build.sh` and `examples/index.html`.
   `chmod +x *.sh`, then `touch registry.jsonl runs.jsonl`.
2. Message each of the user's bots once (skip pure personas). Keep it short:
   > If you have any routines, (a) run `<LOG_DIR>/register.sh '<bot name>' '<bot id>' '<routine id>' '<name>' '<schedule or trigger>' '<purpose>'` once for each, and
   > (b) update each routine's prompt to add, as its final step:
   > `<LOG_DIR>/log-run.sh '<bot name>' '<routine id>' ok|error|skipped '<one-line summary>'`, with no secrets in the summary.
   > If you have no routines, do nothing and don't reply.
3. Don't change anything else in the routines.

## Data

- `registry.jsonl`: `{bot, bot_id, routine_id, name, schedule_or_trigger, purpose, updated_at}`, upserted by `routine_id`.
- `runs.jsonl`: `{ts, bot, routine_id, status, summary}`. `ts` is ISO 8601 with the local offset. The summary is capped at 200 chars.
- Writes are locked (`flock`). Registry updates are atomic (temp file + rename).

## Viewing

- Live: `cd <LOG_DIR> && python3 -m http.server 8765`, then open `http://localhost:8765/`. It refreshes every 60 s.
- Offline: `<LOG_DIR>/build.sh` writes `dist.html` with the data inlined, so it opens via `file://`.

## Rules

- Never log secrets, tokens or personal data in summaries.
- Logging is best-effort. A failed log line must not fail the routine.
