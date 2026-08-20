# Handover

Personal research site for Bavantha Udugama. Live at <https://bavanthau.github.io>.

This document is for whoever picks the work up next. It covers what exists, the rules the content
holds itself to, how to change things, and what is still open. The professional visual design pass
described at the end was completed in August 2026; `DESIGN.md` now documents the implemented system.

---

## 1. What this is

A static site, 17 pages, no framework and no runtime dependency. GitHub Pages serves plain files
that were never touched by a build step at request time. There is one small JavaScript file for
progressive enhancement, and the site is fully readable with it disabled.

| | |
| --- | --- |
| Repository | `BavanthaU/bavanthau.github.io`, branch `main`, Pages serves the root |
| Stack | Hand-written HTML and CSS, rendered from JSON by a Python script |
| Dependencies | Python 3 standard library, plus Pillow and pillow-heif for the media pipeline, plus ffmpeg. None of these ship to the browser |
| Size | About 65 MB, of which roughly 55 MB is processed media |
| Analytics | None. No cookies, no third-party requests except a YouTube facade that loads only on click |

### Pages

```
/                          hero, stats, intro, platform, Part I, Part II, selected work
/research/                 the long-form argument, the progression table
/publications/             10 publications in three groups
/publications/<slug>/      one page per PhD paper (4)
/publications/bibtex/      every BibTeX entry as plain text
/projects/                 list
/projects/<slug>/          one page per system (5)
/cv/                       timeline, newest first, with media on one entry
/contact/
404.html  sitemap.xml  robots.txt  humans.txt
```

---

## 2. How it is built

### The rule that matters

**Content lives in `data/*.json`. HTML is generated from it. Never hand-edit an `index.html`,
it will be overwritten.**

```bash
python3 tools/build.py      # render all pages from data/
python3 tools/media.py      # process source media into media/
python3 tools/og.py         # regenerate the 15 social cards
python3 -m http.server 8000 # preview
```

### Data files

| File | Holds |
| --- | --- |
| `data/site.json` | identity, links, `sameAs` targets, the arc, the stat strip, deployment claim, nav, verification tokens |
| `data/publications.json` | 4 peer-reviewed papers with full page specs, 3 review preprints, 4 earlier-work entries |
| `data/projects.json` | 5 systems, with repositories, method blocks, media assignments |
| `data/timeline.json` | CV timeline and teaching, optionally with attached media |
| `data/media.json` | every source asset, its alt text, caption, and processing settings |

### Generators

**`tools/build.py`** is the renderer. Roughly: helpers at the top (`picture`, `video`, `wipe`,
`gallery`, `switcher`, `youtube_facade`, `descent_svg`), then one `build_*` function per page type,
then `main()`. Page shells come from `shell()`, which handles `<head>`, JSON-LD, OpenGraph,
canonical URLs, breadcrumbs, and the nav.

**`tools/media.py`** reads `data/media.json` and writes `media/`, recording input hashes in
`media/MANIFEST.json` so reruns are idempotent. It:

- emits AVIF, WebP, and JPEG at three widths, never upscaling past the source
- decodes HEIC through pillow-heif, assembling the full tile grid
- tonemaps HLG and PQ video to SDR (`tonemap=hable`), needed for all iPhone footage here
- writes H.264 MP4 with faststart plus a VP9 WebM, **dropping the WebM when it is not at least
  15 percent smaller**, which is usually the case except on rviz screen recordings
- takes posters from a chosen frame, never frame zero, capped at 1200 px
- normalises frame sets to identical dimensions so crossfades do not jitter
- refreshes alt text and captions on every run without re-encoding

**`tools/og.py`** draws 1200x630 social cards from the palette, one per page.

### Components

| Component | Behaviour without JavaScript |
| --- | --- |
| `picture()` | responsive `<picture>`, explicit width and height |
| `video()` | poster shows, autoplay only when 40 percent visible and never under reduced motion, keyboard pause control, click-to-load gate above 8 MB |
| `wipe()` | three aligned frames side by side; JavaScript adds a blend slider |
| `gallery()` | one lead image with the other angles stacked beside it |
| `switcher()` | all panels stack; JavaScript adds a segmented control. **Currently unused, see 5.3** |
| `youtube_facade()` | poster and button; injects `youtube-nocookie` only on click |

