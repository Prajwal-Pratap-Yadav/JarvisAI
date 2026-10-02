from pathlib import Path

import pytest

from jarvis.config import Settings
from jarvis.runtime import Runtime


@pytest.fixture
async def runtime(tmp_path: Path):
    settings = Settings(data_dir=tmp_path / "data", workspace=tmp_path / "workspace")
    runtime = Runtime(settings)
    await runtime.start()
    try:
        yield runtime
    finally:
        await runtime.close()
