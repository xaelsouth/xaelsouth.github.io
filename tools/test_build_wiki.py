import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import build_wiki


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_nav = False
        self.nav_links = []
        self.heading_ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.in_nav = True
        elif tag == "a" and self.in_nav:
            self.nav_links.append(attrs.get("href"))
        elif tag in {"h2", "h3", "h4", "h5", "h6"} and not self.in_nav:
            self.heading_ids.append(attrs.get("id"))

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_nav = False


class WikiNavigationTest(unittest.TestCase):
    def test_article_headings_and_sidebar_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            out = Path(tmp) / "out"
            wiki.mkdir()
            (wiki / "_Sidebar.md").write_text("[Home](Home)\n[Other](Other)", encoding="utf-8")
            (wiki / "Home.md").write_text(
                "# Title\n\n## First\n\n### Child\n\n## First\n\n"
                "```text\n## Not a heading\n```\n",
                encoding="utf-8",
            )
            (wiki / "Other.md").write_text(
                "# Other\n\n<!-- tags: C++, C#, linux, Linux -->\n\nNo subheadings.\n",
                encoding="utf-8",
            )

            build_wiki.main(wiki, out, "owner/repo")

            page = PageParser()
            page.feed((out / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(page.heading_ids, ["first", "child", "first_1"])
            self.assertEqual(
                page.nav_links,
                ["tags.html", "index.html", "Other.html", "#first", "#child", "#first_1"],
            )
            other_html = (out / "Other.html").read_text(encoding="utf-8")
            other = PageParser()
            other.feed(other_html)
            self.assertEqual(other.nav_links, ["tags.html", "index.html", "Other.html"])
            self.assertNotIn("On this page", other_html)
            self.assertNotIn("tags:", other_html)
            self.assertIn("https://github.com/owner/repo/wiki/Other", other_html)
            tags_html = (out / "tags.html").read_text(encoding="utf-8")
            self.assertIn('id="c"', tags_html)
            self.assertIn('id="c-2"', tags_html)
            self.assertIn('aria-label="C#: 1 article"', tags_html)
            self.assertIn("linux <span class=\"tag-count\">(1)</span>", tags_html)
            self.assertIn("Other", tags_html)
            self.assertIn("tags.html", (out / "sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
