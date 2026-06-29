# 引擎配置 —— 数据源、分类法、LLM、阈值
import os

# ---- 数据源：Brave Search API（新闻搜索）----
# 支持中文查询、结果自带摘要(description)，refine 上下文更足。
# 覆盖：竞品 + 跨境支付 + 出海 + 监管。可继续加。
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY', '')
BRAVE_QUERIES = [
    'Airwallex 空中云汇 最新',
    'PingPong 跨境支付',
    'XTransfer 外贸 跨境',
    '万里汇 WorldFirst 跨境',
    '连连 跨境支付',
    '跨境支付 出海 新规 监管',
    '跨境电商 政策 平台',
    '稳定币 牌照 跨境',
    '企业出海 融资 新市场',
]
BRAVE_COUNT = 10           # 每查询取多少条
BRAVE_FRESHNESS = 'pw'     # pd=近一天 / pw=近一周 / pm=近一月

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
