from typing import Union, Callable, Awaitable, Optional
from jsonpatch import JsonPatch
import urllib.parse
import requests
import hashlib
import base64
import websockets
import asyncio
import inspect
import logging
import json
import httpx

from ..models import Kettle
_LOGGER = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)

class HWSocket:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.endpoint = "https://api.homewizardeasyonline.com/v1/"

        self.devices = {}
        self.message_id = 1
        self.message_id_futures = {}
        self.device_update_callbacks = {}
        self.ws = None
        self._reconnect_lock = asyncio.Lock()

    async def _auth_get(self, resource: str) -> dict:
        url = urllib.parse.urljoin(self.endpoint, resource)
        encoded_pass = self.password.encode('utf-8')
        sha1_pass = hashlib.sha1(encoded_pass).hexdigest()

        encoded_token = f"{self.username}:{sha1_pass}".encode("utf-8")
        base64_token = base64.b64encode(encoded_token).decode("utf-8")

        async with httpx.AsyncClient() as client:
            result = await client.get(url, headers={
                "Authorization": f"Basic {str(base64_token)}"
            })

        return result.json()

    async def get_token(self) -> str:
        result = await self._auth_get("auth/login")
        return result.get("token")

    async def get_account(self):
        return await self._auth_get("account")

    async def get_devices(self):
        return await self._auth_get("auth/devices")

    def _get_device(self, device_id: str) -> Kettle:
        device_dict = self.devices[device_id]
        d_type = device_dict.get("type")

        if d_type == "kettle":
            return Kettle(device_dict)

    async def _on_response_msg(self, msg: dict):
        message_id = msg.get("message_id")
        if message_id not in self.message_id_futures.keys():
            _LOGGER.error(f"message_id {message_id} not found", msg)
            return

        self.message_id_futures[message_id](msg)

    async def _on_device_msg(self, msg: dict):
        device_id = msg.get("device")
        self.devices[device_id] = msg
        await self._notify_device_handler(device_id)

    async def _on_device_update_msg(self, msg: dict):
        device_id = msg.get("device")

        patch = JsonPatch(msg.get("patch", []))
        patch.apply(self.devices[device_id], in_place=True)

        await self._notify_device_handler(device_id)

    async def _on_device_name_msg(self, msg: dict):
        device_id = msg.get("device")
        name = msg.get("name")

        device = self._get_device(device_id)
        device.set_name(name)
        self.devices[device_id] = device.to_json()

        await self._notify_device_handler(device_id)

    async def _notify_device_handler(self, device_id: str):
        device = self._get_device(device_id)

        if device_id in self.device_update_callbacks:
            fn = self.device_update_callbacks[device_id]

            if not fn:
                return
            if inspect.iscoroutinefunction(fn):
                await self.device_update_callbacks[device_id](device)
            else:
                fn(device)

    async def subscribe_device(self, device_id: str, callback: Optional[Callable[[Kettle], Union[Awaitable[None], None]]]):
        _LOGGER.debug(f"Subscribing to device {device_id}")

        future = asyncio.get_event_loop().create_future()
        self.device_update_callbacks[device_id] = future.set_result

        await self.send("subscribe_device", {
            "device": device_id
        })

        kettle = await future
        _LOGGER.debug(f"Subscribed to device {device_id}")
        self.device_update_callbacks[device_id] = callback

        if not callback:
            return
        if inspect.iscoroutinefunction(callback):
            await self.device_update_callbacks[device_id](kettle)
        else:
            callback(kettle)

        return kettle

    async def _on_message(self, message: str):
        _LOGGER.debug(f"_on_message(message={repr(message)})")
        msg = json.loads(message)
        msg_type_handlers = {
            "response": self._on_response_msg,
            "kettle": self._on_device_msg,
            "device_name": self._on_device_name_msg,
            "json_patch": self._on_device_update_msg,
        }

        msg_type = msg.get("type")
        if msg_type not in msg_type_handlers.keys():
            _LOGGER.error(f"Message type {msg_type} not found", msg)
            return

        await msg_type_handlers[msg_type](msg)

    async def connect(self, callback: Optional[Callable[[], Union[Awaitable[None], None]]]):
        await asyncio.gather(
            self._connect(callback),
            self._receive_messages()
        )

    async def reconnect(self, force=True):
        _LOGGER.debug("reconnect(): Reconnecting")
        async with self._reconnect_lock:
            if self.ws and not self.ws.closed and not force:
                _LOGGER.debug("reconnect(): Already reconnected")
                return
            future = asyncio.get_event_loop().create_future()
            callback = lambda: (future.set_result(True))
    
            await self._connect(callback)
            await asyncio.wait_for(future, timeout=60)
    
            for device_id, callback in self.device_update_callbacks.copy().items():
                await self.subscribe_device(device_id, callback)

    async def _connect(self, callback: Optional[Callable[[], Union[Awaitable[None], None]]]):
        """Initiate connection"""
        _LOGGER.debug("Connecting")
        self.message_id = 1
        self.message_id_futures = {}
        self.ws = await websockets.connect("wss://app-ws.homewizard.com/ws")
        _LOGGER.debug("Connected")

        await self.send("hello", {
            "type": "hello",
            "os": "android",
            "source": "kitchen",
            "version": "1.5.0",
            "token": await self.get_token(),
            "compatibility": 2
        })

        if not callback:
            return
        elif inspect.iscoroutinefunction(callback):
            await callback()
        else:
            callback()

    async def _receive_messages(self):
        """
        Loop to keep getting websocket messages coming in
        """
        while True:
            await asyncio.sleep(0.5)
            if not self.ws:
                continue
            try:
                message = await self.ws.recv()
                asyncio.get_event_loop().create_task(self._on_message(message))
            except websockets.exceptions.ConnectionClosed:
                _LOGGER.error("_receive_messages(): Connection lost")
                self.ws = None
                asyncio.create_task(self.reconnect())

    async def send(self, msg_type: str, payload: dict):
        for attempt in range(3):
            try:
                if self.ws is None or self.ws.closed:
                    await self.reconnect(False)
            except (AttributeError,
                    websockets.exceptions.ConnectionClosed):
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
    
        message_id = self.message_id
        self.message_id += 1

        future = asyncio.get_event_loop().create_future()
        self.message_id_futures[message_id] = future.set_result

        try:
            msg = json.dumps({
                "device": None,
                "model": None,
                "online": None,
                "state": None,
                **payload,
                "type": msg_type,
                "message_id": message_id
            })
            _LOGGER.debug(f"send(): {msg}")
            await self.ws.send(msg)
        except websockets.ConnectionClosedError:
            _LOGGER.error("send(): Connection lost")
            await self.reconnect()
            return await self.send(msg_type, payload)

        return await future

    async def update(self, device: Kettle):
        device_id = device.get_id()
        updated = device.to_json()
        patch = JsonPatch.from_diff(self.devices[device_id], updated)

        return await self.send("json_patch", {
            "device": device_id,
            "patch": patch.patch
        })
