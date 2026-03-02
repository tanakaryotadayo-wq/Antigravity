#!/bin/bash
# =============================================================
# Fusion Gate v4 — Stop Hook
# =============================================================
# CBF 品質ゲート最終判定
# - 無限ループ防止 (stop_hook_active チェック)
# - .py ファイルが変更されていたら lint チェック
# - テスト未実行なら警告
# =============================================================

set -euo pipefail

INPUT=$(cat)

# --- 無限ループ防止 ---
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  # 既に Stop フックによる継続中 → 二重発火を防止
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
ISSUES=""
ISSUE_COUNT=0

# --- 1. git diff で変更された .py ファイルをチェック ---
CHANGED_PY_FILES=""
if command -v git &>/dev/null && [ -d "${PROJECT_DIR}/.git" ]; then
  CHANGED_PY_FILES=$(cd "$PROJECT_DIR" && git diff --name-only --diff-filter=ACMR HEAD 2>/dev/null | grep '\.py$' || true)

  if [ -n "$CHANGED_PY_FILES" ]; then
    # Ruff lint チェック
    LINT_ERRORS=""
    if command -v ruff &>/dev/null; then
      while IFS= read -r pyfile; do
        FULL_PATH="${PROJECT_DIR}/${pyfile}"
        if [ -f "$FULL_PATH" ]; then
          RESULT=$(ruff check --select E,W,F "$FULL_PATH" 2>&1) || true
          if [ -n "$RESULT" ]; then
            LINT_ERRORS="${LINT_ERRORS}${RESULT}\n"
          fi
        fi
      done <<< "$CHANGED_PY_FILES"
    fi

    if [ -n "$LINT_ERRORS" ]; then
      ISSUE_COUNT=$((ISSUE_COUNT + 1))
      TRIMMED=$(echo -e "$LINT_ERRORS" | head -15)
      ISSUES="${ISSUES}
❌ Ruff lint エラーが残っています:
${TRIMMED}"
    fi
  fi
fi

# --- 2. diff_guard: 変更内容のシークレットスキャン ---
if [ -n "$CHANGED_PY_FILES" ] && command -v git &>/dev/null; then
  DIFF_CONTENT=$(cd "$PROJECT_DIR" && git diff HEAD 2>/dev/null || true)
  if [ -n "$DIFF_CONTENT" ]; then
    # 主要シークレットパターン
    if echo "$DIFF_CONTENT" | grep -qEi '(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----)'; then
      ISSUE_COUNT=$((ISSUE_COUNT + 1))
      ISSUES="${ISSUES}
🔐 diff にシークレットが含まれている可能性があります。コミット前に確認してください。"
    fi
  fi
fi

# --- 判定 ---
if [ $ISSUE_COUNT -gt 0 ]; then
  REASON="🎯 Fusion Gate v4 品質ゲート: ${ISSUE_COUNT} 件の問題を検出
${ISSUES}

上記の問題を修正してから完了してください。"

  jq -n \
    --arg reason "$REASON" \
    '{
      decision: "block",
      reason: $reason
    }'
  exit 0
fi

# 全チェック通過
exit 0
