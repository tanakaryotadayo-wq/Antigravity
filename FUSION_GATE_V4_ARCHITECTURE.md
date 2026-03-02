# 🔮 Fusion Gate v4 — 自律 AI オーケストレーション構想

> 2026-03-02 会話メモ。Fusion Gate v3 (2025/11) から現在の MCP エコシステムまでの進化と、次世代アーキテクチャの設計。

---

## 📜 起源 (2025/10〜11)

### Ryota の直感的発見（AI 触って1ヶ月）

| 時期 | 発見 | 業界用語 | 現在の実装 |
|------|------|----------|------------|
| 10月 | メモリに概念登録→呼び出し | RAG / Semantic Memory | スキルシステム / Knowledge Items |
| 11月 | AI をサーバーに閉じ込める | AI Gateway / Proxy | Fusion Gate v3 → MCP Server |
| 11月 | 閉じ込めた AI 同士を会話させる | Multi-Agent Orchestration | DoD Block / Agent Coordination |

### Fusion Gate 誕生の動機

1. ChatGPT / Gemini がコンテキストをロールバックする → 原因不明
2. ハッキングされていると推測 → 外部からの干渉を遮断したい
3. **AI を Proxy に閉じ込めて外部接続を断つ** → Fusion Gate v3 を作成
4. RLHF データを自前で取りたい → 全会話を fusion.db に記録

実際の原因は「コンテキストウィンドウの限界」だったが、**「信頼できない系を Proxy で制御する」発想はセキュリティの正攻法**。

---

## 🏗️ Fusion Gate v3 (既存・2025/11)

```
GPT-4.1-mini ──┐
Gemini-2.5-flash ──┤──→ Fusion Gate (FastAPI) ──→ 統合レスポンス
GPT-4.1-nano ──┘         ├── SSE ストリーミング
                          ├── SQLite キャッシュ (0.5ms, 45倍高速)
                          ├── Rate Limit (20回/分)
                          └── 比較ダッシュボード
```

- 場所: `/Users/ryota/Desktop/fusion-gate-v3-deploy/`
- ドキュメント: `/Users/ryota/🔮 Fusion Gate v3 Enhanced.md`
- 技術: FastAPI + SQLite + OpenAI SDK + SSE
- コード量: 1,385行

---

## 🚀 Fusion Gate v4 構想

### コンセプト: AI の「口」と「手」を両方制御する

```
Fusion Gate = AI の「口」を制御（何を聞いて何が返るか）
MCP Server  = AI の「手」を制御（何ができるか）
```

AI の「脳」はクラウドサーバーで動く（制御不能）。だが **行動は全て制御下に置ける**。

### 2層サンドイッチ構造

```
外の世界（API: Anthropic / OpenAI / Google）
    ↑ HTTPS（思考用の通信のみ許可）
┌───┴──────────────────────────────┐
│  Fusion Gate（検問所）            │
│    ├── 許可: api.anthropic.com   │
│    ├── 許可: api.openai.com      │
│    ├── 許可: googleapis.com      │
│    ├── 拒否: それ以外全て        │
│    ├── 全通信を記録              │
│    └── キャッシュ + Rate Limit   │
│                                   │
│  MCP Server（手錠）               │
│    ├── shell_run_safe (denylist) │
│    ├── diff_guard (秘密検出)     │
│    ├── fs_read (traversal防止)   │
│    ├── lease_acquire (衝突防止)  │
│    └── 全操作を監査ログに記録    │
│                                   │
│  AI CLI たち（実働部隊）          │
└───────────────────────────────────┘
```

---

## 🐳 OrbStack 20 コンテナ構成

### リソース計算 (Mac Studio M3 Ultra 512GB)

```
1コンテナ ≈ 2-3GB (Alpine + Python + AI CLI)
20コンテナ × 3GB = 60GB
残り 452GB → MLX ローカルLLM 用に十分
```

### コンテナ配置

```
🧠 AI エージェント層 (5個)
├── agent-claude     ← Claude Code CLI
├── agent-gemini     ← Gemini CLI + Concept Jump
├── agent-codex      ← Codex CLI
├── agent-copilot    ← Copilot CLI
└── agent-local      ← MLX-LM (ローカル推論)

🔧 サービス層 (5個)
├── fusion-gate      ← AI Gateway + 比較エンジン
├── ryota-ops        ← MCP Server (37ツール)
├── postgres         ← メインDB (SQLModel)
├── inngest          ← ワークフローエンジン
└── gotenberg        ← PDF生成

🧪 実験・開発層 (5個)
├── sandbox-01       ← AI 実験砂場 A
├── sandbox-02       ← AI 実験砂場 B
├── test-runner      ← pytest 常駐
├── concept-jump     ← ジャンプ実験専用
└── bug-bounty       ← Frida + 解析ツール

🌐 外部接続層 (5個)
├── tailscale        ← VPN (OnePlus 15 接続)
├── ngrok            ← 外部公開トンネル
├── n8n              ← ワークフロー自動化
├── monitoring       ← ログ監視
└── backup           ← DB バックアップ・ECK
```

---

## 🤖 自律行動アーキテクチャ

### ファイルベースのタスクキュー

