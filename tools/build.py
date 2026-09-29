#!/usr/bin/env python3
"""Render the static site from data/*.json.

Python 3 standard library only. No npm, no bundler, no framework.
Output is plain HTML committed to the repository, so GitHub Pages serves files that were
never touched by a build step at request time. Run this after editing anything in data/.

    python3 tools/build.py

Every page it writes contains its full text in the served HTML. Nothing that matters for
search is injected by JavaScript.
"""

import argparse
import html
import json
import os
import re
import shutil
import struct
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TODAY = date.today().isoformat()

SITE = json.loads((DATA / "site.json").read_text())
PUBS = json.loads((DATA / "publications.json").read_text())
PROJECTS = json.loads((DATA / "projects.json").read_text())
TIMELINE = json.loads((DATA / "timeline.json").read_text())
_mf = ROOT / "media" / "MANIFEST.json"
MEDIA = json.loads(_mf.read_text()) if _mf.exists() else {"images": {}, "frames": {}, "videos": {}}
MEDIACFG = json.loads((DATA / "media.json").read_text())
CV = json.loads((DATA / "cv.json").read_text())
GRAPHICS = json.loads((DATA / "graphics.json").read_text())
VIDEOPAGES = json.loads((DATA / "videos.json").read_text())["pages"]

ORIGIN = SITE["origin"].rstrip("/")
NAME = SITE["identity"]["canonicalName"]
PUBNAME = SITE["identity"]["publishingName"]

ORCID_URL = SITE["links"].get("orcid")

# media key -> its watch page. A clip with an entry here has one page whose only subject is
# that clip, and every mention of it anywhere else on the site points back at that page.
WATCH = {w["key"]: w for w in VIDEOPAGES}


def watch_url(key, absolute=False):
    w = WATCH.get(key)
    if not w:
        return ""
    return (ORIGIN if absolute else "") + f"/videos/{w['slug']}/"


def _orcid_id(url):
    """Bare iD from the canonical URL, checksum-verified.

    A wrong ORCID asserts that two different people are the same person, which is the exact
    mistake the ieeeAuthorPageNote in site.json records. Fail the build rather than publish
    an identifier that does not check out.
    """
    if not url:
        return None
    m = re.fullmatch(r"https://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", url)
    if not m:
        raise SystemExit(f"links.orcid is not a canonical ORCID URL: {url!r}")
    ident = m.group(1)
    digits = ident.replace("-", "")
    total = 0
    for d in digits[:15]:
        total = (total + int(d)) * 2
    expect = (12 - total % 11) % 11
    expect = "X" if expect == 10 else str(expect)
    if expect != digits[15]:
        raise SystemExit(f"ORCID checksum fails for {ident}: check digit should be {expect}")
    return ident


ORCID_ID = _orcid_id(ORCID_URL)

PAGES = []  # collected for sitemap.xml


def check_media():
    """Every path the manifest promises has to exist, or a player somewhere shows a poster
    that never plays."""
    missing = []
    for key, rec in MEDIA.get("videos", {}).items():
        for field in ("mp4", "webm", "poster", "preview"):
            path = rec.get(field)
            if path and not (ROOT / path.lstrip("/")).exists():
                missing.append(f"videos/{key}.{field}: {path}")
    for group in ("images", "frames"):
        for key, rec in MEDIA.get(group, {}).items():
            for ext, variants in rec.get("sources", {}).items():
                for v in variants:
                    if not (ROOT / v["path"].lstrip("/")).exists():
                        missing.append(f"{group}/{key}.{ext}: {v['path']}")
    return missing


def git_lastmod(path):
    """Last commit date for the data that produced a page, falling back to today."""
    import subprocess
    for candidate in (path + "/index.html" if path else "index.html", "data"):
        try:
            r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", candidate],
                               cwd=ROOT, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return TODAY


def git_filedate(relpath):
    """Last commit date for one file, so a VideoObject uploadDate stays put across builds.

    TODAY would move every time the site is rebuilt, which reads to a crawler as a video
    that is republished daily."""
    import subprocess
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", relpath.lstrip("/")],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return TODAY


MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def humandate(v):
    """2017-11 -> November 2017, 2026-08-01 -> August 2026, 2014 -> 2014."""
    if not v:
        return ""
    parts = str(v).split("-")
    if len(parts) == 1:
        return parts[0]
    return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"


ROMAN = {1: "I", 2: "II", 3: "III"}


def e(s):
    return html.escape(str(s), quote=True)


def authors_html(authors):
    out = []
    for a in authors:
        cls = ' class="self"' if a.replace(" ", "") == PUBNAME.replace(" ", "") else ""
        out.append(f"<span{cls}>{e(a)}</span>")
    return ", ".join(out)


def jsonld(obj):
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(obj, indent=2, ensure_ascii=False)
        + "\n</script>"
    )


def profile_page_node():
    return {"@context": "https://schema.org", "@type": "ProfilePage",
            "@id": f"{ORIGIN}/#profilepage",
            "url": f"{ORIGIN}/",
            "name": f"{NAME}, {SITE['identity']['role']}",
            "mainEntity": {"@id": f"{ORIGIN}/#person"},
            "dateModified": TODAY}


def breadcrumbs(path, title, flat=False):
    """flat: Home then this page, skipping the path segments in between. Used where a
    directory in the URL is only a container and has no page of its own to link to."""
    if not path:
        return None
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{ORIGIN}/"}]
    if flat:
        crumbs.append({"@type": "ListItem", "position": 2, "name": title,
                       "item": f"{ORIGIN}/{path}/"})
        return {"@context": "https://schema.org", "@type": "BreadcrumbList",
                "itemListElement": crumbs}
    parts = path.split("/")
    acc = ""
    for i, seg in enumerate(parts, start=2):
        acc += seg + "/"
        label = title if i == len(parts) + 1 else seg.replace("-", " ").title()
        crumbs.append({"@type": "ListItem", "position": i, "name": label,
                       "item": f"{ORIGIN}/{acc}"})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": crumbs}


def person_node():
    L = SITE["links"]
    same = [L[k] for k in ("orcid", "googleScholar", "github", "linkedin",
                           "utStaffPage", "ieeeAuthorPage", "youtube") if L.get(k)]
    node = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": f"{ORIGIN}/#person",
        "name": NAME,
        "alternateName": SITE["identity"]["alternateNames"],
        "jobTitle": SITE["identity"].get("headline") or SITE["identity"]["role"],
        "url": f"{ORIGIN}/",
        "affiliation": {
            "@type": "Organization",
            "name": SITE["identity"]["affiliation"]["name"],
            "url": SITE["identity"]["affiliation"]["url"],
        },
        "knowsAbout": [
            "monocular SLAM", "visual-inertial odometry", "3D scene graphs",
            "metric-semantic mapping", "multi-task learning", "dense prediction",
            "autonomous exploration", "edge deployment",
        ],
        "sameAs": same,
    }
    if SITE["contact"].get("email"):
        node["email"] = f"mailto:{SITE['contact']['email']}"
    node["image"] = portrait_node()
    return node


def portrait_node():
    """The portrait as a full ImageObject at its largest encode.

    A knowledge panel or a person card picks the biggest usable copy, so point at the
    1254px original rather than the 480px one the page happens to lay out."""
    img = SITE["identity"].get("image") or "/media/og/home.png"
    rec = MEDIA.get("images", {}).get("portrait")
    if rec:
        jpg = [x for x in rec.get("sources", {}).get("jpg", []) if x.get("path")]
        if jpg:
            best = max(jpg, key=lambda x: x["w"])
            return {
                "@type": "ImageObject",
                "@id": f"{ORIGIN}/#portrait",
                "url": ORIGIN + best["path"],
                "contentUrl": ORIGIN + best["path"],
                "width": best["w"],
                "height": round(best["w"] * rec["height"] / rec["width"]),
                "caption": f"{NAME}, {SITE['identity']['role']}",
                "creditText": NAME,
                "copyrightHolder": {"@id": f"{ORIGIN}/#person"},
            }
    return ORIGIN + img


def asset_hash(path):
    """Content-hashed asset URL. GitHub Pages caches by filename, so a redeploy that only
    changes site.css or media.js would otherwise reach visitors late or not at all."""
    f = ROOT / path.lstrip("/")
    if not f.exists():
        return ""
    import hashlib
    return hashlib.sha256(f.read_bytes()).hexdigest()[:10]


def picture(key, cls="", sizes="(min-width: 56em) 62rem, 100vw", lazy=True, caption=True):
    """Responsive <picture> from the media manifest. Empty string if the asset is absent."""
    rec = MEDIA["images"].get(key) or MEDIA["frames"].get(key)
    if not rec:
        return ""
    def srcset(ext):
        return ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"][ext])
    biggest = rec["sources"]["jpg"][-1]["path"]
    loading = 'loading="lazy" decoding="async"' if lazy else 'decoding="async"'
    img = (f'<picture>'
           f'<source type="image/avif" srcset="{srcset("avif")}" sizes="{sizes}">'
           f'<source type="image/webp" srcset="{srcset("webp")}" sizes="{sizes}">'
           f'<img src="{biggest}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
           f'height="{rec["height"]}" {loading}>'
           f'</picture>')
    if caption and rec.get("caption"):
        return (f'<figure class="{cls}">{img}'
                f'<figcaption>{e(rec["caption"])}</figcaption></figure>')
    return f'<figure class="{cls}">{img}</figure>' if cls else img


def gate_size(rec):
    """What the click actually costs, in MB. A browser fetches one rendition, so this is the
    smallest of them and not the sum of every file the encode produced."""
    sizes = [rec["bytes"][Path(rec[k]).name] for k in ("mp4", "webm")
             if rec.get(k) and rec["bytes"].get(Path(rec[k]).name)]
    return min(sizes) / 1e6 if sizes else 0.0


def video(key, cls="", autoloop=True, watch_link=True, caption=None):
    """Poster-first video. Autoplay is handled by media.js only when in view.

    A clip that has a watch page gets a link to it in the caption, so the page Google is
    meant to rank for that video is reachable from every page the clip appears on."""
    rec = MEDIA["videos"].get(key)
    if not rec:
        return ""
    sources = f'<source src="{rec["mp4"]}" type="video/mp4">'
    if rec.get("webm"):
        sources = f'<source src="{rec["webm"]}" type="video/webm">' + sources
    # a clip with its own controls costs nothing until the reader presses play, so it goes
    # straight into the page; the size gate is for the ones that start themselves
    gated = rec.get("clickToLoad") and not rec.get("audio")
    if rec.get("audio"):
        # narrated clip: it is watched once with the sound on, not looped as wallpaper
        attrs = 'controls playsinline preload="none"'
    else:
        attrs = 'muted loop playsinline preload="none"'
        if autoloop and not gated:
            attrs += ' data-autoloop'
    inner = (f'<video poster="{rec["poster"]}" width="{rec["width"]}" height="{rec["height"]}" '
             f'{attrs} aria-label="{e(rec["alt"])}">{sources}</video>')
    if gated:
        body = (f'<div class="v-gate" data-gate>'
                f'<img src="{rec["poster"]}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
                f'height="{rec["height"]}" loading="lazy" decoding="async">'
                f'<button type="button" class="v-play" data-gate-btn>Load video '
                f'<span class="v-size">{gate_size(rec):.1f} MB</span></button>'
                f'<template data-gate-src>{html.escape(inner)}</template></div>')
    elif rec.get("audio"):
        # the native controls are the play button, so no overlay of our own
        body = f'<div class="v-wrap">{inner}</div>'
    else:
        body = (f'<div class="v-wrap">{inner}'
                f'<button type="button" class="v-toggle" data-toggle '
                f'aria-label="Play or pause video">Pause</button>'
                f'<button type="button" class="v-expand" data-expand hidden '
                f'aria-label="Play this clip in a larger frame">'
                f'<span aria-hidden="true">&#x2921;</span>Expand</button></div>')
    link = (f'<a class="watch-link" href="{watch_url(key)}">Watch the full clip</a>'
            if watch_link and key in WATCH else "")
    text = e(caption if caption is not None else rec.get("caption", ""))
    cap = f'<figcaption>{text}{link}</figcaption>' if (text or link) else ""
    tall = " is-portrait" if rec["height"] > rec["width"] else ""
    return f'<figure class="v-figure {cls}{tall}">{body}{cap}</figure>'


def hero_clip(key):
    """The stage clip on the home page. The inline loop is the small preview encode, so the
    landing page stays light; Expand loads the full clip in the lightbox."""
    rec = MEDIA["videos"].get(key)
    if not rec:
        return ""
    preview = rec.get("preview")
    if preview and not (ROOT / preview.lstrip("/")).exists():
        preview = None          # the encode was never produced; the full clip plays inline
    inline = preview or rec["mp4"]
    full = f' data-full-src="{rec["mp4"]}"' if preview else ""
    return (f'<div class="hero-clip v-wrap">'
            f'<video poster="{rec["poster"]}" width="{rec["width"]}" height="{rec["height"]}" '
            f'muted loop playsinline preload="metadata" data-autoloop{full} '
            f'aria-label="{e(rec["alt"])}"><source src="{inline}" type="video/mp4"></video>'
            f'<button type="button" class="v-toggle" data-toggle '
            f'aria-label="Play or pause video">Pause</button>'
            f'<button type="button" class="v-expand" data-expand hidden '
            f'aria-label="Play this clip in a larger frame">'
            f'<span aria-hidden="true">&#x2921;</span>Expand</button></div>')


def mp4_duration(path):
    """Clip length in seconds, read from the MP4 mvhd atom.

    Google wants a duration on a VideoObject and there is no ffprobe in the build, so walk
    the top-level boxes to moov and read the header the file already carries. Returns None
    if anything is not where the spec says it should be."""
    f = ROOT / path.lstrip("/")
    if not f.exists():
        return None
    try:
        end = f.stat().st_size
        with f.open("rb") as fh:
            pos = 0
            while pos < end:
                fh.seek(pos)
                head = fh.read(8)
                if len(head) < 8:
                    return None
                size, kind = struct.unpack(">I4s", head)
                if size == 1:
                    size = struct.unpack(">Q", fh.read(8))[0]
                elif size == 0:
                    size = end - pos
                if size < 8:
                    return None
                if kind == b"moov":
                    box = fh.read(min(size, 1 << 20))
                    i = box.find(b"mvhd")
                    if i < 0:
                        return None
                    if box[i + 4] == 0:
                        scale, ticks = struct.unpack(">II", box[i + 16:i + 24])
                    else:
                        scale, ticks = struct.unpack(">IQ", box[i + 24:i + 36])
                    return round(ticks / scale) if scale else None
                pos += size
    except Exception:
        return None
    return None


