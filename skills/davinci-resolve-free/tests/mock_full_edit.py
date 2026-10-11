"""Mock Resolve 21 API test for GrokBot_Resolve_Full_Edit.py (no Resolve needed: python3 tests/mock_full_edit.py).
Models behaviour seen in real 21.0.4 runs: AppendToTimeline endFrame exclusive + recordFrame honoured,
timeline start 108000, Insert*IntoTimeline at the playhead on V1 (150 frames), 25 fps sources conformed
into a 30 fps timeline. Unknown methods on Fusion objects are permissive."""
import os, sys, json, shutil, tempfile, time, io, contextlib, copy
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("SCRIPT", os.path.join(HERE, "..", "scripts", "GrokBot_Resolve_Full_Edit.py"))
EXAMPLE = os.path.join(HERE, "..", "examples", "manifest.example.json")
FPS = 30
CALLS = []

class Any:
    """Permissive Fusion object: every call succeeds."""
    def __init__(s, name="any"): s._n = name; s.inputs = {}
    def __getattr__(s, k):
        if k.startswith("__"): raise AttributeError(k)
        def f(*a, **kw):
            CALLS.append((s._n, k, a)); return Any(k)
        return f
    def SetInput(s, k, v, t=None): s.inputs[(k, t)] = v; CALLS.append((s._n, "SetInput", (k, v, t))); return None
    def __bool__(s): return True

class Comp(Any):
    def __init__(s, kind, dur): super().__init__("comp"); s.kind, s.dur, s.tools = kind, dur, []
    def FindTool(s, n):
        if s.kind == "title" and n in ("Template", "MediaOut1"): return Any(n)
        if s.kind == "clip" and n in ("MediaIn1", "MediaOut1"): return Any(n)
        if s.kind == "gen" and n == "MediaOut1": return Any(n)
        return None
    def AddTool(s, tid, x=0, y=0): t = Any(tid); s.tools.append(tid); return t
    def GetAttrs(s): return {"COMPN_RenderStart": 0, "COMPN_RenderEnd": s.dur - 1}

class MPItem:
    def __init__(s, path, frames, fps, res="1280x800"):
        s.path, s.frames, s.fps, s.res, s.color, s.meta, s.flags, s.markers = path, frames, fps, res, None, {}, [], {}
    def GetClipProperty(s, k=None):
        d = {"File Path": s.path, "Frames": str(s.frames), "FPS": "%.3f" % s.fps, "Resolution": s.res}
        return d if k is None else d.get(k, "")
    def GetName(s): return os.path.basename(s.path)
    def SetName(s, n): s.path_name = n; return True
    def SetClipColor(s, c): s.color = c; return True
    def SetMetadata(s, k, v=None):
        if isinstance(k, dict): s.meta.update(k)
        else: s.meta[k] = v
        return True
    def GetMetadata(s, k=None): return dict(s.meta) if k is None else s.meta.get(k)
    def AddFlag(s, c): s.flags.append(c); return True
    def AddMarker(s, f, c, n, note, d, cd=""): s.markers[f] = n; return True

class TLItem:
    def __init__(s, tl, kind, idx, start, end, mpi, comp_kind=None):
        s.tl, s.kind, s.idx, s.start, s.end, s.mpi = tl, kind, idx, start, end, mpi
        s.comps = [Comp(comp_kind, end - start)] if comp_kind else []
        s.props, s.versions, s.cur_version, s.cdl, s.color, s.name, s.group = {}, ["Version 1"], "Version 1", {}, None, None, None
    def GetStart(s, *a): return s.start
    def GetEnd(s, *a): return s.end
    def GetDuration(s, *a): return s.end - s.start
    def GetTrackTypeAndIndex(s): return [s.kind, s.idx]
    def GetMediaPoolItem(s): return s.mpi
    def SetProperty(s, k, v=None):
        if isinstance(k, dict): s.props.update(k); return True
        if k in ("Volume", "AudioVolume", "Level", "Speed"): return False
        s.props[k] = v; return True
    def GetProperty(s, k=None): return dict(Pan=0, Tilt=0, ZoomX=1, ZoomY=1, Opacity=100, RetimeProcess=0) if k is None else s.props.get(k)
    def SetClipColor(s, c): s.color = c; return True
    def AddFlag(s, c): return True
    def SetName(s, n): s.name = n; return True
    def GetFusionCompCount(s): return len(s.comps)
    def GetFusionCompByIndex(s, i): return s.comps[i - 1]
    def AddFusionComp(s): c = Comp("clip", s.end - s.start); s.comps.append(c); return c
    def GetVersionNameList(s, t): return list(s.versions)
    def AddVersion(s, n, t): s.versions.append(n); s.cur_version = n; return True
    def LoadVersionByName(s, n, t):
        if n in s.versions: s.cur_version = n; return True
        return False
    def SetCDL(s, d):
        if STATE_FAIL.get("cdl"): raise RuntimeError("mock SetCDL failure")
        s.cdl[s.cur_version] = d; return True
    def GetNodeGraph(s, *a): return Graph()
    def AssignToColorGroup(s, g): s.group = g; return True

