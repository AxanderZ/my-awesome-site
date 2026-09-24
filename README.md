# Encyclopedia Redesign

A UX class project that rebuilds Wikipedia's core reading experience (the homepage, the search flow, and a full article followed through to a related article), fixing its most severe usability problems and its WAVE accessibility errors.

**Live site:** https://axanderz.github.io/my-awesome-site/

## The task this redesign supports

> *"Find out how many championships the Golden State Warriors have won and who was Finals MVP in 2022, then learn how Stephen Curry's career began."*

Path: **Homepage** → **search** "golden state warriors" (autocomplete or results page) → **[Golden State Warriors](https://axanderz.github.io/my-awesome-site/wiki/Golden_State_Warriors.html)** → related-article link → **[Stephen Curry](https://axanderz.github.io/my-awesome-site/wiki/Stephen_Curry.html)**.

| Page | File |
|---|---|
| Homepage | `index.html` |
| Search results (live Wikipedia search) | `search.html` |
| Article | `wiki/Golden_State_Warriors.html` (all 17,457 words of the original) |
| Related article | `wiki/Stephen_Curry.html` (all 29,420 words of the original) |
| Error page | `404.html` |

## Heuristic violations resolved

| Heuristic (severity) | Problem on Wikipedia | Change in the redesign |
|---|---|---|
| **#8 Aesthetic and minimalist design (3)** | 17,500 words, about 40 screens, 2,795 links. Key facts are buried. | **Nothing is removed; it's reorganized.** "At a glance" stat cards and a fact list come first. "History in brief" gives a two-sentence summary per era, with a link to the full text. Every subsection is a collapsed panel showing its reading time, with "Expand all" per section. The reading column is capped at a comfortable width (46rem). Links use a quiet underline instead of loud blue, citations are small chips, and the 217 sources and the navigation boxes sit in collapsed panels. |
| **#6 Recognition rather than recall (2)** | Roster codes "(TW)" and a red ✚ are explained only in a separate legend. "Pos.", "DOB" and stat abbreviations are unexplained. | The roster legend sits **above** the table, and statuses are text badges ("Two-way contract", "Injured") next to each name. Columns are spelled out ("Jersey number", "Born"). Every table using abbreviations (GP, MPG, FG%…) gets a key above it. Citation previews show the source on hover or focus, so readers don't have to jump away and remember their place. |
| **#2 Match between system and the real world (2)** | "Talk", "View source", "View history", "v · t · e", unexplained padlock, mixed [a]/[1] markers. | Plain-language actions: **Discuss this article**, **See who edited it**, **Suggest a correction**. Protection is explained in a sentence. Navboxes become "Related topics" with no "v · t · e". "References" is renamed **Sources**, and "External links" is renamed **Elsewhere on the web**. Notes and sources are visually distinct and announced as "Note a" / "Source 12". |

The redesign keeps what Wikipedia already does well:
- **H1:** a contents list that highlights the current section, plus a reading progress bar.
- **H3 and H7:** reversible display settings for text size, width and theme.
- **H4:** a conventional header.
- **H5:** search suggestions.
- **H9:** "Showing results for … / Search instead for …" spelling correction, plus a clear error with a retry button if search is unreachable.

## Accessibility issues resolved

Baseline WAVE report for the original article: **AIM score 3.7**, with 25 errors, 93 contrast errors and 1,147 alerts.

| WAVE finding on Wikipedia | Fix |
|---|---|
| 4 missing alt text, 19 linked images missing alt | Every image has alt text. Descriptions come from Wikimedia Commons (95 characters max), and icons get `alt=""`. File links around images are removed. |
| 1 missing form label | Every search field has a `<label>`. |
| 1 empty link | Icon-only links (Wikidata edit pencils) are removed. |
| 93 very low contrast (team-color table headers, tinted navboxes) | Inline colors are stripped, and every text color pair measures at least 6.2:1 in light and dark themes. |
| 13 layout tables, 1 possible table caption | Layout tables become CSS layouts. Data tables get a `<caption>`, `<thead>` and `scope`, and empty header cells are removed. |
| 1,099 redundant title texts, 20 accesskeys, 8 redundant links | `title` attributes and access keys are removed, and the duplicate "Home" link is gone. |
| 3 missing fieldsets | Display options are grouped with `<fieldset>`/`<legend>`. |
| Bold paragraphs used as headings | Converted to real headings, so screen-reader heading navigation works. |

Also included: a skip link, landmarks, a sticky table of contents, visible focus rings, 24px minimum target size for citation markers (WCAG 2.2), an accessible combobox for search suggestions, sortable tables with `aria-sort` and a live announcement, and support for reduced motion and dark mode.

**Automated check** (`tools/check_pages.py`, axe-core 4.10 plus WAVE-style rules, light and dark themes): **0 errors, 0 contrast errors, 0 axe violations on every page.** The only alerts left are WAVE's "Link to PDF document" on citations whose original sources are PDFs: 2 on the Warriors page and 3 on the Curry page. Those source links are kept on purpose.

## How it's built

`tools/build.py` downloads the current articles from the Wikipedia API and turns them into the redesigned pages: cleanup, restructuring, accessibility fixes and image credits. It also snapshots today's featured content for the homepage. The generated HTML is committed, so the site is plain static files.

```bash
pip install -r tools/requirements.txt
```
```bash
python3 tools/build.py
```

To run the checks, serve the folder (`python3 -m http.server 8765`), then run `python3 tools/check_pages.py` (needs `pip install playwright` and Google Chrome).

## Credits and license

Article text and data come from Wikipedia and its contributors under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This project is shared under the same license. Images come from Wikimedia Commons and are credited on each page. The at-a-glance summaries and "History in brief" were written for this redesign. This is a student project, not affiliated with Wikipedia or the Wikimedia Foundation.
