# -*- coding: utf-8 -*-
"""GrokBot_Hello.py - smoke test for DaVinci Resolve menu scripts.

Run from inside Resolve: Workspace > Scripts > GrokBot_Hello
Prints product name/version, the current project and the current page to
Workspace > Console (Py3 tab). Changes nothing.
"""
import sys


def get_resolve():
    r = globals().get("resolve")
    if r:
        return r
    b = globals().get("bmd")
    if b:
        try:
            r = b.scriptapp("Resolve")
            if r:
                return r
        except Exception:
            pass
    a = globals().get("app")
    if a:
        try:
            r = a.GetResolve()
            if r:
                return r
        except Exception:
            pass
    try:
        import DaVinciResolveScript as dvr  # only present if PYTHONPATH is set
        return dvr.scriptapp("Resolve")
    except Exception:
        return None


res = get_resolve()
print("[GrokBot] Hello from a Resolve menu script. Python", sys.version.split()[0])
if not res:
    print("[GrokBot] ERROR: could not get the resolve object")
else:
    try:
        print("[GrokBot] Product:", res.GetProductName(), res.GetVersionString())
    except Exception as e:
        print("[GrokBot] Product: <error>", e)
    try:
        proj = res.GetProjectManager().GetCurrentProject()
        print("[GrokBot] Current project:", proj.GetName() if proj else "<none>")
    except Exception as e:
        print("[GrokBot] Current project: <error>", e)
    try:
        print("[GrokBot] Current page:", res.GetCurrentPage())
    except Exception as e:
        print("[GrokBot] Current page: <error>", e)
print("[GrokBot] Hello done.")
