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
</style>
</head>
<body>
<nav>{nav}</nav>
<main>{body}
<hr><p><small><a href="{edit}">Edit this page in the wiki</a></small></p></main>
</body>
</html>
"""

LINK = re.compile(r'href="([^"#?:]+)((?:#[^"]*)?)"')


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
    nav = render(side.read_text(encoding="utf-8"))[0] if side.exists() else ""
    names = []
    for src in sorted(wiki.glob("*.md")):
        if src.name.startswith("_"):
            continue
        name = src.stem
        body, toc = render(src.read_text(encoding="utf-8"))
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
            edit=f"https://github.com/{repo}/wiki/{quote(name)}",
        )
        (out / f"{slug}.html").write_text(page, encoding="utf-8")
        names.append(slug)
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
