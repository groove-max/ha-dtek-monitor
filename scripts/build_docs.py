"""Build bilingual GitHub Pages from the reviewed, allowlisted user guides."""

from __future__ import annotations

from html import escape
import json
import logging
import os
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import quote, unquote, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from markdown.extensions.toc import slugify_unicode
from mkdocs.commands.build import build
from mkdocs.config import load_config
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "website/pages.json").read_text())
URL = SPEC["site_url"]
PREFIX = urlsplit(URL).path
REPOSITORY = SPEC["repository"]
OUTPUT = ROOT / "build/docs"
STAGING = ROOT / "build/docs-source"
LINK = re.compile(r'(!?\[[^\]]*?\]\()([^\s)]+)(\s+"[^"]*")?(\))')
BADGE = re.compile(r'^(\[!\[[^\]]*\]\([^\n)]+\)\])\(([^\n)]+)\)$', re.M)


def routes():
    return {
        page[language]["source"]: f"{language}/{page['slug'] + '/' if page['slug'] else ''}"
        for page in SPEC["pages"]
        for language in ("uk", "en")
    }


def rewrite_url(value, source):
    """Resolve source-relative links before moving Markdown to its public route."""
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return value
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(parsed.path)))
    mapping = routes()
    if target in mapping:
        destination = PREFIX + mapping[target]
    elif target.startswith("docs/images/"):
        destination = PREFIX + "assets/images/" + target.removeprefix("docs/images/")
    else:
        # Contributor files, licensing, source examples and other non-user pages
        # stay on GitHub. Never copy the repository wholesale to the website.
        if target.startswith("../") or not (ROOT / target).exists():
            raise ValueError(f"Broken relative link in {source}: {value}")
        destination = REPOSITORY + "/blob/main/" + quote(target, safe="/")
    return urlunsplit(("", "", destination, parsed.query, parsed.fragment))