---

## 3. Rules the content holds itself to

These came out of the original brief and several rounds of correction. Breaking them silently would
be worse than not shipping.

1. **Every number is traceable.** No figure appears unless it exists in `results_registry.csv` in
   the thesis repository, with a source location. `publications.json` carries a `registryId` against
   each headline result.
2. **Conditions travel with numbers.** A result never appears without its resolution, hardware, and
   dataset. This is why results render as value, then what, then conditions.
3. **Status is stated exactly.** Work under review says under review. Preprints say not peer
   reviewed. Work in progress says no results exist.
4. **Limitations are mandatory** on every publication page, minimum three.
5. **No PDFs are hosted.** Everything links to DOI, arXiv, or code. This keeps the site clear of
   IEEE and Elsevier rules and means no accepted-manuscript or watermarked copy can leak.
6. **No em-dashes.** Commas, colons, full stops.
7. **No process notes in reader-facing text.** No "coming soon", no "media pending", no explaining
   why something is absent. If it is not ready, it does not appear.
8. **Describe, do not editorialise.** State what a table shows. Do not tell the reader which number
   is interesting, do not personify a paper or an ablation, do not instruct them where to look.
   This was the single most common failure in the first drafts.
9. **All content in the served HTML.** Nothing that matters for search is added by JavaScript.

`_source/AUDIT.md` records every source, every gap, and every conflict found between sources.
`_source/DECISIONS.md` records how each conflict was resolved and by whom. `_source/` is gitignored
and never deployed. **Read both before changing any factual claim.**

---

## 4. Search visibility

`LAUNCH_CHECKLIST.md` is the full list. State as of handover:

**Done on the site.** `Person` node with 6 name variants in `alternateName` and a 5-entry `sameAs`;
`ProfilePage`, `ScholarlyArticle` per paper, `SoftwareSourceCode` per project, `VideoObject`,
`BreadcrumbList` on all pages; unique titles and descriptions within display length; one `h1` per
page; absolute canonicals; `rel="me"`; sitemap with git-derived `lastmod`; robots; humans.txt;
BibTeX endpoint; social cards; Google Search Console verified.

**Not done, and worth more than anything above.** The site has almost no inbound links. The
highest-value actions are all off-site and need the site owner: point the Google Scholar homepage
field at the site and get the UT and UAV Centre pages to link it. The ORCID is now done.

**Name fragmentation is the underlying problem.** Papers are published as *U.V.B.L. Udugama*,
profiles say *Bavantha Udugama*, university pages say *B.L.U. Udugama Vithanage*. The site declares
all variants, but only the upstream pages can actually merge them.

---

## 5. Open items

### 5.1 Factual, needs the site owner

- **The onboard rate.** The stat strip and the CV say perception, odometry, mapping, and scene graph
  construction all run on the drone, on the owner's confirmation. The number shown, 25.53 fps, is
  the *perception* figure from the journal manuscript, because no measured end-to-end figure exists.
  Replace it when one does. `site.json` → `deployment`.
- **Two missing DOIs.** Mono-Hydra in ISPRS Annals, M2H on IEEE Xplore.
- **IEEE author id.** The previously listed id belonged to a co-author and was removed. A wrong
  `sameAs` asserts two researchers are one person, which is worse than an absent one. Needs a
  signed-in Xplore session. Check also whether Xplore has split the record across several ids.
- **ORCID.** `0000-0002-1932-692X`, added 2026-08-20. Checksum verified and resolved against
  pub.orcid.org before it went in. Leads `sameAs`; the record links back to this site.

### 5.2 Content gaps

- No public CV PDF. The private one carries a phone number and home town.
- Part II has no results by design, and its only footage is a simulator screen recording. Footage
  showing the topological graph or branch memory would land the idea far better.

### 5.3 Known code state

