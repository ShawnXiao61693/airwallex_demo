# Composer（编排 · 仅日报）—— 一天一份日报，编排出 3 个不同角度的 release candidate。
# 每份候选同时含 AE 段 + AM 段（每段 6 中 + 2 英，英文垫底）。落库到 daily_reports，
# 默认发布 RC1；被发布的候选写成 report_<date>.json 供用户端读取（按角色看各自段）。
import json, os, re
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, ROLES, DAILY_TOP_N, DAILY_ZH, DAILY_EN
import db

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
OUT_DIR = os.getenv('REPORT_DIR', '/usr/share/nginx/html/airwallex/data/reports')

# 3 个编辑角度 → 3 个 release candidate
ANGLES = [
    ('机会优先', '偏重拓新机会、行业线索、触发事件，帮助销售主动出击'),
    ('竞品防守', '偏重竞品动向、价格战、客户流失风险，帮助稳住存量与反制'),
    ('均衡', '机会与风险兼顾，覆盖面广、不偏科'),
]

CURATE_PROMPT = """你是 Airwallex 销售日报主编。下面是 {date} 当天、面向 {role}（{role_desc}）的候选情报。
本期编辑角度：{angle}（{angle_desc}）——在可行动性相近时，优先体现这个角度。
请精选出当天日报：
1) 同一事件多个来源只保留 1 条（去重）；
2) 尽量覆盖不同类目/信号，不要让同一类刷屏；
3) 按对 {role} 的可行动性 + 上面的编辑角度排序，最多 {n} 条；
4) 写一句当天导语（呼应该角度）。
只输出 JSON：{{"lede":"一句导语","item_ids":[按顺序的 id 数字]}}

候选（id | 分类 | 信号 | 分 | 标题）：
{cands}"""

ROLE_DESC = {'AE': '拓新销售', 'AM': '客户成功'}

def _curate(date, role, rows, n, angle, angle_desc, want_lede=True):
    if not rows:
        return '', []
    cands = "\n".join(
        "%s | %s | %s | %s | %s" % (
            r['id'], "/".join(json.loads(r['category'] or '[]')),
            r['signal_type'], r['s_total'], (r['title'] or '')[:60])
        for r in rows)
    p = CURATE_PROMPT.format(date=date, role=role, role_desc=ROLE_DESC.get(role, ''),
                             angle=angle, angle_desc=angle_desc, n=n, cands=cands)
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": p}], temperature=0.3)
        m = re.search(r'\{.*\}', resp.choices[0].message.content, re.S)
        d = json.loads(m.group(0))
        lede = d.get('lede', '') if want_lede else ''
        return lede, [int(x) for x in d.get('item_ids', [])][:n]
    except Exception as e:
        print(f"  编排失败 {date}/{role}/{angle}: {e} → 兜底按分数 top-N")
        return '', [r['id'] for r in rows[:n]]

def _item(r):
    return {'id': r['id'], 'title': r['title'], 'source': r['source'], 'url': r['url'],
            'lang': r['lang'],
            'category': json.loads(r['category'] or '[]'), 'signal_type': r['signal_type'],
            'industry': json.loads(r['industry'] or '[]'), 'score': round(r['s_total'] or 0, 2),
            'summary': r['summary'], 'comment': r['comment'], 'action': r['action'],
            'products': json.loads(r['products'] or '[]'), 'citation': r['citation']}

def _compose_role(date, role, angle, angle_desc):
    """某天某角色、某角度下的 6 中 + 2 英编排，返回 (lede, [item dict])。"""
    zh = db.get_candidates(date, role, lang='zh')
    en = db.get_candidates(date, role, lang='en')
    if not zh and not en:
        return '', []
    lede, zh_ids = _curate(date, role, zh, DAILY_ZH, angle, angle_desc, want_lede=True)
    _,    en_ids = _curate(date, role, en, DAILY_EN, angle, angle_desc, want_lede=False)
    zmap = {r['id']: r for r in zh}
    emap = {r['id']: r for r in en}
    zh_pick = [zmap[i] for i in zh_ids if i in zmap][:DAILY_ZH]
    en_pick = [emap[i] for i in en_ids if i in emap][:DAILY_EN]
    used = {r['id'] for r in zh_pick + en_pick}
    for r in zh:
        if len(zh_pick) + len(en_pick) >= DAILY_TOP_N: break
        if r['id'] not in used: zh_pick.append(r); used.add(r['id'])
    for r in en:
        if len(zh_pick) + len(en_pick) >= DAILY_TOP_N: break
        if r['id'] not in used: en_pick.append(r); used.add(r['id'])
    ordered = zh_pick + en_pick           # 中文在前，英文垫底
    return lede, [_item(r) for r in ordered]

def write_published_files():
    """把所有已发布候选写成 report_<date>.json + index.json（用户端读这些）。"""
    os.makedirs(OUT_DIR, exist_ok=True)
    index = []
    for row in db.list_daily_published():
        date = row['bucket_date']
        ae = json.loads(row['ae_items'] or '[]')
        am = json.loads(row['am_items'] or '[]')
        rep = {'date': date, 'angle': row['angle'], 'lede': row['lede'], 'cand_no': row['cand_no'],
               'status': 'published',
               'ae': {'count': len(ae), 'items': ae},
               'am': {'count': len(am), 'items': am}}
        json.dump(rep, open(os.path.join(OUT_DIR, f"report_{date}.json"), 'w'),
                  ensure_ascii=False, indent=1)
        index.append({'date': date, 'angle': row['angle'], 'lede': row['lede'],
                      'ae_count': len(ae), 'am_count': len(am)})
    index.sort(key=lambda x: x['date'], reverse=True)
    json.dump({'reports': index}, open(os.path.join(OUT_DIR, 'index.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(f"[compose] 已发布 {len(index)} 天 → {OUT_DIR}/index.json")

def compose_all():
    for date in db.list_bucket_dates():
        for cand_no, (angle, angle_desc) in enumerate(ANGLES, 1):
            ae_lede, ae_items = _compose_role(date, 'AE', angle, angle_desc)
            am_lede, am_items = _compose_role(date, 'AM', angle, angle_desc)
            if not ae_items and not am_items:
                continue
            lede = ae_lede or am_lede
            db.save_daily_candidate(date, cand_no, angle, lede,
                                    json.dumps(ae_items, ensure_ascii=False),
                                    json.dumps(am_items, ensure_ascii=False))
            print(f"[compose] {date} RC{cand_no}「{angle}」: AE {len(ae_items)} / AM {len(am_items)}")
        # 默认发布 RC1（保证用户端不空；后台审核可改发别的）
        if not db.get_daily_published(date):
            db.publish_daily(date, 1)
    write_published_files()

# 兼容旧入口
def compose():
    compose_all()
