"""Record the storyline for the replay that runs with no service behind it (PRD §8.15, §17.2).

Runs every beat with interpretation off and writes one frame per beat to
``apps/console/public/demo/storyline/``: the console snapshot after that beat, and
the ledger up to it. The console plays these frames when the live sandbox is
unreachable and says on screen that it is a recording.

Everything is deterministic (seeded clock, fixed session id, no model), so CI
re-records and fails if the committed frames have drifted from the engine.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from sentra.api.snapshot import snapshot
from sentra.scenario import Session

REPO = Path(__file__).resolve().parents[4]
FIXTURES = REPO / "fixtures" / "reporting"
TARGET = REPO / "apps" / "console" / "public" / "demo" / "storyline"


def _write(path: Path, body: Any) -> None:
    path.write_text(
        json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


async def record(target: Path = TARGET) -> list[dict[str, Any]]:
    os.environ["SENTRA_INTERPRETER"] = "off"
    session = Session("s-recorded", FIXTURES)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    frames: list[dict[str, Any]] = []
    while not session.at_end:
        beat = await session.step()
        title = str(session.beats[session.position - 1]["title"])
        name = f"beat-{beat:02d}.json"
        view = snapshot(session)
        view["labels"] = {"data": "Fictional data", "mode": "Recorded replay"}
        _write(
            target / name,
            {"snapshot": view, "ledger": [e.model_dump() for e in session.ledger.events()]},
        )
        frames.append({"n": beat, "title": title, "file": name})
    _write(
        target / "index.json",
        {
            "note": "Recorded from the SENTRA service with interpretation off. Not a live session.",
            "frames": frames,
        },
    )
    return frames


def main() -> None:
    frames = asyncio.run(record())
    print(f"recorded {len(frames)} frames to {TARGET}")


if __name__ == "__main__":
    main()