class Graph:
    def SetLUT(s, i, p): return True
    def GetNumNodes(s): return 1
    def GetNodeLabel(s, i): return ""
    def GetLUT(s, i): return ""

class Timeline:
    def __init__(s, proj, name, w=1920, h=1080):
        s.proj, s.name, s.items, s.markers, s.playhead = proj, name, [], {}, 108000
        s.tracks = {"video": 1, "audio": 1}; s.settings = {"timelineResolutionWidth": str(w), "timelineResolutionHeight": str(h), "timelineFrameRate": "30"}
        s.tnames = {}
    def GetName(s): return s.name
    def GetStartFrame(s): return 108000
    def GetSetting(s, k): return s.settings.get(k, "")
    def SetSetting(s, k, v): s.settings[k] = v; return True
    def AddMarker(s, f, c, n, note, d, cd=""):
        if f in s.markers: return False
        s.markers[f] = {"color": c, "name": n, "note": note}; return True
    def GetMarkers(s): return dict(s.markers)
    def GetTrackCount(s, k): return s.tracks.get(k, 0)
    def AddTrack(s, k, sub=None): s.tracks[k] = s.tracks.get(k, 0) + 1; return True
    def SetTrackName(s, k, i, n): s.tnames[(k, i)] = n; return True
    def SetTrackEnable(s, k, i, b): return True
    def GetItemListInTrack(s, k, i): return sorted([x for x in s.items if x.kind == k and x.idx == i], key=lambda x: x.start)
    def SetCurrentTimecode(s, tc):
        h, m, sec, f = [int(x) for x in tc.split(":")]; s.playhead = ((h * 60 + m) * 60 + sec) * FPS + f; return True
    def _insert(s, kind):
        if STATE_FAIL.get("titles") and kind == "title": return None
        it = TLItem(s, "video", 1, s.playhead, s.playhead + 150, None, kind); s._add(it); return it
    def InsertFusionTitleIntoTimeline(s, n): return s._insert("title")
    def InsertFusionGeneratorIntoTimeline(s, n): return s._insert("gen") if n == "Noise Gradient" else None
    def InsertGeneratorIntoTimeline(s, n): return s._insert("gen")
    def _add(s, ti):
        for o in s.items:
            if o.kind == ti.kind and o.idx == ti.idx and not (ti.end <= o.start or ti.start >= o.end):
                raise AssertionError("overlap on %s%d: %d-%d vs %d-%d" % (ti.kind, ti.idx, ti.start, ti.end, o.start, o.end))
        if ti.idx > s.tracks.get(ti.kind, 0): raise AssertionError("track %s%d does not exist" % (ti.kind, ti.idx))
        s.items.append(ti)
    def DuplicateTimeline(s, name):
        t = Timeline(s.proj, name); t.items = [copy.copy(i) for i in s.items]; t.markers = dict(s.markers)
        for i in t.items: i.props = dict(i.props); i.tl = t
        t.tracks = dict(s.tracks); s.proj.timelines.append(t); return t
    def GrabStill(s): return object()
    def Export(s, fn, a, b): open(fn, "w").write("x"); return True
    def ApplyGradeFromDRX(s, *a): return True

class Folder:
    def __init__(s, name): s.name, s.subs, s.clips = name, [], []
    def GetName(s): return s.name
    def GetSubFolderList(s): return list(s.subs)
    def GetClipList(s): return list(s.clips)

