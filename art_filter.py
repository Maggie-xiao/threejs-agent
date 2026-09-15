"""Versioned art eligibility gates; popularity cannot bypass visual evidence."""
import json
from pathlib import Path

RULES = json.loads(Path(__file__).with_name('art-criteria.json').read_text())
VERSION = RULES['version']


def classify(item):
    a = item.get('analysis', {})
    valid = a.get('criteria_version') == VERSION
    scores = a.get('art_scores') or {}
    values = [scores.get(k) for k in RULES['weights']]
    total = None
    if all(isinstance(v, (int, float)) and 0 <= v <= 10 for v in values):
        total = round(sum(scores[k] * w for k, w in RULES['weights'].items()) * 10, 1)
    evidence = item.get('visual_evidence', [])
    checked = valid and any(e.get('status') == 'checked' for e in evidence)
    eligible = (checked and a.get('stylization_verdict') == '符合'
                and a.get('world_relevance') is True and a.get('art_observations')
                and a.get('takeaways') and total is not None and total >= RULES['threshold'])
    if eligible:
        status = '美术精选'
    elif not valid or not checked or a.get('stylization_verdict') == '未知':
        status = '待验证' if valid else '旧规则／未评估'
    elif a.get('technical_value'):
        status = '技术备查'
    else:
        status = '排除'
    item.update(selection_status=status, art_total=total if checked else None,
                criteria_version=a.get('criteria_version'),
                decision_reasons=a.get('decision_reasons') or ['视觉证据不足或尚未按新规则评估'])
    return item


def rank_daily(items, limit=20):
    items = [classify(x) for x in items]
    items.sort(key=lambda x: x.get('art_total') or -1, reverse=True)
    count = 0
    for x in items:
        if x['selection_status'] == '美术精选':
            count += 1
            if count > min(20, limit):
                x['selection_status'] = '低优先级跳过'
    return items
