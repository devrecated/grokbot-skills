# -*- coding: utf-8 -*-
"""
GrokBot_Resolve_Full_Edit.py
============================
A DaVinci Resolve *menu script* by Grok Bot. Every edit happens inside Resolve:
run it from Workspace > Scripts > GrokBot_Resolve_Full_Edit (menu scripts work in
the free version; external scripting is Studio-only). Python 3, standard library only.

What it does, page by page (each step is logged and wrapped: a failing step is
logged as "SKIPPED <step>: <reason>" and the run carries on):

  0. Ask      A dialog inside Resolve (UIManager window; falls back to a Fusion
              AskUser dialog, then native macOS dialogs, then manifest defaults):
              title, subtitle, look, pacing, transitions, music level, sections,
              vertical 9:16 yes/no, and "anything you'd like changed".
  1. Project  create/load the project, resolution, frame rate, scale-to-crop,
              color science.
  2. Media    bins per type (Footage / Selects / Audio / Graphics), import raw
              clips + music + logo/branding, clip colours, metadata + keywords,
              flags, select markers, sub-clips of the useful ranges.
  3. Edit     timeline from the raw clips (sub-clip in/out ranges per pacing),
              Fusion Text+ intro/outro titles with keyframed fades/slides,
              per-clip Fusion comps (section title card, animated lower third,
              slow push-in, dip-to-black transitions), end-screen Fusion
              generator, logo overlay on V2, transform/zoom/retime via
              SetProperty, track names, coloured chapter markers.
  4. Alt cut  the same cut with Cross Dissolves + music level, built by writing
              an FCPXML and ImportTimelineFromFile (the API has no transitions).
  5. Color    color group, a local version per look (compare them in Color >
              Local Versions), CDL grade per clip, bundled film LUT, optional
              DRX grade, thumbnail frame export.
  6. Fairlight named Music + Voiceover tracks, music volume (if exposed).
  7. Vertical optional 9:16 duplicate timeline reframed with Zoom/Pan/Tilt.
  8. Deliver  YouTube 1080p H.264/AAC + vertical jobs, saved render presets,
              render + progress, chapters .txt, OTIO/CSV export, .drp backup.
  9. Feedback "What should Grok Bot change?" dialog after the render.

Input: newest ~/Movies/GrokBot-Resolve/*/manifest.json whose "kind" is
"grokbot-full-edit" (see the example manifest). Paths are relative to it.
Log:   ~/Movies/GrokBot-Resolve/log.txt, every line tagged with a run id.
Output: ~/Movies/GrokBot-Resolve/renders/<output_name>[-2...].mp4 (+ -vertical,
        -chapters.txt, -report.json, -thumb-frame.png, .otio, .csv, .drp)
One run at a time (lock file ~/Movies/GrokBot-Resolve/.fulledit.lock).
"""
import os
import sys
import json
import glob
import time
import datetime
import random
import traceback
import subprocess
from fractions import Fraction
try:
    from urllib.parse import quote as _urlquote
except Exception:                                   # pragma: no cover
    _urlquote = None

ROOT_DIR = os.path.expanduser("~/Movies/GrokBot-Resolve")
LOG_PATH = os.path.join(ROOT_DIR, "log.txt")
LOCK_PATH = os.path.join(ROOT_DIR, ".fulledit.lock")
LOCK_STALE_S = 300
RUN_ID = "%04x" % random.randint(0, 0xFFFF)
_HAVE_LOCK = [False]
STAGE_PAUSE = 1.0
RENDER_TIMEOUT = 60 * 60
MANIFEST_KIND = "grokbot-full-edit"
LOOKS = ["Clean", "Warm", "Teal-orange", "B&W", "Film print (LUT)"]
PACINGS = ["tight", "relaxed"]
TRANSITIONS = ["dip", "none"]
MARKER_COLORS = ("Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple", "Fuchsia",
                 "Rose", "Lavender", "Sky", "Mint", "Lemon", "Sand", "Cocoa", "Cream")
# ASC CDL per look: slope / offset / power (R G B) + saturation. Screen recordings
# are flat, dark UIs, so the looks are deliberately gentle.
CDL_LOOKS = {
    "Clean":            ("1.02 1.02 1.02", "0.0 0.0 0.0",        "1.0 1.0 1.0",    "1.05"),
    "Warm":             ("1.05 1.0 0.93",  "0.006 0.0 -0.006",   "0.98 1.0 1.03",  "1.08"),
    "Teal-orange":      ("1.06 1.0 0.95",  "-0.012 0.004 0.016", "1.0 0.98 0.96",  "1.12"),
    "B&W":              ("1.06 1.06 1.06", "-0.01 -0.01 -0.01",  "1.05 1.05 1.05", "0.0"),
    "Film print (LUT)": ("1.0 1.0 1.0",    "0.0 0.0 0.0",        "1.0 1.0 1.0",    "1.0"),
}
FILM_LUTS = ["Film Looks/Rec709 Kodak 2383 D65.cube", "Film Looks/Rec709 Fujifilm 3513DI D65.cube"]
FUSION_GENERATORS = ["Noise Gradient", "Contours", "Paper", "Texture Background"]

RESULTS = []          # (step, status, detail) for the capability summary
STATE = {}            # shared objects (resolve, fusion, project, ...)

# --------------------------------------------------------------------------
# Logging, lock, step wrapper
# --------------------------------------------------------------------------
try:
    os.makedirs(ROOT_DIR, exist_ok=True)
except Exception as _e:
    print("[GrokBot] WARNING: cannot create", ROOT_DIR, _e)


def log(*parts):
    line = "[GrokBot %s #%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), RUN_ID,
                                    " ".join(str(p) for p in parts))
    print(line)
    try:
        sys.stdout.flush()
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    heartbeat()


def heartbeat():
    if _HAVE_LOCK[0]:
        try:
            os.utime(LOCK_PATH, None)
        except Exception:
            pass


def acquire_lock():
    for _ in range(2):
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write("%s %s %s\n" % (RUN_ID, os.getpid(), datetime.datetime.now().isoformat()))
            _HAVE_LOCK[0] = True
            return True
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(LOCK_PATH)
                with open(LOCK_PATH, "r", encoding="utf-8") as fh:
                    owner = fh.read().strip()
            except Exception:
                age, owner = LOCK_STALE_S + 1, "?"
            if age <= LOCK_STALE_S:
                log("Another GrokBot full-edit run is already in progress (lock: %s, active %.0f s ago). "
                    "This second launch does nothing." % (owner, age))
                return False
            log("Removing stale lock (%s, idle %.0f s)" % (owner, age))
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass
        except Exception as e:
            log("WARNING: could not create lock file (%s); continuing without the single-run guard" % e)
            return True
    return False


def release_lock():
    if _HAVE_LOCK[0]:
        _HAVE_LOCK[0] = False
        try:
            os.remove(LOCK_PATH)
        except Exception:
            pass


class Abort(Exception):
    """Fatal: the run cannot continue (no project, no timeline...)."""


class Skip(Exception):
    """Non-fatal: this step is not possible here; logged as SKIPPED."""


def require(value, what):
    if not value:
        raise Abort("FAILED: " + what)
    return value


def step(name, fn, *args, **kwargs):
    """Run one capability. Abort propagates; anything else is logged as SKIPPED."""
    try:
        out = fn(*args, **kwargs)
        RESULTS.append((name, "OK", ""))
        return out
    except Abort:
        RESULTS.append((name, "FAILED", ""))
        raise
    except Skip as e:
        log("SKIPPED %s: %s" % (name, e))
        RESULTS.append((name, "SKIPPED", str(e)))
    except Exception as e:
        log("SKIPPED %s: %s: %s" % (name, type(e).__name__, e))
        tb = traceback.format_exc().strip().splitlines()
        log("   " + " | ".join(t.strip() for t in tb[-3:]))
        RESULTS.append((name, "SKIPPED", "%s: %s" % (type(e).__name__, e)))
    return None


def stage(title):
    log("")
    log("==== %s ====" % title)
    time.sleep(STAGE_PAUSE)


def to_float(value, default=0.0):
    try:
        return float(str(value).strip().split()[0])
    except Exception:
        return default


def tc_to_frames(tc, fps):
    try:
        parts = [int(p) for p in str(tc).replace(";", ":").split(":")]
        if len(parts) != 4:
            return 0
        h, m, s, f = parts
        return int(round(((h * 60 + m) * 60 + s) * fps)) + f
    except Exception:
        return 0


def frames_to_tc(frame, fps):
    fps_i = int(round(fps))
    f = int(frame)
    h, rem = divmod(f, 3600 * fps_i)
    m, rem = divmod(rem, 60 * fps_i)
    s, ff = divmod(rem, fps_i)
    return "%02d:%02d:%02d:%02d" % (h, m, s, ff)


