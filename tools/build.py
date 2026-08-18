#!/usr/bin/env python3
"""Render the static site from data/*.json.

Python 3 standard library only. No npm, no bundler, no framework.
Output is plain HTML committed to the repository, so GitHub Pages serves files that were
never touched by a build step at request time. Run this after editing anything in data/.

    python3 tools/build.py

Every page it writes contains its full text in the served HTML. Nothing that matters for
search is injected by JavaScript.
"""

import html
import json
import os
import re
import shutil
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

ORIGIN = SITE["origin"].rstrip("/")
NAME = SITE["identity"]["canonicalName"]
PUBNAME = SITE["identity"]["publishingName"]

PAGES = []  # collected for sitemap.xml


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


def breadcrumbs(path, title):
    if not path:
        return None
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{ORIGIN}/"}]
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
        "jobTitle": SITE["identity"]["role"],
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
    node["image"] = f"{ORIGIN}/media/og/home.png"
    if SITE["identity"].get("image"):
        node["image"] = SITE["identity"]["image"]
    return node


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


def video(key, cls="", autoloop=True):
    """Poster-first video. Autoplay is handled by media.js only when in view."""
    rec = MEDIA["videos"].get(key)
    if not rec:
        return ""
    sources = f'<source src="{rec["mp4"]}" type="video/mp4">'
    if rec.get("webm"):
        sources = f'<source src="{rec["webm"]}" type="video/webm">' + sources
    gated = rec.get("clickToLoad")
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
                f'<span class="v-size">{sum(rec["bytes"].values())/1e6:.1f} MB</span></button>'
                f'<template data-gate-src>{html.escape(inner)}</template></div>')
    else:
        body = f'<div class="v-wrap">{inner}<button type="button" class="v-toggle" ' \
               f'data-toggle aria-label="Play or pause video">Pause</button></div>'
    cap = f'<figcaption>{e(rec["caption"])}</figcaption>' if rec.get("caption") else ""
    return f'<figure class="v-figure {cls}">{body}{cap}</figure>'


def video_ld(key, page_url):
    rec = MEDIA["videos"].get(key)
    if not rec:
        return None
    return {"@context": "https://schema.org", "@type": "VideoObject",
            "name": rec.get("caption", "")[:110] or NAME,
            "description": rec["alt"],
            "thumbnailUrl": ORIGIN + rec["poster"],
            "uploadDate": TODAY,
            "contentUrl": ORIGIN + rec["mp4"],
            "embedUrl": page_url}


def wipe(set_id="itc-corridor", heading=True):
    """RGB, predicted depth, predicted semantics on one frame.
    Without JavaScript this is three frames side by side, which is already the point."""
    spec = MEDIACFG.get("wipeSets", {}).get(set_id)
    if not spec:
        return ""
    keys = spec["panes"]
    if not all(k in MEDIA["frames"] for k in keys):
        return ""
    panes = ""
    for i, k in enumerate(keys):
        rec = MEDIA["frames"][k]
        big = rec["sources"]["jpg"][-1]["path"]
        av = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["avif"])
        wp = ", ".join(f'{v["path"]} {v["w"]}w' for v in rec["sources"]["webp"])
        panes += (f'<div class="wipe-pane" data-pane="{i}">'
                  f'<picture>'
                  f'<source type="image/avif" srcset="{av}" sizes="(min-width:56em) 22rem, 92vw">'
                  f'<source type="image/webp" srcset="{wp}" sizes="(min-width:56em) 22rem, 92vw">'
                  f'<img src="{big}" alt="{e(rec["alt"])}" width="{rec["width"]}" '
                  f'height="{rec["height"]}" loading="lazy" decoding="async"></picture>'
                  f'<span class="wipe-label">{e(rec["label"])}</span></div>')
    head = f'<p class="wipe-title">{e(spec["title"])}</p>' if heading else ""
    return (f'<figure class="wipe" data-wipe>{head}'
            f'<div class="wipe-stage">{panes}</div>'
            f'<label class="wipe-control" data-wipe-control hidden>'
            f'<span class="sr-only">Blend between RGB, predicted depth, and predicted semantics'
            f'</span>'
            f'<input type="range" min="0" max="200" value="0" step="1" data-wipe-input>'
            f'</label>'
            f'<figcaption>{e(spec["caption"])} Drag the slider to blend between them.'
            f'</figcaption></figure>')


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
    return {
        "mono-hydra-plus": picture("mono-hydra-pp-pipeline") + picture("uhumans2-loop")
                           + picture("scannet-radius") + picture("scannet-failure"),
        "m2h-mx":          wipe("m2h-mx-indoor") + wipe("m2h-mx-outdoor")
                           + picture("m2h-mx-architecture") + picture("m2h-mx-rgm")
                           + picture("m2h-mx-ctm-msca"),
        "m2h":             wipe() + youtube_facade("X2w_AqGwkaY",
                               "Mono Hydra with M2H for Monocular 3D Scene Graph Construction",
                               "https://i.ytimg.com/vi/X2w_AqGwkaY/hqdefault.jpg"),
        "mono-hydra":      picture("scenegraph-system-design"),
    }


