# 周报上传/审核 API（Flask）。nginx 反代 /api/* → 本服务(127.0.0.1:8090)。
# 端点：
#   POST /api/weekly   上传周报 HTML（多部分：period + file），落成草稿
#   POST /api/publish  把某期标为已发布（周/月通用，也可给日报复用）
#   GET  /api/slots    列出周期 slots（6-7月每周一）+ 状态，供后台「周报审核」渲染
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

@app.post('/api/weekly')
def upload_weekly():
    if not _auth():
        return jsonify(error='unauthorized'), 401
    period = (request.form.get('period') or '').strip()      # 当周周一 YYYY-MM-DD
    title = request.form.get('title', '')
    f = request.files.get('file')
    if not period or not f:
        return jsonify(error='need form fields: period(YYYY-MM-DD 周一) + file(html)'), 400
    try:
        datetime.date.fromisoformat(period)
    except ValueError:
        return jsonify(error='period 必须是 YYYY-MM-DD'), 400
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    rel = f'data/weekly/{period}.html'
    f.save(os.path.join(NGINX_ROOT, 'data', 'weekly', f'{period}.html'))
    db.upsert_publication(period, 'weekly', title, rel)
    return jsonify(ok=True, period=period, status='draft',
                   url=f'/airwallex/{rel}')

@app.post('/api/publish')
def publish():
    # demo：发布由操作台触发，不要求 token（上传 /api/weekly 仍需 token）。
    # 生产应把整个 admin 放到登录后。
    period = request.form.get('period', '').strip()
    typ = request.form.get('type', 'weekly')
    if not period:
        return jsonify(error='need period'), 400
    db.set_published(period, typ)
    return jsonify(ok=True, period=period, type=typ, status='published')

@app.get('/api/slots')
def slots():
    typ = request.args.get('type', 'weekly')
    pubs = {p['period']: p for p in db.list_publications(typ)}
    out = []
    d = SLOT_START
    while d.weekday() != 0:          # 移到第一个周一
        d += datetime.timedelta(days=1)
    while d <= SLOT_END:
        per = d.isoformat()
        p = pubs.get(per)
        out.append({
            'period': per, 'publish_date': per,      # 发布日 = 当周周一
            'label': f'{per} 当周',
            'state': p['status'] if p else 'empty',  # empty / draft / published
            'title': (p['title'] if p else '') or '',
            'url': (f"/airwallex/{p['html_path']}" if p else None),
        })
        d += datetime.timedelta(days=7)
    return jsonify(slots=out)

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

@app.get('/api/health')
def health():
    return jsonify(ok=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8090)
