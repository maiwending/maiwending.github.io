"""
Migrate academic papers from the Publii HTML output (wdmai.github.io)
to Hugo Blox publication Markdown files.

Usage:
    python migrate_papers.py

Output: content/publications/<slug>/index.md for each paper found.
"""

import os
import re
import json
import html
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SOURCE_DIR = Path("D:/Github/wdmai.github.io")
OUTPUT_DIR = Path("D:/Github/maiwending.github.io/content/publications")

# Directories to skip (not papers)
SKIP_DIRS = {
    "assets", "media", "authors", "tags", "page", "amp",
    "cv", "publication-list", "contact", "resume",
}

# Tag mapping: old Publii slug → new Hugo tag(s)
TAG_MAP = {
    "numerical-computation":    ["computational-em"],
    "knot-electromagnetics":    ["time-varying-em"],
    "knot":                     ["knot-em"],
    "metamaterials":            ["metamaterials"],
    "software-tools":           ["software-tools"],
    # publication-type tags
    "conferences":              [],   # handled as publication_type
    "journal-paper":            [],   # handled as publication_type
    "community-tools":          ["community-tools"],
}

PUB_TYPE_MAP = {
    "conferences":   "paper-conference",
    "journal-paper": "article-journal",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_meta(content: str) -> dict:
    """Extract all needed metadata from a Publii HTML page."""
    result = {}

    # Title from JSON-LD headline
    m = re.search(r'"headline"\s*:\s*"([^"]+)"', content)
    if m:
        result["title"] = html.unescape(m.group(1))

    # Abstract from meta description
    m = re.search(r'<meta name="description" content="([^"]+)"', content)
    if m:
        result["abstract"] = html.unescape(m.group(1))

    # Date from JSON-LD datePublished
    m = re.search(r'"datePublished"\s*:\s*"([^"T]+)', content)
    if m:
        result["date"] = m.group(1).strip()

    # Tags from /tags/<slug>/ links in the post__tag list
    result["raw_tags"] = re.findall(r'href="[^"]+/tags/([^/"]+)/"', content)

    # Authors from <pre> block (Publii puts author list there)
    m = re.search(r'<pre>([^<]+)</pre>', content)
    if m:
        raw = html.unescape(m.group(1)).strip()
        result["authors_raw"] = raw

    # "Read more" link — may be a bare DOI, a doi.org URL, or a direct paper URL
    m = re.search(r'<a href="([^"]+)"[^>]*>Read more</a>', content)
    if m:
        url = html.unescape(m.group(1)).strip()
        # Bare DOI: 10.xxxx/...
        if re.match(r'^10\.\d{4,}/', url):
            result["doi"] = url
        # doi.org URL: https://doi.org/10.xxxx/...
        elif re.match(r'^https?://doi\.org/(10\.\d{4,}/.+)', url):
            result["doi"] = re.match(r'^https?://doi\.org/(10\.\d{4,}/.+)', url).group(1)
        # Any other URL (IEEE, Optica, AIP, etc.)
        else:
            result["url"] = url

    # Publication venue: look for text after the abstract paragraph that mentions a journal/conference
    # (Not always present in Publii output — skip if missing)

    return result


def build_frontmatter(slug: str, meta: dict) -> str:
    title = meta.get("title", slug.replace("-", " ").title())
    abstract = meta.get("abstract", "")
    date = meta.get("date", "2021-01-01")
    doi = meta.get("doi", "")

    raw_tags = meta.get("raw_tags", [])
    content_tags = []
    pub_type = "article-journal"  # default

    for t in raw_tags:
        if t in PUB_TYPE_MAP:
            pub_type = PUB_TYPE_MAP[t]
        elif t in TAG_MAP:
            content_tags.extend(TAG_MAP[t])

    # Remove duplicates, keep order
    seen = set()
    content_tags = [x for x in content_tags if not (x in seen or seen.add(x))]

    authors_raw = meta.get("authors_raw", "")
    # Split by comma and "and", strip footnote markers (*, †, etc.)
    authors = [re.sub(r'^[\*†‡§]+\s*|\s*[\*†‡§]+$', '', a).strip()
               for a in re.split(r",\s*|\band\b", authors_raw) if a.strip()]
    authors = [a for a in authors if a]
    if not authors:
        authors = ["Dr. Wending Mai"]

    # Escape title for YAML (wrap in quotes, escape inner quotes)
    title_safe = title.replace("'", "''")

    tags_yaml = ""
    if content_tags:
        tags_yaml = "tags:\n" + "".join(f"  - {t}\n" for t in content_tags)

    authors_yaml = "authors:\n" + "".join(f"  - {a}\n" for a in authors)

    url = meta.get("url", "")

    doi_section = ""
    if doi:
        doi_section = f"""hugoblox:
  ids:
    doi: {doi}
"""

    url_section = ""
    if url and not doi:
        url_section = f"""links:
  - name: Paper
    url: {url}
"""

    fm = f"""---
title: '{title_safe}'
{authors_yaml}
date: '{date}T00:00:00Z'
publishDate: '{date}T00:00:00Z'

publication_types: ['{pub_type}']

abstract: '{abstract.replace(chr(39), chr(39)+chr(39))}'

{tags_yaml}
featured: false
{doi_section}{url_section}
---
"""
    return fm


def migrate():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    migrated = 0
    skipped = 0

    for entry in sorted(SOURCE_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS:
            continue

        html_file = entry / "index.html"
        if not html_file.exists():
            continue

        content = html_file.read_text(encoding="utf-8", errors="ignore")

        # Skip if it looks like a tag/list page (no article JSON-LD)
        if '"@type":"Article"' not in content:
            skipped += 1
            continue

        meta = extract_meta(content)
        if not meta.get("title"):
            print(f"  [WARN] No title found in {entry.name}, skipping")
            skipped += 1
            continue

        out_dir = OUTPUT_DIR / entry.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.md"

        fm = build_frontmatter(entry.name, meta)
        out_file.write_text(fm, encoding="utf-8")
        print(f"  [OK] {entry.name}")
        migrated += 1

    print(f"\nDone: {migrated} papers migrated, {skipped} skipped.")


if __name__ == "__main__":
    migrate()
