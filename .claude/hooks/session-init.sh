#!/bin/bash
# =============================================================
# Fusion Gate v4 — SessionStart Hook
# =============================================================
# 環境検証 + コンテキスト注入
# - uv の存在確認
# - Python バージョン確認
# - ryota-ops プロジェクトのサマリを additionalContext で注入
# =============================================================

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# --- 環境チェック ---
WARNINGS=""

# uv チェック
if ! command -v uv &>/dev/null; then
  WARNINGS="${WARNINGS}⚠️ uv が見つかりません。pip の代わりに uv を使ってください。\n"
fi

# ruff チェック
if ! command -v ruff &>/dev/null; then
  WARNINGS="${WARNINGS}⚠️ ruff が見つかりません。uv tool install ruff で入れてください。\n"
fi

# jq チェック（他のフックが依存）
if ! command -v jq &>/dev/null; then
  WARNINGS="${WARNINGS}⚠️ jq が見つかりません。brew install jq で入れてください。\n"
fi

# --- コンテキスト注入 ---
CONTEXT="🔮 Fusion Gate v4 Active — ryota DB プロジェクト
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 プロジェクト: ${PROJECT_DIR}
🛠️ スタック: Python (uv, Ruff, pytest, structlog) / FastAPI (Granian) / SQLModel
🔒 品質ゲート: CBF 5軸 / diff_guard / PCC パイプライン

⚡ ルール:
- パッケージ管理は uv を使え（pip 禁止）
- Linter/Formatter は Ruff を使え（black/pylint 禁止）
- ORM は SQLModel を使え
- テストは pytest + httpx
- ログは structlog
- サーバーは Granian（Uvicorn 禁止）
- コンテナは OrbStack（Docker Desktop 禁止）"

if [ -n "$WARNINGS" ]; then
  CONTEXT="${CONTEXT}

⚠️ 環境警告:
$(echo -e "$WARNINGS")"
fi

# --- CLAUDE_ENV_FILE に環境変数を保持 ---
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export FUSION_GATE_V4=active" >> "$CLAUDE_ENV_FILE"
  echo "export RYOTA_PROJECT_DIR=\"${PROJECT_DIR}\"" >> "$CLAUDE_ENV_FILE"
fi

# --- JSON 出力 ---
jq -n \
  --arg ctx "$CONTEXT" \
  '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $ctx
    }
  }'

exit 0
