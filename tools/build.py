#!/usr/bin/env python3
"""
Build the Encyclopedia Redesign site from live Wikipedia content.

  pip install -r tools/requirements.txt
  python3 tools/build.py            # fetch fresh content and rebuild every page

What it does
  1. Downloads the full article HTML for each article in ARTICLES (Wikipedia Action API).
  2. Cleans and restructures it for the redesign: plain-language labels, collapsible sections,
     accessible tables, citations with previews, navboxes regrouped as "Related topics".
  3. Fixes the accessibility problems WAVE reports on Wikipedia: missing/long alt text, layout
     tables, low-contrast inline colors, empty table headers, redundant title attributes.
  4. Builds the homepage from Wikipedia's daily featured-content feed, plus search.html and 404.html.

Text comes from Wikipedia under CC BY-SA 4.0; image credits are pulled from Wikimedia Commons.
"""
import datetime as dt
import html
import json
import math
import re
import sys
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
API = "https://en.wikipedia.org/w/api.php"
WIKI = "https://en.wikipedia.org/wiki/"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "EncyclopediaRedesign/1.0 (UX class project; https://github.com/AxanderZ/my-awesome-site)"

SITE_NAME = "Encyclopedia"
REPO_URL = "https://github.com/AxanderZ/my-awesome-site"
BASE = "/my-awesome-site/"   # GitHub Pages project path, used only by 404.html (served at any depth)

# ---------------------------------------------------------------------------
# Articles rebuilt locally. Links to these titles stay inside the redesign.
# Curated extras are short, original summaries that sit *on top of* the full article text.
# ---------------------------------------------------------------------------
ARTICLES = {
    "Golden_State_Warriors": {
        "eyebrow": "Sports · Basketball · NBA team",
        "hero_image": "File:Stephen_Curry_dribbling_2016_(cropped).jpg",
        "hero_caption": "Stephen Curry, the franchise's all-time leading scorer, in 2016.",
        "stats": [
            ("7", "League championships"),
            ("1946", "Year founded, in Philadelphia"),
            ("73–9", "Best regular season in NBA history (2015–16)"),
            ("7", "Retired jersey numbers"),
        ],
        "championships": [
            ("1947", "BAA", "Chicago Stags", "Won 4–1", "Award not yet created"),
            ("1956", "NBA", "Fort Wayne Pistons", "Won 4–1", "Award not yet created"),
            ("1975", "NBA", "Washington Bullets", "Won 4–0", "Rick Barry"),
            ("2015", "NBA", "Cleveland Cavaliers", "Won 4–2", "Andre Iguodala"),
            ("2017", "NBA", "Cleveland Cavaliers", "Won 4–1", "Kevin Durant"),
            ("2018", "NBA", "Cleveland Cavaliers", "Won 4–0", "Kevin Durant"),
            ("2022", "NBA", "Boston Celtics", "Won 4–2", "Stephen Curry"),
        ],
        # One short summary per History subsection, in the same order as the article.
        "brief": {
            "section": "History",
            "title": "History in brief",
            "items": [
                "A charter member of the Basketball Association of America, the Philadelphia Warriors won the league's first title in 1947 behind scoring champion Joe Fulks, then won again in 1956.",
                "Wilt Chamberlain scored 100 points in a single game on March 2, 1962, still the NBA record. The team moved to San Francisco that year, lost the 1964 Finals to Boston, and traded Chamberlain in 1965.",
                "Rick Barry and Nate Thurmond rebuilt the team, which became the Golden State Warriors in 1971. In 1975 Al Attles's team swept the heavily favored Washington Bullets for a third title.",
                "Stars left and the Warriors missed the playoffs most years. In 1980 they traded Robert Parish and the pick that became Kevin McHale to Boston.",
                "Coach Don Nelson's fast-paced teams starred Tim Hardaway, Mitch Richmond, and Chris Mullin, known as “Run TMC.” A later rift with Chris Webber and Latrell Sprewell sent the team into decline.",
                "After Sprewell choked coach P. J. Carlesimo at practice in 1997, years of losing followed. In 2007 the “We Believe” Warriors became the first No. 8 seed to beat a No. 1 seed, the Dallas Mavericks.",
                "Drafting Stephen Curry in 2009 and a record $450 million sale in 2010 set up a dynasty: titles in 2015, 2017, 2018, and 2022, and a record 73–9 season in 2015–16.",
            ],
        },
        "roster": True,
    },
    "Stephen_Curry": {
        "eyebrow": "Sports · Basketball · Player",
        "stats": [
            ("4", "NBA championships (2015, 2017, 2018, 2022)"),
            ("2", "MVP awards, including the first unanimous MVP (2016)"),
            ("12", "NBA All-Star selections"),
            ("No. 1", "All-time leader in three-pointers made"),
        ],
    },
}
LOCAL_TITLES = set(ARTICLES)

# Header text → plain-language wording (heading ids are kept, so links still work).
HEADING_RENAMES = {"References": "Sources", "External links": "Elsewhere on the web", "See also": "Related articles"}

# Column abbreviations explained in a key above any table that uses them (Heuristic 6).
ABBREVIATIONS = {
    "GP": "Games played", "GS": "Games started", "MPG": "Minutes per game", "FG%": "Field goal percentage",
    "3P%": "Three-point percentage", "FT%": "Free throw percentage", "RPG": "Rebounds per game",
    "APG": "Assists per game", "SPG": "Steals per game", "BPG": "Blocks per game", "PPG": "Points per game",
    "W": "Wins", "L": "Losses", "W–L%": "Win–loss percentage", "Pos.": "Position", "No.": "Jersey number",
    "DOB": "Date of birth", "Ref": "Source", "Ref.": "Source", "Note(s)": "Notes",
}

POSITIONS = {"G": "Guard", "F": "Forward", "C": "Center", "F/C": "Forward / Center", "G/F": "Guard / Forward", "PG": "Point guard", "SG": "Shooting guard", "SF": "Small forward", "PF": "Power forward"}


