"""Fast deterministic screening before optional AI review."""
from datetime import datetime, timedelta, timezone
import math

POSITIVE_KEYWORDS = {
    "shader": 4, "glsl": 4, "webgpu": 4, "webgl": 3, "raymarch": 4,
    "sdf": 3, "particle": 3, "generative": 3, "procedural": 3,
    "postprocessing": 3, "volumetric": 4, "creative coding": 3,
    "interactive": 2, "immersive": 3, "threejs": 5, "three.js": 5,
    "react three fiber": 4, "r3f": 3, "animation": 2, "simulation": 2,
    "physics": 2, "visual": 1,
}
NEGATIVE_KEYWORDS = ("for hire", "hiring", "job opening", "looking for work",
                     "help me", "beginner question", "error message", "bootcamp")
SOURCE_WEIGHTS = {"threejs_forum": 8, "github": 8, "twitter": 5,
                  "discord": 6, "bluesky": 4, "rss": 4, "devto": 5,
                  "reddit": 4, "hackernews": 5, "mastodon": 4, "youtube": 5}
SOURCE_WEIGHTS.update({"gitlab": 7, "npm": 7, "creative_rss": 7})


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def filter_recent(items, hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for item in items:
        published = parse_time(item.get("published_at"))
        if published is not None and published >= cutoff:
            results.append(item)
    return results


def filter_last_24_hours(items):
    return filter_recent(items, 24)


def score_item(item):
    text = f"{item.get('title', '')} {item.get('content', '')}".lower()
    negative = [word for word in NEGATIVE_KEYWORDS if word in text]
    matches = [word for word in POSITIVE_KEYWORDS if word in text]
    stars = max(0, int(item.get("stars", 0) or 0))
    reactions = max(0, int(item.get("likes", item.get("replies", 0)) or 0))
    engagement = min(10, math.log1p(stars) * 1.5) + min(5, math.log1p(reactions))
    code_sources = {"github", "gitlab", "npm"}
    has_code = item.get("source") in code_sources or any(
        x in text for x in ("github.com", "gitlab.com", "npmjs.com", "codepen.io", "codesandbox.io", "stackblitz.com"))
    score = SOURCE_WEIGHTS.get(item.get("source", ""), 2) + min(sum(POSITIVE_KEYWORDS[x] for x in matches), 20)
    score += engagement + (5 if has_code else 0) - 20 * bool(negative)
    result = dict(item)
    result.update(filter_keywords=matches, excluded_keywords=negative,
                  heuristic_score=round(score, 1), has_code=has_code)
    return result


def filter_by_keywords(items, minimum_score=8):
    scored = [score_item(item) for item in items]
    return sorted((item for item in scored if item["heuristic_score"] >= minimum_score),
                  key=lambda item: item["heuristic_score"], reverse=True)
