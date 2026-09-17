"""Load and expose desk configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "desk.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with cfg_path.open() as f:
        data = yaml.safe_load(f)
    # Resolve relative artifact paths against project root
    for key in ("journal_dir", "signal_dir", "replay_dir"):
        p = Path(data["paths"][key])
        if not p.is_absolute():
            data["paths"][key] = str(ROOT / p)
    ack = Path(data["live"]["owner_ack_path"])
    if not ack.is_absolute():
        data["live"]["owner_ack_path"] = str(ROOT / ack)
    ks = Path(data["kill_switch"]["path"])
    if not ks.is_absolute():
        data["kill_switch"]["path"] = str(ROOT / ks)
    return data


def ensure_artifact_dirs(cfg: dict[str, Any]) -> None:
    for key in ("journal_dir", "signal_dir", "replay_dir"):
        Path(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
    Path(cfg["kill_switch"]["path"]).parent.mkdir(parents=True, exist_ok=True)
