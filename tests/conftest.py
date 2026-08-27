from __future__ import annotations

import pytest_asyncio

from zerofold.cns.store import CNSStore


@pytest_asyncio.fixture
async def store():
    s = CNSStore(":memory:")
    await s.connect()
    yield s
    await s.close()
