# 报告 API（Flask）。nginx 反代 /api/* → 本服务(127.0.0.1:8090)。
# 统一报告（周报/月报，人工成品上传）：
#   POST /api/reports          上传成品（multipart：type=weekly|monthly + period + file），落草稿
#   GET  /api/reports?type=    列出该类型周期 slots + 状态（周=每周一，月=每月 1 号）
#   POST /api/reports/publish  标为已发布（type + period）
# 日报（AI 多候选）：/api/daily/{list,candidates,publish}
# 其他：/api/match /api/pitch /api/feedback /api/stats
# 旧端点 /api/weekly /api/slots /api/publish 保留为向后兼容别名
import os, datetime, json, re
from flask import Flask, request, jsonify
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
import db

app = Flask(__name__)
TOKEN = os.getenv('API_TOKEN', '')
NGINX_ROOT = os.getenv('NGINX_ROOT', '/usr/share/nginx/html/airwallex')
WEEKLY_DIR = os.path.join(NGINX_ROOT, 'data', 'weekly')
CLIENTS_PATH = os.path.join(NGINX_ROOT, 'data', 'clients.json')

llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

def _clients(role):
    try:
        data = json.load(open(CLIENTS_PATH, encoding='utf-8'))
        return data.get(role) or {}
    except Exception:
        return {}

def _news_brief(n):
    # 把前端传来的情报压成喂 LLM 的简述
    parts = [f"标题：{n.get('title','')}"]
    if n.get('summary'): parts.append(f"概览：{n['summary']}")
    if n.get('comment'): parts.append(f"对销售的意义：{n['comment']}")
    if n.get('category'): parts.append(f"分类：{'/'.join(n['category']) if isinstance(n['category'],list) else n['category']}")
    if n.get('industry'): parts.append(f"行业：{'/'.join(n['industry']) if isinstance(n['industry'],list) else n['industry']}")
    return "\n".join(parts)

# slots 范围：2026 年 6-7 月
SLOT_START = datetime.date(2026, 6, 1)
SLOT_END = datetime.date(2026, 7, 31)

def _auth():
    return bool(TOKEN) and request.headers.get('X-Api-Token') == TOKEN

# ============ 统一报告 API：reports（type = weekly / monthly）============
# 日报是 AI 多候选模型，走 /api/daily/*；周报、月报是人工成品上传，走这里。
REPORT_DIRS = {'weekly': 'weekly', 'monthly': 'monthly'}

def _next_month(d):
    return (d.replace(day=28) + datetime.timedelta(days=7)).replace(day=1)

def _gen_slots(typ):
    """生成该类型的周期 slots + 状态（weekly=每周一，monthly=每月 1 号）。"""
    pubs = {p['period']: p for p in db.list_publications(typ)}
    out = []
    if typ == 'monthly':
        d, step, unit = SLOT_START.replace(day=1), _next_month, '当月'
    else:
        d = SLOT_START
        while d.weekday() != 0:
            d += datetime.timedelta(days=1)
        step, unit = (lambda x: x + datetime.timedelta(days=7)), '当周'
    while d <= SLOT_END:
        per = d.isoformat()
        p = pubs.get(per)
        out.append({
            'period': per, 'publish_date': per, 'label': f'{per} {unit}',
            'state': p['status'] if p else 'empty',     # empty / draft / published
            'title': (p['title'] if p else '') or '',
            'url': (f"/airwallex/{p['html_path']}" if p else None),
        })
        d = step(d)
    return out

def _save_report(typ, period, title, f):
    dirn = REPORT_DIRS.get(typ, 'weekly')
    os.makedirs(os.path.join(NGINX_ROOT, 'data', dirn), exist_ok=True)
    rel = f'data/{dirn}/{period}.html'
    f.save(os.path.join(NGINX_ROOT, rel))
    db.upsert_publication(period, typ, title, rel)
    return rel

