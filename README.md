# Golden State Warriors: Wikipedia Article Redesign

A UX class project that rebuilds the Wikipedia article
[Golden State Warriors](https://en.wikipedia.org/wiki/Golden_State_Warriors) to fix its most severe
usability problems (found with Nielsen's 10 heuristics) and to raise its WAVE accessibility score.

Open `index.html` in a browser, or serve the folder with any static server:

```bash
python3 -m http.server 8765
```

The page is plain HTML, CSS and JavaScript with no build step. Everything works without JavaScript; scripts only add enhancements.

## Heuristic violations resolved

| Heuristic | Severity | Problem on Wikipedia | What the redesign does |
|---|---|---|---|
| #8 Aesthetic and minimalist design | 3 | About 17,500 words, 34,000 px of scrolling, 2,795 links and 217 citation markers. Key facts are buried. | An **At a glance** section (stat cards and a fact list) answers the common questions first. History is condensed into a 7-era **timeline**, each era a two-sentence summary with optional "More about this era" details. Paragraphs are capped at about 70 characters per line, and there are no inline link or citation clutter. |
| #6 Recognition rather than recall | 2 | Roster uses "(TW)", a red ✚ icon, and "Pos." / "DOB" codes, explained only in a legend in a separate column. | The legend sits **above** the table, and statuses appear as text badges ("Two-way contract", "Injured") beside each name. Column names are spelled out ("Jersey number", "Position", "Born"), and positions are written in full ("Forward / Center"). |
| #2 Match between system and the real world | 2 | Wiki jargon: "Talk", "View source", "View history", "v · t · e", an unexplained padlock, mixed [a]/[1] markers. | Plain-language actions: **Discuss this article**, **See who edited it**, **Suggest a correction**. Page protection is explained in a sentence, and a **Sources** section describes each source instead of using bracket numbers. |

The redesign keeps what Wikipedia already does well: a table of contents that highlights the current section (H1), reversible reading settings for text size and a light/dark theme (H3, H7), and conventional search and header placement (H4).

## Accessibility issues resolved (WAVE baseline: AIM score 3.7/10)

| WAVE finding on Wikipedia | Fix in this redesign |
|---|---|
| 23 missing or linked-image missing alt text | The one content image has descriptive alt text. Decorative SVGs use `aria-hidden="true"`. |
| 1 missing form label | Search has a visible `<label for="search-input">`. |
| 1 empty link | Every link has text. |
| 93 very-low-contrast errors (blue links on tinted navboxes, about 3.5:1) | Color tokens tested at **7.3:1 or higher** in both light and dark themes, above even the WCAG AAA 7:1 level. |
| 3 missing fieldsets | Radio groups are wrapped in `<fieldset>` and `<legend>`. |
| 13 layout tables, 1 possible table caption | Tables are used only for data, each with a `<caption>` and `scope`d header cells. Layout uses CSS grid. |
| 1,099 redundant title texts, 20 accesskeys, 8 redundant links | No `title` attributes, access keys, or duplicate adjacent links. |

Other accessibility features: a skip link, landmarks (`header`, `main`, `aside`, `nav`, `footer`), one `h1` with a logical heading order, a visible focus ring, 44 px touch targets, sortable table headers that set `aria-sort` and announce changes through a live region, `prefers-reduced-motion` and `prefers-color-scheme` support, and a layout that works down to 320 px wide.

Automated check: [axe-core](https://github.com/dequelabs/axe-core) 4.10 (WCAG 2.2 A/AA and best-practice rules) reports **0 violations** in both light and dark themes.

## Files

```
index.html       the redesigned article
css/styles.css   design tokens, light and dark themes, layout
js/main.js       table-of-contents highlight, reading settings, history expand/collapse, sortable roster
```

## Credits and license

Article text is condensed and adapted from the Wikipedia article
["Golden State Warriors"](https://en.wikipedia.org/wiki/Golden_State_Warriors) by its contributors, under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This project is shared under the same license.
Photo of Stephen Curry by Keith Allison, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/), via Wikimedia Commons.

This is a student redesign concept, not affiliated with Wikipedia, the Wikimedia Foundation, the NBA, or the Golden State Warriors.
