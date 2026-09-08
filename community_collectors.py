"""Additional public and credentialed discovery sources."""
import os
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests


def search_gitlab(hours=24, session=None):
    session = session or requests.Session()
    updated_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z")
    found = {}
    for query in ("three.js", "threejs", "react three fiber"):
        response = session.get("https://gitlab.com/api/v4/projects", timeout=(5, 15),
            params={"search": query, "simple": "true", "order_by": "updated_at", "sort": "desc",
                    "updated_after": updated_after, "per_page": 100})
        response.raise_for_status()
        for row in response.json():
            found[row["web_url"]] = {"source": "gitlab", "source_tier": "open_source",
                "title": row.get("path_with_namespace") or row["name"], "url": row["web_url"],
                "content": row.get("description") or "", "published_at": row["last_activity_at"],
                "stars": row.get("star_count", 0), "language": None}
    return list(found.values())


def search_npm(hours=24, session=None):
    session = session or requests.Session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    found = {}
    for query in ("threejs shader", "three.js webgpu", "react-three-fiber"):
        response = session.get("https://registry.npmjs.org/-/v1/search", timeout=(5, 15),
                               params={"text": query, "size": 100, "quality": 0.7, "popularity": 0.1, "maintenance": 0.2})
        response.raise_for_status()
        for entry in response.json().get("objects", []):
            row = entry.get("package", {})
            try:
                modified = datetime.fromisoformat(row.get("date", "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if modified < cutoff:
                continue
            name = row.get("name", "")
            found[name] = {"source": "npm", "source_tier": "package_registry", "title": name,
                "url": row.get("links", {}).get("npm", f"https://www.npmjs.com/package/{name}"),
                "content": row.get("description") or "", "published_at": row["date"],
                "version": row.get("version"), "license": None}
    return list(found.values())


RSS_FEEDS = {
    "codrops": "https://tympanus.net/codrops/feed/",
    "webdev": "https://web.dev/feed.xml",
}


def _text(node, *names):
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def search_creative_rss(hours=24, session=None):
    session = session or requests.Session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for publisher, url in RSS_FEEDS.items():
        response = session.get(url, headers={"User-Agent": "threejs-good-cases/2.0"}, timeout=(5, 15))
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
        for node in entries:
            title = _text(node, "title", "{http://www.w3.org/2005/Atom}title")
            summary = _text(node, "description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content")
            clean = html.unescape(re.sub(r"<[^>]+>", " ", summary))
            text = f"{title} {clean}".lower()
            if not any(word in text for word in ("three.js", "threejs", "webgl", "webgpu", "shader", "3d", "creative coding")):
                continue
            link = _text(node, "link")
            if not link:
                link_node = node.find("{http://www.w3.org/2005/Atom}link")
                link = link_node.get("href", "") if link_node is not None else ""
            published = _text(node, "pubDate", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated")
            from email.utils import parsedate_to_datetime
            try:
                created = parsedate_to_datetime(published) if "," in published else datetime.fromisoformat(published.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if created.astimezone(timezone.utc) >= cutoff:
                results.append({"source": "creative_rss", "source_tier": "editorial_curated",
                    "publisher": publisher, "title": title, "url": link, "content": clean[:1500],
                    "published_at": created.astimezone(timezone.utc).isoformat()})
    return results


def search_devto(hours=24, session=None):
    session = session or requests.Session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    response = session.get("https://dev.to/api/articles", params={"tag": "threejs", "per_page": 100}, timeout=(5, 15))
    response.raise_for_status()
    results = []
    for row in response.json():
        created = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
        if created >= cutoff:
            results.append({"source": "devto", "source_tier": "creator_article", "title": row["title"],
                "url": row["url"], "content": row.get("description", ""), "published_at": row["published_at"],
                "likes": row.get("positive_reactions_count", 0), "comments": row.get("comments_count", 0)})
    return results


def search_reddit(hours=24, session=None):
    session = session or requests.Session()
    response = session.get("https://www.reddit.com/search.json",
        headers={"User-Agent": "threejs-good-cases/2.0 (daily research radar)"}, timeout=(5, 15),
        params={"q": '(threejs OR "three.js" OR react-three-fiber) (shader OR art OR interactive OR webgpu)',
                "sort": "new", "t": "day", "limit": 100, "type": "link"})
    response.raise_for_status()
    results = []
    for child in response.json().get("data", {}).get("children", []):
        row = child.get("data", {})
        results.append({"source": "reddit", "source_tier": "social_community", "title": row.get("title", ""),
            "url": "https://www.reddit.com" + row.get("permalink", ""), "content": row.get("selftext", "")[:1000],
            "published_at": datetime.fromtimestamp(row.get("created_utc", 0), timezone.utc).isoformat(),
            "likes": row.get("score", 0), "comments": row.get("num_comments", 0), "subreddit": row.get("subreddit")})
    return results


def search_hackernews(hours=24, session=None):
    session = session or requests.Session()
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    response = session.get("https://hn.algolia.com/api/v1/search_by_date", timeout=(5, 15),
        params={"query": "three.js OR threejs OR react three fiber", "tags": "story", "numericFilters": f"created_at_i>{cutoff}", "hitsPerPage": 100})
    response.raise_for_status()
    return [{"source": "hackernews", "source_tier": "tech_community", "title": row.get("title") or "Untitled",
             "url": row.get("url") or f"https://news.ycombinator.com/item?id={row['objectID']}",
             "content": row.get("story_text") or "", "published_at": row["created_at"],
             "likes": row.get("points", 0), "comments": row.get("num_comments", 0)}
            for row in response.json().get("hits", [])]


def search_mastodon(hours=24, session=None):
    session = session or requests.Session()
    response = session.get("https://mastodon.social/api/v1/timelines/tag/threejs",
                           params={"limit": 40}, timeout=(5, 15))
    response.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for row in response.json():
        created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        if created >= cutoff:
            results.append({"source": "mastodon", "source_tier": "social_first_party",
                "title": row.get("content", "")[:120], "url": row["url"], "content": row.get("content", ""),
                "published_at": row["created_at"], "likes": row.get("favourites_count", 0)})
    return results


def search_youtube(hours=24, session=None):
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return []
    session = session or requests.Session()
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z")
    results = []
    for query in ("three.js art", "threejs shader", "react three fiber creative"):
        response = session.get("https://www.googleapis.com/youtube/v3/search", timeout=(5, 15),
            params={"key": key, "part": "snippet", "q": query, "type": "video", "order": "date",
                    "publishedAfter": published_after, "maxResults": 50})
        response.raise_for_status()
        for row in response.json().get("items", []):
            snippet, video_id = row["snippet"], row["id"]["videoId"]
            results.append({"source": "youtube", "source_tier": "video_creator", "title": snippet["title"],
                "url": f"https://www.youtube.com/watch?v={video_id}", "content": snippet.get("description", ""),
                "published_at": snippet["publishedAt"], "channel": snippet.get("channelTitle")})
    return results
