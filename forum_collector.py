import requests


def search_forum(hours=24, session=None):
    session = session or requests.Session()
    response = session.get("https://discourse.threejs.org/latest.json",
                           headers={"User-Agent": "threejs-good-cases/2.0"}, timeout=(5, 15))
    response.raise_for_status()
    return [{"source": "threejs_forum", "source_tier": "specialist_community",
             "title": topic["title"],
             "url": f"https://discourse.threejs.org/t/{topic['slug']}/{topic['id']}",
             "content": topic.get("excerpt", ""), "published_at": topic["created_at"],
             "views": topic.get("views", 0), "replies": max(0, topic.get("posts_count", 1) - 1)}
            for topic in response.json().get("topic_list", {}).get("topics", [])]
