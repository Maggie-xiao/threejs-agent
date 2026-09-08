import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def write_reports(items, output_dir="output"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path, md_path = out / f"cases-{stamp}.json", out / f"cases-{stamp}.md"
    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
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
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path