def iso_duration(secs):
    """Seconds -> ISO 8601, the only duration format Google reads."""
    if not secs:
        return None
    m, sec = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return "PT" + (f"{h}H" if h else "") + (f"{m}M" if m else "") + (f"{sec}S" if sec else "")


def video_title(key, rec):
    """A whole sentence for the VideoObject name, never a cut mid-word.

    The name is what Google prints under the thumbnail in a video result, so it has to
    read as a title rather than as the first 110 bytes of a caption."""
    text = (rec.get("caption") or rec.get("alt") or "").strip()
    if not text:
        return f"{NAME} | {key.replace('-', ' ')}"
    first = re.split(r"(?<=[.!?])\s", text)[0].strip().rstrip(".")
    if len(first) > 100:
        first = first[:100].rsplit(" ", 1)[0].rstrip(",;:")
    return first


def video_ld(key, page_url):
    """One VideoObject for one clip.

    A clip with a watch page is described against that page wherever it appears: the same
    @id, the same mainEntityOfPage, and a url pointing at it. The alternative is one node
    per embedding page, which asks Google to choose which of six pages a video belongs to."""
    rec = MEDIA["videos"].get(key)
    if not rec:
        return None
    w = WATCH.get(key)
    home = watch_url(key, absolute=True) if w else page_url
    node = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "@id": f"{home}#video-{key}",
        "name": w["title"] if w else video_title(key, rec),
        "description": rec["alt"],
        "thumbnailUrl": ORIGIN + rec["poster"],
        "uploadDate": git_filedate(rec["mp4"]),
        "contentUrl": ORIGIN + rec["mp4"],
        "width": rec["width"],
        "height": rec["height"],
        "inLanguage": "en",
        "isFamilyFriendly": True,
        "creator": {"@id": f"{ORIGIN}/#person", "@type": "Person", "name": NAME},
        "copyrightHolder": {"@id": f"{ORIGIN}/#person", "@type": "Person", "name": NAME},
        "mainEntityOfPage": home,
    }
    # contentUrl is the file itself, so no embedUrl: there is no third-party player here
    # and pointing embedUrl at the page describes a player that does not exist.
    d = iso_duration(mp4_duration(rec["mp4"]))
    if d:
        node["duration"] = d
    if w:
        node["url"] = home
        node["description"] = w["description"] + " " + rec["alt"]
        if w.get("chapters"):
            # Key moments. Each url carries a media fragment the watch page seeks to, so a
            # result that lands on a chapter starts where the chapter starts.
            node["hasPart"] = [{
                "@type": "Clip",
                "name": c["name"],
                "startOffset": c["start"],
                "endOffset": c["end"],
                "url": f"{home}#t={c['start']}",
            } for c in w["chapters"]]
    return node


# Every path a clip can appear under in the markup, back to its media key. The preview
# encode counts: on the home page that is the file the inline <source> points at.
VIDEO_BY_PATH = {}
for _k, _r in MEDIA.get("videos", {}).items():
    for _f in (_r.get("mp4"), _r.get("preview")):
        if _f:
            VIDEO_BY_PATH[_f] = _k


def videos_in(body):
    """Media keys for the clips this page actually carries, in the order they appear."""
    found = []
    for path in re.findall(r"/media/video/[A-Za-z0-9_.-]+\.mp4", body):
        k = VIDEO_BY_PATH.get(path)
        if k and k not in found:
            found.append(k)
    return found


def wipe(set_id="itc-corridor", heading=True, compact=False, start=2,
         sizes="(min-width:56em) 22rem, 92vw"):
    """One frame, three ways: RGB, predicted depth, predicted semantics.

    `start` picks the layer shown first once JavaScript is running, and defaults to the
    semantic prediction rather than the raw camera frame. Without JavaScript the three
    panes sit side by side, which is already the point."""
    spec = MEDIACFG.get("wipeSets", {}).get(set_id)
    if not spec:
        return ""
    keys = spec["panes"]
    if not all(k in MEDIA["frames"] for k in keys):
        return ""
    panes, steps = "", ""
    for i, k in enumerate(keys):
        rec = MEDIA["frames"][k]
        big = rec["sources"]["jpg"][-1]["path"]
        av = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["avif"])
        wp = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["webp"])
        panes += (f'<div class="wipe-pane" data-pane="{i}">'
                  f'<picture>'
                  f'<source type="image/avif" srcset="{av}" sizes="{sizes}">'
                  f'<source type="image/webp" srcset="{wp}" sizes="{sizes}">'
                  f'<img src="{big}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
                  f'height="{rec["height"]}" loading="lazy" decoding="async"></picture>'
                  f'<span class="wipe-label">{e(rec["label"])}</span></div>')
        steps += (f'<button type="button" class="wipe-step" data-wipe-step="{i}" '
                  f'aria-pressed="{"true" if i == start else "false"}">{e(rec["label"])}'
                  f'</button>')
    head = f'<p class="wipe-title">{e(spec["title"])}</p>' if heading else ""
    cap = spec.get("captionShort") if compact else spec["caption"]
    cap = cap or spec["caption"]
    cls = "wipe wipe-compact" if compact else "wipe"
    return (f'<figure class="{cls}" data-wipe>{head}'
            f'<div class="wipe-stage">{panes}</div>'
            f'<div class="wipe-steps" data-wipe-steps hidden role="group" '
            f'aria-label="Choose the layer to show">{steps}</div>'
            f'<label class="wipe-control" data-wipe-control hidden>'
            f'<span class="sr-only">Blend between RGB, predicted depth, and predicted semantics'
            f'</span>'
            f'<input type="range" min="0" max="200" value="{start * 100}" step="1" '
            f'data-wipe-input>'
            f'</label>'
            f'<figcaption>{e(cap)} Pick a layer, or drag to blend between them.'
            f'</figcaption></figure>')


def platform_showcase(lead, pair, clip):
    """One wide still, two beneath it, and the flight clip running full height beside them."""
    def img(key, cls):
        rec = MEDIA["images"].get(key)
        if not rec:
            return ""
        av = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["avif"])
        wp = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["webp"])
        big = rec["sources"]["jpg"][-1]["path"]
        sizes = "(min-width: 52em) 34rem, 100vw" if cls == "ps-lead" else "(min-width: 52em) 17rem, 50vw"
        return (f'<div class="{cls}"><picture>'
                f'<source type="image/avif" srcset="{av}" sizes="{sizes}">'
                f'<source type="image/webp" srcset="{wp}" sizes="{sizes}">'
                f'<img src="{big}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
                f'height="{rec["height"]}" loading="lazy" decoding="async">'
                f'</picture></div>')

    rec = MEDIA["videos"].get(clip)
    vid = ""
    if rec:
        sources = f'<source src="{rec["mp4"]}" type="video/mp4">'
        if rec.get("webm"):
            sources = f'<source src="{rec["webm"]}" type="video/webm">' + sources
        vid = (f'<div class="ps-clip v-wrap">'
               f'<video poster="{rec["poster"]}" width="{rec["width"]}" height="{rec["height"]}" '
               f'muted loop playsinline preload="none" data-autoloop '
               f'aria-label="{e(rec["alt"])}">{sources}</video>'
               f'<button type="button" class="v-toggle" data-toggle '
               f'aria-label="Play or pause video">Pause</button>'
               f'<button type="button" class="v-expand" data-expand hidden '
               f'aria-label="Play this clip in a larger frame">'
               f'<span aria-hidden="true">&#x2921;</span>Expand</button></div>')

    caption = (rec or {}).get("caption", "")
    return (f'<figure class="showcase">'
            f'<div class="showcase-grid">'
            f'{img(lead, "ps-lead")}'
            f'{"".join(img(k, "ps-small") for k in pair)}'
            f'{vid}'
            f'</div>'
            f'{f"<figcaption>{e(caption)}</figcaption>" if caption else ""}</figure>')


def gallery(lead, rest, caption=""):
    """One large figure on the left, the remaining angles stacked in a column on the right."""
    lead_rec = MEDIA["images"].get(lead)
    if not lead_rec:
        return ""

    def frame(key, cls):
        rec = MEDIA["images"].get(key)
        if not rec:
            return ""
        av = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["avif"])
        wp = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["webp"])
        big = rec["sources"]["jpg"][-1]["path"]
        sizes = ("(min-width: 52em) 40rem, 100vw" if cls == "g-lead"
                 else "(min-width: 52em) 18rem, 50vw")
        return (f'<div class="{cls}">'
                f'<picture>'
                f'<source type="image/avif" srcset="{av}" sizes="{sizes}">'
                f'<source type="image/webp" srcset="{wp}" sizes="{sizes}">'
                f'<img src="{big}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
                f'height="{rec["height"]}" loading="lazy" decoding="async">'
                f'</picture></div>')

    thumbs = "".join(frame(k, "g-thumb") for k in rest)
    cap = caption or lead_rec.get("caption", "")
    return (f'<figure class="gallery">'
            f'<div class="gallery-grid">{frame(lead, "g-lead")}'
            f'<div class="gallery-side">{thumbs}</div></div>'
            f'{f"<figcaption>{e(cap)}</figcaption>" if cap else ""}</figure>')


def switcher(sid, panels, label="Media views"):
    """panels: list of (label, html). One slot, one visible panel, buttons to change it."""
    panels = [(lab, h) for lab, h in panels if h]
    if not panels:
        return ""
    if len(panels) == 1:
        return panels[0][1]
    tabs = "".join(
        f'<button type="button" role="tab" id="{sid}-t{i}" aria-controls="{sid}-p{i}" '
        f'aria-selected="{"true" if i == 0 else "false"}" data-switch-tab>{e(lab)}</button>'
        for i, (lab, _) in enumerate(panels))
    body = "".join(
        f'<div class="switch-panel" role="tabpanel" id="{sid}-p{i}" aria-labelledby="{sid}-t{i}" '
        f'data-switch-panel>{h}</div>'
        for i, (_, h) in enumerate(panels))
    return (f'<div class="switch" data-switch>'
            f'<div class="switch-tabs" role="tablist" aria-label="{e(label)}" hidden data-switch-tabs>{tabs}</div>'
            f'{body}</div>')


def youtube_facade(video_id, title, thumb):
    return (f'<figure class="yt" data-yt="{e(video_id)}">'
            f'<button type="button" class="yt-btn" data-yt-btn>'
            f'<img src="{e(thumb)}" alt="Thumbnail for {e(title)}" width="480" height="360" '
            f'loading="lazy" decoding="async">'
            f'<span class="yt-play" aria-hidden="true"></span>'
            f'<span class="sr-only">Play {e(title)} on YouTube</span></button>'
            f'<figcaption>{e(title)}. The full length version, loaded from YouTube only when '
            f'you press play.</figcaption></figure>')


# which figure belongs to which page
def _pub_figures():
    """Per publication: themedia that actually belongs to that paper, best first."""
    return {
        "mono-hydra-plus": video("stairs-zupt") + pipeline_story()
                           + picture("uhumans2-loop") + picture("scannet-radius")
                           + picture("scannet-failure"),
        "m2h-mx":          video("icra26")
                           + wipe("m2h-mx-indoor", compact=True)
                           + wipe("m2h-mx-outdoor", compact=True)
                           + picture("m2h-mx-architecture") + picture("m2h-mx-rgm")
                           + picture("m2h-mx-ctm-msca"),
        "m2h":             video("itc-loop") + wipe(compact=True)
                           + youtube_facade("X2w_AqGwkaY",
                               "Mono Hydra with M2H for Monocular 3D Scene Graph Construction",
                               MEDIA["videos"]["itc-loop"]["poster"]),
        "mono-hydra":      picture("scenegraph-system-design") + picture("scene-graph-itc"),
    }


def _proj_media():
    return {
        "mono-hydra-plus": gallery("drone-side", ["drone-top", "drone-angle"])
                           + picture("scene-graph-itc") + picture("itc-embedded"),
        "m2h-mx":          video("icra26") + wipe("m2h-mx-indoor", compact=True)
                           + wipe("m2h-mx-outdoor", compact=True)
                           + picture("m2h-mx-architecture"),
        "m2h":             video("itc-loop") + wipe(compact=True),
        "mono-hydra":      picture("scenegraph-system-design"),
        "learned-exploration": video("scope-explorer"),
    }


PUB_FIGURE = {}
PROJ_MEDIA = {}


def og_for(path):
    """Map a page path to its OpenGraph card, falling back to the section card."""
    if path == "":
        slug = "home"
    elif path.startswith("publications/") and path != "publications/bibtex":
        slug = "pub-" + path.split("/", 1)[1]
    elif path.startswith("projects/"):
        slug = "proj-" + path.split("/", 1)[1]
    elif path.startswith("videos/"):
        slug = "video-" + path.split("/", 1)[1]
    elif path == "publications/bibtex":
        slug = "publications"
    else:
        slug = path or "home"
    if not (ROOT / "media" / "og" / f"{slug}.png").exists():
        slug = "home"
    return f"/media/og/{slug}.png"


