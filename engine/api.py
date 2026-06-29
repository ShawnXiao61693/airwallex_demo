# 周报上传/审核 API（Flask）。nginx 反代 /api/* → 本服务(127.0.0.1:8090)。
# 端点：
#   POST /api/weekly   上传周报 HTML（多部分：period + file），落成草稿
#   POST /api/publish  把某期标为已发布（周/月通用，也可给日报复用）
#   GET  /api/slots    列出周期 slots（6-7月每周一）+ 状态，供后台「周报审核」渲染
import os, datetime
from flask import Flask, request, jsonify
import db

app = Flask(__name__)
TOKEN = os.getenv('API_TOKEN', '')
NGINX_ROOT = os.getenv('NGINX_ROOT', '/usr/share/nginx/html/airwallex')
WEEKLY_DIR = os.path.join(NGINX_ROOT, 'data', 'weekly')

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

@app.get('/api/health')
def health():
    return jsonify(ok=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8090)
