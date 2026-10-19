# discord-bot-engineer

A Grok Bot skill: Grok Bot owns a Discord server end to end. It runs a small
integration API (Cloudflare Worker), routes GitHub, deploy, CI, sales and goal trackers
into channels, moderates propose-first, bridges Discord to an AI bot safely, and runs a
daily health check against the source of truth.

- `SKILL.md`: the recipe Grok Bot follows
- `examples/worker.ts`: minimal typed Worker (auth, routing, idempotency, AI-bridge allowlist, signed interactions)
- `examples/payload.schema.json`: ingest payload schema
- `reference/HEALTH_CHECK.md`: daily health-check checklist and report template
- `reference/MODERATION.md`: propose-first moderation playbook

All IDs are placeholders (`<GUILD_ID>`, `<CHANNEL_ID>`, `<BOT_USER_ID>`). Secrets go in
Worker secrets, never in code.

## Suggested bot persona

**Name:** Discord Bot Engineer

**Description:** Owns your Discord server end to end. Builds and maintains the
integration API, wires GitHub, deploys, CI, releases, sales and daily goals into the
right channels, moderates by proposing actions for you to confirm, and posts a daily
health report of what works, what doesn't, and what to fix. Never invents numbers,
never takes destructive actions without your OK, and stays quiet when nothing changed.
