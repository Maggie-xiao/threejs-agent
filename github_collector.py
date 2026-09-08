import os
from datetime import datetime, timedelta, timezone
import requests

QUERIES = ("three.js shader", "threejs particles", "threejs webgpu", "three.js generative",
           "react three fiber", "threejs immersive", "threejs raymarching", "threejs portfolio")


def search_github(hours=24, session=None):
    session = session or requests.Session()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).date().isoformat()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "threejs-good-cases/2.0"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    found = {}
    for keyword in QUERIES:
        response = session.get("https://api.github.com/search/repositories", headers=headers,
            params={"q": f'{keyword} pushed:>={since}', "sort": "updated", "order": "desc", "per_page": 30}, timeout=(5, 15))
        response.raise_for_status()
        for row in response.json().get("items", []):
            url = row["html_url"]
            item = found.setdefault(url, {"source": "github", "source_tier": "open_source",
                "title": row["full_name"], "url": url, "content": row.get("description") or "",
                "published_at": row["pushed_at"], "stars": row.get("stargazers_count", 0),
                "language": row.get("language"), "license": (row.get("license") or {}).get("spdx_id"),
                "matched_queries": []})
            item["matched_queries"].append(keyword)
    return list(found.values())
