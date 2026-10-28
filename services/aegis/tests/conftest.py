"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "fixtures" / "aegis_reporting"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
