"""Eidolon Layer — ペルソナ進化・自問自答.

StellarEngine の EidolonReflector パターンを移植:
思考プロセスを振り返り、ユーザーに問いかけ、
回答（Axiom）を吸収してシンボル定義を進化させる。
"""
from __future__ import annotations
import json, time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import structlog

logger = structlog.get_logger()

@dataclass
class Axiom:
    """吸収された知識単位."""
    query: str
    question: str
    answer: str
    keywords: list[str]
    timestamp: float = field(default_factory=time.time)

class EidolonReflector:
    """ペルソナ進化レイヤー.

    Usage:
        eidolon = EidolonReflector()
        question = eidolon.reflect({"query": "...", "trace": "..."})
        eidolon.absorb("query", question, "user answer")
    """
    def __init__(self, data_dir: str | Path | None = None):
        self.log = logger.bind(component="eidolon")
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".antigravity" / "eidolon"
        self.axioms: deque[Axiom] = deque(maxlen=1000)
        self._load_axioms()

    def reflect(self, context: dict) -> str:
        """思考プロセスを振り返って質問を生成."""
        query = context.get("query", "")
        trace = context.get("trace", "")
        blocked = context.get("blocked_steps", [])
        if blocked:
            return f"ブロックされたステップ {blocked} について、別のアプローチはありますか？"
        if "error" in str(trace).lower():
            return f"エラーが発生しました。目標 '{query}' を再定義しますか？"
        return f"'{query}' の結果を検証しますか？"

    def absorb(self, query: str, question: str, answer: str) -> Axiom:
        """ユーザー回答を Axiom として吸収."""
        words = [w for w in answer.lower().split() if len(w) > 2]
        axiom = Axiom(query=query, question=question, answer=answer, keywords=words[:5])
        self.axioms.append(axiom)
        self._save_axioms()
        self.log.info("axiom_absorbed", keywords=axiom.keywords)
        return axiom

    def get_axioms(self, limit: int = 20) -> list[dict]:
        return [{"query": a.query, "answer": a.answer, "keywords": a.keywords}
                for a in list(self.axioms)[-limit:]]

    def _save_axioms(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "axioms.jsonl"
        with open(path, "a") as f:
            a = self.axioms[-1]
            f.write(json.dumps({"query": a.query, "question": a.question,
                "answer": a.answer, "keywords": a.keywords, "timestamp": a.timestamp},
                ensure_ascii=False) + chr(10))

    def _load_axioms(self) -> None:
        path = self.data_dir / "axioms.jsonl"
        if not path.exists(): return
        try:
            for line in path.read_text().strip().split(chr(10)):
                if not line.strip(): continue
                d = json.loads(line)
                self.axioms.append(Axiom(**d))
        except (json.JSONDecodeError, KeyError):
            pass