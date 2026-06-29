---
name: deploy-weekly-report
description: Use when a finished weekly-report HTML for the Airwallex 销售情报 demo needs to go online — uploading it to the platform so it appears as a draft in the RevE 周报审核 backend. Triggers include "上线周报"、"发布周报"、"把周报传上去", or a just-uploaded weekly showing 404 / no styling.
---

# 上线周报（部署周报到平台）

## Overview

把一份**人工策展好的周报 HTML** 通过平台上传接口送上线。核心流程：**上传 → 草稿（draft）→ 人审 → 发布（published）**。

**核心原则：只传到草稿，发布由人点。** 上传是机器的事，发布是 RevE 的人审环节（你们设计里就是这样）。除非用户明确要求，**不要自动发布**。

## When to Use

- 有一份做好的周报 HTML（如仓库 `web/weekly.html`），要让它线上能打开。
- 上传后页面 404 或样式全丢 → 多半是资产路径坑（见下）。

不适用：周报内容的"制作"（选题/转化/出题）——那是另一件事。本 skill 只管"已经做好了，怎么上线"。

## Quick Reference

| 项 | 值 |
|---|---|
| 平台服务器 | `http://13.214.205.219`（AirWallex demo 专用，非老的 ClawnServer） |
| SSH | `ssh -i "~/Downloads/PEM密钥/airwallex.pem" ec2-user@13.214.205.219`（用户 **ec2-user**，Amazon Linux） |
| 上传接口 | `POST /api/weekly`，header `X-Api-Token`，multipart：`period`、`title`、`file` |
| Token 位置 | 服务器 `~/airwallex/engine/.env` 的 `API_TOKEN`（别写进任何提交/文档） |
| 上传后服务路径 | `/airwallex/data/weekly/<period>.html` |
| 平台样式 | `/airwallex/assets/style.css`（绝对路径，已验证可访问） |
| 后台审核 | `http://13.214.205.219/airwallex/admin.html` →「周报审核」 |
| 接口全文档 | 仓库 `docs/周报上传接口.md` |

## 步骤

### 1. 修资产路径（最容易踩的坑）

上传的周报被服务在 `/airwallex/data/weekly/<period>.html`。页面里的**相对**路径会解析到 `…/data/weekly/assets/` → **404、样式全丢**。

做一份**上传专用副本**，把样式引用改成**绝对路径**（或把 CSS 内联成自包含单文件）：

```
<!-- ❌ 仓库里是相对路径（本地预览用，别上传这份） -->
<link rel="stylesheet" href="assets/style.css">
<!-- ✅ 上传副本改成绝对路径 -->
<link rel="stylesheet" href="/airwallex/assets/style.css">
```

> 保留仓库原文件的相对路径（方便本地 `python3 -m http.server` 预览），只改副本。

### 2. 定 period

`period` = 该周报对应那一周的**周一**日期，格式 `YYYY-MM-DD`，它同时是期数标识和发布日。例：第 26 周（6/22–6/28）→ `2026-06-22`。
先查现有 slots 避免覆盖：`curl "http://13.214.205.219/api/slots?type=weekly"`。

### 3. 拿 Token

SSH 进服务器读：
```bash
ssh -i "~/Downloads/PEM密钥/airwallex.pem" ec2-user@13.214.205.219 \
  'grep API_TOKEN ~/airwallex/engine/.env'
```
（SSH 连不上就找 Shawn 要。token 别落进 git / 文档 / 聊天记录之外的地方。）

### 4. 上传（→ 草稿）

```bash
curl -X POST "http://13.214.205.219/api/weekly" \
  -H "X-Api-Token: $API_TOKEN" \
  -F "period=2026-06-22" \
  -F "title=第26周·费率战来了" \
  -F "file=@weekly_2026-06-22.html"
# → {"ok":true,"period":"2026-06-22","status":"draft","url":"/airwallex/data/weekly/2026-06-22.html"}
```

### 5. 验证（必须，发布前自检）

```bash
BASE=http://13.214.205.219
curl -s -o /dev/null -w "draft %{http_code}\n" "$BASE/airwallex/data/weekly/2026-06-22.html"   # 期望 200
curl -s "$BASE/airwallex/data/weekly/2026-06-22.html" | grep -c "/airwallex/assets/style.css"   # 期望 1（绝对路径）
curl -s -o /dev/null -w "css %{http_code}\n" "$BASE/airwallex/assets/style.css"                  # 期望 200
curl -s "$BASE/api/slots?type=weekly" | grep '"2026-06-22"'                                       # 期望 state=draft
```
（可再用浏览器打开草稿 URL，确认 5 页翻页/样式无崩。）

### 6. STOP — 人审后发布

把草稿 URL 给到 RevE / Shawn，请其在后台「周报审核」预览后点「通过发布」。
**不要替人点发布**，除非用户明确说"直接发布"。真要发布：`POST /api/publish`，form `period=… & type=weekly`（无需 token）。

## Common Mistakes

| 现象 | 原因 / 修复 |
|---|---|
| 草稿打开后样式全丢 | 相对路径 → 404。改绝对 `/airwallex/assets/style.css` 或内联（步骤 1）。 |
| 草稿在 slots 里不显示 | `period` 不是 6–7 月的周一；用合法 period（见 `/api/slots`）。 |
| 覆盖了别人的草稿 | 同 `period` 重传 = 覆盖并重置为 draft。先查 slots。 |
| 上传了就当上线了 | 那只是草稿，需人审点「通过发布」才真正 published。 |
| 把 demo 的 data.js 当真实数据 | 周报选题取自 data.js，新闻真伪/数字对外前须复核。 |

## Notes

- 这台服务器 SSH/HTTP 都通（与老的 `47.129.174.5` 不同，那台有 IP 白名单）。
- 媒体（AI 播客/视频）目前为占位，非真实。