def _proj_media():
    return {
        "mono-hydra-plus": picture("scene-graph-itc") + picture("itc-embedded"),
        "m2h-mx":          wipe("m2h-mx-indoor") + wipe("m2h-mx-outdoor")
                           + video("icra26") + picture("m2h-mx-architecture"),
        "m2h":             video("itc-loop") + wipe(),
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


def shell(path, title, description, body, extra_ld=None, og_type="website", crumb=None):
    description = clamp(description)
    """path: '' for root, else 'research' or 'publications/m2h' with no slashes at the edges."""
    canonical = f"{ORIGIN}/" if path == "" else f"{ORIGIN}/{path}/"
    depth_prefix = "/"  # absolute paths throughout, the site sits at a domain root
    current = ' aria-current="page"'
    nav_bits = []
    for n in SITE["nav"]:
        mark = current if n["href"].strip("/") == path else ""
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
    bc = breadcrumbs(path, crumb or title.split(" | ")[0])
    if bc:
        nodes.append(bc)
    ld = "\n".join(jsonld(o) for o in nodes)
    og = ORIGIN + og_for(path)

    out = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
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
<link rel="stylesheet" href="{depth_prefix}assets/site.css">
<link rel="icon" href="{depth_prefix}assets/favicon.svg" type="image/svg+xml">
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead-inner">
    <a class="wordmark" href="/">{e(NAME)}</a>
    <nav class="nav" aria-label="Primary">{nav}</nav>
  </div>
</header>
<main id="main">
<div class="wrap">
{body}
</div>
</main>
<footer class="foot">
  <div class="wrap">
    <ul>
      <li><a rel="me" href="{e(SITE['links']['googleScholar'])}">Google Scholar</a></li>
      <li><a rel="me" href="{e(SITE['links']['github'])}">GitHub</a></li>
      <li><a rel="me" href="{e(SITE['links']['linkedin'])}">LinkedIn</a></li>
      <li><a rel="me" href="{e(SITE['links']['utStaffPage'])}">University of Twente</a></li>
      <li><a href="/publications/bibtex/">BibTeX</a></li>
    </ul>
    <p>{e(NAME)}, published as {e(PUBNAME)}. {e(SITE['identity']['affiliation']['shortName'])}.</p>
  </div>
</footer>
<script src="/assets/media.js" defer></script>
</body>
</html>
"""
    target = ROOT / (path + "/index.html" if path else "index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out)
    PAGES.append(path)
    return target


# ---------------------------------------------------------------- the descent

def descent_svg():
    prog = SITE["headlineProgression"]
    rows = prog["rows"]
    main = [r for r in rows if "embedded" not in r["system"].lower()]
    emb = [r for r in rows if "embedded" in r["system"].lower()]

    def val(r):
        return float(re.match(r"([\d.]+)", r["error"]).group(1))

    W, H = 720, 300
    x0, x1, y0, y1 = 78, 640, 34, 236
    vmax = 0.24
    ys = lambda v: y1 - (v / vmax) * (y1 - y0)
    step = (x1 - x0 - 80) / max(len(main) - 1, 1)
    xs = [x0 + 30 + i * step for i in range(len(main))]
    xe = x1 - 6

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-labelledby="descent-title descent-desc">',
             '<title id="descent-title">Mean mapping error on the ITC building second floor, '
             'across four system generations</title>',
             f'<desc id="descent-desc">Error falls from 0.19 metres for Mono-Hydra in 2023 to '
             f'0.08 metres for M2H-MX-L in 2026. A separate embedded operating point on the '
             f'Jetson Orin NX measures 0.22 metres at reduced input resolution.</desc>']

    for gv in (0.05, 0.10, 0.15, 0.20):
        y = ys(gv)
        parts.append(f'<line class="axis" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                     f'stroke-dasharray="2 4" opacity="0.6"/>')
        parts.append(f'<text x="{x0 - 10}" y="{y + 4:.1f}" text-anchor="end" '
                     f'font-size="11">{gv:.2f}</text>')

    parts.append(f'<line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}"/>')
    parts.append(f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    parts.append(f'<text x="{x0 - 10}" y="{y0 + 4}" text-anchor="end" font-size="11">metres</text>')

    pts = " ".join(f"{x:.1f},{ys(val(r)):.1f}" for x, r in zip(xs, main))
    parts.append(f'<polyline class="trend" points="{pts}"/>')

    slug_by_system = {"Mono-Hydra": "mono-hydra", "M2H": "m2h",
                      "M2H-MX-B": "m2h-mx", "M2H-MX-L": "m2h-mx"}

    for x, r in zip(xs, main):
        y = ys(val(r))
        slug = slug_by_system.get(r["system"])
        label = f'{r["system"]} {r["year"]}'
        inner = (f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5"/>'
                 f'<text class="plabel" x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" '
                 f'font-size="12">{e(r["error"])}</text>'
                 f'<text x="{x:.1f}" y="{y1 + 20:.1f}" text-anchor="middle" '
                 f'font-size="11">{e(label)}</text>')
        if slug:
            parts.append(f'<g class="pt"><a href="/publications/{slug}/" '
                         f'aria-label="{e(label)}, {e(r["error"])} mean error">{inner}</a></g>')
        else:
            parts.append(f'<g class="pt">{inner}</g>')

    for r in emb:
        y = ys(val(r))
        parts.append(
            f'<g class="pt">'
            f'<path class="dot-embedded" d="M {xe} {y - 6} L {xe + 6} {y} L {xe} {y + 6} '
            f'L {xe - 6} {y} Z"/>'
            f'<text class="plabel" x="{xe}" y="{y - 14:.1f}" text-anchor="middle" '
            f'font-size="12" fill="var(--signal)">{e(r["error"])}</text>'
            f'<text x="{xe}" y="{y1 + 20:.1f}" text-anchor="middle" font-size="11">embedded</text>'
            f'</g>')

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------- home

def build_home():
    d = SITE["deployment"]
    v = d["verified"]
    arc = SITE["arc"]
    prog = SITE["headlineProgression"]

    pubs = PUBS["publications"]
    cards = "".join(f"""
      <li class="card">
        <p class="eyebrow">{e(p["venueShort"])}</p>
        <h3><a href="/publications/{e(p["slug"])}/">{e(p["title"])}</a></h3>
        <p>{e(p["claim"])}</p>
        <p class="card-meta"><span>{e(p["statusLabel"])}</span></p>
      </li>""" for p in pubs)

    rows = "".join(f"""
        <tr{' class="embedded"' if "embedded" in r["system"].lower() else ""}>
          <td>{e(r["system"])}</td><td>{e(r["year"])}</td><td>{e(r["error"])}</td>
          <td>{e(r["resolution"])}</td><td>{e(r["hardware"])}</td>
        </tr>""" for r in prog["rows"])

    body = f"""
<div class="hero">
  <div>
    <h1>{e(NAME)}</h1>
    <p class="affil mono">{e(SITE['identity']['role'])} &middot;
      {e(SITE['identity']['affiliation']['shortName'])} &middot;
      published as {e(PUBNAME)}</p>
    <p class="lede">{e(arc['statement'])}</p>
  </div>

  <aside class="rail" aria-labelledby="rail-h">
    <p class="rail-title" id="rail-h">Running on the drone</p>
    <p class="metric">{e(v['rate'])}</p>
    <p class="metric-sub">{e(v['what'])}<br>
      {e(v['pipeline'])}<br>
      {e(v['inputResolution'])} input, {e(v['gpuCompute'])} GPU compute<br>
      {e(v['device'])}</p>
    <p class="caveat">Perception only. Odometry, mapping, and scene graph construction ran
      off-board. Full-suite onboard deployment is in progress.</p>
  </aside>
</div>

<figure class="descent">
  <div class="descent-head">
    <h2>The descent</h2>
    <span class="unit">{e(prog['label'])}</span>
  </div>
  <div class="descent-figure">{descent_svg()}</div>
  <div class="legend">
    <span><i class="k-main"></i> measured on laptop or desktop GPU</span>
    <span><i class="k-emb"></i> embedded operating point, Jetson Orin NX</span>
  </div>
  <figcaption>{e(prog['caption'])} The embedded point is a different accuracy, latency, and
    compute trade-off at reduced input resolution, not a regression.</figcaption>
</figure>

<div class="table-scroll">
  <table>
    <caption class="sr-only">Mapping error by system generation</caption>
    <thead><tr><th>System</th><th>Year</th><th>Mean error</th><th>Input</th><th>Hardware</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<h2>Watch it build</h2>
{video("itc-loop")}

<h2>Two parts</h2>
<div class="acts">
  <section class="act">
    <p class="act-no">{e(arc['actOne']['label'])}</p>
    <h3>{e(arc['actOne']['title'])}</h3>
    <p>{e(arc['actOne']['line'])}</p>
    <p><span class="tag">Four papers</span></p>
  </section>
  <section class="act">
    <p class="act-no">{e(arc['actTwo']['label'])}</p>
    <h3>{e(arc['actTwo']['title'])}</h3>
    <p>{e(arc['actTwo']['line'])}</p>
    <p><span class="tag tag-progress">In progress, no results yet</span></p>
  </section>
</div>
<p class="section-intro"><a href="/research/">Read the long-form argument</a>.</p>

<h2>What the camera gives the map</h2>
<p class="section-intro">M2H-MX takes one RGB frame and predicts metric depth and semantic labels
together. Those two outputs are the entire input to the mapping backend. Indoors is what the
system is built for; the street scene is the same model on data it was not designed for.</p>
{wipe("m2h-mx-indoor")}
{wipe("m2h-mx-outdoor")}

<h2>Selected work</h2>
<ul class="cards">{cards}</ul>
<p><a href="/publications/">All publications</a> &middot; <a href="/projects/">Projects and code</a></p>
"""
    shell("", f"{NAME} | Monocular spatial perception for robots",
          "Bavantha Udugama builds real-time 3D scene graphs from a single camera and IMU, "
          "with no depth sensor. PhD candidate at ITC, University of Twente.",
          body, extra_ld=[n for n in (person_node(), profile_page_node(),
                                      video_ld("itc-loop", f"{ORIGIN}/")) if n],
          og_type="profile")


# ---------------------------------------------------------------- research

def build_research():
    arc = SITE["arc"]
    a2 = arc["actTwo"]
    proj2 = next(p for p in PROJECTS["projects"] if p["slug"] == "learned-exploration")
    points = "".join(f"<li>{e(x)}</li>" for x in proj2["designPoints"])

    body = f"""
<h1>Research</h1>
<p class="standfirst">{e(arc['statement'])}</p>

<div class="note">
  <span class="note-label">Prologue</span>
  <p>{e(arc['prologue'])} <a href="{e(arc['prologueVideo'])}">The project video</a> is still online.</p>
</div>

<h2>{e(arc['actOne']['label'])}. {e(arc['actOne']['title'])}</h2>
<p>{e(arc['actOne']['line'])}</p>
{picture("perception-pipeline")}
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
ScanNet sequences fell from 17.59 cm to 6.91 cm, which puts a monocular system within reach of the
RGB-D baselines in the same table. The ablation is blunt about where the gain comes from: the
backbone matters more than the new decoder blocks.
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
those options and it may abstain. It may not invent one. Three requirements follow from the shape
of the task rather than from the hardware:</p>
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


def build_publications_index():
    items = "".join(f"""
    <li class="pub">
      <h3><a href="/publications/{e(p["slug"])}/">{e(p["title"])}</a></h3>
      <p class="pub-authors">{authors_html(p["authors"])}</p>
      <p class="pub-venue">{e(p["venue"])}
        {'<span class="tag tag-review">Under review</span>' if p["status"] == "under review" else ""}</p>
      <p>{e(p["claim"])}</p>
      {linkrow(p)}
    </li>""" for p in PUBS["publications"])

    ew = PUBS["earlierWork"]
    early = ""
    for x in ew["entries"]:
        xl = x.get("links", {})
        bits = []
        if xl.get("arxiv"):
            bits.append(f'<a href="{e(xl["arxiv"])}">arXiv</a>')
        if xl.get("video"):
            bits.append(f'<a href="{e(xl["video"])}">Video</a>')
        link = f'<div class="linkrow">{"".join(bits)}</div>' if bits else ""
        auth = f'<p class="pub-authors">{authors_html(x["authors"])}</p>' if x.get("authors") else ""
        role = f'<p class="pub-venue">{e(x["role"])}</p>' if x.get("role") else ""
        awards = ('<p class="pub-venue">' + e("; ".join(x["awards"])) + "</p>") if x.get("awards") else ""
        vattr = f'<p class="pub-venue">{e(x["videoAttribution"])}</p>' if x.get("videoAttribution") else ""
        when = f'{e(x["context"])}, {e(x["year"])}'
        early += f"""
    <li class="pub">
      <h3>{e(x["title"])}</h3>
      {auth}
      <p class="pub-venue">{when}{", " + e(x["grade"]) if x.get("grade") else ""}</p>
      {role}
      {awards}
      {f'<p>{e(x["relevance"])}</p>' if x.get("relevance") else ""}
      {f'<p class="pub-venue">{e(x["note"])}</p>' if x.get("note") else ""}
      {link}
      {vattr}
    </li>"""

    body = f"""
<h1>Publications</h1>
<p class="standfirst">Published as {e(PUBNAME)}.</p>
<ul class="publist">{items}</ul>

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
<p class="eyebrow"><a href="/publications/">Publications</a></p>
<h1>{e(p["title"])}</h1>
{alt}
<p class="pub-authors">{authors_html(p["authors"])}</p>
<p class="pub-venue">{e(p["venue"])}{"" if str(p["year"]) in p["venue"] else ", " + str(p["year"])}</p>
{linkrow(p)}
{review_note}

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
  title  = {Mono-Hydra++: Real-Time Monocular Scene Graph Construction with Multi-Task Learning for 3D Indoor Mapping},
  author = {Udugama, U. V. B. L. and Vosselman, George and Nex, Francesco},
  note   = {Under review, ISPRS Journal of Photogrammetry and Remote Sensing, manuscript PHOTO-S-26-02536},
  year   = {2026}
}""",
}


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
    body = f"""
<p class="eyebrow"><a href="/publications/">Publications</a></p>
<h1>BibTeX</h1>
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
    items = "".join(f"""
    <li class="card">
      <p class="eyebrow">{e(pr["partLabel"])}{" &middot; in progress" if pr["status"] == "in progress" else ""}</p>
      <h3><a href="/projects/{e(pr["slug"])}/">{e(pr["name"])}</a></h3>
      <p>{e(pr["oneLine"])}</p>
      <p class="card-meta">{"".join(chr(60)+"span"+chr(62)+e(k)+chr(60)+"/span"+chr(62) for k in pr.get("keyNumbers", [])[:2])}</p>
    </li>""" for pr in PROJECTS["projects"])

    body = f"""
