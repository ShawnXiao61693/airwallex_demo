# engine —— 后端引擎

销售情报平台的后端：把新闻从外部抓进来 → LLM 提炼评分 → 编排成日报 → 存库 → 供前端/后台读取。
日报全自动走这条链路；周报由外部 agent 人工编排后经 API 上传审核。

> 部署：服务器 `~/airwallex/engine/`，venv `.venv`(py3.9)。数据库用 Supabase（托管 Postgres）。所有 key 在 `.env`（见 `.env.example`）。

---

## 数据流主链路（一条新闻的一生）

```
Brave News API
   │  collect.py   采集，归一化，入库
   ▼
news 表 (raw) ──────────── db.py（Supabase Postgres）
   │  refine.py    并发 LLM：判相关性 / 打标 / 评分 / 炼点评
   ▼
news 表 (refined / irrelevant)
   │  compose.py   按「天 × 角色」编排 LLM：去重 + 多样化 + 排序 + 导语
   ▼
data/reports/*.json  →  前端 app.html 按角色展示
```

| 文件 | 角色 | 用途 |
|---|---|---|
| `collect.py` | **Collector 采集** | 用 Brave Search API 按 `config` 里的查询拉新闻，归一化字段后写入 `news` 表（status=raw，按 URL 去重）。 |
| `refine.py` | **Refiner 提炼** | 读 raw，**并发 12 路** 调 LLM：判断对销售是否有用、打分类/角色/行业标签、给信号强度评分、炼成可直接用的"弹药"点评，回写 `news`（refined / irrelevant）。差异化核心，逻辑全在 prompt 里。 |
| `compose.py` | **Composer 制作** | 按「天 × 角色(AE/AM)」用编排 LLM 出日报：同事件去重、保证多样性、排序、写导语，产出 `data/reports/report_<date>_<role>.json` + `index.json`。仅日报走它。 |

---

## 数据与配置

| 文件 | 用途 |
|---|---|
| `db.py` | **数据层**。封装 Supabase Postgres（走 pooler 连接串 `DATABASE_URL`）。一张 `news` 表（raw→refined→irrelevant）+ 一张 `publications` 表（周/月报期数与状态）。提供 upsert/查询/状态更新等 helper。本质是标准 PG，将来自托管换连接串即可。 |
| `config.py` | **配置中心**。Brave 查询词、新闻分类法、角色/行业枚举、LLM（key/base_url/model，从环境读）、日报条数等阈值。 |
| `.env.example` | 环境变量模板。`cp .env.example .env` 后填入 `LLM_API_KEY`(OpenRouter)、`BRAVE_API_KEY`、`DATABASE_URL`(Supabase)、`API_TOKEN`。`.env` 已被 gitignore。 |
| `requirements.txt` | 依赖：`requests`、`openai`、`psycopg[binary]`、`flask`。 |

---

## 服务与运维

| 文件 | 用途 |
|---|---|
| `api.py` | **周报上传/审核 Flask API**（systemd 服务 `airwallex-api`，:8090，nginx `/api` 反代）。`POST /api/weekly` 上传周报 HTML 落成草稿（需 token）、`POST /api/publish` 标为已发布、`GET /api/slots` 列出周期 slots 及状态供后台渲染。上传契约见 `docs/周报上传接口.md`。 |
| `run.py` | 串起主链路：`collect → refine → compose`。生产由定时任务跑它。 |
| `run.sh` | 一键脚本：加载 `.env` → 跑 `run.py` → `export.py` 导库 → 同步日报 JSON 到 nginx 目录。 |
| `export.py` | 把 `news` 表导成前端可读 JSON（供后台「情报库」页浏览），带统计（总数/已提炼/无关/raw）。`run.sh` 末尾会调它。 |
| `backfill.py` | **历史回填**：对日期区间内每天用 Brave 拉那天的新闻 → 提炼 → 按天编排出日报。用法 `python backfill.py 2026-06-22 2026-06-28`。 |

---

## 跑起来

```bash
cd engine
cp .env.example .env          # 填入 LLM / Brave / DATABASE_URL / API_TOKEN
python -m venv .venv && .venv/bin/pip install -r requirements.txt

./run.sh                      # 跑一遍主链路 + 导出
# 或回填历史：
.venv/bin/python backfill.py 2026-06-22 2026-06-28
```

## 现在是什么、不是什么（诚实说明）

- **是**：真实采集 + 真实 LLM 提炼评分 + 编排出真日报，整条管道在线上能跑。
- **基于标题 + 摘要加工**：Brave 给标题/来源/摘要；正文需再抓（Crawl4AI/trafilatura）——下一步，能显著提升点评质量。
- **去重**：先按 URL + compose 阶段编排 LLM 同事件去重；语义去重（pgvector + embedding）后续加。
- **周报/月报**：不走本引擎。周报经 `api.py` 上传审核；月报暂缓。
