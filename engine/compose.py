# Composer（制作 · 仅日报）—— 按"天 × 角色"用编排 LLM 出日报：去重 + 多样化 + 排序 + 导语。
import json, os, re
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, ROLES, DAILY_TOP_N
import db

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
OUT_DIR = os.getenv('REPORT_DIR', '/usr/share/nginx/html/airwallex/data/reports')

CURATE_PROMPT = """你是 Airwallex 销售日报主编。下面是 {date} 当天、面向 {role}（{role_desc}）的候选情报。
请精选出当天日报：
1) 同一事件多个来源只保留 1 条（去重）；
2) 尽量覆盖不同类目/信号，不要让同一类刷屏；
3) 按对 {role} 的可行动性排序，最多 {n} 条；
4) 写一句当天导语。
只输出 JSON：{{"lede":"一句导语","item_ids":[按顺序的 id 数字]}}

候选（id | 分类 | 信号 | 分 | 标题）：
{cands}"""

ROLE_DESC = {'AE': '拓新销售', 'AM': '客户成功'}

def _curate(date, role, rows):
    cands = "\n".join(
        "%s | %s | %s | %s | %s" % (
            r['id'], "/".join(json.loads(r['category'] or '[]')),
            r['signal_type'], r['s_total'], (r['title'] or '')[:60])
        for r in rows)
    p = CURATE_PROMPT.format(date=date, role=role, role_desc=ROLE_DESC.get(role, ''),
                             n=DAILY_TOP_N, cands=cands)
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": p}], temperature=0.2)
        m = re.search(r'\{.*\}', resp.choices[0].message.content, re.S)
        d = json.loads(m.group(0))
        return d.get('lede', ''), [int(x) for x in d.get('item_ids', [])]
    except Exception as e:
        print(f"  编排失败 {date}/{role}: {e} → 兜底按分数 top-N")
        return '', [r['id'] for r in rows[:DAILY_TOP_N]]

def _item(r):
    return {'id': r['id'], 'title': r['title'], 'source': r['source'], 'url': r['url'],
            'category': json.loads(r['category'] or '[]'), 'signal_type': r['signal_type'],
            'industry': json.loads(r['industry'] or '[]'), 'score': round(r['s_total'] or 0, 2),
            'comment': r['comment'], 'action': r['action'],
            'products': json.loads(r['products'] or '[]'), 'citation': r['citation']}

def compose_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    index = []
    for date in db.list_bucket_dates():
        for role in ROLES:
            rows = db.get_candidates(date, role)
            if not rows:
                continue
            lede, ids = _curate(date, role, rows)
            by_id = {r['id']: r for r in rows}
            ordered = [by_id[i] for i in ids if i in by_id] or rows[:DAILY_TOP_N]
            report = {'date': date, 'role': role, 'status': 'draft', 'lede': lede,
                      'count': len(ordered), 'items': [_item(r) for r in ordered]}
            fn = f"report_{date}_{role}.json"
            json.dump(report, open(os.path.join(OUT_DIR, fn), 'w'), ensure_ascii=False, indent=1)
            index.append({'date': date, 'role': role, 'status': 'draft',
                          'count': len(ordered), 'lede': lede, 'file': fn})
            print(f"[compose] {date} {role}: {len(ordered)} 条")
    index.sort(key=lambda x: (x['date'], x['role']), reverse=True)
    json.dump({'reports': index}, open(os.path.join(OUT_DIR, 'index.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(f"[compose] 共 {len(index)} 份日报 → {OUT_DIR}/index.json")

# 兼容旧入口（run.py 调用）
def compose():
    compose_all()
