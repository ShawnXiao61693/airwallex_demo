---
name: deploy-report
description: Use when a finished weekly or monthly report HTML for the Airwallex 销售情报 demo needs to go online — uploading it through the platform's report API so it appears as a draft in the RevE 审核 backend. Triggers include "上线周报"、"上线月报"、"发布周报/月报"、"把报告传上去", or a just-uploaded report showing 404 / no styling / broken media.
---

# 上线报告（周报 / 月报）

## Overview

把**人工做好的周报或月报 HTML** 通过统一接口送上线。流程：**上传 → 草稿（draft）→ 人审 → 发布（published）**。

**核心原则：只传到草稿，发布由人点。** 上传是机器的事，发布是 RevE 的人审环节。除非用户明确要求，**不要自动发布**。

> 日报不走这里——日报是 AI 多候选模型，走 `/api/daily/*`，由另一套流程产出。本 skill 只管**周报 / 月报**这两种"人工成品上传"。

## When to Use

- 有一份做好的周报或月报 HTML（如仓库 `web/weekly.html` / `web/monthly.html`），要让它线上能打开。
- 上传后页面 404、样式全丢、或内嵌视频/音频不播 → 多半是资产/媒体路径坑（见下）。

不适用：报告内容的**制作**（选题/转化/出题）；日报的任何部分。

## Quick Reference

| 项 | 值 |
|---|---|
| 平台服务器 | `http://13.214.205.219`（AirWallex demo 专用） |
| SSH | `ssh -i "~/Downloads/PEM密钥/airwallex.pem" ec2-user@13.214.205.219`（用户 **ec2-user**，Amazon Linux） |
| 上传接口 | `POST /api/reports`，header `X-Api-Token`，multipart：`type`、`period`、`title`、`file` |
| `type` | `weekly` 或 `monthly` |
| `period` | `YYYY-MM-DD`：**周报=当周周一**，**月报=当月 1 号** |
| 服务路径 | 周报 `/airwallex/data/weekly/<period>.html`、月报 `/airwallex/data/monthly/<period>.html` |
| 平台样式 | `/airwallex/assets/style.css`（绝对路径，已验证可访问） |
| 媒体目录 | `/airwallex/data/media/<file>`（视频/音频放这里） |
| 列 slots | `GET /api/reports?type=weekly\|monthly` |
| 发布 | `POST /api/reports/publish`（form/json：`type` + `period`）|
| Token 位置 | 服务器 `~/airwallex/engine/.env` 的 `API_TOKEN`（别写进任何提交/文档）|
| 后台审核 | `http://13.214.205.219/airwallex/admin.html` →「周报审核 / 月报审核」 |
| 接口全文档 | 仓库 `docs/周报上传接口.md` |

> 旧端点 `/api/weekly`、`/api/slots`、`/api/publish` 仍作兼容别名（等价于 `type=weekly`），新代码统一用 `/api/reports`。

## 步骤

### 1. 修资产路径（最容易踩的坑）

报告被服务在 `/airwallex/data/<type>/<period>.html`（比根目录深两层）。页面里的**相对**路径会解析到 `…/data/<type>/assets/` → **404、样式全丢**。

做一份**上传专用副本**，把样式引用改成**绝对路径**（或把 CSS 内联）：

```
<!-- ❌ 仓库里是相对路径（本地预览用，别上传这份） -->
<link rel="stylesheet" href="assets/style.css">
<!-- ✅ 上传副本改成绝对路径 -->
<link rel="stylesheet" href="/airwallex/assets/style.css">
```

跨页导航链接同理改绝对：`/airwallex/app.html`、`/airwallex/data/weekly/<p>.html`、`/airwallex/data/monthly/<p>.html`。保留仓库原文件的相对路径（方便本地 `python3 -m http.server` 预览），只改副本。

### 2. 定 type 与 period

- 周报：`type=weekly`，`period=` 当周周一（如 `2026-06-22`）。
- 月报：`type=monthly`，`period=` 当月 1 号（如 `2026-06-01`）。
- 先查现有 slots 避免覆盖：`curl "http://13.214.205.219/api/reports?type=monthly"`。

### 3. 拿 Token

```bash
ssh -i "~/Downloads/PEM密钥/airwallex.pem" ec2-user@13.214.205.219 \
  'grep API_TOKEN ~/airwallex/engine/.env'
```
（SSH 连不上就找 Shawn 要。token 别落进 git / 文档 / 聊天记录之外的地方。）

