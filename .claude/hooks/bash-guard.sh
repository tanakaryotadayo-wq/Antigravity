#!/bin/bash
# =============================================================
# Fusion Gate v4 — PreToolUse(Bash) Hook
# =============================================================
# 危険コマンド遮断
# - ryota-ops shell_run_safe と同じ denylist を共有
# - 検出時: permissionDecision "deny"
# =============================================================

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# --- Denylist（ryota-ops shell_run_safe 準拠）---
# 各パターンにコメントで理由を記載
DENY_PATTERNS=(
  # ファイルシステム破壊
  'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*/'    # rm -rf /
  'rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/'                     # rm -r /
  'chmod\s+777'                                         # 全権限開放
  'chmod\s+-R\s+777'                                    # 再帰的全権限開放
  'chown\s+-R\s+.*\s+/'                                 # ルート所有者変更

  # コード実行危険
  'curl\s+.*\|\s*(ba)?sh'                               # curl | sh
  'wget\s+.*\|\s*(ba)?sh'                               # wget | sh
  'curl\s+.*\|\s*python'                                # curl | python

  # ディスク破壊
  'dd\s+if='                                            # dd (ディスク上書き)
  'mkfs\.'                                              # ファイルシステム作成

  # フォーク爆弾
  ':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;'                      # :(){ :|:& };:

  # 環境破壊
  'export\s+PATH\s*=\s*$'                               # PATH 空にする
  'unset\s+PATH'                                        # PATH 削除

  # ネットワーク危険（外部送信）
  'nc\s+-[a-zA-Z]*l'                                    # netcat リスナー
  'ncat\s+-[a-zA-Z]*l'                                  # ncat リスナー

  # Python 危険パターン
  'python.*-c.*__import__.*subprocess'                  # subprocess インジェクション
  'python.*-c.*os\.system'                              # os.system インジェクション
)

BLOCKED=""
for pattern in "${DENY_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qEi "$pattern"; then
    BLOCKED="$pattern"
    break
  fi
done

if [ -n "$BLOCKED" ]; then
  jq -n \
    --arg cmd "$COMMAND" \
    --arg pattern "$BLOCKED" \
    '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("🔒 Fusion Gate: 危険コマンドをブロック\nコマンド: " + $cmd + "\n一致パターン: " + $pattern)
      }
    }'
  exit 0
fi

# 安全 — 通過
exit 0
