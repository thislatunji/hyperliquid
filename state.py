from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any

from config import STATE_FILE

log = logging.getLogger("state")


@dataclass
class MonitorState:
    last_block: int = 0
    known_pairs: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_pairs_this_session: set[str] = field(default_factory=set)

    def pair_key(self, token0: str, token1: str) -> str:
        a, b = token0.lower(), token1.lower()
        return f"{a}:{b}" if a < b else f"{b}:{a}"

    def mark_known(self, pair_key: str, token0: str, token1: str, amm_name: str, pool: str) -> None:
        self.known_pairs[pair_key] = {
            "token0": token0,
            "token1": token1,
            "amm": amm_name,
            "pool": pool,
        }
        self.new_pairs_this_session.add(pair_key)

    def is_known(self, pair_key: str) -> bool:
        return pair_key in self.known_pairs

    def is_new_this_session(self, pair_key: str) -> bool:
        return pair_key in self.new_pairs_this_session


def load_state() -> MonitorState:
    if not os.path.exists(STATE_FILE):
        log.info("No state file found, starting fresh")
        return MonitorState()
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        state = MonitorState(
            last_block=data.get("last_block", 0),
            known_pairs=data.get("known_pairs", {}),
            new_pairs_this_session=set(data.get("new_pairs_this_session", [])),
        )
        log.info(
            "Loaded state: last_block=%d, %d known pairs, %d new this session",
            state.last_block, len(state.known_pairs), len(state.new_pairs_this_session),
        )
        return state
    except Exception as e:
        log.warning("Failed to load state: %s, starting fresh", e)
        return MonitorState()


def save_state(state: MonitorState) -> None:
    try:
        data = {
            "last_block": state.last_block,
            "known_pairs": state.known_pairs,
            "new_pairs_this_session": list(state.new_pairs_this_session),
        }
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        log.error("Failed to save state: %s", e)
