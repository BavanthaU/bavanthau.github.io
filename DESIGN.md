# Design system

Current visual direction, implemented in August 2026.

## The idea

The site behaves like a spatial-perception instrument rather than a generic portfolio. Its visual
language comes from the work itself:

- the sparse grid of a point-cloud viewer;
- continuous depth fields and categorical semantic layers;
- measurements with their conditions attached;
- the scene graph hierarchy, mesh, objects, places, rooms, building;
- real system output as the primary visual evidence.

The homepage hero makes the argument in one screen: one camera produces a map a robot can reason
with, the system runs on the drone, and the claims below are measured operating points. The rest of
the page is paced as a sequence of research chapters rather than an undifferentiated media feed.

## Principles

1. Evidence is the decoration. Every image is a paper figure or real deployment footage.
2. The interface can frame and annotate evidence, but it must not invent a result.
3. Numbers always keep their dataset, resolution, and hardware conditions.
4. Amber is reserved for the embedded Jetson operating point. Status uses teal or neutral styling.
5. JavaScript enhances theme choice, video, and comparison controls. It is not needed for layout or
   content.
6. Dark and light modes are both first-class designs.

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

Body, supporting, and accent text exceed WCAG AA contrast against their page grounds. The light
signal colour is deliberately darker than the original amber so embedded table rows also meet the
4.5:1 text threshold.

## Type

No web fonts are requested. Display type uses the narrowest available system sans, body copy uses
the system UI stack, and all measurements, metadata, controls, and conditions use the system
monospace stack with tabular numerals.

The homepage pitch and page titles use large display type. Dense research metadata remains small
and monospaced, preserving the distinction between argument and provenance.

## Layout

- The shell is capped at 82 rem, with a sticky, translucent navigation bar.
- The hero is a two-column evidence composition above 52 rem and a single column below it.
- Homepage sections have a persistent chapter rail at desktop sizes and source-order labels on
  mobile.
- Media may break beyond the reading measure while prose remains constrained.
- Publication lists, result units, methods, and timelines use ruled structures instead of floating
  cards.
- Every page remains usable at 320 px. Primary navigation fits at that width and never requires a
  menu script.

## Motion and interaction

The descent plot draws once and its measured points land in sequence. Wipe comparisons use a short
linear blend. Hover transitions are limited to navigation and action affordances. Under
`prefers-reduced-motion: reduce`, all motion is effectively removed and videos do not autoplay.

Theme choice is stored locally. The inline theme bootstrap prevents a light-to-dark flash, while
the control itself remains progressive enhancement and is hidden without JavaScript.

## Social cards

`tools/og.py` mirrors the live visual system with the dark measurement grid, BU locator mark, teal
status point, and a framed crop of real research output. It never uses the amber signal colour for
review or work-in-progress status.

## Constraints preserved

- no CDN or third-party page-load request;
- no stock imagery, generated imagery, icon library, skill meters, or invented charts;
- visible keyboard focus and logical source order;
- one `h1` per page;
- content and navigation remain available without JavaScript;
- the YouTube facade uses a local poster and contacts YouTube only after activation.
