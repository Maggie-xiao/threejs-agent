"""Social connectors. Credentialed sources are skipped when not configured."""
import os
from datetime import datetime, timedelta, timezone
import requests

SOCIAL_QUERY = '("three.js" OR threejs OR "react three fiber") (shader OR webgpu OR art OR interactive OR generative OR immersive) -is:retweet'


def search_twitter(hours=24, session=None):
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        return []
    session = session or requests.Session()
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z")
    response = session.get("https://api.x.com/2/tweets/search/recent",
        headers={"Authorization": f"Bearer {token}"}, timeout=(5, 15),
        params={"query": SOCIAL_QUERY, "start_time": start, "max_results": 100,
                "tweet.fields": "created_at,public_metrics,author_id,entities"})
    response.raise_for_status()
    return [{"source": "twitter", "source_tier": "social_first_party", "title": row["text"][:120],
             "url": f"https://x.com/i/web/status/{row['id']}", "content": row["text"],
             "published_at": row["created_at"], "likes": row.get("public_metrics", {}).get("like_count", 0)}
            for row in response.json().get("data", [])]


def search_discord(hours=24, session=None):
    token, channels = os.getenv("DISCORD_BOT_TOKEN"), os.getenv("DISCORD_CHANNEL_IDS", "")
    if not token or not channels.strip():
        return []
    session = session or requests.Session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for channel in [value.strip() for value in channels.split(",") if value.strip()]:
        response = session.get(f"https://discord.com/api/v10/channels/{channel}/messages",
                               headers={"Authorization": f"Bot {token}"}, params={"limit": 100}, timeout=(5, 15))
        response.raise_for_status()
        for row in response.json():
            created = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if created < cutoff or not row.get("content"):
                continue
            guild = row.get("guild_id", "@me")
            results.append({"source": "discord", "source_tier": "curated_community",
                "title": row["content"][:120], "content": row["content"],
                "url": f"https://discord.com/channels/{guild}/{channel}/{row['id']}",
                "published_at": row["timestamp"]})
    return results


def search_bluesky(hours=24, session=None):
    session = session or requests.Session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    headers = {"User-Agent": "threejs-good-cases/2.0 (+https://github.com/threejs)",
               "Accept": "application/json"}
    for query in ("threejs", '"three.js"', '"react three fiber"'):
        response = session.get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
                               headers=headers, params={"q": query, "limit": 100, "sort": "latest"}, timeout=(5, 15))
        response.raise_for_status()
        for row in response.json().get("posts", []):
            record, created = row.get("record", {}), row.get("record", {}).get("createdAt", "")
            try:
                if datetime.fromisoformat(created.replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                continue
            handle, post_id, post_text = row.get("author", {}).get("handle", "unknown"), row.get("uri", "").rsplit("/", 1)[-1], record.get("text", "")
            results.append({"source": "bluesky", "source_tier": "social_first_party", "title": post_text[:120],
                "content": post_text, "url": f"https://bsky.app/profile/{handle}/post/{post_id}",
                "published_at": created, "likes": row.get("likeCount", 0)})
    return results
