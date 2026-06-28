# 串起整条最小链路：采集 → 提炼 → 制作。生产环境由 cron 定时跑这一个文件。
import db, collect, refine, compose

if __name__ == '__main__':
    db.init_db()
    collect.collect()   # GDELT → news(raw)
    refine.refine()     # LLM 打标评分 → news(refined)
    compose.compose()   # 出 daily_AE.json / daily_AM.json
    print("✅ 完成：daily_AE.json / daily_AM.json")
