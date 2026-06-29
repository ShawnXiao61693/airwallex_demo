#!/bin/bash
# 一键跑整条链路：采集 → 提炼 → 制作。先 cp .env.example .env 并填 key。
cd "$(dirname "$0")"
set -a; [ -f .env ] && . ./.env; set +a
if [ -z "$LLM_API_KEY" ]; then
  echo "⚠️  未设置 LLM_API_KEY —— 请 cp .env.example .env 并填入 key"; exit 1
fi
.venv/bin/python run.py
# 导出库到后台「情报库」可读的位置 + 同步日报 JSON
DATA=/usr/share/nginx/html/airwallex/data
.venv/bin/python export.py "$DATA/news.json" 2>/dev/null || .venv/bin/python export.py news.json
cp -f daily_*.json "$DATA/" 2>/dev/null || true
