import asyncio


async def fetch_item(item_id, delay):
    """Simulate fetching an item with a delay."""
    await asyncio.sleep(delay)
    return f"item-{item_id}"


async def fetch_all(items):
    """Fetch all items and return them in the original order."""
    tasks = [fetch_item(item['id'], item['delay']) for item in items]
    # Bug: using as_completed returns results in completion order, not original order
    results = []
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
    return results