def clamp(text, limit=155):
    """Trim to a sentence boundary under the limit, else a word boundary."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "? ", "! "):
        i = cut.rfind(sep)
        if i > limit * 0.55:
            return cut[:i + 1].strip()
    i = cut.rfind(" ")
    return cut[:i].rstrip(",;:") + "."


def orcid_mark():
    """The iD beside the wordmark, on every page. Empty when no ORCID is set.

    rel="me" so the link is machine-readable as an identity claim, matching the footer
    profile links. The mark is inline SVG because the site ships no external assets.
    """
    if not ORCID_ID:
        return ""
    return (
        f'<a class="orcid" rel="me noopener" target="_blank" href="{e(ORCID_URL)}"'
        f' aria-label="ORCID iD {e(ORCID_ID)}, opens orcid.org in a new tab">'
        '<svg class="orcid-glyph" viewBox="0 0 256 256" aria-hidden="true" focusable="false">'
        '<circle cx="128" cy="128" r="128" fill="#A6CE39"/>'
        '<path fill="#fff" d="M86.3 186.2H70.9V79.1h15.4v107.1z"/>'
        '<path fill="#fff" d="M108.9 79.1h41.6c39.6 0 57 28.3 57 53.6 0 27.5-21.5 53.6-56.8 53.6'
        'h-41.8V79.1zm15.4 93.3h24.5c34.9 0 42.9-26.5 42.9-39.7 0-21.5-13.7-39.7-43.7-39.7h-23.7'
        'v79.4z"/>'
        '<circle cx="78.6" cy="56.8" r="10.1" fill="#fff"/>'
        '</svg>'
        f'<span class="orcid-num">{e(ORCID_ID)}</span></a>'
    )


def orcid_foot():
    """ORCID in the footer profile list, first because it is the canonical scholarly id."""
    if not ORCID_URL:
        return ""
    return f'<li><a rel="me" href="{e(ORCID_URL)}">ORCID</a></li>'


def shell(path, title, description, body, extra_ld=None, og_type="website", crumb=None,
          flat_crumbs=False, extra_head=""):
    description = clamp(description)
    """path: '' for root, else 'research' or 'publications/m2h' with no slashes at the edges."""
    canonical = f"{ORIGIN}/" if path == "" else f"{ORIGIN}/{path}/"
    depth_prefix = "/"  # absolute paths throughout, the site sits at a domain root
    current = ' aria-current="page"'
    nav_bits = []
    for n in SITE["nav"]:
        nav_path = n["href"].strip("/")
        mark = current if path == nav_path or path.startswith(nav_path + "/") else ""
        nav_bits.append(f'<a href="{e(n["href"])}"{mark}>{e(n["label"])}</a>')
    nav = "".join(nav_bits)
    def ver_value(v):
        """Accept the bare token or a whole pasted meta tag, never emit nested markup."""
        if not v:
            return None
        m = re.search(r'content=["\']([^"\']+)["\']', str(v))
        token = m.group(1) if m else str(v)
        return token.strip().strip("<>/ ") or None

    ver = SITE.get("verification", {})
    vtags = ""
    g = ver_value(ver.get("googleSearchConsole"))
    if g:
        vtags += f'\n<meta name="google-site-verification" content="{e(g)}">'
    b = ver_value(ver.get("bingWebmaster"))
    if b:
        vtags += f'\n<meta name="msvalidate.01" content="{e(b)}">'

    nodes = list(extra_ld or [])
    have = {n.get("@id") for n in nodes}
    for key in videos_in(body):
        n = video_ld(key, canonical)
        if n and n["@id"] not in have:
            nodes.append(n)
            have.add(n["@id"])
    bc = breadcrumbs(path, crumb or title.split(" | ")[0], flat=flat_crumbs)
    if bc:
        nodes.append(bc)
    ld = "\n".join(jsonld(o) for o in nodes)
    og = ORIGIN + og_for(path)
    section = path.split("/", 1)[0] if path else "home"
    page_class = "page page-" + re.sub(r"[^a-z0-9-]", "-", section.lower())

    out = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<link rel="canonical" href="{e(canonical)}">{vtags}
<meta property="og:type" content="{e(og_type)}">
<meta property="og:site_name" content="{e(NAME)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(og)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{e(og)}">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<link rel="stylesheet" href="{depth_prefix}assets/site.css?v={asset_hash("/assets/site.css")}">{extra_head}
<link rel="stylesheet" href="/assets/fieldbook.css?v={asset_hash("/assets/fieldbook.css")}">
<link rel="icon" href="{depth_prefix}assets/favicon.svg?v={asset_hash('/assets/favicon.svg')}" type="image/svg+xml">
<link rel="icon" href="{depth_prefix}assets/favicon-32.png?v={asset_hash('/assets/favicon-32.png')}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{depth_prefix}assets/favicon-180.png?v={asset_hash('/assets/favicon-180.png')}">
<script>try{{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}}catch(e){{}}</script>
{ld}
</head>
<body class="{page_class}">
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="scroll-progress" data-progress aria-hidden="true"></div>
  <div class="wrap masthead-inner">
    <div class="masthead-id">
      <a class="wordmark" href="/" aria-label="{e(NAME)}, home">
        <span class="wordmark-mark" aria-hidden="true">BU</span>
        <span class="wordmark-name">{e(NAME)}</span>
      </a>
      {orcid_mark()}
    </div>
    <nav class="nav" aria-label="Primary">{nav}</nav>
    <button class="theme-toggle" type="button" data-theme-toggle hidden>
      <span class="theme-toggle-dot" aria-hidden="true"></span>
      <span data-theme-label>Theme</span>
    </button>
  </div>
</header>
<main id="main" class="site-main">
<div class="wrap page-content">
{body}
</div>
</main>
<footer class="foot">
  <div class="wrap foot-inner">
    <div class="foot-signoff">
      <span class="wordmark-mark" aria-hidden="true">BU</span>
      <p><strong>{e(NAME)}</strong><br>{e(SITE['identity']['field'])}.</p>
    </div>
    <div>
      <ul>
        {orcid_foot()}
        <li><a rel="me" href="{e(SITE['links']['googleScholar'])}">Google Scholar</a></li>
        <li><a rel="me" href="{e(SITE['links']['github'])}">GitHub</a></li>
        <li><a rel="me" href="{e(SITE['links']['linkedin'])}">LinkedIn</a></li>
        <li><a rel="me" href="{e(SITE['links']['utStaffPage'])}">University of Twente</a></li>
        <li><a href="/publications/bibtex/">BibTeX</a></li>
      </ul>
      <p>{e(SITE['identity']['affiliation']['shortName'])}, Enschede.</p>
    </div>
  </div>
</footer>
<script src="{depth_prefix}assets/media.js?v={asset_hash("/assets/media.js")}" defer></script>
</body>
</html>
"""
    target = ROOT / (path + "/index.html" if path else "index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out)
    PAGES.append(path)
    return target


# Small conceptual graphics use HTML labels so they reflow and remain accessible.
ENGINEERING_ICONS = {
    'sense': '<rect x="10" y="17" width="48" height="32" rx="3"/><circle cx="34" cy="33" r="10"/><path d="M58 25 81 15v36L58 41M20 11h15M76 5h12v12M8 54v5h12"/>',
    'perceive': '<path d="m12 40 20-25 21 9 27-12M12 40l28 12 13-28M40 52l40-13V12M12 40l68-1"/><circle cx="32" cy="15" r="4"/><circle cx="53" cy="24" r="4"/><circle cx="40" cy="52" r="4"/>',
    'map': '<path d="m12 44 21-12 23 12 25-17M12 44v10l21-12 23 12 25-17V27M33 32V15l23-9 25 11v10M56 6v38"/><circle cx="12" cy="44" r="3"/><circle cx="81" cy="27" r="3"/>',
    'navigate': '<path d="M12 49h20V32h24V12h23M12 49V12h20M45 49h34V32M70 5l9 7-9 7"/><circle cx="12" cy="49" r="4"/><path d="M20 57h60" stroke-dasharray="2 5"/>',
    'compute': '<rect x="26" y="14" width="40" height="36" rx="3"/><path d="M36 24h20v16H36zM18 22h8M18 32h8M18 42h8M66 22h8M66 32h8M66 42h8M36 6v8M46 6v8M56 6v8M36 50v8M46 50v8M56 50v8"/>',
    'graph': '<path d="M46 13v10M19 34v-11h54v11M19 42v8H9v5M19 50h12v5M73 42v8H62v5M73 50h12v5"/><circle cx="46" cy="9" r="4"/><circle cx="19" cy="38" r="4"/><circle cx="73" cy="38" r="4"/>'
}


def engineering_icon(kind, cls='diagram-icon'):
    return (f'<svg class="{e(cls)}" viewBox="0 0 92 64" aria-hidden="true" focusable="false">'
            f'{ENGINEERING_ICONS[kind]}</svg>')


def system_diagram(key):
    d = GRAPHICS[key]
    steps = ''
    for n, step in enumerate(d['steps'], 1):
        label = f'<strong>{e(step["title"])}</strong><span>{e(step["text"])}</span>'
        if step.get('href'):
            label = f'<a href="{e(step["href"])}">{label}</a>'
        steps += (f'<li><span class="diagram-number">0{n}</span>'
                  f'{engineering_icon(step["icon"])}<div>{label}</div></li>')
    feedback = (f'<p class="diagram-feedback"><span aria-hidden="true">↶</span> '
                f'{e(d["feedback"])}</p>' if d.get('feedback') else '')
    return (f'<figure class="system-diagram" aria-label="{e(d["title"])}">'
            f'<div class="diagram-heading"><span class="eyebrow">System sketch</span>'
            f'<p>{e(d["title"])}</p></div><ol>{steps}</ol>{feedback}'
            f'<figcaption>{e(d["note"])}</figcaption></figure>')


def explainer_figure(key):
    rec = MEDIA['images'][key]
    full = rec['sources']['webp'][-1]['path']
    return (f'<figure class="explainer-figure"><a href="{e(full)}" '
            f'aria-label="Open full-size illustration: {e(rec["alt"])}">'
            f'{picture(key, caption=False, sizes="(min-width: 58em) 76rem, 94vw")}</a>'
            f'<figcaption>{e(rec["caption"])} <a href="{e(full)}">Open full-size ↗</a></figcaption></figure>')


def pipeline_story():
    parts = ''
    for i, item in enumerate(GRAPHICS['pipelineStory'], 1):
        parts += (f'<section class="pipeline-step" id="{e(item["id"])}">'
                  f'<div class="pipeline-step-copy"><p class="eyebrow">0{i} / Inside Mono-Hydra++</p>'
                  f'<h3>{e(item["title"])}</h3><p>{e(item["text"])}</p>'
                  f'<p class="pipeline-purpose">{e(item["purpose"])}</p></div>'
                  f'{explainer_figure(item["key"])}</section>')
    return (f'<section class="pipeline-story" id="pipeline"><p class="eyebrow">Architecture / Mono-Hydra++</p>'
            f'<h2>Trace a camera frame through the mapping stack.</h2>'
            f'<p class="lede">RGB and IMU measurements become depth, semantic labels, motion estimates, '
            f'refined poses and a hierarchical map.</p>{explainer_figure("pipeline-overview")}'
            f'<nav class="pipeline-nav" aria-label="Pipeline explanation">'
            f'<a href="#temporal-alignment">01 / Temporal alignment</a>'
            f'<a href="#depth-selection">02 / Depth-factor selection</a>'
            f'<a href="#depth-geometry">03 / Factor geometry</a></nav>{parts}</section>')


def onboard_configuration():
    d = GRAPHICS['onboardConfiguration']
    cards = ''.join(
        f'<article class="config-card"><p class="eyebrow">{e(c["label"])}</p>'
        f'{engineering_icon(c["icon"])}<h3>{e(c["title"])}</h3>'
        f'<p>{e(c["text"])}</p><p class="config-output">{e(c["output"])}</p></article>'
        for c in d['steps'])
    return (f'<section class="onboard-config" id="configuration" aria-labelledby="config-title">'
            f'<p class="eyebrow">Hardware × software integration</p><h2 id="config-title">{e(d["title"])}</h2>'
            f'<p class="lede">{e(d["intro"])}</p>'
            f'<div class="config-hardware"><div>{picture("drone-top")}</div>'
            f'<div><p class="eyebrow">Built and flight-tested</p><h3>Carry the mapping stack into the air.</h3>'
            f'<p>I built the custom drone and integrated perception, odometry and scene graph construction on its Jetson. '
            f'The carbon frame, propeller cage, battery placement and onboard compute are visible in the hardware photographs.</p>'
            f'<dl class="config-specs"><div><dt>Sensing</dt><dd>One RGB camera + IMU</dd></div>'
            f'<div><dt>Compute</dt><dd>Jetson Orin NX</dd></div>'
            f'<div><dt>Inference</dt><dd>ONNX → TensorRT FP16</dd></div>'
            f'<div><dt>Mapping</dt><dd>RVIO2 + local refinement + Hydra</dd></div></dl></div></div>'
            f'<div class="config-grid">{cards}</div>'
            f'<div class="config-demos"><div><h3>Watch the platform fly.</h3>{video("drone-flight")}</div>'
            f'<div><h3>Inspect the onboard pose estimate.</h3>{video("stairs-zupt")}</div></div>'
            f'<p class="illustration-note">{e(d["note"])}</p></section>')


def hierarchy_story():
    levels = [('Building', 'The top-level environment.'), ('Rooms', 'Regions that organise the building.'),
              ('Places', 'Connected locations through the space.'), ('Objects', 'Semantic entities in the map.'),
              ('Mesh', 'Reconstructed geometry carrying semantic labels.')]
    labels = ''.join(f'<li><strong>{e(title)}</strong><span>{e(text)}</span></li>' for title, text in levels)
    return (f'<section class="hierarchy-story"><div class="hierarchy-art">'
            f'{picture("scenegraph-explained", caption=False, sizes="(min-width: 58em) 32rem, 90vw")}'
            f'</div><div><p class="eyebrow">Read the map at five levels</p>'
            f'<h2>Turn geometry into a map a robot can reason about.</h2>'
            f'<p>A scene graph connects geometric detail to objects and larger spaces. '
            f'The illustration shows the hierarchy; the experimental reconstructions appear below.</p>'
            f'<ol>{labels}</ol><p class="illustration-note">Conceptual thesis illustration, not an experimental reconstruction.</p>'
            f'<a href="/projects/mono-hydra-plus/#pipeline">Follow the mapping pipeline ↗</a></div></section>')


def experience_graphic():
    """Visual links back to the three engineering experiences, without new claims."""
    rows = ''
    for c in SITE['home']['portfolio']['cases']:
        rec = MEDIA['videos'][c['clip']]
        rows += (f'<li><a href="/#{e(c["id"])}"><img src="{e(rec["poster"])}" '
                 f'width="{rec["width"]}" height="{rec["height"]}" alt="" loading="lazy">'
                 f'<span><span class="eyebrow">{e(c["index"])} / {e(c["type"])}</span>'
                 f'<strong>{e(c["title"])}</strong></span><span aria-hidden="true">↗</span></a></li>')
    return f'<nav class="experience-graphic" aria-label="Engineering experience in three projects"><ul>{rows}</ul></nav>'


# ---------------------------------------------------------------- home

def arc_stage():
    """The signature sequence: one system, five representations, scroll-linked.

    The markup is the fallback. Without JavaScript, below 58em, or under reduced motion it
    is a plain numbered sequence of frame + explanation, which is already the argument.
    stage.js adds `is-live` and the frames become one sticky stage the notes drive."""
    S = SITE["home"].get("arcStage")
    if not S:
        return ""
    frames, notes = "", ""
    for i, st in enumerate(S["steps"]):
        if st["media"] == "pair":
            panes = ""
            for pane in st["panes"]:
                rec = MEDIA["frames"].get(pane["key"]) or MEDIA["images"].get(pane["key"])
                if not rec:
                    continue
                img = picture(pane["key"], caption=False, lazy=i > 0,
                              sizes="(min-width: 58em) 30vw, 92vw")
                # growing each pane in proportion to its own aspect ratio is what makes the
                # two frames the same height without cropping either one to fit the other
                ar = rec["width"] / rec["height"]
                panes += (f'<div class="pxm-pane" style="--ar: {ar:.4f}">{img}'
                          f'<span class="pxm-pane-label">{e(pane["label"])}</span></div>')
            if not panes:
                continue
            frames += (f'<figure class="pxm-frame" data-step="{i}">'
                       f'<div class="pxm-frame-media pxm-pair">{panes}</div>'
                       f'<figcaption class="spec">{e(st["spec"])}</figcaption></figure>')
            notes += (f'<li class="pxm-note" data-step="{i}">'
                      f'<p class="pxm-index">{e(st["index"])}</p>'
                      f'<h3>{e(st["title"])}</h3>'
                      f'<p>{e(st["text"])}</p></li>')
            continue

        key = st["key"]
        if st["media"] == "video":
            rec = MEDIA["videos"].get(key)
            if not rec:
                continue
            inner = (f'<video poster="{rec["poster"]}" width="{rec["width"]}" '
                     f'height="{rec["height"]}" muted loop playsinline preload="none" '
                     f'data-step-video aria-label="{e(rec["alt"])}">'
                     f'<source src="{rec["mp4"]}" type="video/mp4"></video>')
        else:
            inner = picture(key, caption=False, lazy=i > 0,
                            sizes="(min-width: 58em) 58vw, 92vw")
        if not inner:
            continue
        frames += (f'<figure class="pxm-frame" data-step="{i}">'
                   f'<div class="pxm-frame-media">{inner}</div>'
                   f'<figcaption class="spec">{e(st["spec"])}</figcaption></figure>')
        notes += (f'<li class="pxm-note" data-step="{i}">'
                  f'<p class="pxm-index">{e(st["index"])}</p>'
                  f'<h3>{e(st["title"])}</h3>'
                  f'<p>{e(st["text"])}</p></li>')
    ticks = "".join(f'<span class="pxm-tick" data-tick="{i}"></span>'
                    for i in range(len(S["steps"])))
    return f"""
<section class="pxm bleed ground-dark" id="arc" data-pxm aria-labelledby="pxm-title">
  <div class="pxm-head bleed-wide">
    <p class="spec">{e(S['eyebrow'])}</p>
    <h2 id="pxm-title">{e(S['heading'])}</h2>
    <p class="pxm-lede">{e(S['lede'])}</p>
  </div>
  <div class="pxm-body bleed-wide">
    <div class="pxm-frames">{frames}<div class="pxm-ticks" aria-hidden="true">{ticks}</div></div>
    <ol class="pxm-notes">{notes}</ol>
  </div>
  <p class="pxm-foot bleed-wide spec-lg">{e(S['foot'])}</p>
</section>"""


def build_home():
    P = SITE['home']['portfolio']
    hero_video = MEDIA['videos']['itc-loop']
    def tile_video(key, caption, start=0):
        rec = MEDIA['videos'][key]
        playback = f'data-start="{start}"' if start else 'loop'
        src = rec['mp4'] + (f'#t={start}' if start else '')
        return (f'<figure class="tile-player"><div class="tile-player-frame">'
                f'<video controls muted {playback} playsinline preload="none" data-autoloop '
                f'poster="{e(rec["poster"])}" width="{rec["width"]}" height="{rec["height"]}" '
                f'aria-label="{e(rec["alt"])}"><source src="{e(src)}" type="video/mp4"></video>'
                f'<button class="v-toggle" type="button" data-toggle '
                f'aria-label="Play or pause {e(caption)}">Play</button></div>'
                f'<figcaption>{e(caption)}</figcaption></figure>')

    cases = ''
    for c in P['cases']:
        tags = ''.join(f'<li>{e(t)}</li>' for t in c['skills'][:3])
        if c['id'] == 'origin':
            preview = ('<div class="tile-clipbar"><span>SLAM &amp; control · from 0:59</span></div>'
                       + tile_video(c['clip'], 'My SLAM and control explanation · starts at 0:59', start=59))
        else:
            preview = ('<div class="tile-clipbar"><span>Commercial deployment</span></div>'
                       + tile_video(c['clip'], c['caption']))
        if c['id'] == 'onboard':
            preview = switcher('doctoral-clips', [
                ('3D mapping', tile_video('icra26', 'Monocular 3D scene graph · ScanNet scene 0000')),
                ('Exploration', tile_video('scope-explorer', 'ATLAS autonomous exploration · simulation')),
            ], label='Doctoral research demos')
        cases += f'''
<article class="work-tile work-tile-{e(c['id'])}" id="{e(c['id'])}" aria-labelledby="tile-{e(c['id'])}">
  <div class="tile-card-body">
    <div class="tile-video-area"><p class="tile-video-category">{e(c['type'])}</p>{preview}</div>
    <div class="tile-copy">
      <p class="tile-location">{e(c['place'])}</p>
      <h3 id="tile-{e(c['id'])}"><a href="{e(c['href'])}">{e(c['tileTitle'])}</a></h3>
      <p class="tile-description">{e(c['tileText'])}</p>
      <div class="tile-outcome"><strong>{e(c['tileMetric'])}</strong><span>{e(c['tileMetricLabel'])}</span></div>
      <ul class="tile-tags" aria-label="Skills demonstrated">{tags}</ul>
      <a class="tile-cta" href="{e(c['href'])}">{e(c['tileLink'])}<span aria-hidden="true">↗</span></a>
    </div>
  </div>
</article>'''
    loop = P['expertiseLoop']
    loop_nodes = ''.join(
        f'<li><a href="{e(step["href"])}"><span class="loop-number">{e(step["number"])}</span>'
        f'<strong>{e(step["title"])}</strong><span class="loop-description">{e(step["detail"])}</span></a></li>'
        for step in loop['steps'])
    def dive_image(d):
        if d.get('media') == 'video-poster':
            rec = MEDIA['videos'][d['key']]
            return (f'<img src="{e(rec["poster"])}" width="{rec["width"]}" height="{rec["height"]}" '
                    f'alt="{e(rec["alt"])}" loading="lazy" decoding="async">')
        return picture(d['key'], caption=False, sizes='(min-width: 58em) 36rem, 92vw')

    dives = ''.join(
        f'<article class="deep-tile"><a href="{e(d["href"])}">'
        f'<div class="deep-image">{dive_image(d)}</div>'
        f'<div class="deep-copy"><p class="tile-eyebrow">{e(d["label"])}</p>'
        f'<h3>{e(d["title"])}</h3><p>{e(d["text"])}</p>'
        f'<span class="tile-cta">{e(d["link"])}<span aria-hidden="true">↗</span></span></div></a></article>'
        for d in P['deepDives'])
    body = f'''
<header class="tile-hero">
  <div class="intro-tile">
    <p class="tile-eyebrow">{e(P['eyebrow'])}</p>
    <h1>{e(P['headline'])}<br><em>{e(P['headlineAccent'])}</em></h1>
    <p class="intro-summary">{e(P['intro'])}</p>
    <div class="tile-actions"><a class="tile-button" href="#work">Explore my projects <span aria-hidden="true">↓</span></a>
      <a class="intro-cv" href="/cv/">View CV ↗</a></div>
    <p class="intro-availability"><span aria-hidden="true"></span>{e(SITE['contact']['availability'])}</p>
  </div>
  <figure class="hardware-tile hero-video-tile">
    <div class="hardware-label"><span>ITC second floor</span><span>Mapping demo · 10× speed</span></div>
    <div class="hero-video-media">
      <video controls muted loop playsinline preload="metadata" data-autoloop
        poster="{e(hero_video['poster'])}" width="{hero_video['width']}" height="{hero_video['height']}"
        aria-label="{e(hero_video['alt'])}">
        <source src="{e(hero_video['mp4'])}" type="video/mp4">
      </video>
      <button class="v-toggle" type="button" data-toggle aria-label="Play or pause the ITC mapping video">Play</button>
    </div>
    <figcaption><div><strong>Build a 3D scene graph from one camera.</strong><span>ITC corridor loop · Scene graph construction shown at 10× real time</span></div>
      <a href="{watch_url('itc-loop')}" aria-label="Watch the full ITC mapping video">↗</a></figcaption>
  </figure>
</header>

<section class="tile-section" id="work" aria-labelledby="work-title">
  <div class="tile-section-head"><div><p class="tile-eyebrow">Selected engineering work</p>
    <h2 id="work-title">Mapping, exploration and field deployment.</h2></div>
    <a class="section-link" href="/projects/">All projects ↗</a></div>
  <div class="work-grid">{cases}</div>
</section>

<section class="tile-section" id="flight" aria-labelledby="flight-title">
  <div class="tile-section-head"><div><p class="tile-eyebrow">Designed, integrated, flight-tested</p>
    <h2 id="flight-title">Build it. Fly it. Map with it.</h2>
    <p class="expertise-intro">A custom airframe. Its own onboard computer. A mapping stack I took from models to a flying robot.</p></div>
    <a class="section-link" href="/projects/mono-hydra-plus/#configuration">Explore the onboard setup ↗</a></div>
  <div class="flight-grid">
    <article class="flight-hardware">
      <div class="flight-photo">{picture('drone-angle', caption=False, sizes='(min-width: 52em) 45vw, 92vw')}<span class="flight-badge">01 / The robot I built</span></div>
      <div class="flight-copy"><h3>Fit the software to the aircraft.</h3><p>Camera and IMU sensing, Jetson compute, and a protected carbon frame: the hardware behind my onboard mapping research.</p>
        <ul class="flight-chips"><li>RGB + IMU</li><li>Jetson Orin NX</li><li>TensorRT FP16</li></ul></div>
    </article>
    <article class="flight-demo"><div class="flight-demo-head"><p class="tile-eyebrow">02 / Flight test</p><h3>Watch it leave the lab bench.</h3></div>
      {tile_video('drone-flight', 'Real flight footage · take-off and an indoor corridor pass')}
      <p class="flight-demo-note">The robot carries its mapping compute onboard. See the separate ITC recording above for the scene graph output.</p>
    </article>
  </div>
  <a class="flight-route" href="/projects/mono-hydra-plus/#configuration"><span>03 / Inside the onboard stack</span><strong>Camera + IMU → learned perception → refined poses → 3D scene graph</strong><span aria-hidden="true">↗</span></a>
</section>

<section class="tile-section expertise-section" id="skills" aria-labelledby="skills-title">
  <div class="tile-section-head"><div><p class="tile-eyebrow">Research &amp; engineering</p>
    <h2 id="skills-title">{e(loop['title'])}</h2>
    <p class="expertise-intro">{e(loop['intro'])}</p></div></div>
  <figure class="expertise-loop" aria-label="Perception, mapping and autonomous exploration feedback loop">
    <ol class="loop-nodes">{loop_nodes}</ol>
    <div class="loop-return"><span>{e(loop['feedback'])}</span></div>
    <div class="loop-deployment">
      <div><span class="loop-number">04 / Engineering delivery</span><strong>{e(loop['deploymentTitle'])}</strong></div>
      <div class="loop-delivery-links"><a href="/projects/mono-hydra-plus/">{e(loop['onboard'])} ↗</a>
        <a href="/projects/#commercial">{e(loop['commercial'])} ↗</a></div>
    </div>
    <figcaption>{e(loop['note'])}</figcaption>
  </figure>
</section>

<section class="tile-section" id="research" aria-labelledby="research-title">
  <div class="tile-section-head"><div><p class="tile-eyebrow">Explore the technical details</p>
    <h2 id="research-title">Inside the mapping and exploration stack.</h2></div>
    <a class="section-link" href="/publications/">Papers &amp; results ↗</a></div>
  <div class="deep-grid">{dives}</div>
</section>

<div class="closing-grid">
  <section class="profile-tile" aria-labelledby="profile-title">
    <div class="profile-photo">{picture('portrait', caption=False, sizes='100px')}</div>
    <div><p class="tile-eyebrow">Engineering &amp; leadership</p>
      <h2 id="profile-title">Lead deployments. Teach robotics.</h2>
      <p>I led a three-engineer team in industry, designed robotics labs at Twente, and supervised three master’s thesis students.</p>
      <a class="section-link" href="/cv/">Experience &amp; education ↗</a></div>
  </section>
  <section class="contact-tile" aria-labelledby="contact-title">
    <p class="tile-eyebrow">Based in the Netherlands</p>
    <h2 id="contact-title">Build perception and navigation for real robots.</h2>
    <a class="tile-button" href="/contact/">Discuss a robotics role <span aria-hidden="true">↗</span></a>
  </section>
</div>
'''
    shell('', f'{NAME} | Robotics and computer vision engineer',
          'Robotics engineer working across computer vision, SLAM and embedded systems. '
          'Monocular 3D mapping, Jetson deployment and real-world service robotics.',
          body, extra_ld=[person_node(), profile_page_node()], og_type='profile',
          extra_head=f'\n<link rel="stylesheet" href="/assets/portfolio.css?v={asset_hash("/assets/portfolio.css")}">')

# ---------------------------------------------------------------- research

def applied_press():
    """The press the Dubai deployments were covered in, listed once from the CV role."""
    role = next((r for r in CV["experience"] if r.get("press")), None)
    if not role:
        return ""
    rows = "".join(f'<li><a href="{e(x["href"])}">{e(x["title"])}</a>'
                   f' <span class="pub-venue">{e(x["outlet"])}, {e(x["date"])}</span></li>'
                   for x in role["press"])
    return (f'<p class="media-label">{e(role.get("pressLabel", "In the press"))}</p>'
            f'<ul class="limits role-press">{rows}</ul>')


def thenow_pair():
    """The 2017 question beside the 2026 one."""
    TN = SITE["home"]["thenNow"]
    PERA = PUBS["earlierWork"]["entries"][0]
    return f"""
<div class="thenow">
  <article class="thenow-card">
    <p class="thenow-when">{e(TN['thenTitle'])}</p>
    <h4>Autonomous exploration planning for a reconnaissance agent</h4>
    <p>{e(TN['thenText'])}</p>
    {video("peradeniya-2017", cls="thenow-figure")}
    <p class="thenow-links"><a href="{e(PERA['links']['doi'])}">{e(TN['thenLinkLabel'])}</a></p>
  </article>
  <article class="thenow-card thenow-now">
    <p class="thenow-when">{e(TN['nowTitle'])}</p>
    <h4>Monocular 3D scene graphs, built in real time</h4>
    <p>{e(TN['nowText'])}</p>
    {picture("scene-graph-itc", cls="thenow-figure", sizes="(min-width: 56em) 28rem, 92vw",
             caption=False)}
    <p class="thenow-links"><a href="/publications/mono-hydra-plus/">{e(TN['nowLinkLabel'])}</a></p>
  </article>
</div>
"""


def build_research():
    arc = SITE["arc"]
    prog = SITE["headlineProgression"]
    rows = "".join(f"""
        <tr{' class="embedded"' if "embedded" in r["system"].lower() else ""}>
          <td>{e(r["system"])}</td><td>{e(r["year"])}</td><td>{e(r["error"])}</td>
          <td>{e(r["resolution"])}</td><td>{e(r["hardware"])}</td>
        </tr>""" for r in prog["rows"])
    a2 = arc["actTwo"]
    proj2 = next(p for p in PROJECTS["projects"] if p["slug"] == "learned-exploration")
    points = "".join(f"<li>{e(x)}</li>" for x in proj2["designPoints"])

    body = f"""
<header class="folio-heading"><p class="eyebrow">Research / University of Twente</p>
<h1>Research.<br><em>From sensing to autonomy.</em></h1>
<p class="standfirst">{e(arc['statement'])}</p></header>
{system_diagram('research')}
{hierarchy_story()}

<h2 class="prologue-heading">Prologue. The same question, ten years earlier</h2>
<p>{e(arc['prologue'])}</p>
{thenow_pair()}

<h2>{e(arc['actOne']['label'])}. {e(arc['actOne']['title'])}</h2>
<p>{e(arc['actOne']['line'])}</p>
{picture("perception-pipeline")}

<h3>One building, four generations</h3>
<p>{e(prog['caption'])}</p>
<div class="table-scroll">
  <table>
    <caption class="sr-only">Mapping error by system generation</caption>
    <thead><tr><th>System</th><th>Year</th><th>Mean error</th><th>Input</th><th>Hardware</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<p>Metric-semantic mapping systems that produce usable scene graphs have almost always assumed
RGB-D or LiDAR input, because reliable geometry is the hard part and a depth sensor supplies it
directly. That assumption rules out the platforms where the mapping is most useful, since payload
and power are exactly what limit a small drone. Removing the depth sensor was the question, and
four papers answer it in sequence.</p>

<h3>Mono-Hydra, 2023. Proving it is possible</h3>
<p>Learned depth and learned semantics, running as two separate networks, feed a robocentric
square-root visual-inertial odometry front end, and the resulting semantic mesh drives the layered
scene graph. Measured against a LiDAR backpack point cloud of the ITC building it reached 0.19 m
and 0.21 m mean error on two floors, at 15 fps.
<a href="/publications/mono-hydra/">Read more</a>.</p>

<h3>M2H, 2025. One model instead of two</h3>
<p>Two independent networks duplicate compute and produce two representations that do not agree
with each other. M2H collapses them into a single multi-task model in which depth, semantics,
surface normals, and edges exchange information through window-based cross-task attention. The
benchmark numbers improved, and so did the map: 0.11 m on the same building, at twice the frame
rate. <a href="/publications/m2h/">Read more</a>.</p>

<h3>M2H-MX, 2026. Testing whether the map actually cares</h3>
<p>A better benchmark score is not the same thing as a better map, and dense prediction papers
usually stop before finding out. M2H-MX is evaluated twice, once as a predictor and once as the
front end inside an otherwise unchanged SLAM pipeline. Average trajectory error on selected
ScanNet sequences fell from 17.59 cm to 6.91 cm, which puts a monocular system close to the RGB-D
baselines in the same table. The ablation attributes most of the gain to the backbone features
rather than to the new decoder blocks.
<a href="/publications/m2h-mx/">Read more</a>.</p>

<h3>Mono-Hydra++, under review. Closing the loop backwards</h3>
<p>Everything so far runs perception forwards into mapping. Mono-Hydra++ sends it back the other
way as well: predicted sparse depth enters the estimator as metric anchor factors, semantic masks
keep dynamic regions out of it, and the poses that come back out temporally align the next dense
predictions. 0.08 m on the ITC second floor, 0.033 m calibrated trajectory error on 7-Scenes.
<a href="/publications/mono-hydra-plus/">Read more</a>.</p>

{picture("scene-graph-itc")}

<h2>{e(a2['label'])}. {e(a2['title'])} <span class="tag tag-progress">In progress</span></h2>
<p>{e(a2['line'])}</p>

<div class="note">
  <span class="note-label">Status</span>
  <p>{e(proj2['honesty'])}</p>
</div>

<p>{e(proj2['whatItDoes'])}</p>
<p class="lede">{e(a2['commitment'])}</p>
<p>The learned component sits between two deterministic layers and has no path to the actuators
except by selecting an option the planner above it has already certified as safe. It may re-order
those options and it may abstain. It may not invent one. The requirements that follow come from
the shape of the task rather than from the hardware:</p>
<ul class="limits">{points}</ul>
<p><a href="/projects/learned-exploration/">More on the exploration work</a>.</p>

<h2>Thesis</h2>
<p>The two parts above take their names from the thesis,
<em>Structuring the Seen, Exploring the Unseen</em>, which is expected to be completed in 2026 at the
Faculty ITC, University of Twente, supervised by
{e(" and ".join(SITE['identity']['supervisors']))}.</p>
"""
    shell("research", f"{NAME} | Research",
          "The two-part research arc: building hierarchical metric-semantic 3D scene graphs from a "
          "single camera, then learning to select among certified exploration routes.",
          body, extra_ld=[person_node()], og_type="article", crumb="Research")


# ---------------------------------------------------------------- publications

def pub_ld(p):
    node = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": p["title"],
        "name": p["title"],
        "author": [{"@type": "Person", "name": a,
                    **({"@id": f"{ORIGIN}/#person"} if a == PUBNAME else {})}
                   for a in p["authors"]],
        "datePublished": str(p["year"]),
        "url": f"{ORIGIN}/publications/{p['slug']}/",
        "isPartOf": {"@type": "Periodical", "name": p["venue"]},
        "publisher": {"@type": "Organization", "name": p["venue"]},
        "abstract": p["claim"],
        "creativeWorkStatus": p["statusLabel"],
    }
    ids = p.get("identifiers") or {}
    idents = []
    if ids.get("doi"):
        idents.append({"@type": "PropertyValue", "propertyID": "DOI", "value": ids["doi"]})
    if ids.get("arxiv"):
        idents.append({"@type": "PropertyValue", "propertyID": "arXiv", "value": ids["arxiv"]})
    if idents:
        node["identifier"] = idents
    return node


