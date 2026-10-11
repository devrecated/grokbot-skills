---
name: DaVinci Resolve (free) - Grok Bot drives the edit
description: >-
  Use when the user wants Grok Bot to build, re-cut, grade, title or render a video
  inside DaVinci Resolve (free or Studio) on their computer, or to turn a Resolve
  export into Shorts/Reels/thumbnails. Covers permissions, installing the in-app
  scripts, the in-Resolve questions dialog, what is scriptable in free vs Studio,
  the reformat step, and the feedback loop after every render.
---
# DaVinci Resolve (free): Grok Bot drives the edit

The edit always happens **inside Resolve**: cut, Fusion titles and graphics, grade,
music, markers, and render. Grok Bot prepares the inputs, starts the in-app script,
watches the log, and afterwards only **reformats** Resolve's export (vertical
safe-zone version, thumbnails, description pack). Grok Bot never re-cuts, re-grades
or re-mixes outside Resolve. If something should change, change the manifest or the
answers and run the script in Resolve again.

Bundled files (next to this SKILL.md):
- `scripts/GrokBot_Resolve_Full_Edit.py`: the in-app menu script, Python 3, standard library only.
- `scripts/GrokBot_Hello.py`: a smoke test that prints the Resolve version and current project.
- `scripts/grokbot_reformat.py` + `REFORMAT.md`: the post-export reformat step (ffmpeg).
- `examples/manifest.example.json`: the input manifest format.
- `tests/mock_full_edit.py`: an offline mock of the Resolve API (`python3 tests/mock_full_edit.py`).

## 1. Ask first

Before touching anything, ask the user (one short message):
- Free or Studio, which version (Help > About), and macOS or Windows?
- What is the video: the source clips, the story or sections in order, the title or tagline, any brand assets, and the music?
- Which deliverables: YouTube 16:9, a vertical Short/Reel, a thumbnail?
- What look, pacing (tight or relaxed) and music level? Use these answers as the
  dialog defaults, so the user can just click **Build my edit** in Resolve.

## 2. Permission: Accessibility (macOS)

