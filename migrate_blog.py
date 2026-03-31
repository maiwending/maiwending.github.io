"""
Migrate personal blog posts from the Publii HTML output (maiwending_personal_backup)
to Hugo Blox blog Markdown files.

Usage:
    python migrate_blog.py
"""

import os
import re
import html
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SOURCE_DIR = Path("D:/Github/maiwending_personal_backup")
OUTPUT_DIR = Path("D:/Github/maiwending.github.io/content/blog")

SKIP_DIRS = {"assets", "media", "authors", "tags", "page", "amp", "test"}


def extract_meta(content: str) -> dict:
    result = {}

    m = re.search(r'"headline"\s*:\s*"([^"]+)"', content)
    if m:
        result["title"] = html.unescape(m.group(1))

    m = re.search(r'"datePublished"\s*:\s*"([^"T]+)', content)
    if m:
        result["date"] = m.group(1).strip()

    m = re.search(r'<meta name="description" content="([^"]+)"', content)
    if m:
        result["summary"] = html.unescape(m.group(1))

    # Tags from /tags/<slug>/ links
    result["raw_tags"] = list(set(re.findall(
        r'href="[^"]+/tags/([^/"]+)/"', content
    )))

    # Extract article body text from post__entry div
    body_match = re.search(
        r'class="(?:wrapper )?post__entry"[^>]*>(.*?)</div>\s*<footer',
        content, re.DOTALL
    )
    if body_match:
        raw_html = body_match.group(1)
        # Convert <p> tags to paragraphs, strip all other HTML
        text = re.sub(r'<p[^>]*>', '\n\n', raw_html)
        text = re.sub(r'</p>', '', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text).strip()
        result["body"] = text

    return result


def build_markdown(slug: str, meta: dict) -> str:
    title = meta.get("title", slug.replace("-", " ").title())
    date = meta.get("date", "2021-01-01")
    summary = meta.get("summary", "")
    body = meta.get("body", "")
    tags = [t for t in meta.get("raw_tags", []) if t not in {""}]

    title_safe = title.replace("'", "''")
    summary_safe = summary.replace("'", "''")

    tags_yaml = ""
    if tags:
        tags_yaml = "tags:\n" + "".join(f"  - {t}\n" for t in tags)

    fm = f"""---
title: '{title_safe}'
date: '{date}T00:00:00Z'
summary: '{summary_safe}'
{tags_yaml}
---

{body}
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

        if '"@type":"Article"' not in content:
            skipped += 1
            continue

        meta = extract_meta(content)
        if not meta.get("title"):
            print(f"  [WARN] No title in {entry.name}, skipping")
            skipped += 1
            continue

        out_dir = OUTPUT_DIR / entry.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.md"
        out_file.write_text(build_markdown(entry.name, meta), encoding="utf-8")
        print(f"  [OK] {meta['title'][:60]}")
        migrated += 1

    print(f"\nDone: {migrated} posts migrated, {skipped} skipped.")


if __name__ == "__main__":
    migrate()