<h1>Projects</h1>
<p class="standfirst">Systems and code. Each entry links to its repository and to the paper that
measures it.</p>
<ul class="cards">{items}</ul>

<h2>Platform</h2>
<p>{e(PROJECTS["platform"]["name"])}, {e(PROJECTS["platform"]["compute"])}.
{e(PROJECTS["platform"]["deploymentStatus"])}</p>
"""
    shell("projects", f"{NAME} | Projects and open-source code",
          "Open-source robotics perception systems: Mono-Hydra, M2H, M2H-MX, Mono-Hydra++, and "
          "ongoing work on learned exploration.",
          body, extra_ld=[person_node()], crumb="Projects")


def build_project_pages():
    pub_by_slug = {p["slug"]: p for p in PUBS["publications"]}
    for pr in PROJECTS["projects"]:
        repos = "".join(
            f'<li><a href="{e(r["url"])}">{e(r["name"])}</a> <span class="pub-venue">{e(r["role"])}</span></li>'
            for r in pr["repos"])
        repos_block = f"<h2>Code</h2><ul class=\"limits\">{repos}</ul>" if repos else ""

        nums = "".join(f'<li class="result"><span class="value">{e(k)}</span></li>'
                       for k in pr["keyNumbers"]) if pr.get("keyNumbers") else ""
        nums_block = f'<h2>Key numbers</h2><ul class="results">{nums}</ul>' if nums else ""

        honesty = ""
        if pr.get("honesty"):
            honesty = f"""