def prepare_page(page, language):
    item = page[language]
    source = item["source"]
    text = (ROOT / source).read_text()
    # The site header supplies a contextual language switcher. Keep the source
    # language bar for readers on GitHub, but don't repeat it inside each page.
    text = re.sub(r"^.*\[(?:Українська|English)\]\([^\n]+\).*\n", "", text, count=1, flags=re.M)
    # Preserve installation/status badges, including their nested image links.
    text = BADGE.sub(lambda match: match[1] + "(" + rewrite_url(match[2], source) + ")", text)
    text = LINK.sub(
        lambda match: match[1] + rewrite_url(match[2], source) + (match[3] or "") + match[4],
        text,
    )
    slug = page["slug"]
    metadata = {
        "title": item["title"],
        "description": item["description"],
        "alternates": {lang: URL + f"{lang}/" + (slug + "/" if slug else "") for lang in ("uk", "en")},
    }
    path = STAGING / language / (slug + ".md" if slug else "index.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + text)
    return path.name


def main():
    verification = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    if verification and not re.fullmatch(r"[A-Za-z0-9_=-]+", verification):
        raise ValueError("Invalid Google site verification token")
    shutil.rmtree(OUTPUT, ignore_errors=True)
    shutil.rmtree(STAGING, ignore_errors=True)
    OUTPUT.mkdir(parents=True)
    assets = OUTPUT / "assets"
    assets.mkdir()
    shutil.copytree(ROOT / "docs/images", assets / "images")
    shutil.copy2(ROOT / "website/assets/social-preview.png", assets / "social-preview.png")
    shutil.copy2(ROOT / "website/assets/MATERIAL-LICENSE.txt", assets / "MATERIAL-LICENSE.txt")
    for language in ("uk", "en"):
        navigation = [{page[language]["label"]: prepare_page(page, language)} for page in SPEC["pages"]]
        nav_bot = "Telegram-бот" if language == "uk" else "Telegram companion"
        bot_url = "https://github.com/groove-max/ha-dtek-telegram-bot"
        navigation.append({nav_bot: bot_url + ("/blob/main/README.uk.md" if language == "uk" else "")})
        language_assets = STAGING / language / "assets"
        language_assets.mkdir()
        shutil.copy2(ROOT / "custom_components/dtek_monitor/brand/icon.png", language_assets / "icon.png")
        shutil.copy2(ROOT / "website/assets/site.css", language_assets / "site.css")
        config = load_config(
            config_file=str(ROOT / "website/mkdocs.yml"),
            docs_dir=str(STAGING / language),
            site_dir=str(OUTPUT / language),
            site_url=URL + language + "/",
            nav=navigation,
            strict=True,
        )
        config.theme["language"] = language
        config.extra["project_url"] = URL
        config.extra["google_site_verification"] = verification
        config.mdx_configs["toc"]["slugify"] = slugify_unicode
        build(config)

    # The root opens Ukrainian by default. English remains a normal crawlable
    # link, not a browser-language redirect. Each translated page is canonical.
    # Link-preview crawlers may read this page without following its refresh.
    homepage = next(page["uk"] for page in SPEC["pages"] if not page["slug"])
    title = escape(homepage["title"], quote=True)
    description = escape(homepage["description"], quote=True)
    (OUTPUT / "index.html").write_text(
        '<!doctype html><html lang="uk"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title>'
        f'<meta name="description" content="{description}">'
        '<meta property="og:type" content="website">'
        '<meta property="og:site_name" content="DTEK Monitor">'
        f'<meta property="og:title" content="{title}">'
        f'<meta property="og:description" content="{description}">'
        f'<meta property="og:url" content="{URL}uk/">'
        '<meta property="og:locale" content="uk_UA">'
        '<meta property="og:locale:alternate" content="en_US">'
        f'<meta property="og:image" content="{URL}assets/social-preview.png">'
        '<meta property="og:image:width" content="1280">'
        '<meta property="og:image:height" content="640">'
        '<meta property="og:image:alt" content="DTEK Monitor for Home Assistant — schedules, personal accounts and meter readings">'
        '<meta name="twitter:card" content="summary_large_image">'
        + (f'<meta name="google-site-verification" content="{verification}">' if verification else "")
        +
        f'<link rel="canonical" href="{URL}uk/">'
        '<meta http-equiv="refresh" content="0;url=uk/"></head>'
        '<body><main><h1>DTEK Monitor</h1>'
        '<p><a href="uk/">Українська</a> · <a href="en/">English</a></p>'
        '</main></body></html>'
    )
    (OUTPUT / "404.html").write_text(
        '<!doctype html><html lang="uk"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex"><title>DTEK Monitor — 404</title>'
        '</head><body><main><h1>404 · Сторінку не знайдено / Page not found</h1>'
        f'<p><a href="{PREFIX}uk/">Українська</a> · <a href="{PREFIX}en/">English</a></p>'
        '</main></body></html>'
    )
    # One sitemap lists only canonical content URLs, never language redirects,
    # local demo files, maintainer notes or source archives.
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    xhtml = "http://www.w3.org/1999/xhtml"
    ET.register_namespace("", namespace)
    ET.register_namespace("xhtml", xhtml)
    sitemap = ET.Element(f"{{{namespace}}}urlset")
    for page in SPEC["pages"]:
        suffix = page["slug"] + "/" if page["slug"] else ""
        for language in ("uk", "en"):
            item = ET.SubElement(sitemap, f"{{{namespace}}}url")
            ET.SubElement(item, f"{{{namespace}}}loc").text = URL + language + "/" + suffix
            for alternate in ("uk", "en", "x-default"):
                target = "uk" if alternate == "x-default" else alternate
                ET.SubElement(item, f"{{{xhtml}}}link", {
                    "rel": "alternate", "hreflang": alternate,
                    "href": URL + target + "/" + suffix,
                })
    ET.ElementTree(sitemap).write(OUTPUT / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (OUTPUT / ".nojekyll").touch()
    print(f"Built {len(routes())} pages in {OUTPUT}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
