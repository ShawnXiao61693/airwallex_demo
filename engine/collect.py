# Collector（采集 · Engine）—— 从 GDELT 拉真实新闻 → 归一化 → 入库(raw)
# 这是"薄摄取层"：脏活（多源覆盖）交给 GDELT，这里只做拉取+归一+去重入库。
import requests, datetime, time
from config import GDELT_QUERIES, GDELT_MAXRECORDS, GDELT_TIMESPAN
import db

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
GAP_SEC = 6          # GDELT 免费 API：每 5 秒最多 1 次请求，间隔留 6 秒保险

def _iso(s):
    try:
        return datetime.datetime.strptime(s, "%Y%m%dT%H%M%SZ").isoformat()
    except Exception:
        return s

def _fetch(params, retries=3):
    # GDELT 限流有两种表现：429，或 200 但正文是纯文本提示。两者都退避重试。
    for i in range(retries + 1):
        r = requests.get(GDELT, params=params, timeout=30)
        throttled = (r.status_code == 429) or ('limit requests' in r.text.lower())
        if throttled:
            time.sleep(6 + 4 * i); continue
        r.raise_for_status()
        try:
            return r.json().get('articles', [])
        except ValueError:                     # 200 但非 JSON（多为节流/空）→ 退避重试
            time.sleep(6 + 4 * i); continue
    return []

def collect():
    total = 0
    for idx, q in enumerate(GDELT_QUERIES):
        if idx:
            time.sleep(GAP_SEC)                 # 查询之间留间隔
        params = {'query': q, 'mode': 'ArtList', 'format': 'json',
                  'maxrecords': GDELT_MAXRECORDS, 'timespan': GDELT_TIMESPAN, 'sort': 'DateDesc'}
        try:
            arts = _fetch(params)
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