```
/shared/inbox/    ← タスク投入
/shared/outbox/   ← 結果出力
/shared/approved/ ← PCC 合格品
/shared/errors/   ← エラーログ
/shared/done/     ← 完了済み
```

### 自律ループ

```
/shared/inbox/ にタスクが置かれる
  ↓
Inngest が検知 → 難易度で振り分け
  ├── 高 → agent-claude
  ├── 中 → agent-gemini
  └── 低 → agent-mlx (ローカル、通信ゼロ)
  ↓
エージェントが処理 → /shared/outbox/ に結果
  ↓
Fusion Gate が PCC 採点
  ├── 合格 → /shared/approved/
  └── 不合格 → /shared/inbox/ に修正指示付きで戻す
  ↓
自己増殖: 結果が次のタスクを生む（テスト→バグ修正→再テスト）
```

### トリガー一覧

| トリガー | タイミング |
|----------|-----------|
| 人間が inbox にファイル置く | 手動 |
| Antigravity が inbox に書く | 人間が VS Code 開いてる時 |
| cron が定期タスクを投入 | 毎時 / 毎日 |
| Inngest がイベントで発火 | webhook / スケジュール |
| n8n が外部トリガーで投入 | Slack / GitHub / メール |
| 前タスクの結果から次タスク生成 | **自己増殖**（完全自律） |

### Antigravity の役割

```
人間がいる時: 俺が司令塔 → docker exec で各コンテナに指示
人間がいない時: cron / Inngest が自動実行 → 結果は fusion.db に記録
朝起きたら: 俺が fusion.db を読んで「昨夜の結果です」と報告
```

---

## 📱 Android (Termux) 拡張

OnePlus 15 (rooted, KernelSU) で MCP サーバーを建てれば、Android も同じアーキテクチャに統合可能。

```
OnePlus 15 (Termux)
├── MCP Server → am/pm/content/input/dumpsys 全部公開
├── root 権限 → Gemini App の AppFunctions 以上のことが可能
└── Tailscale → Mac Studio から接続
```

---

## 🔑 設計思想の進化線

```
2025/10  メモリで概念呼び出し → 今の Skills / KI
2025/11  Fusion Gate v3      → 今の MCP Gateway
2025/11  AI 同士の会話       → 今の Multi-Agent Orchestration
2026/01  ryota-ops MCP       → 37ツール公開
2026/02  PCC/CBF/ECK         → 品質制御・監査・不可逆記録
2026/03  Fusion Gate v4 構想 → OrbStack 20コンテナ + 自律ループ
```

**一貫した思想: 「サーバーにして、プロトコルを統一して、どこからでも叩けるようにする」**

---

## ⚡ 回線制約 (現状: 楽天モバイル)

- API テキスト通信: 問題なし（1リクエスト ~60KB）
- Docker イメージ pull: 初回のみ辛い → カフェ WiFi 推奨
- MLX モデル DL: 要事前準備
- **キャッシュ + ローカル推論で回線弱さを補える**
- NURO 10Gbps 開通後は完全に制約なし

---

## 🪝 Claude Code Hooks（実装済み）

### コンセプト: 外部 Proxy なしで「口」の検問を実現

Claude Code Hooks を使えば、**Claude Code 自体の中に Fusion Gate を埋め込める**。
外部 Gateway (v3) は API 通信の制御、Hooks は **エージェントの行動そのものの制御**。

```
┌─────────────────────────────────────────────┐
│ Claude Code Session                          │
│                                              │
│  SessionStart ──→ 環境チェック + ルール注入   │
│  UserPrompt   ──→ シークレット検出            │
│  PreToolUse   ──→ 危険コマンド遮断            │
│               ──→ diff_guard (機密ファイル)   │
│  PostToolUse  ──→ Ruff lint 自動実行 (async)  │
│  Stop         ──→ CBF 品質ゲート最終判定      │
│                                              │
└─────────────────────────────────────────────┘
```

### フック一覧

| # | イベント | スクリプト | 機能 |
|---|---------|----------|------|
| ① | SessionStart | `session-init.sh` | uv/ruff/jq チェック、スタックルール注入 |
| ② | UserPromptSubmit | `prompt-guard.sh` | API キー/トークン/パスワード検出→ブロック |
| ③ | PreToolUse(Bash) | `bash-guard.sh` | rm -rf, curl\|sh, dd 等 denylist 遮断 |
| ④ | PreToolUse(Write\|Edit) | `diff-guard.sh` | .env/id_rsa 保護 + コード内シークレット検出 |
| ⑤ | PostToolUse(Write\|Edit) | `post-write-lint.sh` | Ruff 自動実行 (非同期、結果をフィードバック) |
| ⑥ | Stop | `quality-gate.sh` | 変更ファイル lint + シークレットスキャン |

### ファイル構成

```
.claude/
├── settings.json           ← フック定義（6イベント）
└── hooks/
    ├── session-init.sh     ← ① 環境 + コンテキスト
    ├── prompt-guard.sh     ← ② プロンプト検問
    ├── bash-guard.sh       ← ③ コマンド遮断
    ├── diff-guard.sh       ← ④ ファイル検問
    ├── post-write-lint.sh  ← ⑤ Ruff lint (async)
    └── quality-gate.sh     ← ⑥ 最終品質ゲート
```
