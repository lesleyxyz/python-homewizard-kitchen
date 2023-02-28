import asyncio
from hwkitchen import HWSocket, Kettle


ws_client = HWSocket("<email>", "<password>")


async def on_new_status(kettle: Kettle):
    # Get the latest status
    print("Updated", kettle.to_json())


async def on_connection():
    # Get the first device from my HomeWizard Kitchen Account
    devices = await ws_client.get_devices()
    kettle_id = devices.get("devices", [])[0].get("identifier")

    # Subscribe for new status
    kettle = await ws_client.subscribe_device(kettle_id, on_new_status)

    # Update target temperature
    kettle.set_target_temperature(65)
    await ws_client.update(kettle)

# This will run forever
future = ws_client.connect(on_connection)
asyncio.get_event_loop().run_until_complete(future)