def linkrow(p):
    links, L = [], p["links"]
    if L.get("doi"):
        links.append(f'<a href="{e(L["doi"])}">DOI</a>')
    if L.get("arxiv"):
        links.append(f'<a href="{e(L["arxiv"])}">arXiv</a>')
    if L.get("code"):
        links.append(f'<a href="{e(L["code"])}">Code</a>')
    if L.get("video"):
        links.append(f'<a href="{e(L["video"])}">Video</a>')
    if L.get("linkedin"):
        links.append(f'<a href="{e(L["linkedin"])}">LinkedIn</a>')
    if L.get("bibtex"):
        links.append(f'<a href="{e(L["bibtex"])}">BibTeX</a>')
    return f'<div class="linkrow">{"".join(links)}</div>' if links else ""


def cite_links(x):
    L = x.get("links", {})
    bits = []
    for key, label in (("doi", "DOI"), ("arxiv", "arXiv"), ("code", "Code"),
                       ("video", "Video")):
        if L.get(key):
            bits.append(f'<a href="{e(L[key])}">{label}</a>')
    return f'<div class="linkrow">{"".join(bits)}</div>' if bits else ""


def cite_entry(x, extra_class=""):
    auth = f'<p class="pub-authors">{authors_html(x["authors"])}</p>' if x.get("authors") else ""
    when = f'{e(x["context"])}, {e(x["year"])}'
    if x.get("posted"):
        when = (f'{e(x["context"])}, written {e(x["written"])}, '
                f'posted {humandate(x["posted"])}')
    if x.get("grade"):
        when += f', {e(x["grade"])}'
    role = f'<p class="pub-venue">{e(x["role"])}</p>' if x.get("role") else ""
    awards = ('<p class="pub-venue">' + e("; ".join(x["awards"])) + "</p>") if x.get("awards") else ""
    summ = f'<p>{e(x["summary"])}</p>' if x.get("summary") else ""
    rel = f'<p>{e(x["relevance"])}</p>' if x.get("relevance") else ""
    note = f'<p class="pub-venue">{e(x["note"])}</p>' if x.get("note") else ""
    vattr = f'<p class="pub-venue">{e(x["videoAttribution"])}</p>' if x.get("videoAttribution") else ""
    status = ""
    if x.get("statusLabel"):
        status = f'<p class="pub-venue"><span class="tag">{e(x["statusLabel"])}</span></p>'
    return f"""
    <li class="pub {extra_class}">
      <h3>{e(x["title"])}</h3>
      {auth}
      <p class="pub-venue">{when}</p>
      {status}{role}{awards}{summ}{rel}{note}
      {cite_links(x)}
      {vattr}
    </li>"""


