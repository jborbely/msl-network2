from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

home = Path(tempfile.gettempdir()) / ".msl"
os.environ["MSL_NETWORK_HOME"] = str(home)


@pytest.fixture
def home_dir() -> Iterator[Path]:
    shutil.rmtree(home, ignore_errors=True)
    yield home
    shutil.rmtree(home)
