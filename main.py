import asyncio
import contextlib
import logging
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
import time
from functools import partial

device_dict: dict[str, BLEDevice] = dict()

logging.basicConfig()
logging.root.setLevel(logging.NOTSET)
logging.basicConfig(level=logging.NOTSET)

log = logging.getLogger(__name__)

event_loop = asyncio.get_event_loop()

queue_map: dict['str', asyncio.Queue]


async def connect_to_devices(lock: asyncio.Lock):
    # Keep scanning and connecting to devices as their advertisements appear
    try:
        async with contextlib.AsyncExitStack() as stack:
            while True:
                async with BleakScanner() as scanner:
                    async with lock:
                        log.debug(f"Find devices like Lgr_ ...")
                        async for bd, ad in scanner.advertisement_data():
                            # what's the signal to toss the stack?
                            if bd.name and bd.name.startswith('Lgr_'):
                                log.debug(f"Found target device: {bd!r} advertisement: {ad!r}")
                                if bd.name not in device_dict:
                                    log.debug('Device %s not in dict', bd.name)
                                    device_dict[bd.name] = bd
                                    client = BleakClient(bd)
                                    log.debug("connecting to %s", bd)
                                    await stack.enter_async_context(client)
                                    # This will be called immediately before client.__aexit__ when
                                    # the stack context manager exits.
                                    stack.callback(callback_disco, bd.name)
                                    # Start a new queue consumer for this connection
                                    queue = asyncio.Queue()
                                    queue_map[bd.name] = queue
                                    asyncio.ensure_future(run_queue_consumer(queue), loop=event_loop)

                                    async def callback_disco(bd_name: str):
                                        log.debug("Disconnecting from %s", bd.name)
                                        del queue_map[bd.name]
                                        del device_dict[bd.name]

                                    async def callback_notify(_, client: BleakClient, sender: int, data: bytearray):
                                        # Notifications arrive here
                                        log.debug(f"Notification from device address: {client.address} "
                                                  f"characteristic handle: {client.services.get_characteristic(sender)}. "
                                                  f"Data: {data}")
                                        await queue.put((time.time(), data))

                                    await client.start_notify('B1190EFB-176F-4B32-A715-89B3425A4076',
                                                              partial(callback_notify, client))
                                else:
                                    # The device might still be advertising for connections ...
                                    pass
                            else:
                                # Not a matching device - next one ...
                                pass
                        # End of the advertisements loop
                    # The lock is released here. The device is still connected and the
                    # Bluetooth adapter is now free to scan and connect another device
                    # without disconnecting this one.
                await asyncio.sleep(5.0)
            # end infinite loop
        # The stack context manager exits here, triggering disconnection
        log.debug("disconnected from all connections")
    except Exception as ex:
        log.exception("error with %s", ex)


async def run_queue_consumer(queue: asyncio.Queue):
    # TODO Need one of these per connection
    log.info("Starting queue consumer")
    while True:
        # Use await asyncio.wait_for(queue.get(), timeout=1.0) if you want a timeout for getting data.
        epoch, data = await queue.get()
        if data is None:
            log.info("Got message from client about disconnection. Exiting consumer loop...")
            break
        else:
            log.info("Received callback data via async queue at %s: %r", epoch, data)


async def main():
    # queue = asyncio.Queue() # TODO need several of these - one per connection
    # consumer_task = run_queue_consumer(queue)
    lock = asyncio.Lock()
    await asyncio.gather(connect_to_devices(lock))


if __name__ == "__main__":
    asyncio.run(main())
