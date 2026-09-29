# Design system

## Homepage tile layout

The landing page now uses rounded, separated tiles with short summaries, consistent padding
and clear navigation. Reading order: introduction and muted ITC mapping video; three engineering
project tiles; the perception–mapping–exploration feedback diagram; technical deep dives;
experience and contact. Long-form case details remain on their dedicated pages.

Doctoral work covers both mapping and autonomous exploration. Its tile shows map output and
simulation exploration together, labels the simulation, and links to the full thesis project
group. The feedback loop follows the author's preferred dark diagram, with real HTML text,
linked stages and a vertical layout on phones. The delivery row distinguishes onboard drone
software from commercial humanoid deployment. No unsupported end-to-end autonomy result is
implied. Inline category videos sit outside project navigation links. The doctoral tile switches
between mapping and exploration clips; humanoid and reconnaissance tiles each have their
own player. The hero and category videos autoplay muted while visible, with native controls
and explicit pause buttons. Manual pauses survive scrolling. Reduced-motion preferences
disable automatic playback, and background tabs pause playback.

## Shared fieldbook — all routes

The homepage theme is now shared by projects, research, publications, BibTeX, CV, contact,
video pages and the 404 page. `assets/fieldbook.css` owns the palette and common type/control
styles, loading after the original structural and route styles. `assets/portfolio.css`
contains homepage compositions only. Avoid duplicating palette tokens in route files.

Headlines name engineering work: perception, SLAM, navigation, hardware integration and
onboard deployment. Avoid generic slogans such as “works in the world”. The landing page
uses short role/outcome summaries, three evidence clips and a clearly labelled illustration
of the custom drone. Technical mechanisms, numeric conditions and additional demos belong
on the relevant subpages.

`data/graphics.json` and shared SVG symbols provide small conceptual system sketches.
Manuscript figures explain the actual Mono-Hydra++ pipeline, temporal alignment, sparse
depth selection and factor geometry. Thesis artwork explains the aerial platform and the
scene-graph hierarchy. These illustrations are explicitly labelled; they are not presented
as experimental outputs. Real hardware photographs, footage and reconstruction figures
remain available. Diagram links open larger renditions without JavaScript.

Only responsive website derivatives and metadata are published. Raw source files stay in
ignored `_source/`; manuscript and thesis workspaces are unchanged. Existing numbers,
publication statuses, citations and routes are preserved.

## Homepage fieldbook — September 2026

The homepage now leads with engineering delivery. Its three case studies are the doctoral
onboard mapping stack, commercial humanoid deployments, and the bachelor’s reconnaissance
robot. Each identifies the personal role, delivered work, evidence and demonstrated skills.
Research system names and publication statuses follow those concrete examples.

The visual composition pairs oversized sans-serif type and a serif headline accent with a
navy hardware plate, cobalt links, rust section numbers and custom vector skill illustrations.
Actual drone photography and deployment footage remain the evidence. The illustrations are
conceptual skill symbols, not synthetic results. Layout stacks on narrow screens, respects
light/dark preferences, and exposes native video controls and disclosure elements without JS.
Video is loaded on request; the homepage no longer uses the scroll-driven stage.

Homepage content: `data/site.json` → `home.portfolio`; renderer: `build_home()` in
`tools/build.py`; styles: `assets/portfolio.css`. Run `python3 tools/build.py --home-only`.

The design notes below are historical context. The shared fieldbook rules above supersede
their palette, typography, controls and page-opening rules; existing media interactions and
evidence constraints continue to apply.

## The idea

The site is designed outward from the work rather than into a portfolio template. Its visual
material is the actual output of the systems — camera frames, predicted depth and semantics,
estimated trajectories, meshes, scene graphs, deployment footage — and the interface exists to
frame and annotate that output at the size it deserves.

Three rules follow from that:

1. **Evidence is the decoration.** Every image on the site is a paper figure, a prediction, or
   real footage. Nothing is illustrative and nothing is generated.
2. **The interface may frame evidence; it must not invent a result.** Frames keep their own
   proportions rather than being cropped into a shared card ratio.
3. **Numbers travel with their conditions.** A figure never appears without its dataset,
   resolution and hardware.

## Grounds

The page has two grounds, and the change between them is how the reading is paced.

- **Paper** — the light or dark page ground, for reading. Prose sits in a measure; evidence
  breaks out of it.
