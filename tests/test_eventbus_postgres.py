import asyncio

from server.eventbus.postgres import PostgresEventBus


async def test_publish_subscribe_round_trip(test_engine):
    bus = PostgresEventBus(test_engine)
    received: list[str] = []

    stop = asyncio.Event()

    async def consumer():
        async for payload in bus.subscribe("test_channel"):
            received.append(payload)
            stop.set()
            break

    task = asyncio.create_task(consumer())
    # give the LISTEN time to register
    await asyncio.sleep(0.2)

    await bus.publish("test_channel", "hello")
    await asyncio.wait_for(stop.wait(), timeout=2.0)

    task.cancel()
    assert received == ["hello"]
    await bus.close()