class MediaPool:
    def __init__(s, proj): s.proj, s.root, s.cur = proj, Folder("Master"), None
    def GetRootFolder(s): return s.root
    def AddSubFolder(s, p, n): f = Folder(n); p.subs.append(f); return f
    def SetCurrentFolder(s, f): s.cur = f; return True
    def ImportMedia(s, paths):
        out = []
        for p in paths:
            if p.endswith(".wav"): it = MPItem(p, 4971, 30.0, "")
            elif p.endswith(".png"): it = MPItem(p, 125, 30.0, "1920x1080")
            else:
                it = MPItem(p, 900, 25.0)
            s.cur.clips.append(it); out.append(it)
        return out
    def CreateEmptyTimeline(s, name):
        if any(t.name == name for t in s.proj.timelines): return None
        t = Timeline(s.proj, name); s.proj.timelines.append(t); return t
    def AppendToTimeline(s, infos):
        tl = s.proj.cur_tl; out = []
        for info in infos:
            it = info["mediaPoolItem"]
            a, b = info.get("startFrame", 0), info.get("endFrame", it.frames)
            n_src = min(b, it.frames) - a
            n = int(round(n_src * FPS / it.fps))
            kind = "audio" if (info.get("mediaType") == 2 or it.path.endswith(".wav")) else "video"
            idx = info.get("trackIndex", 1)
            rec = info.get("recordFrame")
            ti = TLItem(tl, kind, idx, rec, rec + n, it); tl._add(ti); out.append(ti)
        return out
    def ImportTimelineFromFile(s, path, opts):
        ET.parse(path)                                   # must be well-formed
        t = Timeline(s.proj, opts["timelineName"]); s.proj.timelines.append(t)
        t.items.append(TLItem(t, "video", 1, 108000, 108100, None)); return t

class MediaStorage:
    def AddItemListToMediaPool(s, items): return [MPItem(i["media"], i["endFrame"] - i["startFrame"] + 1, 25.0) for i in items]

class Project:
    def __init__(s, name): s.name, s.timelines, s.cur_tl, s.settings, s.jobs, s.groups = name, [], None, {}, [], []; s.mp = MediaPool(s)
    def GetName(s): return s.name
    def SetSetting(s, k, v):
        if k == "timelinePlaybackFrameRate": return False
        s.settings[k] = v; return True
    def GetSetting(s, k): return s.settings.get(k, "30")
    def GetMediaPool(s): return s.mp
    def GetTimelineCount(s): return len(s.timelines)
    def GetTimelineByIndex(s, i): return s.timelines[i - 1]
    def SetCurrentTimeline(s, t): s.cur_tl = t; return True
    def RefreshLUTList(s): return True
    def GetColorGroupsList(s): return list(s.groups)
    def AddColorGroup(s, n):
        g = type("G", (), {"GetName": lambda self: n})(); s.groups.append(g); return g
    def ExportCurrentFrameAsStill(s, p): open(p, "wb").write(b"png"); return True
    def SetCurrentRenderMode(s, m): return True
    def GetRenderPresetList(s): return ["H.264 Master", "YouTube - 1080p", "YouTube - 2160p", "Vertical - 1080p"]
    def LoadRenderPreset(s, n): return True
    def SaveAsNewRenderPreset(s, n): return True
    def SetCurrentRenderFormatAndCodec(s, f, c): return True
    def SetRenderSettings(s, d): s.render = dict(d); return True
    def AddRenderJob(s): s.jobs.append((s.cur_tl.name, dict(s.render))); return "job%d" % len(s.jobs)
    def StartRendering(s, *ids):
        for _, d in s.jobs: open(os.path.join(d["TargetDir"], d["CustomName"] + ".mp4"), "wb").write(b"x")
        return True
    def IsRenderingInProgress(s): return False
    def GetRenderJobStatus(s, j): return {"JobStatus": "Complete", "CompletionPercentage": 100}
    def GetRenderJobList(s): return []

class PM:
    def __init__(s): s.cur = None
    def GetCurrentProject(s): return s.cur
    def CreateProject(s, n): s.cur = Project(n); return s.cur
    def SaveProject(s): return True
    def ExportProject(s, n, p, w=True): open(p, "w").write("drp"); return True

class Resolve:
    EXPORT_OTIO, EXPORT_TEXT_CSV, EXPORT_NONE = 1, 2, 0
    def __init__(s): s.pm = PM()
    def GetProjectManager(s): return s.pm
    def GetMediaStorage(s): return MediaStorage()
    def GetProductName(s): return "DaVinci Resolve (mock)"
    def GetVersionString(s): return "21.0.4.5"
    def OpenPage(s, p): return True
    def GetFairlightPresets(s): return []
    def Fusion(s): return None