@app.post('/api/reports')            # 上传成品 → 草稿（需 token）
def reports_upload():
    if not _auth():
        return jsonify(error='unauthorized'), 401
    typ = request.form.get('type', 'weekly')
    if typ not in ('weekly', 'monthly'):
        return jsonify(error='type 必须是 weekly / monthly'), 400
    period = (request.form.get('period') or '').strip()
    title = request.form.get('title', '')
    f = request.files.get('file')
    if not period or not f:
        return jsonify(error='need form fields: type + period(YYYY-MM-DD) + file(html)'), 400
    try:
        datetime.date.fromisoformat(period)
    except ValueError:
        return jsonify(error='period 必须是 YYYY-MM-DD'), 400
    rel = _save_report(typ, period, title, f)
    return jsonify(ok=True, type=typ, period=period, status='draft', url=f'/airwallex/{rel}')

@app.get('/api/reports')             # 列出某类型的周期 slots + 状态
def reports_list():
    typ = request.args.get('type', 'weekly')
    return jsonify(type=typ, slots=_gen_slots(typ))

@app.post('/api/reports/publish')    # 标为已发布
def reports_publish():
    src = request.get_json(silent=True) or request.form
    period = (src.get('period') or '').strip()
    typ = src.get('type', 'weekly')
    if not period:
        return jsonify(error='need period'), 400
    db.set_published(period, typ)
    return jsonify(ok=True, type=typ, period=period, status='published')

# ---- 向后兼容旧端点（已弃用，等价于上面的 reports 调用）----
@app.post('/api/weekly')
def upload_weekly():
    if not _auth():
        return jsonify(error='unauthorized'), 401
    period = (request.form.get('period') or '').strip()
    title = request.form.get('title', '')
    f = request.files.get('file')
    if not period or not f:
        return jsonify(error='need period + file'), 400
    rel = _save_report('weekly', period, title, f)
    return jsonify(ok=True, period=period, status='draft', url=f'/airwallex/{rel}')

@app.get('/api/slots')
def slots():
    return jsonify(slots=_gen_slots(request.args.get('type', 'weekly')))

@app.post('/api/publish')
def publish():
    period = request.form.get('period', '').strip()
    typ = request.form.get('type', 'weekly')
    if not period:
        return jsonify(error='need period'), 400
    db.set_published(period, typ)
    return jsonify(ok=True, period=period, type=typ, status='published')

MATCH_PROMPT = """你是 Airwallex 销售情报助手。下面是一条市场情报，以及销售 {name}（{role_desc}）负责的客户名单。
判断这条情报和哪些客户相关，挑出**最相关的最多 3 个**；对每个客户说明为什么相关，以及一句可落地的切入角度。
只依据给定信息，不要编造客户。若没有明显相关的客户，matches 给空数组。

【情报】
{news}

【客户名单】
{clients}

只输出 JSON：{{"matches":[{{"client":"客户名","stage":"潜客/已成交","why":"为什么和这条相关","angle":"一句切入角度"}}]}}"""

PITCH_PROMPT = """你是 Airwallex 销售 {name}。结合下面这条情报，给客户「{client}」（{profile}）写一段可以直接发出去的开场话术。
要求：中文，60-120 字，自然口语、不夸张、有钩子，落到 Airwallex 能帮的点上。只输出话术正文，不要前后缀。

【情报】
{news}"""

def _llm_json(prompt):
    resp = llm.chat.completions.create(
        model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.3, timeout=60)
    txt = resp.choices[0].message.content
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else {}

