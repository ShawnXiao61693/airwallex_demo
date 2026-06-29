# Collector（采集 · Engine）—— 用 Brave Search API 拉真实新闻 → 归一化 → 入库(raw)
# Brave 支持中文、结果自带摘要(description)，喂给 Refiner 上下文更足。
import requests, time
from config import BRAVE_API_KEY, BRAVE_QUERIES, BRAVE_COUNT, BRAVE_FRESHNESS
from lang import detect_lang
import db

BRAVE_URL = "https://api.search.brave.com/res/v1/news/search"
GAP_SEC = 1.1   # Brave 免费版约 1 req/s

def _brave(q):
    headers = {'Accept': 'application/json', 'X-Subscription-Token': BRAVE_API_KEY}
    params = {'q': q, 'count': BRAVE_COUNT, 'freshness': BRAVE_FRESHNESS, 'spellcheck': 0}
    r = requests.get(BRAVE_URL, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get('results', [])

def collect():
    if not BRAVE_API_KEY:
        print("[collect] 未设置 BRAVE_API_KEY，跳过采集")
        return
    total = 0
    for i, q in enumerate(BRAVE_QUERIES):
        if i:
            time.sleep(GAP_SEC)
        try:
            results = _brave(q)
        except Exception as e:
            print(f"[collect] 查询失败 {q}: {e}")
            continue
        for a in results:
            if not a.get('url'):
                continue
            desc = a.get('description') or ''
            text = ((a.get('title') or '') + ' — ' + desc).strip(' —')
            db.upsert_raw({
                'url': a.get('url'),
                'title': a.get('title'),
                'source': (a.get('meta_url') or {}).get('hostname') or (a.get('profile') or {}).get('name'),
                'country': None, 'lang': detect_lang(text),
                'published_at': a.get('page_age') or a.get('age'),
                'raw_content': text,
            })
            total += 1
    print(f"[collect] 采集 {total} 条（去重后入库）")
