#!/usr/bin/env bash
# 一键推送到 GitHub
# 用法：./push.sh <你的PAT>
#
# 网络说明（本机实测）：
#   · 直连 github.com 可用；走本地代理反而 502
#   · 因此这里显式清空代理变量
set -e

PAT="${1:?请传入 Personal Access Token：./push.sh ghp_xxxxx}"

REPO="apso-particle-morph"
REMOTE="https://github.com/funiyayue-art/$REPO.git"
API="https://api.github.com/user/repos"

cd "$(dirname "$0")"

echo "=== 1/4  检查仓库是否已存在于 GitHub ==="
EXISTS=$(curl -s --noproxy '*' -H "Authorization: token $PAT" "$API/$REPO" | grep -c '"full_name"')
if [ "$EXISTS" = "1" ]; then
  echo "  仓库已存在，跳过创建"
else
  echo "  创建新仓库 $REPO ..."
  curl -s --noproxy '*' -X POST -H "Authorization: token $PAT" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"$REPO\",
      \"description\": \"文字粒子形变引擎：整行文字粒子溶解→空场→重组。含 4 个逐像素验证工具与 Agent 方法论文档。\",
      \"private\": false,
      \"auto_init\": false
    }" "$API" | head -c 200
  echo ""
fi

echo "=== 2/4  配置远端 ==="
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git branch -M main

echo "=== 3/4  提交 ==="
git add -A
git -c user.name="funiyayue-art" \
    -c user.email="funiyayue-art@users.noreply.github.com" \
    commit -q -m "完善 README：加入验证器实测结果与徽章" || echo "  （无新改动，跳过提交）"

echo "=== 4/4  推送 ==="
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  git push -u origin main

echo ""
echo "✓ 完成"
echo "  https://github.com/funiyayue-art/$REPO"