@app.post('/api/match')
def match():
    body = request.get_json(force=True, silent=True) or {}
    role = body.get('role', 'AE')
    news = body.get('news') or {}
    acc = _clients(role)
    clients = acc.get('clients') or []
    if not clients:
        return jsonify(matches=[])
    clist = "\n".join(f"- {c['name']}（{c['stage']}，{c['industry']}）：{c['profile']}" for c in clients)
    prompt = MATCH_PROMPT.format(name=acc.get('name', ''), role_desc=acc.get('role_desc', ''),
                                 news=_news_brief(news), clients=clist)
    try:
        d = _llm_json(prompt)
        return jsonify(matches=d.get('matches', []))
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post('/api/pitch')
def pitch():
    body = request.get_json(force=True, silent=True) or {}
    role = body.get('role', 'AE')
    news = body.get('news') or {}
    client_name = body.get('client', '')
    acc = _clients(role)
    cli = next((c for c in (acc.get('clients') or []) if c['name'] == client_name), None)
    profile = cli['profile'] if cli else ''
    prompt = PITCH_PROMPT.format(name=acc.get('name', ''), client=client_name,
                                 profile=profile, news=_news_brief(news))
    try:
        resp = llm.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.4, timeout=60)
        return jsonify(pitch=resp.choices[0].message.content.strip())
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post('/api/feedback')
def feedback():
    body = request.get_json(force=True, silent=True) or {}
    news_id = body.get('news_id')
    role = body.get('role', '')
    vote = body.get('vote', '')
    if news_id is None or vote not in ('up', 'down'):
        return jsonify(error='need news_id + vote(up/down)'), 400
    db.add_feedback(news_id, role, vote)
    return jsonify(ok=True)

@app.get('/api/daily/list')
def daily_list():
    rows = db.list_daily_days()
    return jsonify(days=[{'date': r['bucket_date'], 'cands': r['cands'],
                          'published_no': r['published_no']} for r in rows])

@app.get('/api/daily/candidates')
def daily_candidates():
    date = request.args.get('date', '')
    out = []
    for r in db.get_daily_candidates(date):
        out.append({'cand_no': r['cand_no'], 'angle': r['angle'], 'lede': r['lede'],
                    'status': r['status'],
                    'ae': json.loads(r['ae_items'] or '[]'),
                    'am': json.loads(r['am_items'] or '[]')})
    return jsonify(date=date, candidates=out)

@app.post('/api/daily/publish')
def daily_publish():
    body = request.get_json(force=True, silent=True) or {}
    date = (body.get('date') or '').strip()
    cand_no = body.get('cand_no')
    if not date or cand_no is None:
        return jsonify(error='need date + cand_no'), 400
    db.publish_daily(date, int(cand_no))
    import compose
    compose.write_published_files()      # 重写 report_<date>.json + index.json
    return jsonify(ok=True, date=date, cand_no=int(cand_no))

@app.get('/api/stats')
def stats():
    # 数据看板：合格情报量 + 真实反馈（埋点）+ 最受认可的情报
    with db.conn() as c:
        refined = c.execute("SELECT count(*) n FROM news WHERE status='refined' AND relevant=1").fetchone()['n']
        total_news = c.execute("SELECT count(*) n FROM news").fetchone()['n']
        # 日报：覆盖天数 + 候选总数
        daily_days = c.execute("SELECT count(DISTINCT bucket_date) n FROM daily_reports").fetchone()['n']
        daily_cands = c.execute("SELECT count(*) n FROM daily_reports").fetchone()['n']
        # 周/月报已发布数
        pub = {f"{r['type']}_{r['status']}": r['n'] for r in
               c.execute("SELECT type, status, count(*) n FROM publications GROUP BY type, status").fetchall()}
        votes = {r['vote']: r['n'] for r in
                 c.execute("SELECT vote, count(*) n FROM feedback GROUP BY vote").fetchall()}
        top = c.execute(
            """SELECT n.title, count(*) up FROM feedback f JOIN news n ON n.id=f.news_id
               WHERE f.vote='up' GROUP BY n.title ORDER BY up DESC LIMIT 5""").fetchall()
    up, down = votes.get('up', 0), votes.get('down', 0)
    total = up + down
    return jsonify(refined=refined, total_news=total_news,
                   daily_days=daily_days, daily_cands=daily_cands,
                   weekly_published=pub.get('weekly_published', 0),
                   monthly_published=pub.get('monthly_published', 0),
                   up=up, down=down, feedback_total=total,
                   useful_rate=(round(100 * up / total) if total else None),
                   top=[{'title': r['title'], 'up': r['up']} for r in top])

@app.get('/api/health')
def health():
    return jsonify(ok=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8090)
