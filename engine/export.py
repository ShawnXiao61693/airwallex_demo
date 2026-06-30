# 把 news 表导成前端可读的 JSON（供 RevE 后台「情报库」页浏览）。run.sh 末尾会调它。
import json, sys
import db

def _j(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []

COLS = ['id', 'fetched_at', 'published_at', 'source', 'status', 'relevant',
        'category', 'roles', 'industry', 'signal_type', 's_total', 'lang',
        'title', 'summary', 'comment', 'action', 'citation', 'url']

def export(path):
    rows = db.conn().execute(
        "SELECT %s FROM news ORDER BY (s_total IS NULL), s_total DESC, id DESC" % ",".join(COLS)
    ).fetchall()
    items = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        for k in ('category', 'roles', 'industry'):
            d[k] = _j(d[k])
        items.append(d)
    # 概览统计
    def cnt(where=''):
        return db.conn().execute("SELECT count(*) AS n FROM news " + where).fetchone()['n']
    stats = {
        'total': cnt(),
        'refined': cnt("WHERE status='refined'"),
        'irrelevant': cnt("WHERE status='irrelevant'"),
        'raw': cnt("WHERE status='raw'"),
    }
    json.dump({'stats': stats, 'items': items}, open(path, 'w'),
              ensure_ascii=False, indent=1)
    print(f"[export] {len(items)} 条 → {path}  {stats}")

if __name__ == '__main__':
    export(sys.argv[1] if len(sys.argv) > 1 else 'news.json')
