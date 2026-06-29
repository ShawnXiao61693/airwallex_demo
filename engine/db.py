# 数据层 —— Postgres（Supabase）。一张 news 表（status: raw→refined→irrelevant）。
# 走 DATABASE_URL（Supabase pooler）；本质是标准 PG，将来要自托管换连接串即可。
import os, json, datetime
import psycopg
from psycopg.rows import dict_row

DB_URL = os.getenv('DATABASE_URL')

def conn():
    # 走 pgbouncer 事务池：autocommit + 关闭预编译，避免 "prepared statement" 冲突
    return psycopg.connect(DB_URL, autocommit=True, prepare_threshold=None, row_factory=dict_row)

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  url TEXT UNIQUE,
  title TEXT, source TEXT, source_country TEXT, lang TEXT,
  published_at TEXT, fetched_at TEXT, raw_content TEXT,
  bucket_date TEXT,
  status TEXT DEFAULT 'raw',
  relevant INTEGER,
  category TEXT, roles TEXT, industry TEXT, signal_type TEXT,
  s_rel REAL, s_time REAL, s_act REAL, s_cred REAL, s_total REAL,
  comment TEXT, action TEXT, products TEXT, citation TEXT,
  refined_at TEXT
);
"""

SCHEMA_PUB = """
CREATE TABLE IF NOT EXISTS publications (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  period TEXT,                  -- 当周周一日期 YYYY-MM-DD，作为期数标识
  type TEXT,                    -- weekly / monthly
  title TEXT,
  html_path TEXT,              -- nginx 下相对路径，如 data/weekly/2026-06-01.html
  status TEXT DEFAULT 'draft',  -- draft / published
  created_at TEXT, published_at TEXT,
  UNIQUE(period, type)
);
"""

def init_db():
    with conn() as c:
        c.execute(SCHEMA)
        c.execute(SCHEMA_PUB)

# ---- 周/月报出版物（手搓上传 → 审核发布）----
def upsert_publication(period, typ, title, html_path):
    with conn() as c:
        c.execute(
            """INSERT INTO publications (period,type,title,html_path,status,created_at)
               VALUES (%s,%s,%s,%s,'draft',%s)
               ON CONFLICT (period,type) DO UPDATE
               SET title=EXCLUDED.title, html_path=EXCLUDED.html_path,
                   status='draft', created_at=EXCLUDED.created_at, published_at=NULL""",
            (period, typ, title, html_path, datetime.datetime.utcnow().isoformat()))

def set_published(period, typ):
    with conn() as c:
        c.execute("UPDATE publications SET status='published', published_at=%s WHERE period=%s AND type=%s",
                  (datetime.datetime.utcnow().isoformat(), period, typ))

def list_publications(typ):
    with conn() as c:
        return c.execute("SELECT * FROM publications WHERE type=%s", (typ,)).fetchall()

def upsert_raw(it):
    bucket = it.get('bucket_date') or datetime.date.today().isoformat()
    with conn() as c:
        c.execute(
            """INSERT INTO news
               (url,title,source,source_country,lang,published_at,fetched_at,raw_content,bucket_date,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'raw')
               ON CONFLICT (url) DO NOTHING""",
            (it['url'], it['title'], it.get('source'), it.get('country'), it.get('lang'),
             it.get('published_at'), datetime.datetime.utcnow().isoformat(),
             it.get('raw_content', it['title']), bucket))

def get_unrefined(limit=5000):
    with conn() as c:
        return c.execute("SELECT * FROM news WHERE status='raw' LIMIT %s", (limit,)).fetchall()

def update_refined(news_id, r):
    status = 'refined' if r.get('relevant') else 'irrelevant'
    with conn() as c:
        c.execute(
            """UPDATE news SET status=%s, relevant=%s, category=%s, roles=%s, industry=%s, signal_type=%s,
               s_rel=%s, s_time=%s, s_act=%s, s_cred=%s, s_total=%s, comment=%s, action=%s, products=%s, citation=%s, refined_at=%s
               WHERE id=%s""",
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
            """SELECT * FROM news WHERE status='refined' AND relevant=1 AND roles LIKE %s
               ORDER BY s_total DESC LIMIT %s""",
            (f'%"{role}"%', top_n)).fetchall()

# ---- 按天回填用 ----
def list_bucket_dates():
    with conn() as c:
        rows = c.execute(
            "SELECT DISTINCT bucket_date FROM news WHERE status='refined' AND relevant=1 ORDER BY bucket_date").fetchall()
        return [r['bucket_date'] for r in rows]

def get_candidates(bucket_date, role, limit=60, lang=None):
    q = ["SELECT * FROM news WHERE status='refined' AND relevant=1 AND bucket_date=%s AND roles LIKE %s"]
    params = [bucket_date, f'%"{role}"%']
    if lang:                          # 'zh' / 'en'，按语言取候选
        q.append("AND lang=%s"); params.append(lang)
    q.append("ORDER BY s_total DESC LIMIT %s"); params.append(limit)
    with conn() as c:
        return c.execute(" ".join(q), tuple(params)).fetchall()