Free Resolve blocks *external* scripting (that's Studio-only), but scripts installed
in Resolve's Scripts folder run from **Workspace > Scripts** in both versions. For Grok
Bot to click that menu, and the dialog's buttons, it needs macOS Accessibility access.
Ask, and explain why:

> To run the edit inside DaVinci Resolve for you, I need to click Resolve's
> **Workspace > Scripts** menu. macOS only allows that with Accessibility access:
> open **System Settings > Privacy & Security > Accessibility**, click **+**, add the
> **Grok Bot** app, and turn it on. I only use it to click Resolve's menus and dialog
> buttons. You can switch it off afterwards.

Without it, ask the user to click **Workspace > Scripts > GrokBot_Resolve_Full_Edit** themselves.
On Windows, ask the user to click the menu, or use whatever desktop automation is
available on that machine. Never try to bypass the permission.

## 3. Install the scripts (once)

Copy the `.py` files from `scripts/` (not `grokbot_reformat.py`) into the per-user Utility scripts folder, creating it if needed:

| OS | Folder |
|---|---|
| macOS | `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/` |
| Windows | `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\` |
| Linux | `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/` |

Then quit and reopen Resolve. The scripts appear under **Workspace > Scripts**.
Resolve needs a system Python 3 (python.org installer). Check with **GrokBot_Hello**
first, and open **Workspace > Console** (Py3 tab) to see its output.

## 4. Prepare the inputs

Make one folder per video: `~/Movies/GrokBot-Resolve/<video-name>/` (Windows: `%USERPROFILE%\Movies\GrokBot-Resolve\<video-name>\`) containing:
- `manifest.json` (copy `examples/manifest.example.json`; `"kind": "grokbot-full-edit"` is required)
- `raw/` original clips. Each section has `tight` and `relaxed` in/out times in **seconds of the source**. Pick the ranges where the action happens; scrub the clips or look at frame grabs first.
- `music/` a licensed music bed (put a fade-out at the end of the file; `music_align: "end"` lands it on the last frame)
- `brand/` optional: `logo_bug_16x9.png` (1920x1080 transparent canvas with the logo in a corner), `logo_bug_9x16.png` (1080x1920), `wordmark.png`

The script uses the newest full-edit manifest under `~/Movies/GrokBot-Resolve/*/`.
Renders go to `~/Movies/GrokBot-Resolve/renders/`, and existing files are never overwritten.

## 5. Run it inside Resolve

1. Bring Resolve to the front and click **Workspace > Scripts > GrokBot_Resolve_Full_Edit**. On macOS with Accessibility:
   ```
   osascript -e 'tell application "DaVinci Resolve" to activate' \
     -e 'delay 1' \
     -e 'tell application "System Events" to tell process "Resolve" to click menu item "GrokBot_Resolve_Full_Edit" of menu 1 of menu item "Scripts" of menu 1 of menu bar item "Workspace" of menu bar 1'
   ```
   (If the click fails, list the menu with System Events to confirm the process and menu names.)
   Click it **once**. A lock file stops a second run, but don't rely on it.
2. **The questions dialog appears inside Resolve**: title, subtitle, look, pacing, transitions,
   music level, which sections to include, a vertical 9:16 yes/no, and *"Anything you'd like changed?"*.
   It is a UIManager window. If this build has no UIManager (some free builds restrict it),
   the script falls back to a Fusion AskUser dialog, then native macOS dialogs, then manifest defaults.
   Let the user answer. In a hands-off run, press **Build my edit** (Return) with the prefilled defaults.
   **Cancel** stops the run before anything changes.
3. Tell the user not to touch Resolve until the log says `DONE`. Follow `~/Movies/GrokBot-Resolve/log.txt`.
   Every line carries a run id, every step is wrapped, and a failure is logged as `SKIPPED <step>: <reason>`
   while the run continues. A capability summary is printed at the end.
4. After the render, a feedback box asks *"What should Grok Bot change next?"*, and the answer is logged as `USER FEEDBACK`.

## 6. What the script does in Resolve (free version)

| Page | Capability | API used | Free |
|---|---|---|---|
| Project | create/load project, resolution, fps, scale-full-frame-with-crop, colour science | `CreateProject`, `SetSetting` | yes |
| Media | bins per type, import clips/music/graphics, clip colours, flags, metadata and keywords, select markers, sub-clips | `AddSubFolder`, `ImportMedia`, `SetClipColor`, `AddFlag`, `SetMetadata`, `MediaPoolItem.AddMarker`, `MediaStorage.AddItemListToMediaPool` | yes |
| Edit | timeline of source in/out ranges (endFrame is **exclusive** in Resolve 21), placed with `recordFrame` | `CreateEmptyTimeline`, `AppendToTimeline` | yes |
| Edit | Text+ intro/outro titles styled in Fusion (gradient plate, wordmark Loader, slide-up, fades) | `InsertFusionTitleIntoTimeline`, `GetFusionCompByIndex`, Fusion `AddTool`/`SetInput`/`ConnectInput`/`AddModifier` | yes |
| Edit | per-clip Fusion comp: section title card, animated lower third, slow push-in, dip-to-black | `AddFusionComp` + Fusion tools | yes |
| Edit | end-screen Fusion generator, logo bug on V2, zoom/pan/tilt/opacity/retime, item names, track names, coloured chapter markers | `InsertFusionGeneratorIntoTimeline`, `AddTrack`, `TimelineItem.SetProperty`, `SetName`, `SetTrackName`, `AddMarker` | yes |
| Edit | Cross Dissolve version of the cut | writes FCPXML, then `MediaPool.ImportTimelineFromFile` (the API has no transition call) | yes |
| Color | colour group, one local version per look (compare in Color > Local Versions), CDL grade, bundled film LUT, optional DRX, thumbnail still | `AddColorGroup`, `AssignToColorGroup`, `AddVersion`, `LoadVersionByName`, `SetCDL`, `Graph.SetLUT`, `ApplyGradeFromDRX`, `ExportCurrentFrameAsStill`, `GrabStill` | yes |
| Fairlight | music on A1 (aligned to the end), voiceover track, track names | `AppendToTimeline(mediaType 2)`, `AddTrack("audio","stereo")` | yes |
| Vertical | 9:16 duplicate, reframed with Zoom/Tilt, 9:16 logo | `DuplicateTimeline`, `Timeline.SetSetting(useCustomSettings…)`, `SetProperty` | yes |
| Deliver | YouTube 1080p H.264/AAC and vertical jobs, saved render presets, render and poll, chapters .txt, OTIO/CSV, .drp backup | `LoadRenderPreset`, `SetRenderSettings`, `SaveAsNewRenderPreset`, `AddRenderJob`, `StartRendering`, `GetRenderJobStatus`, `Timeline.Export`, `ExportProject` | yes |

**Not scriptable, so do these by hand in the UI (the script logs them as SKIPPED):** clip speed/retime
amount, audio clip volume and fades, EQ, Ducker, loudness normalisation, setting node labels, adding
color nodes, Edit-page transitions on the main timeline, and keyframes on Edit-page transforms (Fusion
keyframes work).

**Studio-only:** external scripting (running scripts from outside Resolve), Voice Isolation,
Smart Reframe, Magic Mask, auto subtitles (`CreateSubtitlesFromAudio`), AI IntelliSearch,
speech generation, Speed Warp, and possibly the UIManager dialogs in some versions. Always give the user a free
fallback (manual Inspector reframe, typed or imported .srt captions, and so on).

**Gotchas:** a project's frame rate locks once it has a timeline, so use a new project name to
change fps. Mixed-fps sources are conformed (the script sets `RetimeProcess` to nearest so screen
text stays crisp). Insert*IntoTimeline places items at the playhead, so the script moves the
playhead first and checks where each item landed. Still images have a default length, so the
script tiles them.

## 7. Reformat (the only work outside Resolve)

See `REFORMAT.md`. In short:
- If Resolve rendered a 9:16 version, check it against the Shorts/Reels UI zones (about 250 px top,
  420 px bottom and 150 px right on 1080x1920): `python3 scripts/grokbot_reformat.py check <vertical.mp4> check.png`.
- Otherwise make one from the 16:9 export: `python3 scripts/grokbot_reformat.py vertical <name>.mp4 <name>-shorts.mp4`.
- Thumbnails come from Resolve's thumb frame: `python3 scripts/grokbot_reformat.py thumb <name>-thumb-frame.png <name> --title "..."`.
- Draft the description from `<name>-chapters.txt`. YouTube needs a first chapter at 0:00, at least 3 chapters, and each ≥10 s.

## 8. Ask for feedback after every render

Every time a render finishes:
1. Show the user the renders (16:9, vertical, thumbnail) and the capability summary, including anything SKIPPED that they may want to do by hand.
2. Read `USER NOTES` and `USER FEEDBACK` from the log or `<name>-report.json`.
3. Ask what they'd like to see changed: pacing, sections, look, titles, music level, length, platform versions. Offer two or three concrete options.
4. Apply changes by editing the manifest (defaults, in/out ranges, sections, brand) and run the script in Resolve again. Never patch the edit outside Resolve.
