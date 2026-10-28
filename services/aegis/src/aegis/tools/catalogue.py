"""The tool catalogue: effect class, resource and registered inverse for every tool.

Names are dotted (``report_store.write_draft``) everywhere in HAEGIS: the
ledger, the plans and the console. On the MCP wire FastMCP namespaces mounted
tools with an underscore (``report_store_write_draft``); this module is the one
place that translates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

Effect = Literal["read", "write", "grant", "send", "destructive"]


class ToolSpec(BaseModel):
    name: str
    effect: Effect
    resource: str
    inverse: str | None = None
    recovery_only: bool = False

    @property
    def server(self) -> str:
        return self.name.split(".", 1)[0]

    @property
    def local_name(self) -> str:
        return self.name.split(".", 1)[1]

    @property
    def wire_name(self) -> str:
        return f"{self.server}_{self.local_name}"

    @property
    def irreversible(self) -> bool:
        return self.inverse == "irreversible"


class Catalogue:
    def __init__(self, tools: list[ToolSpec]) -> None:
        self._by_name = {tool.name: tool for tool in tools}
        self._by_wire = {tool.wire_name: tool for tool in tools}

    @classmethod
    def load(cls, path: str | Path) -> Catalogue:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls([ToolSpec(**entry) for entry in raw["tools"]])

    def get(self, name: str) -> ToolSpec:
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"Unknown tool {name!r}.") from None

    def by_wire(self, wire_name: str) -> ToolSpec:
        try:
            return self._by_wire[wire_name]
        except KeyError:
            raise KeyError(f"Unknown tool {wire_name!r}.") from None

    def all(self) -> list[ToolSpec]:
        return list(self._by_name.values())
