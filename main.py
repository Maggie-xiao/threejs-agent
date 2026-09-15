import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from requests import RequestException
from ai_analyzer import analyze_item, fallback_analysis
from art_filter import VERSION, rank_daily
from community_collectors import (search_creative_rss, search_devto, search_gitlab,
                                  search_hackernews, search_mastodon, search_npm,
                                  search_reddit, search_x_web, search_youtube)
from deduplicator import deduplicate_items
from enricher import enrich_items
from filters import filter_by_keywords, filter_recent
from forum_collector import search_forum
from github_collector import search_github
from report import write_reports
from social_collectors import search_bluesky, search_discord, search_twitter

COLLECTORS = {"github": search_github, "threejs_forum": search_forum,
              "gitlab": search_gitlab, "npm": search_npm, "creative_rss": search_creative_rss,
              "devto": search_devto, "reddit": search_reddit, "hackernews": search_hackernews,
              "mastodon": search_mastodon, "youtube": search_youtube, "x_search": search_x_web,
              "bluesky": search_bluesky,
              "twitter": search_twitter, "discord": search_discord}


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def analysis_cache_key(item):
    payload = json.dumps({"id": item["id"], "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
                          "version": VERSION, "images": item.get('image_urls', []),
                          "content": item.get("content"), "enriched": item.get("enriched_content")},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def select_diverse(candidates, limit, per_source=2):
    """Keep strong cross-source coverage, then fill remaining slots by score."""
    selected, selected_ids = [], set()
    by_source = {}
    for item in candidates:
        by_source.setdefault(item.get("source", "unknown"), []).append(item)
    for items in by_source.values():
        for item in items[:per_source]:
            if len(selected) >= limit:
                break
            selected.append(item)
            selected_ids.add(item["id"])
    for item in candidates:
        if len(selected) >= limit:
            break
        if item["id"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["id"])
    return selected


def collect(hours):
    items, status = [], {}
    for name, collector in COLLECTORS.items():
        if name == "twitter" and not os.getenv("X_BEARER_TOKEN"):
            status[name] = {"ok": False, "skipped": True, "reason": "missing X_BEARER_TOKEN"}
            continue
        if name == "discord" and not (os.getenv("DISCORD_BOT_TOKEN") and os.getenv("DISCORD_CHANNEL_IDS")):
            status[name] = {"ok": False, "skipped": True, "reason": "missing Discord token or channel IDs"}
            continue
        if name == "youtube" and not os.getenv("YOUTUBE_API_KEY"):
            status[name] = {"ok": False, "skipped": True, "reason": "missing YOUTUBE_API_KEY"}
            continue
        try:
            print(f"[source] {name}: scanning...", file=sys.stderr, flush=True)
            result = collector(hours=hours)
            batch, warnings = result if isinstance(result, tuple) else (result, [])
            items.extend(batch)
            status[name] = {"ok": bool(batch) or not warnings, "count": len(batch)}
            if warnings:
                status[name]["warnings"] = warnings[:10]
            if name == "bluesky" and warnings and not (os.getenv("BSKY_HANDLE") and os.getenv("BSKY_APP_PASSWORD")):
                status[name]["hint"] = "public endpoint blocked; set free BSKY_HANDLE and BSKY_APP_PASSWORD"
            print(f"[source] {name}: {len(batch)} items", file=sys.stderr, flush=True)
        except (RequestException, ValueError, KeyError) as exc:
            status[name] = {"ok": False, "error": str(exc)[:240]}
            if name == "bluesky" and not (os.getenv("BSKY_HANDLE") and os.getenv("BSKY_APP_PASSWORD")):
                status[name]["hint"] = "public endpoint blocked; set free BSKY_HANDLE and BSKY_APP_PASSWORD"
            print(f"[source] {name}: failed ({type(exc).__name__})", file=sys.stderr, flush=True)
    return items, status


def run(hours=24, minimum_score=8, max_cases=20, ai_limit=25, include_seen=False, output_dir="output"):
    load_dotenv(Path(__file__).with_name('.env'))
    ai_limit = min(25, max(0, ai_limit))
    raw, status = collect(hours)
    candidates = deduplicate_items(filter_by_keywords(filter_recent(raw, hours), minimum_score))
    state_path = Path(output_dir) / "seen.json"
    seen = set(load_json(state_path, []))
    if not include_seen:
        candidates = [item for item in candidates if item["id"] not in seen]
    candidates.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
    candidates.sort(key=lambda x: any(w in (x.get('content','')+' '+x.get('title','')).lower()
                    for w in ('world', 'game', 'stylized', 'low-poly', 'voxel', 'forest', 'explore')), reverse=True)
    selected = select_diverse(candidates, max(max_cases, ai_limit))
    evaluated_ids = {item["id"] for item in selected}
    enrichment_path = Path(output_dir) / "enrichment-cache.json"
    enrichment_cache = load_json(enrichment_path, {})
    _, enrichment_cache = enrich_items(selected[:ai_limit], enrichment_cache)
    atomic_json(enrichment_path, enrichment_cache)
    cache_path = Path(output_dir) / "analysis-cache.json"
    cache = load_json(cache_path, {})
    pending = {}
    for index, item in enumerate(selected):
        if not item.get('image_urls'):
            item['image_urls'] = [item['thumbnail_url']] if item.get('thumbnail_url') else []
        key = analysis_cache_key(item)
        if index < ai_limit and key in cache and item.get('image_urls'):
            item["analysis"] = cache[key]
            item["analysis_cached"] = True
            item['visual_evidence'] = [{'url': u, 'status': 'checked', 'scope': '缓存静态图片判断'} for u in item['image_urls'][:2]]
        elif index < ai_limit and os.getenv("OPENAI_API_KEY"):
            pending[index] = (item, key)
        else:
            item["analysis"] = fallback_analysis(item)
    if pending:
        with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
            futures = {pool.submit(analyze_item, item): (item, key) for item, key in pending.values()}
            for future in as_completed(futures):
                item, key = futures[future]
                try:
                    item["analysis"] = future.result()
                    if item.get('visual_evidence'):
                        cache[key] = item["analysis"]
                        atomic_json(cache_path, cache)
                except Exception as exc:
                    item["analysis"] = fallback_analysis(item)
                    item["analysis_error"] = str(exc)[:240]
    selected = rank_daily(selected, max_cases)
    selected.sort(key=lambda item: (item["analysis"].get("recommendation_score", 0),
                                    item.get("heuristic_score", 0)), reverse=True)
    md_path, json_path, daily_items = write_reports(selected, output_dir)
    atomic_json(state_path, sorted(seen | evaluated_ids))
    atomic_json(Path(output_dir) / "last-run.json", {"sources": status, "raw": len(raw),
        "candidates": len(candidates), "published_this_run": len(selected), "daily_total": len(daily_items)})
    return md_path, json_path, status, len(raw), len(selected)


if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Daily three.js good-case radar")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--minimum-score", type=int, default=8)
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--ai-limit", type=int, default=25)
    parser.add_argument("--include-seen", action="store_true")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    md, data, status, raw_count, final_count = run(**vars(args))
    print(json.dumps({"raw": raw_count, "published": final_count, "markdown": str(md),
                      "json": str(data), "sources": status}, ensure_ascii=False, indent=2))
