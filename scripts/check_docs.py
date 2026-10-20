"""Validate the generated public website, its links and bilingual SEO metadata."""

from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import os
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/docs"
SPEC = json.loads((ROOT / "website/pages.json").read_text())
BASE = SPEC["site_url"]
PREFIX = urlsplit(BASE).path
errors = []
documents = {}


def document(path):
    if path not in documents:
        documents[path] = BeautifulSoup(path.read_text(), "html.parser")
    return documents[path]


def check(condition, message):
    if not condition:
        errors.append(message)


def local_path(url, current):
    parsed = urlsplit(url)
    if parsed.netloc and parsed.netloc != urlsplit(BASE).netloc:
        return None
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return None
    name = unquote(parsed.path)
    if name.startswith(PREFIX):
        path = OUTPUT / name.removeprefix(PREFIX)
    elif name.startswith("/"):
        return None
    else:
        path = current.parent / name if name else current
    path = path.resolve()
    check(path.is_relative_to(OUTPUT.resolve()), f"Link escapes published site: {url}")
    if name.endswith("/") or path.is_dir():
        path /= "index.html"
    return path, unquote(parsed.fragment)


def main():
    expected = set()
    for page in SPEC["pages"]:
        for language in ("uk", "en"):
            suffix = page["slug"] + "/" if page["slug"] else ""
            url = BASE + language + "/" + suffix
            expected.add(url)
            path = OUTPUT / language / suffix / "index.html"
            check(path.is_file(), f"Missing page: {path}")
            if not path.exists():
                continue
            soup = document(path)
            check(soup.html.get("lang") == language, f"Wrong HTML language: {url}")
            check(len(soup.select("main h1")) == 1, f"Expected one content heading: {url}")
            if not page["slug"]:
                install = soup.select_one(f'a[href="{SPEC["installation_url"]}"] img')
                check(install is not None, f"Missing clickable installation badge: {url}")
            check(soup.select_one('link[rel="canonical"]').get("href") == url, f"Wrong canonical: {url}")
            description = soup.select_one('meta[name="description"]')
            check(description and description.get("content") == page[language]["description"], f"Missing description: {url}")
            verification = soup.select_one('meta[name="google-site-verification"]')
            token = os.environ.get("GOOGLE_SITE_VERIFICATION")
            check(
                verification and verification.get("content") == token if token else verification is None,
                f"Incorrect optional Search Console verification: {url}",
            )
            for lang in ("uk", "en"):
                target = BASE + lang + "/" + suffix
                switch = soup.select_one(f'.language-switch a[hreflang="{lang}"]')
                check(switch and switch.get("href") == target, f"Language switch loses current page: {url}")
            image = soup.select_one('meta[property="og:image"]')
            check(image and image.get("content") == BASE + "assets/social-preview.png", f"Missing social image: {url}")
            check(not soup.select('meta[name="robots"][content*="noindex"]'), f"Content excluded from index: {url}")
            # Includes generated navigation, styles, icons, images, search scripts
            # and source Markdown links. Invalid fragments fail the build.
            for node in soup.select("[href], [src]"):
                value = node.get("href") or node.get("src")
                target = local_path(value, path)
                if target is None:
                    continue
                file, fragment = target
                check(file.is_file(), f"Broken link on {url}: {value}")
                if fragment and file.is_file() and file.suffix == ".html":
                    check(document(file).find(id=fragment) is not None, f"Broken anchor on {url}: {value}")

    sitemap = ET.parse(OUTPUT / "sitemap.xml")
    root = document(OUTPUT / "index.html")
    verification = root.select_one('meta[name="google-site-verification"]')
    token = os.environ.get("GOOGLE_SITE_VERIFICATION")
    check(verification and verification.get("content") == token if token else verification is None,
          "Incorrect root Search Console verification")
    homepage = next(page["uk"] for page in SPEC["pages"] if not page["slug"])
    for selector, value in {
        'meta[name="description"]': homepage["description"],
        'meta[property="og:title"]': homepage["title"],
        'meta[property="og:description"]': homepage["description"],
        'meta[property="og:image"]': BASE + "assets/social-preview.png",
        'meta[property="og:url"]': BASE + "uk/",
        'meta[name="twitter:card"]': "summary_large_image",
        'meta[http-equiv="refresh"]': "0;url=uk/",
    }.items():
        tag = root.select_one(selector)
        check(tag and tag.get("content") == value, f"Incorrect root metadata: {selector}")
    actual = {item.text for item in sitemap.findall(".//{*}loc")}
    check(actual == expected, "Sitemap must contain exactly the canonical content pages")
    for item in sitemap.findall("./{*}url"):
        url = item.find("{*}loc").text
        suffix = url.removeprefix(BASE).split("/", 1)[1]
        languages = {
            link.get("hreflang"): link.get("href")
            for link in item.findall("{http://www.w3.org/1999/xhtml}link")
            if link.get("rel") == "alternate"
        }
        check(languages == {
            "uk": BASE + "uk/" + suffix,
            "en": BASE + "en/" + suffix,
            "x-default": BASE + "uk/" + suffix,
        }, f"Wrong sitemap language alternatives: {url}")
    for path in OUTPUT.rglob("*"):
        check(not any(part in (".local", "graphify-out", ".git") for part in path.relative_to(OUTPUT).parts), f"Private output: {path}")
        check(path.suffix not in (".py", ".yaml", ".yml", ".sqlite", ".env"), f"Unexpected public source: {path}")
    if errors:
        raise SystemExit("\n".join(dict.fromkeys(errors)))
    print(f"Verified {len(expected)} canonical pages, language links, assets, fragments and sitemap.")


if __name__ == "__main__":
    main()
