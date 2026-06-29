#!/bin/bash
# 一键跑整条链路：采集 → 提炼 → 制作。先 cp .env.example .env 并填 key。
cd "$(dirname "$0")"
set -a; [ -f .env ] && . ./.env; set +a
if [ -z "$LLM_API_KEY" ]; then
  echo "⚠️  未设置 LLM_API_KEY —— 请 cp .env.example .env 并填入 key"; exit 1
fi
.venv/bin/python run.py