### 4. 上传（→ 草稿）

```bash
curl -X POST "http://13.214.205.219/api/reports" \
  -H "X-Api-Token: $API_TOKEN" \
  -F "type=monthly" \
  -F "period=2026-06-01" \
  -F "title=6月月报特刊·跨境支付的地壳动了" \
  -F "file=@monthly_deploy.html"
# → {"ok":true,"type":"monthly","period":"2026-06-01","status":"draft","url":"/airwallex/data/monthly/2026-06-01.html"}
```

### 5. 嵌媒体（视频 / 音频，月报常用）

报告里用绝对路径引用媒体，文件单独放到服务器媒体目录：

```html
<video controls preload="metadata" src="/airwallex/data/media/xxx.mp4"></video>
<audio controls preload="metadata" src="/airwallex/data/media/xxx.m4a"></audio>
```

媒体文件**不能走 `/api/reports`（只收 HTML）**，要 scp 到 `/usr/share/nginx/html/airwallex/data/media/`：

```bash
scp -i "$KEY" video.mp4 ec2-user@13.214.205.219:/tmp/v.mp4
ssh -i "$KEY" ec2-user@13.214.205.219 \
  'sudo mkdir -p /usr/share/nginx/html/airwallex/data/media && \
   sudo cp /tmp/v.mp4 /usr/share/nginx/html/airwallex/data/media/xxx.mp4 && \
   sudo chmod 644 /usr/share/nginx/html/airwallex/data/media/xxx.mp4'
```

⚠️ **scp / sudo 写 nginx 根目录是敏感操作**（CLAUDE.md「不可自动 scp 推送」红线，会被安全拦截）——**必须 Shawn 明确授权或由他本人执行**，不要默认自动跑。文件名用 ASCII，避免 URL 编码问题。

### 6. 验证（必须，发布前自检）

```bash
B=http://13.214.205.219; P=2026-06-01; T=monthly
curl -s -o /dev/null -w "draft %{http_code}\n" "$B/airwallex/data/$T/$P.html"        # 期望 200
curl -s "$B/airwallex/data/$T/$P.html" | grep -c "/airwallex/assets/style.css"        # 期望 ≥1（绝对路径）
curl -s -o /dev/null -w "css %{http_code}\n" "$B/airwallex/assets/style.css"           # 期望 200
curl -s "$B/api/reports?type=$T" | grep "\"$P\""                                       # 期望 state=draft
# 有媒体再验：
curl -s -o /dev/null -w "media %{http_code}\n" -r 0-0 "$B/airwallex/data/media/xxx.mp4" # 期望 206
```
（可再用浏览器打开草稿 URL，确认翻页/样式/媒体都正常。）

### 7. STOP — 人审后发布

把草稿 URL 给 RevE / Shawn，请其在后台「周报审核 / 月报审核」预览后点「通过发布」。
**不要替人点发布**，除非用户明确说"直接发布"。真要发布：`POST /api/reports/publish`，form/json `type=… & period=…`。

## Common Mistakes

| 现象 | 原因 / 修复 |
|---|---|
| 草稿打开后样式全丢 | 相对路径 → 404。改绝对 `/airwallex/assets/style.css` 或内联（步骤 1）。 |
| 内嵌视频/音频不播 | 媒体没上传，或路径不是绝对 `/airwallex/data/media/…`；媒体走 scp 不走 API（步骤 5）。 |
| 月报传成了周报 | `type` 没设或设错；月报必须 `type=monthly`、period 用当月 1 号。 |
| 草稿在后台列表不显示 | period 不在 6–7 月的合法档（周一 / 每月 1 号）；用 `/api/reports?type=` 查合法档。 |
| 覆盖了别人的草稿 | 同 `type`+`period` 重传 = 覆盖并重置为 draft。先查 slots。 |
| 上传了就当上线了 | 那只是草稿，需人审点「通过发布」才真正 published。 |
| 想上传日报 | 日报不走这里，是 `/api/daily/*` 的 AI 多候选流程。 |

## Notes

- 这台服务器 SSH/HTTP 都通（与老的 `47.129.174.5` 不同，那台有 IP 白名单）。
- 报告内容若取自 demo 的 `data.js` / 引擎库，新闻真伪/数字对外前须复核。
