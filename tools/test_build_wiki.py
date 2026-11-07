import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

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
                "# Other\n\n<!-- read-time: 5 minutes -->\n"
                "<!-- tags: C++, C#, linux, Linux -->\n\nNo subheadings.\n",
                encoding="utf-8",
            )

            build_wiki.main(wiki, out, "owner/repo")

            page = PageParser()
            home_html = (out / "index.html").read_text(encoding="utf-8")
            page.feed(home_html)
            self.assertEqual(page.heading_ids, ["first", "child", "first_1"])
            self.assertEqual(
                page.nav_links,
                ["tags.html", "index.html", "Other.html", "#first", "#child", "#first_1"],
            )
            home_timestamp = re.search(
                r'Page generated: <time datetime="([^"]+)">([^<]+)</time>',
                home_html,
            )
            self.assertIsNotNone(home_timestamp)
            self.assertEqual(home_timestamp[1], home_timestamp[2])
            generated_at = datetime.fromisoformat(home_timestamp[1])
            self.assertEqual(generated_at.utcoffset(), timedelta(0))
            other_html = (out / "Other.html").read_text(encoding="utf-8")
            other = PageParser()
            other.feed(other_html)
            self.assertEqual(other.nav_links, ["tags.html", "index.html", "Other.html"])
            self.assertNotIn("On this page", other_html)
            self.assertNotIn("tags:", other_html)
            self.assertNotIn("read-time:", other_html)
            self.assertIn(
                '</h1><p class="page-meta">Estimated reading time: 5 minutes '
                f'&middot; Page generated: <time datetime="{home_timestamp[1]}">'
                f"{home_timestamp[1]}</time></p>",
                other_html,
            )
            self.assertEqual(generated_at.tzinfo, timezone.utc)
            self.assertIn(
                '<meta name="description" content="Other No subheadings.',
                other_html,
            )
            self.assertIn("https://github.com/owner/repo/wiki/Other", other_html)
            tags_html = (out / "tags.html").read_text(encoding="utf-8")
            self.assertIn('id="c"', tags_html)
            self.assertIn('id="c-2"', tags_html)
            self.assertIn('aria-label="C#: 1 article"', tags_html)
            self.assertIn("linux <span class=\"tag-count\">(1)</span>", tags_html)
            self.assertIn("Other", tags_html)
            self.assertIn("tags.html", (out / "sitemap.xml").read_text(encoding="utf-8"))

    def test_incremental_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            out = Path(tmp) / "out"
            wiki.mkdir()
            home = wiki / "Home.md"
            other = wiki / "Other.md"
            sidebar = wiki / "_Sidebar.md"
            home.write_text("# Home\n\nHome content.\n", encoding="utf-8")
            other.write_text(
                "# Other\n\n<!-- tags: Linux -->\n\nOther content.\n", encoding="utf-8"
            )
            sidebar.write_text("[Home](Home)\n", encoding="utf-8")

            def build(day):
                with patch.object(build_wiki, "datetime", wraps=datetime) as clock:
                    clock.now.return_value = datetime(2026, 11, day, tzinfo=timezone.utc)
                    build_wiki.main(wiki, out, "owner/repo")

            build(1)
            original = {
                path.name: path.read_bytes()
                for path in out.iterdir() if path.is_file()
            }
            build(2)
            self.assertEqual(original, {
                path.name: path.read_bytes()
                for path in out.iterdir() if path.is_file()
            })

            other.write_text(other.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
            build(3)
            self.assertEqual((out / "index.html").read_bytes(), original["index.html"])
            self.assertEqual((out / "tags.html").read_bytes(), original["tags.html"])
            self.assertIn("2026-11-03T00:00:00+00:00", (out / "Other.html").read_text())
            dates = build_wiki.sitemap_dates(out / "sitemap.xml")
            self.assertEqual(dates[build_wiki.BASE_URL], "2026-11-01")
            self.assertEqual(dates[build_wiki.BASE_URL + "Other.html"], "2026-11-03")
            self.assertEqual(dates[build_wiki.BASE_URL + "tags.html"], "2026-11-01")

            sidebar.write_text("[Other](Other)\n", encoding="utf-8")
            build(4)
            self.assertIn("2026-11-04T00:00:00+00:00", (out / "index.html").read_text())
            self.assertIn("2026-11-04T00:00:00+00:00", (out / "Other.html").read_text())
            self.assertIn('href="Other.html"', (out / "tags.html").read_text())

            other.unlink()
            build(5)
            self.assertFalse((out / "Other.html").exists())
            self.assertIn("No article tags have been added yet.", (out / "tags.html").read_text())
            self.assertNotIn(build_wiki.BASE_URL + "Other.html", build_wiki.sitemap_dates(out / "sitemap.xml"))

    def test_tag_only_edits_update_tags_without_regenerating_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            out = Path(tmp) / "out"
            wiki.mkdir()
            article = wiki / "Home.md"

            def build(day):
                with patch.object(build_wiki, "datetime", wraps=datetime) as clock:
                    clock.now.return_value = datetime(2026, 11, day, tzinfo=timezone.utc)
                    build_wiki.main(wiki, out, "owner/repo")

            article.write_text("# Home\n\nHome content.\n", encoding="utf-8")
            build(1)
            original_article = (out / "index.html").read_bytes()

            for day, tag in [(2, "Linux"), (3, "Embedded")]:
                article.write_text(
                    f"# Home\n\n<!-- tags: {tag} -->\n\nHome content.\n", encoding="utf-8"
                )
                build(day)
                self.assertEqual((out / "index.html").read_bytes(), original_article)
                tags_html = (out / "tags.html").read_text(encoding="utf-8")
                self.assertIn(f'aria-label="{tag}: 1 article"', tags_html)
                dates = build_wiki.sitemap_dates(out / "sitemap.xml")
                self.assertEqual(dates[build_wiki.BASE_URL], "2026-11-01")
                self.assertEqual(dates[build_wiki.BASE_URL + "tags.html"], f"2026-11-0{day}")

            article.write_text("# Home\n\nHome content.\n", encoding="utf-8")
            build(4)
            self.assertEqual((out / "index.html").read_bytes(), original_article)
            self.assertIn(
                "No article tags have been added yet.",
                (out / "tags.html").read_text(encoding="utf-8"),
            )
            dates = build_wiki.sitemap_dates(out / "sitemap.xml")
            self.assertEqual(dates[build_wiki.BASE_URL], "2026-11-01")
            self.assertEqual(dates[build_wiki.BASE_URL + "tags.html"], "2026-11-04")


if __name__ == "__main__":
    unittest.main()
