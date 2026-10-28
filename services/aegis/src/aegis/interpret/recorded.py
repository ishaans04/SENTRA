"""Recorded model responses, for replay and for model-off runs.

From the AEGIS cassette: store the model's raw structured output, not the
finished plan, and replay it through the same validation the live path uses.
A recording that stored finished state would prove nothing about the validator.

Entries are keyed by kind and normalised text, so a judge's dictation that
differs only in spacing, punctuation or capitalisation still hits the recording.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_PUNCTUATION = re.compile(r"[^\w\s/-]+")


def _key(kind: str, text: str) -> str:
    normalised = " ".join(_PUNCTUATION.sub(" ", text.lower()).split())
    return f"{kind}:{hashlib.sha256(normalised.encode()).hexdigest()[:16]}"


class RecordedResponses:
    """A JSON file of ``{key: raw model output}``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, Any] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = dict(data.get("entries", {}))

    def get(self, kind: str, text: str) -> Any | None:
        return self.entries.get(_key(kind, text))

    def put(self, kind: str, text: str, payload: Any) -> None:
        self.entries[_key(kind, text)] = payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "note": "Recorded model outputs, replayed through the same validation as live output.",
            "entries": self.entries,
        }
        self.path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def __len__(self) -> int:
        return len(self.entries)
