# Narrative and information architecture

Phase 1 output. Content lives in `data/*.json`; this file fixes the argument, the URL structure, and what
each page must contain.

## The argument

One sentence, what a visitor must understand in 20 seconds:

> This person made a monocular camera produce the hierarchical metric-semantic map the field assumed needed a
> depth sensor, measured it against LiDAR ground truth in a real building, and got the perception running on
> the drone's own compute.

The arc statement, 44 words, from `site.json`:

> A monocular camera, one that the field assumed needed a depth sensor beside it, builds a hierarchical
> metric-semantic 3D scene graph in real time. The next question is what a robot does with that structure
> when it has to decide where to look next.

### Act I, understanding space

Complete, four papers, one continuous measurement. The spine of the whole site is a single number measured the
same way across four system generations on the same building:

| | ITC 2nd floor mean error | Rate | Input | Hardware |
| --- | --- | --- | --- | --- |
| Mono-Hydra, 2023 | 0.19 m | 15 fps | 848x480 | RTX 3080 laptop |
| M2H, 2025 | 0.11 m | 30 fps | 224x224 | RTX 3080 laptop |
| M2H-MX-B, 2026 | 0.10 m | 25 to 30 Hz | 640x480 | RTX 4080 Super |
| M2H-MX-L, 2026 | 0.08 m | 25 to 30 Hz | 640x480 | RTX 4080 Super |
| M2H-MX-L embedded | 0.22 m | 25.53 fps | 256x192 | Jetson Orin NX 16GB |

Hardware and resolution change across the rows, so the caption must say this is a system progression and not a
controlled ablation. The embedded row is a different operating point, not a regression, and must be labelled
that way or it reads as the system getting worse.

The internal logic, which is what makes it an argument rather than a list:

1. **Mono-Hydra** proves the thing is possible, with two separate networks doing depth and semantics.
2. Two networks is a bad architecture: duplicated compute, two representations that disagree.
   **M2H** collapses them into one multi-task model, and the map improves as a side effect.
3. A better benchmark score is not a better map. **M2H-MX** tests the same model inside the running system and
   shows the trajectory error drops with it.
4. **Mono-Hydra++** closes the loop the other way, feeding predicted depth back into the estimator as metric
   anchors and using pose to stabilise the next prediction.

### Act II, learning to explore

In progress, no results. Presented as: the problem, the formulation, the design commitment. The commitment is
the memorable part and it is genuinely unusual:

> Certification creates, learning selects.

The learned layer sits between two deterministic layers and has no path to the actuators except by choosing an
option the planner has already certified as safe. It may re-order options and it may abstain. It may never
invent one.

Three constraints stated as consequences of the task, which is what gives the act intellectual content even
without results: options must be judged against each other so duplicates are not treated as alternatives;
actions must be temporally extended because passing through a doorway is locally expensive and locally
uninformative; and the agent needs persistent memory of unfinished work or it leaves regions half-explored
forever.

**Honesty requirements for this act, non-negotiable:**
- Label it work in progress everywhere it appears.
- State no result, because none exists.
- Do not imply the exploration agent consumes the Act I scene graph. It maintains its own topological memory
  over a 2D occupancy map from simulated depth and pose. Connecting the acts is future work.

### Prologue, `/research/` only, 2 sentences

> The same question was asked in 2016 and 2017 at Peradeniya, with a 2D laser range finder and a particle
> filter on a Raspberry Pi. It is being asked again 10 years later with a learned model and a single camera.

Stated once, plainly, not dressed up.

## URL structure

Every paper is an indexable page, never an anchor. Trailing slashes throughout, `index.html` in each directory.

```
/                                    hero, deployment evidence, the arc, selected work, recent
/research/                           the two-act story, long form, plus the prologue
/publications/                       list, four PhD papers plus earlier work as citation-only
/publications/mono-hydra-plus/       under review, ISPRS J. Photogramm. Remote Sens.
/publications/m2h-mx/                ICRA 2026 SRRA Workshop
/publications/m2h/                   IROS 2025
/publications/mono-hydra/            ISPRS Annals 2023
/publications/bibtex/                every BibTeX entry as plain text
/projects/                           list
/projects/mono-hydra-plus/           the current system, heavy media
/projects/m2h-mx/                    model and embedded deployment
/projects/m2h/                       the aligned-stream wipe lives here
/projects/mono-hydra/                where it started
/projects/learned-exploration/       Act II, labelled work in progress
/cv/                                 HTML CV plus PDF download
/contact/
/sitemap.xml  /robots.txt  /humans.txt
```

No `/papers/` directory. Decision Q2: the site hosts no PDFs and links to DOI, arXiv, and code instead.

No `/thesis/` page. Decision Q3: one line on `/research/`.

No `/notes/` or `/blog/`. Decision Q4.

Earlier work has no pages. Decision Q6: citation-only entries under a heading on `/publications/`.

## Page specification: publication pages

Each of the four gets, in this order:

1. **Plain-language claim**, 1 sentence. What a non-specialist would understand.
2. **Context**, 3 sentences. What the field assumed, why that was limiting, what this paper did instead.
3. **The honest contribution.** What is actually new, and where the gain really came from. For M2H-MX this
   means stating that the backbone drives the improvement more than the proposed decoder blocks, because the
   ablation says so.
4. **Headline results**, 3 of them, each with its exact conditions attached. Never a bare number.
5. **Limitations.** Mandatory, minimum 3. Where the paper states none, say that it states none rather than
   inventing one, then list the costs instead. This is what reads as confidence to reviewers and hosts.
6. **Links.** DOI, arXiv, code, video, BibTeX. Status stated exactly, so "Under review at ISPRS Journal of
   Photogrammetry and Remote Sensing" and never "published".

All of this is already populated in `data/publications.json`, per slug.

## Home page order

1. Name, role, one-line positioning.
2. **Deployment evidence, above the fold.** Perception on the drone's Jetson Orin NX 16GB: 25.53 fps,
   39.02 ms mean GPU compute, 256x192, ONNX with TensorRT FP16 and CUDA Graphs. With the scope line: VIO,
   mapping, and scene graph construction ran off-board. Sourced from `site.json.deployment`, which carries a
   `status` field so the block upgrades in place when the full-suite deployment lands in August 2026.
3. The arc, 44 words, both acts, Act II visibly marked in progress.
4. The progression table. This is the strongest single object on the site.
5. Selected work, four cards.
6. Recent.

## Provenance rule

No number reaches a page unless it exists in the thesis `results_registry.csv` with a source location.
`publications.json` carries a `registryId` against every headline figure so this is checkable by script, which
is what `tools/check/` will do in Phase 5.

## Gate 1

| Criterion | Status |
| --- | --- |
| All four data files validate as JSON | Pass, verified with `json.load` |
| Every publication has a unique slug | Pass, 4 unique slugs, no collision with the 5 project slugs |
| Every publication has a populated page spec | Pass, all 13 required fields present and non-empty on all 4, each with 3 headline results and 4 limitations |
| Home page states the two-act arc in under 60 words | Pass, 44 words |

Also verified: no em-dashes or en-dashes anywhere in the data files, and no dangling cross-references between
projects and publications.

**Gate 1 passes.**
