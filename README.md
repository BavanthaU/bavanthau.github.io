# bavanthau.github.io

Personal research site for Bavantha Udugama. Hand-written static HTML and CSS.
No framework, no npm, no runtime dependency, no external requests.

## Preview locally

    python3 tools/serve.py 8000
    # open http://localhost:8000

`python3 -m http.server` also works for reading, but it ignores Range requests, so video
seeking is broken under it: chapter links and `#t=` deep links on the watch pages snap back to
the start. `tools/serve.py` answers ranges the way GitHub Pages does.

## How to change anything

All content lives in `data/*.json`. The HTML is generated from it, so edit the JSON and
re-render, never edit an `index.html` by hand (it will be overwritten):

    python3 tools/build.py

For homepage-only content or design changes, preserve all other generated pages with:

    python3 tools/build.py --home-only

Page stylesheets load after `assets/site.css`: `assets/portfolio.css` on `/`,
`assets/projects.css` on `/projects/`, `assets/case.css` on the project detail pages.
`assets/fieldbook.css` loads last on every page and owns shared colours, typography,
controls and interior layouts.
The homepage fieldbook is generated from `data/site.json` → `home.portfolio`.
It presents doctoral mapping and autonomous exploration, industrial humanoids, and the
bachelor’s robot as three visual project tiles. The preferred perception–mapping–exploration
feedback diagram is driven by `home.portfolio.expertiseLoop`. Technical deep-dive tiles
link to the detailed pipeline, learned perception, and ATLAS pages. The homepage includes inline demos for each category, with mapping/exploration tabs in
the doctoral tile. Videos autoplay muted when visible; native controls remain usable without
JavaScript. Technical explanations remain on the subpages.
`assets/home.css` and `assets/stage.js` retain the previous homepage design but are no
longer loaded on `/`.

For the Projects overview, edit `data/projects.json` → `overview`, then run:

    python3 tools/build.py --projects-only

This updates `/projects/` only. Its styles live in `assets/projects.css`; existing project
detail pages and their URLs are preserved.

Python 3 standard library only. No install step.

| File | Holds |
| --- | --- |
| `data/site.json` | identity, links, the arc, the deployment block, the progression table |
| `data/publications.json` | one entry per paper: claim, context, contribution, results, limitations |
| `data/projects.json` | one entry per system, with repositories and media |
| `data/timeline.json` | CV timeline and teaching |
| `data/videos.json` | one entry per clip that gets its own watch page at `/videos/<slug>/` |

## Technical illustrations and site validation

`data/graphics.json` holds the conceptual system sketches and the guided Mono-Hydra++
explanation. Six manuscript/thesis illustrations have responsive AVIF, WebP and JPEG
renditions in `media/images/`. Their captions distinguish illustration from experimental
output; source filenames and credits live in `data/media.json` and `media/MANIFEST.json`.
Original files are archived under ignored `_source/media/web-explainers/`. The Overleaf
projects are read-only sources and are not modified by the website build.

After a site-wide change:

    python3 tools/build.py
    python3 tools/check_site.py
    node tools/tests/media_playback.cjs

The checker validates every generated page's local links, media, anchors, markup nesting,
heading count, shared stylesheet, image alt text/dimensions and structured data. It does
not replace browser layout/accessibility testing or verify external URLs.

## How to add a publication

1. Add an entry to `data/publications.json`. Required: `slug`, `title`, `authors`, `venue`,
   `year`, `status`, `links`, `rights`, `claim`, `context`, `contribution`, `headline`
   (3 items, each with its exact conditions), `limitations` (at least 3).
2. Add a BibTeX block to the `BIBTEX` dict in `tools/build.py`, keyed by the same slug.
3. Run `python3 tools/build.py`.
4. Commit and push. GitHub Pages serves `main` at the domain root.

A page appears at `/publications/<slug>/`, the sitemap picks it up, and the publications
list and home page cards update themselves.

## How to add a watch page for a clip

Google only considers a video for video results, Video mode and key moments if some page exists
whose main purpose is watching it. `/videos/<slug>/` is that page.

1. Add an entry to `data/videos.json`. Required: `key` (the media key in `data/media.json`),
   `slug`, `title`, `metaTitle`, `description`, `standfirst`, `stageHead`, `stageFoot`,
   `sections`, `specs`. Optional: `chapters`, `paper`, `resultIds`, `project`, `related`.
2. Chapters are key moments, and each one has to be checked against the footage before it is
   written down:

       ffmpeg -ss 16 -i media/video/<clip>.mp4 -frames:v 1 /tmp/at16.jpg

3. Run `python3 tools/og.py` for the social card, then `python3 tools/build.py`.

The page, its `VideoObject` with chapters, its breadcrumb and its sitemap entry follow. Every other
page that embeds the clip picks up a link to it, and points its markup at it rather than declaring
a competing copy.

## Rules this site holds itself to

- **Every number is traceable.** No figure appears unless it exists in the thesis
  `results_registry.csv` with a source location. `publications.json` carries a `registryId`
  against each headline result so this is checkable.
- **Status is stated exactly.** Work under review is labelled under review, never published.
- **Conditions travel with numbers.** A result never appears without its resolution, hardware,
  and dataset.
- **No PDFs are hosted.** Everything links to the DOI, arXiv, or the code. This keeps the site
  clear of IEEE and Elsevier hosting rules.
- **Limitations are mandatory** on every publication page.
- **All content is in the served HTML.** Nothing that matters for search is added by JavaScript.
  A small progressive-enhancement script handles media controls, comparison sliders, and the
  explicit light/dark theme choice; the site remains readable and navigable without it.

## Not deployed

`_source/` holds the papers, raw media, and CV that the site is built from. It is gitignored
and never published. `_source/AUDIT.md` records what exists, what is missing, and every
conflict between sources. `_source/DECISIONS.md` records how each was resolved.

## Current state

Responsive media, local video posters, per-page OpenGraph cards, structured data, and the complete
visual system are implemented. See `HANDOVER.md` for remaining factual and off-site launch items.
