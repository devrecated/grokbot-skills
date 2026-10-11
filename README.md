# Grok Bot skills

Reusable skills for **Grok Bot**. A skill is a folder with a `SKILL.md` recipe
(YAML front matter with `name` and `description`, then the steps), plus any scripts or
examples it needs. Grok Bot reads the recipe and runs it on your computer, asking for
permission and for your input along the way.

| Skill | What it does |
|---|---|
| [`davinci-resolve-free`](skills/davinci-resolve-free/) | Grok Bot builds a full edit inside DaVinci Resolve (free): Fusion titles, lower thirds, grades, music, markers, YouTube and vertical renders. It asks you questions in a dialog inside Resolve, and afterwards only reformats the export for Shorts/Reels and thumbnails. |

## Add a skill to Grok Bot

1. Open the skill's folder and copy its `SKILL.md` (or the whole folder, if it has scripts).
2. In Grok Bot, ask: *"Save this as a skill"* and paste the `SKILL.md`, or point Grok Bot
   at the folder URL, for example
   `https://github.com/devrecated/grokbot-skills/tree/main/skills/davinci-resolve-free`.
   Grok Bot saves it to your skill library.
3. Use it any time by typing `/` or `@` and the skill name, or just ask
   (*"edit my demo clips in DaVinci Resolve"*).
4. Skills with scripts (like `davinci-resolve-free`) tell Grok Bot where to install them
   and which permissions to ask you for.

## Links

- Tutorial video: **How to use Grok Bot with DaVinci Resolve (free)**, *link coming soon*
- Our GitHub: https://github.com/devrecated/grokbot

## Contributing

Pull requests are welcome. Keep skills generic: no personal paths, accounts or secrets.
Include a short test or a dry-run mode when a skill ships code.

## License

[MIT](LICENSE)
