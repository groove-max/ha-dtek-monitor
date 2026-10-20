# Maintaining the documentation website

The published site is [DTEK Monitor documentation](https://groove-max.github.io/ha-dtek-monitor/).
Ukrainian lives under `/uk/`; English under `/en/`. The project root opens Ukrainian.

## Content and preview

Edit the existing `README*.md` and `docs/*.md` user guides. `pages.json` selects the
published guides and supplies translated navigation labels, search titles and
descriptions. Each guide is copied into a temporary build directory; there is no
second manually maintained copy of its content. Other repository files stay on
GitHub, including contributor instructions, source examples and license texts.

```sh
python -m pip install -r website/requirements.txt
python scripts/build_docs.py
python scripts/check_docs.py
```

The build creates `build/docs/`. Serve it at `/ha-dtek-monitor/` when previewing,
so that the project-relative asset URLs match GitHub Pages. Generated files are
ignored by Git. The checker validates all 12 content pages, internal links and
anchors, images, page languages, canonical URLs, alternate-language links and the
sitemap. Translation clusters use reciprocal `hreflang` entries in the sitemap;
the visible language links are rendered in HTML. Both locale builds run in strict mode.

The **Documentation** workflow builds pull requests and publishes successful
builds from `main`. Keep GitHub **Settings → Pages → Build and deployment**
set to **GitHub Actions**. Changes to the website do not create an integration
release or update Home Assistant.

After editing navigation or styling, check desktop and mobile layouts, search,
keyboard navigation, dark mode and language switching. The language selector
must keep the equivalent guide open.

## Search Console

1. Add the URL-prefix property `https://groove-max.github.io/ha-dtek-monitor/`
   in the owner's Google Search Console.
2. Choose HTML-tag verification. Copy only the `content` value of the supplied
   `google-site-verification` tag.
3. Add a GitHub Actions **repository variable** named `GOOGLE_SITE_VERIFICATION`
   with that value. It is public verification metadata, not a password.
4. Run the **Documentation** workflow on `main`, then complete Google's check.
5. Submit `https://groove-max.github.io/ha-dtek-monitor/sitemap.xml`.

The verification tag is added to the root and both language versions. Search
Console can then report indexing, queries, impressions and clicks. A sitemap
helps discovery but does not guarantee indexing or a ranking.

Do not place a `robots.txt` in the project subdirectory expecting it to control
the `groove-max.github.io` host: crawler rules are read at the host root.

## Sharing preview

`assets/social-preview.png` is the 1280 × 640 sharing image used by the site's
Open Graph metadata. Its reproducible layout is `social-preview.html`, which
uses the project's icon and fictional-account screenshot.

Serve the repository root, open that HTML at a 1280 × 640 viewport, and capture
the viewport with Playwright to regenerate the PNG. It must remain below 1 MB.

GitHub's repository preview is a separate setting: upload this PNG at
**Settings → General → Social preview**. GitHub's supported repository REST and
GraphQL update APIs do not expose that image setting.

The theme is [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/),
licensed under MIT. Its bundled notices and license comments remain in the
generated assets. Project content retains the repository's own license.
