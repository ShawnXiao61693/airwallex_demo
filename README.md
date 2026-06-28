# Airwallex 销售情报平台 · Demo

> 作业：站在 Airwallex 角度，设计并实现一个「市场信息 / 新闻收集与分析」工具，稳定产出日报 / 周报 / 月报，信噪比要高。
> 本仓库 = 方案 + 可运行的前端 demo + 真实样例。

## 一句话

**这道题表面是"收集新闻"，本质是一道销售赋能题：把海量、低价值的市场信息，转化为一线销售能直接使用的成交能力。** 同样一句"做新闻工具"，可以交出一个没人用的聚合器，也可以交出一个改变销售产出的系统——差别不在技术，而在于先回答了"为谁、解决什么"。

## 怎么看

```bash
cd web && python3 -m http.server 8000
# 浏览器打开 http://localhost:8000
```
四个页面：
- `index.html` — 首页，三个入口
- `solution.html` — 完整解题思路
- `app.html` — 用户端：注册选身份（AE / AM）→ 看到按角色差异化的日报 → 一键生成客户话术
- `admin.html` — RevE 工作台：采集策略、日 / 周 / 月报审核（含时间设置）、数据统计、用户列表

## 解题思路（精简）

1. **问题界定**：岗位是 Revenue Enablement，所以把题目重定义为"为一线销售，把市场信息转化为成交能力"。信噪比从此是必须守住的**约束**，而非核心。
2. **用户**：运营主体是 RevE → 用户必然是它服务的人：**AE（拓新 / Hunter）+ AM（客户成功 / Farmer）**。两类角色情报需求不同。
3. **决定性论据**：几乎每份销售 JD 都写着"跟进行业趋势、做行业动态代言人"——市场情报是 Airwallex 自己写进考核的硬职责，却没有工具支撑。本平台填的正是这个缺口。
4. **三种产品**：不是同一内容的三种长度，而是沿"周期越长、自动化越低、人的判断越重"展开——日报全自动 / 周报半自动 / 月报人主导。信噪比分解进每种：日报靠过滤、周报靠选择、月报靠判断。
5. **如何触达（Reach · Teach · Engage）**：让情报按角色到达（日报）→ 炼成可复用话术与培训（周报）→ 让销售主动参与、行为可追踪（按钮、自测、反馈回路）。

## 架构

```mermaid
flowchart TB
  S["数据源<br/>RSSHub·DailyHotApi·GDELT·we-mp-rss·Crawl4AI·Tavily/Exa"]

  subgraph PIPE["主链路"]
    direction LR
    C["Collector 采集<br/>Engine·薄摄取层"]
    R["Refiner 提炼<br/>Agent·LLM"]
    CO["Composer 制作<br/>Agent·仅日报"]
    RV["审核发布<br/>RevE工作台·人"]
    D["Distributor 分发<br/>Engine·按角色·可归因链接"]
    FE["用户端<br/>HTML·按角色渲染"]
    U["销售 AE/AM"]
  end

  subgraph DB["数据库 自建 Postgres + pgvector"]
    NEWS[("news 表<br/>status raw→refined + embedding")]
    REP[("report<br/>日报·item_ids")]
    PUB[("publication<br/>周/月·HTML")]
    VEC["共享向量层<br/>去重·检索·聚类"]
  end

  subgraph CROSS["贯穿层"]
    UC["用户中心<br/>身份·角色·客户档案"]
    TR["实名埋点"]
    EV[("events 行为库")]
    DASH["数据看板<br/>采用漏斗·内容效果·参与"]
  end

  MAN["手搓上传<br/>周/月报 HTML"]
  EN["Engage 实时话术Agent<br/>个性化按钮"]

  S --> C
  C -->|写raw| NEWS
  NEWS <-->|读raw·写refined| R
  NEWS -->|读refined| CO
  CO -->|写日报| REP
  CO --> RV
  MAN -->|写| PUB
  MAN -.送审.-> RV
  RV -->|发布| D
  REP -.读已发布.-> D
  PUB -.读已发布.-> D
  D --> FE --> U

  UC -.路由.-> D
  UC -.个性化.-> FE
  U <-->|按钮·话术| EN
  U -.实名事件.-> TR --> EV --> DASH
  DASH -.反馈回路·调策略.-> R
```

技术栈全部开源、可自托管（Postgres+pgvector / Git / Nginx / Python），可跑在一台 EC2 上；唯一外部付费项是 LLM API。

## Demo 范围与取舍

敢于取舍本身是方案的一部分。本次聚焦：**日报**为核心（真实新闻 + 信噪比过滤 + 按角色差异化 + 个性化话术按钮）+ **周报 / 月报**样例 + **RevE 工作台**。明确不做：CRM 整合、全自动替代人写话术、多语言全球版、秒级实时——不在"用最小的东西证明方案成立"的关键路径上。

## 已知局限

- 参与数据（打开率 / 点击 / 答题）与销售真实业绩、KPI 的因果关系尚无法证明，当前仅作参考。
- 采集对微信 / 小红书生态内的、以及付费源的新闻覆盖有限。
- 月报「人主导」意味着样例含人工编辑成分；当前 demo 的报告内容为同一份（日 / 周 / 月暂不做内容区别）。

## 目录

```
web/        前端四页 + 设计系统
docs/       产品方案、架构图
samples/    日报 / 周报 / 月报样例（真实新闻跑出）
```
