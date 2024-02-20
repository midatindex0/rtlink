from __future__ import annotations
import argparse
import shlex
import logging
import asyncio

from typing import (
    TYPE_CHECKING,
    List,
    Optional,
    TypeVar,
    Coroutine,
    Any,
    Callable,
    Dict,
    Union,
)

from .types import Comment

if TYPE_CHECKING:
    from .bot import Bot

T = TypeVar("T")
Coro = Coroutine[Any, Any, T]
CoroT = Callable[..., Coro[Any]]
logger = logging.getLogger(__name__)

# Types that define hw to parse arguments
Flag = TypeVar("Flag")
ShortFlag = TypeVar("ShortFlag")
LongFlag = TypeVar("LongFlag")


class Ctx:
    def __init__(self, bot: Bot, comment: Comment):
        self.bot = bot
        self.comment = comment

    async def reply(self, content: str) -> Comment:
        return await self.comment.reply(content)


class Command:
    def __init__(self, fn, name: Optional[str] = None, aliases: List[str] = []):
        self.name = name
        self.aliases = aliases
        self.fn = fn


class CommandManager(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(exit_on_error=False, *args, **kwargs)

    def _set_bot(self, bot: Bot):
        self.commands: Dict[str, Union[CoroT, Callable]] = {}
        self.subparsers = self.add_subparsers(dest="command")
        self.bot = bot

    def add_command(self, command: Command):
        self.commands[command.name or command.fn.__name__] = command.fn
        self.subparsers.add_parser(
            command.name or command.fn.__name__,
            help=command.fn.__doc__,
            aliases=command.aliases,
        )
        for alias in command.aliases:
            self.commands[alias] = command.fn

    async def try_process_command(self, comment: Comment) -> Any:
        prefix = f"@{self.bot.user.username}"
        if comment.content.startswith(prefix):
            to_parse = comment.content[len(prefix) :]
            try:
                namespace = self.parse_args(shlex.split(to_parse))
            except argparse.ArgumentError as e:
                logger.warn(e)
                await self.bot.dispatch(
                    "command_error", e
                )  # TODO: use correct rtwalk error
                return
            logger.debug(f"Command namespace: {namespace}")
            if command := self.commands.get(namespace.command):
                return await self.run(command, namespace, comment)

    async def run(
        self,
        command: Union[CoroT, Callable],
        namespace: argparse.Namespace,
        comment: Comment,
    ) -> Any:
        ctx = Ctx(self.bot, comment)
        if asyncio.iscoroutinefunction(command):
            return await command(ctx)
        else:
            return await asyncio.to_thread(command, ctx)


async def help_command(ctx: Ctx):
    """Replies with the default help message"""
    await ctx.reply(ctx.bot.command_manager.format_help())
