#!/bin/bash
# =============================================================
# Fusion Gate v4 — UserPromptSubmit Hook
# =============================================================
# プロンプト内のシークレット検出
# - API キー、トークン、パスワードのパターンをスキャン
# - 検出時: decision "block" で処理を阻止
# =============================================================

set -euo pipefail

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

if [ -z "$PROMPT" ]; then
  exit 0
fi

# --- シークレットパターン定義 ---
# 順に: OpenAI, Anthropic, AWS, GitHub, Slack, Generic password, Bearer token, Private key
SECRET_PATTERNS=(
  'sk-[a-zA-Z0-9]{20,}'
  'sk-ant-[a-zA-Z0-9-]{20,}'
  'AKIA[0-9A-Z]{16}'
  'ghp_[a-zA-Z0-9]{36}'
  'gho_[a-zA-Z0-9]{36}'
  'xoxb-[0-9]{10,}'
  'xoxp-[0-9]{10,}'
  'password[[:space:]]*[:=]'
  'Bearer[[:space:]]+[a-zA-Z0-9_./-]{20,}'
  'BEGIN[[:space:]]+(RSA[[:space:]]+)?PRIVATE[[:space:]]+KEY'
)

FOUND=""
for pattern in "${SECRET_PATTERNS[@]}"; do
  if echo "$PROMPT" | grep -qEi "$pattern"; then
    MATCH=$(echo "$PROMPT" | grep -oEi "$pattern" | head -1)
    # マスク: 先頭4文字 + ****
    MASKED="${MATCH:0:4}****"
    FOUND="${FOUND}  - パターン一致: ${MASKED}\n"
  fi
done

if [ -n "$FOUND" ]; then
  REASON="🛡️ Fusion Gate: プロンプトにシークレットが含まれています。
$(echo -e "$FOUND")
プロンプトからシークレットを除去してください。"

  jq -n \
    --arg reason "$REASON" \
    '{
      decision: "block",
      reason: $reason
    }'
  exit 0
fi

# シークレットなし — 通過
exit 0