STATE_FAIL = {}

def setup():
    home = tempfile.mkdtemp()
    d = os.path.join(home, "Movies/GrokBot-Resolve/example")
    man = json.load(open(EXAMPLE))
    os.makedirs(d)
    files = [s["clip"] for s in man["sections"]] + [man["music"]] + [v for k, v in man["brand"].items() if k in ("logo_16x9", "logo_9x16", "wordmark")]
    for f in files:
        os.makedirs(os.path.dirname(os.path.join(d, f)), exist_ok=True)
        open(os.path.join(d, f), "wb").write(b"0")
    shutil.copy(EXAMPLE, os.path.join(d, "manifest.json"))
    # an older non-full-edit manifest must be ignored
    os.makedirs(os.path.join(home, "Movies/GrokBot-Resolve/old-assembly"))
    json.dump({"project": "old", "pieces": []}, open(os.path.join(home, "Movies/GrokBot-Resolve/old-assembly/manifest.json"), "w"))
    return home

def run_case(home, extra_globals=None):
    os.environ["HOME"] = home
    res = Resolve()
    g = {"__name__": "__main__", "resolve": res}
    g.update(extra_globals or {})
    src = open(SCRIPT).read().replace("STAGE_PAUSE = 1.0", "STAGE_PAUSE = 0.0")
    real = time.sleep; time.sleep = lambda x: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(src, SCRIPT, "exec"), g)
    finally:
        time.sleep = real
    log = open(os.path.join(home, "Movies/GrokBot-Resolve/log.txt")).read()
    return res, g, log

def renders(home): return os.path.join(home, "Movies/GrokBot-Resolve/renders")


# ---------- case 1: no-touch run with defaults ----------
h = setup(); r, g, log = run_case(h)
p = r.pm.cur
assert "DONE:" in log and "FAILED" not in log, log[-3000:]
main = [t for t in p.timelines if t.name.endswith("Grok Bot edit")][0]
v1 = main.GetItemListInTrack("video", 1)
exp = 108000
for it in v1:
    assert it.start == exp, ("gap/overlap", it.start, exp); exp = it.end
clips = [it for it in v1 if it.mpi]
assert len(clips) == 3 and len(v1) == 6, len(v1)
assert clips[0].end - clips[0].start == 330                 # 1.0-12.0 s at 25 fps -> 11 s at 30 fps
assert all(c.comps and c.comps[0].kind == "clip" for c in clips)
assert main.GetItemListInTrack("video", 2) and main.GetItemListInTrack("audio", 1)
assert [t for t in p.timelines if "vertical" in t.name] and [t for t in p.timelines if "dissolves" in t.name]
fx = ET.parse(os.path.join(h, "Movies/GrokBot-Resolve/example/grokbot-dissolves.fcpxml")).getroot()
assert len(fx.findall(".//transition")) == 2
rd = renders(h)
for f in ("my-product-demo.mp4", "my-product-demo-vertical.mp4", "my-product-demo-chapters.txt", "my-product-demo-report.json"):
    assert os.path.exists(os.path.join(rd, f)), f
print("PASS no-touch defaults")
print(open(os.path.join(rd, "my-product-demo-chapters.txt")).read())

# ---------- case 2: cancel -> nothing touched ----------
class C2:
    def AskUser(s, *a): return None
h = setup(); r, g, log = run_case(h, {"fusion": type("F", (), {"GetCurrentComp": lambda self: C2()})()})
assert r.pm.cur is None and "CANCELLED" in log
print("PASS cancel leaves Resolve untouched")

# ---------- case 3: failures are SKIPPED ----------
STATE_FAIL.update(titles=True, cdl=True)
h = setup(); r, g, log = run_case(h)
STATE_FAIL.clear()
assert "DONE:" in log and "SKIPPED Edit: intro Text+ title" in log
print("PASS failures logged as SKIPPED; run reaches DONE")

# ---------- case 4: lock ----------
h = setup(); lp = os.path.join(h, "Movies/GrokBot-Resolve/.fulledit.lock"); open(lp, "w").write("beef 1 now")
r, g, log = run_case(h)
assert r.pm.cur is None and "already in progress" in log
print("PASS single-run lock")
print("\nALL MOCK TESTS PASSED")
