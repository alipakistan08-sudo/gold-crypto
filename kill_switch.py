"""Independent kill switch — outside LLM / agent control."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trading_desk.models.enums import KillLevel


class KillSwitch:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(KillLevel.CLEAR, actor="system", reason="init")

    def _write(self, level: KillLevel, actor: str, reason: str) -> dict:
        record = {
            "level": level.value,
            "actor": actor,
            "reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Append to log file sibling
        log_path = self.path.with_suffix(".log.jsonl")
        with log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        self.path.write_text(json.dumps(record, indent=2))
        return record

    def status(self) -> dict:
        return json.loads(self.path.read_text())

    def level(self) -> KillLevel:
        return KillLevel(self.status()["level"])

    def is_halted(self) -> bool:
        return self.level() != KillLevel.CLEAR

    def activate(self, level: KillLevel, actor: str, reason: str) -> dict:
        if level == KillLevel.CLEAR:
            raise ValueError("use clear() to clear kill switch")
        return self._write(level, actor, reason)

    def clear(self, actor: str, reason: str, *, owner_confirmed: bool = False) -> dict:
        if not owner_confirmed:
            raise PermissionError("clearing kill switch requires owner_confirmed=True")
        return self._write(KillLevel.CLEAR, actor, reason)
