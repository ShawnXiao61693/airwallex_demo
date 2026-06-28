# Collector（采集 · Engine）—— 从 GDELT 拉真实新闻 → 归一化 → 入库(raw)
# 这是"薄摄取层"：脏活（多源覆盖）交给 GDELT，这里只做拉取+归一+去重入库。
import requests, datetime
from config import GDELT_QUERIES, GDELT_MAXRECORDS, GDELT_TIMESPAN
import db

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"

def _iso(s):
    try:
        return datetime.datetime.strptime(s, "%Y%m%dT%H%M%SZ").isoformat()
    except Exception:
        return s

def collect():
    total = 0
    for q in GDELT_QUERIES:
        params = {'query': q, 'mode': 'ArtList', 'format': 'json',
                  'maxrecords': GDELT_MAXRECORDS, 'timespan': GDELT_TIMESPAN, 'sort': 'DateDesc'}
        try:
            r = requests.get(GDELT, params=params, timeout=30)
            r.raise_for_status()
            arts = r.json().get('articles', [])
        except Exception as e:
            print(f"[collect] 查询失败 {q[:30]}…: {e}")
            continue
        for a in arts:
            if not a.get('url'):
                continue
            db.upsert_raw({
                'url': a.get('url'), 'title': a.get('title'),
                'source': a.get('domain'), 'country': a.get('sourcecountry'),
                'lang': a.get('language'), 'published_at': _iso(a.get('seendate', '')),
                'raw_content': a.get('title'),
            })
            total += 1
    print(f"[collect] 采集 {total} 条（去重后入库）")
