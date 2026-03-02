# Antigravity

Fusion Gate v4 — Claude Code Hooks による AI 品質ゲートシステム。

## 概要

Claude Code のフックシステムを使って、AI エージェントの行動を自動検問する。

```
SessionStart  ──→ 環境チェック + ルール注入
UserPrompt    ──→ シークレット検出
PreToolUse    ──→ 危険コマンド遮断 / diff_guard
PostToolUse   ──→ Ruff lint 自動実行 (async)
Stop          ──→ CBF 品質ゲート最終判定
```

## フック一覧

| # | イベント | スクリプト | 機能 |
|---|---------|----------|------|
| ① | SessionStart | `session-init.sh` | uv/ruff/jq チェック、スタックルール注入 |
| ② | UserPromptSubmit | `prompt-guard.sh` | API キー/トークン/パスワード検出→ブロック |
| ③ | PreToolUse(Bash) | `bash-guard.sh` | rm -rf, curl\|sh, dd 等 denylist 遮断 |
| ④ | PreToolUse(Write\|Edit) | `diff-guard.sh` | .env/id_rsa 保護 + コード内シークレット検出 |
| ⑤ | PostToolUse(Write\|Edit) | `post-write-lint.sh` | Ruff 自動実行 (非同期) |
| ⑥ | Stop | `quality-gate.sh` | 変更ファイル lint + シークレットスキャン |

## 使い方

`.claude/` ディレクトリをプロジェクトルートにコピーして Claude Code CLI を起動するだけ。

## ライセンス

MIT
