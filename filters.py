"""Fast deterministic screening before optional AI review."""
from datetime import datetime, timedelta, timezone

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
                  "discord": 6, "bluesky": 4, "rss": 4}


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def filter_recent(items, hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [item for item in items if (parse_time(item.get("published_at")) or cutoff) >= cutoff]


def filter_last_24_hours(items):
    return filter_recent(items, 24)


def score_item(item):
    text = f"{item.get('title', '')} {item.get('content', '')}".lower()
    negative = [word for word in NEGATIVE_KEYWORDS if word in text]
    matches = [word for word in POSITIVE_KEYWORDS if word in text]
    engagement = min(10, int(item.get("stars", 0) or 0) // 25)
    engagement += min(5, int(item.get("likes", item.get("replies", 0)) or 0) // 5)
    has_code = item.get("source") == "github" or any(x in text for x in ("github.com", "codepen.io", "codesandbox.io"))
    score = SOURCE_WEIGHTS.get(item.get("source", ""), 2) + min(sum(POSITIVE_KEYWORDS[x] for x in matches), 20)
    score += engagement + (5 if has_code else 0) - 20 * bool(negative)
    result = dict(item)
    result.update(filter_keywords=matches, excluded_keywords=negative,
                  heuristic_score=score, has_code=has_code)
    return result


def filter_by_keywords(items, minimum_score=8):
    scored = [score_item(item) for item in items]
    return sorted((item for item in scored if item["heuristic_score"] >= minimum_score),
                  key=lambda item: item["heuristic_score"], reverse=True)

    return results
