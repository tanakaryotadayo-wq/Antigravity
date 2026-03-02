"""Claude Code ラッパー.

Claude Code はネイティブ Hooks をサポートしているため、
.claude/settings.json が存在すればそのまま使う。
このラッパーは追加の Gate Engine チェックを実行してから claude を起動する。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

from antigravity.gate_engine import GateEngine

logger = structlog.get_logger()


def run(prompt: str, *, engine: GateEngine, project_dir: str = ".") -> int:
    """Claude Code をゲート付きで実行."""
    project = Path(project_dir).resolve()

    # Claude Code のネイティブ Hooks があるか確認
    hooks_settings = project / ".claude" / "settings.json"
    if hooks_settings.exists():
        logger.info("claude_native_hooks", path=str(hooks_settings))
    else:
        logger.warning("no_native_hooks", msg=".claude/settings.json が見つかりません")

    # claude コマンドの存在確認
    claude_cmd = _find_claude()
    if not claude_cmd:
        print("❌ claude コマンドが見つかりません", file=sys.stderr)
        print("   インストール: npm install -g @anthropic-ai/claude-code", file=sys.stderr)
        return 1

    # 実行
    logger.info("launching_claude", prompt=prompt[:50])
    env = os.environ.copy()
    env["FUSION_GATE_V4"] = "active"

    try:
        result = subprocess.run(
            [claude_cmd, "-p", prompt],
            cwd=project,
            env=env,
        )
        return result.returncode
    except KeyboardInterrupt:
        return 130


def _find_claude() -> str | None:
    """claude コマンドのパスを探す."""
    import shutil

    return shutil.which("claude")
