#!/usr/bin/env python3
"""
Auto-update the 4LLab publications page from OpenAlex.

What it does
------------
* Reads scripts/authors.json for the staff ORCIDs / OpenAlex IDs.
* Fetches each author's works from OpenAlex (>= start_year).
* De-duplicates across authors (by DOI, then by normalised title).
* Skips any paper whose title already appears in publications.html
  (so your manually-curated entries and their local [PDF] links are never touched).
* Inserts only the NEW papers at the top of the BibTeX block, tagged with the date.
* Regenerates publications.rss from the full list.

It is intentionally append-only: it never edits or removes existing entries.

Usage:  python scripts/update_publications.py
Env:    OPENALEX_MAILTO   (optional) an email for the OpenAlex "polite pool" — faster, nicer.
"""

import json, os, re, sys, time, html, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB_HTML = os.path.join(ROOT, "publications.html")
RSS = os.path.join(ROOT, "publications.rss")
CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authors.json")
ANCHOR = '<textarea id="bibtex_input" style="display:none;">'
MAILTO = os.environ.get("OPENALEX_MAILTO", "")

# ----------------------------------------------------------------- helpers
def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())

def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "4LLab-pub-updater/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def openalex_filter(author):
    if author.get("orcid"):
        return "author.orcid:" + author["orcid"].strip()
    if author.get("openalex"):
        return "author.id:" + author["openalex"].strip().split("/")[-1]
    return None

def fetch_author_works(author, start_year):
    filt = openalex_filter(author)
    if not filt:
        print("  ! skipping %s (no orcid/openalex id)" % author.get("name"))
        return []
    works, cursor = [], "*"
    base = "https://api.openalex.org/works"
    flt = "%s,from_publication_date:%d-01-01" % (filt, start_year)
    while cursor:
        params = {"filter": flt, "per-page": "200", "cursor": cursor}
        if MAILTO:
            params["mailto"] = MAILTO
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            data = http_json(url)
        except Exception as e:
            print("  ! OpenAlex error for %s: %s" % (author.get("name"), e))
            break
        works.extend(data.get("results", []))
        cursor = data.get("meta", {}).get("next_cursor")
        time.sleep(0.3)
    print("  + %s: %d works" % (author.get("name"), len(works)))
    return works

# ----------------------------------------------------------- bibtex output
def bib_key(authorships, year):
    last = "anon"
    if authorships:
        nm = authorships[0].get("author", {}).get("display_name", "").split()
        if nm:
            last = re.sub(r"[^A-Za-z]", "", nm[-1]).lower()
    return "%s%s" % (last, year or "")

def work_to_bibtex(w):
    title = (w.get("title") or "").strip()
    if not title:
        return None
    year = w.get("publication_year") or ""
    authors = " and ".join(
        a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])
        if a.get("author", {}).get("display_name")
    )
    loc = (w.get("primary_location") or {}).get("source") or {}
    venue = (loc.get("display_name") or "").strip()
    bib = w.get("biblio") or {}
    wtype = w.get("type") or "article"
    is_conf = wtype in ("proceedings-article",) or "conference" in venue.lower() or "proceedings" in venue.lower()
    entry_type = "inproceedings" if is_conf else "article"
    venue_field = "booktitle" if is_conf else "journal"
    doi = w.get("doi") or ""

    def esc(s):  # escape for bibtex braces/specials minimally
        return (s or "").replace("{", "").replace("}", "")

    lines = ["@%s{%s," % (entry_type, bib_key(w.get("authorships"), year))]
    lines.append("  title={%s}," % esc(title))
    if authors: lines.append("  author={%s}," % esc(authors))
    if venue:   lines.append("  %s={%s}," % (venue_field, esc(venue)))
    if bib.get("volume"):     lines.append("  volume={%s}," % bib["volume"])
    if bib.get("issue"):      lines.append("  number={%s}," % bib["issue"])
    if bib.get("first_page"):
        pages = bib["first_page"] + ("--" + bib["last_page"] if bib.get("last_page") else "")
        lines.append("  pages={%s}," % pages)
    if year: lines.append("  year={%s}," % year)
    if doi:  lines.append("  doi={%s}," % doi.replace("https://doi.org/", ""))
    lines.append("}")
    return "\n".join(lines)

