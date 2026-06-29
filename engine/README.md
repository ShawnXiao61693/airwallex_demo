# engine —— 日报引擎（最小可跑切片）

一条真能跑的链路：**采集 → 提炼 → 制作**，产出真实日报 JSON（供前端渲染）。
对应架构里的 Collector / Refiner / Composer，数据落在一张 `news` 表（SQLite）。

```
collect.py   Collector  Brave Search API 拉真实新闻 → news(raw)
refine.py    Refiner    LLM 逐条判断/打标/评分/炼点评动作 → news(refined)
compose.py   Composer   按角色取数 → daily_AE.json / daily_AM.json
db.py        一张 news 表（status: raw→refined→irrelevant）
run.py       串起来（生产由 cron 跑它）
```

## 跑起来

```bash
cd engine
pip install -r requirements.txt

# 配 LLM（OpenAI 兼容；用 Kimi 就填 Kimi 的 base_url/model）
export LLM_API_KEY=你的key
export LLM_BASE_URL=https://api.openai.com/v1     # Kimi: https://api.moonshot.cn/v1
export LLM_MODEL=gpt-4o-mini                       # Kimi: 例如 kimi-k2 / moonshot-v1-8k

python run.py        # → 生成 daily_AE.json / daily_AM.json
```

采集需配 `BRAVE_API_KEY`（免费版即可），可单独验证：`python -c "import db,collect; db.init_db(); collect.collect()"`

## 现在是什么、不是什么（诚实说明）

- **是**：真实采集 + 真实 LLM 打标评分 + 出真日报 JSON，整条管道能跑。
- **暂用 SQLite**：量大再换 Postgres + pgvector（schema 一致）。
- **基于标题+摘要加工**：Brave 给标题/来源/摘要(description)；正文需要再抓（Crawl4AI/trafilatura）——列入下一步，能显著提升点评质量。
- **Composer 暂为确定性 top-N**：策展 LLM（整组精选+排序+导语）是下一步升级（见 compose.py TODO）。
- **去重**：先按 URL；语义去重（pgvector + embedding）后续加。
- **周报/月报**：不走本引擎，手搓上传。

## 下一步

正文抓取 → 语义去重 → Composer 策展 LLM → 推送(飞书) → 埋点回流。
