from __future__ import annotations
import json
import logging
import sys
from typing import Any, Dict, Optional, TYPE_CHECKING
import asyncio
from asyncio.futures import Future

from pymediasoup import Device
from pymediasoup import AiortcHandler
from pymediasoup.transport import Transport

from aiortc.contrib.media import MediaBlackhole, MediaStreamTrack

from websockets.client import WebSocketClientProtocol, connect as ws_connect

if TYPE_CHECKING:
    from .bot import Bot

_log = logging.getLogger(__name__)


class VcClient:
    def __init__(
        self,
        bot: Bot,
        url: str,
        vc_name: str,
        loop=None,
        recorder=MediaBlackhole(),
    ):
        self._loop = loop
        self._bot = bot
        self.vc_name = vc_name
        self.recorder = recorder

        self._url = url
        self._waiting_for_response: Dict[str, Future] = {}
        self._ws: Optional[WebSocketClientProtocol] = None
        self._device: Optional[Device] = None

        self._send_transport: Optional[Transport] = None
        self._recv_transport: Optional[Transport] = None

        self._producers = []
        self._consumers = []
        self._tasks = []
        self._connected = False
        self._events: Dict[str, Future] = {}

        self.closed = False

    async def _recv_msg_task(self):
        while True:
            if self._ws:
                try:
                    msg = json.loads(await self._ws.recv())
                    _log.debug(f"S2C {msg}")
                    callback = self._waiting_for_response.get(msg["action"])
                    if callback:
                        del self._waiting_for_response[msg["action"]]
                        callback.set_result(msg)
                    else:
                        if msg["action"] == "Init":
                            t = asyncio.create_task(self._init(msg))
                            self._tasks.append(t)
                        else:
                            _log.debug("^^ Action: IGNORED")
                except asyncio.CancelledError:
                    await self._ws.close()
                    break

    async def _send(self, msg):
        if self._ws:
            _log.debug(f"C2S {msg}")
            await self._ws.send(json.dumps(msg))

    async def _wait_for(self, event: str, timeout: Optional[float], **kwargs: Any):
        self._waiting_for_response[event] = self._loop.create_future()  # type: ignore
        try:
            return await asyncio.wait_for(
                self._waiting_for_response[event], timeout=timeout, **kwargs
            )
        except asyncio.TimeoutError:
            raise Exception(f"Operation '{event}' timed out")

    async def _init(self, msg):
        self._device = Device(handlerFactory=AiortcHandler.createFactory())
        await self._device.load(msg["routerRtpCapabilities"])
        await self._send(
            {
                "action": "Init",
                "rtpCapabilities": self._device.rtpCapabilities.dict(),  # type: ignore
            }
        )
        self._send_transport = self._device.createSendTransport(
            id=msg["producerTransportOptions"]["id"],
            iceParameters=msg["producerTransportOptions"]["iceParameters"],
            iceCandidates=msg["producerTransportOptions"]["iceCandidates"],
            dtlsParameters=msg["producerTransportOptions"]["dtlsParameters"],
            sctpParameters=None,
        )

        @self._send_transport.on("connect")
        async def on_producer_connect(dtlsParams):
            await self._send(
                {
                    "action": "ConnectProducerTransport",
                    "dtlsParameters": dtlsParams.dict(exclude_none=True),
                }
            )
            await self._wait_for("ConnectedProducerTransport", timeout=15)

        @self._send_transport.on("produce")
        async def on_produce(kind: str, rtpParameters, appData: dict):
            await self._send(
                {
                    "action": "Produce",
                    "kind": kind,
                    "rtpParameters": rtpParameters.dict(exclude_none=True),
                }
            )
            ans = await self._wait_for("ProducerCreated", timeout=15)
            return ans["id"]

        self._recv_transport = self._device.createRecvTransport(
            id=msg["consumerTransportOptions"]["id"],
            iceParameters=msg["consumerTransportOptions"]["iceParameters"],
            iceCandidates=msg["consumerTransportOptions"]["iceCandidates"],
            dtlsParameters=msg["consumerTransportOptions"]["dtlsParameters"],
            sctpParameters=None,
        )

        @self._recv_transport.on("connect")
        async def on_consumer_connect(dtlsParameters):
            await self._send(
                {
                    "action": "ConnectConsumerTransport",
                    "dtlsParameters": dtlsParameters.dict(exclude_none=True),
                }
            )
            await self._wait_for("ConnectedConsumerTransport", timeout=15)

        self._connected = True

    async def close(self):
        for task in self._tasks:
            task.cancel()
        for consumer in self._consumers:
            await consumer.close()
        for producer in self._producers:
            await producer.close()
        if self._send_transport:
            await self._send_transport.close()
        if self._recv_transport:
            await self._recv_transport.close()
        self.closed = True
        _log.debug("Disconnected from VC")

    async def connect(self):
        self._ws = await ws_connect(
            self._url + "?user={}".format(self._bot.user.username)
        )
        _log.debug('Connected to VC "{}"'.format(self.vc_name))

        if not self._loop:
            if sys.version_info.major == 3 and sys.version_info.minor == 6:
                loop = asyncio.get_event_loop()
            else:
                loop = asyncio.get_running_loop()
            self._loop = loop

        task_run_recv_msg = asyncio.create_task(self._recv_msg_task())
        self._tasks.append(task_run_recv_msg)
        while not self._connected:
            await asyncio.sleep(0.02)
        await self._tasks[1]
        self._tasks.pop(1)

    async def play(self, track: MediaStreamTrack):
        p = await self._send_transport.produce(track=track, stopTracks=False)  # type: ignore
        self._producers.append(p)

        @p.observer.on("trackended")
        async def on_track_end():
            track.stop()
            if e := self._events.pop(f"{track.id}-ended"):
                e.set_result(None)

        return p

    async def wait_for_track_end(self, track_id: str, timeout: Optional[float] = None):
        self._events[f"{track_id}-ended"] = self._loop.create_future()  # type: ignore
        await asyncio.wait_for(self._events[f"{track_id}-ended"], timeout=timeout)