# ----------------------------------------------------------------- RSS
def rebuild_rss(textarea_text):
    blocks = re.split(r"(?=@\w+\s*\{)", textarea_text)
    items = []
    for b in blocks:
        t = re.search(r"title\s*=\s*\{([^}]*)\}", b, re.I)
        if not t:
            continue
        title = re.sub(r"\s+", " ", t.group(1)).strip()
        au = re.search(r"author\s*=\s*\{([^}]*)\}", b, re.I)
        yr = re.search(r"year\s*=\s*\{?\s*(\d{4})", b, re.I)
        ven = re.search(r"(journal|booktitle)\s*=\s*\{([^}]*)\}", b, re.I)
        if not yr:
            continue
        items.append((int(yr.group(1)), title,
                      au.group(1).strip() if au else "",
                      ven.group(2).strip() if ven else ""))
    items.sort(key=lambda x: -x[0])
    items = items[:25]
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    def esc(x): return html.escape(x, quote=True)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<rss version=\"2.0\"><channel>",
           "<title>4LLab Data Analytics Group — Publications</title>",
           "<link>https://4llab.net/publications.html</link>",
           "<description>Recent publications from the 4LLab Data Analytics Group, Adelaide University.</description>",
           "<language>en</language>", "<lastBuildDate>%s</lastBuildDate>" % now]
    for yr, title, au, ven in items:
        desc = ", ".join(x for x in [au, ven, str(yr)] if x)
        out.append("<item><title>%s</title><description>%s</description><pubDate>%s</pubDate></item>"
                   % (esc(title), esc(desc), now))
    out.append("</channel></rss>")
    with open(RSS, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

# ----------------------------------------------------------------- main
def main():
    with open(CONF, encoding="utf-8") as f:
        conf = json.load(f)
    start_year = int(conf.get("start_year", 2015))

    with open(PUB_HTML, encoding="utf-8") as f:
        page = f.read()
    if ANCHOR not in page:
        print("ERROR: could not find the BibTeX textarea anchor in publications.html")
        sys.exit(1)
    ta = page.split(ANCHOR, 1)[1].split("</textarea>", 1)[0]
    existing = {norm_title(m) for m in re.findall(r"title\s*=\s*\{([^}]*)\}", ta, re.I)}
    print("Existing entries: %d" % len(existing))

    # gather + dedup
    seen_doi, seen_title, new_entries = set(), set(), []
    for a in conf.get("authors", []):
        for w in fetch_author_works(a, start_year):
            doi = (w.get("doi") or "").lower()
            nt = norm_title(w.get("title"))
            if not nt or nt in existing or nt in seen_title:
                continue
            if doi and doi in seen_doi:
                continue
            bib = work_to_bibtex(w)
            if not bib:
                continue
            seen_title.add(nt)
            if doi:
                seen_doi.add(doi)
            new_entries.append(bib)

    print("New papers to add: %d" % len(new_entries))
    if not new_entries:
        rebuild_rss(ta)
        print("No new papers. RSS refreshed.")
        return

    stamp = datetime.now().strftime("%Y-%m-%d")
    block = "\n\n%% auto-added %s\n" % stamp + "\n\n".join(new_entries) + "\n"
    page = page.replace(ANCHOR, ANCHOR + block, 1)
    with open(PUB_HTML, "w", encoding="utf-8") as f:
        f.write(page)

    new_ta = page.split(ANCHOR, 1)[1].split("</textarea>", 1)[0]
    rebuild_rss(new_ta)
    print("Done: added %d papers and refreshed publications.rss" % len(new_entries))

if __name__ == "__main__":
    main()
