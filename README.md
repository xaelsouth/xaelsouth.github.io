My personal notes can be found in [Wiki](https://github.com/xaelsouth/xaelsouth.github.io/wiki).

The wiki is published as HTML on GitHub Pages. `_Sidebar.md` supplies the
article links, and each page automatically lists its own subheadings in the
navigation. A tags cloud is generated at [Tags](https://xaelsouth.github.io/tags.html).

Add a comma-separated `tags` HTML comment to an article to include it in the
cloud, for example:

```markdown
<!-- tags: embedded, Linux, i.MX23 -->
```

Add a `read-time` comment to show an estimated reading time below the article
title:

```markdown
<!-- read-time: 25 minutes -->
```

Both comments are consumed by the site generator and do not appear in the
published article. The generator displays its UTC build time in ISO 8601 format
below each article title. It preserves unchanged pages and their timestamps;
changes to shared navigation or layout update all affected pages. The tags page
and sitemap are updated when needed, and removed wiki pages are removed from
the site. Edit the articles in the wiki as usual.
