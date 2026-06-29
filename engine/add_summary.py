# 一次性：给已提炼但 summary 为空的 news 行补「一句话新闻概述」（中文、客观、不带评价）。
# 只补 summary，不动 comment/action。并发跑。用法：python add_summary.py
import time, concurrent.futures as cf
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
import db

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
WORKERS = 12

PROMPT = """用一句中文客观概括下面这条新闻本身讲了什么，不要评价、不要建议，只陈述事实。
只输出这一句话（不超过 50 字）。

标题：{title}
摘要：{summary}"""

def _one(row):
    p = PROMPT.format(title=row['title'], summary=(row['raw_content'] or '')[:500])
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "user", "content": p}],
                temperature=0.2, timeout=60)
            return row['id'], resp.choices[0].message.content.strip().strip('"「」')
        except Exception:
            if attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            raise

def main():
    with db.conn() as c:
        rows = c.execute(
            "SELECT id, title, raw_content FROM news WHERE status='refined' AND relevant=1 AND (summary IS NULL OR summary='')").fetchall()
    print(f"[add_summary] 待补 {len(rows)} 条，并发 {WORKERS}")
    ok = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_one, r): r['id'] for r in rows}
        for fut in cf.as_completed(futs):
            rid = futs[fut]
            try:
                _id, s = fut.result()
            except Exception as e:
                print(f"[add_summary] 跳过 id={rid}: {e}"); continue
            with db.conn() as c:
                c.execute("UPDATE news SET summary=%s WHERE id=%s", (s, _id))
            ok += 1
    print(f"[add_summary] 完成，补了 {ok} 条")

if __name__ == '__main__':
    main()
