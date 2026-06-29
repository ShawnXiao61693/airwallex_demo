# 一次性：给历史入库但 lang 为空的 news 行补打语言标签（按 title + 摘要判断）。
# 之后 compose 才能做「6 中 + 2 英」编排。用法：python set_lang.py
import db
from lang import detect_lang

def main():
    with db.conn() as c:
        rows = c.execute("SELECT id, title, raw_content FROM news WHERE lang IS NULL").fetchall()
        for r in rows:
            l = detect_lang((r['title'] or '') + ' ' + (r['raw_content'] or ''))
            c.execute("UPDATE news SET lang=%s WHERE id=%s", (l, r['id']))
        print(f"[set_lang] 已为 {len(rows)} 行补语言标签")
        # 汇总当前分布
        for row in c.execute("SELECT lang, count(*) n FROM news GROUP BY lang ORDER BY n DESC").fetchall():
            print(f"  lang={row['lang']}: {row['n']}")

if __name__ == '__main__':
    main()
