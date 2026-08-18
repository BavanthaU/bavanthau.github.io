# bavanthau.github.io

Personal research site for Bavantha Udugama. Hand-written static HTML and CSS.
No framework, no npm, no runtime dependency, no external requests.

## Preview locally

    python3 -m http.server 8000
    # open http://localhost:8000

## How to change anything

All content lives in `data/*.json`. The HTML is generated from it, so edit the JSON and
re-render, never edit an `index.html` by hand (it will be overwritten):

    python3 tools/build.py

Python 3 standard library only. No install step.

| File | Holds |
| --- | --- |
| `data/site.json` | identity, links, the arc, the deployment block, the progression table |
| `data/publications.json` | one entry per paper: claim, context, contribution, results, limitations |
| `data/projects.json` | one entry per system, with repositories and media |
| `data/timeline.json` | CV timeline and teaching |

## How to add a publication

1. Add an entry to `data/publications.json`. Required: `slug`, `title`, `authors`, `venue`,
   `year`, `status`, `links`, `rights`, `claim`, `context`, `contribution`, `headline`
   (3 items, each with its exact conditions), `limitations` (at least 3).
2. Add a BibTeX block to the `BIBTEX` dict in `tools/build.py`, keyed by the same slug.
3. Run `python3 tools/build.py`.
4. Commit and push. GitHub Pages serves `main` at the domain root.

A page appears at `/publications/<slug>/`, the sitemap picks it up, and the publications
list and home page cards update themselves.

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
