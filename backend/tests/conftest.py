"""Make `backend/` importable when pytest is launched from the repo root."""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def _restore_event_loop():
    """Motor's GridFSBucket needs a current loop when `server` is imported.

    Tests that call ``asyncio.run()`` close that loop; put one back so later
    tests (member auth) can still import the app.
    """
    yield
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
