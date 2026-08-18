#!/usr/bin/env python3
"""Process source media into web assets.

Reads data/media.json, writes into media/, records everything in media/MANIFEST.json.
Idempotent: an entry whose source hash and settings are unchanged is skipped.

    python3 tools/media.py            # process anything new or changed
    python3 tools/media.py --force    # reprocess everything

Needs ffmpeg on PATH (or at ~/.local/bin/ffmpeg) and Pillow.

Images become AVIF, WebP, and JPEG at three widths, wired through <picture> and srcset by
tools/build.py. Video becomes H.264 MP4 with faststart, a VP9 WebM, a poster JPEG taken from a
representative frame rather than frame zero, and a short muted preview loop for grids.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "data" / "media.json").read_text())
OUT = ROOT / "media"
MANIFEST = OUT / "MANIFEST.json"

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
WIDTHS = CFG["widths"]
PREVIEW_W = 480
MAX_VIDEO_W = 1600


def sh(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(args[:6])}...\n{r.stderr[-1500:]}")
    return r


def digest(path, extra=""):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    h.update(extra.encode())
    return h.hexdigest()[:16]


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"images": {}, "frames": {}, "videos": {}}


def emit_responsive(name, im, kind, man, key):
    """Write AVIF, WebP and JPEG at each width. Returns the record."""
    im = im.convert("RGB")
    ow, oh = im.size
    rec = {"kind": kind, "width": ow, "height": oh, "sources": {}, "bytes": {}}
    for w in WIDTHS:
        if w > ow:
            w = ow
        h = round(oh * w / ow)
        resized = im.resize((w, h), Image.LANCZOS)
        for ext, kwargs in (("avif", dict(quality=58)),
                            ("webp", dict(quality=82, method=6)),
                            ("jpg", dict(quality=84, optimize=True, progressive=True))):
            p = OUT / "images" / f"{name}-{w}.{ext}"
            p.parent.mkdir(parents=True, exist_ok=True)
            resized.save(p, **kwargs)
            rec["sources"].setdefault(ext, []).append({"w": w, "path": f"/media/images/{p.name}"})
            rec["bytes"][p.name] = p.stat().st_size
        if w == ow:
            break
    man[key][name] = rec
    return rec


def do_images(man, force):
    for name, spec in CFG["images"].items():
        src = ROOT / spec["src"]
        if not src.exists():
            print(f"  skip {name}: source missing")
            continue
        d = digest(src, json.dumps(WIDTHS))
        if not force and man["images"].get(name, {}).get("digest") == d:
            print(f"  ok   {name} (unchanged)")
            continue
        im = Image.open(src)
        # flatten transparency onto white, these are figures on white pages
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        rec = emit_responsive(name, im, "image", man, "images")
        rec["digest"] = d
        rec["alt"] = spec["alt"]
        rec["caption"] = spec.get("caption", "")
        rec["credit"] = spec.get("credit", "")
        print(f"  wrote {name}  {rec['width']}x{rec['height']}  "
              f"{sum(rec['bytes'].values())/1024:.0f} KB total")


def do_frames(man, force):
    tmp = OUT / ".cache"
    tmp.mkdir(parents=True, exist_ok=True)
    for name, spec in CFG["frames"].items():
        src = (ROOT / spec["src"]).resolve()
        if not src.exists():
            print(f"  skip {name}: source missing")
            continue
        d = digest(src, f"{spec.get('at')}{spec.get('resize')}{WIDTHS}")
        if not force and man["frames"].get(name, {}).get("digest") == d:
            print(f"  ok   {name} (unchanged)")
            continue
        if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            im = Image.open(src)
        else:
            still = tmp / f"{name}.png"
            sh(FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(spec["at"]),
               "-i", str(src), "-frames:v", "1", "-y", str(still))
            im = Image.open(still)
        if spec.get("resize"):
            # panes in one set must share exact dimensions or the crossfade jitters
            im = im.convert("RGB").resize(tuple(spec["resize"]), Image.LANCZOS)
        rec = emit_responsive(name, im, "frame", man, "frames")
        rec["digest"] = d
        rec["alt"] = spec["alt"]
        rec["label"] = spec.get("label", "")
        print(f"  wrote {name}  {rec['width']}x{rec['height']}")


def do_videos(man, force):
    for name, spec in CFG["videos"].items():
        src = (ROOT / spec["src"]).resolve()
        if not src.exists():
            print(f"  skip {name}: source missing")
            continue
        d = digest(src, json.dumps(spec, sort_keys=True))
        prev = man["videos"].get(name, {})
        outputs_present = all((ROOT / str(prev.get(k, "x")).lstrip("/")).exists()
                              for k in ("mp4", "poster") if prev.get(k))
        if not force and prev.get("digest") == d and outputs_present:
            print(f"  ok   {name} (unchanged)")
            continue

        vd = OUT / "video"
        vd.mkdir(parents=True, exist_ok=True)
        crop = spec.get("crop")
        chain = (f"crop={crop}," if crop else "")
        maxw = spec.get("maxWidth", MAX_VIDEO_W)
        scale = f"scale='min({maxw},iw)':-2"
        crf = str(spec.get("crf", 23))
        wcrf = str(spec.get("webmCrf", 36))
        trim = spec.get("trim")
        cut = ["-ss", str(trim["start"]), "-t", str(trim["duration"])] if trim else []

        mp4 = vd / f"{name}.mp4"
        sh(FFMPEG, "-hide_banner", "-loglevel", "error", *cut, "-i", str(src),
           "-vf", chain + scale, "-c:v", "libx264", "-crf", crf, "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           *(["-an"] if spec.get("silent", True) else []), "-y", str(mp4))

        webm = vd / f"{name}.webm"
        sh(FFMPEG, "-hide_banner", "-loglevel", "error", *cut, "-i", str(src),
           "-vf", chain + scale, "-c:v", "libvpx-vp9", "-crf", wcrf, "-b:v", "0",
           "-row-mt", "1", "-cpu-used", "4",
           *(["-an"] if spec.get("silent", True) else []), "-y", str(webm))

        poster_png = OUT / ".cache" / f"{name}-poster.png"
        poster_png.parent.mkdir(parents=True, exist_ok=True)
        sh(FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(spec["posterAt"] + (trim["start"] if trim else 0)),
           "-i", str(src), "-frames:v", "1", "-vf", chain + scale, "-y", str(poster_png))
        pim = Image.open(poster_png).convert("RGB")
        poster = vd / f"{name}-poster.jpg"
        pim.save(poster, quality=82, optimize=True, progressive=True)

        preview = None
        if spec.get("preview"):
            preview = vd / f"{name}-preview.mp4"
            sh(FFMPEG, "-hide_banner", "-loglevel", "error", *cut, "-i", str(src),
               "-vf", chain + f"scale={PREVIEW_W}:-2", "-c:v", "libx264", "-crf", "31",
               "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-an", "-y", str(preview))

        if webm.stat().st_size > 0.85 * mp4.stat().st_size:
            webm.unlink()
            webm = None

        man["videos"][name] = {
            "digest": d,
            "width": pim.size[0], "height": pim.size[1],
            "mp4": f"/media/video/{mp4.name}",
            "webm": (f"/media/video/{webm.name}" if webm else None),
            "poster": f"/media/video/{poster.name}", "preview": (f"/media/video/{preview.name}" if preview else None),
            "bytes": {p.name: p.stat().st_size for p in (mp4, webm, poster, preview) if p},
            "alt": spec["alt"], "caption": spec.get("caption", ""),
            "credit": spec.get("credit", ""),
            # a browser fetches one rendition, so gate on the smallest it could pick
            "clickToLoad": spec.get("clickToLoad", False) or min(
                [mp4.stat().st_size] + ([webm.stat().st_size] if webm else [])
            ) > 8 * 1024 * 1024,
        }
        tot = sum(man["videos"][name]["bytes"].values()) / 1024 / 1024
        print(f"  wrote {name}  {pim.size[0]}x{pim.size[1]}  "
              f"mp4 {mp4.stat().st_size/1e6:.1f} MB, "
              f"webm {webm.stat().st_size/1e6:.1f} MB, " if webm else "webm dropped, "
              f"(total {tot:.1f} MB)"
              + ("  [click to load]" if man['videos'][name]['clickToLoad'] else ""))


def refresh_text(man):
    """Alt text, captions and labels are metadata, not pixels. Update them on every run so that
    editing data/media.json does not require a re-encode."""
    n = 0
    for key in ("images", "frames", "videos"):
        for name, spec in CFG.get(key, {}).items():
            rec = man.get(key, {}).get(name)
            if not rec:
                continue
            for field in ("alt", "caption", "credit", "label"):
                if field in spec and rec.get(field) != spec[field]:
                    rec[field] = spec[field]
                    n += 1
    if n:
        print(f"  refreshed {n} text fields")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    man = load_manifest()
    print("images:");  do_images(man, a.force)
    print("frames:");  do_frames(man, a.force)
    print("videos:");  do_videos(man, a.force)
    refresh_text(man)
    MANIFEST.write_text(json.dumps(man, indent=2))
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()
                and ".cache" not in p.parts)
    print(f"\nmedia/ total: {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
