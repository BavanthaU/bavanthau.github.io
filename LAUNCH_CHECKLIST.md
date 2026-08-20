# Search visibility: what to do next

The on-page work is done. What remains is off-site, and it matters more than anything on the
pages. Search engines resolve a name to an entity, then rank the pages that entity owns. Markup
makes the site eligible. Links between profiles are what actually consolidate the entity.

Ordered by effect. The first three are worth more than everything below them combined.

---

## Do these first

### 1. Tell Google the site exists (15 minutes, do it today)

Nothing else works until this happens. The site has zero inbound links, so Google has no path to
discover it.

1. Go to [Google Search Console](https://search.google.com/search-console), add a property for
   `https://bavanthau.github.io`, and verify with the HTML-tag method. Paste the tag you are given
   into `SEARCH_CONSOLE_TAG` in `data/site.json`, then run `python3 tools/build.py` and push. The
   tag goes into the `<head>` of every page.
2. Submit `https://bavanthau.github.io/sitemap.xml`.
3. Use **URL Inspection** on the home page and click **Request indexing**. Do the same for
   `/publications/` and `/research/`.
4. Repeat at [Bing Webmaster Tools](https://www.bing.com/webmasters). Bing feeds DuckDuckGo and,
   increasingly, several AI assistants.

Expect nothing for one to two weeks. Indexing is not fast and is not controllable.

### 2. Point your five existing profiles at the site

Every one of these already ranks for your name. Right now each is a dead end. A link from each is
both a discovery path for the crawler and the strongest available signal that these accounts are
one person.

| Where | What to change |
| --- | --- |
| **Google Scholar** | Edit your profile, set the **Homepage** field to `https://bavanthau.github.io`. Highest value single link you own, because Scholar already ranks first for your name. |
| **LinkedIn** | Contact info, add the website. Also put it in your About section as plain text, since the contact-info link is `nofollow`. |
| **GitHub profile** | Set the website field on `github.com/BavanthaU`, and add the link to the top of your profile README. |
| **UT Pure page** | Personal website field on `research.utwente.nl`. A `.utwente.nl` link carries real institutional authority. |
| **ResearchGate** | Profile, add the site under your web links. |

### 3. Get an ORCID (done 2026-08-20)

`0000-0002-1932-692X`, set in `data/site.json` under `links.orcid`. It renders in the masthead,
the footer and the contact page, and leads the `sameAs` array on all 17 pages. The record already
lists this site under researcher-urls, so the link is reciprocal.

Remaining: add all four publications to the ORCID record itself. That is off-site work and cannot
be done from the repo.

---

## Then these

### 4. Fix the name fragmentation

Your record is split across five spellings, which splits one researcher into several weak
entities. The site declares all of them in `alternateName`, but only the upstream pages can
actually merge them.

- Every paper is published as **U.V.B.L. Udugama**.
- Scholar, LinkedIn, and GitHub say **Bavantha Udugama**.
- UT pages say **B.L.U. Udugama Vithanage** and **Bavantha Udugama Vithanage**.

Pick **Bavantha Udugama**, since it is already dominant on the three profiles that rank. Ask UT to
display it alongside the formal name on the Pure profile and the UAV Centre page. Keep the full
legal form on the thesis, where it belongs.

For future papers, consider publishing as **Bavantha Udugama** rather than the initialised form.
This is the single change that would do the most for the next five years, and only you can make it.

### 5. Clean up the YouTube channel

Your channel is `@udugamavithanagebavanthala6361`, an auto-generated handle. The display name is
already correct.

- Claim a clean handle, ideally `@bavanthaudugama`. It is already in the site's `sameAs` array, so
  update `data/site.json` when you change it.
- Edit the demo video: put the canonical name and the paper title in the video title, and put
  `https://bavanthau.github.io` plus the DOI in the first two lines of the description, above the
  fold. YouTube is a high-authority domain that ranks for names, so a video pointing back at the
  site is worth more than one sitting alone.

### 6. Find your real IEEE Xplore author id

The id previously listed here, `37061362800`, belongs to **Sachini Ekanayake**, a co-author on the
Peradeniya papers, not to you. It has been removed, because a wrong `sameAs` entry tells search
engines that two different researchers are the same person, which is worse than having no entry.

Sign in to IEEE Xplore, open one of your own papers (M2H at IROS 2025 is the surest), click your
name in the author list, and copy the id from the URL. Put the full URL into
`links.ieeeAuthorPage` in `data/site.json` and rebuild. It will rejoin the `sameAs` array on every
page. While you are there, check that IEEE has not split you across several author ids, which is
common with initialised names, and merge them if so.

### 7. Get the missing DOIs into the site

Two are absent, and DOIs are strong identifiers for the `ScholarlyArticle` markup:

- **Mono-Hydra**, from ISPRS Annals.
- **M2H**, from IEEE Xplore.

Add each to `identifiers.doi` and `links.doi` in `data/publications.json`, rebuild, push.

### 8. Ask for three links

A handful of relevant links from real sites beats any amount of on-page tuning.

- Francesco Nex and George Vosselman, to link from their staff pages or group pages.
- The ITC UAV Centre page maintainer, to add you to the people list with a link.
- The three co-authors on the Peradeniya paper, if any of them keep a site.

Also add the site link to the README of each code repository: `mono_hydra`, `M2H`, `m2h_mx`,
`mono-hydra-pp`, and `mono_hydra_vio`. GitHub repositories get crawled.

---

## Content that would help

### 9. Fill the two visual gaps

- **A portrait.** Goes into the `Person` JSON-LD `image` field, which Google uses when building a
  person panel. Set `identity.image` in `data/site.json`.
- **A photograph of the drone.** The deployment section is currently numbers with no machine
  behind it. This is the most persuasive missing asset on the site, for humans more than crawlers.

### 10. Publish a public CV PDF

`/cv/` has no download. The current CV carries a personal phone number and home town, so produce a
version with those removed and drop it in. PDFs get indexed and rank for name queries.

---

## What not to do

- **Do not buy links, use link exchanges, or post the URL across unrelated forums.** It does not
  work any more and it can demote the site.
- **Do not add hidden text, repeated name blocks, or keyword-stuffed footers.** Actively harmful.
- **Do not create duplicate profile pages** on aggregator sites hoping to rank twice. It splits the
  entity further, which is the exact problem you already have.
- **Do not check rankings daily.** Indexing takes weeks and the noise will mislead you. Check after
  four to six weeks, then monthly.

---

## What to expect

Nobody competes with you for "Bavantha Udugama", so rank 1 is realistic rather than hopeful. Every
result today is a third-party profile, and the site's job is to become the destination those
profiles point at.

With steps 1 to 3 done, **two to three months** is a reasonable expectation for rank 1 on the
canonical name. The timeline is not controllable, and anyone who promises one is guessing.

The variant spellings will take longer, and may never fully merge unless the upstream pages are
corrected. That is step 4, and it is the only part nobody else can do for you.

Searches for the paper titles should start working sooner, because there is little competition for
those exact phrases and the publication pages target them directly.

---

## Already done on the site

For reference, so you do not pay anyone to redo it:

- `Person` node with all six name variants in `alternateName` and a five-entry `sameAs` array,
  linking Scholar, GitHub, LinkedIn, the UT staff page, and YouTube. ORCID and the IEEE author page
  are pending, see steps 3 and 6.
- `ProfilePage`, `ScholarlyArticle` on each paper, `SoftwareSourceCode` on each project,
  `VideoObject` on the home page, and `BreadcrumbList` on all 16 pages.
- Unique title and meta description on every page, all descriptions within display length.
- One `<h1>` per page, absolute self-referencing canonical URLs, `rel="me"` on the profile links.
- `sitemap.xml` with git-derived `lastmod`, `robots.txt`, `humans.txt`, and a BibTeX endpoint.
- A 1200x630 OpenGraph card per page, so shared links render properly.
- Full text present in the served HTML, with no JavaScript required to read any of it.
- 97 KB critical path on the home page. Speed is a ranking factor and this is comfortably fast.
