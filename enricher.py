"""Fetch source-native detail for shortlisted cases before AI analysis."""
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser

import requests

MEDIA_VERSION = 'art-images-v2'


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img':
            self.images.append(a.get('src') or a.get('data-src') or '')
        if tag == 'meta' and a.get('property') in ('og:image', 'twitter:image'):
            self.images.append(a.get('content', ''))


def extract_images(text, base):
    parser = ImageParser()
    parser.feed(text)
    paths = parser.images + re.findall(r'!\[[^\]]*\]\(([^\s)]+)', text)
    images = []
    for path in paths:
        url = urljoin(base, html.unescape(path))
        if urlparse(url).scheme != 'https':
            continue
        if any(w in url.lower() for w in ('badge', 'shields.io', 'avatar', 'logo', '.svg')):
            continue
        if url not in images:
            images.append(url)
    return images[:2]


def _plain(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def enrich_item(item):
    source = item.get("source")
    session = requests.Session()
    headers = {"User-Agent": "threejs-good-cases/2.0", "Accept": "application/json"}
    if source == "github" and os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    updates = {}
    if source == "github":
        response = session.get(f"https://api.github.com/repos/{item['title']}/readme",
            headers={**headers, "Accept": "application/vnd.github.raw+json"}, timeout=(4, 10))
        response.raise_for_status()
        updates["enriched_content"] = response.text[:8000]
        updates['image_urls'] = extract_images(response.text,
            f"https://raw.githubusercontent.com/{item['title']}/HEAD/")
    elif source == "threejs_forum":
        response = session.get(item["url"] + ".json", headers=headers, timeout=(4, 10))
        response.raise_for_status()
        posts = response.json().get("post_stream", {}).get("posts", [])
        if posts:
            updates["enriched_content"] = _plain(posts[0].get("cooked", ""))[:8000]
            updates['image_urls'] = extract_images(posts[0].get('cooked', ''), item['url'])
    elif source == "npm":
        name = quote(item["title"], safe="@")
        response = session.get(f"https://registry.npmjs.org/{name}", headers=headers, timeout=(4, 10))
        response.raise_for_status()
        data = response.json()
        updates["enriched_content"] = (data.get("readme") or "")[:8000]
        updates["demo_url"] = data.get("homepage") or ""
        repository = data.get("repository") or {}
        updates["repository_url"] = repository.get("url", "") if isinstance(repository, dict) else str(repository)
        repo = updates['repository_url'].removeprefix('git+').removesuffix('.git')
        base = repo.replace('https://github.com/', 'https://raw.githubusercontent.com/') + '/HEAD/'
        updates['image_urls'] = extract_images(data.get('readme', ''), base)
    elif not item.get('image_urls') and not item.get('thumbnail_url') and source not in ('discord', 'x_search', 'twitter'):
        response = session.get(item['url'], headers={'User-Agent': 'threejs-good-cases/2.0'}, timeout=(4, 10))
        response.raise_for_status()
        updates['image_urls'] = extract_images(response.text[:500000], response.url)
    updates['media_version'] = MEDIA_VERSION
    return updates


def enrich_items(items, cache, workers=6):
    pending = [item for item in items if cache.get(item['id'], {}).get('media_version') != MEDIA_VERSION]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(enrich_item, item): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            try:
                cache[item["id"]] = future.result()
            except (requests.RequestException, ValueError, KeyError) as exc:
                cache[item["id"]] = {"enrichment_error": str(exc)[:240]}
    for item in items:
        item.update(cache.get(item["id"], {}))
    return items, cache
