import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from requests import RequestException
from ai_analyzer import analyze_item, fallback_analysis
from community_collectors import (search_creative_rss, search_devto, search_gitlab,
                                  search_hackernews, search_mastodon, search_npm,
                                  search_reddit, search_youtube)
from deduplicator import deduplicate_items
from filters import filter_by_keywords, filter_recent
from forum_collector import search_forum
from github_collector import search_github
from report import write_reports
from social_collectors import search_bluesky, search_discord, search_twitter

COLLECTORS = {"github": search_github, "threejs_forum": search_forum,
              "gitlab": search_gitlab, "npm": search_npm, "creative_rss": search_creative_rss,
              "devto": search_devto, "reddit": search_reddit, "hackernews": search_hackernews,
              "mastodon": search_mastodon, "youtube": search_youtube, "bluesky": search_bluesky,
              "twitter": search_twitter, "discord": search_discord}


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
            batch = collector(hours=hours)
            items.extend(batch)
            status[name] = {"ok": True, "count": len(batch)}
            print(f"[source] {name}: {len(batch)} items", file=sys.stderr, flush=True)
        except (RequestException, ValueError, KeyError) as exc:
            status[name] = {"ok": False, "error": str(exc)[:240]}
            print(f"[source] {name}: failed ({type(exc).__name__})", file=sys.stderr, flush=True)
    return items, status


def run(hours=24, minimum_score=8, max_cases=50, ai_limit=25, include_seen=False, output_dir="output"):
    raw, status = collect(hours)
    candidates = deduplicate_items(filter_by_keywords(filter_recent(raw, hours), minimum_score))
    state_path = Path(output_dir) / "seen.json"
    try:
        seen = set(json.loads(state_path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        seen = set()
    if not include_seen:
        candidates = [item for item in candidates if item["id"] not in seen]
    candidates.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
    selected = select_diverse(candidates, max_cases)
    for index, item in enumerate(selected):
        try:
            item["analysis"] = analyze_item(item) if index < ai_limit else fallback_analysis(item)
        except Exception as exc:
            item["analysis"] = fallback_analysis(item)
            item["analysis_error"] = str(exc)[:240]
    selected = [item for item in selected if item["analysis"].get("relevant", True)]
    selected.sort(key=lambda item: (item["analysis"].get("recommendation_score", 0),
                                    item.get("heuristic_score", 0)), reverse=True)
    md_path, json_path = write_reports(selected, output_dir)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(seen | {item["id"] for item in selected}), indent=2), encoding="utf-8")
    (Path(output_dir) / "last-run.json").write_text(json.dumps({"sources": status, "raw": len(raw),
        "candidates": len(candidates), "published": len(selected)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path, status, len(raw), len(selected)


if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Daily three.js good-case radar")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--minimum-score", type=int, default=8)
    parser.add_argument("--max-cases", type=int, default=50)
    parser.add_argument("--ai-limit", type=int, default=25)
    parser.add_argument("--include-seen", action="store_true")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    md, data, status, raw_count, final_count = run(**vars(args))
    print(json.dumps({"raw": raw_count, "published": final_count, "markdown": str(md),
                      "json": str(data), "sources": status}, ensure_ascii=False, indent=2))