def fmt_chapter_time(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def unique_base(directory, base, ext):
    if not os.path.exists(os.path.join(directory, base + ext)):
        return base
    n = 2
    while os.path.exists(os.path.join(directory, "%s-%d%s" % (base, n, ext))):
        n += 1
    return "%s-%d" % (base, n)


def open_page(page):
    ok = STATE["res"].OpenPage(page)
    log("OpenPage(%r) -> %s" % (page, ok))
    time.sleep(STAGE_PAUSE)
    return ok


def get_resolve():
    r = globals().get("resolve")
    if r:
        return r
    for getter in (lambda: globals()["bmd"].scriptapp("Resolve"),
                   lambda: globals()["app"].GetResolve()):
        try:
            r = getter()
            if r:
                return r
        except Exception:
            pass
    try:
        import DaVinciResolveScript as dvr
        r = dvr.scriptapp("Resolve")
        if r:
            return r
    except Exception:
        pass
    return None


def get_fusion():
    fu = globals().get("fusion") or globals().get("fu")
    if fu:
        return fu
    try:
        return STATE["res"].Fusion()
    except Exception:
        return None


def item_track(item):
    try:
        t = item.GetTrackTypeAndIndex()
        return "%s%s" % (t[0], t[1])
    except Exception:
        return "?"


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------
def load_manifest():
    stage("1/10 Manifest")
    found = []
    for p in glob.glob(os.path.join(ROOT_DIR, "*", "manifest.json")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                if json.load(fh).get("kind") == MANIFEST_KIND:
                    found.append(p)
        except Exception as e:
            log("  ignoring unreadable manifest %s (%s)" % (p, e))
    if not found:
        raise Abort("FAILED: no manifest with kind=%r under %s/*/manifest.json" % (MANIFEST_KIND, ROOT_DIR))
    found.sort(key=os.path.getmtime, reverse=True)
    path = found[0]
    log("Using manifest:", path, "(%d full-edit manifest(s) found)" % len(found))
    with open(path, "r", encoding="utf-8") as fh:
        m = json.load(fh)
    base = os.path.dirname(os.path.abspath(path))
    m["manifest_path"] = path
    m["manifest_dir"] = base

    def rel(p):
        return os.path.normpath(os.path.join(base, p)) if p else None

    m["project"] = str(require(m.get("project"), "manifest has no 'project'")).strip()
    m["fps"] = to_float(m.get("fps", 30), 30) or 30
    m["width"] = int(m.get("width", 1920))
    m["height"] = int(m.get("height", 1080))
    vs = m.get("vertical_size") or [1080, 1920]
    m["vwidth"], m["vheight"] = int(vs[0]), int(vs[1])
    secs = require(m.get("sections"), "manifest has no 'sections'")
    clean = []
    for i, s in enumerate(secs, 1):
        full = rel(require(s.get("clip"), "section %d has no 'clip'" % i))
        if not os.path.isfile(full):
            log("WARNING: section %d clip not found, dropping it: %s" % (i, full))
            continue
        s = dict(s)
        s["path"] = full
        s["index"] = i
        s.setdefault("key", "section%d" % i)
        s.setdefault("label", s["key"].upper())
        s.setdefault("chapter", s["key"].title())
        s.setdefault("title", s["chapter"])
        s.setdefault("command", "")
        if s.get("marker_color") not in MARKER_COLORS:
            s["marker_color"] = "Blue"
        s.setdefault("clip_color", "Green")
        clean.append(s)
    require(clean, "no usable sections")
    m["sections"] = clean
    brand = m.setdefault("brand", {})
    for k in ("logo_16x9", "logo_9x16", "wordmark", "hero"):
        p = rel(brand.get(k))
        brand[k + "_path"] = p if (p and os.path.isfile(p)) else None
        if brand.get(k) and not brand[k + "_path"]:
            log("WARNING: brand file missing:", brand.get(k))
    brand.setdefault("font", "Open Sans")
    brand.setdefault("font_style", "Bold")
    brand.setdefault("mono_font", "Menlo")
    brand.setdefault("text_rgb", [0.95, 0.97, 1.0])
    brand.setdefault("accent_rgb", [0.37, 0.92, 0.83])
    brand.setdefault("bg_rgb", [0.04, 0.07, 0.12])
    brand.setdefault("bg2_rgb", [0.06, 0.46, 0.43])
    mp = rel(m.get("music"))
    m["music_path"] = mp if (mp and os.path.isfile(mp)) else None
    if m.get("music") and not m["music_path"]:
        log("WARNING: music file not found; continuing without music:", mp)
    m["drx_path"] = rel(m.get("drx")) if m.get("drx") else None
    m["renders_dir"] = os.path.normpath(os.path.join(base, "..", "renders"))
    m["name"] = (m.get("output_name") or "%s-resolve" % m["project"]).strip()
    d = m.setdefault("defaults", {})
    d.setdefault("title", m.get("intro", {}).get("title", m["project"]))
    d.setdefault("subtitle", m.get("intro", {}).get("subtitle", ""))
    d.setdefault("look", "Clean")
    d.setdefault("music_db", -8)
    d.setdefault("pacing", "tight")
    d.setdefault("vertical", True)
    d.setdefault("transitions", "dip")
    d.setdefault("notes", "")
    log("Project %r | %dx%d @ %s fps | %d sections | music: %s"
        % (m["project"], m["width"], m["height"], m["fps"], len(clean), m["music_path"]))
    return m


# --------------------------------------------------------------------------
# 0. Ask the user (inside Resolve)
# --------------------------------------------------------------------------
def default_answers(m):
    d = m["defaults"]
    return {"title": d["title"], "subtitle": d["subtitle"], "look": d["look"],
            "music_db": float(d["music_db"]), "pacing": d["pacing"], "vertical": bool(d["vertical"]),
            "transitions": d["transitions"], "sections": [s["key"] for s in m["sections"]],
            "notes": d.get("notes", ""), "source": "defaults"}


def _idx(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0


def ask_uimanager(m, ans):
    fu = get_fusion()
    if not fu:
        raise Skip("no fusion object")
    ui = getattr(fu, "UIManager", None)
    if not ui:
        raise Skip("fusion.UIManager not available (UI Manager scripting may be Studio-only in this build)")
    bmd = globals().get("bmd")
    disp = None
    for get in (lambda: bmd.UIDispatcher(ui), lambda: __import__("fusionscript").UIDispatcher(ui)):
        try:
            disp = get()
            if disp:
                break
        except Exception:
            pass
    if not disp:
        raise Skip("bmd.UIDispatcher not available")
    secs = [ui.CheckBox({"ID": "Sec_" + s["key"], "Text": "%s  -  %s" % (s["chapter"], s["title"]),
                         "Checked": True}) for s in m["sections"]]
    win = disp.AddWindow(
        {"ID": "GrokBotAsk", "WindowTitle": "Grok Bot - build this edit in Resolve",
         "Geometry": [220, 120, 600, 720]},
        ui.VGroup({"Spacing": 6}, [
            ui.Label({"Text": "<b>Grok Bot is about to build this edit inside DaVinci Resolve.</b><br>"
                              "Change anything you like, then click <b>Build my edit</b>.", "WordWrap": True}),
            ui.Label({"Text": "Video title"}), ui.LineEdit({"ID": "Title", "Text": ans["title"]}),
            ui.Label({"Text": "Subtitle / tagline"}), ui.LineEdit({"ID": "Subtitle", "Text": ans["subtitle"]}),
            ui.HGroup([ui.Label({"Text": "Look"}), ui.ComboBox({"ID": "Look"})]),
            ui.HGroup([ui.Label({"Text": "Pacing"}), ui.ComboBox({"ID": "Pacing"})]),
            ui.HGroup([ui.Label({"Text": "Transitions"}), ui.ComboBox({"ID": "Transitions"})]),
            ui.HGroup([ui.Label({"Text": "Music level (dB)"}),
                       ui.SpinBox({"ID": "MusicDb", "Minimum": -40, "Maximum": 6, "Value": int(ans["music_db"])})]),
            ui.Label({"Text": "Sections to include"}),
            ui.VGroup(secs),
            ui.CheckBox({"ID": "Vertical", "Text": "Also build a vertical 9:16 timeline (Shorts / Reels)",
                         "Checked": bool(ans["vertical"])}),
            ui.Label({"Text": "Anything you'd like changed? Grok Bot reads this after the run."}),
            ui.TextEdit({"ID": "Notes", "PlainText": ans["notes"]}),
            ui.HGroup([ui.Button({"ID": "Cancel", "Text": "Cancel"}),
                       ui.Button({"ID": "Build", "Text": "Build my edit", "Default": True})]),
        ]))
    items = win.GetItems()
    items["Look"].AddItems(LOOKS)
    items["Look"].CurrentIndex = _idx(LOOKS, ans["look"])
    items["Pacing"].AddItems(PACINGS)
    items["Pacing"].CurrentIndex = _idx(PACINGS, ans["pacing"])
    items["Transitions"].AddItems(["dip (Fusion fade through black)", "none (hard cuts)"])
    items["Transitions"].CurrentIndex = _idx(TRANSITIONS, ans["transitions"])
    result = {"ok": False}

    def on_build(ev):
        result["ok"] = True
        disp.ExitLoop()

    def on_cancel(ev):
        disp.ExitLoop()

    win.On.Build.Clicked = on_build
    win.On.Cancel.Clicked = on_cancel
    win.On.GrokBotAsk.Close = on_cancel
    log("Showing the Grok Bot dialog (UIManager) - waiting for Build / Cancel")
    win.Show()
    disp.RunLoop()
    win.Hide()
    if not result["ok"]:
        return None
    out = dict(ans)
    out.update({"title": items["Title"].Text, "subtitle": items["Subtitle"].Text,
                "look": LOOKS[int(items["Look"].CurrentIndex)],
                "pacing": PACINGS[int(items["Pacing"].CurrentIndex)],
                "transitions": TRANSITIONS[int(items["Transitions"].CurrentIndex)],
                "music_db": float(items["MusicDb"].Value),
                "vertical": bool(items["Vertical"].Checked),
                "sections": [s["key"] for s in m["sections"] if items["Sec_" + s["key"]].Checked],
                "notes": items["Notes"].PlainText, "source": "UIManager dialog"})
    return out


def ask_fusion_askuser(m, ans):
    fu = get_fusion()
    comp = fu.GetCurrentComp() if fu else None
    if not comp:
        raise Skip("no current Fusion composition for AskUser")
    controls = {
        1: {1: "Title", 2: "Text", "Name": "Video title", "Default": ans["title"]},
        2: {1: "Subtitle", 2: "Text", "Name": "Subtitle / tagline", "Default": ans["subtitle"]},
        3: {1: "Look", 2: "Dropdown", "Name": "Look", "Options": dict((i + 1, v) for i, v in enumerate(LOOKS)),
            "Default": _idx(LOOKS, ans["look"])},
        4: {1: "Pacing", 2: "Dropdown", "Name": "Pacing", "Options": {1: "tight", 2: "relaxed"},
            "Default": _idx(PACINGS, ans["pacing"])},
        5: {1: "Transitions", 2: "Dropdown", "Name": "Transitions", "Options": {1: "dip", 2: "none"},
            "Default": _idx(TRANSITIONS, ans["transitions"])},
        6: {1: "MusicDb", 2: "Slider", "Name": "Music level (dB)", "Min": -40, "Max": 6, "Integer": True,
            "Default": ans["music_db"]},
        7: {1: "Vertical", 2: "Checkbox", "Name": "Also build a vertical 9:16 timeline", "Default": 1 if ans["vertical"] else 0},
    }
    n = 8
    for s in m["sections"]:
        controls[n] = {1: "Sec_" + s["key"], 2: "Checkbox", "Name": "Include: " + s["chapter"], "Default": 1}
        n += 1
    controls[n] = {1: "Notes", 2: "Text", "Name": "Anything you'd like changed?", "Lines": 4, "Default": ans["notes"]}
    log("Showing the Grok Bot dialog (Fusion AskUser) - waiting for OK / Cancel")
    r = comp.AskUser("Grok Bot - build this edit in Resolve", controls)
    if r is None:
        return None
    out = dict(ans)
    out.update({"title": r.get("Title", ans["title"]), "subtitle": r.get("Subtitle", ans["subtitle"]),
                "look": LOOKS[int(r.get("Look", 0))], "pacing": PACINGS[int(r.get("Pacing", 0))],
                "transitions": TRANSITIONS[int(r.get("Transitions", 0))],
                "music_db": float(r.get("MusicDb", ans["music_db"])), "vertical": bool(int(r.get("Vertical", 1))),
                "sections": [s["key"] for s in m["sections"] if int(r.get("Sec_" + s["key"], 1))],
                "notes": r.get("Notes", ""), "source": "Fusion AskUser dialog"})
    return out


def _osa(script, timeout=200):
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _osa_q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


def ask_osascript(m, ans, give_up=90):
    if sys.platform != "darwin":
        raise Skip("native dialog fallback is macOS-only")
    title = _osa_q("Grok Bot - DaVinci Resolve")
    summary = ("Grok Bot will build \"%s\" in Resolve: look %s, %s pacing, %s transitions, music %+.0f dB, "
               "%d sections%s." % (ans["title"], ans["look"], ans["pacing"], ans["transitions"], ans["music_db"],
                                   len(ans["sections"]), ", plus a vertical 9:16 timeline" if ans["vertical"] else ""))
    rc, out, err = _osa('display dialog %s with title %s buttons {"Cancel", "Customize", "Build my edit"} '
                        'default button "Build my edit" giving up after %d' % (_osa_q(summary), title, give_up))
    if rc != 0:
        return None                                      # Cancel
    res = dict(ans, source="macOS dialog (defaults)")
    if "Customize" not in out:
        return res

    def text(prompt, default):
        rc, o, _ = _osa('text returned of (display dialog %s default answer %s with title %s giving up after %d)'
                        % (_osa_q(prompt), _osa_q(default), title, give_up))
        return o if rc == 0 else default

    def choose(prompt, options, default, multi=False):
        lst = "{" + ", ".join(_osa_q(o) for o in options) + "}"
        dflt = "{" + ", ".join(_osa_q(o) for o in (default if multi else [default])) + "}"
        rc, o, _ = _osa('choose from list %s with prompt %s default items %s%s'
                        % (lst, _osa_q(prompt), dflt, " with multiple selections allowed" if multi else ""))
        if rc != 0 or o in ("", "false"):
            return default
        return [x.strip() for x in o.split(", ")] if multi else o

    res["title"] = text("Video title", ans["title"])
    res["subtitle"] = text("Subtitle / tagline", ans["subtitle"])
    res["look"] = choose("Look", LOOKS, ans["look"])
    res["pacing"] = choose("Pacing", PACINGS, ans["pacing"])
    res["transitions"] = choose("Transitions", TRANSITIONS, ans["transitions"])
    res["music_db"] = to_float(text("Music level in dB (e.g. -8)", "%g" % ans["music_db"]), ans["music_db"])
    names = [s["chapter"] for s in m["sections"]]
    picked = choose("Sections to include", names, names, multi=True)
    res["sections"] = [s["key"] for s in m["sections"] if s["chapter"] in picked] or ans["sections"]
    rc, o, _ = _osa('button returned of (display dialog "Also build a vertical 9:16 timeline (Shorts / Reels)?" '
                    'with title %s buttons {"No", "Yes"} default button "%s" giving up after %d)'
                    % (title, "Yes" if ans["vertical"] else "No", give_up))
    res["vertical"] = (o == "Yes") if rc == 0 and o else ans["vertical"]
    res["notes"] = text("Anything you'd like changed? Grok Bot reads this after the run.", ans["notes"])
    res["source"] = "macOS dialogs"
    return res


def ask_user(m):
    stage("0/10 Ask the user")
    ans = default_answers(m)
    if not m.get("ask_user", True):
        log("ask_user is false in the manifest; using defaults")
        return ans
    for label, fn in (("UIManager dialog", ask_uimanager), ("Fusion AskUser dialog", ask_fusion_askuser),
                      ("macOS native dialog", ask_osascript)):
        try:
            got = fn(m, ans)
        except Skip as e:
            log("Dialog option %s unavailable: %s" % (label, e))
            RESULTS.append(("Ask: " + label, "SKIPPED", str(e)))
            continue
        except Exception as e:
            log("Dialog option %s failed: %s: %s" % (label, type(e).__name__, e))
            RESULTS.append(("Ask: " + label, "SKIPPED", "%s: %s" % (type(e).__name__, e)))
            continue
        RESULTS.append(("Ask: " + label, "OK", ""))
        if got is None:
            raise Abort("CANCELLED: you clicked Cancel, so nothing was changed in Resolve.")
        ans = got
        break
    else:
        log("No dialog could be shown; using the manifest defaults (no-touch run)")
    if ans["look"] not in LOOKS:
        ans["look"] = "Clean"
    if ans["pacing"] not in PACINGS:
        ans["pacing"] = "tight"
    if ans["transitions"] not in TRANSITIONS:
        ans["transitions"] = "dip"
    if not ans["sections"]:
        log("No sections ticked; using all of them")
        ans["sections"] = [s["key"] for s in m["sections"]]
    log("Answers (%s): %s" % (ans["source"], json.dumps(ans, ensure_ascii=False)))
    if ans.get("notes"):
        log("USER NOTES for Grok Bot: " + ans["notes"].replace("\n", " / "))
    try:                                             # remember the answers next to the manifest
        with open(m["manifest_path"], "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        raw.setdefault("history", []).append(dict(ans, run_id=RUN_ID, at=datetime.datetime.now().isoformat()))
        raw["history"] = raw["history"][-20:]
        with open(m["manifest_path"], "w", encoding="utf-8") as fh:
            json.dump(raw, fh, indent=2, ensure_ascii=False)
        log("Saved answers + notes to manifest history")
    except Exception as e:
        log("NOTE: could not save answers to the manifest (%s)" % e)
    return ans


# --------------------------------------------------------------------------
# 1. Project
# --------------------------------------------------------------------------
def fps_setting_value(fps):
    return str(int(fps)) if float(fps).is_integer() else ("%.3f" % fps).rstrip("0").rstrip(".")


def stage_project(m):
    stage("2/10 Project")
    res = STATE["res"]
    pm = require(res.GetProjectManager(), "GetProjectManager")
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() == m["project"]:
        project = cur
        log("Project already open:", m["project"])
    else:
        if cur:
            log("Saving current project before switching:", cur.GetName(), "->", pm.SaveProject())
        project = pm.CreateProject(m["project"])
        if project:
            log("Created project:", m["project"])
        else:
            project = require(pm.LoadProject(m["project"]), "LoadProject(%s)" % m["project"])
            log("Loaded existing project:", m["project"])
    fps_val = fps_setting_value(m["fps"])
    for key, val in [("timelineResolutionWidth", str(m["width"])),
                     ("timelineResolutionHeight", str(m["height"])),
                     ("timelineFrameRate", fps_val),
                     ("timelineInputResMismatchBehavior", "scaleToCrop"),
                     ("colorScienceMode", "davinciYRGB"),
                     ("timelinePlaybackFrameRate", fps_val)]:
        ok = project.SetSetting(key, val)
        log("SetSetting(%s=%s) -> %s   now: %s" % (key, val, ok, project.GetSetting(key)))
    if abs(to_float(project.GetSetting("timelineFrameRate")) - m["fps"]) > 0.01:
        log("WARNING: project frame rate is %s, not %s (locked once a timeline exists). "
            "Delete the project and re-run for a clean result." % (project.GetSetting("timelineFrameRate"), m["fps"]))
    STATE.update(pm=pm, project=project)
    return project


# --------------------------------------------------------------------------
# 2. Media page
# --------------------------------------------------------------------------
def find_or_add_folder(mp, parent, name):
    for f in (parent.GetSubFolderList() or []):
        if f.GetName() == name:
            log("Bin exists:", name)
            return f
    f = require(mp.AddSubFolder(parent, name), "AddSubFolder(%s)" % name)
    log("Created bin:", name)
    return f


def import_into(mp, folder, paths):
    require(mp.SetCurrentFolder(folder), "SetCurrentFolder(%s)" % folder.GetName())
    have = {}
    for item in (folder.GetClipList() or []):
        fp = item.GetClipProperty("File Path") or ""
        if fp:
            have[os.path.normpath(fp)] = item
    todo = [p for p in dict.fromkeys(paths) if p not in have]
    for p in paths:
        if p in have:
            log("Already in bin:", os.path.basename(p))
    if todo:
        log("ImportMedia: %d file(s) into %s" % (len(todo), folder.GetName()))
        got = mp.ImportMedia(todo) or []
        log("ImportMedia returned %d item(s)" % len(got))
        for item in got:
            have[os.path.normpath(item.GetClipProperty("File Path") or "")] = item
    missing = [p for p in paths if p not in have]
    if missing:
        log("WARNING: could not import: %s" % ", ".join(missing))
    return have


def clip_fps(item, fallback):
    f = to_float(item.GetClipProperty("FPS"))
    return f if f > 0 else fallback


def clip_frames(item, fps):
    n = int(to_float(item.GetClipProperty("Frames")))
    if n > 0:
        return n
    dur = item.GetClipProperty("Duration")
    return tc_to_frames(dur, fps) if dur else 0


def clip_res(item, default):
    r = str(item.GetClipProperty("Resolution") or "")
    try:
        w, h = [int(x) for x in r.lower().split("x")[:2]]
        return w, h
    except Exception:
        return default


def stage_media(m, ans):
    stage("3/10 Media page: bins, import, metadata")
    open_page("media")
    project = STATE["project"]
    mp = require(project.GetMediaPool(), "GetMediaPool")
    root = require(mp.GetRootFolder(), "GetRootFolder")
    top = find_or_add_folder(mp, root, m["project"])
    bins = {k: find_or_add_folder(mp, top, k) for k in ("Footage", "Selects", "Audio", "Graphics")}
    STATE.update(mp=mp, bins=bins)

    raw = import_into(mp, bins["Footage"], [s["path"] for s in m["sections"]])
    for s in m["sections"]:
        s["item"] = raw.get(s["path"])
    m["sections"] = [s for s in m["sections"] if s.get("item")]
    require(m["sections"], "none of the raw clips imported")
    for s in m["sections"]:
        w, h = clip_res(s["item"], (0, 0))
        f = clip_fps(s["item"], 0)
        if (w, h) != (m["width"], m["height"]) or abs(f - m["fps"]) > 0.01:
            log("NOTE: %s is %dx%d @ %.3f fps vs timeline %dx%d @ %s: scale-to-crop fills the frame, "
                "Resolve conforms the frame rate" % (s["key"], w, h, f, m["width"], m["height"], m["fps"]))
    if m["music_path"]:
        m["music_item"] = import_into(mp, bins["Audio"], [m["music_path"]]).get(m["music_path"])
    gfx = [m["brand"][k] for k in ("logo_16x9_path", "logo_9x16_path", "wordmark_path", "hero_path") if m["brand"].get(k)]
    g = import_into(mp, bins["Graphics"], gfx) if gfx else {}
    for k in ("logo_16x9", "logo_9x16", "wordmark", "hero"):
        m["brand"][k + "_item"] = g.get(m["brand"].get(k + "_path"))

    step("Media: clip colours (SetClipColor)", media_colors, m, ans)
    step("Media: metadata + keywords (SetMetadata)", media_metadata, m, ans)
    step("Media: flags (AddFlag)", media_flags, m, ans)
    step("Media: select-range markers on source clips (MediaPoolItem.AddMarker)", media_markers, m, ans)
    step("Media: sub-clips of the selects (MediaStorage.AddItemListToMediaPool)", media_subclips, m, ans)


def section_range(s, ans, item, fps):
    """(startFrame, endFrame_exclusive, source_fps) in SOURCE frames for this pacing."""
    sfps = clip_fps(item, fps)
    a, b = s.get(ans["pacing"]) or s.get("tight") or [0, 0]
    total = clip_frames(item, sfps)
    start = max(0, int(round(float(a) * sfps)))
    end = int(round(float(b) * sfps)) if b else total
    if total:
        end = min(end, total)
    if end <= start:
        start, end = 0, total
    return start, end, sfps


def media_colors(m, ans):
    for s in m["sections"]:
        log("SetClipColor(%s, %s) -> %s" % (os.path.basename(s["path"]), s["clip_color"], s["item"].SetClipColor(s["clip_color"])))
    if m.get("music_item"):
        log("SetClipColor(music, Purple) -> %s" % m["music_item"].SetClipColor("Purple"))
    for k in ("logo_16x9", "logo_9x16", "wordmark", "hero"):
        it = m["brand"].get(k + "_item")
        if it:
            log("SetClipColor(%s, Pink) -> %s" % (k, it.SetClipColor("Pink")))


def media_metadata(m, ans):
    for s in m["sections"]:
        meta = {"Keywords": ", ".join(s.get("keywords") or [s["key"]]),
                "Description": s["title"], "Comments": "Command: " + s["command"],
                "Scene": s["chapter"], "Shot": s["key"]}
        ok = s["item"].SetMetadata(meta)
        if not ok:
            ok = dict((k, s["item"].SetMetadata(k, v)) for k, v in meta.items())
        log("SetMetadata(%s) -> %s" % (s["key"], ok))
    try:
        log("Readback %s metadata: %s" % (m["sections"][0]["key"], m["sections"][0]["item"].GetMetadata()))
    except Exception:
        pass


def media_flags(m, ans):
    for s in m["sections"]:
        color = "Green" if s["key"] in ans["sections"] else "Red"
        log("AddFlag(%s, %s) -> %s" % (s["key"], color, s["item"].AddFlag(color)))


def media_markers(m, ans):
    for s in m["sections"]:
        a, b, sfps = section_range(s, ans, s["item"], m["fps"])
        ok = s["item"].AddMarker(a, "Green", "Select (%s)" % ans["pacing"], s["command"], max(1, b - a), "grokbot-select")
        log("MediaPoolItem.AddMarker(%s, src %d, %d frames) -> %s" % (s["key"], a, b - a, ok))


def media_subclips(m, ans):
    storage = STATE["res"].GetMediaStorage()
    if not storage:
        raise Skip("GetMediaStorage returned nothing")
    mp = STATE["mp"]
    mp.SetCurrentFolder(STATE["bins"]["Selects"])
    existing = set(i.GetName() for i in (STATE["bins"]["Selects"].GetClipList() or []))
    for s in m["sections"]:
        if s["key"] not in ans["sections"]:
            continue
        a, b, _ = section_range(s, ans, s["item"], m["fps"])
        name = "%s select (%s)" % (s["chapter"], ans["pacing"])
        if name in existing:
            log("Sub-clip exists:", name)
            continue
        got = storage.AddItemListToMediaPool([{"media": s["path"], "startFrame": a, "endFrame": b - 1}]) or []
        if got:
            try:
                got[0].SetName(name)
            except Exception:
                pass
            got[0].SetClipColor(s["clip_color"])
        log("Sub-clip %r src %d-%d -> %s" % (name, a, b - 1, bool(got)))


# --------------------------------------------------------------------------
# Fusion helpers (edits happen in each item's own Fusion composition)
# --------------------------------------------------------------------------
def fz_add(comp, tool_id, name=None):
    t = comp.AddTool(tool_id, -32768, -32768)
    if not t:
        raise Skip("Fusion AddTool(%s) failed" % tool_id)
    if name:
        try:
            t.SetAttrs({"TOOLS_Name": name})
        except Exception:
            pass
    return t


def fz_anim(tool, inp, keys):
    """Keyframe a number input: keys = [(time, value), ...]."""
    tool.AddModifier(inp, "BezierSpline")
    for t, v in keys:
        tool.SetInput(inp, v, t)


def fz_point_anim(tool, inp, keys):
    try:
        tool.AddModifier(inp, "XYPath")
        for t, (x, y) in keys:
            tool.SetInput(inp, {1: x, 2: y, 3: 0.0}, t)
        return True
    except Exception as e:
        log("   (point animation on %s skipped: %s)" % (inp, e))
        return False


def fz_size(tool, w, h):
    if w and h:
        tool.SetInput("UseFrameFormatSettings", 0)
        tool.SetInput("Width", int(w))
        tool.SetInput("Height", int(h))


def fz_text(comp, text, size, rgb, font, style, center, w=None, h=None, name=None):
    t = fz_add(comp, "TextPlus", name)
    fz_size(t, w, h)
    t.SetInput("StyledText", text)
    t.SetInput("Font", font)
    t.SetInput("Style", style)
    t.SetInput("Size", size)
    t.SetInput("Red1", rgb[0])
    t.SetInput("Green1", rgb[1])
    t.SetInput("Blue1", rgb[2])
    t.SetInput("Center", {1: center[0], 2: center[1], 3: 0.0})
    return t


def fz_bg(comp, rgb, alpha=1.0, w=None, h=None, rgb2=None, name=None):
    b = fz_add(comp, "Background", name)
    fz_size(b, w, h)
    if rgb2:
        b.SetInput("Type", 3)                                   # four-corner gradient
        for corner, c in (("TopLeft", rgb), ("TopRight", rgb), ("BottomLeft", rgb), ("BottomRight", rgb2)):
            b.SetInput(corner + "Red", c[0])
            b.SetInput(corner + "Green", c[1])
            b.SetInput(corner + "Blue", c[2])
            b.SetInput(corner + "Alpha", alpha)
    else:
        b.SetInput("TopLeftRed", rgb[0])
        b.SetInput("TopLeftGreen", rgb[1])
        b.SetInput("TopLeftBlue", rgb[2])
        b.SetInput("TopLeftAlpha", alpha)
    return b


def fz_merge(comp, bg, fg, name=None):
    mg = fz_add(comp, "Merge", name)
    mg.ConnectInput("Background", bg)
    mg.ConnectInput("Foreground", fg)
    return mg


def comp_range(comp, fallback_len):
    try:
        a = comp.GetAttrs()
        t0, t1 = int(a.get("COMPN_RenderStart", 0)), int(a.get("COMPN_RenderEnd", fallback_len - 1))
        if t1 > t0:
            return t0, t1
    except Exception:
        pass
    return 0, fallback_len - 1


def item_comp(item, create=True):
    n = int(item.GetFusionCompCount() or 0)
    if n:
        return item.GetFusionCompByIndex(1)
    if create:
        return item.AddFusionComp()
    return None


def with_comp(comp, fn):
    for meth, args in (("Lock", ()), ("StartUndo", ("GrokBot",))):
        try:
            getattr(comp, meth)(*args)
        except Exception:
            pass
    try:
        return fn()
    finally:
        for meth, args in (("EndUndo", (True,)), ("Unlock", ())):
            try:
                getattr(comp, meth)(*args)
            except Exception:
                pass


def style_title_item(item, m, title, subtitle, fade_frames=12, logo=True):
    """Text+ Fusion title: brand gradient plate, wordmark (Loader), title slide-up, subtitle fade, fade out."""
    comp = item.GetFusionCompByIndex(1) if int(item.GetFusionCompCount() or 0) else None
    if not comp:
        raise Skip("title has no Fusion composition")
    b = m["brand"]
    dur = int(item.GetDuration() or 150)

    def build():
        tpl = comp.FindTool("Template")
        mo = comp.FindTool("MediaOut1")
        if not tpl or not mo:
            raise Skip("Text+ template tools not found (Template / MediaOut1)")
        t0, t1 = comp_range(comp, dur)
        tpl.SetInput("StyledText", title)
        tpl.SetInput("Font", b["font"])
        tpl.SetInput("Style", b["font_style"])
        tpl.SetInput("Size", 0.11 if len(title) < 18 else 0.07)
        for c, v in zip(("Red1", "Green1", "Blue1"), b["text_rgb"]):
            tpl.SetInput(c, v)
        plate = fz_bg(comp, b["bg_rgb"], 1.0, rgb2=b["bg2_rgb"], name="GrokBotPlate")
        last = plate
        if logo and b.get("wordmark_path"):
            try:
                ld = fz_add(comp, "Loader", "GrokBotWordmark")
                ld.SetInput("Clip", b["wordmark_path"])
                xf = fz_add(comp, "Transform", "GrokBotWordmarkXf")
                xf.ConnectInput("Input", ld)
                xf.SetInput("Size", 0.35)
                xf.SetInput("Center", {1: 0.5, 2: 0.78, 3: 0.0})
                last = fz_merge(comp, last, xf, "GrokBotLogoMerge")
                log("   title: wordmark Loader added")
            except Exception as e:
                log("   title: wordmark Loader skipped (%s)" % e)
        mt = fz_merge(comp, last, tpl, "GrokBotTitleMerge")
        fz_anim(mt, "Blend", [(t0, 0.0), (t0 + fade_frames, 1.0)])
        fz_point_anim(mt, "Center", [(t0, (0.5, 0.46)), (t0 + fade_frames + 6, (0.5, 0.5))])
        last = mt
        if subtitle:
            sub = fz_text(comp, subtitle, 0.038, b["accent_rgb"], b["font"], "Regular", (0.5, 0.36), name="GrokBotSubtitle")
            ms = fz_merge(comp, last, sub, "GrokBotSubtitleMerge")
            fz_anim(ms, "Blend", [(t0 + fade_frames, 0.0), (t0 + 2 * fade_frames, 1.0)])
            last = ms
        out = fz_add(comp, "BrightnessContrast", "GrokBotFadeOut")
        out.ConnectInput("Input", last)
        fz_anim(out, "Gain", [(t0, 0.0), (t0 + 8, 1.0), (t1 - fade_frames, 1.0), (t1, 0.0)])
        mo.ConnectInput("Input", out)
        return t0, t1

    t0, t1 = with_comp(comp, build)
    log("   Fusion title styled: %r / %r (comp frames %d-%d, plate + slide-up + fades)" % (title, subtitle, t0, t1))


def build_clip_comp(item, s, m, ans, card_frames, dip_frames):
    """Per-clip Fusion comp: slow push-in, dip-to-black, section title card, animated lower third."""
    comp = item_comp(item)
    if not comp:
        raise Skip("AddFusionComp returned nothing")
    b = m["brand"]
    w, h = clip_res(s["item"], (m["width"], m["height"]))
    dur = int(item.GetDuration() or 100)

    def build():
        mi = comp.FindTool("MediaIn1")
        mo = comp.FindTool("MediaOut1")
        if not mi or not mo:
            raise Skip("MediaIn1/MediaOut1 not found in the clip's comp")
        t0, t1 = comp_range(comp, dur)
        xf = fz_add(comp, "Transform", "GrokBotPush")
        xf.ConnectInput("Input", mi)
        fz_anim(xf, "Size", [(t0, 1.0), (t1, 1.035)])
        last = xf
        if ans["transitions"] == "dip":
            dip = fz_add(comp, "BrightnessContrast", "GrokBotDip")
            dip.ConnectInput("Input", last)
            fz_anim(dip, "Gain", [(t0, 0.0), (t0 + dip_frames, 1.0), (t1 - dip_frames, 1.0), (t1, 0.0)])
            last = dip
        plate = fz_bg(comp, b["bg_rgb"], 0.86, w, h, name="GrokBotCardPlate")
        lab = fz_text(comp, s["label"], 0.032, b["accent_rgb"], b["font"], b["font_style"], (0.5, 0.6), w, h, "GrokBotCardLabel")
        ttl = fz_text(comp, s["title"], 0.05 if len(s["title"]) < 34 else 0.038, b["text_rgb"], b["font"],
                      b["font_style"], (0.5, 0.48), w, h, "GrokBotCardTitle")
        card = fz_merge(comp, fz_merge(comp, plate, lab, "GrokBotCardM1"), ttl, "GrokBotCardM2")
        mc = fz_merge(comp, last, card, "GrokBotCard")
        fz_anim(mc, "Blend", [(t0, 1.0), (t0 + card_frames - 8, 1.0), (t0 + card_frames, 0.0)])
        last = mc
        if s.get("command"):
            cmd = "$ " + s["command"]
            size = max(0.016, min(0.03, 0.85 / (max(len(cmd), 10) * 0.62)))
            ltp = fz_bg(comp, b["bg_rgb"], 0.82, w, h, name="GrokBotLTPlate")
            try:
                rect = fz_add(comp, "RectangleMask", "GrokBotLTMask")
                rect.SetInput("Center", {1: 0.5, 2: 0.15, 3: 0.0})
                rect.SetInput("Width", min(0.95, len(cmd) * size * 0.62 + 0.06))
                rect.SetInput("Height", size * 2.2)
                rect.SetInput("CornerRadius", 0.3)
                ltp.ConnectInput("EffectMask", rect)
            except Exception as e:
                log("   lower-third mask skipped (%s)" % e)
            ltt = fz_text(comp, cmd, size, b["accent_rgb"], b["mono_font"], "Regular", (0.5, 0.15), w, h, "GrokBotLTText")
            lt = fz_merge(comp, ltp, ltt, "GrokBotLTM")
            ml = fz_merge(comp, last, lt, "GrokBotLowerThird")
            fade = 8
            a = t0 + card_frames
            z = max(a + 2 * fade + 1, t1 - dip_frames - 4)
            fz_anim(ml, "Blend", [(t0, 0.0), (a, 0.0), (a + fade, 1.0), (z - fade, 1.0), (z, 0.0)])
            fz_point_anim(ml, "Center", [(a, (0.46, 0.5)), (a + fade + 4, (0.5, 0.5))])
            last = ml
        mo.ConnectInput("Input", last)
        return t0, t1

    t0, t1 = with_comp(comp, build)
    log("   Fusion comp on %s: push-in, %s, title card %d f, lower third (comp %d-%d, clip %dx%d)"
        % (s["key"], "dip %d f" % dip_frames if ans["transitions"] == "dip" else "no dip", card_frames, t0, t1, w, h))


def style_generator(item, m, text):
    comp = item.GetFusionCompByIndex(1) if int(item.GetFusionCompCount() or 0) else None
    if not comp:
        raise Skip("generator has no Fusion comp to style")
    b = m["brand"]

    def build():
        mo = comp.FindTool("MediaOut1")
        if not mo:
            raise Skip("MediaOut1 not found in generator comp")
        src = None
        try:
            src = mo.Input.GetConnectedOutput().GetTool()
        except Exception:
            pass
        plate = fz_bg(comp, b["bg_rgb"], 1.0, rgb2=b["bg2_rgb"], name="GrokBotEndPlate")
        base = plate
        if src:
            tint = fz_merge(comp, plate, src, "GrokBotEndTexture")
            tint.SetInput("Blend", 0.18)
            base = tint
        txt = fz_text(comp, text, 0.034, b["accent_rgb"], b["font"], b["font_style"], (0.5, 0.12), name="GrokBotEndText")
        mo.ConnectInput("Input", fz_merge(comp, base, txt, "GrokBotEndMerge"))

    with_comp(comp, build)
    log("   End-screen generator styled (brand gradient, %r)" % text)


# --------------------------------------------------------------------------
# 3. Edit page
# --------------------------------------------------------------------------
def unique_timeline_name(project, base):
    names = set()
    for i in range(1, int(project.GetTimelineCount() or 0) + 1):
        tl = project.GetTimelineByIndex(i)
        if tl:
            names.add(tl.GetName())
    if base not in names:
        return base
    n = 2
    while "%s %d" % (base, n) in names:
        n += 1
    return "%s %d" % (base, n)


def create_timeline(base):
    project, mp = STATE["project"], STATE["mp"]
    tried = []
    for attempt in range(5):
        name = unique_timeline_name(project, base)
        if name in tried:
            name = "%s %d" % (base, len(tried) + 1)
        tried.append(name)
        tl = mp.CreateEmptyTimeline(name)
        if tl:
            return tl, name
        time.sleep(0.5)
    raise Abort("FAILED: CreateEmptyTimeline (tried %s)" % ", ".join(repr(t) for t in tried))


def track_end(timeline, kind, idx, default):
    try:
        items = timeline.GetItemListInTrack(kind, idx) or []
        return max([int(i.GetEnd()) for i in items] + [default])
    except Exception:
        return default


def insert_at(timeline, frame, fps, inserter, what):
    """Move the playhead to `frame` (absolute) and insert a title/generator there."""
    ok = timeline.SetCurrentTimecode(frames_to_tc(frame, fps))
    item = inserter()
    if not item:
        raise Skip("%s returned nothing" % what)
    st = int(item.GetStart())
    log("%s at %s (SetCurrentTimecode -> %s) -> %s %d-%d (%d frames)"
        % (what, frames_to_tc(frame, fps), ok, item_track(item), st, int(item.GetEnd()) - 1, int(item.GetDuration() or 0)))
    if st != frame:
        log("WARNING: %s landed at %d, expected %d" % (what, st, frame))
    return item


def stage_edit(m, ans):
    stage("4/10 Edit page: timeline, Fusion titles, overlays, markers")
    open_page("edit")
    project, mp = STATE["project"], STATE["mp"]
    timeline, name = create_timeline("%s - Grok Bot edit" % ans["title"])
    project.SetCurrentTimeline(timeline)
    tl_start = int(timeline.GetStartFrame() or 0)
    tw = int(to_float(timeline.GetSetting("timelineResolutionWidth")))
    th = int(to_float(timeline.GetSetting("timelineResolutionHeight")))
    log("Created timeline %r, start %d, %sx%s @ %s" % (name, tl_start, tw, th, timeline.GetSetting("timelineFrameRate")))
    if (tw, th) != (m["width"], m["height"]):
        log("WARNING: timeline is %dx%d, manifest wants %dx%d" % (tw, th, m["width"], m["height"]))
    STATE.update(timeline=timeline, tl_start=tl_start, tl_name=name)
    fps = m["fps"]
    tight = ans["pacing"] == "tight"
    card_frames = int(round((1.6 if tight else 2.6) * fps))
    dip_frames = 6 if tight else 12

    rec = tl_start
    intro = step("Edit: intro Text+ title (InsertFusionTitleIntoTimeline)", insert_at, timeline, rec, fps,
                 lambda: timeline.InsertFusionTitleIntoTimeline("Text+"), "InsertFusionTitleIntoTimeline('Text+')")
    if intro:
        step("Fusion: style intro title (Text+, Background, Loader, Merge, keyframes)", style_title_item,
             intro, m, ans["title"], ans["subtitle"])
        rec = int(intro.GetEnd())
        m["intro_item"] = intro

    placed = []
    for s in m["sections"]:
        if s["key"] not in ans["sections"]:
            log("Section %s not selected; skipping" % s["key"])
            continue
        a, b, sfps = section_range(s, ans, s["item"], fps)
        got = []
        for end in (b, b - 1):                     # Resolve 21: endFrame is exclusive; retry once if refused
            info = {"mediaPoolItem": s["item"], "startFrame": a, "endFrame": end, "trackIndex": 1,
                    "recordFrame": rec, "mediaType": 1}
            got = mp.AppendToTimeline([info]) or []
            if got:
                break
            info.pop("mediaType")
            got = mp.AppendToTimeline([info]) or []
            if got:
                break
        if not got:
            log("WARNING: AppendToTimeline(%s) failed; section dropped" % s["key"])
            continue
        it = ([g for g in got if item_track(g).startswith("video")] or got)[0]
        st, en = int(it.GetStart()), int(it.GetEnd())
        log("V1 %-10s src %d-%d of %s @ %.3f fps -> rec %d-%d (%d tl frames)%s"
            % (s["key"], a, b - 1, s["item"].GetClipProperty("Frames"), sfps, st, en - 1, en - st,
               "" if st == rec else "  <-- WARNING: expected %d" % rec))
        s["tl_item"] = it
        placed.append(s)
        rec = en
        time.sleep(0.2)
    require(placed, "no clips on the timeline")
    picture_end = rec
    STATE["placed"] = placed

    for s in placed:
        step("Edit: item colour/name/flag (%s)" % s["key"], item_basics, s, m)
        step("Edit: transform/zoom + retime (SetProperty) (%s)" % s["key"], item_transform, s, m)
        step("Fusion: clip comp - title card, lower third, push-in, dip (%s)" % s["key"],
             build_clip_comp, s["tl_item"], s, m, ans, card_frames, dip_frames)

    outro = step("Edit: outro Text+ title", insert_at, timeline, picture_end, fps,
                 lambda: timeline.InsertFusionTitleIntoTimeline("Text+"), "InsertFusionTitleIntoTimeline('Text+') outro")
    if outro:
        o = m.get("outro", {})
        step("Fusion: style outro title", style_title_item, outro, m, o.get("title", "Subscribe for more tutorials"),
             o.get("subtitle", ""), 12, True)
        picture_end = max(picture_end, int(outro.GetEnd()))
        m["outro_item"] = outro
    gen = step("Edit: end-screen generator (InsertFusionGeneratorIntoTimeline)", insert_generator, timeline, picture_end, fps)
    if gen:
        step("Fusion: style end-screen generator", style_generator, gen, m, m.get("endscreen", {}).get("text", ""))
        picture_end = max(picture_end, int(gen.GetEnd()))
    picture_end = max(picture_end, track_end(timeline, "video", 1, picture_end))
    total = picture_end - tl_start
    STATE["total"] = total
    log("Picture runs %d frames (%.2f s)" % (total, total / fps))

    step("Edit: logo overlay on V2 (AppendToTimeline trackIndex 2 + Opacity)", place_logo, timeline, m, placed, 2, "logo_16x9")
    step("Edit: chapter markers (Timeline.AddMarker)", add_markers, timeline, m, placed)
    step("Edit: track names (SetTrackName)", name_tracks, timeline)
    return timeline


def item_basics(s, m):
    it = s["tl_item"]
    log("TimelineItem %s: SetClipColor(%s) -> %s, AddFlag(Green) -> %s"
        % (s["key"], s["clip_color"], it.SetClipColor(s["clip_color"]), it.AddFlag("Green")))
    try:
        log("   SetName(%r) -> %s" % (s["chapter"], it.SetName(s["chapter"])))
    except Exception as e:
        log("   SetName not available (%s)" % e)


def item_transform(s, m):
    it = s["tl_item"]
    z = float(s.get("punch_in") or 1.0)
    props = [("RetimeProcess", 1)]                    # nearest frame: crisp text for 25->30 fps screen recordings
    if z > 1.0:
        # punch-in anchored to the top-left, where the terminal prompt lives
        props += [("ZoomX", z), ("ZoomY", z),
                  ("Pan", round(m["width"] * (z - 1) / 2.0, 1)), ("Tilt", round(-m["height"] * (z - 1) / 2.0, 1))]
    for k, v in props:
        log("   %s SetProperty(%s, %s) -> %s" % (s["key"], k, v, it.SetProperty(k, v)))
    try:
        got = it.GetProperty()
        if isinstance(got, dict) and not STATE.get("logged_props"):
            STATE["logged_props"] = True
            log("   TimelineItem properties exposed: %s" % ", ".join(sorted(str(k) for k in got)))
            if not any(str(k).lower() in ("speed", "retimespeed", "clipspeed") for k in got):
                log("SKIPPED Edit: clip speed change: no speed property in the API (use Retime Controls in the UI)")
                RESULTS.append(("Edit: clip speed change", "SKIPPED", "no speed property exposed"))
    except Exception:
        pass


def insert_generator(timeline, frame, fps):
    for gname in FUSION_GENERATORS:
        try:
            return insert_at(timeline, frame, fps, lambda: timeline.InsertFusionGeneratorIntoTimeline(gname),
                             "InsertFusionGeneratorIntoTimeline(%r)" % gname)
        except Skip as e:
            log("   %s" % e)
    return insert_at(timeline, frame, fps, lambda: timeline.InsertGeneratorIntoTimeline("Solid Color"),
                     "InsertGeneratorIntoTimeline('Solid Color')")


def cover_with_still(timeline, mp, still, track, start, end):
    """Lay a still image over [start, end) on `track` in chunks of its default length."""
    n = clip_frames(still, 30) or 125
    pos, items = start, []
    while pos < end:
        length = min(n, end - pos)
        base = {"mediaPoolItem": still, "startFrame": 0, "endFrame": length, "trackIndex": track, "recordFrame": pos}
        got = mp.AppendToTimeline([dict(base, mediaType=1)]) or mp.AppendToTimeline([base]) or []
        if not got:
            raise Skip("AppendToTimeline(still, track %d) returned nothing" % track)
        it = got[0]
        items.append(it)
        nxt = int(it.GetEnd())
        if nxt <= pos:
            break
        pos = nxt
    return items


def ensure_tracks(timeline, kind, count, sub=None):
    while int(timeline.GetTrackCount(kind) or 0) < count:
        ok = timeline.AddTrack(kind, sub) if sub else timeline.AddTrack(kind)
        log("AddTrack(%s%s) -> %s (now %s)" % (kind, ", " + sub if sub else "", ok, timeline.GetTrackCount(kind)))
        if not ok:
            raise Skip("AddTrack(%s) failed" % kind)


def place_logo(timeline, m, placed, track, which):
    logo = m["brand"].get(which + "_item")
    if not logo:
        raise Skip("no %s image imported" % which)
    ensure_tracks(timeline, "video", track)
    items = []
    for s in placed:
        it = s["tl_item"]
        items += cover_with_still(timeline, STATE["mp"], logo, track, int(it.GetStart()), int(it.GetEnd()))
    for it in items:
        it.SetProperty("Opacity", 90.0)
        it.SetClipColor("Pink")
    log("Logo %s: %d still segment(s) on V%d, Opacity 90" % (which, len(items), track))
    return items


def add_markers(timeline, m, placed):
    tl_start = STATE["tl_start"]
    rows = []
    intro = m.get("intro_item")
    if intro:
        rows.append((int(intro.GetStart()) - tl_start, "Blue", "Intro", "Fusion Text+ title"))
    for s in placed:
        rows.append((int(s["tl_item"].GetStart()) - tl_start, s["marker_color"], s["chapter"], s["command"]))
    outro = m.get("outro_item")
    if outro:
        rows.append((int(outro.GetStart()) - tl_start, "Red", "Outro", m.get("outro", {}).get("title", "")))
    for f, color, nm, note in rows:
        log("AddMarker(%d, %s, %r) -> %s" % (f, color, nm, timeline.AddMarker(f, color, nm, note, 1, "grokbot")))


def name_tracks(timeline):
    names = [("video", 1, "Picture"), ("video", 2, "Logo"), ("audio", 1, "Music"), ("audio", 2, "Voiceover")]
    for kind, idx, nm in names:
        if int(timeline.GetTrackCount(kind) or 0) >= idx:
            log("SetTrackName(%s, %d, %r) -> %s" % (kind, idx, nm, timeline.SetTrackName(kind, idx, nm)))


# --------------------------------------------------------------------------
# Fairlight (music)
# --------------------------------------------------------------------------
def stage_fairlight(m, ans):
    stage("7/10 Fairlight: music + voiceover tracks")
    open_page("fairlight")
    timeline = STATE["timeline"]
    if m.get("music_item"):
        step("Fairlight: music bed on A1 (AppendToTimeline mediaType 2)", place_music, timeline, m, ans)
    else:
        log("SKIPPED Fairlight: music: no music in the manifest")
        RESULTS.append(("Fairlight: music bed", "SKIPPED", "no music"))
    step("Fairlight: voiceover track (AddTrack audio stereo)", ensure_tracks, timeline, "audio", 2, "stereo")
    step("Fairlight: track names", name_tracks, timeline)
    step("Fairlight: presets list (GetFairlightPresets)",
         lambda: log("Fairlight presets: %s" % STATE["res"].GetFairlightPresets()))
    log("SKIPPED Fairlight: fades / EQ / Ducker / loudness: not exposed by the scripting API")
    RESULTS.append(("Fairlight: fades / EQ / ducker / normalize", "SKIPPED", "not exposed by the API"))
    log("SKIPPED Fairlight: Voice Isolation: Studio-only (SetVoiceIsolationState)")
    RESULTS.append(("Fairlight: Voice Isolation", "SKIPPED", "Studio-only"))


def place_music(timeline, m, ans):
    mp, tl_start, total, fps = STATE["mp"], STATE["tl_start"], STATE["total"], m["fps"]
    item = m["music_item"]
    mframes = clip_frames(item, fps) or total
    want = min(mframes, total)
    start = max(0, mframes - total) if (m.get("music_align") == "end" and mframes > total) else 0
    log("Music %d frames, picture %d: source %d-%d (%s-aligned so the baked fade-out lands on the end)"
        % (mframes, total, start, start + want - 1, "end" if start else "start"))
    placed = None
    for label, extra in (("mediaType=2", {"mediaType": 2}), ("no mediaType", {})):
        base = {"mediaPoolItem": item, "startFrame": start, "endFrame": start + want, "trackIndex": 1,
                "recordFrame": tl_start}
        base.update(extra)
        got = mp.AppendToTimeline([base]) or []
        audio = [g for g in got if item_track(g).startswith("audio")] or got
        if audio:
            placed = audio[0]
            log("Music placed (%s): %s %d-%d" % (label, item_track(placed), int(placed.GetStart()), int(placed.GetEnd()) - 1))
            break
    if not placed:
        raise Skip("AppendToTimeline(music) returned nothing")
    m["music_tl_item"] = placed
    ok = None
    for key in ("Volume", "AudioVolume", "Level"):
        try:
            ok = placed.SetProperty(key, float(ans["music_db"]))
        except Exception as e:
            ok = "error %s" % e
        log("Music SetProperty(%r, %s dB) -> %s" % (key, ans["music_db"], ok))
        if ok is True:
            break
    if ok is not True:
        log("SKIPPED Fairlight: music level: clip volume is not exposed; set it in Inspector > Audio > Volume "
            "(the Cross Dissolve FCPXML timeline carries the level via adjust-volume)")
        RESULTS.append(("Fairlight: music level via SetProperty", "SKIPPED", "Volume not exposed"))


# --------------------------------------------------------------------------
# Color page
# --------------------------------------------------------------------------
def stage_color(m, ans):
    stage("6/10 Color page: versions, CDL looks, LUT, color group")
    open_page("color")
    project = STATE["project"]
    try:
        log("RefreshLUTList -> %s" % project.RefreshLUTList())
    except Exception as e:
        log("RefreshLUTList not available (%s)" % e)
    group = step("Color: color group (AddColorGroup / AssignToColorGroup)", color_group, m)
    for s in STATE["placed"]:
        step("Color: local versions + CDL + LUT (%s)" % s["key"], grade_item, s, ans, group)
    if m.get("drx_path"):
        step("Color: ApplyGradeFromDRX", apply_drx, m)
    else:
        RESULTS.append(("Color: ApplyGradeFromDRX", "SKIPPED", "no 'drx' in manifest"))
        log("SKIPPED Color: ApplyGradeFromDRX: no 'drx' file in the manifest")
    log("SKIPPED Color: node labels: the API can read node labels (GetNodeLabel) but not set them")
    RESULTS.append(("Color: set node labels", "SKIPPED", "API has GetNodeLabel only"))
    step("Color: thumbnail frame (ExportCurrentFrameAsStill + GrabStill)", export_thumb, m)


def color_group(m):
    project = STATE["project"]
    name = "Grok Bot - screen recordings"
    group = None
    for g in (project.GetColorGroupsList() or []):
        if g.GetName() == name:
            group = g
    if not group:
        group = project.AddColorGroup(name)
    if not group:
        raise Skip("AddColorGroup returned nothing")
    for s in STATE["placed"]:
        log("AssignToColorGroup(%s) -> %s" % (s["key"], s["tl_item"].AssignToColorGroup(group)))
    return group


def find_lut():
    for rel in FILM_LUTS:
        for root in ("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT",
                     os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT"),
                     os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\LUT")):
            if os.path.isfile(os.path.join(root, rel)):
                return rel, os.path.join(root, rel)
    return FILM_LUTS[0], None


def apply_look(item, look):
    slope, offset, power, sat = CDL_LOOKS[look]
    ok = item.SetCDL({"NodeIndex": "1", "Slope": slope, "Offset": offset, "Power": power, "Saturation": sat})
    lut_ok = None
    if look.startswith("Film"):
        rel, full = find_lut()
        graph = item.GetNodeGraph()
        lut_ok = graph.SetLUT(1, rel) if graph else None
        if not lut_ok and full and graph:
            lut_ok = graph.SetLUT(1, full)
    return ok, lut_ok


def grade_item(s, ans, group):
    it = s["tl_item"]
    have = list(it.GetVersionNameList(0) or [])
    log("%s local versions before: %s" % (s["key"], have))
    for look in LOOKS:
        vname = "Grok Bot - " + look
        if vname not in have:
            it.AddVersion(vname, 0)
        loaded = it.LoadVersionByName(vname, 0)
        ok, lut = apply_look(it, look)
        log("   version %-28r load %s  SetCDL %s%s" % (vname, loaded, ok, "  SetLUT %s" % lut if lut is not None else ""))
    chosen = "Grok Bot - " + ans["look"]
    log("   active version -> %r: %s (compare in Color > right-click clip > Local Versions)"
        % (chosen, it.LoadVersionByName(chosen, 0)))
    try:
        g = it.GetNodeGraph()
        log("   node graph: %s node(s), node 1 label %r, LUT %r" % (g.GetNumNodes(), g.GetNodeLabel(1), g.GetLUT(1)))
    except Exception:
        pass


def apply_drx(m):
    tl = STATE["timeline"]
    items = [s["tl_item"] for s in STATE["placed"]]
    log("ApplyGradeFromDRX(%s) -> %s" % (m["drx_path"], tl.ApplyGradeFromDRX(m["drx_path"], 0, items)))


def export_thumb(m):
    tl, s = STATE["timeline"], STATE["placed"][0]
    it = s["tl_item"]
    frame = int(it.GetStart()) + min(int(it.GetDuration()) - 1, int(3.0 * m["fps"]))
    tl.SetCurrentTimecode(frames_to_tc(frame, m["fps"]))
    os.makedirs(m["renders_dir"], exist_ok=True)
    path = os.path.join(m["renders_dir"], unique_base(m["renders_dir"], m["name"] + "-thumb-frame", ".png") + ".png")
    ok = STATE["project"].ExportCurrentFrameAsStill(path)
    log("ExportCurrentFrameAsStill(%s) -> %s" % (path, ok))
    m["thumb_path"] = path if ok else None
    still = tl.GrabStill()
    log("GrabStill -> %s (saved to the Gallery for PowerGrade reuse)" % bool(still))


# --------------------------------------------------------------------------
# Alternate cut with Cross Dissolves via FCPXML
# --------------------------------------------------------------------------
def _rt(fr):
    fr = Fraction(fr).limit_denominator(30000)
    return "%d/%ds" % (fr.numerator, fr.denominator) if fr.denominator != 1 else "%ds" % fr.numerator


def _url(path):
    q = _urlquote(path) if _urlquote else path.replace(" ", "%20")
    return "file://" + q


def _xml(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_fcpxml(m, ans, path):
    fps = Fraction(int(round(m["fps"])), 1)
    d = Fraction(int(0.5 * fps), fps)                    # 0.5 s dissolves
    res, spine, clips = [], [], []
    res.append('<format id="r0" name="GrokBot%dp%d" frameDuration="%s" width="%d" height="%d"/>'
               % (m["height"], int(fps), _rt(1 / fps), m["width"], m["height"]))
    for n, s in enumerate(STATE["placed"], 1):
        a, b, sfps = section_range(s, ans, s["item"], m["fps"])
        sf = Fraction(sfps).limit_denominator(1001)
        w, h = clip_res(s["item"], (1280, 800))
        total = clip_frames(s["item"], sfps)
        fid, aid = "f%d" % n, "a%d" % n
        res.append('<format id="%s" frameDuration="%s" width="%d" height="%d"/>' % (fid, _rt(1 / sf), w, h))
        res.append('<asset id="%s" name="%s" start="0s" duration="%s" hasVideo="1" format="%s" videoSources="1">'
                   '<media-rep kind="original-media" src="%s"/></asset>'
                   % (aid, _xml(s["key"]), _rt(Fraction(total) / sf), fid, _xml(_url(s["path"]))))
        dur = Fraction(int(round(float(Fraction(b - a) / sf) * fps)), fps)
        clips.append(dict(s=s, aid=aid, fid=fid, start=Fraction(a) / sf, dur=dur, src_len=Fraction(total) / sf))
    seq_dur = sum((c["dur"] for c in clips), Fraction(0))
    music = ""
    if m.get("music_item"):
        mi = m["music_item"]
        mfps = Fraction(clip_fps(mi, m["fps"])).limit_denominator(1001)
        mlen = Fraction(clip_frames(mi, float(mfps))) / mfps
        mstart = max(Fraction(0), mlen - seq_dur) if m.get("music_align") == "end" else Fraction(0)
        mstart = Fraction(int(mstart * fps), fps)
        res.append('<asset id="m1" name="music" start="0s" duration="%s" hasAudio="1" audioSources="1" audioChannels="2" '
                   'audioRate="48000"><media-rep kind="original-media" src="%s"/></asset>' % (_rt(mlen), _xml(_url(m["music_path"]))))
        music = ('<asset-clip ref="m1" lane="-1" offset="%%s" name="music" start="%s" duration="%s" audioRole="music">'
                 '<adjust-volume amount="%+.1fdB"/></asset-clip>' % (_rt(mstart), _rt(min(seq_dur, mlen - mstart)), ans["music_db"]))
    res.append('<effect id="x1" name="Cross Dissolve" uid="FxPlug:4731E73A-8DAC-4113-9A30-AE85B1761265"/>')
    skipped, offset = 0, Fraction(3600)
    for i, c in enumerate(clips):
        inner = (music % _rt(c["start"])) if (i == 0 and music) else ""
        spine.append('<asset-clip ref="%s" offset="%s" name="%s" start="%s" duration="%s" format="%s" tcFormat="NDF">%s</asset-clip>'
                     % (c["aid"], _rt(offset), _xml(c["s"]["chapter"]), _rt(c["start"]), _rt(c["dur"]), c["fid"], inner))
        offset += c["dur"]
        if i + 1 < len(clips):
            nxt = clips[i + 1]
            tail = c["src_len"] - (c["start"] + c["dur"])
            if tail >= d / 2 and nxt["start"] >= d / 2:
                spine.append('<transition name="Cross Dissolve" offset="%s" duration="%s">'
                             '<filter-video ref="x1" name="Cross Dissolve"/></transition>' % (_rt(offset - d / 2), _rt(d)))
            else:
                skipped += 1
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9">\n<resources>\n%s\n</resources>\n'
           '<library><event name="Grok Bot"><project name="%s"><sequence format="r0" duration="%s" tcStart="3600s" '
           'tcFormat="NDF" audioLayout="stereo" audioRate="48k"><spine>\n%s\n</spine></sequence></project></event>'
           '</library>\n</fcpxml>\n' % ("\n".join(res), _xml(ans["title"] + " - dissolves"), _rt(seq_dur), "\n".join(spine)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(xml)
    return len(clips), max(0, len(clips) - 1 - skipped), skipped


def stage_alt_cut(m, ans):
    stage("5/10 Alternate cut: Cross Dissolves via FCPXML import")
    mp, project = STATE["mp"], STATE["project"]
    path = os.path.join(m["manifest_dir"], "grokbot-dissolves.fcpxml")
    nclips, ntr, skipped = build_fcpxml(m, ans, path)
    log("Wrote %s (%d clips, %d Cross Dissolves%s, music %+.1f dB)" % (
        path, nclips, ntr, ", %d skipped for lack of handles" % skipped if skipped else "", ans["music_db"]))
    name = unique_timeline_name(project, "%s - dissolves (FCPXML)" % ans["title"])
    mp.SetCurrentFolder(STATE["bins"]["Selects"])
    tl = mp.ImportTimelineFromFile(path, {"timelineName": name, "importSourceClips": False,
                                          "sourceClipsFolders": [STATE["bins"]["Footage"], STATE["bins"]["Audio"]]})
    how = "matched existing media"
    if not tl:
        log("ImportTimelineFromFile (reuse media) returned None; retrying with importSourceClips=True")
        tl = mp.ImportTimelineFromFile(path, {"timelineName": name, "importSourceClips": True,
                                              "sourceClipsPath": m["manifest_dir"]})
        how = "re-imported source clips"
    if not tl:
        raise Skip("ImportTimelineFromFile returned None for the FCPXML")
    counts = {}
    for kind in ("video", "audio"):
        for i in range(1, int(tl.GetTrackCount(kind) or 0) + 1):
            counts["%s%d" % (kind[0].upper(), i)] = len(tl.GetItemListInTrack(kind, i) or [])
    log("Imported timeline %r (%s): items per track %s" % (name, how, counts))
    try:
        tl.SetTrackName("video", 1, "Picture (dissolves)")
        tl.SetTrackName("audio", 1, "Music")
    except Exception:
        pass
    project.SetCurrentTimeline(STATE["timeline"])
    return tl


# --------------------------------------------------------------------------
# Vertical 9:16
# --------------------------------------------------------------------------
def stage_vertical(m, ans):
    stage("8/10 Vertical 9:16 timeline")
    open_page("edit")
    src, project = STATE["timeline"], STATE["project"]
    project.SetCurrentTimeline(src)
    name = unique_timeline_name(project, "%s - vertical 9x16" % ans["title"])
    vt = src.DuplicateTimeline(name)
    if not vt:
        raise Skip("DuplicateTimeline returned nothing")
    log("DuplicateTimeline -> %r" % vt.GetName())
    for k, v in (("useCustomSettings", "1"), ("timelineResolutionWidth", str(m["vwidth"])),
                 ("timelineResolutionHeight", str(m["vheight"])), ("timelineInputResMismatchBehavior", "scaleToFit")):
        log("   vertical SetSetting(%s=%s) -> %s   now: %s" % (k, v, vt.SetSetting(k, v), vt.GetSetting(k)))
    vw = int(to_float(vt.GetSetting("timelineResolutionWidth")))
    vh = int(to_float(vt.GetSetting("timelineResolutionHeight")))
    if (vw, vh) != (m["vwidth"], m["vheight"]):
        raise Skip("vertical timeline stayed %dx%d (could not change timeline resolution)" % (vw, vh))
    project.SetCurrentTimeline(vt)
    raw_paths = set(s["path"] for s in m["sections"])
    tilt = float(m.get("vertical_tilt", 140))
    placed_v = []
    for it in (vt.GetItemListInTrack("video", 1) or []):
        mpi = it.GetMediaPoolItem()
        fp = os.path.normpath(mpi.GetClipProperty("File Path") or "") if mpi else ""
        if fp in raw_paths:
            # the clip fits the width (1280x800 -> 1080x675); lift it out of the Shorts/Reels caption zone
            ok = it.SetProperty({"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": tilt})
            if not ok:
                ok = it.SetProperty("Tilt", tilt)
            placed_v.append({"tl_item": it})
    log("   reframed %d clip(s): fit width, Tilt %+.0f px" % (len(placed_v), tilt))
    if int(vt.GetTrackCount("video") or 0) >= 2:
        log("   SetTrackEnable(video, 2, False) [16:9 logo] -> %s" % vt.SetTrackEnable("video", 2, False))
    if m["brand"].get("logo_9x16_item") and placed_v:
        step("Vertical: 9:16 logo on V3", place_logo, vt, m, placed_v, 3, "logo_9x16")
        try:
            vt.SetTrackName("video", 3, "Logo 9x16")
        except Exception:
            pass
    project.SetCurrentTimeline(src)
    STATE["vertical"] = vt
    return vt


# --------------------------------------------------------------------------
# Deliver
# --------------------------------------------------------------------------
def pick_preset(project, want_words):
    try:
        presets = project.GetRenderPresetList() or []
    except Exception:
        presets = []
    names = [p if isinstance(p, str) else (p.get("PresetName") or p.get("Name") or str(p)) for p in presets]
    for nm in names:
        if all(w in nm.lower() for w in want_words):
            return nm, names
    return None, names


def queue_job(m, timeline, base, width, height, preset_words, save_as):
    project = STATE["project"]
    project.SetCurrentTimeline(timeline)
    preset, names = pick_preset(project, preset_words)
    if not STATE.get("logged_presets"):
        STATE["logged_presets"] = True
        log("Render presets available: %s" % names)
    if preset:
        log("LoadRenderPreset(%r) -> %s" % (preset, project.LoadRenderPreset(preset)))
    ok = project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    log("SetCurrentRenderFormatAndCodec('mp4', 'H264') -> %s" % ok)
    if not ok:
        raise Abort("FAILED: could not select MP4/H264")
    out_dir = m["renders_dir"]
    os.makedirs(out_dir, exist_ok=True)
    name = unique_base(out_dir, base, ".mp4")
    settings = {"SelectAllFrames": True, "TargetDir": out_dir, "CustomName": name,
                "FormatWidth": width, "FormatHeight": height, "FrameRate": float(m["fps"]),
                "ExportVideo": True, "ExportAudio": True, "AudioCodec": "aac", "AudioSampleRate": 48000}
    ok = project.SetRenderSettings(settings)
    for k in ("AudioSampleRate", "AudioCodec"):
        if ok:
            break
        settings.pop(k, None)
        ok = project.SetRenderSettings(settings)
    log("SetRenderSettings(%s) -> %s" % (settings, ok))
    if not ok:
        raise Abort("FAILED: SetRenderSettings")
    try:
        saved = project.SaveAsNewRenderPreset(save_as)
        log("SaveAsNewRenderPreset(%r) -> %s%s" % (save_as, saved, "" if saved else " (probably exists already)"))
    except Exception as e:
        log("SaveAsNewRenderPreset not available (%s)" % e)
    job = require(project.AddRenderJob(), "AddRenderJob")
    log("AddRenderJob (%s, %dx%d) -> %s" % (timeline.GetName(), width, height, job))
    return job, os.path.join(out_dir, name + ".mp4"), name


def stage_render(m, ans):
    stage("9/10 Deliver page: render queue")
    open_page("deliver")
    project = STATE["project"]
    try:
        project.SetCurrentRenderMode(1)
    except Exception:
        pass
    jobs = []
    j, out, name = queue_job(m, STATE["timeline"], m["name"], m["width"], m["height"], ("youtube", "1080"),
                             "Grok Bot - YouTube 1080p")
    jobs.append((j, out, "16:9"))
    m["out_name"] = name
    if STATE.get("vertical"):
        try:
            j2, out2, _ = queue_job(m, STATE["vertical"], m["name"] + "-vertical", m["vwidth"], m["vheight"],
                                    ("vertical",), "Grok Bot - Vertical 1080x1920")
            jobs.append((j2, out2, "9:16"))
            RESULTS.append(("Deliver: vertical render job", "OK", ""))
        except Abort as e:
            log("SKIPPED Deliver: vertical job: %s" % e)
            RESULTS.append(("Deliver: vertical render job", "SKIPPED", str(e)))
    project.SetCurrentTimeline(STATE["timeline"])
    ids = [j for j, _, _ in jobs]
    started = project.StartRendering(*ids) or project.StartRendering(ids) or project.StartRendering()
    require(started, "StartRendering(%s)" % ids)
    log("Rendering %d job(s)" % len(ids))
    t0, last = time.time(), {}
    time.sleep(1.0)
    while project.IsRenderingInProgress():
        for j, _, lab in jobs:
            st = project.GetRenderJobStatus(j) or {}
            pct = st.get("CompletionPercentage")
            if pct != last.get(j):
                log("Render %s: %s %s%%" % (lab, st.get("JobStatus"), pct))
                last[j] = pct
        if time.time() - t0 > RENDER_TIMEOUT:
            log("WARNING: still rendering after %d s; stopping the wait" % RENDER_TIMEOUT)
            break
        heartbeat()
        time.sleep(1.0)
    outs = []
    for j, out, lab in jobs:
        st = project.GetRenderJobStatus(j) or {}
        log("Final render status %s: %s" % (lab, st))
        for job in (project.GetRenderJobList() or []):
            if job.get("JobId") == j:
                out = os.path.join(job.get("TargetDir", os.path.dirname(out)), job.get("OutputFilename", os.path.basename(out)))
        if st.get("JobStatus") not in (None, "Complete"):
            log("WARNING: %s render ended with %s %s" % (lab, st.get("JobStatus"), st.get("Error", "")))
        outs.append((lab, out))
    RESULTS.append(("Deliver: render queue + StartRendering", "OK", ""))
    return outs


def stage_exports(m, ans):
    stage("10/10 Chapters, exports, save")
    step("Deliver: YouTube chapters .txt", write_chapters, m)
    step("Deliver: timeline exports (OTIO / CSV)", export_timeline, m)
    step("Deliver: project backup (.drp)", export_drp, m)


def write_chapters(m):
    tl, tl_start, fps = STATE["timeline"], STATE["tl_start"], m["fps"]
    markers = tl.GetMarkers() or {}
    rows = []
    for frame in sorted(markers, key=lambda f: to_float(f)):
        f = to_float(frame)
        if f >= tl_start:
            f -= tl_start
        rows.append((f / fps, (markers[frame] or {}).get("name") or "Chapter"))
    if not rows:
        raise Skip("no markers")
    if int(rows[0][0]) != 0:
        rows.insert(0, (0.0, "Intro"))
    for (a, n1), (b, _) in zip(rows, rows[1:]):
        if b - a < 10:
            log("NOTE: chapter %r is %.1f s; YouTube wants each chapter >= 10 s" % (n1, b - a))
    lines = ["%s %s" % (fmt_chapter_time(t), n) for t, n in rows]
    path = os.path.join(m["renders_dir"], m.get("out_name", m["name"]) + "-chapters.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    m["chapters_path"] = path
    log("Wrote chapters: %s" % path)
    for line in lines:
        log("   " + line)


def export_timeline(m):
    res, tl = STATE["res"], STATE["timeline"]
    base = os.path.join(m["renders_dir"], m.get("out_name", m["name"]))
    for label, attr, ext in (("OTIO", "EXPORT_OTIO", ".otio"), ("CSV edit list", "EXPORT_TEXT_CSV", ".csv")):
        const = getattr(res, attr, None)
        if const is None:
            log("   %s: resolve.%s not available" % (label, attr))
            continue
        log("   Timeline.Export(%s) -> %s" % (base + ext, tl.Export(base + ext, const, getattr(res, "EXPORT_NONE", 0))))


def export_drp(m):
    path = os.path.join(m["renders_dir"], m.get("out_name", m["name"]) + ".drp")
    log("SaveProject -> %s; ExportProject(%s) -> %s" % (STATE["pm"].SaveProject(), path,
                                                         STATE["pm"].ExportProject(m["project"], path, False)))


def ask_feedback(m, outs):
    if not m.get("ask_feedback_after_render", True):
        return
    msg = ("Your Resolve edit is rendered:\n%s\n\nWhat should Grok Bot change next? (pacing, look, titles, music, "
           "sections...) Leave it empty if it's good." % "\n".join("%s: %s" % (l, os.path.basename(o)) for l, o in outs))
    text = None
    try:
        fu = get_fusion()
        comp = fu.GetCurrentComp() if fu else None
        if comp:
            r = comp.AskUser("Grok Bot - how did it turn out?",
                             {1: {1: "Feedback", 2: "Text", "Name": msg, "Lines": 5, "Default": ""}})
            if r is not None:
                text = r.get("Feedback", "")
    except Exception as e:
        log("Feedback dialog (Fusion) unavailable: %s" % e)
    if text is None and sys.platform == "darwin":
        try:
            rc, o, _ = _osa('text returned of (display dialog %s default answer "" with title "Grok Bot - feedback" '
                            'buttons {"Skip", "Send to Grok Bot"} default button "Send to Grok Bot" giving up after 180)'
                            % _osa_q(msg), timeout=200)
            text = o if rc == 0 else ""
        except Exception as e:
            log("Feedback dialog (macOS) unavailable: %s" % e)
    if text:
        log("USER FEEDBACK after render: " + text.replace("\n", " / "))
        m["feedback"] = text
    else:
        log("No feedback entered (Grok Bot will ask in chat)")


def write_report(m, ans, outs):
    try:
        path = os.path.join(m["renders_dir"], m.get("out_name", m["name"]) + "-report.json")
        rep = {"run_id": RUN_ID, "answers": ans, "outputs": dict(outs), "chapters": m.get("chapters_path"),
               "thumbnail_frame": m.get("thumb_path"), "feedback": m.get("feedback"),
               "capabilities": [{"step": a, "status": b, "detail": c} for a, b, c in RESULTS]}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, ensure_ascii=False)
        log("Report: " + path)
    except Exception as e:
        log("NOTE: report not written (%s)" % e)


def summary():
    log("")
    log("==== Capability summary ====")
    for a, b, c in RESULTS:
        log("  %-8s %s%s" % (b, a, ("  (" + c + ")") if c else ""))


# --------------------------------------------------------------------------
def main():
    log("=" * 60)
    if not acquire_lock():
        return
    try:
        run()
    finally:
        release_lock()


def run():
    log("GrokBot full Resolve edit starting. Python", sys.version.split()[0])
    res = get_resolve()
    if not res:
        log("FAILED: no 'resolve' object. Run this from Workspace > Scripts inside DaVinci Resolve.")
        return
    STATE["res"] = res
    log("Connected to", res.GetProductName(), res.GetVersionString())
    try:
        m = load_manifest()
        ans = ask_user(m)
        stage_project(m)
        stage_media(m, ans)
        stage_edit(m, ans)
        log("Saving project ->", STATE["pm"].SaveProject())
        step("Alt cut: Cross Dissolve timeline via FCPXML (ImportTimelineFromFile)", stage_alt_cut, m, ans)
        stage_color(m, ans)
        stage_fairlight(m, ans)
        if ans["vertical"]:
            step("Vertical: 9:16 timeline (DuplicateTimeline + SetSetting + Zoom/Tilt)", stage_vertical, m, ans)
        else:
            log("Vertical timeline not requested")
        open_page("edit")
        STATE["project"].SetCurrentTimeline(STATE["timeline"])
        log("Saving project ->", STATE["pm"].SaveProject())
        outs = stage_render(m, ans)
        stage_exports(m, ans)
        log("Saving project ->", STATE["pm"].SaveProject())
        summary()
        for lab, out in outs:
            if os.path.isfile(out):
                log("Output %s: %s (%.1f MB)" % (lab, out, os.path.getsize(out) / 1048576.0))
            else:
                log("WARNING: %s render reported done but file not found at %s" % (lab, out))
        if m.get("chapters_path"):
            log("Chapters: " + m["chapters_path"])
        if m.get("thumb_path"):
            log("Thumbnail frame: " + m["thumb_path"])
        log("DONE: " + " | ".join(out for _, out in outs))
        write_report(m, ans, outs)
        ask_feedback(m, outs)
        write_report(m, ans, outs)
    except Abort as e:
        log(str(e))
        summary()
    except Exception as e:
        log("FAILED with exception:", repr(e))
        log(traceback.format_exc())
        summary()


main()
