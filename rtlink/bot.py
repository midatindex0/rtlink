import asyncio
from typing import Optional, Dict, List, Coroutine, TypeVar, Union, Callable, Any
import json
import time
import logging

from .http import HTTPClient
from .types import Comment, User, Forum
from .utils import setup_logging
from .commands import Command, CommandManager, help_command

from websockets.client import connect


T = TypeVar("T")
Coro = Coroutine[Any, Any, T]
CoroT = Callable[..., Coro[Any]]
logger = logging.getLogger(__name__)


class Bot:
    """The Bot isinstance represents a connection to the rtwalk API, handles events and commands.

    Args:
        api_url: Url of the rtwalk server.
        client (rtlink.http.HTTPClient): A http client that maintains the API connection.
        loop: Asyncio event loop.

    Attributes:
        user (rtlink.types.User): The bot user. Only available after login.
    """

    def __init__(
        self,
        api_url: Optional[str] = "http://localhost:3758/api/v1",
        client: Optional[HTTPClient] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        setup_logging()
        self._client: HTTPClient = client or HTTPClient(
            api_url=api_url or "http://localhost:3758/api/v1"
        )
        self._events: Dict[str, List[Union[CoroT, Callable]]] = {}
        self._closed: bool = False
        self._rte_options = {
            "comment": False,
            "comment_edit": False,
            "post": False,
            "post_edit": False,
        }

        self.command_manager = CommandManager()
        self.command_manager._set_bot(self)
        self.command_manager.add_command(Command(help_command, "help"))
        asyncio.set_event_loop(loop)

    def is_closed(self) -> bool:
        """Check if the RTE connection has closed. Implies the bot has logged out.

        Note:
            There is a bit of time delay between self._closed turning True and the bot actually logging out but
            it is bound to happen in the near future.

        Returns:
            (bool): True if the RTE connection has closed.
        """
        return self._closed

    async def start(self, token: str):
        """Non-blocking entry point for the bot. Logs in and starts the RTE websocket connection.
            For a blocking method use [`Bot.run`][rtlink.bot.Bot.run].

        Args:
            token (string): Your bot token
        """
        email, password = token.split("@")
        await self._validate_and_set_api_info()
        await self._client.login(email, password)
        logger.info(
            f"Bot logged in to {self._client.api_url} (Username: {self._client.user.username})"
        )
        logger.debug(f"Self: {self._client.user}")
        self.user: User = self._client.user
        self.command_manager.prog = f"@{self.user.username}"
        await self._on_login()
        try:
            async with connect(
                "{}?comment_new={}&comment_edit={}&post_new={}&post_edit={}".format(
                    self.rte_url,
                    self._rte_options["comment"],
                    self._rte_options["comment_edit"],
                    self._rte_options["post"],
                    self._rte_options["post_edit"],
                )
            ) as ws:
                self.ws = ws
                logger.info("Listening to RTE websocket at {}".format(self.rte_url))
                logger.info(
                    f"RTE websocket latency: {(await self._calc_latency_ms(ws)):.2f}ms"
                )
                while not self.is_closed():
                    try:
                        msg = json.loads(await ws.recv())
                    except asyncio.CancelledError:
                        logger.info("Disconnecting from RTE websocket")
                        break
                    logger.debug("RTE Event: {}".format(msg))
                    if msg["event"] == "COMMENT_NEW":
                        cmnt = Comment(**msg["item"])
                        cmnt._client = self._client
                        await self._on_comment(cmnt)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, logging out")
        await self._client.logout()
        logger.info("Bot has logged out")
        await self._on_logout()

    async def _calc_latency_ms(self, ws):
        t1 = time.time()
        await ws.ping()
        return (time.time() - t1) * 1000

    async def _validate_and_set_api_info(self):
        version = await self._client.get_api_info()
        self.rte_url = version["rte"]
        self.vc_url = version["vc"]

    async def latency(self) -> float:
        """The RTE websocket latency in milliseconds.

        Returns:
            (float): The latency in milliseconds.
        """
        return await self._calc_latency_ms(self.ws)

    def run(self, token: str):
        """
        Blocking call to start the bot. Use [`Bot.start`][rtlink.bot.Bot.start] for a nonblocking call.

        This is equivalent to calling `asyncio.run(bot.start(token))`
        """
        asyncio.run(self.start(token))

    def on_event(self, name: str):
        def __dec(fn):
            if name == "comment":
                self._rte_options["comment"] = True
            if event := self._events.get(name):
                event.append(fn)
            else:
                self._events[name] = [fn]

        return __dec

    def command(self, name: Optional[str] = None, aliases: List[str] = []):
        def __dec(fn):
            self._rte_options["comment"] = True
            self.command_manager.add_command(Command(fn, name or fn.__name__, aliases))

        return __dec

    async def dispatch(self, event: str, *args, **kwargs):
        if event_fn := self._events.get(event):
            async with asyncio.TaskGroup() as tg:
                for fn in event_fn:
                    if asyncio.iscoroutinefunction(fn):
                        tg.create_task(fn(*args, **kwargs))
                    else:
                        tg.create_task(asyncio.to_thread(fn, *args, **kwargs))

    async def _on_login(self):
        await self.dispatch("login")

    async def _on_logout(self):
        await self.dispatch("logout")

    async def _on_comment(self, comment: Comment):
        await self.dispatch("comment", comment)
        await self.command_manager.try_process_command(comment)

    async def fetch_forum(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        ids: Optional[List[str]] = None,
        names: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> Optional[Union[Forum, List[Forum]]]:
        """Fetches a single/multiple forums using name/ids.
        Checks the cache first and hits the API only when it can't find the forum in cache.

        Args:
            name: Name of the forum (not display name).
            id: ID of the forum.
            names: To fetch multiple forums by name.
            ids: To fetch multiple forums by ID.

        Returns:
            : The forum/forums to be fetch.
        """
        if use_cache:
            if r := await self._client.get_cache(name or id or ids or names):
                if not isinstance(r, list):
                    return r
                elif None not in r:
                    return r
        return await self._client.fetch_forum(
            name=name,
            id=id,
            ids=ids,
            names=names,
        )
