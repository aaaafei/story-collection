#!/usr/bin/env bash
# 把本仓库当前提交同步到 Gitee 镜像：
#   https://gitee.com/aaaafei/story-collection.git
#
# 令牌（不要写进 Git）：按优先级读取
#   1. 环境变量 GITEE_TOKEN（Cursor 网页 Secrets / GitHub Actions secrets）
#   2. 环境变量 GITEE_PRIVATE_TOKEN（Gitee 私人令牌的别名）
#   3. tools/.env 或仓库根目录 .env 里的同上变量
#
# 用法：
#   bash tools/sync_to_gitee.sh                 # 推送当前分支
#   bash tools/sync_to_gitee.sh --ref refs/heads/master
#   bash tools/sync_to_gitee.sh --install-hook  # 提交后自动同步
#   GITEE_SYNC_SKIP=1                           # 临时跳过

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUIET_IF_UNCONFIGURED=0
INSTALL_HOOK=0
REF=""

usage() {
  sed -n '2,14p' "$0"
}

load_dotenv() {
  local file="$1"
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      ''|'#'*) continue ;;
    esac
    local key="${line%%=*}"
    local value="${line#*=}"
    case "$key" in
      GITEE_TOKEN|GITEE_PRIVATE_TOKEN|GITEE_USERNAME|GITEE_REMOTE_URL) ;;
      *) continue ;;
    esac
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    if [ -z "${!key:-}" ]; then
      export "$key=$value"
    fi
  done < "$file"
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --install-hook)
      INSTALL_HOOK=1
      shift
      ;;
    --quiet-if-unconfigured)
      QUIET_IF_UNCONFIGURED=1
      shift
      ;;
    --ref)
      REF="${2:-}"
      if [ -z "$REF" ]; then
        echo "sync_to_gitee: --ref 需要一个 git ref，例如 refs/heads/master" >&2
        exit 2
      fi
      shift 2
      ;;
    --ref=*)
      REF="${1#--ref=}"
      shift
      ;;
    *)
      echo "sync_to_gitee: 未知参数 $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$INSTALL_HOOK" -eq 1 ]; then
  cd "$ROOT"
  git config core.hooksPath .githooks
  chmod +x "$ROOT/.githooks/post-commit" "$ROOT/tools/sync_to_gitee.sh"
  echo "已启用 .githooks（git config core.hooksPath .githooks）。之后每次 git commit 会尝试同步到 Gitee。"
  exit 0
fi

load_dotenv "$ROOT/tools/.env"
load_dotenv "$ROOT/.env"

GITEE_HTTPS_URL="${GITEE_REMOTE_URL:-https://gitee.com/aaaafei/story-collection.git}"
GITEE_USER="${GITEE_USERNAME:-oauth2}"
TOKEN="${GITEE_TOKEN:-${GITEE_PRIVATE_TOKEN:-}}"
if [ -z "$TOKEN" ]; then
  if [ "$QUIET_IF_UNCONFIGURED" -eq 1 ]; then
    exit 0
  fi
  echo "sync_to_gitee: 未找到 GITEE_TOKEN。" >&2
  echo "请使用网页上已配置的 Gitee 仓库令牌，任选其一：" >&2
  echo "  - Cursor Cloud Agents → Secrets → GITEE_TOKEN" >&2
  echo "  - GitHub 仓库 Settings → Secrets and variables → Actions → GITEE_TOKEN" >&2
  echo "  - 本地 tools/.env 写入 GITEE_TOKEN=（不要提交）" >&2
  exit 1
fi

cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "sync_to_gitee: 当前目录不是 git 仓库" >&2
  exit 1
fi

if [ -z "$REF" ]; then
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$branch" = "HEAD" ]; then
    echo "sync_to_gitee: 当前是游离 HEAD，请用 --ref 指定目标分支，例如 --ref refs/heads/master" >&2
    exit 1
  fi
  REF="refs/heads/${branch}"
fi

askpass="$(mktemp)"
cleanup() {
  rm -f "$askpass"
}
trap cleanup EXIT
cat > "$askpass" <<ASKPASS
#!/bin/sh
case "\$1" in
  *[Uu]sername*) echo "${GITEE_USER}" ;;
  *) echo "\$GITEE_TOKEN" ;;
esac
ASKPASS
chmod 700 "$askpass"

# 把私人令牌只交给 askpass，避免出现在 git 远程 URL / 日志里。
export GITEE_TOKEN="$TOKEN"
export GIT_ASKPASS="$askpass"
export GIT_TERMINAL_PROMPT=0
unset TOKEN

case "$REF" in
  refs/*) DEST="$REF" ;;
  *) DEST="refs/heads/$REF" ;;
esac

# 用户名写在 URL 里，密码由 GIT_ASKPASS 提供，避免令牌出现在远程 URL 中。
# 关闭 credential.helper，避免误用 GitHub 的凭据去推 Gitee。
PUSH_URL="https://${GITEE_USER}@${GITEE_HTTPS_URL#https://}"
echo "sync_to_gitee: 推送 HEAD:${DEST} → ${GITEE_HTTPS_URL}"
if [ "${DEST#refs/tags/}" != "$DEST" ]; then
  git -c credential.helper= push --follow-tags "$PUSH_URL" "$DEST"
else
  git -c credential.helper= push --follow-tags "$PUSH_URL" "HEAD:${DEST}"
fi
echo "sync_to_gitee: 完成"
