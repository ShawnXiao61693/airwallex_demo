# Refiner（提炼 · Agent/LLM）—— 读 raw → 逐条判断相关性/打标/评分/炼点评动作 → 回写
# 这是我们的差异化核心，也是可 review 的部分：逻辑全在下面这段 prompt 里。
import json, re, time, concurrent.futures as cf
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, CATEGORIES, INDUSTRIES
import db

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

PROMPT = """你是 Airwallex（空中云汇，跨境支付/金融科技公司）的销售情报分析员。
针对下面这条新闻，判断它对 Airwallex 的一线销售是否有用，并打标、评分、提炼成可直接用的弹药。
要求：只依据给定信息，不要编造；若与 Airwallex 销售无关，relevant 设为 false。

分类 category 只能从这 6 类里选(可多选)：{cats}
  · 我方生态 = Airwallex/空中云汇 自己的消息（融资/新品/牌照/高管/合作）。
  · 竞品 = 其他公司：PingPong / 连连 / 万里汇(WorldFirst) / XTransfer / Wise / Stripe / 蚂蚁国际 等。
  · 关键：Airwallex 自己的新闻只归"我方生态"，绝不要标成"竞品"。
角色 roles：AE(拓新销售) / AM(客户成功)，可多选。
行业 industry：{inds}
信号类型 signal_type（只填一个）：线索 / 触发 / 竞品 / 话题 / 雷区

新闻：
标题：{title}
摘要：{summary}
来源：{source}　时间：{date}

只输出一个 JSON 对象（分数 0~1）：
{{"relevant": true/false,
  "category": ["..."], "roles": ["AE"|"AM"], "industry": ["..."], "signal_type": "...",
  "s_rel": 0.0, "s_time": 0.0, "s_act": 0.0, "s_cred": 0.0, "s_total": 0.0,
  "summary": "一句话客观概述这条新闻本身讲了什么(中文，不带评价)",
  "comment": "一句话点评：这条对销售意味着什么(so-what)，要具体",
  "action": "建议销售下一步做什么动作，要具体",
  "products": ["关联的 Airwallex 产品"],
  "citation": "用于佐证的出处(标题/来源)"}}"""

def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else None

WORKERS = 12   # 并发条数

def _refine_one(row):
    p = PROMPT.format(cats="/".join(CATEGORIES), inds="/".join(INDUSTRIES),
                      title=row['title'], summary=(row['raw_content'] or '')[:500],
                      source=row['source'], date=row['published_at'])
    for attempt in range(3):                      # 限流/抖动重试
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "user", "content": p}],
                temperature=0.2, timeout=60)
            r = _parse(resp.choices[0].message.content)
            if r is None:
                raise ValueError("无法解析 JSON")
            return row['id'], r
        except Exception:
            if attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            raise

def refine(workers=WORKERS):
    rows = db.get_unrefined()
    print(f"[refine] 待加工 {len(rows)} 条，并发 {workers}")
    ok = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_refine_one, row): row['id'] for row in rows}
        for fut in cf.as_completed(futs):
            rid = futs[fut]
            try:
                _id, r = fut.result()
            except Exception as e:
                print(f"[refine] 跳过 id={rid}: {e}")
                continue
            db.update_refined(_id, r)             # 主线程写库，避免 SQLite 并发锁
            ok += 1
    print(f"[refine] 完成，成功加工 {ok} 条")