def build_publications_index():
    previews = {'mono-hydra-plus': 'scene-graph-itc', 'm2h-mx': 'm2h-mx-architecture',
                'mono-hydra': 'scenegraph-system-design'}
    items = "".join(f"""
    <li class="pub pub-illustrated">
      <a class="pub-preview" href="/publications/{e(p['slug'])}/" tabindex="-1" aria-hidden="true">
        {picture(previews[p['slug']], caption=False, sizes='(min-width: 58em) 15rem, 90vw') if p['slug'] != 'm2h' else '<img src="' + MEDIA['videos']['itc-loop']['poster'] + '" alt="" width="1280" height="570" loading="lazy">'}
      </a><div class="pub-copy"><p class="eyebrow">{e(p['year'])} / {e(p['statusLabel'])}</p>
      <h3><a href="/publications/{e(p["slug"])}/">{e(p["title"])}</a></h3>
      <p class="pub-authors">{authors_html(p["authors"])}</p>
      <p class="pub-venue">{e(p["venue"])}
        {'<span class="tag tag-review">Under review</span>' if p["status"] == "under review" else ""}</p>
      <p>{e(p["claim"])}</p>
      {linkrow(p)}</div>
    </li>""" for p in PUBS["publications"])

    pre = PUBS.get("preprints")
    prelist = ""
    if pre:
        for x in pre["entries"]:
            y = dict(x)
            y["context"] = x["venue"]
            prelist += cite_entry(y)

    ew = PUBS["earlierWork"]
    early = ""
    for x in ew["entries"]:
        early += cite_entry(x)

    preprint_block = ""
    if pre:
        preprint_block = (f'<h2>{e(pre["heading"])}</h2>'
                          f'<p class="section-intro">{e(pre["note"])}</p>'
                          f'<ul class="publist">{prelist}</ul>')

    body = f"""
<header class="folio-heading"><p class="eyebrow">Papers &amp; technical evidence</p>
<h1>Publications.<br><em>Perception, SLAM &amp; exploration.</em></h1>
<p class="standfirst">Papers are indexed under {e(PUBNAME)}, and the earlier ones under
B. Udugama.</p></header>

<h2>Research papers</h2>
<ul class="publist">{items}</ul>

{preprint_block}

<h2>{e(ew["heading"])}</h2>
<p class="section-intro">{e(ew["note"])}</p>
<ul class="publist">{early}</ul>

<p style="margin-top:2rem"><a href="/publications/bibtex/">All BibTeX entries</a> &middot;
<a href="{e(SITE['links']['googleScholar'])}">Google Scholar</a> for citation counts.</p>
"""
    shell("publications", f"{NAME} | Publications",
          "Peer-reviewed publications on monocular 3D scene graphs, multi-task dense prediction, "
          "and real-time metric-semantic mapping, by Bavantha Udugama (U.V.B.L. Udugama).",
          body, extra_ld=[person_node()], crumb="Publications")


def build_publication_pages():
    for p in PUBS["publications"]:
        results = "".join(f"""
      <li class="result">
        <span class="value">{e(h["value"])}</span>
        <span class="what">{e(h["what"])}</span>
        <span class="conditions">{e(h["conditions"])}</span>
      </li>""" for h in p["headline"])

        limits = "".join(f"<li>{e(x)}</li>" for x in p["limitations"])

        alt = ""
        if p.get("alternateTitle"):
            alt = (f'<p class="pub-venue">Also circulated as: {e(p["alternateTitle"])}</p>')

        review_note = ""
        if p["status"] == "under review":
            review_note = f"""
<div class="note">
  <span class="note-label">Status</span>
  <p>{e(p["statusLabel"])}. Manuscript number {e(p.get("manuscriptNumber", "not assigned"))}.</p>
</div>"""

        body = f"""
<header class="publication-head"><p class="eyebrow"><a href="/publications/">Publications</a> / {e(p['year'])}</p>
<h1>{e(p["title"])}</h1>
{alt}
<p class="pub-authors">{authors_html(p["authors"])}</p>
<p class="pub-venue">{e(p["venue"])}{"" if str(p["year"]) in p["venue"] else ", " + str(p["year"])}</p>
{linkrow(p)}
{review_note}</header>

<p class="lede" style="margin-top:2rem">{e(p["claim"])}</p>

<h2>Context</h2>
<p>{e(p["context"])}</p>

<h2>Contribution</h2>
<p>{e(p["contribution"])}</p>
{PUB_FIGURE.get(p["slug"], "")}

<h2>Results</h2>
<ul class="results">{results}</ul>
<p class="pub-venue">Datasets: {e(", ".join(p["datasets"]))}. Hardware: {e(p["hardware"])}</p>

<h2>Limitations</h2>
<ul class="limits">{limits}</ul>

<h2>Links</h2>
{linkrow(p)}
"""
        shell(f"publications/{p['slug']}",
              f"{p['title']} | {NAME}",
              f"{p['claim']} {p['statusLabel']}. By {', '.join(p['authors'])}.",
              body, extra_ld=[pub_ld(p)], og_type="article", crumb=p["title"])


