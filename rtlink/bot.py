import asyncio
import functools
from typing import Optional, Dict, List, Coroutine, TypeVar, Union, Callable, Any

from .http import HTTPClient
from .types import User


T = TypeVar("T")
Coro = Coroutine[Any, Any, T]
CoroT = TypeVar("CoroT", bound=Callable[..., Coro[Any]])


class Bot:
    def __init__(self, client: HTTPClient = None, api_url: str = None) -> None:
        self.client: HTTPClient = client or HTTPClient(api_url=api_url)
        self.user: Optional[User] = None
        self._events: Dict[str, List[Union[CoroT, Callable]]] = {}
        self._closed: bool = False

    def is_closed(self):
        self._closed

    async def start(self, token: str):
        email, password = token.split("@")
        await self.client.login(email, password)
        self.user = self.client.user
        await self.on_login()
        try:
            while not self.is_closed():
                pass
        except KeyboardInterrupt:
            pass
        await self.client.logout()
        await self.on_logout()

    def run(self, token: str):
        """
        This is equivalent to calling `asyncio.run(Bot.start(token))`
        """
        asyncio.run(self.start(token))

    def on_event(self, name: str):
        def __dec(fn):
            if event := self._events.get(name):
                event.append(fn)
            else:
                self._events[name] = [fn]

        return __dec

    async def dispatch(self, event: str, *args, **kwargs):
        if event := self._events.get(event):
            for fn in event:
                if asyncio.iscoroutinefunction(fn):
                    await fn(*args, **kwargs)
                else:
                    fn(*args, **kwargs)

    async def on_login(self):
        await self.dispatch("login")

    async def on_logout(self):
        await self.dispatch("logout")
