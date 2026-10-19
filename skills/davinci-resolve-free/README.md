# davinci-resolve-free

[![Watch: Use GrokBot to Automate DaVinci Resolve](https://img.youtube.com/vi/hfUNIVahOMo/maxresdefault.jpg)](https://www.youtube.com/watch?v=hfUNIVahOMo&t=64s)

▶ **[Watch the walkthrough: Use GrokBot to Automate DaVinci Resolve](https://www.youtube.com/watch?v=hfUNIVahOMo&t=64s)**

A Grok Bot skill: Grok Bot builds a complete edit **inside DaVinci Resolve (free)** with
an in-app menu script, asks the user questions in a dialog inside Resolve, renders
YouTube and vertical versions, and afterwards only reformats the export (Shorts/Reels
safe-zone check or version, thumbnails).

- `SKILL.md`: the recipe Grok Bot follows
- `scripts/GrokBot_Resolve_Full_Edit.py`: install into Resolve's `Fusion/Scripts/Utility` folder, run from **Workspace > Scripts**
- `scripts/GrokBot_Hello.py`: smoke test
- `scripts/grokbot_reformat.py`, `REFORMAT.md`: the post-export step (ffmpeg)
- `examples/manifest.example.json`: inputs (clips with in/out ranges, music, brand, dialog defaults)
- `tests/mock_full_edit.py`: offline mock of the Resolve API: `python3 tests/mock_full_edit.py`

Tested against DaVinci Resolve 21.0.4 (free) on macOS. Calls that a real run hasn't
exercised yet are wrapped, and the log reports them as `SKIPPED <step>: <reason>`.
