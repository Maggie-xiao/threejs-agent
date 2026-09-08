"""Additional public and credentialed discovery sources."""
import os
from datetime import datetime, timedelta, timezone

import requests


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
