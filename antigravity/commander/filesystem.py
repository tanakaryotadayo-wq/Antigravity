"""FileSystem Manager — ファイルシステム操作.

Gate Engine と統合された安全なファイル操作エンジン。
読み書き、検索、diff パッチ、ディレクトリ一覧を提供。
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from pathlib import Path

import structlog

from antigravity.gate_engine import Decision, GateEngine

logger = structlog.get_logger()


@dataclass
class FileInfo:
    """ファイル情報."""

    path: str
    name: str
    size: int
    is_dir: bool
    is_file: bool
    extension: str
    modified: float


class FileSystem:
    """安全なファイルシステム操作エンジン.

    Gate Engine で書き込みを検問してからファイル操作を実行。

    Usage:
        fs = FileSystem()
        content = fs.read("/path/to/file.py")
        fs.write("/path/to/file.py", "new content")
        files = fs.search("/project", "*.py")
    """

    def __init__(self, gate_engine: GateEngine | None = None) -> None:
        self.gate = gate_engine or GateEngine()
        self.log = logger.bind(component="filesystem")

    def read(self, path: str, max_bytes: int = 1024 * 1024) -> str | None:
        """ファイルを読み取り.

        Returns:
            ファイル内容、またはエラー時 None
        """
        p = Path(path)
        if not p.exists():
            self.log.warning("file_not_found", path=path)
            return None
        if not p.is_file():
            self.log.warning("not_a_file", path=path)
            return None
        try:
            content = p.read_bytes()[:max_bytes]
            return content.decode("utf-8", errors="replace")
        except PermissionError:
            self.log.error("permission_denied", path=path)
            return None

    def write(self, path: str, content: str, *, create_dirs: bool = True) -> bool:
        """ファイルに書き込み（Gate Engine チェック付き）.

        Returns:
            True if successful, False if blocked or error.
        """
        gate_result = self.gate.check_write(path, content)
        if gate_result.decision == Decision.BLOCK:
            self.log.warning("write_blocked", path=path, reason=gate_result.reason)
            return False

        p = Path(path)
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content, encoding="utf-8")
            self.log.info("file_written", path=path, size=len(content))
            return True
        except PermissionError:
            self.log.error("permission_denied", path=path)
            return False

    def append(self, path: str, content: str) -> bool:
        """ファイルに追記."""
        gate_result = self.gate.check_write(path, content)
        if gate_result.decision == Decision.BLOCK:
            return False
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return True
        except (PermissionError, FileNotFoundError):
            return False

    def delete(self, path: str) -> bool:
        """ファイルを削除."""
        p = Path(path)
        if not p.exists():
            return False
        # .env や id_rsa は削除もブロック
        gate_result = self.gate.check_write(path, "")
        if gate_result.decision == Decision.BLOCK:
            self.log.warning("delete_blocked", path=path)
            return False
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p)
            return True
        except PermissionError:
            return False

    def list_dir(self, path: str, recursive: bool = False) -> list[FileInfo]:
        """ディレクトリ一覧."""
        p = Path(path)
        if not p.is_dir():
            return []

        items: list[FileInfo] = []
        try:
            iterator = p.rglob("*") if recursive else p.iterdir()
            for item in iterator:
                try:
                    stat = item.stat()
                    items.append(FileInfo(
                        path=str(item),
                        name=item.name,
                        size=stat.st_size,
                        is_dir=item.is_dir(),
                        is_file=item.is_file(),
                        extension=item.suffix,
                        modified=stat.st_mtime,
                    ))
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            pass
        return items

    def search(
        self,
        directory: str,
        pattern: str = "*",
        *,
        max_results: int = 100,
        extensions: list[str] | None = None,
    ) -> list[str]:
        """ファイル検索（glob パターン）."""
        p = Path(directory)
        if not p.is_dir():
            return []

        results: list[str] = []
        for match in p.rglob(pattern):
            if extensions and match.suffix not in extensions:
                continue
            results.append(str(match))
            if len(results) >= max_results:
                break
        return results

    def diff(self, path: str, new_content: str) -> str:
        """現在のファイルと新しいコンテンツの diff."""
        p = Path(path)
        if p.exists():
            old_content = p.read_text(encoding="utf-8", errors="replace")
        else:
            old_content = ""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{p.name}",
            tofile=f"b/{p.name}",
        )
        return "".join(diff_lines)

    def patch(self, path: str, old_text: str, new_text: str) -> bool:
        """ファイル内のテキストを置換（surgical edit）."""
        content = self.read(path)
        if content is None:
            return False
        if old_text not in content:
            self.log.warning("patch_target_not_found", path=path)
            return False

        new_content = content.replace(old_text, new_text, 1)
        return self.write(path, new_content)
