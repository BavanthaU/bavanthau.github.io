# Design direction

Phase 2 output. Written before any CSS, as required.

## Where the vocabulary comes from

Not from "research portfolio" as a genre. From the artefacts of this specific work:

- **Depth fields.** Continuous grey gradients where value means distance. Cool, not warm.
- **Semantic label palettes.** Flat, saturated, categorical patches sitting on top of grey geometry. The
  contrast between a continuous grey field and a few flat saturated patches is the visual signature of every
  figure in these papers.
- **Measurement with conditions attached.** Every number in this record travels with its resolution, its
  hardware, and its table reference. That is not decoration, it is the discipline of the work, and the layout
  should make it structural.
- **The layered graph.** Mesh, objects, places, rooms, buildings. Five levels of abstraction over one space.

## Palette

Six values. Light is the default; dark is a full re-declaration, not an inversion.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--paper` | `#EDEFF2` | `#0E1116` | Page ground. Cool grey, the background of a point-cloud viewer |
| `--surface` | `#F7F8FA` | `#161B22` | Cards, table rows |
| `--ink` | `#14181F` | `#E6EAF0` | Body text |
| `--ink-2` | `#5A6472` | `#9AA5B4` | Metadata, conditions, captions |
| `--accent` | `#1F6F6B` | `#4FB3AC` | Deep teal. Links, the measured line in the plot, act markers |
| `--signal` | `#C8951C` | `#E0AC3B` | Amber. Reserved exclusively for the embedded and Jetson operating point |

`--rule: #C9CFD8` / `#2A313B` for hairlines and table borders.

The two accents are doing semantic work, not decoration. Teal marks the main measured progression. Amber marks
exactly one thing across the whole site: the embedded operating point. When a reader sees amber they should
learn to expect "this is the Jetson, and it is a different trade-off". Body text on `--paper` is 13.4:1, and
`--ink-2` is 5.1:1, both above the 4.5:1 floor.

## Typefaces, 3 roles

| Role | Stack | Used for |
| --- | --- | --- |
| Display | `"Inter Tight", "Helvetica Neue", Arial, sans-serif`, weight 620, tracking `-0.02em` | Page titles, section heads, the arc statement |
| Body | `"Inter", -apple-system, "Segoe UI", Roboto, sans-serif`, 400 to 500 | Prose |
| Utility | `ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace` | Every number, every condition string, table cells, captions, registry ids, venue lines |

The utility face is the load-bearing decision. **All numerals are monospace with `font-variant-numeric:
tabular-nums`, always.** A result and its conditions render as one unit: the value large in mono, the
conditions directly beneath it, smaller, in `--ink-2` mono. A number never appears without them. This is what
makes the site look like instrumentation rather than a portfolio, and it is honest to the source material.

Fonts are loaded from system stacks with no web font request, so first paint costs zero network. If Inter is
later self-hosted, it goes in `/vendor/fonts/` as a subset woff2 with `font-display: swap`, never from a CDN.

## Layout

Asymmetric. A wide reading column with a narrow right-hand rail that carries conditions, provenance, and
status. The rail is the lab-notebook margin: it is where the caveats live, permanently visible rather than
hidden in footnotes. Below 900px the rail collapses beneath its content block, in source order.

