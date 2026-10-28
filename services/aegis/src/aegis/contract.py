"""Write the HAEGIS OpenAPI contract to ``contracts/openapi/haegis-v1.json``.

Same convention as the HIVE core: the committed contract is generated from the
service, and CI fails if the two drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from aegis.api.app import create_app

TARGET = Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "haegis-v1.json"


def main() -> None:
    document = create_app().openapi()
    TARGET.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
