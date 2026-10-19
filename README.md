<div align="center">

# Grok Bot Skills

**Open-source skills that teach [Grok Bot](https://grokbot.dev) real jobs: editing video in DaVinci Resolve, running a Discord server, tracking every routine.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Grok Bot](https://img.shields.io/badge/runs%20on-Grok%20Bot-black.svg)](https://grokbot.dev)
[![GitHub stars](https://img.shields.io/github/stars/devrecated/grokbot-skills?style=social)](https://github.com/devrecated/grokbot-skills/stargazers)

</div>

---

A skill is a folder with a `SKILL.md` recipe (YAML front matter with `name` and
`description`, then the steps) plus any scripts or examples it needs. Grok Bot reads
the recipe and runs it on your computer, asking for permission and for your input
along the way.

## Skills

| Skill | What it does |
|---|---|
| 🎬 [`davinci-resolve-free`](skills/davinci-resolve-free/) | Grok Bot builds a full edit inside DaVinci Resolve (free): Fusion titles, lower thirds, grades, music, markers, YouTube and vertical renders. It asks you questions in a dialog inside Resolve, then reformats the export for Shorts/Reels and thumbnails. [Video walkthrough](https://www.youtube.com/watch?v=hfUNIVahOMo&t=64s). |
| 🤖 [`discord-bot-engineer`](skills/discord-bot-engineer/) | Grok Bot owns your Discord server: a small integration API, GitHub/deploy/CI/sales trackers routed to channels, propose-first moderation, a safe AI-bot bridge, and a daily health check against the source of truth. |
| 📋 [`routine-run-log`](skills/routine-run-log/) | One local page of every Grok Bot routine across all your bots, with last run, status and a filterable run history. Each routine appends one line per run to a shared log, so the page stays current without asking each bot. |

## Quick start

1. Pick a skill above and open its folder.
2. In Grok Bot, say *"Save this as a skill"* and point it at the folder URL, for example
   `https://github.com/devrecated/grokbot-skills/tree/main/skills/davinci-resolve-free`.
3. Use it by typing `/` or `@` and the skill name, or just ask:
   *"edit my demo clips in DaVinci Resolve"*.
4. Skills that ship scripts tell Grok Bot where to install them and which permissions
   to ask you for.

## Links

- 🎥 [Use GrokBot to Automate DaVinci Resolve](https://www.youtube.com/watch?v=hfUNIVahOMo&t=64s) on YouTube
- 🌐 [grokbot.dev](https://grokbot.dev)
- 🏢 [Devrecated on GitHub](https://github.com/devrecated)

## Contributing

Pull requests are welcome. Keep skills generic, with no personal paths, accounts or
secrets, and include a short test or a dry-run mode when a skill ships code.

If a skill saved you time, a ⭐ helps other people find it.

## License

[MIT](LICENSE)