BIBTEX = {
    "mono-hydra": """@article{udugama2023monohydra,
  title   = {Mono-Hydra: Real-Time 3D Scene Graph Construction from Monocular Camera Input with IMU},
  author  = {Udugama, U. V. B. L. and Vosselman, G. and Nex, F.},
  journal = {ISPRS Annals of the Photogrammetry, Remote Sensing and Spatial Information Sciences},
  volume  = {1},
  pages   = {439--445},
  year    = {2023}
}""",
    "m2h": """@inproceedings{udugama2025m2h,
  title     = {M2H: Multi-Task Learning with Efficient Window-Based Cross-Task Attention for Monocular Spatial Perception},
  author    = {Udugama, U. V. B. L. and Vosselman, George and Nex, Francesco},
  booktitle = {IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)},
  year      = {2025},
  note      = {arXiv:2510.17363}
}""",
    "m2h-mx": """@inproceedings{udugama2026m2hmx,
  title     = {M2H-MX: Multi-Task Semantic and Geometric Perception for Real-Time Monocular 3D Scene Graph Construction},
  author    = {Udugama, U. V. B. L. and Vosselman, George and Nex, Francesco},
  booktitle = {IEEE International Conference on Robotics and Automation (ICRA), SRRA Workshop},
  year      = {2026},
  doi       = {10.48550/arXiv.2603.29236}
}""",
    "mono-hydra-plus": """@unpublished{udugama2026monohydrapp,
  title        = {Mono-Hydra++: Real-Time Monocular Scene Graph Construction with Multi-Task Learning for 3D Indoor Mapping},
  author       = {Udugama, U. V. B. L. and Vosselman, George and Nex, Francesco},
  note         = {Under review, ISPRS Journal of Photogrammetry and Remote Sensing, manuscript PHOTO-S-26-02536},
  eprint       = {2605.17661},
  archivePrefix= {arXiv},
  year         = {2026}
}""",
}

OTHER_BIBTEX = [
    ("evolution-of-slam", "Evolution of SLAM: Toward the Robust-Perception of Autonomy", """@misc{udugama2023slamreview,
  title         = {Evolution of SLAM: Toward the Robust-Perception of Autonomy},
  author        = {Udugama, B.},
  year          = {2023},
  note          = {Written 2021},
  eprint        = {2302.06365},
  archivePrefix = {arXiv}
}"""),
    ("drl-autonomous-driving", "Review of Deep Reinforcement Learning for Autonomous Driving", """@misc{udugama2023drlreview,
  title         = {Review of Deep Reinforcement Learning for Autonomous Driving},
  author        = {Udugama, B.},
  year          = {2023},
  note          = {Written 2021},
  eprint        = {2302.06370},
  archivePrefix = {arXiv}
}"""),
    ("swarm-robotics-coordination", "Review on Efficient Strategies for Coordinated Motion and Tracking in Swarm Robotics", """@misc{udugama2023swarmreview,
  title         = {Review on Efficient Strategies for Coordinated Motion and Tracking in Swarm Robotics},
  author        = {Udugama, B.},
  year          = {2023},
  note          = {Written 2021},
  eprint        = {2302.06360},
  archivePrefix = {arXiv}
}"""),
    ("exploration-planning-2017", "Autonomous exploration planning strategy for a reconnaissance agent", """@inproceedings{thelasingha2017exploration,
  title     = {Autonomous exploration planning strategy for a reconnaissance agent},
  author    = {Thelasingha, Nilanga and Ekanayake, Sachini and Udugama, Bavantha and Godaliyadda, G. M. R. I. and Ekanayake, M. P. B. and Samaranayake, B. G. L. T. and Wijayakulasooriya, J. V.},
  booktitle = {2017 IEEE International Conference on Industrial and Information Systems (ICIIS)},
  pages     = {1--6},
  year      = {2017},
  doi       = {10.1109/ICIINFS.2017.8300386}
}"""),
    ("object-dimension-extraction", "Object Dimension Extraction for Environment Mapping with Low Cost Cameras Fused with Laser Ranging", """@inproceedings{ekanayake2017objectdimension,
  title         = {Object Dimension Extraction for Environment Mapping with Low Cost Cameras Fused with Laser Ranging},
  author        = {Ekanayake, E. M. S. P. and Thelasingha, T. H. M. N. C. and Udugama, U. V. B. L. and Godaliyadda, G. M. R. I. and Ekanayake, M. P. B. and Samaranayake, B. G. L. T. and Wijayakulasooriya, J. V.},
  booktitle     = {24th Annual Technical Conference of the IET Sri Lanka Network},
  year          = {2017},
  eprint        = {2302.01387},
  archivePrefix = {arXiv}
}"""),
    ("laser-ranging-mapping", "Laser Ranging Based Intelligent System for Unknown Environment Mapping", """@inproceedings{thelasingha2017laserranging,
  title     = {Laser Ranging Based Intelligent System for Unknown Environment Mapping},
  author    = {Thelasingha, T. H. M. N. C. and Udugama, U. V. B. L. and Ekanayake, E. M. S. P. and Godaliyadda, G. M. R. I. and Ekanayake, M. P. B. and Samaranayake, B. G. L. T. and Wijayakulasooriya, J. V.},
  booktitle = {Annual Sessions 2017, The Institution of Engineers Sri Lanka},
  year      = {2017}
}"""),
]


def build_bibtex():
    blocks = ""
    for p in PUBS["publications"]:
        bt = BIBTEX.get(p["slug"])
        if not bt:
            continue
        blocks += f"""
<h2 id="{e(p['slug'])}">{e(p['title'])}</h2>
<p class="pub-venue">{e(p['statusLabel'])}</p>
<pre style="overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:1rem;font-family:var(--mono);font-size:0.8125rem;line-height:1.6">{e(bt)}</pre>
"""
    for slug, title, bt in OTHER_BIBTEX:
        blocks += f"""
<h2 id="{e(slug)}">{e(title)}</h2>
<pre style="overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:1rem;font-family:var(--mono);font-size:0.8125rem;line-height:1.6">{e(bt)}</pre>
"""

    body = f"""
<p class="eyebrow"><a href="/publications/">Publications</a></p>
<h1>BibTeX.<br><em class="title-accent">Ready to cite.</em></h1>
<p class="standfirst">Every entry, as plain text. The Mono-Hydra++ entry is marked unpublished
because it is under review.</p>
{blocks}
"""
    shell("publications/bibtex", f"{NAME} | BibTeX entries for all publications",
          "Copy-ready BibTeX for every publication by Bavantha Udugama (U.V.B.L. Udugama), "
          "including Mono-Hydra, M2H, M2H-MX, and Mono-Hydra++.",
          body, crumb="BibTeX")


# ---------------------------------------------------------------- projects

def project_ld(pr):
    if pr["repos"]:
        return {
            "@context": "https://schema.org",
            "@type": "SoftwareSourceCode",
            "name": pr["name"],
            "description": pr["oneLine"],
            "url": f"{ORIGIN}/projects/{pr['slug']}/",
            "codeRepository": [r["url"] for r in pr["repos"]],
            "programmingLanguage": ["C++", "Python"],
            "author": {"@id": f"{ORIGIN}/#person", "@type": "Person", "name": NAME},
        }
    return {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": pr["name"],
        "description": pr["oneLine"],
        "url": f"{ORIGIN}/projects/{pr['slug']}/",
        "creativeWorkStatus": pr.get("statusLabel", pr["status"]),
        "author": {"@id": f"{ORIGIN}/#person", "@type": "Person", "name": NAME},
    }


def build_projects_index():
    overview = PROJECTS["overview"]

    def links(items, cls="entry-links"):
        return (f'<div class="{cls}">' + "".join(
            f'<a href="{e(x["href"])}">{e(x["label"])} <span aria-hidden="true">&#8599;</span></a>'
            for x in items) + '</div>')

    def entry_media(item):
        """The preview for one entry. Each system gets the output that actually shows it."""
        kind, key = item.get("mediaKind"), item.get("mediaKey")
        if kind == "video":
            return video(key, cls="entry-clip", autoloop=False,
                         caption=MEDIA["videos"].get(key, {}).get("caption", ""))
        if kind == "wipe":
            return wipe(key, heading=False, compact=True,
                        sizes="(min-width: 62em) 20rem, 90vw")
        if kind == "image":
            return picture(key, cls="entry-still", sizes="(min-width: 62em) 44rem, 92vw")
        return ""

    groups = []
    for gi, group in enumerate(overview["groups"], 1):
        entries = ""
        for n, item in enumerate(group["items"], 1):
            layout = item.get("layout", "split")
            media = entry_media(item)
            tags = "".join(f'<li>{e(tag)}</li>' for tag in item["tags"])
            copy = (f'<div class="entry-copy">'
                    f'<p class="spec entry-index">{gi:02d}.{n} &mdash; {e(item["focus"])}</p>'
                    f'<h3 class="entry-title">{e(item["name"])}</h3>'
                    f'<p class="spec entry-status">{e(item["status"])}</p>'
                    f'<p class="entry-text">{e(item["text"])}</p>'
                    f'<ul class="entry-tags" aria-label="Technologies">{tags}</ul>'
                    f'{links(item["links"])}</div>')
            entries += (f'<article class="entry entry-{e(layout)}">'
                        f'<div class="entry-media">{media}</div>{copy}</article>')

        related = (f'<p class="group-note spec-lg">{e(group["note"])} '
                   f'<a href="{e(group["related"]["href"])}">{e(group["related"]["label"])}</a>.</p>'
                   if group.get("related") else "")

        supporting = ""
        if group["id"] == "thesis":
            pf = overview["platform"]
            supporting = f"""
<aside class="platform-band bleed ground-dark" aria-labelledby="platform-title">
  <div class="bleed-wide platform-band-inner">
    <div class="platform-band-media">{picture("drone-top", sizes="(min-width: 62em) 34rem, 92vw", caption=False)}</div>
    <div class="platform-band-copy">
      <p class="spec">Embedded deployment</p>
      <h3 id="platform-title">{e(pf['title'])}</h3>
      <p>{e(pf['text'])}</p>
      <div class="readout readout-emb">
        <dl><dt>{e(pf['metric'])}</dt>
          <dd><span class="readout-label">{e(pf['metricLabel'])}</span>
            <span class="readout-note">{e(pf['conditions'])}</span></dd></dl>
      </div>
      <p><a href="{e(pf['href'])}">{e(pf['linkLabel'])} <span aria-hidden="true">&#8599;</span></a></p>
    </div>
  </div>
</aside>"""
        elif group["id"] == "commercial":
            supporting = ('<div class="group-aside">'
                          + video("humanoid-mapping", autoloop=False,
                                  caption="The venue map and robot pose, built with GMapping SLAM.")
                          + '<div class="group-press"><p class="spec">Deployment coverage</p>'
                          + links(group["press"], "group-press-links") + '</div></div>')

        groups.append(f"""
<section class="project-group" id="{e(group['id'])}" aria-labelledby="{e(group['id'])}-title">
  <div class="chapter-head">
    <p class="spec"><span>{e(group['label'])}</span><span>{e(group['meta'])}</span></p>
    <h2 class="chapter-title" id="{e(group['id'])}-title">{e(group['title'])}</h2>
    <p class="chapter-lede">{e(group['intro'])}</p>
  </div>
  <div class="entries">{entries}</div>{related}{supporting}
</section>""")

    nav = "".join(f'<a href="#{e(g["id"])}">{e(g["label"].split(" / ", 1)[1])}</a>'
                  for g in overview["groups"])
    body = f"""
<header class="page-open">
  <p class="spec">Research &amp; engineering</p>
  <h1 class="page-open-title">Projects.<br><em class="title-accent">Map, navigate &amp; deploy.</em></h1>
  <p class="page-open-lede">{e(overview['intro'])}</p>
  <nav class="page-open-jumps spec" aria-label="Project categories">{nav}</nav>
</header>
{''.join(groups)}
"""
    shell("projects", f"{NAME} | Robotics research and engineering projects",
          "Monocular mapping with Mono-Hydra++, multi-task perception with M2H and M2H-MX, "
          "ATLAS exploration, commercial service robots and reconnaissance robotics.",
          body, extra_ld=[person_node()], crumb="Projects",
          extra_head=f'\n<link rel="stylesheet" href="/assets/projects.css?v={asset_hash("/assets/projects.css")}">')


# the opening plate for each system: the output that shows what it is, at full width
PROJECT_LEAD = {
    "mono-hydra-plus": ("image", "pipeline-overview"),
    "m2h-mx":          ("video", "icra26"),
    "m2h":             ("video", "itc-loop"),
    "mono-hydra":      ("image", "scenegraph-system-design"),
    "learned-exploration": ("video", "scope-explorer"),
}


def project_lead(slug):
    kind, key = PROJECT_LEAD.get(slug, (None, None))
    if kind == "video":
        rec = MEDIA["videos"].get(key)
        if not rec:
            return ""
        src = rec.get("preview") or rec["mp4"]
        if rec.get("preview") and not (ROOT / rec["preview"].lstrip("/")).exists():
            src = rec["mp4"]
        inner = (f'<video poster="{rec["poster"]}" width="{rec["width"]}" height="{rec["height"]}" '
                 f'muted loop playsinline preload="metadata" data-autoloop '
                 f'data-full-src="{rec["mp4"]}" aria-label="{e(rec["alt"])}">'
                 f'<source src="{src}" type="video/mp4"></video>'
                 f'<button type="button" class="v-toggle" data-toggle '
                 f'aria-label="Play or pause video">Pause</button>'
                 f'<button type="button" class="v-expand" data-expand hidden '
                 f'aria-label="Play this clip in a larger frame">'
                 f'<span aria-hidden="true">&#x2921;</span>Expand</button>')
        caption = rec.get("caption", "")
        return (f'<figure class="case-lead"><div class="case-lead-media v-wrap">{inner}</div>'
                f'<figcaption class="spec">{e(caption)}</figcaption></figure>')
    if kind == "image":
        rec = MEDIA["images"].get(key)
        if not rec:
            return ""
        img = picture(key, caption=False, lazy=False, sizes="100vw")
        return (f'<figure class="case-lead"><div class="case-lead-media">{img}</div>'
                f'<figcaption class="spec">{e(rec.get("caption", ""))}</figcaption></figure>')
    return ""


