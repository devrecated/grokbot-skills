# routine-run-log

One local page showing every Grok Bot routine across all your bots, with last run and a
filterable run history. Each routine appends one JSON line per run to a shared file, so
the page stays current without re-asking every bot.

```
scripts/register.sh  "Bot" "bot-id" "routine-id" "Name" "daily 9am" "Purpose"
scripts/log-run.sh   "Bot" "routine-id" ok "Sent the inbox digest (12 threads)"
scripts/build.sh     # -> dist.html (self-contained snapshot)
```

Set `ROUTINE_LOG_DIR` to put the data somewhere other than the scripts' folder.
Requires `bash` and `python3`; no other dependencies. See [SKILL.md](SKILL.md).