- **Instrument** (`.ground-dark`) — a near-black full-bleed band for anything that is system
  output or a measured claim. It keeps its own colours in both themes, because perception
  output was authored on black. Used for the hero, the pixels-to-map sequence, the origin
  chapter, the platform band, case-study openings and the outro.

`.bleed` takes a block out of the reading column to the full viewport; `.bleed-wide` and
`.bleed-inner` put content back inside it at two widths.

## The signature sequence

`/` carries one interaction, the pixels-to-map stage: five representations of the same
problem — RGB, predicted depth, predicted semantics, estimated trajectory, scene graph —
with a note for each.

The three perception stages show an indoor and an outdoor frame side by side, from the same
network, because one network covering both domains is the claim being made. The two panes
grow in proportion to their own aspect ratios, so a 2.57:1 street frame and a 1.34:1 room
frame end up the same height with neither cropped to suit the other. Frames on the
instrument ground are exempt from the dark-mode image filter: that ground is dark in both
themes, and the same predicted depth must not render two different ways.

It ships as a plain numbered sequence of frame and explanation. That is the fallback and it is
complete on its own. `assets/stage.js` upgrades it to a sticky stage driven by the notes beside
it, and only where there is room (≥ 58em) and the reader has not asked for reduced motion.
Scrolling is native; nothing is hijacked; no understanding depends on the motion.

## No cards

A card is used only where the thing genuinely is a discrete object you could pick up — a link
to another clip, for instance. Everything else is built from rules, scale and space:

- `.index` / `.index-row` — the editorial index that replaced card grids for selected work,
  code and papers;
- `.chapter-head` — a hairline, a mono index line, a title and a lede;
- `.readout` — a measurement set as the composition, with its label and conditions beneath;
- `.entry-feature` / `.entry-split` / `.entry-flip` — the three project-index compositions,
  chosen per project by the proportions of its own media.

## Palette

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--paper` | `#EEF3F2` | `#071113` | page ground |
| `--surface` | `#F9FBFA` | `#0D1A1D` | evidence and text surfaces |
| `--ink` | `#0B1719` | `#E9F1F0` | primary text |
| `--ink-2` | `#506064` | `#A6B5B7` | supporting text and conditions |
| `--accent` | `#006F6B` | `#5AD1CA` | navigation, hierarchy, links |
| `--signal` | `#945500` | `#FFBD4A` | embedded Jetson operating point only |
| `--rule` | `#C6D1CF` | `#263639` | structure and measurement grid |
| `--stage` | `#071113` | `#040B0D` | the instrument ground |

Colour beyond this comes from the media itself — semantic class colours, depth ramps,
trajectory overlays. The interface around it stays disciplined.

## Type

No web fonts are requested; the site still makes no external request. Display type uses the
narrowest available system sans, body copy the system UI stack, and every measurement, label
and condition the system monospace stack with tabular numerals.

Scale is tokenised and fluid, so a heading fills the measure it was composed against at any
width: `--t-display` (hero only), `--t-h1`, `--t-h2`, `--t-h3`, `--t-lede`, `--t-body`,
`--t-sm`, `--t-mono`, `--t-micro`. Vertical rhythm comes from `--chapter` and
`--chapter-tight` so pacing is tuned in one place.

## Layout

- The shell is capped at 82rem; long-form pages (`research`, `publications`, `contact`) narrow
  to 68rem so prose reads in a column.
- Media is allowed to dominate. The hero clip, case-study openings and the platform band run
  edge to edge; the signature stage takes roughly two thirds of the viewport.
- Project entries do not share one component. Each uses the composition its own output asks
  for, declared as `layout` in `data/projects.json`.
- Every page remains usable at 320px, and no page scrolls horizontally. Wide diagrams scroll
  inside their own container, with the clipped edge marked.
- A measured claim is made beside the output that produced it, not as a chart of itself. The
  home page states the mapping error in the rail under the clip of the system running; the
  full progression, with the conditions for every row, is the table on the research page.

## Motion and interaction

The masthead joins the hero's dark ground and hands itself back at the top of the page. The
signature stage crossfades between representations and plays a clip only while its step is
showing. Hover transitions are limited to navigation and action
affordances.

Under `prefers-reduced-motion: reduce` the stage stays a static sequence, all motion is
removed, and videos do not autoplay.

## Constraints preserved

- no CDN or third-party page-load request, no framework, no npm;
- no stock imagery, generated imagery, icon library, skill meters, or invented charts;
- content and navigation remain available without JavaScript;
- visible keyboard focus and logical source order; one `h1` per page;
- the YouTube facade uses a local poster and contacts YouTube only after activation.
