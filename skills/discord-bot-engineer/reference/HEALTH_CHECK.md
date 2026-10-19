# Daily Discord health check

Run once a day. Post the report only if something changed since the last one.

## Checklist
1. **Channels resolve**: GET each routed `<CHANNEL_ID>`. A 404 or 403 is a dead or inaccessible route; flag it.
2. **Posts match the source of truth**: for the last 24 h, compare
   - GitHub commits / PRs / releases vs cards in the GitHub channel,
   - Actions runs (failures especially) vs cards in the CI channel,
   - deploys vs cards in the deploys channel.
   Report missing cards, duplicates, and cards whose status is out of date.
3. **Boards are fresh**: leaderboards, goals and rollups updated within their period; flag stale ones with last-updated time.
4. **Commands work**: each slash command answers (dependent ones may answer "offline", which counts as handled).
5. **Secrets**: flag any secret not rotated within policy or after a known leak.
6. **AI bridge**: confirm it answered only in allow-listed channels with @mentions.
7. **Moderation**: open proposals awaiting the owner, unusual join spikes.

## Report template
**Working**: streams and commands that matched the source.
**Not working**: each issue with evidence (counts from the APIs, links).
**Suggestions**: one concrete fix per issue, smallest change first.

Only numbers the APIs returned. Mark anything inferred as *unverified*.
