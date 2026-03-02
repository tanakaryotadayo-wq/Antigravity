#!/bin/bash
# =============================================================
# Fusion Gate v4 — PostToolUse(Write|Edit) Hook [ASYNC]
# =============================================================
# Ruff lint 自動実行
# - .py ファイルのみ対象
# - 非同期実行: Claude はブロックされない
# - 結果は systemMessage で次ターンにフィードバック
# =============================================================

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# .py ファイルのみ対象
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# ファイル存在チェック (Write が成功したか)
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# --- Ruff lint 実行 ---
LINT_RESULT=""
LINT_EXIT=0

if command -v ruff &>/dev/null; then
  LINT_RESULT=$(ruff check --select E,W,F "$FILE_PATH" 2>&1) || LINT_EXIT=$?
else
  # ruff がない場合、uv 経由で試行
  if command -v uv &>/dev/null; then
    LINT_RESULT=$(uv run ruff check --select E,W,F "$FILE_PATH" 2>&1) || LINT_EXIT=$?
  else
    jq -n '{systemMessage: "⚠️ ruff が見つかりません。uv tool install ruff を実行してください。"}'
    exit 0
  fi
fi

BASENAME=$(basename "$FILE_PATH")

if [ $LINT_EXIT -ne 0 ] && [ -n "$LINT_RESULT" ]; then
  # lint エラーあり — Claude にフィードバック
  # 出力が長すぎる場合は切り詰め
  TRIMMED=$(echo "$LINT_RESULT" | head -20)
  LINE_COUNT=$(echo "$LINT_RESULT" | wc -l | tr -d ' ')

  MSG="🧹 Ruff lint: ${BASENAME} に問題あり (${LINE_COUNT} 件)
${TRIMMED}"

  if [ "$LINE_COUNT" -gt 20 ]; then
    MSG="${MSG}
... (残り $((LINE_COUNT - 20)) 件省略)"
  fi

  jq -n --arg msg "$MSG" '{systemMessage: $msg}'
else
  # lint クリーン
  jq -n --arg file "$BASENAME" '{systemMessage: ("✅ Ruff lint: " + $file + " — クリーン")}'
fi

exit 0
