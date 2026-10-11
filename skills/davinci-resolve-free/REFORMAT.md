# Grok Bot reformat step (after the Resolve export)

Everything editorial happens inside DaVinci Resolve: the cut, titles, Fusion
graphics, grade, music, markers, and the render. Grok Bot only *repackages*
Resolve's finished files for each platform. It never re-cuts, re-grades or re-mixes.

Inputs (written by `GrokBot_Resolve_Full_Edit.py` to `~/Movies/GrokBot-Resolve/renders/`):

| File | From Resolve |
|---|---|
| `<name>.mp4` | 16:9 YouTube render (H.264 + AAC) |
| `<name>-vertical.mp4` | 9:16 render, if you ticked "vertical" in the dialog |
| `<name>-thumb-frame.png` | frame exported with `ExportCurrentFrameAsStill` |
| `<name>-chapters.txt` | YouTube chapters built from the timeline markers |
| `<name>-report.json` | dialog answers, the capability summary, and post-render feedback |

## What Grok Bot does

1. **Shorts / Reels / TikTok safe vertical.** If Resolve rendered a 9:16 version,
   Grok Bot only checks it (`grokbot_reformat.py check`) against the platform UI zones:
   about **250 px top**, **420 px bottom** (captions and buttons) and **150 px right**
   (like/comment rail) on a 1080x1920 frame. If there's no Resolve vertical, or it
   fails the check, Grok Bot builds one from the 16:9 export:
   `grokbot_reformat.py vertical <name>.mp4 <name>-shorts.mp4`. The picture is fitted
   inside the safe box (60 px left margin) over a blurred, darkened copy of itself.
   Audio is copied bit for bit.
2. **Thumbnails.** `grokbot_reformat.py thumb <name>-thumb-frame.png <name> --title "..."`
   makes a 1280x720 YouTube thumbnail and a 1080x1920 cover from Resolve's frame.
3. **Description pack.** Pastes `<name>-chapters.txt` into a description draft, plus the
   links the user wants (the tutorial video, the skill repo).
4. **Ask for feedback.** Grok Bot reads `USER NOTES` / `USER FEEDBACK` from the log
   and report, shows the renders, and asks what to change. Changes go back into the
   manifest defaults, and the Resolve script runs again. The edit itself is never
   patched outside Resolve.

## Commands

```
python3 grokbot_reformat.py vertical in.mp4 out-shorts.mp4 [--top 250 --bottom 420 --right 150 --left 60]
python3 grokbot_reformat.py thumb frame.png out_prefix --title "My video"
python3 grokbot_reformat.py check vertical.mp4 check.png --at 5
```
Requires `ffmpeg` (and Pillow for `thumb` / `check`).
