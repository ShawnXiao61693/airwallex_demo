# 按天回填历史日报：对日期区间内每一天，用 Brave 拉那天的新闻 → 提炼 → 按天编排出日报。
# 用法：python backfill.py 2026-06-22 2026-06-28
import sys, time, datetime, requests
from config import BRAVE_API_KEY, BRAVE_QUERIES, BRAVE_COUNT
from lang import detect_lang
import db, refine, compose

BRAVE_URL = "https://api.search.brave.com/res/v1/news/search"
GAP = 1.1

def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)

def _brave(q, fresh):
    h = {'Accept': 'application/json', 'X-Subscription-Token': BRAVE_API_KEY}
    p = {'q': q, 'count': BRAVE_COUNT, 'freshness': fresh, 'spellcheck': 0}
    r = requests.get(BRAVE_URL, headers=h, params=p, timeout=30)
    r.raise_for_status()
    return r.json().get('results', [])

def collect_day(day):
    nxt = (day + datetime.timedelta(days=1)).isoformat()
    fresh = "%sto%s" % (day.isoformat(), nxt)
    n = 0
    for i, q in enumerate(BRAVE_QUERIES):
        if i:
            time.sleep(GAP)
        try:
            results = _brave(q, fresh)
        except Exception as e:
            print(f"  [{day}] 查询失败 {q}: {e}")
            continue
        for a in results:
            if not a.get('url'):
                continue
            desc = a.get('description') or ''
            text = ((a.get('title') or '') + ' — ' + desc).strip(' —')
            db.upsert_raw({
                'url': a.get('url'), 'title': a.get('title'),
                'source': (a.get('meta_url') or {}).get('hostname') or (a.get('profile') or {}).get('name'),
                'lang': detect_lang(text),
                'published_at': a.get('page_age') or a.get('age'),
                'raw_content': text,
                'bucket_date': day.isoformat(),
            })
            n += 1
    print(f"[backfill] {day} 采集 {n} 条")

if __name__ == '__main__':
    db.init_db()
    start = datetime.date.fromisoformat(sys.argv[1])
    end = datetime.date.fromisoformat(sys.argv[2])
    for day in daterange(start, end):
        collect_day(day)
    refine.refine()       # 提炼所有新 raw（含各天）
    compose.compose_all() # 按天 × 角色 编排出日报
