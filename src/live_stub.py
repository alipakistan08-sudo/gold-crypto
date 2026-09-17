"""Live execution adapter stub — fails closed unless gates are satisfied."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class LiveGateError(RuntimeError):
    """Raised when live path is attempted without gates."""


class LiveExecutionAdapter:
    """Stub that refuses all live orders unless config + owner ack are present."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.enabled = bool(cfg.get("live", {}).get("enabled", False))
        self.require_ack = bool(cfg.get("live", {}).get("require_owner_ack_file", True))
        self.ack_path = Path(cfg.get("live", {}).get("owner_ack_path", "artifacts/LIVE_OWNER_ACK"))

    def _gates_ok(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "LIVE_DISABLED (config live.enabled != true)"
        if self.require_ack and not self.ack_path.exists():
            return False, f"OWNER_ACK_MISSING ({self.ack_path})"
        return True, "OK"

    def place(self, *args: Any, **kwargs: Any) -> None:
        ok, reason = self._gates_ok()
        if not ok:
            raise LiveGateError(
                f"LIVE PATH REFUSED: {reason}. "
                "Set live.enabled=true AND create owner ack file after Phase 6 checklist."
            )
        raise LiveGateError(
            "LIVE PATH GATED: gates present but live adapter is a stub with no broker credentials. "
            "Refusing to place any live order."
        )
