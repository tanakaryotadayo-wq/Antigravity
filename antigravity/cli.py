"""Antigravity CLI — Universal AI Quality Gate.

Usage:
    antigravity claude "Fix the bug"
    antigravity gemini "Add tests"
    antigravity codex "Refactor API"
    antigravity gate check-prompt "my prompt text"
    antigravity gate check-command "rm -rf /"
"""

from __future__ import annotations

import argparse
import json
import sys

import structlog

from antigravity.gate_engine import Decision, GateEngine

logger = structlog.get_logger()


def cmd_gate(args: argparse.Namespace) -> int:
    """Gate Engine サブコマンド — 直接ゲートチェックを実行."""
    engine = GateEngine(project_dir=args.project_dir)

    if args.gate_action == "check-prompt":
        result = engine.check_prompt(args.text)
    elif args.gate_action == "check-command":
        result = engine.check_command(args.text)
    elif args.gate_action == "check-write":
        content = ""
        if args.content:
            content = args.content
        result = engine.check_write(args.text, content)
    elif args.gate_action == "quality-gate":
        result = engine.quality_gate()
    else:
        print(f"Unknown gate action: {args.gate_action}", file=sys.stderr)
        return 1

    # JSON 出力
    output = {
        "decision": result.decision.value,
        "reason": result.reason,
        "details": result.details,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.decision == Decision.PASS else 1


def cmd_wrap(args: argparse.Namespace) -> int:
    """AI CLI ラッパー — ゲート付きで CLI を実行."""
    engine = GateEngine(project_dir=args.project_dir)

    # プロンプト検問
    prompt = " ".join(args.prompt)
    check = engine.check_prompt(prompt)
    if check.decision == Decision.BLOCK:
        print(f"\n{check.reason}", file=sys.stderr)
        for detail in check.details:
            print(f"  {detail}", file=sys.stderr)
        return 1

    # CLI 実行
    cli = args.cli
    try:
        if cli == "claude":
            from antigravity.wrappers.claude import run
        elif cli == "gemini":
            from antigravity.wrappers.gemini import run
        elif cli == "codex":
            from antigravity.wrappers.codex import run
        else:
            print(f"Unknown CLI: {cli}. Supported: claude, gemini, codex", file=sys.stderr)
            return 1

        return run(prompt, engine=engine, project_dir=args.project_dir)
    except ImportError:
        print(f"Wrapper for '{cli}' is not installed.", file=sys.stderr)
        return 1


def main() -> None:
    """Antigravity CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        prog="antigravity",
        description="Universal AI Quality Gate — Fusion Gate + Hooks + Keyboard + Commander",
    )
    parser.add_argument("--project-dir", "-p", default=".", help="プロジェクトディレクトリ")

    subparsers = parser.add_subparsers(dest="command")

    # gate サブコマンド
    gate_parser = subparsers.add_parser("gate", help="Gate Engine を直接実行")
    gate_parser.add_argument(
        "gate_action",
        choices=["check-prompt", "check-command", "check-write", "quality-gate"],
    )
    gate_parser.add_argument("text", nargs="?", default="")
    gate_parser.add_argument("--content", default="")

    # AI CLI ラッパー (claude, gemini, codex)
    for cli_name in ("claude", "gemini", "codex"):
        cli_parser = subparsers.add_parser(cli_name, help=f"{cli_name} をゲート付きで実行")
        cli_parser.add_argument("prompt", nargs="+", help="AI に送るプロンプト")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)
    elif args.command == "gate":
        sys.exit(cmd_gate(args))
    elif args.command in ("claude", "gemini", "codex"):
        args.cli = args.command
        sys.exit(cmd_wrap(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
