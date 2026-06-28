# Refiner（提炼 · Agent/LLM）—— 读 raw → 逐条判断相关性/打标/评分/炼点评动作 → 回写
# 这是我们的差异化核心，也是可 review 的部分：逻辑全在下面这段 prompt 里。
import json, re
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, CATEGORIES, INDUSTRIES
import db

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

PROMPT = """你是 Airwallex（空中云汇，跨境支付/金融科技公司）的销售情报分析员。
针对下面这条新闻，判断它对 Airwallex 的一线销售是否有用，并打标、评分、提炼成可直接用的弹药。
要求：只依据给定信息，不要编造；若与 Airwallex 销售无关，relevant 设为 false。

可选分类(可多选)：{cats}
角色：AE(拓新销售) / AM(客户成功)
可选行业：{inds}
信号类型：线索 / 触发 / 竞品 / 话题 / 雷区

新闻：
标题：{title}
来源：{source}（{country}）
时间：{date}

只输出一个 JSON 对象，字段如下（分数 0~1）：
{{"relevant": true/false,
  "category": ["..."], "roles": ["AE"|"AM"], "industry": ["..."], "signal_type": "...",
  "s_rel": 0.0, "s_time": 0.0, "s_act": 0.0, "s_cred": 0.0, "s_total": 0.0,
  "comment": "一句话点评：这条对销售意味着什么(so-what)",
  "action": "建议销售下一步做什么动作",
  "products": ["关联的 Airwallex 产品"],
  "citation": "用于佐证的出处(标题/来源)"}}"""

def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else None

def refine():
    rows = db.get_unrefined()
    print(f"[refine] 待加工 {len(rows)} 条")
    ok = 0
    for row in rows:
        p = PROMPT.format(cats="/".join(CATEGORIES), inds="/".join(INDUSTRIES),
                          title=row['title'], source=row['source'],
                          country=row['source_country'], date=row['published_at'])
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "user", "content": p}], temperature=0.2)
            r = _parse(resp.choices[0].message.content)
            if r is None:
                raise ValueError("无法解析 JSON")
        except Exception as e:
            print(f"[refine] 跳过 id={row['id']}: {e}")
            continue
        db.update_refined(row['id'], r)
        ok += 1
    print(f"[refine] 完成，成功加工 {ok} 条")
