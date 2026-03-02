# ⚡ Antigravity — StellarWorkspace

> Fusion Gate + Neural Keyboard + Universal Hooks + Desktop Commander を統合した
> AI CLI 品質ゲート & OS レベル制御システム

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  StellarWorkspace                   │
├─────────────────────────────────────────────────────┤
│  Input Layer    │ Neural Keyboard                   │
│                 │  ├ quartz_listener (macOS events)  │
│                 │  ├ ghost_hand (stealth injection)  │
│                 │  └ doppelganger (intent mirror)    │
├─────────────────────────────────────────────────────┤
│  Hook Layer     │ Universal Hooks                   │
│                 │  ├ antigravity claude <prompt>     │
│                 │  ├ antigravity gemini <prompt>     │
│                 │  └ antigravity codex  <prompt>     │
├─────────────────────────────────────────────────────┤
│  Gate Layer     │ Fusion Gate Engine                │
│                 │  ├ check_prompt  (secret scan)     │
│                 │  ├ check_command (denylist)         │
│                 │  ├ check_write   (path protect)    │
│                 │  ├ check_lint    (ruff)             │
│                 │  └ quality_gate  (final check)     │
├─────────────────────────────────────────────────────┤
│  Exec Layer     │ Desktop Commander                 │
│                 │  ├ terminal  (safe command exec)    │
│                 │  ├ filesystem (read/write/diff)     │
│                 │  └ process   (list/kill/port)       │
└─────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install
uv pip install -e ".[dev]"

# Run quality gate checks
antigravity gate check-prompt "my api key is sk-..."
antigravity gate check-command "rm -rf /"
antigravity gate quality-gate

# Wrap AI CLIs with quality gates
antigravity claude "Fix the authentication bug"
antigravity gemini "Add unit tests for the API"
antigravity codex  "Refactor the database layer"
```

## Python API

```python
from antigravity.gate_engine import GateEngine, Decision
from antigravity.commander.terminal import Terminal
from antigravity.commander.filesystem import FileSystem
from antigravity.keyboard.doppelganger import Doppelganger

# Gate Engine
engine = GateEngine()
result = engine.check_prompt("my key: sk-abc123...")
assert result.decision == Decision.BLOCK

# Terminal (Gate-integrated)
term = Terminal()
result = term.run("echo hello")   # ✅ PASS
result = term.run("rm -rf /")     # 🚫 BLOCKED

# FileSystem (Gate-integrated)
fs = FileSystem()
fs.write("/project/app.py", code)     # ✅ PASS
fs.write("/project/.env", secrets)     # 🚫 BLOCKED

# Doppelganger (Keystroke Intent)
doppel = Doppelganger()
signals = doppel.feed_keystrokes("AKIA...")
# → IntentSignal(intent="secret", confidence=0.9)
```

## Tests

```bash
uv run pytest tests/ -v
# 30 passed in 1.48s
```

## Stack

- **Python 3.12+** / **uv** / **structlog**
- **macOS Quartz** (optional: Neural Keyboard)
- **Ruff** (lint gate)

## License

MIT
