#!/usr/bin/env python3
"""Generate 1200x630 OpenGraph cards, one per page.

    python3 tools/og.py

Cards carry the canonical name, the page subject, and where it was published, in the site
palette. Pages that have a figure get a cropped band of it down the right side. Output goes to
media/og/<slug>.png and is referenced by tools/build.py.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media" / "og"
SITE = json.loads((ROOT / "data" / "site.json").read_text())
PUBS = json.loads((ROOT / "data" / "publications.json").read_text())
PROJECTS = json.loads((ROOT / "data" / "projects.json").read_text())
_mf = ROOT / "media" / "MANIFEST.json"
MEDIA = json.loads(_mf.read_text()) if _mf.exists() else {"images": {}, "videos": {}}

W, H = 1200, 630
PAPER, INK, INK2 = "#EDEFF2", "#14181F", "#5A6472"
ACCENT, SIGNAL, RULE = "#1F6F6B", "#C8951C", "#C9CFD8"

F = "/usr/share/fonts/truetype/croscore/"
D = "/usr/share/fonts/truetype/dejavu/"
bold = lambda s: ImageFont.truetype(F + "Arimo-Bold.ttf", s)
reg = lambda s: ImageFont.truetype(F + "Arimo-Regular.ttf", s)
mono = lambda s: ImageFont.truetype(D + "DejaVuSansMono.ttf", s)


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(slug, kicker, title, meta, figure_key=None, accent=ACCENT):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)

    text_w = 700
    if figure_key:
        rec = MEDIA["images"].get(figure_key) or MEDIA["videos"].get(figure_key)
        path = None
        if rec:
            path = rec["sources"]["jpg"][-1]["path"] if "sources" in rec else rec.get("poster")
        if path:
            fig = Image.open(ROOT / path.lstrip("/")).convert("RGB")
            band_w = W - text_w - 60
            ratio = max(band_w / fig.width, H / fig.height)
            fig = fig.resize((round(fig.width * ratio), round(fig.height * ratio)), Image.LANCZOS)
            left = (fig.width - band_w) // 2
            top = (fig.height - H) // 2
            im.paste(fig.crop((left, top, left + band_w, top + H)), (text_w + 60, 0))
            d.line([(text_w + 60, 0), (text_w + 60, H)], fill=RULE, width=2)
    else:
        text_w = 1040

    x, y = 72, 74
    d.line([(x, y), (x + 54, y)], fill=accent, width=4)
    y += 26
    d.text((x, y), kicker.upper(), font=mono(19), fill=accent)
    y += 46

    for line in wrap(d, title, bold(48), text_w - 100)[:4]:
        d.text((x, y), line, font=bold(48), fill=INK)
        y += 60

    y += 14
    for line in wrap(d, meta, reg(24), text_w - 100)[:3]:
        d.text((x, y), line, font=reg(24), fill=INK2)
        y += 34

    d.text((x, H - 96), SITE["identity"]["canonicalName"], font=bold(26), fill=INK)
    d.text((x, H - 60), "bavanthau.github.io", font=mono(19), fill=INK2)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{slug}.png"
    im.save(p, optimize=True)
    return p


def main():
    made = []
    made.append(card("home", "PhD candidate, ITC University of Twente",
                     "Monocular spatial perception for robots that move",
                     "3D scene graphs from a single camera and IMU. 0.19 m to 0.08 m mean mapping "
                     "error across four system generations.",
                     "scene-graph-itc"))

    made.append(card("research", "Research",
                     "Structuring the seen, exploring the unseen",
                     "Building hierarchical metric-semantic scene graphs from one camera, then "
                     "learning to choose where to look next.",
                     "perception-pipeline"))

    figs = {"mono-hydra-plus": "scene-graph-itc", "m2h-mx": "m2h-mx-architecture",
            "m2h": "wipe-semantics", "mono-hydra": "scenegraph-system-design"}
    for p in PUBS["publications"]:
        key = figs.get(p["slug"])
        if key and key not in MEDIA["images"]:
            key = None
        made.append(card(f"pub-{p['slug']}", p["venueShort"], p["title"], p["claim"], key,
                         accent=SIGNAL if p["status"] == "under review" else ACCENT))

    made.append(card("publications", "Publications",
                     "Peer-reviewed work on monocular 3D scene graphs",
                     "Mono-Hydra, M2H, M2H-MX, and Mono-Hydra++. Published as U.V.B.L. Udugama."))

    pfigs = {"mono-hydra-plus": "scene-graph-itc", "m2h-mx": "m2h-mx-architecture",
             "m2h": "wipe-depth", "mono-hydra": "scenegraph-system-design",
             "learned-exploration": None}
    for pr in PROJECTS["projects"]:
        key = pfigs.get(pr["slug"])
        if key and key not in MEDIA["images"] and key not in MEDIA.get("frames", {}):
            key = None
        made.append(card(f"proj-{pr['slug']}", pr["partLabel"], pr["name"], pr["oneLine"], key,
                         accent=SIGNAL if pr["status"] == "in progress" else ACCENT))

    made.append(card("projects", "Projects", "Systems and open-source code",
                     "Mono-Hydra, M2H, M2H-MX, Mono-Hydra++, and ongoing exploration work."))
    made.append(card("cv", "Curriculum vitae", "Bavantha Udugama",
                     "Robotics perception engineer and PhD candidate. Available from August 2026."))
    made.append(card("contact", "Contact", "Get in touch",
                     "Collaboration on SLAM, spatial perception, and edge deployment."))

    total = sum(p.stat().st_size for p in made)
    print(f"wrote {len(made)} cards, {total/1024:.0f} KB total, into media/og/")


if __name__ == "__main__":
    main()
