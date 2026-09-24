#!/usr/bin/env bash
# 一键发布 trade-view：解析 → 校验 → 自检 → push 到 ktzwei/trade-view（GitHub Pages）
# 线上地址：https://ktzwei.github.io/trade-view/
set -euo pipefail
cd "$(dirname "$0")"
PY=python3

echo "[1/4] 拉取 Google Docs 并解析 sourceData"
$PY parser/parse_gdoc.py

echo "[2/4] 证据校验 + 统计口径 + 合并输出"
$PY parser/build.py

echo "[3/4] 自检"
$PY parser/selfcheck.py

echo "[4/4] 提交并推送"
git add -A
git -c user.name=ktzwei -c user.email=ktzwei@users.noreply.github.com \
    commit -m "publish $(date '+%Y-%m-%d %H:%M')" || echo "（无改动）"
TOK=$(cat /Users/maomao/.hermes/secrets/github_token | tr -d '\n')
git remote set-url origin "https://x-access-token:${TOK}@github.com/ktzwei/trade-view.git"
git push -u origin main
echo "[OK] https://ktzwei.github.io/trade-view/"
