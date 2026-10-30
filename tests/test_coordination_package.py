"""Synthetic coordination/recovery acceptance scenarios; no live model quality claims."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.utils.capabilities import invoke_pipeline


@pytest.mark.asyncio
async def test_capability_registry_cannot_dispatch_unknown_tools():
    worker = SimpleNamespace(send_email=AsyncMock())
    with pytest.raises(ValueError, match="Unsupported"):
        await invoke_pipeline({"Mail": worker}, "send_email", {"message": "Hello"})
    worker.send_email.assert_not_awaited()


