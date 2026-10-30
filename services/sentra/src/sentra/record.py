"""Record the storyline for the replay that runs with no service behind it (PRD §8.15, §17.2).

Runs every beat with interpretation off and writes one frame per beat to
``apps/console/public/demo/storyline/``: the console snapshot after that beat, and
the ledger up to it. The console plays these frames when the live sandbox is
unreachable and says on screen that it is a recording.

The storyline ends with a standing order kept. The week after is recorded too, in
``storyline/next-week/``: a new session loaded with that order, where the
scratchpad read is refused and the report goes out.

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


async def record(target: Path = TARGET) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    os.environ["SENTRA_INTERPRETER"] = "off"
    if target.exists():
        shutil.rmtree(target)
    session = Session("s-recorded", FIXTURES)
    frames = await _record(session, target)
    week = Session(
        "s-recorded-next-week", FIXTURES, orders=session.orders, storyline="next-week.yaml"
    )
    return frames, await _record(week, target / "next-week")


async def _record(session: Session, target: Path) -> list[dict[str, Any]]:
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
    frames, week = asyncio.run(record())
    print(f"recorded {len(frames)} frames and {len(week)} next-week frames to {TARGET}")


if __name__ == "__main__":
    main()
