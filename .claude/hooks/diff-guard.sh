#!/bin/bash
# =============================================================
# Fusion Gate v4 — PreToolUse(Write|Edit) Hook
# =============================================================
# diff_guard: ファイル書き込み/編集前のセキュリティ検査
# - 機密ファイルパスへの書き込みをブロック
# - 書き込み内容内のシークレットを検出
# =============================================================

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# --- 機密ファイルパスの保護 ---
BLOCKED_PATHS=(
  '.env'
  '.env.local'
  '.env.production'
  '.env.staging'
  'id_rsa'
  'id_ed25519'
  'id_ecdsa'
  '.ssh/config'
  '.git/config'
  '.gitconfig'
  '.netrc'
  '.npmrc'
  'credentials'
  'secrets.json'
  'service-account.json'
  '.gcloud/'
  'token.json'
)

BASENAME=$(basename "$FILE_PATH")
for blocked in "${BLOCKED_PATHS[@]}"; do
  if [[ "$FILE_PATH" == *"$blocked"* ]] || [[ "$BASENAME" == "$blocked" ]]; then
    jq -n \
      --arg path "$FILE_PATH" \
      --arg blocked "$blocked" \
      '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: ("🔍 Fusion Gate diff_guard: 機密ファイルへの書き込みをブロック\nパス: " + $path + "\n一致: " + $blocked)
        }
      }'
    exit 0
  fi
done

# --- 書き込み内容のシークレット検出 ---
if [ "$TOOL_NAME" = "Write" ]; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
elif [ "$TOOL_NAME" = "Edit" ]; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
else
  CONTENT=""
fi

if [ -n "$CONTENT" ]; then
  SECRET_PATTERNS=(
    'sk-[a-zA-Z0-9]{20,}'
    'sk-ant-[a-zA-Z0-9-]{20,}'
    'AKIA[0-9A-Z]{16}'
    'ghp_[a-zA-Z0-9]{36}'
    'gho_[a-zA-Z0-9]{36}'
    'xoxb-[0-9]{10,}'
    'BEGIN[[:space:]]+(RSA[[:space:]]+)?PRIVATE[[:space:]]+KEY'
    'password[[:space:]]*[:=]'
  )

  for pattern in "${SECRET_PATTERNS[@]}"; do
    if echo "$CONTENT" | grep -qEi "$pattern"; then
      MATCH=$(echo "$CONTENT" | grep -oEi "$pattern" | head -1)
      MASKED="${MATCH:0:6}****"
      jq -n \
        --arg path "$FILE_PATH" \
        --arg masked "$MASKED" \
        '{
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: ("🔍 Fusion Gate diff_guard: シークレットがコードに含まれています\nファイル: " + $path + "\n検出: " + $masked + "\n環境変数またはシークレットマネージャーを使ってください")
          }
        }'
      exit 0
    fi
  done
fi

# 安全 — 通過
exit 0
