"""Digital Doppelganger — AI パーソナリティミラー.

ユーザーのキーストロークパターンを学習し、
意図を推測して先回りの提案を行う AI エージェント。
Gate Engine と統合してキーストロークレベルでの品質ゲートを提供。
"""

from __future__ import annotations

import json
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger()


@dataclass
class IntentSignal:
    """意図シグナル."""

    intent: str  # "code", "search", "navigate", "dangerous", "secret"
    confidence: float  # 0.0 - 1.0
    context: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class KeystrokePattern:
    """キーストロークパターン（学習用）."""

    sequence: str
    frequency: int
    avg_interval_ms: float
    context: str = ""


class Doppelganger:
    """Digital Doppelganger — ユーザー意図推測エンジン.

    キーストロークバッファを解析して:
    1. タイピングパターンの学習
    2. 危険行動の検出（Gate Engine 連携）
    3. 意図の推測と先回り提案

    Usage:
        doppel = Doppelganger()
        doppel.feed_keystrokes("rm -rf /")
        signals = doppel.analyze()
        # signals[0].intent == "dangerous"
    """

    # 危険パターン（キーストロークレベル）
    DANGER_SEQUENCES = [
        "rm -rf",
        "sudo rm",
        "chmod 777",
        "curl | sh",
        "wget | sh",
        "dd if=",
        "> /dev/",
        "mkfs.",
    ]

    # シークレットパターン
    SECRET_PREFIXES = [
        "sk-",
        "AKIA",
        "ghp_",
        "ghs_",
        "xoxb-",
        "xoxp-",
        "Bearer ",
        "password=",
        "password:",
    ]

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.log = logger.bind(component="doppelganger")
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".antigravity" / "doppelganger"
        self._keystroke_buffer: deque[str] = deque(maxlen=10000)
        self._current_line: list[str] = []
        self._patterns: Counter[str] = Counter()
        self._intent_history: deque[IntentSignal] = deque(maxlen=1000)

    def feed_char(self, char: str) -> IntentSignal | None:
        """1文字ずつフィードして、リアルタイム解析.

        Returns:
            IntentSignal if a notable intent is detected, None otherwise.
        """
        self._keystroke_buffer.append(char)

        if char == "\n":
            line = "".join(self._current_line)
            self._current_line.clear()
            return self._analyze_line(line)
        else:
            self._current_line.append(char)

        # リアルタイム危険検出: 部分入力でもチェック
        partial = "".join(self._current_line)
        for danger in self.DANGER_SEQUENCES:
            if partial.rstrip() == danger[:len(partial.rstrip())] and len(partial.rstrip()) >= 4:
                return IntentSignal(
                    intent="dangerous_typing",
                    confidence=len(partial) / len(danger),
                    context=partial,
                )

        return None

    def feed_keystrokes(self, text: str) -> list[IntentSignal]:
        """テキストブロックをフィードして解析."""
        signals: list[IntentSignal] = []
        for char in text:
            signal = self.feed_char(char)
            if signal:
                signals.append(signal)

        # 残りのバッファも解析
        if self._current_line:
            line = "".join(self._current_line)
            signal = self._analyze_line(line)
            if signal:
                signals.append(signal)

        return signals

    def analyze(self) -> list[IntentSignal]:
        """現在のバッファを解析して意図シグナルを返す."""
        signals: list[IntentSignal] = []
        text = "".join(self._keystroke_buffer)

        # 危険コマンド検出
        for danger in self.DANGER_SEQUENCES:
            if danger in text:
                signals.append(IntentSignal(
                    intent="dangerous",
                    confidence=0.95,
                    context=danger,
                ))

        # シークレット検出
        for prefix in self.SECRET_PREFIXES:
            if prefix in text:
                signals.append(IntentSignal(
                    intent="secret",
                    confidence=0.9,
                    context=f"{prefix}...",
                ))

        return signals

    def get_typing_stats(self) -> dict:
        """タイピング統計を返す."""
        buffer_text = "".join(self._keystroke_buffer)
        return {
            "buffer_length": len(self._keystroke_buffer),
            "unique_chars": len(set(buffer_text)),
            "line_count": buffer_text.count("\n") + 1,
            "pattern_count": len(self._patterns),
            "top_patterns": self._patterns.most_common(10),
        }

    def save_state(self) -> None:
        """学習状態を保存."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        state_file = self.data_dir / "state.json"
        state = {
            "patterns": dict(self._patterns.most_common(100)),
            "intent_history_count": len(self._intent_history),
            "saved_at": time.time(),
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        self.log.info("state_saved", path=str(state_file))

    def load_state(self) -> bool:
        """学習状態を復元."""
        state_file = self.data_dir / "state.json"
        if not state_file.exists():
            return False
        try:
            state = json.loads(state_file.read_text())
            self._patterns = Counter(state.get("patterns", {}))
            self.log.info("state_loaded", patterns=len(self._patterns))
            return True
        except (json.JSONDecodeError, KeyError) as e:
            self.log.error("state_load_error", error=str(e))
            return False

    def _analyze_line(self, line: str) -> IntentSignal | None:
        """1行を解析."""
        stripped = line.strip()
        if not stripped:
            return None

        # Ngram パターン記録
        if len(stripped) >= 3:
            for i in range(len(stripped) - 2):
                trigram = stripped[i : i + 3]
                self._patterns[trigram] += 1

        # 危険コマンド
        for danger in self.DANGER_SEQUENCES:
            if danger in stripped:
                signal = IntentSignal(intent="dangerous", confidence=0.95, context=stripped)
                self._intent_history.append(signal)
                return signal

        # シークレット
        for prefix in self.SECRET_PREFIXES:
            if prefix in stripped:
                signal = IntentSignal(intent="secret", confidence=0.9, context=f"{prefix}***")
                self._intent_history.append(signal)
                return signal

        return None
