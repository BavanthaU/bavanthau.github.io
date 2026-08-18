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
PAPER, SURFACE, INK, INK2 = "#071113", "#0D1A1D", "#E9F1F0", "#A6B5B7"
ACCENT, SIGNAL, RULE = "#5AD1CA", "#FFBD4A", "#263639"

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

    # The same sparse measurement grid used by the site, kept quiet enough for social crops.
    for gx in range(12, W, 24):
        for gy in range(12, H, 24):
            d.ellipse((gx, gy, gx + 1, gy + 1), fill="#183033")

    text_w = 700
    if figure_key:
        rec = MEDIA["images"].get(figure_key) or MEDIA["videos"].get(figure_key)
        path = None
        if rec:
            path = rec["sources"]["jpg"][-1]["path"] if "sources" in rec else rec.get("poster")
        if path:
            fig = Image.open(ROOT / path.lstrip("/")).convert("RGB")
            panel = (770, 54, 1148, 576)
            band_w, band_h = panel[2] - panel[0], panel[3] - panel[1]
            ratio = max(band_w / fig.width, band_h / fig.height)
            fig = fig.resize((round(fig.width * ratio), round(fig.height * ratio)), Image.LANCZOS)
            left = (fig.width - band_w) // 2
            top = (fig.height - band_h) // 2
            d.rounded_rectangle((panel[0] - 10, panel[1] - 10, panel[2] + 10, panel[3] + 10),
                                radius=18, fill=SURFACE, outline=RULE, width=2)
            im.paste(fig.crop((left, top, left + band_w, top + band_h)), (panel[0], panel[1]))
            d.rectangle(panel, outline=RULE, width=2)
            d.text((panel[0], panel[3] + 18), "RESEARCH SYSTEM OUTPUT", font=mono(13),
                   fill=INK2)
    else:
        text_w = 1040

    x, y = 72, 74
    d.ellipse((x, y + 5, x + 10, y + 15), fill=accent)
    d.ellipse((x - 5, y, x + 15, y + 20), outline="#1D5554", width=2)
    x_text = x + 28
    y += 2
    d.text((x_text, y), kicker.upper(), font=mono(18), fill=accent)
    y += 46

    for line in wrap(d, title, bold(49), text_w - 100)[:4]:
        d.text((x, y), line, font=bold(49), fill=INK)
        y += 59

    y += 14
    for line in wrap(d, meta, reg(24), text_w - 100)[:3]:
        d.text((x, y), line, font=reg(24), fill=INK2)
        y += 34

    d.rectangle((x, H - 103, x + 38, H - 65), outline="#46595C", width=1)
    d.text((x + 7, H - 93), "BU", font=mono(13), fill=INK)
    d.text((x + 54, H - 105), SITE["identity"]["canonicalName"], font=bold(24), fill=INK)
    d.text((x + 54, H - 70), "bavanthau.github.io", font=mono(17), fill=INK2)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{slug}.png"
    im.save(p, optimize=True)
    return p


def main():
    made = []
    made.append(card("home", "PhD candidate, ITC University of Twente",
                     "One camera. A map robots can reason with.",
                     "Real-time hierarchical mapping from monocular RGB and an IMU, with no depth "
                     "sensor. 0.19 m to 0.08 m mean error across four generations.",
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
        made.append(card(f"pub-{p['slug']}", p["venueShort"], p["title"], p["claim"], key))

    made.append(card("publications", "Publications",
                     "Ten papers on mapping and exploration",
                     "Mono-Hydra, M2H, M2H-MX, Mono-Hydra++, three review preprints, and the "
                     "undergraduate work from Peradeniya."))

    pfigs = {"mono-hydra-plus": "scene-graph-itc", "m2h-mx": "m2h-mx-architecture",
             "m2h": "wipe-depth", "mono-hydra": "scenegraph-system-design",
             "learned-exploration": None}
    for pr in PROJECTS["projects"]:
        key = pfigs.get(pr["slug"])
        if key and key not in MEDIA["images"] and key not in MEDIA.get("frames", {}):
            key = None
        made.append(card(f"proj-{pr['slug']}", pr["partLabel"], pr["name"], pr["oneLine"], key))

    made.append(card("projects", "Projects", "Systems and open-source code",
                     "Mono-Hydra, M2H, M2H-MX, Mono-Hydra++, and ongoing exploration work."))
    made.append(card("cv", "Curriculum vitae", "Bavantha Udugama",
                     "Robotics perception engineer and PhD candidate. Available from August 2026."))
    made.append(card("contact", "Contact", "Bavantha Udugama",
                     "Available from August 2026. Open to work on SLAM, spatial perception, and "
                     "edge deployment."))

    total = sum(p.stat().st_size for p in made)
    print(f"wrote {len(made)} cards, {total/1024:.0f} KB total, into media/og/")


if __name__ == "__main__":
    main()
