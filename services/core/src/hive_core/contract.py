"""Generate the committed OpenAPI document from the running application.

Keeping the contract hand-written guarantees it drifts from the service. This
module derives it instead, and a contract test fails the build when the checked-in
copy is stale.

Regenerate with::

    uv run python -m hive_core.contract
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hive_core.main import app

_REPO_ROOT = Path(__file__).resolve().parents[4]

CONTRACT_PATH = _REPO_ROOT / "contracts" / "openapi" / "hive-core-v1.json"


def build_document() -> dict[str, Any]:
    """The OpenAPI description of the service as it is currently defined."""
    document = dict(app.openapi())
    document["servers"] = [
        {"url": "http://127.0.0.1:8000", "description": "Local development server"}
    ]
    return document


def write_document(path: Path = CONTRACT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_document(), indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return path


if __name__ == "__main__":  # pragma: no cover - developer entry point
    written = write_document()
    print(f"Wrote {written}")
