#!/usr/bin/env python3
"""Render the GitHub wiki (Markdown) into static, crawlable HTML."""
import html
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

import markdown

BASE_URL = "https://xaelsouth.github.io/"
SITE = "xaelsouth.github.io"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<style>
body{{font:16px/1.6 system-ui,sans-serif;margin:0;display:flex;flex-wrap:wrap}}
nav{{flex:0 0 14em;padding:1em 1.5em;background:#f6f8fa;
    position:sticky;top:0;max-height:100vh;overflow-y:auto;box-sizing:border-box}}
nav ul{{padding-left:1.2em}}
main{{flex:1 1 30em;max-width:60em;padding:1em 2em}}
pre{{background:#f6f8fa;padding:1em;overflow:auto}}
code{{background:#f6f8fa}}table{{border-collapse:collapse}}
td,th{{border:1px solid #d0d7de;padding:.3em .6em}}img{{max-width:100%}}
@media(max-width:700px){{
  nav{{flex-basis:100%;position:static;max-height:none}}
  main{{min-width:0;padding:1em}}
}}
.tag-cloud{{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35em 1em}}
.tag-cloud a{{text-decoration:none}}
.tag-cloud a:hover{{text-decoration:underline}}
.tag-count{{font-size:.7em;color:#57606a}}
</style>
</head>
<body>
<nav>{nav}</nav>
<main>{body}
{footer}</main>
</body>
</html>
"""

LINK = re.compile(r'href="([^"#?:]+)((?:#[^"]*)?)"')
TAGS = re.compile(r"<!--\s*tags:\s*(.*?)\s*-->\s*", re.I | re.S)


def extract_tags(text):
    match = TAGS.search(text)
    if not match:
        return [], text
    tags = []
    seen = set()
    for tag in match[1].split(","):
        tag = tag.strip()
        if tag and tag.casefold() not in seen:
            tags.append(tag)
            seen.add(tag.casefold())
    return tags, text[:match.start()] + text[match.end():]


def tag_id(tag):
    return re.sub(r"[^a-z0-9]+", "-", tag.casefold()).strip("-") or "tag"


def render_tag_page(articles):
    by_tag = {}
    for slug, title, tags in articles:
        for tag in tags:
            by_tag.setdefault(tag.casefold(), (tag, []))[1].append((slug, title))

    tags = sorted(by_tag.values(), key=lambda item: item[0].casefold())
    ids = {}
    used_ids = set()
    for tag, _ in tags:
        base = tag_id(tag)
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        ids[tag.casefold()] = candidate
        used_ids.add(candidate)

    counts = [len(articles) for _, articles in tags]
    minimum, maximum = min(counts, default=0), max(counts, default=0)
    cloud = []
    sections = []
    for tag, articles in tags:
        count = len(articles)
        size = 1.0 if maximum == minimum else 1.0 + 0.8 * (count - minimum) / (maximum - minimum)
        anchor = ids[tag.casefold()]
        article_label = "article" if count == 1 else "articles"
        cloud.append(
            f'<a href="#{anchor}" style="font-size:{size:.2f}em" '
            f'aria-label="{html.escape(tag)}: {count} {article_label}">'
            f'{html.escape(tag)} <span class="tag-count">({count})</span></a>'
        )
        links = "".join(
            f'<li><a href="{quote(slug)}.html">{html.escape(title)}</a></li>'
            for slug, title in articles
        )
        sections.append(
            f'<section><h2 id="{anchor}">{html.escape(tag)} '
            f'<small>({count})</small></h2><ul>{links}</ul></section>'
        )

    if cloud:
        body = (
            "<h1>Tags</h1><p>Browse articles by topic. Larger tags appear on more articles.</p>"
            f'<div class="tag-cloud" aria-label="Article tags">{"".join(cloud)}</div>'
            f'{"".join(sections)}'
        )
    else:
        body = "<h1>Tags</h1><p>No article tags have been added yet.</p>"
    return body


def render(text):
    text = re.sub(
        r"\[\[([^\]|]+)\|([^\]]+)\]\]", lambda m: f"[{m[1]}]({m[2].strip().replace(' ', '-')})", text
    )
    text = re.sub(
        r"\[\[([^\]]+)\]\]", lambda m: f"[{m[1]}]({m[1].strip().replace(' ', '-')})", text
    )
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-6"}},
    )
    out = md.convert(text)
    # Wiki-relative links -> .html (leave files like images/pdfs alone)
    out = LINK.sub(
        lambda m: m[0]
        if re.search(r"\.[A-Za-z0-9]{2,5}$", m[1])
        else f'href="{"index" if m[1] == "Home" else m[1]}.html{m[2]}"',
        out,
    )
    return out, md.toc if md.toc_tokens else ""


def first_text(body):
    plain = re.sub(r"<[^>]+>", " ", body)
    return html.escape(" ".join(plain.split())[:160], quote=True)


def main(wiki, out, repo):
    wiki, out = Path(wiki), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.html"):
        old.unlink()
    side = wiki / "_Sidebar.md"
    nav = '<p><a href="tags.html">Browse tags</a></p>'
    nav += render(side.read_text(encoding="utf-8"))[0] if side.exists() else ""
    names = []
    articles = []
    for src in sorted(wiki.glob("*.md")):
        if src.name.startswith("_"):
            continue
        name = src.stem
        tags, source = extract_tags(src.read_text(encoding="utf-8"))
        body, toc = render(source)
        page_nav = nav
        if toc:
            page_nav += '<section aria-label="On this page"><h3>On this page</h3>' + toc + "</section>"
        m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
        title = re.sub(r"<[^>]+>", "", m[1]) if m else name.replace("-", " ")
        slug = "index" if name == "Home" else name
        page = PAGE.format(
            title=html.escape(f"{title} – {SITE}"),
            description=first_text(body),
            canonical=BASE_URL + ("" if slug == "index" else quote(slug) + ".html"),
            nav=page_nav,
            body=body,
            footer=(
                '<hr><p><small><a href="'
                f'https://github.com/{repo}/wiki/{quote(name)}'
                '">Edit this page in the wiki</a></small></p>'
            ),
        )
        (out / f"{slug}.html").write_text(page, encoding="utf-8")
        names.append(slug)
        if tags:
            articles.append((slug, title, tags))

    tags_page = PAGE.format(
        title=html.escape(f"Tags – {SITE}"),
        description="Browse wiki articles by topic.",
        canonical=BASE_URL + "tags.html",
        nav=nav,
        body=render_tag_page(articles),
        footer=(
            '<hr><p><small>Article tags are maintained in the '
            f'<a href="https://github.com/{repo}/wiki">GitHub wiki</a>.'
            "</small></p>"
        ),
    )
    (out / "tags.html").write_text(tags_page, encoding="utf-8")
    names.append("tags")
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{BASE_URL}{'' if s == 'index' else quote(s) + '.html'}</loc>"
        f"<lastmod>{today}</lastmod></url>\n"
        for s in names
    )
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
    )
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n")
    (out / ".nojekyll").touch()
    print(f"Rendered {len(names)} pages")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "xaelsouth/xaelsouth.github.io")