# ---------------------------------------------------------------------------
# Wikipedia API helpers
# ---------------------------------------------------------------------------
def api(**params):
    params.update(format="json", formatversion=2)
    r = SESSION.get(API, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def fetch_article(title):
    parse = api(action="parse", page=title, prop="text|sections|properties|displaytitle|revid",
                disableeditsection=1, redirects=1)["parse"]
    info = api(action="query", titles=title, prop="info|revisions", inprop="protection",
               rvprop="timestamp")["query"]["pages"][0]
    return parse, info


def fetch_image_info(files):
    """files: iterable of 'File:Name' → {file: {desc, artist, license, license_url, page}}"""
    out, files = {}, sorted(set(files))
    for i in range(0, len(files), 50):
        batch = files[i:i + 50]
        data = api(action="query", titles="|".join(batch), prop="imageinfo", iiprop="extmetadata|url",
                   iiextmetadatafilter="ImageDescription|Artist|LicenseShortName|LicenseUrl|ObjectName",
                   iiextmetadatalanguage="en")
        norm = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
        for page in data["query"]["pages"]:
            ii = (page.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            val = lambda k: strip_tags(meta.get(k, {}).get("value", ""))
            key = norm.get(page["title"], page["title"])
            out[key] = {
                "desc": val("ImageDescription") or val("ObjectName"),
                "artist": val("Artist"),
                "license": val("LicenseShortName"),
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                "page": ii.get("descriptionurl") or WIKI + urllib.parse.quote(page["title"].replace(" ", "_")),
            }
    return out


def strip_tags(s):
    return re.sub(r"\s+", " ", BeautifulSoup(s or "", "html.parser").get_text(" ")).strip()


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(s, quote=True)


def words(text):
    return len(re.findall(r"\w[\w'’–-]*", text))


def read_time(n):
    return f"{max(1, math.ceil(n / 230))} min read"


def text_of(el):
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


def shorten(s, limit=95):
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(",;:–-")
    return cut + "…"


def file_from_src(src):
    m = re.search(r"/wikipedia/(?:commons|en)/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?]+)", src)
    return "File:" + urllib.parse.unquote(m.group(1)).replace("_", " ") if m else None


def fix_url(u):
    if not u:
        return u
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    u = re.sub(r"[?&]utm_[a-z]+=[^&\s]*", "", u)
    return u.replace("?&", "?").rstrip("?")


def local_href(title, fragment, prefix):
    """prefix: path from the current page to the site root ('' or '../')."""
    return f"{prefix}wiki/{title}.html" + (f"#{fragment}" if fragment else "")


def wiki_href(href, prefix):
    """Map a Wikipedia-relative href to a local page (if rebuilt) or an absolute Wikipedia URL."""
    if href.startswith("#"):
        return href
    if href.startswith("./"):
        href = "/wiki/" + href[2:]
    if href.startswith("/wiki/"):
        path = href[len("/wiki/"):]
        title, _, frag = path.partition("#")
        title = urllib.parse.unquote(title)
        if title in LOCAL_TITLES:
            return local_href(title, frag, prefix)
        return WIKI + path
    if href.startswith("/w/"):
        return "https://en.wikipedia.org" + href
    return fix_url(href)


# ---------------------------------------------------------------------------
# Content transformation
# ---------------------------------------------------------------------------
KEEP_ATTRS = {"href", "src", "srcset", "alt", "width", "height", "colspan", "rowspan", "id", "lang", "dir",
              "scope", "datetime", "start", "type", "title", "headers", "loading", "decoding", "role", "tabindex",
              "data-sortable", "data-value", "data-type"}
# Classes created by this script (Wikipedia's own classes are dropped).
KEEP_CLASSES = {"mw-heading", "cite", "cite--note", "needs-source", "backrefs", "backref", "refs", "refs--notes",
                "refs--sources", "ext", "hlist", "plainlist", "notice", "hatnote", "figure-right", "figure-left",
                "figure-center", "multi", "pullquote", "kit-grid", "kit", "inline-list", "layout", "layout-row",
                "layout-cell", "data-table", "table-wrap", "table-key", "nb", "nb-groups", "nb-full", "roster", "meta",
                "legend", "legend__title", "badge", "badge--twoway", "badge--injured", "facts", "facts--compact",
                "facts__group", "facts__more", "facts__extra", "credit"}


class Cleaner:
    def __init__(self, title, prefix):
        self.title = title
        self.prefix = prefix
        self.files = set()          # every File: used, for credits
        self.content_images = []    # (img Tag, file) needing alt text from Commons
        self.captions = {}          # caption text → count, to keep table landmarks uniquely named

    # -- links ------------------------------------------------------------
    def links(self, root):
        for a in root.find_all("a"):
            href = a.get("href", "")
            cls = a.get("class") or []
            if "new" in cls or "redlink=1" in href or href.startswith("/wiki/File:") or "mw-file-description" in cls:
                a.unwrap()          # red links, file-description links → plain text / bare image
                continue
            if not a.get_text(strip=True) and "wikidata.org" in href:
                a.decompose()       # icon-only "edit on Wikidata" pencils
                continue
            a["href"] = wiki_href(href, self.prefix)
            for attr in ("title", "rel", "class"):
                a.attrs.pop(attr, None)
            ours = [c for c in cls if c in KEEP_CLASSES]
            if "external" in cls or "extiw" in cls:
                ours.append("ext")
            if ours:
                a["class"] = ours

    # -- images -----------------------------------------------------------
    def images(self, root):
        for img in root.find_all("img"):
            src = img.get("src", "")
            f = file_from_src(src)
            w = int(img.get("width") or 0)
            # Non-free files (logos) live on en.wikipedia, not Commons. Leave them out.
            if "/wikipedia/en/" in src and w > 60:
                (img.find_parent("figure") or img).decompose()
                continue
            img["src"] = fix_url(src)
            if img.get("srcset"):
                img["srcset"] = ", ".join(fix_url(p.strip()) for p in img["srcset"].split(","))
            img["loading"] = "lazy"
            img["decoding"] = "async"
            decorative = (w and w <= 40) or img.find_parent(class_=re.compile(
                r"flagicon|mbox-image|side-box-image|portal-bar|noviewer|kit|navbox|succession"))
            if decorative:
                img["alt"] = "" if not img.get("alt") or img.find_parent(class_="kit") is None else img["alt"]
                if img.get("alt") and len(img["alt"]) > 95:
                    img["alt"] = shorten(img["alt"])
                continue
            if f:
                self.files.add(f)
                img["data-file"] = f
                self.content_images.append((img, f))

    def apply_alt(self, info):
        for img, f in self.content_images:
            if img.parent is None:
                continue
            meta = info.get(f, {})
            alt = img.get("alt", "").strip()
            if not alt or len(alt) > 95 or re.search(r"\.(jpe?g|png|svg|gif|tiff?)\b", alt, re.I):
                fig = img.find_parent("figure")
                cap = text_of(fig.find("figcaption")) if fig and fig.find("figcaption") else ""
                alt = meta.get("desc") or cap or re.sub(r"\.[a-z]+$", "", f[5:], flags=re.I)
                alt = re.sub(r"^(an? )?(image|photo|picture|photograph|file)( of)?:?\s+", "", alt, flags=re.I)
                alt = re.sub(r"\.(jpe?g|png|svg|gif|tiff?)\b", "", alt, flags=re.I)
            img["alt"] = shorten(alt, 95)
            del img["data-file"]

    # -- citations ---------------------------------------------------------
    def citations(self, root):
        for sup in root.select("sup.reference"):
            a = sup.find("a")
            if not a:
                sup.decompose()
                continue
            label = re.sub(r"[\[\]\s]", "", a.get_text())
            is_note = bool(re.fullmatch(r"[a-z]{1,2}", label))
            new = root_soup(root).new_tag("sup", attrs={"class": "cite cite--note" if is_note else "cite", "id": sup.get("id", "")})
            link = root_soup(root).new_tag("a", href=a["href"])
            link["aria-label"] = ("Note " if is_note else "Source ") + label
            link.string = label
            new.append(link)
            sup.replace_with(new)
        # "[citation needed]" and similar inline cleanup tags
        for sup in root.select("sup.Inline-Template, sup.noprint"):
            t = text_of(sup).strip("[] ")
            a = sup.find("a")
            chip = root_soup(root).new_tag("span", attrs={"class": "needs-source"})
            if a:
                a.string = t
                chip.append(a)
            else:
                chip.string = t
            sup.replace_with(chip)

    def reference_lists(self, root):
        for ol in root.select("ol.references"):
            ol["class"] = ["refs", "refs--notes" if ol.get("data-mw-group") else "refs--sources"]
            for li in ol.find_all("li", recursive=False):
                back = li.select_one(".mw-cite-backlink")
                links = [{"href": x.get("href", "")} for x in back.find_all("a")] if back else []
                if back:
                    back.decompose()
                span = root_soup(root).new_tag("span", attrs={"class": "backrefs"})
                if len(links) == 1:
                    a = root_soup(root).new_tag("a", href=links[0]["href"], attrs={"class": "backref"})
                    a["aria-label"] = "Back to text"
                    a.string = "↑"
                    span.append(a)
                elif links:
                    lead = root_soup(root).new_tag("span", attrs={"aria-hidden": "true"})
                    lead.string = "↑ "
                    span.append(lead)
                    for i, l in enumerate(links):
                        letter = chr(97 + i) if i < 26 else str(i + 1)
                        a = root_soup(root).new_tag("a", href=l["href"], attrs={"class": "backref"})
                        a["aria-label"] = f"Back to mention {letter}"
                        a.string = letter
                        span.append(a)
                        span.append(" ")
                li.insert(0, span)

    # -- styles & attributes -------------------------------------------------
    def attributes(self, root):
        # Hidden sort keys would appear once inline styles are removed.
        for el in root.select('[style*="display:none"], [style*="display: none"], .sortkey'):
            el.decompose()
        for el in root.find_all(True):
            style = el.get("style")
            keep_style = style and not text_of(el) and el.name in ("div", "span") and \
                         re.search(r"background|position|width|height", style)
            cls = el.get("class") or []
            for attr in list(el.attrs):
                if attr == "style" and keep_style:
                    el["style"] = re.sub(r"(?<![-\w])color\s*:\s*[^;]+;?", "", style)
                    continue
                if attr == "class":
                    continue
                if attr == "title" and el.name != "abbr":
                    del el[attr]
                elif attr not in KEEP_ATTRS and not attr.startswith("aria-") and attr != "data-file":
                    del el[attr]
            if cls:
                keep = [c for c in cls if c in KEEP_CLASSES]
                if keep:
                    el["class"] = keep
                else:
                    del el["class"]

    # -- structural components ---------------------------------------------
    def components(self, root):
        soup = root_soup(root)
        for el in root.select("style, link, meta, .mw-empty-elt, .shortdescription, .navbox-styles, .mw-editsection, .noprint.portal-bar-header"):
            el.decompose()
        # Layout wrappers that only arrange columns.
        for el in root.select(".columns-start, .column, .div-col"):
            if el.name == "div":
                el.unwrap()
        # Hatnotes ("Main article: …")
        for el in root.select(".hatnote"):
            el.name = "p"
            el["class"] = ["hatnote"]
        # Maintenance banners → plain notice
        for el in root.select("table.ambox"):
            msg = el.select_one(".mbox-text") or el
            div = soup.new_tag("div", attrs={"class": "notice", "role": "note"})
            for child in list(msg.contents):
                div.append(child)
            el.replace_with(div)
        # Figures: alignment classes
        for fig in root.find_all("figure"):
            cls = " ".join(fig.get("class") or [])
            fig["class"] = ["figure-left" if "halign-left" in cls else "figure-center" if "halign-center" in cls or "halign-none" in cls else "figure-right"]
        # Multi-image boxes → one figure
        for box in root.select(".thumb.tmulti"):
            fig = soup.new_tag("figure", attrs={"class": ["figure-right", "multi"]})
            row = soup.new_tag("div", attrs={"class": "multi"})
            for img in box.find_all("img"):
                row.append(img.extract())
            fig.append(row)
            cap = box.select_one(".thumbcaption")
            if cap:
                fc = soup.new_tag("figcaption")
                for c in list(cap.contents):
                    fc.append(c)
                fig.append(fc)
            box.replace_with(fig)
        # Pull quotes
        for q in root.select(".quotebox"):
            q.name = "aside"
            q["class"] = ["pullquote"]
            q["aria-label"] = "Quotation"
        # Uniform "kit" drawings → a grid of figures (keeps their color boxes, no layout table)
        for kit in root.select("table.kit"):
            grid = soup.new_tag("div", attrs={"class": "kit-grid"})
            for td in kit.find_all("td"):
                cell = soup.new_tag("div", attrs={"class": "kit"})
                for c in list(td.contents):
                    cell.append(c)
                grid.append(cell)
            kit.replace_with(grid)
        # Sister-project boxes and portal bars → simple lists of links
        for box in root.select(".side-box, .portal-bar, ul.portalbox"):
            ul = soup.new_tag("ul", attrs={"class": "inline-list"})
            for a in box.find_all("a"):
                if not a.get_text(strip=True):
                    continue
                li = soup.new_tag("li")
                li.append(a.extract())
                ul.append(li)
            box.replace_with(ul)

    def tables(self, root, heading_for):
        soup = root_soup(root)
        for tbl in list(root.find_all("table")):
            if tbl.parent is None or tbl.find_parent("table") or tbl.find_parent(class_="table-wrap"):
                continue
            self._table(tbl, soup, heading_for(tbl))

    def _table(self, tbl, soup, context):
        # Nested tables first (inner-most out)
        for inner in tbl.find_all("table"):
            if inner.find("table"):
                continue
            self._table(inner, soup, context)
        if tbl.parent is None:
            return
        rows = [tr for tr in tbl.find_all("tr") if tr.find_parent("table") is tbl]
        ths = [th for th in tbl.find_all("th") if th.find_parent("table") is tbl]
        is_layout = tbl.get("role") == "presentation" or not ths or "succession-box" in (tbl.get("class") or [])
        if is_layout:
            if len(rows) == 1 and len(rows[0].find_all(["td", "th"], recursive=False)) > 3:
                ul = soup.new_tag("ul", attrs={"class": "inline-list"})
                for cell in rows[0].find_all(["td", "th"], recursive=False):
                    if not cell.get_text(strip=True):
                        continue
                    li = soup.new_tag("li")
                    for c in list(cell.contents):
                        li.append(c)
                    ul.append(li)
                tbl.replace_with(ul)
                return
            box = soup.new_tag("div", attrs={"class": "layout"})
            for tr in rows:
                row = soup.new_tag("div", attrs={"class": "layout-row"})
                for cell in tr.find_all(["td", "th"], recursive=False):
                    c = soup.new_tag("div", attrs={"class": "layout-cell"})
                    for x in list(cell.contents):
                        c.append(x)
                    row.append(c)
                box.append(row)
            tbl.replace_with(box)
            return

        # --- data table ---
        was_sortable = "sortable" in (tbl.get("class") or [])
        ncols = max((sum(int(c.get("colspan", 1) or 1) for c in tr.find_all(["td", "th"], recursive=False)) for tr in rows), default=1)
        caption = tbl.find("caption")
        # A first row that is a single header spanning the table is really a caption.
        first = rows[0] if rows else None
        if first is not None:
            cells = first.find_all(["td", "th"], recursive=False)
            if len(cells) == 1 and cells[0].name == "th" and int(cells[0].get("colspan", 1) or 1) >= ncols and ncols > 1:
                if caption is None or not caption.get_text(strip=True):
                    caption = caption or soup.new_tag("caption")
                    caption.clear()
                    for c in list(cells[0].contents):
                        caption.append(c)
                first.decompose()
                rows = rows[1:]
        if caption is None:
            caption = soup.new_tag("caption")
        if not caption.get_text(strip=True):
            caption.clear()
            caption.string = f"{context or 'Data'} table"
        label = text_of(caption)
        self.captions[label] = self.captions.get(label, 0) + 1
        if self.captions[label] > 1:
            caption.append(f" ({self.captions[label]})")
        for navbar in caption.select(".navbar"):
            navbar.decompose()
        tbl.insert(0, caption.extract())

        # Header rows (all <th>) → <thead>
        thead = soup.new_tag("thead")
        tbody = soup.new_tag("tbody")
        in_head = True
        for tr in rows:
            cells = tr.find_all(["td", "th"], recursive=False)
            if in_head and cells and all(c.name == "th" for c in cells):
                thead.append(tr.extract())
            else:
                in_head = False
                tbody.append(tr.extract())
        for old in tbl.find_all(["tbody", "thead", "tfoot"], recursive=False):
            old.decompose()
        if thead.contents:
            tbl.append(thead)
        tbl.append(tbody)

        for th in thead.find_all("th"):
            th["scope"] = "colgroup" if int(th.get("colspan", 1) or 1) > 1 else "col"
        for tr in tbody.find_all("tr", recursive=False):
            for th in tr.find_all("th", recursive=False):
                th["scope"] = "row"
        # Empty header cells are WAVE errors: make them ordinary cells.
        for th in tbl.find_all("th"):
            if not th.get_text(strip=True) and not th.find("img"):
                th.name = "td"
                th.attrs.pop("scope", None)

        # Key for abbreviated column names (Heuristic 6)
        used = []
        for th in thead.find_all("th"):
            t = text_of(th)
            if t in ABBREVIATIONS and t not in [u[0] for u in used]:
                used.append((t, ABBREVIATIONS[t]))
        simple = was_sortable and len(thead.find_all("tr")) == 1 and not tbody.find(attrs={"rowspan": True}) \
            and not tbody.find(attrs={"colspan": True})
        tbl.attrs = {"class": ["data-table"]}
        if simple:
            tbl["data-sortable"] = ""
        wrap = soup.new_tag("div", attrs={"class": "table-wrap", "role": "region", "tabindex": "0"})
        cid = "cap-" + re.sub(r"\W+", "-", text_of(caption).lower()).strip("-")[:40] + f"-{id(tbl) % 10000}"
        caption["id"] = cid
        wrap["aria-labelledby"] = cid
        tbl.replace_with(wrap)
        if used:
            key = soup.new_tag("dl", attrs={"class": "table-key"})
            for abbr, full in used:
                d = soup.new_tag("div")
                dt_ = soup.new_tag("dt"); dt_.string = abbr
                dd = soup.new_tag("dd"); dd.string = full
                d.append(dt_); d.append(dd)
                key.append(d)
            wrap.insert_before(key)
        wrap.append(tbl)


def root_soup(el):
    while el.parent is not None:
        el = el.parent
    return el


# ---------------------------------------------------------------------------
# Navboxes → "Related topics"
# ---------------------------------------------------------------------------
def navbox_rows(table, soup, cleaner):
    out = soup.new_tag("div", attrs={"class": "nb"})
    dl = None
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        group = tr.find("th", class_="navbox-group", recursive=False)
        lst = tr.find("td", class_=re.compile("navbox-list|navbox-abovebelow"), recursive=False)
        if lst is None:
            continue
        sub = lst.find("table", class_="navbox-subgroup") or lst.find("table", class_="navbox-inner")
        body = navbox_rows(sub, soup, cleaner) if sub is not None else soup.new_tag("div")
        if sub is None:
            for c in list(lst.contents):
                body.append(c)
        if group is not None and group.get_text(strip=True):
            if dl is None:
                dl = soup.new_tag("dl", attrs={"class": "nb-groups"})
                out.append(dl)
            row = soup.new_tag("div")
            dt_ = soup.new_tag("dt")
            for c in list(group.contents):
                dt_.append(c)
            dd = soup.new_tag("dd")
            dd.append(body)
            row.append(dt_)
            row.append(dd)
            dl.append(row)
        else:
            dl = None
            full = soup.new_tag("div", attrs={"class": "nb-full"})
            full.append(body)
            out.append(full)
    return out


def extract_navboxes(root, cleaner):
    soup = root_soup(root)
    boxes = []
    for nav in root.select("div.navbox"):
        if nav.find_parent(class_="navbox"):
            continue
        table = nav.find("table")
        if table is None:
            nav.decompose()
            continue
        title_th = table.find("th", class_="navbox-title")
        for bar in nav.select(".navbar"):
            bar.decompose()
        title = soup.new_tag("span")
        if title_th is not None:
            inner = title_th.find(id=True) or title_th
            for c in list(inner.contents):
                title.append(c)
        if not text_of(title):
            title.string = "Authority control databases" if "authority-control" in (nav.get("class") or []) else "More links"
        for img in nav.select(".navbox-image"):
            img.decompose()
        body = navbox_rows(table, soup, cleaner)
        nav.extract()
        boxes.append((title, body))
    return boxes


# ---------------------------------------------------------------------------
# Infobox → "At a glance" facts
# ---------------------------------------------------------------------------
def convert_infobox(root, soup):
    box = root.select_one("table.infobox")
    if box is None:
        return None, None
    box.extract()
    image = None
    groups = [[None, []]]
    extras = []
    for tr in box.find_all("tr"):
        if tr.find_parent("table") is not box:
            continue
        th = tr.find("th", recursive=False)
        td = tr.find("td", recursive=False)
        tcls = " ".join(th.get("class") or []) if th else ""
        dcls = " ".join(td.get("class") or []) if td else ""
        if "infobox-above" in tcls:
            continue
        if td is not None and "infobox-image" in dcls:
            img = td.find("img")
            if img is not None and image is None:
                cap = td.select_one(".infobox-caption")
                image = (img, cap)
            continue
        if th is not None and "infobox-header" in tcls:
            groups.append([th, []])
        elif th is not None and td is not None:
            groups[-1][1].append((th, td))
        elif td is not None and td.get_text(strip=True) or (td is not None and td.find("img")):
            extras.append(td)
    return image, (groups, extras)


def render_facts(groups, extras, soup):
    parts = []
    for head, rows in groups:
        if not rows and head is None:
            continue
        chunk = []
        if head is not None:
            chunk.append(f'<h3 class="facts__group">{inner_html(head)}</h3>')
        if rows:
            chunk.append('<dl class="facts">' + "".join(
                f"<div><dt>{inner_html(th)}</dt><dd>{inner_html(td)}</dd></div>" for th, td in rows) + "</dl>")
        parts.append("".join(chunk))
    extra_html = ""
    for td in extras:
        content = inner_html(td).strip()
        if not content:
            continue
        n = words(text_of(td))
        if n > 60:
            extra_html += f'<details class="facts__more"><summary>{"Career highlights and awards" if "champion" in text_of(td).lower() else "More details"} <span class="meta">({n} words)</span></summary><div class="facts__extra">{content}</div></details>'
        else:
            extra_html += f'<div class="facts__extra">{content}</div>'
    return "".join(parts) + extra_html


def inner_html(el):
    return "".join(str(c) for c in el.contents).strip() if el is not None else ""


# ---------------------------------------------------------------------------
# Roster (Golden State Warriors): template table → accessible roster component
# ---------------------------------------------------------------------------
def build_roster(root, soup):
    box = None
    for t in root.select("table.toccolours"):
        if "roster" in text_of(t).lower():
            box = t
            break
    if box is None:
        return
    players = box.select_one("table.sortable")
    rows = []
    for tr in players.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 7:
            continue
        name_cell = cells[2]
        injured = bool(name_cell.find("img", alt=re.compile("injur", re.I)) or name_cell.find(title=re.compile("injur", re.I)))
        name_txt = text_of(name_cell)
        badges = []
        for code, label, cls in (("(TW)", "Two-way contract", "badge--twoway"), ("(DP)", "Unsigned draft pick", "badge--twoway"),
                                 ("(FA)", "Free agent", "badge--twoway"), ("(S)", "Suspended", "badge--injured"),
                                 ("(GL)", "On G League assignment", "badge--twoway")):
            if code in name_txt:
                badges.append((label, cls))
        if injured:
            badges.append(("Injured", "badge--injured"))
        link = name_cell.find("a")
        name = re.sub(r"\s*\((TW|DP|FA|S|GL)\)\s*", "", name_txt).strip()
        rows.append({
            "pos": POSITIONS.get(text_of(cells[0]), text_of(cells[0])), "num": text_of(cells[1]), "name": name,
            "href": link["href"] if link else None, "badges": badges, "height": text_of(cells[3]),
            "weight": text_of(cells[4]), "born": text_of(cells[5]), "from": text_of(cells[6]),
        })
    coaches = []
    for li in box.find_all("li"):
        t = text_of(li)
        if t and not re.match(r"^\((DP|FA|S|GL|TW)\)", t) and "njured" not in t:
            coaches.append(t)
    updated = re.search(r"Updated:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", text_of(box))

    def last(n):
        return n.split()[-1] if n.split()[-1] not in ("II", "III", "Jr.") else n.split()[-2]

    rows.sort(key=lambda r: last(r["name"]))
    def born(s):
        try:
            d = dt.date.fromisoformat(s)
            return d.strftime("%b %-d, %Y"), d.strftime("%Y%m%d")
        except ValueError:
            return s, s
    def inches(s):
        m = re.match(r"(\d+) ft (\d+) in", s)
        return str(int(m.group(1)) * 12 + int(m.group(2))) if m else "0"
    trs = []
    for r in rows:
        b = "".join(f' <span class="badge {c}">{esc(l)}</span>' for l, c in r["badges"])
        name = f'<a href="{esc(r["href"])}">{esc(r["name"])}</a>' if r["href"] else esc(r["name"])
        bd, bkey = born(r["born"])
        trs.append(f'<tr><th scope="row" data-value="{esc(last(r["name"]))}">{name}{b}</th><td>{esc(r["num"])}</td>'
                   f'<td>{esc(r["pos"])}</td><td data-value="{inches(r["height"])}">{esc(r["height"])}</td>'
                   f'<td data-value="{re.match(r"\d+", r["weight"]).group(0) if re.match(r"\d+", r["weight"]) else 0}">{esc(r["weight"])}</td>'
                   f'<td data-value="{bkey}">{esc(bd)}</td><td>{esc(r["from"])}</td></tr>')
    used = {l for r in rows for l, _ in r["badges"]}
    legend_items = {
        "Two-way contract": ("badge--twoway", "Splits time between the Warriors and their G League team, the Santa Cruz Warriors."),
        "Injured": ("badge--injured", "Currently out with an injury."),
        "Unsigned draft pick": ("badge--twoway", "Drafted by the team but not yet signed."),
        "Free agent": ("badge--twoway", "Not currently under contract."),
        "Suspended": ("badge--injured", "Currently suspended by the league."),
        "On G League assignment": ("badge--twoway", "Temporarily playing for the G League affiliate."),
    }
    legend = "".join(f'<li><span class="badge {legend_items[k][0]}">{esc(k)}</span> {esc(legend_items[k][1])}</li>' for k in legend_items if k in used)
    head_coach = coaches[0] if coaches else ""
    html_ = f'''
<div class="roster">
  <p class="meta">{"Roster last updated on Wikipedia " + updated.group(1) + "." if updated else ""}</p>
  {f'<div class="legend"><p class="legend__title">Labels used in this table</p><ul>{legend}</ul></div>' if legend else ""}
  <div class="table-wrap" role="region" aria-labelledby="roster-caption" tabindex="0">
    <table class="data-table" data-sortable id="roster-table">
      <caption id="roster-caption">Current players. Use the column buttons to sort.</caption>
      <thead><tr><th scope="col">Player</th><th scope="col" data-type="number">Jersey number</th><th scope="col">Position</th>
      <th scope="col" data-type="number">Height</th><th scope="col" data-type="number">Weight</th><th scope="col" data-type="number">Born</th><th scope="col">College or country</th></tr></thead>
      <tbody>{"".join(trs)}</tbody>
    </table>
  </div>
  <h4>Coaching staff</h4>
  <dl class="facts facts--compact">
    <div><dt>Head coach</dt><dd>{esc(head_coach)}</dd></div>
    <div><dt>Assistant coaches</dt><dd>{esc(", ".join(coaches[1:]))}</dd></div>
  </dl>
</div>'''
    box.replace_with(BeautifulSoup(html_, "html.parser"))


# ---------------------------------------------------------------------------
# Sectioning: flat Wikipedia output → sections with collapsible subsections (Heuristic 8)
# ---------------------------------------------------------------------------
def flatten_headings(root):
    """Headings nested in wrapper divs → top level, so sections can be split linearly."""
    changed = True
    while changed:
        changed = False
        for child in list(root.find_all(recursive=False)):
            if child.name == "div" and "mw-heading" not in (child.get("class") or []) and child.select_one(".mw-heading"):
                child.unwrap()
                changed = True


def split_sections(root):
    lead, sections = [], []
    cur_sec, cur_sub = None, None
    for node in list(root.children):
        if isinstance(node, NavigableString):
            if node.strip():
                (cur_sub["body"] if cur_sub else cur_sec["intro"] if cur_sec else lead).append(node)
            continue
        h = node.find(re.compile("^h[2-6]$")) if "mw-heading" in (node.get("class") or []) else None
        if h is not None:
            level = int(h.name[1])
            if level == 2 or cur_sec is None:
                cur_sec = {"id": h.get("id"), "title": text_of(h), "heading": h, "intro": [], "subs": []}
                sections.append(cur_sec)
                cur_sub = None
            elif level == 3 or cur_sub is None:
                cur_sub = {"id": h.get("id"), "title": text_of(h), "heading": h, "body": []}
                cur_sec["subs"].append(cur_sub)
            else:
                h.name = "h4" if level <= 4 else "h5"
                cur_sub["body"].append(h)
            continue
        (cur_sub["body"] if cur_sub else cur_sec["intro"] if cur_sec else lead).append(node)
    return lead, sections


def nodes_html(nodes):
    return "".join(str(n) for n in nodes)


def promote_pseudo_headings(nodes, base_level):
    """<p><b>Short label</b></p> used as a heading → a real heading (WAVE 'possible heading')."""
    last = base_level
    for n in nodes:
        if not isinstance(n, Tag):
            continue
        if re.fullmatch(r"h[2-6]", n.name):
            last = int(n.name[1])
            continue
        for p in ([n] if n.name == "p" else n.find_all("p")):
            kids = [c for c in p.contents if not (isinstance(c, NavigableString) and not c.strip())]
            if len(kids) == 1 and isinstance(kids[0], Tag) and kids[0].name in ("b", "strong") and 0 < len(text_of(p)) <= 60:
                p.name = f"h{min(last + 1, 6)}"
                kids[0].unwrap()


def nodes_words(nodes):
    total = 0
    for n in nodes:
        if isinstance(n, Tag):
            c = BeautifulSoup(str(n), "html.parser")
            for s in c.select("sup, .table-key, caption"):
                s.decompose()
            total += words(c.get_text(" "))
        else:
            total += words(str(n))
    return total


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&amp;display=swap">')

ICON_SEARCH = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
ICON_DISPLAY = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h10M4 17h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
LOGO = ('<svg class="brand__mark" viewBox="0 0 40 40" aria-hidden="true" focusable="false">'
        '<rect width="40" height="40" rx="11" fill="currentColor"/>'
        '<path d="M11 12h18M11 20h18M11 28h11" stroke="var(--brand-mark-ink)" stroke-width="3" stroke-linecap="round"/></svg>')


def search_form(prefix, fid, big=False, value=""):
    cls = "search search--big" if big else "search"
    return f'''<form class="{cls}" role="search" action="{prefix}search.html" method="get" data-prefix="{prefix}">
  <label class="{'search__label' if big else 'vh'}" for="{fid}">Search the encyclopedia</label>
  <div class="search__field">
    {ICON_SEARCH}
    <input id="{fid}" class="search__input" type="search" name="q" value="{esc(value)}" placeholder="Search 7 million articles" autocomplete="off" spellcheck="false"
      role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="{fid}-list">
    <button class="search__submit" type="submit">Search</button>
    <ul class="search__list" id="{fid}-list" role="listbox" aria-label="Suggestions" hidden></ul>
  </div>
  <p class="vh" id="{fid}-status" role="status" aria-live="polite"></p>
</form>'''


def page(*, title, description, body, prefix, active="", header_search=True, extra_head=""):
    nav = [("Search", f"{prefix}search.html", "search"), ("About this redesign", f"{REPO_URL}#readme", "about")]
    nav_html = "".join(f'<li><a href="{h}"{" aria-current=\"page\"" if k == active else ""}>{t}</a></li>' for t, h, k in nav)
    year = dt.date.today().year
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="color-scheme" content="light dark">
{FONTS}
<link rel="stylesheet" href="{prefix}css/site.css">
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<script>
try{{var s=JSON.parse(localStorage.getItem("display")||"{{}}");var d=document.documentElement;if(s.theme&&s.theme!=="auto")d.dataset.theme=s.theme;if(s.size&&s.size!=="standard")d.dataset.size=s.size;if(s.width==="wide")d.dataset.width="wide";}}catch(e){{}}
document.documentElement.classList.add("js");
</script>
<script src="{prefix}js/site.js" defer></script>
{extra_head}
</head>
<body>
<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header">
  <div class="site-header__inner">
    <a class="brand" href="{prefix}index.html">{LOGO}<span class="brand__name">{SITE_NAME}</span><span class="brand__tag">Redesign</span></a>
    {search_form(prefix, "site-q") if header_search else ""}
    <nav class="site-nav" aria-label="Site">
      <ul>{nav_html}</ul>
    </nav>
    <div class="display">
      <button class="display__toggle" type="button" aria-expanded="false" aria-controls="display-panel">{ICON_DISPLAY}<span>Display</span></button>
      <div class="display__panel" id="display-panel" hidden>
        <fieldset><legend>Text size</legend>
          <label><input type="radio" name="size" value="small"> Small</label>
          <label><input type="radio" name="size" value="standard" checked> Standard</label>
          <label><input type="radio" name="size" value="large"> Large</label>
        </fieldset>
        <fieldset><legend>Page width</legend>
          <label><input type="radio" name="width" value="standard" checked> Comfortable</label>
          <label><input type="radio" name="width" value="wide"> Wide</label>
        </fieldset>
        <fieldset><legend>Color theme</legend>
          <label><input type="radio" name="theme" value="auto" checked> Match device</label>
          <label><input type="radio" name="theme" value="light"> Light</label>
          <label><input type="radio" name="theme" value="dark"> Dark</label>
        </fieldset>
      </div>
    </div>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="site-footer__inner">
    <div class="site-footer__brand">{LOGO}<span>{SITE_NAME} Redesign</span></div>
    <p>Article text and data come from <a href="https://en.wikipedia.org/">Wikipedia</a> and its contributors under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Images are credited on each page.</p>
    <p>A student UX project, {year}. Not affiliated with Wikipedia or the Wikimedia Foundation. <a href="{REPO_URL}">Source code on GitHub</a>.</p>
  </div>
</footer>
</body>
</html>
'''


# ---------------------------------------------------------------------------
# Article page
# ---------------------------------------------------------------------------
def build_article(slug):
    cfg = ARTICLES[slug]
    prefix = "../"
    print(f"• {slug}: fetching")
    parse, info = fetch_article(slug)
    title = strip_tags(parse["displaytitle"])
    soup = BeautifulSoup(parse["text"], "html.parser")
    root = soup.select_one(".mw-parser-output")
    cl = Cleaner(slug, prefix)

    for hat in root.select(".hatnote"):
        if "other uses" in text_of(hat).lower() or "other people" in text_of(hat).lower() or "disambiguation" in text_of(hat).lower():
            hat["class"] = hat.get("class", []) + ["hatnote--top"]
    top_hatnotes = [h.extract() for h in root.select(".hatnote.hatnote--top") if not h.find_previous(class_="mw-heading")]

    cl.components(root)
    image, facts = convert_infobox(root, soup)
    navboxes = extract_navboxes(root, cl)
    if cfg.get("roster"):
        build_roster(root, soup)
    flatten_headings(root)

    def heading_for(tbl):
        h = tbl.find_previous(re.compile("^h[2-5]$"))
        return text_of(h) if h else title
    cl.tables(root, heading_for)
    cl.citations(root)
    cl.reference_lists(root)
    cl.links(root)
    cl.images(root)

    # Hero / glance image
    hero_file = cfg.get("hero_image")
    hero_img_html, hero_cap = "", ""
    if image is not None and hero_file is None:
        img, cap = image
        if "/commons/" in img.get("src", ""):
            hero_file = file_from_src(img["src"])
            hero_cap = text_of(cap) if cap else ""
    if hero_file:
        cl.files.add(hero_file)

    # Facts from infobox, cleaned the same way as the body
    facts_html = ""
    if facts:
        groups, extras = facts
        holder = BeautifulSoup("<div></div>", "html.parser").div
        tmp = BeautifulSoup(render_facts(groups, extras, soup), "html.parser")
        holder.append(tmp)
        cl.components(holder); cl.tables(holder, lambda t: "Medal record"); cl.citations(holder); cl.links(holder); cl.images(holder)
        facts_html = holder
    # Navboxes cleaned
    nav_holder = BeautifulSoup("<div></div>", "html.parser").div
    for t, b in navboxes:
        wrap = soup.new_tag("div")
        wrap.append(t); wrap.append(b)
        nav_holder.append(wrap)
    cl.components(nav_holder); cl.tables(nav_holder, lambda t: "Related topics"); cl.links(nav_holder); cl.images(nav_holder)

    print(f"  image credits for {len(cl.files)} files")
    img_info = fetch_image_info(cl.files)
    cl.apply_alt(img_info)
    for holder in [root, nav_holder] + ([facts_html] if facts_html else []):
        cl.attributes(holder)
    # links inside curated/hatnote bits
    for h in top_hatnotes:
        cl.links(h); cl.attributes(h)

    lead, sections = split_sections(root)
    for s_ in sections:
        promote_pseudo_headings(s_["intro"], 2)
        for sub in s_["subs"]:
            promote_pseudo_headings(sub["body"], 3)
    total_words = nodes_words(lead) + sum(nodes_words(s["intro"]) + sum(nodes_words(x["body"]) for x in s["subs"]) for s in sections)

    # ---- hero ----
    ts = dt.datetime.fromisoformat(info["revisions"][0]["timestamp"].replace("Z", "+00:00"))
    protected = any(p["type"] == "edit" for p in info.get("protection", []))
    enc = urllib.parse.quote(slug)
    shortdesc = parse.get("properties", {}).get("wikibase-shortdesc", "")
    hero_media = ""
    if hero_file:
        meta = img_info.get(hero_file, {})
        src = image_url(hero_file, 640)
        alt = shorten(re.sub(r"\.(jpe?g|png|svg)\b", "", meta.get("desc") or cfg.get("hero_caption", title), flags=re.I), 95)
        cap = cfg.get("hero_caption") or hero_cap
        hero_media = f'''<figure class="glance__photo">
  <img src="{esc(src)}" alt="{esc(alt)}" width="640" height="800" decoding="async">
  <figcaption>{esc(cap)} <span class="credit">{credit_html(meta)}</span></figcaption>
</figure>'''

    stats = "".join(f'<li class="stat"><span class="stat__value">{esc(v)}</span><span class="stat__label">{esc(l)}</span></li>' for v, l in cfg.get("stats", []))
    champs = ""
    if cfg.get("championships"):
        rows = "".join(f"<tr><th scope=\"row\">{a}</th><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>" for a, b, c, d, e in cfg["championships"])
        champs = f'''<h3 class="glance__h">Championships</h3>
<div class="table-wrap" role="region" aria-labelledby="cap-champs" tabindex="0"><table class="data-table">
<caption id="cap-champs">Every Warriors league title</caption>
<thead><tr><th scope="col">Season</th><th scope="col">League</th><th scope="col">Finals opponent</th><th scope="col">Series</th><th scope="col">Finals MVP</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''

    toc_items, sections_html = [], []
    # Overview (lead)
    toc_items.append(('overview', "Overview", []))
    lead_html = f'''<section class="section section--lead" aria-labelledby="overview">
  <h2 id="overview">Overview</h2>
  {"".join(str(h) for h in top_hatnotes)}
  {nodes_html(lead)}
</section>'''

    for s in sections:
        sid = s["id"]
        disp = HEADING_RENAMES.get(s["title"], s["title"])
        subs_toc = []
        intro_html = nodes_html(s["intro"])
        curated = ""
        brief = cfg.get("brief")
        if brief and brief["section"] == s["title"]:
            items = []
            for i, (sub, summary) in enumerate(zip(s["subs"], brief["items"])):
                years, _, name = sub["title"].partition(":")
                items.append(f'<li class="era"><p class="era__years">{esc(years.strip())}</p><h4 class="era__title">{esc(name.strip() or sub["title"])}</h4>'
                             f'<p>{esc(summary)}</p><a class="era__link" href="#{esc(sub["id"])}">Read the full section<span class="vh">: {esc(sub["title"])}</span></a></li>')
            curated = f'<div class="brief"><h3 class="brief__title">{esc(brief["title"])}</h3><ol class="timeline">{"".join(items)}</ol></div>'
        body = ""
        n_intro = nodes_words(s["intro"])
        if s["subs"]:
            parts = []
            for sub in s["subs"]:
                n = nodes_words(sub["body"])
                subs_toc.append((sub["id"], sub["title"]))
                parts.append(f'''<details class="sub">
  <summary><h3 id="{esc(sub["id"])}" class="sub__title">{esc(sub["title"])}</h3><span class="sub__meta">{read_time(n)}</span></summary>
  <div class="sub__body">{nodes_html(sub["body"])}</div>
</details>''')
            label = "full sections" if curated else "sections"
            body = (f'<div class="section__tools"><button class="btn btn--quiet" type="button" data-expand>Expand all {len(s["subs"])} {label}</button></div>'
                    + '<div class="subs">' + "".join(parts) + "</div>")
        is_refs = s["title"] == "References"
        if is_refs:
            count = len(BeautifulSoup(intro_html, "html.parser").select("ol.refs--sources > li"))
            intro_html = f'''<p>Every numbered marker in the article links to one of these sources. Hover over or focus a marker to preview its source without leaving your place.</p>
<details class="sub sub--plain">
  <summary><span class="sub__title">Show all {count} sources</span><span class="sub__meta">Opens the full list</span></summary>
  <div class="sub__body">{intro_html}</div>
</details>'''
        elif not s["subs"] and n_intro > 700:
            first, rest = split_first_paragraph(s["intro"])
            intro_html = f'''{first}<details class="sub sub--plain">
  <summary><span class="sub__title">Continue reading “{esc(disp)}”</span><span class="sub__meta">{read_time(n_intro)}</span></summary>
  <div class="sub__body">{rest}</div>
</details>'''
        toc_items.append((sid, disp, subs_toc))
        sections_html.append(f'''<section class="section" aria-labelledby="{esc(sid)}">
  <h2 id="{esc(sid)}">{esc(disp)}</h2>
  {intro_html}
  {curated}
  {body}
</section>''')

    # Related topics (navboxes)
    if navboxes:
        items = []
        for wrap in nav_holder.find_all("div", recursive=False):
            kids = [k for k in wrap.children if isinstance(k, Tag)]
            t, b = kids[0], kids[1]
            label = text_of(t)
            items.append(f'<details class="sub sub--plain related"><summary><span class="sub__title">{esc(label)}</span></summary><div class="sub__body">{b}</div></details>')
        toc_items.append(("related-topics", "Related topics", []))
        sections_html.append(f'''<section class="section" aria-labelledby="related-topics">
  <h2 id="related-topics">Related topics</h2>
  <p>Groups of related Wikipedia articles, as listed at the bottom of the original page.</p>
  {"".join(items)}
</section>''')

    # Image credits
    credits = []
    for f in sorted(cl.files):
        m = img_info.get(f)
        if not m:
            continue
        credits.append(f'<li><a href="{esc(m["page"])}">{esc(f[5:])}</a>: {credit_html(m)}</li>')
    toc_items.append(("image-credits", "Image credits", []))
    sections_html.append(f'''<section class="section" aria-labelledby="image-credits">
  <h2 id="image-credits">Image credits</h2>
  <details class="sub sub--plain"><summary><span class="sub__title">Show credits for {len(credits)} images</span></summary>
  <div class="sub__body"><ul class="credits">{"".join(credits)}</ul></div></details>
</section>''')

    toc = render_toc(toc_items)
    actions = f'''<nav class="page-actions" aria-label="Page actions"><ul>
  <li><a href="https://en.wikipedia.org/wiki/Talk:{enc}">Discuss this article</a></li>
  <li><a href="https://en.wikipedia.org/w/index.php?title={enc}&amp;action=history">See who edited it</a></li>
  <li><a href="https://en.wikipedia.org/w/index.php?title=Talk:{enc}&amp;action=edit&amp;section=new">Suggest a correction</a></li>
  <li><a href="https://en.wikipedia.org/wiki/{enc}">Read on Wikipedia</a></li>
</ul></nav>'''
    protect = ('<p class="protect-note"><svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 7V5a4 4 0 1 1 8 0v2h1v8H3V7zm2 0h4V5a2 2 0 1 0-4 0z" fill="currentColor"/></svg>'
               '<span>Only experienced, registered editors can change this article directly, to guard against vandalism. Anyone can suggest a correction.</span></p>') if protected else ""

    body = f'''<div class="progress" aria-hidden="true"><span class="progress__bar"></span></div>
<main id="main" tabindex="-1">
  <header class="article-hero">
    <div class="article-hero__inner">
      <nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="{prefix}index.html">Home</a></li><li><a href="{prefix}search.html">Articles</a></li><li><a href="#main" aria-current="page">{esc(title)}</a></li></ol></nav>
      <p class="eyebrow">{esc(cfg.get("eyebrow", "Article"))}</p>
      <h1 id="page-title">{esc(title)}</h1>
      <p class="lede">{esc(shortdesc[:1].upper() + shortdesc[1:])}</p>
      <p class="article-meta"><span>Last edited <time datetime="{ts.date().isoformat()}">{ts.strftime("%B %-d, %Y")}</time></span><span>{total_words:,} words</span><span>About {max(1, round(total_words / 230))} minutes to read in full</span></p>
      {actions}
      {protect}
    </div>
  </header>
  <div class="article-layout">
    <nav class="toc" aria-labelledby="toc-title">
      <details class="toc__box" open>
        <summary class="toc__title" id="toc-title">Contents</summary>
        {toc}
      </details>
    </nav>
    <article class="article" aria-labelledby="page-title">
      <section class="section glance" aria-labelledby="at-a-glance">
        <h2 id="at-a-glance">At a glance</h2>
        {f'<ul class="stats">{stats}</ul>' if stats else ""}
        <div class="glance__grid">
          <div class="glance__facts">{facts_html}</div>
          {hero_media}
        </div>
        {champs}
      </section>
      {lead_html}
      {"".join(sections_html)}
      <p class="attribution">This page adapts the Wikipedia article <a href="https://en.wikipedia.org/wiki/{enc}">“{esc(title)}”</a> (revision {parse["revid"]}), shared under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. The summaries under “At a glance” and “{esc(cfg["brief"]["title"]) if cfg.get("brief") else "Overview"}” were written for this redesign.</p>
    </article>
  </div>
</main>
<div class="cite-pop" id="cite-pop" role="tooltip" hidden></div>'''
    page_html = finalize(page(title=f"{title} | {SITE_NAME} Redesign", description=shortdesc, body=body, prefix=prefix, active=""))
    out = ROOT / "wiki" / f"{slug}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page_html)
    print(f"  wrote {out.relative_to(ROOT)} ({len(page_html) // 1024} KB, {total_words:,} words)")
    return {"slug": slug, "title": title, "desc": shortdesc, "words": total_words, "hero": hero_file,
            "hero_alt": img_info.get(hero_file, {}).get("desc", "") if hero_file else ""}


def finalize(page_html):
    """Last pass over a whole page for WAVE alerts that only show up in context."""
    soup = BeautifulSoup(page_html, "html.parser")
    # Redundant link: two consecutive links to the same URL → keep the first, unlink the second.
    prev = None
    for a in soup.select("main a[href]"):
        href = a["href"]
        if href.startswith("#"):
            continue            # WAVE skips in-page links (citation markers) when comparing neighbors
        if href == prev and "btn" not in (a.get("class") or []):
            a.unwrap()
            continue
        prev = href
    # Redundant alternative text: alt that repeats the visible caption → caption alone describes it.
    for fig in soup.select("main figure"):
        cap = fig.find("figcaption")
        if cap is None:
            continue
        ctext = text_of(cap).lower()
        for img in fig.find_all("img"):
            alt = img.get("alt", "").strip().lower().rstrip(".")
            if alt and (alt in ctext or ctext.startswith(alt[:40])):
                img["alt"] = ""
    return "<!DOCTYPE html>\n" + str(soup).replace("<!DOCTYPE html>", "", 1).lstrip()


def split_first_paragraph(nodes):
    for i, n in enumerate(nodes):
        if isinstance(n, Tag) and n.name == "p" and n.get_text(strip=True):
            return nodes_html(nodes[: i + 1]), nodes_html(nodes[i + 1:])
    return "", nodes_html(nodes)


def render_toc(items):
    out = ['<ol class="toc__list">']
    for sid, title, subs in items:
        if subs:
            sub = "".join(f'<li><a href="#{esc(i)}">{esc(t)}</a></li>' for i, t in subs)
            out.append(f'<li class="toc__item has-subs"><div class="toc__row"><a href="#{esc(sid)}">{esc(title)}</a>'
                       f'<button class="toc__toggle" type="button" aria-expanded="false" aria-label="Show subsections of {esc(title)}"><span aria-hidden="true"></span></button></div>'
                       f'<ol class="toc__sub">{sub}</ol></li>')
        else:
            out.append(f'<li class="toc__item"><a href="#{esc(sid)}">{esc(title)}</a></li>')
    out.append("</ol>")
    return "".join(out)


def image_url(file, width):
    name = file[5:].replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(name)}?width={width}"


def credit_html(meta):
    if not meta:
        return ""
    who = esc(shorten(meta.get("artist") or "Unknown author", 60))
    lic = esc(meta.get("license") or "see file page")
    if meta.get("license_url"):
        lic = f'<a href="{esc(meta["license_url"])}">{lic}</a>'
    return f"{who}, {lic}"


# ---------------------------------------------------------------------------
# Homepage (daily featured-content snapshot)
# ---------------------------------------------------------------------------
def feed_html(fragment, prefix):
    """Sanitize feed HTML: keep links/bold/italics, rewrite hrefs."""
    s = BeautifulSoup(re.sub(r"<!--.*?-->", "", fragment or ""), "html.parser")
    for el in s.find_all(True):
        if el.name == "a":
            el.attrs = {"href": wiki_href(el.get("href", ""), prefix)}
        elif el.name in ("b", "i", "em", "strong"):
            el.attrs = {}
        else:
            el.unwrap()
    return str(s)


def build_home(articles):
    today = dt.date.today()
    print("• homepage: fetching featured feed")
    r = SESSION.get(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{today:%Y/%m/%d}", timeout=90)
    r.raise_for_status()
    d = r.json()
    prefix = ""
    date_str = today.strftime("%A, %B %-d, %Y")

    tfa = d.get("tfa") or {}
    tfa_title = tfa.get("titles", {}).get("normalized", "")
    tfa_html = f'''<article class="card card--feature" aria-labelledby="tfa-title">
  <p class="card__kicker">Today's featured article</p>
  <h3 id="tfa-title" class="card__title"><a href="{WIKI + urllib.parse.quote(tfa_title.replace(" ", "_"))}">{esc(tfa_title)}</a></h3>
  <p class="card__desc">{esc(tfa.get("description", "").capitalize())}</p>
  <p>{esc(shorten(tfa.get("extract", ""), 520))}</p>
  <p class="card__source">From Wikipedia's front page</p>
</article>''' if tfa_title else ""

    news = "".join(f"<li>{feed_html(n.get('story'), prefix)}</li>" for n in (d.get("news") or [])[:5])
    otd = "".join(f'<li><span class="year">{o["year"]}</span><span>{esc(o["text"])}</span></li>' for o in (d.get("onthisday") or [])[:5])
    most = [a for a in (d.get("mostread") or {}).get("articles", []) if a.get("type", "standard") == "standard"][:8]
    most_html = "".join(f'<li><a href="{WIKI + urllib.parse.quote(a["titles"]["canonical"])}">{esc(a["titles"]["normalized"])}</a>'
                        f'<span class="meta">{a.get("views", 0):,} views</span></li>' for a in most)

    pic = d.get("image") or {}
    pic_html = ""
    if pic.get("title"):
        info = fetch_image_info([pic["title"]]).get(pic["title"], {})
        alt = shorten(re.sub(r"\.(jpe?g|png)\b", "", strip_tags((pic.get("description") or {}).get("text", "")) or info.get("desc", "")), 95)
        pic_html = f'''<figure class="potd">
  <img src="{esc(image_url(pic["title"], 960))}" alt="{esc(alt)}" width="960" height="640" loading="lazy" decoding="async">
  <figcaption><strong>Picture of the day.</strong> {esc(shorten(strip_tags((pic.get("description") or {}).get("text", "")), 220))} <span class="credit">{credit_html(info)}</span></figcaption>
</figure>'''

    redesigned = "".join(f'''<li class="card card--article">
  <p class="card__kicker">Redesigned article · {a["words"]:,} words</p>
  <h3 class="card__title"><a href="wiki/{a["slug"]}.html">{esc(a["title"])}</a></h3>
  <p class="card__desc">{esc(a["desc"])}</p>
</li>''' for a in articles)

    topics = [("Arts", "Portal:The_arts"), ("Biography", "Portal:Biography"), ("Geography", "Portal:Geography"),
              ("History", "Portal:History"), ("Mathematics", "Portal:Mathematics"), ("Science", "Portal:Science"),
              ("Society", "Portal:Society"), ("Sports", "Portal:Sports"), ("Technology", "Portal:Technology")]
    topics_html = "".join(f'<li><a href="{WIKI}{p}">{t}</a></li>' for t, p in topics)

    body = f'''<main id="main" tabindex="-1">
  <section class="home-hero" aria-labelledby="home-title">
    <div class="home-hero__inner">
      <h1 id="home-title">The free encyclopedia, <span>easier to read.</span></h1>
      <p class="lede">Search more than 7 million English Wikipedia articles, then read them in a calmer layout with summaries first and details on demand.</p>
      {search_form(prefix, "home-q", big=True)}
      <p class="home-hero__try">Try: <a href="wiki/Golden_State_Warriors.html">Golden State Warriors</a> · <a href="wiki/Stephen_Curry.html">Stephen Curry</a> · <a href="search.html?q=Chase+Center">Chase Center</a></p>
    </div>
  </section>
  <div class="home">
    <section aria-labelledby="redesigned-title" class="home__section">
      <h2 id="redesigned-title">Redesigned articles</h2>
      <p class="section-desc">These pages are fully rebuilt in the new reading layout. Other links open the original article on Wikipedia.</p>
      <ul class="card-grid">{redesigned}</ul>
    </section>
    <div class="home__cols">
      <section aria-labelledby="today-title" class="home__section home__main">
        <h2 id="today-title">Today on Wikipedia <span class="meta">{date_str}</span></h2>
        {tfa_html}
        {pic_html}
      </section>
      <div class="home__side">
        <section aria-labelledby="news-title" class="home__section panel">
          <h2 id="news-title">In the news</h2>
          <ul class="news">{news}</ul>
        </section>
        <section aria-labelledby="otd-title" class="home__section panel">
          <h2 id="otd-title">On this day</h2>
          <ul class="otd">{otd}</ul>
        </section>
        <section aria-labelledby="most-title" class="home__section panel">
          <h2 id="most-title">Most read yesterday</h2>
          <ol class="most">{most_html}</ol>
        </section>
      </div>
    </div>
    <section aria-labelledby="topics-title" class="home__section">
      <h2 id="topics-title">Browse by topic</h2>
      <ul class="chips">{topics_html}</ul>
    </section>
    <p class="attribution">Featured content is a snapshot of Wikipedia's front page for {date_str}, used under CC BY-SA 4.0.</p>
  </div>
</main>'''
    (ROOT / "index.html").write_text(finalize_page(title=f"{SITE_NAME} Redesign: the free encyclopedia, easier to read",
                                          description="A usability and accessibility redesign of Wikipedia's reading experience.",
                                          body=body, prefix=prefix, active="home", header_search=False))
    print("  wrote index.html")


def finalize_page(**kw):
    return finalize(page(**kw))


def build_search():
    body = f'''<main id="main" tabindex="-1" class="search-page">
  <div class="search-page__head">
    <h1 id="search-title">Search</h1>
    {search_form("", "page-q", big=True)}
  </div>
  <div class="search-page__body">
    <p class="search-status" id="search-status" role="status" aria-live="polite">Type a word or phrase above, then press Enter.</p>
    <div id="search-notice"></div>
    <ol class="results" id="results" aria-labelledby="search-title"></ol>
    <div class="search-more"><button class="btn" type="button" id="more-results" hidden>Show more results</button></div>
    <section class="search-help" id="search-help" aria-labelledby="help-title">
      <h2 id="help-title">Search tips</h2>
      <ul>
        <li>Suggestions appear as you type. Use the arrow keys to move through them and Enter to open one.</li>
        <li>Misspelled words are corrected automatically, and you can always search for your original spelling instead.</li>
        <li>Put words in quotes to match an exact phrase, for example <a href="search.html?q=%22Run+TMC%22">“Run TMC”</a>.</li>
        <li>Articles marked <span class="badge badge--local">Redesigned</span> open in this site's reading layout. Others open on Wikipedia.</li>
      </ul>
    </section>
  </div>
</main>'''
    local = {ARTICLES_TITLES.get(s, s.replace("_", " ")): f"wiki/{s}.html" for s in ARTICLES}
    extra = f'<script>window.LOCAL_ARTICLES={json.dumps(local)};</script>'
    (ROOT / "search.html").write_text(page(title=f"Search | {SITE_NAME} Redesign", description="Search the encyclopedia.",
                                           body=body, prefix="", active="search", header_search=False, extra_head=extra))
    print("  wrote search.html")


def build_404():
    body = f'''<main id="main" tabindex="-1" class="notfound">
  <p class="eyebrow">Error 404</p>
  <h1>We couldn't find that page</h1>
  <p class="lede">The address may be mistyped, or the page may have moved. Try searching for the article instead.</p>
  {search_form(BASE, "nf-q", big=True)}
  <div><a class="btn" href="{BASE}index.html">Go to the homepage</a></div>
</main>'''
    html_ = page(title=f"Page not found | {SITE_NAME} Redesign", description="Page not found.", body=body, prefix=BASE, header_search=False)
    (ROOT / "404.html").write_text(html_)
    print("  wrote 404.html")


ARTICLES_TITLES = {}


def main():
    built = []
    for slug in ARTICLES:
        r = build_article(slug)
        ARTICLES_TITLES[slug] = r["title"]
        built.append(r)
    build_home(built)
    build_search()
    build_404()
    print("done")


if __name__ == "__main__":
    sys.exit(main())
