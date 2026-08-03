import asyncio
import pytest
from src.fetcher import fetch_all


@pytest.mark.asyncio
async def test_fetch_all_preserves_order():
    items = [
        {'id': 1, 'delay': 0.03},
        {'id': 2, 'delay': 0.01},
        {'id': 3, 'delay': 0.02}
    ]
    results = await fetch_all(items)
    # Should return in original order: [item-1, item-2, item-3]
    # Not completion order: [item-2, item-3, item-1]
    assert results == ['item-1', 'item-2', 'item-3']