<div class="note">
  <span class="note-label">Status</span>
  <p>{e(pr["honesty"])}</p>
</div>"""

        design = ""
        if pr.get("designPoints"):
            pts = "".join(f"<li>{e(x)}</li>" for x in pr["designPoints"])
            design = f'<h2>Design commitments</h2><p class="lede">{e(pr["commitment"])}</p><ul class="limits">{pts}</ul>'

        paper = ""
        if pr.get("paper") and pr["paper"] in pub_by_slug:
            p = pub_by_slug[pr["paper"]]
            paper = (f'<h2>Paper</h2><p><a href="/publications/{e(p["slug"])}/">{e(p["title"])}</a>'
                     f'<br><span class="pub-venue">{e(p["statusLabel"])}</span></p>')

        body = f"""
<p class="eyebrow"><a href="/projects/">Projects</a> &middot; {e(pr["partLabel"])}</p>
<h1>{e(pr["name"])}</h1>
<p class="standfirst">{e(pr["oneLine"])}</p>
<p class="pub-venue">{e(pr["years"])} &middot;
  {'<span class="tag tag-progress">' + e(pr.get("statusLabel", pr["status"])) + '</span>'
   if pr["status"] == "in progress" else e(pr.get("statusLabel", pr["status"]))}</p>
{honesty}
<h2>What it does</h2>
<p>{e(pr["whatItDoes"])}</p>
{PROJ_MEDIA.get(pr["slug"], "")}
{design}
{nums_block}
{paper}
{repos_block}
"""
        shell(f"projects/{pr['slug']}", f"{NAME} | {pr['name']}",
              f"{pr['oneLine']} By Bavantha Udugama, ITC University of Twente.",
              body, extra_ld=[project_ld(pr)], og_type="article", crumb=pr["name"])


# ---------------------------------------------------------------- cv, contact

def build_cv():
    def ym(v, default_month):
        if v is None:
            return (9999, 12)          # ongoing sorts to the top
        parts = str(v).split("-")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else default_month)

    def sortkey(t):
        # newest first, by when it ended; ongoing roles lead, then by start
        return (ym(t["end"], 12), ym(t["start"], 1))

    items = ""
    for t in sorted(TIMELINE["timeline"], key=sortkey, reverse=True):
        a, b = humandate(t["start"]), humandate(t["end"])
        if t["end"] is None:
            when = a if "milestone" in t.get("tags", []) else f"{a} to present"
        elif a == b:
            when = a
        else:
            when = f"{a} to {b}"
        items += f"""
    <li class="tl-item">
      <div class="tl-when">{e(when)}</div>
      <div class="tl-what">
        <h3>{e(t["title"])}</h3>
        <p class="tl-org">{e(t["org"])}</p>
        <p>{e(t["detail"])}</p>
      </div>
    </li>"""

    teaching = "".join(f'<p>{e(x["detail"])} <span class="pub-venue">{e(x["period"])}</span></p>'
                       for x in TIMELINE["teaching"])

    body = f"""