```
┌────────────────────────────────────────────────────────────────────────┐
│  Bavantha Udugama                    research  publications  projects  │
│  ──────────────────────────────────────────────────────────────────────│
│                                                                        │
│  MONOCULAR SPATIAL PERCEPTION                    ┌───────────────────┐ │
│  FOR ROBOTS THAT MOVE                            │ ON THE DRONE      │ │
│                                                  │                   │ │
│  A monocular camera, one that the field          │ 25.53 fps         │ │
│  assumed needed a depth sensor beside it,        │ 39.02 ms GPU      │ │
│  builds a hierarchical metric-semantic 3D        │ 256x192           │ │
│  scene graph in real time.                       │ Jetson Orin NX    │ │
│                                                  │ ................. │ │
│                                                  │ perception only;  │ │
│                                                  │ VIO, mapping and  │ │
│                                                  │ graph ran offboard│ │
│                                                  └───────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  THE DESCENT            ITC building, 2nd floor mean error       │  │
│  │                                                                  │  │
│  │  0.20m ┤●  Mono-Hydra 2023                                       │  │
│  │        │ ╲                                                       │  │
│  │  0.15m ┤  ╲                                    ◆ 0.22 embedded   │  │
│  │        │   ╲                                                     │  │
│  │  0.10m ┤    ●────●──── ●   M2H · MX-B · MX-L                     │  │
│  │        │                                                         │  │
│  │  0.05m ┤                                                         │  │
│  │        └──┬────┬────┬────┬───────────────────────────────────    │  │
│  │          2023 2025 2026 2026                                     │  │
│  │  Each point links to its paper. Hardware and resolution change   │  │
│  │  across points, so this is a progression, not an ablation.       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ACT I  Understanding space        ACT II  Learning to explore         │
│  ──────────────────────────        ─────────────────────[in progress]  │
└────────────────────────────────────────────────────────────────────────┘
```

## Signature element

**The descent.** An inline SVG plot of one measurement, mean mapping error on the ITC building 2nd floor,
across four system generations, where every point is a link to that paper's page and the embedded Jetson point
sits off the trend in amber to mark it as a different operating point rather than a regression.

It is the argument, the navigation, and the honesty caveat in one object, built from nothing but the numbers in
`results_registry.csv`. Boldness is spent here and nowhere else.

## Motion

One orchestrated moment. On first load the descent line draws left to right over 900 ms and the four points
land in sequence, 60 ms apart. Nothing else on the site animates except focus and hover state changes.

Under `prefers-reduced-motion: reduce` the plot renders complete and static at frame one, and any video loop
elsewhere on the site is replaced by its poster frame rather than autoplaying.

## Critique pass

Checked against the known defaults. Two items had to be revised.

| Default to avoid | Present? | Action |
| --- | --- | --- |
| Cream `#F4F1EA`, high-contrast serif, terracotta `#D97757` | No | Ground is cool grey `#EDEFF2`, not cream. No serif anywhere. Accents are teal and amber |
| Near-black with a single acid-green or vermilion accent | No | Light ground by default, two accents, neither acid |
| Broadsheet layout, hairline rules, zero radius, dense columns | **Partly, revised** | The first draft had the right rail as a hairline-ruled column at 1px `--rule` with zero radius and tight leading, which is broadsheet. Revised: the rail is a filled `--surface` block at 3px radius with generous internal padding, body leading raised to 1.65, and the reading column capped at 68 characters instead of running dense |
| Full-bleed gradient hero | No | Hero is flat `--paper` with type and one bordered rail |
| Generic 01/02/03 numbered sections | **Partly, revised** | The first draft numbered the four papers 01 to 04 on the publications list. A publication list is not a sequence, so the numbers are removed there. Act I and Act II keep their numbering because the arc genuinely is a sequence, which the pack allows |
| Floating glassmorphic cards | No | Cards are opaque `--surface` with a 1px `--rule` border, no blur, no shadow beyond a 1px bottom edge |
| Stock AI brain motif | No | The only illustration is a plot of real measurements |

Two further self-imposed rules, from the subject rather than the reject list:

- No stock robot or drone imagery. Every image on the site is a figure from the actual papers or a frame from
  actual footage.
- No progress bars, no skill meters, no percentage rings. The work has real metrics; inventing visual ones
  next to them would undermine them.

## Gate 2

| Criterion | Status |
| --- | --- |
| Design plan written to `DESIGN.md` | Pass |
| Critique pass documented | Pass, 7 items checked, 2 revised with the reason recorded |
| No item from the reject list present | Pass |
| Signature element named in one sentence | Pass, "the descent" |

**Gate 2 passes.**
