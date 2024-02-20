from __future__ import annotations
import json
import logging
import sys
from typing import Any, Dict, Optional
import asyncio
from asyncio.futures import Future

from pymediasoup import Device
from pymediasoup import AiortcHandler
from pymediasoup.transport import Transport
from pymediasoup.consumer import Consumer
from pymediasoup.producer import Producer
from pymediasoup.sctp_parameters import SctpStreamParameters

# from aiortc import VideoStreamTrack
# from aiortc.mediastreams import AudioStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaBlackhole

import websockets

_log = logging.getLogger(__name__)


class VcClient:
    def __init__(
        self,
        url: str,
        player: Optional[MediaPlayer] = None,
        recorder=MediaBlackhole(),
        loop=None,
    ):
        self._loop = loop

        self.url = url
        self.player = player
        self.recorder = recorder
        self._waiting_for_response: Dict[str, Future] = {}
        self._ws: Any = None
        self._device: Optional[Device] = None
        self._tracks = []

        if player and player.audio:
            self._tracks.append(player.audio)
        if player and player.video:
            self._tracks.append(player.video)

        self._send_transport: Optional[Transport] = None
        self._recv_transport: Optional[Transport] = None

        self._producers = []
        self._consumers = []
        self._tasks = []
        self._closed = False

    async def recv_msg_task(self):
        while True:
            if self._ws:
                msg = json.loads(await self._ws.recv())
                _log.debug(f"S2C {msg}")
                callback = self._waiting_for_response.get(msg["action"])
                if callback:
                    del self._waiting_for_response[msg["action"]]
                    callback.set_result(msg)
                else:
                    if msg["action"] == "Init":
                        t = asyncio.create_task(self.init(msg))
                        self._tasks.append(t)
                    else:
                        _log.debug("^^ Action: IGNORED")

    async def send(self, msg):
        _log.debug(f"C2S {msg}")
        await self._ws.send(json.dumps(msg))

    async def _wait_for(self, event: str, timeout: Optional[float], **kwargs: Any):
        self._waiting_for_response[event] = self._loop.create_future()
        try:
            return await asyncio.wait_for(
                self._waiting_for_response[event], timeout=timeout, **kwargs
            )
        except asyncio.TimeoutError:
            raise Exception(f"Operation '{event}' timed out")

    async def init(self, msg):
        self._device = Device(
            handlerFactory=AiortcHandler.createFactory(tracks=self._tracks)
        )
        await self._device.load(msg["routerRtpCapabilities"])
        await self.send(
            {
                "action": "Init",
                "rtpCapabilities": self._device.rtpCapabilities.dict(),
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
            await self.send(
                {
                    "action": "ConnectProducerTransport",
                    "dtlsParameters": dtlsParams.dict(exclude_none=True),
                }
            )
            await self._wait_for("ConnectedProducerTransport", timeout=15)

        @self._send_transport.on("produce")
        async def on_produce(kind: str, rtpParameters, appData: dict):
            await self.send(
                {
                    "action": "Produce",
                    "kind": kind,
                    "rtpParameters": rtpParameters.dict(exclude_none=True),
                }
            )
            ans = await self._wait_for("ProducerCreated", timeout=15)
            return ans["id"]

        for track in self._tracks:
            self._producers.append(
                await self._send_transport.produce(
                    track=track, stopTracks=False, appData={}
                )
            )

        self._recv_transport = self._device.createRecvTransport(
            id=msg["consumerTransportOptions"]["id"],
            iceParameters=msg["consumerTransportOptions"]["iceParameters"],
            iceCandidates=msg["consumerTransportOptions"]["iceCandidates"],
            dtlsParameters=msg["consumerTransportOptions"]["dtlsParameters"],
            sctpParameters=None,
        )

        @self._recv_transport.on("connect")
        async def on_consumer_connect(dtlsParameters):
            await self.send(
                {
                    "action": "ConnectConsumerTransport",
                    "dtlsParameters": dtlsParameters.dict(exclude_none=True),
                }
            )
            await self._wait_for("ConnectedConsumerTransport", timeout=15)

    async def close(self):
        _log.debug("Closing VC consumer connections")
        for consumer in self._consumers:
            await consumer.close()
        _log.debug("Closing VC producer connections")
        for producer in self._producers:
            await producer.close()
        _log.debug("Disconnecting from VC websocket")
        for task in self._tasks:
            task.cancel()
        _log.debug("Closing send transport")
        if self._send_transport:
            await self._send_transport.close()
        _log.debug("Closing receive transport")
        if self._recv_transport:
            await self._recv_transport.close()
        _log.debug("Stopping media recorder")
        await self.recorder.stop()
        _log.info("Disconnected from VC")

    async def run(self):
        if not self._loop:
            if sys.version_info.major == 3 and sys.version_info.minor == 6:
                loop = asyncio.get_event_loop()
            else:
                loop = asyncio.get_running_loop()
            self._loop = loop

        self._ws = await websockets.connect(self.url)
        _log.info("Connected to VC")
        task_run_recv_msg = asyncio.create_task(self.recv_msg_task())
        self._tasks.append(task_run_recv_msg)
