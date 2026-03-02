"""Antigravity Gate Engine — CLI 非依存の品質ゲートエンジン.

Claude Code Hooks のロジックを Python に移植し、
どの AI CLI (Claude, Gemini, Codex, Copilot) でも同じ品質ゲートを適用する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import structlog

logger = structlog.get_logger()


class Decision(Enum):
    """ゲート判定結果."""

    PASS = "pass"
    BLOCK = "block"
    WARN = "warn"


@dataclass
class GateResult:
    """ゲート判定の結果."""

    decision: Decision
    reason: str = ""
    details: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# シークレットパターン
# ──────────────────────────────────────────────
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("Anthropic API Key", re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub PAT", re.compile(r"gh[ps]_[a-zA-Z0-9]{36}")),
    ("Slack Token", re.compile(r"xox[bp]-[0-9]{10,}")),
    ("Bearer Token", re.compile(r"Bearer\s+[a-zA-Z0-9_./-]{20,}")),
    ("Private Key", re.compile(r"BEGIN\s+(RSA\s+)?PRIVATE\s+KEY")),
    ("Password Assignment", re.compile(r"password\s*[:=]", re.IGNORECASE)),
]

# ──────────────────────────────────────────────
# 危険コマンド denylist
# ──────────────────────────────────────────────
COMMAND_DENYLIST: list[tuple[str, re.Pattern[str]]] = [
    ("rm -rf /", re.compile(r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*/")),
    ("rm -r /", re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/")),
    ("chmod 777", re.compile(r"chmod\s+(-R\s+)?777")),
    ("curl | sh", re.compile(r"curl\s+.*\|\s*(ba)?sh")),
    ("wget | sh", re.compile(r"wget\s+.*\|\s*(ba)?sh")),
    ("curl | python", re.compile(r"curl\s+.*\|\s*python")),
    ("dd if=", re.compile(r"dd\s+if=")),
    ("mkfs", re.compile(r"mkfs\.")),
    ("fork bomb", re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;")),
    ("unset PATH", re.compile(r"(export\s+PATH\s*=\s*$|unset\s+PATH)")),
    ("netcat listener", re.compile(r"n?cat\s+-[a-zA-Z]*l")),
    ("subprocess injection", re.compile(r"python.*-c.*(__import__.*subprocess|os\.system)")),
]

# ──────────────────────────────────────────────
# 保護ファイルパス
# ──────────────────────────────────────────────
PROTECTED_PATHS: list[str] = [
    ".env", ".env.local", ".env.production", ".env.staging",
    "id_rsa", "id_ed25519", "id_ecdsa",
    ".ssh/config", ".git/config", ".gitconfig", ".netrc", ".npmrc",
    "credentials", "secrets.json", "service-account.json",
    "token.json",
]


class GateEngine:
    """CLI 非依存の品質ゲートエンジン."""

    def __init__(self, project_dir: str | Path | None = None) -> None:
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.log = logger.bind(component="gate_engine")

    def check_prompt(self, prompt: str) -> GateResult:
        """プロンプト内のシークレット検出."""
        found: list[str] = []
        for name, pattern in SECRET_PATTERNS:
            match = pattern.search(prompt)
            if match:
                masked = match.group()[:4] + "****"
                found.append(f"{name}: {masked}")
        if found:
            self.log.warning("secret_in_prompt", secrets=found)
            return GateResult(
                decision=Decision.BLOCK,
                reason="シークレットが含まれています",
                details=found,
            )
        return GateResult(decision=Decision.PASS)

    def check_command(self, command: str) -> GateResult:
        """危険コマンドの遮断."""
        for name, pattern in COMMAND_DENYLIST:
            if pattern.search(command):
                self.log.warning("dangerous_command", command=command, pattern=name)
                return GateResult(
                    decision=Decision.BLOCK,
                    reason=f"危険コマンドをブロック: {name}",
                    details=[f"コマンド: {command}"],
                )
        return GateResult(decision=Decision.PASS)

    def check_write(self, file_path: str, content: str = "") -> GateResult:
        """ファイル書き込み前の検問."""
        path = Path(file_path)
        for protected in PROTECTED_PATHS:
            if protected in str(path) or path.name == protected:
                self.log.warning("protected_path", path=file_path)
                return GateResult(
                    decision=Decision.BLOCK,
                    reason=f"機密ファイルへの書き込みをブロック: {protected}",
                    details=[f"パス: {file_path}"],
                )
        if content:
            for name, pattern in SECRET_PATTERNS:
                match = pattern.search(content)
                if match:
                    masked = match.group()[:6] + "****"
                    self.log.warning("secret_in_code", path=file_path, pattern=name)
                    return GateResult(
                        decision=Decision.BLOCK,
                        reason=f"コードにシークレットが含まれています: {name}",
                        details=[f"ファイル: {file_path}", f"検出: {masked}"],
                    )
        return GateResult(decision=Decision.PASS)

    def check_lint(self, file_path: str) -> GateResult:
        """Ruff lint 実行."""
        import subprocess

        path = Path(file_path)
        if path.suffix != ".py" or not path.exists():
            return GateResult(decision=Decision.PASS)
        try:
            result = subprocess.run(
                ["ruff", "check", "--select", "E,W,F", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                return GateResult(
                    decision=Decision.WARN,
                    reason=f"Ruff lint: {path.name} に {len(lines)} 件の問題",
                    details=lines[:20],
                )
        except FileNotFoundError:
            return GateResult(decision=Decision.WARN, reason="ruff が見つかりません")
        except subprocess.TimeoutExpired:
            return GateResult(decision=Decision.WARN, reason="ruff タイムアウト")
        return GateResult(decision=Decision.PASS, reason=f"{path.name} — クリーン")

    def quality_gate(self) -> GateResult:
        """最終品質ゲート."""
        import subprocess

        issues: list[str] = []
        git_dir = self.project_dir / ".git"
        if not git_dir.exists():
            return GateResult(decision=Decision.PASS, reason="git リポジトリなし — スキップ")
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
                capture_output=True, text=True, cwd=self.project_dir, timeout=10,
            )
            changed_py = [f for f in diff_result.stdout.strip().split("\n") if f.endswith(".py")]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            changed_py = []
        for py_file in changed_py:
            full_path = self.project_dir / py_file
            if full_path.exists():
                result = self.check_lint(str(full_path))
                if result.decision == Decision.WARN and result.details:
                    issues.extend(result.details[:5])
        try:
            diff_content = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, cwd=self.project_dir, timeout=10,
            )
            for name, pattern in SECRET_PATTERNS[:4]:
                if pattern.search(diff_content.stdout):
                    issues.append(f"diff に {name} が含まれている可能性")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        if issues:
            return GateResult(
                decision=Decision.BLOCK,
                reason=f"品質ゲート: {len(issues)} 件の問題を検出",
                details=issues,
            )
        return GateResult(decision=Decision.PASS, reason="品質ゲート通過")