- `switcher()` exists, is tested, and is **currently unused**. Media was moved out of tabs because
  tabbed content does not get clicked. Keep the function or delete it, but do not reintroduce tabs
  for primary content.
- The repository is 65 MB and grows with each video. The largest single file is an 11.7 MB H.264
  fallback whose VP9 sibling is 3 MB. If this becomes a problem, lower `maxWidth` in
  `data/media.json` rather than re-encoding by hand.
- `tools/media.py` gates on the *smallest* rendition a browser could pick, not the sum.

---

## 6. Original brief: the professional design pass

**Status: completed in August 2026.** The brief is retained below as the rationale for the pass.
The current tokens, components, interaction rules, and social-card design are in `DESIGN.md`.

The content, structure, and mechanics are settled. What the site does not yet have is a considered
visual identity. Current styling is deliberate but minimal, and was written to be replaced.

### What exists now

`assets/site.css`, hand-written, about 1,000 lines, no preprocessor. Design tokens are declared once
on `:root` and redefined for dark mode twice, under `prefers-color-scheme` and under
`[data-theme="dark"]`.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--paper` | `#EDEFF2` | `#0E1116` | page ground |
| `--surface` | `#F7F8FA` | `#161B22` | cards, rows |
| `--ink` | `#14181F` | `#E6EAF0` | body text |
| `--ink-2` | `#5A6472` | `#9AA5B4` | metadata, captions |
| `--accent` | `#1F6F6B` | `#4FB3AC` | links, measured values |
| `--signal` | `#C8951C` | `#E0AC3B` | **reserved: means Jetson or embedded, nothing else** |

Type is three roles: a display face for headings, a body face, and a monospace utility face for
every number, condition string, caption, and label. All numerals are monospace with tabular figures.
Fonts are system stacks, so first paint costs no network request.

### Constraints the design must keep

1. **Accessibility.** 4.5:1 minimum on body text, visible focus on every interactive element, skip
   link, logical tab order, `prefers-reduced-motion` fully honoured, works from 320 px up.
2. **Performance.** Home page critical path is currently 386 KB against a 1.5 MB budget.
   Media is lazy, video is `preload="none"`. If a web font is introduced, self-host it in
   `/vendor/`, subset it, and use `font-display: swap`. No CDN.
3. **No JavaScript for layout or content.** JavaScript may enhance; it may not be required to read
   or navigate anything.
4. **The signal colour stays semantic.** Amber means the embedded or Jetson operating point. Do not
   spend it on decoration.
5. **Numbers keep their conditions.** Any redesign of the results display must keep resolution and
   hardware attached to each value.
6. **No stock imagery, no icon sets, no progress bars or skill meters.** Every image on the site is
   a figure from a paper or a frame from real footage. The work has real metrics; inventing visual
   ones beside them undermines them.

### What is weak and worth attacking

- **The home page is long.** Five videos and six image blocks, none hidden, by explicit request.
  The opportunity is rhythm and pacing, not removal: better sectioning, stronger use of full-bleed
  versus contained media, clearer visual hierarchy between the personal introduction, the platform,
  and the two research parts.
- **The stat strip is plain.** Three figures on rules. It carries the headline claim and could do
  much more.
- **The descent plot** is a hand-drawn inline SVG and the one deliberately bold element. It is
  functional but unrefined.
- **Publication and project pages are dense text.** They read well but look uniform.
- **Dark mode was designed second.** It works, and figures are dimmed slightly to stop white paper
  backgrounds glaring, but it has not been given the same attention as light.
- **Vertical rhythm is inconsistent** where sections were added at different times.

### Audience, in priority order

Postdoc hosts and hiring managers in robotics and computer vision, then reviewers and fellow
researchers, then recruiters. The site's job in one sentence: someone lands here and understands
within 20 seconds that this person made a monocular camera do what the field assumed needed a depth
sensor, and got it running on a drone.

The tone to hold: precise, quietly confident, and unmistakably an engineer's page. Not a startup
landing page, not a design portfolio. Every claim on it is defensible, and the design should look
like it knows that.
