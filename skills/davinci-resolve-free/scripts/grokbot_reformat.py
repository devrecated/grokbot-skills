#!/usr/bin/env python3
"""grokbot_reformat.py - the only step Grok Bot does outside DaVinci Resolve.

Takes Resolve's finished 16:9 export (and optional thumbnail frame) and makes
platform deliverables. Nothing here edits the cut: no trims, no grades, no mix.

  vertical   16:9 export -> 1080x1920 Shorts/Reels/TikTok-safe MP4. The picture is
             fitted inside the platform safe area (default 250 px top, 420 px bottom,
             150 px right, 60 px left free of UI), over a blurred, darkened copy of
             itself. Audio is copied untouched.
  thumb      Resolve thumbnail frame (PNG) -> 1280x720 YouTube thumbnail and a
             1080x1920 cover, with an optional headline.
  check      Draws the safe-zone boxes on a frame of a vertical video so you can
             eyeball it (e.g. Resolve's own 9:16 render).

Usage:
  grokbot_reformat.py vertical in.mp4 out.mp4 [--top 250 --bottom 420 --right 150 --left 60]
  grokbot_reformat.py thumb frame.png out_prefix [--title "My video"]
  grokbot_reformat.py check vertical.mp4 out.png [--at 5]
Requires ffmpeg on PATH; Pillow for thumb/check.
"""
import argparse
import json
import os
import subprocess
import sys


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"]), s["r_frame_rate"]


def vertical(args):
    W, H = 1080, 1920
    box_w = W - args.left - args.right
    box_h = H - args.top - args.bottom
    w, h, _ = probe(args.input)
    scale = min(box_w / w, box_h / h)
    fw, fh = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    x = args.left + (box_w - fw) // 2
    y = args.top + (box_h - fh) // 2
    fc = ("[0:v]split=2[bg][fg];"
          "[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=30:3,eq=brightness=-0.18:saturation=0.8[b];"
          "[fg]scale=%d:%d:flags=lanczos[f];"
          "[b][f]overlay=%d:%d,format=yuv420p[v]" % (W, H, W, H, fw, fh, x, y))
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", args.input, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-c:a", "copy",
           "-movflags", "+faststart", args.output]
    subprocess.run(cmd, check=True)
    print(json.dumps({"output": args.output, "picture_box": [x, y, fw, fh],
                      "safe_area": {"top": args.top, "bottom": args.bottom, "left": args.left, "right": args.right}}))


def thumb(args):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    src = Image.open(args.frame).convert("RGB")

    def font(size):
        for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.isfile(f):
                return ImageFont.truetype(f, size)
        return ImageFont.load_default()

    yt = src.resize((1280, 720), Image.LANCZOS)
    if args.title:
        d = ImageDraw.Draw(yt, "RGBA")
        d.rectangle([0, 520, 1280, 720], fill=(8, 12, 20, 200))
        d.text((48, 560), args.title, font=font(76), fill=(240, 247, 255))
    yt.save(args.out_prefix + "-youtube-1280x720.jpg", quality=92)
    cover = src.resize((int(1920 * src.width / src.height), 1920)).crop((0, 0, 1080, 1920)).filter(ImageFilter.GaussianBlur(24))
    fg = src.resize((960, int(960 * src.height / src.width)), Image.LANCZOS)
    cover.paste(fg, (60, 250 + (1250 - fg.height) // 2))
    if args.title:
        d = ImageDraw.Draw(cover, "RGBA")
        d.text((60, 300), args.title, font=font(72), fill=(240, 247, 255))
    cover.save(args.out_prefix + "-cover-1080x1920.jpg", quality=92)
    print(json.dumps({"youtube": args.out_prefix + "-youtube-1280x720.jpg", "cover": args.out_prefix + "-cover-1080x1920.jpg"}))


def check(args):
    from PIL import Image, ImageDraw
    tmp = args.output + ".frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.at), "-i", args.input, "-frames:v", "1", tmp], check=True)
    im = Image.open(tmp).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, W, args.top], fill=(255, 0, 0, 70))
    d.rectangle([0, H - args.bottom, W, H], fill=(255, 0, 0, 70))
    d.rectangle([W - args.right, 0, W, H], fill=(255, 0, 0, 70))
    im.save(args.output)
    os.remove(tmp)
    print(args.output)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("vertical"); v.add_argument("input"); v.add_argument("output")
    for k, dflt in (("top", 250), ("bottom", 420), ("right", 150), ("left", 60)):
        v.add_argument("--" + k, type=int, default=dflt)
    t = sub.add_parser("thumb"); t.add_argument("frame"); t.add_argument("out_prefix"); t.add_argument("--title", default="")
    c = sub.add_parser("check"); c.add_argument("input"); c.add_argument("output"); c.add_argument("--at", type=float, default=5)
    for k, dflt in (("top", 250), ("bottom", 420), ("right", 150)):
        c.add_argument("--" + k, type=int, default=dflt)
    a = p.parse_args()
    {"vertical": vertical, "thumb": thumb, "check": check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
