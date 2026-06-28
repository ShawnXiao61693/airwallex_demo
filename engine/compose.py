# Composer（制作 · 仅日报）—— 从情报里按角色取数 → 组成日报 JSON（供前端渲染）
# MVP：确定性 top-N（按综合分）。下一步升级：加一步 LLM 策展（set-level 精选+排序+导语）。
import json, datetime
from config import DAILY_TOP_N, ROLES
import db

def compose():
    out = {}
    for role in ROLES:
        rows = db.get_for_daily(role, DAILY_TOP_N)
        items = [{
            'title': r['title'], 'source': r['source'], 'url': r['url'],
            'category': json.loads(r['category'] or '[]'),
            'signal_type': r['signal_type'],
            'industry': json.loads(r['industry'] or '[]'),
            'score': round(r['s_total'] or 0, 2),
            'comment': r['comment'], 'action': r['action'],
            'products': json.loads(r['products'] or '[]'),
            'citation': r['citation'],
        } for r in rows]
        daily = {'date': datetime.date.today().isoformat(),
                 'role': role, 'count': len(items), 'items': items}
        fn = f"daily_{role}.json"
        json.dump(daily, open(fn, 'w'), ensure_ascii=False, indent=2)
        out[role] = fn
        print(f"[compose] {role}: {len(items)} 条 → {fn}")
    return out

# TODO（升级）：策展 Agent —— 把候选池喂给 LLM，做整组精选+排序+写导语，
#               再渲染；当前先用分数排序占位。