<h1>Curriculum vitae</h1>
<p class="standfirst">{e(SITE['identity']['role'])} at {e(SITE['identity']['affiliation']['name'])},
available from {e(humandate(SITE['contact']['availableFrom']))}. Published as {e(PUBNAME)}.</p>

<h2>Timeline</h2>
<ul class="timeline">{items}</ul>

<h2>Teaching and supervision</h2>
{teaching}

<h2>Selected skills</h2>
<p>Real-time perception and 3D mapping: visual-inertial SLAM, sensor fusion, 6-DoF state
estimation, pose graph optimisation, metric-semantic mapping. Computer vision and machine
learning: PyTorch, semantic segmentation, monocular depth, dense multi-task learning. Deployment:
C++, Python, ROS 1 and ROS 2, Docker, TensorRT, Jetson Orin NX, FP16 inference optimisation.</p>
"""
    shell("cv", f"{NAME} | Curriculum vitae",
          "Curriculum vitae of Bavantha Udugama: PhD candidate at ITC University of Twente, "
          "robotics perception engineer, available from August 2026.",
          body, extra_ld=[person_node()], crumb="Curriculum vitae")


def build_contact():
    L = SITE["links"]
    email = SITE["contact"]["email"]
    rows = [("Email", f'<a href="mailto:{e(email)}">{e(email)}</a>') if email else None,
            ("Google Scholar", f'<a href="{e(L["googleScholar"])}">Google Scholar profile</a>'),
            ("GitHub", f'<a href="{e(L["github"])}">github.com/BavanthaU</a>'),
            ("LinkedIn", f'<a href="{e(L["linkedin"])}">LinkedIn profile</a>'),
            ("University", f'<a href="{e(L["utStaffPage"])}">University of Twente staff page</a>'),
            ("IEEE", f'<a href="{e(L["ieeeAuthorPage"])}">IEEE author page</a>')]
    lis = "".join(f"<li><strong>{k}</strong>: {v}</li>" for k, v in rows if v)

    body = f"""