def build_project_pages():
    pub_by_slug = {p["slug"]: p for p in PUBS["publications"]}
    for pr in PROJECTS["projects"]:
        repos = "".join(
            f'<li><a class="index-row" href="{e(r["url"])}">'
            f'<span class="index-title">{e(r["name"])}</span>'
            f'<span class="spec">{e(r["role"])}</span></a></li>'
            for r in pr["repos"])
        repos_block = (f'<section class="case-section"><h2 class="case-h">Code</h2>'
                       f'<ol class="index case-index">{repos}</ol></section>') if repos else ""

        nums_block = ""
        if pr.get("keyNumbers"):
            nums = "".join(f'<li><span class="case-number">{e(k)}</span></li>'
                           for k in pr["keyNumbers"])
            nums_block = f"""
<section class="case-results bleed ground-dark" aria-labelledby="{e(pr['slug'])}-results">
  <div class="bleed-wide">
    <p class="spec">Measured</p>
    <h2 class="case-h" id="{e(pr['slug'])}-results">Key numbers</h2>
    <ol class="case-numbers">{nums}</ol>
    <p class="spec case-provenance">Every figure here appears in the thesis results registry with
      its source location. Conditions are stated with the number.</p>
  </div>
</section>"""

        honesty = ""
        if pr.get("honesty"):
            honesty = (f'<div class="note case-note"><span class="note-label">Status</span>'
                       f'<p>{e(pr["honesty"])}</p></div>')

        method = ""
        if pr.get("method"):
            blocks = "".join(
                f'<div class="method-item"><h3>{e(m["title"])}</h3><p>{e(m["text"])}</p></div>'
                for m in pr["method"]["items"])
            method = (f'<section class="case-section"><h2 class="case-h">{e(pr["method"]["heading"])}</h2>'
                      f'<div class="method">{blocks}</div></section>')

        hyp = ""
        if pr.get("hypothesis"):
            hyp = (f'<section class="case-section"><h2 class="case-h">What is being tested</h2>'
                   f'<blockquote class="hypothesis"><p>{e(pr["hypothesis"])}</p></blockquote></section>')

        design = ""
        if pr.get("designPoints"):
            pts = "".join(f"<li>{e(x)}</li>" for x in pr["designPoints"])
            design = (f'<section class="case-section"><h2 class="case-h">Design commitments</h2>'
                      f'<p class="lede">{e(pr["commitment"])}</p>'
                      f'<ul class="limits">{pts}</ul></section>')

        paper = ""
        if pr.get("paper") and pr["paper"] in pub_by_slug:
            p = pub_by_slug[pr["paper"]]
            paper = (f'<section class="case-section"><h2 class="case-h">Paper</h2>'
                     f'<ol class="index case-index"><li>'
                     f'<a class="index-row" href="/publications/{e(p["slug"])}/">'
                     f'<span class="index-title">{e(p["title"])}</span>'
                     f'<span class="spec">{e(p["statusLabel"])}</span></a></li></ol></section>')

        status_bit = (f'<span class="tag tag-progress">{e(pr.get("statusLabel", pr["status"]))}</span>'
                      if pr["status"] == "in progress" else e(pr.get("statusLabel", pr["status"])))
        sysname = (e(pr["systemName"]) + " &middot; ") if pr.get("systemName") else ""

        body = f"""
<header class="case-open field-case-open">
  <div class="case-open-inner">
    <p class="spec case-crumb"><a href="/projects/">Projects</a> &middot; {e(pr["partLabel"])}</p>
    <h1 class="case-title">{e(pr["name"])}</h1>
    <div class="case-open-foot">
      <p class="case-line">{e(pr["oneLine"])}</p>
      <p class="spec case-meta">{sysname}{e(pr["years"])} &middot; {status_bit}</p>
    </div>
  </div>
  {project_lead(pr["slug"])}
</header>
<nav class="case-jumps" aria-label="Case study sections">
  <a href="#system">System</a>
{('<a href="#configuration">Onboard configuration</a><a href="#pipeline">Pipeline explained</a>' if pr['slug'] == 'mono-hydra-plus' else '')}
  <a href="#evidence">Evidence</a>
  <a href="/projects/">All projects ↗</a>
</nav>
{honesty}
<section class="case-section case-does" id="system">
  <div class="case-does-head"><p class="spec">01 &mdash; The system</p>
    <h2 class="case-h">What it does</h2></div>
  <p class="case-does-text">{e(pr["whatItDoes"])}</p>
</section>
{system_diagram(pr['slug'])}
{onboard_configuration() + pipeline_story() if pr['slug'] == 'mono-hydra-plus' else ''}
<section class="case-section case-evidence" id="evidence">
  <p class="spec">02 &mdash; Evidence</p>
  {PROJ_MEDIA.get(pr["slug"], "")}
</section>
{method}
{design}
{hyp}
{nums_block}
{paper}
{repos_block}
"""
        shell(f"projects/{pr['slug']}", f"{NAME} | {pr['name']}",
              f"{pr['oneLine']} By Bavantha Udugama, ITC University of Twente.",
              body, extra_ld=[project_ld(pr)], og_type="article", crumb=pr["name"],
              extra_head=f'\n<link rel="stylesheet" href="/assets/case.css?v={asset_hash("/assets/case.css")}">')


# ---------------------------------------------------------------- watch pages

def mmss(secs):
    m, s = divmod(int(secs or 0), 60)
    return f"{m}:{s:02d}"


def watch_player(key, w):
    """The clip, as the subject of the page rather than a figure inside an argument.

    Native controls, because this is the one page where scrubbing is the point, and the
    chapter list seeks through them. Autoplay still follows the site rule: media.js starts
    it only when it is in view, and never under reduced motion."""
    rec = MEDIA["videos"][key]
    sources = f'<source src="{rec["mp4"]}" type="video/mp4">'
    if rec.get("webm"):
        sources = f'<source src="{rec["webm"]}" type="video/webm">' + sources
    # a narrated clip is started by the viewer, with its sound, and stops at the end
    loop_attrs = "" if rec.get("audio") else 'muted loop data-autoloop'
    return f"""
<div class="watch-stage">
  <div class="watch-stage-head"><span>{e(w["stageHead"])}</span><span>{e(w["stageFoot"])}</span></div>
  <div class="watch-player">
    <video poster="{rec["poster"]}" width="{rec["width"]}" height="{rec["height"]}"
      controls playsinline preload="metadata" data-watch {loop_attrs}
      aria-label="{e(rec["alt"])}">{sources}</video>
  </div>
</div>"""


def build_video_pages():
    """One page per clip in data/videos.json, whose single subject is that clip.

    Google will not consider a video for video results unless some page exists whose main
    purpose is watching it. The clips also stay where they are on the home, publication and
    project pages; those embeds now link here, and their markup points here too."""
    pub_by_slug = {p["slug"]: p for p in PUBS["publications"]}
    proj_by_slug = {pr["slug"]: pr for pr in PROJECTS["projects"]}

    for w in VIDEOPAGES:
        key = w["key"]
        rec = MEDIA["videos"].get(key)
        if not rec:
            print(f"NOTE: no media for watch page {w['slug']}, skipped")
            continue
        secs = mp4_duration(rec["mp4"])

        notes = "".join(f'<div class="watch-note"><h3>{e(s["heading"])}</h3>'
                        f'<p>{e(s["text"])}</p></div>' for s in w["sections"])

        chapters = ""
        if w.get("chapters"):
            # the row is a span here and media.js swaps it for a button that seeks. Without
            # JavaScript this stays a list of times against what happens at them, which is
            # still the whole point of a chapter list.
            items = "".join(
                f'<li data-seek="{c["start"]}"><span class="chapter-row">'
                f'<span class="chapter-time">{mmss(c["start"])}</span>'
                f'<span class="chapter-name">{e(c["name"])}</span></span></li>'
                for c in w["chapters"])
            chapters = (f'<h2 id="key-moments">Key moments</h2>'
                        f'<ol class="chapters" data-chapters>{items}</ol>')

        facts = list(w["specs"])
        mb = rec["bytes"].get(Path(rec["mp4"]).name)
        facts += [
            {"label": "Length", "value": f"{mmss(secs)} ({secs} seconds)" if secs else "unknown"},
            {"label": "Frame", "value": f'{rec["width"]} x {rec["height"]} pixels'},
            {"label": "File", "value": f"MP4, H.264, {mb / 1e6:.1f} MB" if mb else "MP4, H.264"},
            {"label": "Published", "value": humandate(git_filedate(rec["mp4"])[:7])},
        ]
        specs = "".join(f'<div><dt>{e(f["label"])}</dt><dd>{e(f["value"])}</dd></div>'
                        for f in facts)

        work = ""
        pub = pub_by_slug.get(w.get("paper"))
        if pub:
            wanted = set(w.get("resultIds", []))
            res = [h for h in pub.get("headline", []) if h["registryId"] in wanted]
            res_html = ""
            if res:
                res_html = ('<ul class="results is-single">' + "".join(
                    f'<li class="result"><span class="value">{e(h["value"])}</span>'
                    f'<span class="what">{e(h["what"])}</span>'
                    f'<span class="conditions">{e(h["conditions"])}</span></li>'
                    for h in res) + "</ul>")
            links = [f'<li><a href="/publications/{e(pub["slug"])}/">The paper, in full</a>'
                     f' <span class="pub-venue">{e(pub["statusLabel"])}</span></li>']
            pr = proj_by_slug.get(w.get("project"))
            if pr:
                links.append(f'<li><a href="/projects/{e(pr["slug"])}/">{e(pr["name"])}</a>'
                             f' <span class="pub-venue">how the system is put together</span></li>')
            if pub["links"].get("arxiv"):
                links.append(f'<li><a href="{e(pub["links"]["arxiv"])}">Preprint on arXiv</a></li>')
            if pub["links"].get("code"):
                links.append(f'<li><a href="{e(pub["links"]["code"])}">Code on GitHub</a></li>')
            work = f"""
<h2 id="the-work">The work behind it</h2>
<p>{e(pub["claim"])}</p>
{res_html}
<ul class="limits">{"".join(links)}</ul>"""
        elif w.get("work"):
            # A clip whose paper is not one of the numbered publications, so there is no
            # slug to look up. The entry states the links itself.
            items = "".join(
                f'<li><a href="{e(l["href"])}">{e(l["label"])}</a>'
                + (f' <span class="pub-venue">{e(l["note"])}</span>' if l.get("note") else "")
                + '</li>' for l in w["work"]["links"])
            work = f"""
<h2 id="the-work">The work behind it</h2>
<p>{e(w["work"]["text"])}</p>
<ul class="limits">{items}</ul>"""

        more = ""
        if w.get("related"):
            cards = "".join(
                f'<li class="card"><p class="eyebrow">Watch next</p>'
                f'<h3><a href="{e(r["href"])}">{e(r["label"])}</a></h3>'
                f'<p>{e(r["text"])}</p></li>' for r in w["related"])
            single = " is-single" if len(w["related"]) == 1 else ""
            head = "Another clip" if len(w["related"]) == 1 else "More clips"
            more = f'<h2 id="more">{head}</h2><ul class="cards{single}">{cards}</ul>'

        body = f"""
<p class="eyebrow">{e(w["eyebrow"])}</p>
<h1>{e(w["title"])}</h1>
<p class="standfirst">{e(w["standfirst"])}</p>
{watch_player(key, w)}
<p class="watch-caption">{e(rec["caption"])}</p>
{chapters}
<h2 id="what-you-are-seeing">What you are seeing</h2>
<div class="watch-notes">{notes}</div>
<h2 id="details">Recording details</h2>
<dl class="specs">{specs}</dl>
{work}
{more}
"""
        # og:video lets a share of this page carry the clip itself, not only the card.
        og_video = (f'\n<meta property="og:video" content="{ORIGIN}{rec["mp4"]}">'
                    f'\n<meta property="og:video:secure_url" content="{ORIGIN}{rec["mp4"]}">'
                    f'\n<meta property="og:video:type" content="video/mp4">'
                    f'\n<meta property="og:video:width" content="{rec["width"]}">'
                    f'\n<meta property="og:video:height" content="{rec["height"]}">'
                    + (f'\n<meta property="video:duration" content="{secs}">' if secs else ""))

        shell(f"videos/{w['slug']}", f"{NAME} | {w['metaTitle']}", w["description"], body,
              extra_ld=[watch_page_ld(w, key)], og_type="video.other",
              crumb=w["metaTitle"], flat_crumbs=True, extra_head=og_video)


def watch_page_ld(w, key):
    """The page node, saying in as many words that this page exists to show this video."""
    url = watch_url(key, absolute=True)
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "url": url,
        "name": w["title"],
        "description": w["description"],
        "inLanguage": "en",
        "isPartOf": {"@id": f"{ORIGIN}/#profilepage"},
        "primaryImageOfPage": ORIGIN + MEDIA["videos"][key]["poster"],
        "mainEntity": {"@id": f"{url}#video-{key}"},
        "author": {"@id": f"{ORIGIN}/#person", "@type": "Person", "name": NAME},
    }


# ---------------------------------------------------------------- cv, contact

def watch_title_link(key, title):
    """A clip title, linked to its watch page where it has one."""
    url = watch_url(key)
    return f'<a href="{url}">{e(title)}</a>' if url else e(title)


def role_loop(role):
    """The stages of a role's work as clips, laid out as a strip inside the role itself.

    Data lives in cv.json so the sequence is editable without touching markup. autoplay is
    per clip: stairs-zupt is 15 MB, larger than the rest together, so it stays poster-only
    until asked for.
    """
    cells = []
    for c in role.get("loop", []):
        # captions are hidden in this strip, so the watch-page link would be too: link the
        # clip from its title instead of emitting a link nobody can see.
        clip = video(c["clip"], cls="loopstrip-clip", autoloop=c.get("autoplay", True),
                     watch_link=False)
        if not clip:
            continue
        cells.append(
            f'<li class="loopstrip-item">'
            f'<p class="loopstrip-index">{e(c["index"])}</p>'
            f'<h4>{watch_title_link(c["clip"], c["title"])}</h4>'
            f'{clip}'
            f'<p class="loopstrip-note">{e(c["note"])}</p>'
            f'</li>')
    if not cells:
        return ""
    intro = (f'<p class="media-label">{e(role["loopIntro"])}</p>'
             if role.get("loopIntro") else "")
    return f'<div class="role-loop">{intro}<ol class="loopstrip">{"".join(cells)}</ol></div>'


