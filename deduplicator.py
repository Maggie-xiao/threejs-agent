import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_title(title):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", title.lower())).strip()


def normalize_url(url):
    try:
        parts = urlsplit(url)
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")])
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    except ValueError:
        return url


def item_id(item):
    value = normalize_url(item.get("url", "")) or normalize_title(item.get("title", ""))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def deduplicate_items(items):

    unique = {}
    for raw in items:
        item = dict(raw)
        key = item_id(item)
        item["id"] = key
        if key not in unique or item.get("heuristic_score", 0) > unique[key].get("heuristic_score", 0):
            unique[key] = item
    return list(unique.values())
