# 数据层 —— 一张 news 表（status: raw→refined→irrelevant）。MVP 用 SQLite，量大再上 Postgres+pgvector。
import sqlite3, json, datetime
from config import DB_PATH

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE,                 -- 去重靠它
  title TEXT, source TEXT, source_country TEXT, lang TEXT,
  published_at TEXT, fetched_at TEXT, raw_content TEXT,
  bucket_date TEXT,                -- 这条归属哪一天的日报（回填用）
  status TEXT DEFAULT 'raw',       -- raw / refined / irrelevant
  -- 以下由 Refiner 回填：
  relevant INTEGER,
  category TEXT, roles TEXT, industry TEXT, signal_type TEXT,
  s_rel REAL, s_time REAL, s_act REAL, s_cred REAL, s_total REAL,
  comment TEXT, action TEXT, products TEXT, citation TEXT,
  refined_at TEXT
);
"""

def init_db():
    with conn() as c:
        c.executescript(SCHEMA)

def upsert_raw(it):
    bucket = it.get('bucket_date') or datetime.date.today().isoformat()
    with conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO news
               (url,title,source,source_country,lang,published_at,fetched_at,raw_content,bucket_date,status)
               VALUES (?,?,?,?,?,?,?,?,?,'raw')""",
            (it['url'], it['title'], it.get('source'), it.get('country'), it.get('lang'),
             it.get('published_at'), datetime.datetime.utcnow().isoformat(),
             it.get('raw_content', it['title']), bucket))

def get_unrefined(limit=5000):
    with conn() as c:
        return c.execute("SELECT * FROM news WHERE status='raw' LIMIT ?", (limit,)).fetchall()

def update_refined(news_id, r):
    status = 'refined' if r.get('relevant') else 'irrelevant'
    with conn() as c:
        c.execute(
            """UPDATE news SET status=?, relevant=?, category=?, roles=?, industry=?, signal_type=?,
               s_rel=?, s_time=?, s_act=?, s_cred=?, s_total=?, comment=?, action=?, products=?, citation=?, refined_at=?
               WHERE id=?""",
            (status, 1 if r.get('relevant') else 0,
             json.dumps(r.get('category', []), ensure_ascii=False),
             json.dumps(r.get('roles', []), ensure_ascii=False),
             json.dumps(r.get('industry', []), ensure_ascii=False),
             r.get('signal_type'),
             r.get('s_rel'), r.get('s_time'), r.get('s_act'), r.get('s_cred'), r.get('s_total'),
             r.get('comment'), r.get('action'),
             json.dumps(r.get('products', []), ensure_ascii=False), r.get('citation'),
             datetime.datetime.utcnow().isoformat(), news_id))

def get_for_daily(role, top_n):
    with conn() as c:
        return c.execute(
            """SELECT * FROM news WHERE status='refined' AND relevant=1 AND roles LIKE ?
               ORDER BY s_total DESC LIMIT ?""",
            (f'%"{role}"%', top_n)).fetchall()

# ---- 按天回填用 ----
def list_bucket_dates():
    with conn() as c:
        return [r[0] for r in c.execute(
            "SELECT DISTINCT bucket_date FROM news WHERE status='refined' AND relevant=1 ORDER BY bucket_date").fetchall()]

def get_candidates(bucket_date, role, limit=40):
    with conn() as c:
        return c.execute(
            """SELECT * FROM news WHERE status='refined' AND relevant=1
               AND bucket_date=? AND roles LIKE ? ORDER BY s_total DESC LIMIT ?""",
            (bucket_date, f'%"{role}"%', limit)).fetchall()