def build_cv():
    def ym(v, default_month):
        if v is None:
            return (9999, 12)          # ongoing sorts to the top
        parts = str(v).split("-")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else default_month)

    def sortkey(t):
        # reverse chronological by start, which is the order a reader expects on a CV;
        # ties fall back to the end date so a milestone sits above the role it happened in
        return (ym(t["start"], 1), ym(t["end"], 12))

    items = ""
    for t in sorted(TIMELINE["timeline"], key=sortkey, reverse=True):
        a, b = humandate(t["start"]), humandate(t["end"])
        if t["end"] is None:
            when = a if "milestone" in t.get("tags", []) else f"{a} to present"
        elif a == b:
            when = a
        else:
            when = f"{a} to {b}"
        anchor = f' id="{e(t["anchor"])}"' if t.get("anchor") else ""
        kind = " tl-milestone" if "milestone" in t.get("tags", []) else ""
        items += f"""
    <li class="tl-item{kind}"{anchor}>
      <div class="tl-when">{e(when)}</div>
      <div class="tl-what">
        <h3>{e(t["title"])}</h3>
        <p class="tl-org">{e(t["org"])}</p>
        <p>{e(t["detail"])}</p>
      </div>
    </li>"""

    facts = "".join(f'<div><dt>{e(f["label"])}</dt><dd>{e(f["value"])}</dd></div>'
                    for f in CV["facts"])

    glance = "".join(
        f'<div class="readout glance-item"><dt>{e(g["value"])}</dt>'
        f'<dd><span class="readout-label">{e(g["label"])}</span>'
        f'<span class="readout-note">{e(g["detail"])}</span></dd></div>'
        for g in CV["glance"])

    roles = ""
    for r in CV["experience"]:
        bullets = "".join(f"<li>{e(b)}</li>" for b in r["bullets"])
        tags = "".join(f'<span class="chip">{e(t)}</span>' for t in r.get("tags", []))
        note = f'<p class="role-note">{e(r["note"])}</p>' if r.get("note") else ""
        press = ""
        if r.get("press"):
            rows = "".join(
                f'<li><a href="{e(x["href"])}">{e(x["title"])}</a>'
                f' <span class="pub-venue">{e(x["outlet"])}, {e(x["date"])}</span>'
                + (f'<span class="press-note">{e(x["note"])}</span>' if x.get("note") else "")
                + '</li>' for x in r["press"])
            press = (f'<p class="media-label">{e(r.get("pressLabel", "In the press"))}</p>'
                     f'<ul class="limits role-press">{rows}</ul>')
        loop = role_loop(r)
        media = ""
        if r.get("media"):
            clips = "".join(video(k) for k in r["media"])
            if clips:
                intro = (f'<p class="media-label">{e(r["mediaIntro"])}</p>'
                         if r.get("mediaIntro") else "")
                media = f'<div class="tl-media">{intro}{clips}</div>'
        roles += f"""
    <article class="role">
      <div class="role-when"><span>{e(r["period"])}</span></div>
      <div class="role-body">
        <h3>{e(r["role"])}</h3>
        <p class="role-org">{e(r["org"])} <span>{e(r["place"])}</span></p>
        {note}
        <ul class="role-points">{bullets}</ul>
        {press}
        <div class="chips">{tags}</div>
        {loop}
        {media}
      </div>
    </article>"""

    edu = "".join(f"""
    <article class="role role-edu">
      <div class="role-when"><span>{e(x["period"])}</span></div>
      <div class="role-body">
        <h3>{e(x["degree"])}</h3>
        <p class="role-org">{e(x["org"])} <span>{e(x["place"])}</span></p>
        <p class="role-result">{e(x["result"])}</p>
        <p>{e(x["detail"])}</p>
      </div>
    </article>""" for x in CV["education"])

    pub_rows = "".join(f"""
    <li class="cv-pub">
      <span class="cv-pub-year">{e(str(p["year"]))}</span>
      <span class="cv-pub-body">
        <a href="/publications/{e(p["slug"])}/">{e(p["title"])}</a>
        <span class="cv-pub-meta">{authors_html(p["authors"])} &middot; {e(p["venue"])}
          &middot; {e(p["status"])}</span>
      </span>
    </li>""" for p in PUBS["publications"])

    teaching = "".join(
        f'<div class="teach"><p class="teach-when">{e(x["period"])}</p>'
        f'<p>{e(x["detail"])}</p></div>' for x in TIMELINE["teaching"])

    awards = "".join(
        f'<li class="award"><span class="award-year">{e(a["year"])}</span>'
        f'<span><strong>{e(a["title"])}</strong><br>{e(a["org"])}</span></li>'
        for a in CV["awards"])

    skills = "".join(f"""
    <div class="skill">
      <p class="skill-head">{e(k["group"])}{(" <span>" + e(k["years"]) + "</span>") if k.get("years") else ""}</p>
      <div class="chips">{"".join(f'<span class="chip">{e(i)}</span>' for i in k["items"])}</div>
    </div>""" for k in CV["skills"])

    toc = "".join(f'<a href="#{e(x["id"])}" data-spy-link>{e(x["label"])}</a>'
                  for x in CV["sections"])

    body = f"""
<header class="cv-head">
  <div class="cv-identity"><div>
  <p class="eyebrow">Curriculum vitae / Robotics software engineer</p>
  <h1>{e(NAME)}</h1>
  <p class="standfirst">{e(CV["summary"])}</p></div>
  <div class="cv-portrait">{picture('portrait', caption=False, lazy=False, sizes='180px')}</div></div>
  <dl class="cv-facts">{facts}</dl>
  <div class="cv-actions">
    <button class="action action-primary" type="button" data-print hidden>Print or save as PDF</button>
    <a class="action" href="mailto:{e(SITE['contact']['email'])}">Email me</a>
    <a class="action" href="/publications/bibtex/">BibTeX</a>
  </div>
</header>

<div class="cv-layout">
  <nav class="cv-toc" aria-label="Sections of this CV" data-spy>{toc}</nav>
  <div class="cv-main">
    {experience_graphic()}
    <section class="cv-section" id="profile">
      <h2>At a glance</h2>
      <dl class="glance" aria-label="Key figures">{glance}</dl>
    </section>

    <section class="cv-section" id="experience">
      <h2>Experience</h2>
      <div class="roles">{roles}</div>
    </section>

    <section class="cv-section" id="education">
      <h2>Education</h2>
      <div class="roles">{edu}</div>
    </section>

    <section class="cv-section" id="publications">
      <h2>Publications</h2>
      <p class="section-intro">Four first-author papers from the PhD. Each links to a page with
      the claim, the numbers, and the code.</p>
      <ul class="cv-pubs">{pub_rows}</ul>
      <p class="beat-link"><a href="/publications/">All publications, with abstracts</a></p>
    </section>

    <section class="cv-section" id="teaching">
      <h2>Teaching and supervision</h2>
      {teaching}
    </section>

    <section class="cv-section" id="awards">
      <h2>Awards</h2>
      <ul class="awards">{awards}</ul>
    </section>

    <section class="cv-section" id="skills">
      <h2>Skills</h2>
      <div class="skills">{skills}</div>
    </section>

    <section class="cv-section" id="timeline">
      <h2>Timeline</h2>
      <p class="section-intro">Every position and every milestone in one column, newest first.</p>
      <ul class="timeline">{items}</ul>
    </section>

  </div>
</div>
"""
    shell("cv", f"{NAME} | Curriculum vitae",
          "Curriculum vitae of Bavantha Udugama: PhD candidate at ITC University of Twente, "
          "robotics perception engineer, available from August 2026.",
          body, extra_ld=[person_node()], crumb="Curriculum vitae")


def build_contact():
    L = SITE["links"]
    email = SITE["contact"]["email"]
    rows = [("Email", f'<a href="mailto:{e(email)}">{e(email)}</a>') if email else (None, None),
            (("ORCID", f'<a rel="me" href="{e(ORCID_URL)}">{e(ORCID_ID)}</a>')
             if ORCID_URL else (None, None)),
            ("Google Scholar", f'<a href="{e(L["googleScholar"])}">Google Scholar profile</a>'),
            ("GitHub", f'<a href="{e(L["github"])}">github.com/BavanthaU</a>'),
            ("LinkedIn", f'<a href="{e(L["linkedin"])}">LinkedIn profile</a>'),
            ("University", f'<a href="{e(L["utStaffPage"])}">University of Twente staff page</a>'),
            (("IEEE", f'<a href="{e(L["ieeeAuthorPage"])}">IEEE author page</a>')
             if L.get("ieeeAuthorPage") else (None, None))]
    lis = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in rows if k and v)

    body = f"""
<header class="folio-heading contact-heading"><div>
<p class="eyebrow">Contact / {e(SITE['contact']['location'])}</p>
<h1>Build robot perception.<br><em>Deploy it onboard.</em></h1>
<p class="standfirst">For robotics software, perception, SLAM and navigation roles, or research collaborations.</p>
<p class="contact-availability">{e(SITE['contact']['availability'])}</p>
<a class="action action-primary" href="mailto:{e(email)}">Email me</a></div>
<div class="contact-portrait">{picture('portrait', caption=False, lazy=False, sizes='260px')}
<p class="spec">{e(NAME)}<br>Robotics software engineer</p></div></header>
<h2>Find me here</h2>
<dl class="contact-links">{lis}</dl>
<div class="note">
  <span class="note-label">Email</span>
  <p>Please use the address above. My former University of Twente email is no longer the contact address listed for this site.</p>
</div>
"""
    shell("contact", f"{NAME} | Contact",
          "Contact Bavantha Udugama, robotics perception researcher, for collaboration on SLAM, "
          "spatial perception, and edge deployment.",
          body, extra_ld=[person_node()], crumb="Contact")


def build_404():
    body = """
<p class="eyebrow">404 / Page not found</p>
<h1>Find the project<br><em class="title-accent">you came for.</em></h1>
<p class="standfirst">That address does not exist on this site.</p>
<p><a href="/">Home</a> &middot; <a href="/publications/">Publications</a> &middot;
<a href="/projects/">Projects</a></p>
"""
    out = ROOT / "404.html"
    shell("__404__", f"{NAME} | Page not found", "Page not found.", body)
    tmp = ROOT / "__404__" / "index.html"
    out.write_text(tmp.read_text())
    shutil.rmtree(ROOT / "__404__")
    PAGES.remove("__404__")


# ---------------------------------------------------------------- site files

def _page_images(markup):
    """Every distinct image the rendered page shows, largest encode first per source set.

    Read back out of the HTML that was just written rather than tracked while building, so
    a figure added anywhere reaches the sitemap without a second place to remember."""
    seen = []
    for src in re.findall(r'<img[^>]+src="(/[^"]+)"', markup):
        if src not in seen:
            seen.append(src)
    for poster in re.findall(r'<video[^>]+poster="(/[^"]+)"', markup):
        if poster not in seen:
            seen.append(poster)
    return seen


def build_sitemap():
    urls = ""
    for p in sorted(PAGES):
        loc = f"{ORIGIN}/" if p == "" else f"{ORIGIN}/{p}/"
        pri = "1.0" if p == "" else ("0.8" if p.count("/") == 0 else "0.6")
        f = ROOT / (("index.html" if p == "" else p + "/index.html"))
        markup = f.read_text() if f.exists() else ""
        extra = ""
        for src in _page_images(markup):
            extra += f"\n    <image:image><image:loc>{ORIGIN}{src}</image:loc></image:image>"
        for key in videos_in(markup):
            # A clip with a watch page is listed against that page only. Listing the same
            # content_loc under six URLs invites Google to rank one of the six that is not
            # the page built for watching it.
            if key in WATCH and p != f"videos/{WATCH[key]['slug']}":
                continue
            rec = MEDIA["videos"][key]
            dur = mp4_duration(rec["mp4"])
            extra += (
                "\n    <video:video>"
                f"\n      <video:thumbnail_loc>{ORIGIN}{rec['poster']}</video:thumbnail_loc>"
                f"\n      <video:title>{e(WATCH[key]['title'] if key in WATCH else video_title(key, rec))}</video:title>"
                f"\n      <video:description>{e(((WATCH[key]['description'] + ' ' + rec['alt']) if key in WATCH else rec['alt'])[:2040])}</video:description>"
                f"\n      <video:content_loc>{ORIGIN}{rec['mp4']}</video:content_loc>"
                + (f"\n      <video:duration>{dur}</video:duration>" if dur else "")
                + f"\n      <video:publication_date>{git_filedate(rec['mp4'])}</video:publication_date>"
                "\n      <video:family_friendly>yes</video:family_friendly>"
                "\n      <video:live>no</video:live>"
                "\n    </video:video>")
        urls += (f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{git_lastmod(p)}</lastmod>"
                 f"\n    <priority>{pri}</priority>{extra}\n  </url>\n")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"\n'
        '        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">\n'
        + urls + "</urlset>\n")

    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n")

    (ROOT / "humans.txt").write_text(f"""/* TEAM */
Name: {NAME}
Publishes as: {PUBNAME}
Role: {SITE['identity']['role']}, {SITE['identity']['affiliation']['name']}
Contact: {SITE['contact'].get('email') or 'see /contact/'}
ORCID: {ORCID_URL or 'none'}
Scholar: {SITE['links']['googleScholar']}
GitHub: {SITE['links']['github']}

/* SITE */
Standards: HTML5, CSS3
Components: none. Hand-written, no framework, no runtime dependency.
Built: {TODAY}
Source of truth: data/*.json, rendered by tools/build.py
""")


MONO_STACK = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def _bu_svg(radius, size=32):
    """The BU mark on the brand accent. Shared by the tab icon and the PNG rasteriser.

    radius 4 for the tab icon; 0 for apple-touch, because iOS applies its own mask and a
    pre-rounded source shows corner fringing under it.
    """
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
        f'width="{size}" height="{size}">'
        f'<rect width="32" height="32" rx="{radius}" fill="#006f6b"/>'
        '<text x="16" y="16" text-anchor="middle" dominant-baseline="central" '
        f"font-family='{MONO_STACK}' font-size=\"13\" font-weight=\"700\" "
        'letter-spacing="-1" fill="#eef3f2">BU</text>'
        "</svg>"
    )


def build_favicon():
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "favicon.svg").write_text(_bu_svg(4) + "\n")
    missing = [n for n in ("favicon-32.png", "favicon-180.png")
               if not (ROOT / "assets" / n).exists()]
    if missing:
        print("NOTE: raster fallbacks missing: " + ", ".join(missing))
        print("      regenerate with: python3 tools/favicon_png.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument("--home-only", action="store_true",
                        help="Render only the homepage, preserving all other generated pages")
    targets.add_argument("--projects-only", action="store_true",
                         help="Render only the Projects overview, preserving all other pages")
    args = parser.parse_args()
    if args.home_only:
        build_home()
        print("built homepage only")
        return

    if args.projects_only:
        build_projects_index()
        print("built Projects overview only")
        return

    global PUB_FIGURE, PROJ_MEDIA
    PUB_FIGURE = _pub_figures()
    PROJ_MEDIA = _proj_media()
    build_favicon()
    build_home()
    build_research()
    build_publications_index()
    build_publication_pages()
    build_bibtex()
    build_projects_index()
    build_project_pages()
    build_video_pages()
    build_cv()
    build_contact()
    build_404()
    build_sitemap()
    missing = check_media()
    if missing:
        print("WARNING: the manifest names files that are not on disk:")
        for m in missing:
            print("  " + m)
    print(f"built {len(PAGES)} pages + sitemap.xml, robots.txt, humans.txt, 404.html")
    for p in sorted(PAGES):
        print("  /" + (p + "/" if p else ""))


if __name__ == "__main__":
    main()