<h1>Contact</h1>
<p class="standfirst">Open to research and code collaboration on autonomous exploration, robust
SLAM, spatial perception, and edge deployment. Available from
{e(humandate(SITE['contact']['availableFrom']))}.</p>
<ul class="limits">{lis}</ul>
<div class="note">
  <span class="note-label">Note</span>
  <p>Please use the address above rather than any university address. The University of Twente
     address stops working after 1 August 2026.</p>
</div>
"""
    shell("contact", f"{NAME} | Contact",
          "Contact Bavantha Udugama, robotics perception researcher, for collaboration on SLAM, "
          "spatial perception, and edge deployment.",
          body, extra_ld=[person_node()], crumb="Contact")


def build_404():
    body = """
<h1>Page not found</h1>
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

def build_sitemap():
    urls = ""
    for p in sorted(PAGES):
        loc = f"{ORIGIN}/" if p == "" else f"{ORIGIN}/{p}/"
        pri = "1.0" if p == "" else ("0.8" if p.count("/") == 0 else "0.6")
        urls += (f"  <url><loc>{loc}</loc><lastmod>{git_lastmod(p)}</lastmod>"
                 f"<priority>{pri}</priority></url>\n")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")

    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n")

    (ROOT / "humans.txt").write_text(f"""/* TEAM */
Name: {NAME}
Publishes as: {PUBNAME}
Role: {SITE['identity']['role']}, {SITE['identity']['affiliation']['name']}
Contact: {SITE['contact'].get('email') or 'see /contact/'}
Scholar: {SITE['links']['googleScholar']}
GitHub: {SITE['links']['github']}

/* SITE */
Standards: HTML5, CSS3
Components: none. Hand-written, no framework, no runtime dependency.
Built: {TODAY}
Source of truth: data/*.json, rendered by tools/build.py
""")


def build_favicon():
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="4" fill="#14181F"/>'
        '<circle cx="9" cy="10" r="2.6" fill="#4FB3AC"/>'
        '<circle cx="23" cy="8" r="2.6" fill="#4FB3AC"/>'
        '<circle cx="16" cy="22" r="2.6" fill="#E0AC3B"/>'
        '<path d="M9 10 L23 8 M9 10 L16 22 M23 8 L16 22" stroke="#4FB3AC" '
        'stroke-width="1.4" fill="none" opacity="0.75"/>'
        "</svg>\n")


def main():
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
    build_cv()
    build_contact()
    build_404()
    build_sitemap()
    print(f"built {len(PAGES)} pages + sitemap.xml, robots.txt, humans.txt, 404.html")
    for p in sorted(PAGES):
        print("  /" + (p + "/" if p else ""))


if __name__ == "__main__":
    main()
