import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPORT_TZ = ZoneInfo("Asia/Singapore")
WEB_TEMPLATE = Path(__file__).with_name("web") / "dashboard.html"


def _atomic_write(path, content):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_reports(items, output_dir="output", merge_existing=True):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(REPORT_TZ).strftime("%Y-%m-%d")
    json_path, md_path = out / f"cases-{stamp}.json", out / f"cases-{stamp}.md"
    if merge_existing and json_path.exists():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = []
        merged = {item.get("id", item.get("url")): item for item in previous}
        merged.update({item.get("id", item.get("url")): item for item in items})
        items = list(merged.values())
        items.sort(key=lambda item: (item.get("analysis", {}).get("recommendation_score", 0),
                                    item.get("heuristic_score", 0)), reverse=True)
    _atomic_write(json_path, json.dumps(items, ensure_ascii=False, indent=2))
    sources = Counter(item.get("source", "unknown") for item in items)
    lines = [f"# three.js Good Cases · {stamp}", "",
             f"> 共 {len(items)} 条高潜案例；来源：" + "、".join(f"{k} {v}" for k, v in sources.items()), ""]
    for index, item in enumerate(items, 1):
        analysis = item.get("analysis", {})
        code = "有代码" if analysis.get("has_code", item.get("has_code")) else "无代码/待确认"
        lines += [f"## {index}. [{item.get('title', 'Untitled')}]({item.get('url', '')})", "",
                  f"- 来源：{item.get('source')} · {item.get('source_tier', 'unknown')} · {code}",
                  f"- 核心亮点：{analysis.get('highlight', '')}",
                  f"- 可借鉴价值：{analysis.get('reusable_value', '')}",
                  f"- 推荐分：{analysis.get('recommendation_score', 0)}/10 · 预筛分：{item.get('heuristic_score', 0)}", ""]
    _atomic_write(md_path, "\n".join(lines))
    web_path = out / "index.html"
    template = WEB_TEMPLATE.read_text(encoding="utf-8")
    browser_items = []
    for item in items:
        browser_items.append({key: value for key, value in item.items()
                              if key != "enriched_content"})
    payload = json.dumps(browser_items, ensure_ascii=False).replace("</", "<\\/")
    _atomic_write(web_path, template.replace("__CASE_DATA__", payload))
    return md_path, json_path, items
