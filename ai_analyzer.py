import json
import os
import math
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).with_name(".env")

SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "relevant": {"type": "boolean"}, "category": {"type": "string"},
    "has_code": {"type": "boolean"}, "highlight": {"type": "string"},
    "reusable_value": {"type": "string"},
    **{name: {"type": "integer", "minimum": 0, "maximum": 10} for name in
       ("visual_score", "technical_score", "innovation_score", "recommendation_score")}},
    "required": ["relevant", "category", "has_code", "highlight", "reusable_value",
                 "visual_score", "technical_score", "innovation_score", "recommendation_score"]}


def fallback_analysis(item):
    content = (item.get("content") or item.get("title") or "").strip()
    return {"relevant": True, "category": "待人工复核", "has_code": bool(item.get("has_code")),
            "highlight": content[:180] or "来源信息有限，建议打开原文查看视觉效果。",
            "reusable_value": "可从原链接检查实现方式、视觉语言与交互机制。",
            "visual_score": 0, "technical_score": 0, "innovation_score": 0,
            "recommendation_score": round(min(10, max(1, 1 + math.log1p(max(0, item.get("heuristic_score", 0))) * 1.8)), 1)}


def analyze_item(item):
    load_dotenv(ENV_PATH)
    if not os.getenv("OPENAI_API_KEY"):
        return fallback_analysis(item)
    from openai import OpenAI
    source_data = {key: item.get(key) for key in
                   ("source", "source_tier", "title", "url", "content", "enriched_content",
                    "stars", "likes", "views", "language", "license", "topics", "demo_url",
                    "thumbnail_url", "has_images", "external_link")}
    response = OpenAI(timeout=20.0, max_retries=1).responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), store=False,
        instructions=("你是 three.js / Creative Web / 3D Art 案例编辑。只根据输入证据评估，不得虚构。"
                      "highlight 用中文写核心亮点；reusable_value 用中文写具体可借鉴的视觉语言、"
                      "世界观、交互、游戏化或工程方法。"),
        input=json.dumps(source_data, ensure_ascii=False), max_output_tokens=800,
        text={"format": {"type": "json_schema", "name": "case_analysis", "strict": True, "schema": SCHEMA}})
    return json.loads(response.output_text)


if __name__ == "__main__":
    load_dotenv(ENV_PATH)
    if not os.getenv("OPENAI_API_KEY"):
        print(f"未配置 OPENAI_API_KEY。请在 {ENV_PATH} 中添加：OPENAI_API_KEY=你的密钥")
        print("这不会阻止 main.py 运行；未配置时会自动使用无 AI 降级摘要。")
    else:
        print(f"OPENAI_API_KEY 已读取，模型：{os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')}")
