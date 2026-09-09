"""Fetch source-native detail for shortlisted cases before AI analysis."""
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests


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
    elif source == "threejs_forum":
        response = session.get(item["url"] + ".json", headers=headers, timeout=(4, 10))
        response.raise_for_status()
        posts = response.json().get("post_stream", {}).get("posts", [])
        if posts:
            updates["enriched_content"] = _plain(posts[0].get("cooked", ""))[:8000]
    elif source == "npm":
        name = quote(item["title"], safe="@")
        response = session.get(f"https://registry.npmjs.org/{name}", headers=headers, timeout=(4, 10))
        response.raise_for_status()
        data = response.json()
        updates["enriched_content"] = (data.get("readme") or "")[:8000]
        updates["demo_url"] = data.get("homepage") or ""
        repository = data.get("repository") or {}
        updates["repository_url"] = repository.get("url", "") if isinstance(repository, dict) else str(repository)
    return updates


def enrich_items(items, cache, workers=6):
    pending = [item for item in items if item["id"] not in cache and item.get("source") in
               {"github", "threejs_forum", "npm"}]
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
