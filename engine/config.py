# 引擎配置 —— 数据源、分类法、LLM、阈值
import os

# ---- 数据源：GDELT 查询（关键词）。免费、免部署、免 key ----
# 覆盖：竞品 + 跨境支付 + 出海 + 监管。可继续加。
# 注意：竞品名里 Wise/Stripe/PingPong 等是常见英文词，单独 OR 会捞进大量噪音。
# 用精确短语 + 行业限定收紧；最终信号保证仍在 Refiner。查询需按效果持续调优。
GDELT_QUERIES = [
    '"Airwallex"',
    '"cross-border payment" OR "跨境支付"',
    '"跨境电商" OR "企业出海"',
    '"XTransfer" OR "WorldFirst" OR "stablecoin license"',
]
GDELT_MAXRECORDS = 20      # 每个查询最多取多少条
GDELT_TIMESPAN = '3d'      # 近 3 天

# ---- 情报分类法（喂给 Refiner）----
CATEGORIES = ['竞品', '监管牌照', '汇率宏观', '目标行业', '客户潜客', '我方生态']
ROLES = ['AE', 'AM']       # AE=拓新销售  AM=客户成功
INDUSTRIES = ['跨境电商/独立站', '游戏出海', 'OTA/旅游', 'SaaS', 'B2B外贸', '物流', '其他']

# ---- LLM（OpenAI 兼容接口；Kimi/OpenAI 等都可通过 base_url 切换）----
# 用环境变量，别把 key 写进代码：
#   export LLM_API_KEY=...      export LLM_BASE_URL=...     export LLM_MODEL=...
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o-mini')

DB_PATH = os.getenv('DB_PATH', 'engine.db')
DAILY_TOP_N = 8            # 每个角色日报取多少条
