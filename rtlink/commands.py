from __future__ import annotations
import argparse
import shlex
import logging
import asyncio
import inspect

from typing import (
    TYPE_CHECKING,
    Annotated,
    List,
    Optional,
    TypeVar,
    Coroutine,
    Any,
    Callable,
    Dict,
    Union,
    Sequence,
)
import typing

from .types import Comment

if TYPE_CHECKING:
    from .bot import Bot

T = TypeVar("T")
Coro = Coroutine[Any, Any, T]
CoroT = Callable[..., Coro[Any]]
logger = logging.getLogger(__name__)


# Types that define hw to parse arguments
class Flag:
    def __init__(self, _v: bool):
        self._v = _v

    def __bool__(self):
        return self._v


class Ctx:
    def __init__(self, bot: Bot, comment: Comment):
        self.bot = bot
        self.comment = comment

    async def reply(self, content: str) -> Comment:
        return await self.comment.reply(content)


allowed_annotations = [
    inspect._empty,
    Ctx,
    "Ctx",
    str,
    int,
    bool,
    Flag,
]


class Command:
    def __init__(self, fn, name: Optional[str] = None, aliases: List[str] = []):
        self.name = name or fn.__name__
        self.aliases = aliases
        self.fn = fn


class JoinAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        if values and isinstance(values, list):
            values = " ".join(values)  # type: ignore
            setattr(namespace, self.dest, values)
        if getattr(namespace, self.dest):
            return
        else:
            raise argparse.ArgumentError(
                self, "{} is a required argument that is missing".format(self.dest)
            )


class CommandManager(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(exit_on_error=False, *args, **kwargs)

    def _set_bot(self, bot: Bot):
        self.signatures: Dict[str, inspect.Signature] = {}
        self.commands: Dict[str, Union[CoroT, Callable]] = {}
        self.subparsers = self.add_subparsers(dest="command")
        self.bot = bot

    def add_command(self, command: Command):
        # First parse the command to get arguments
        sig = inspect.signature(command.fn)
        haskeywordonly = False
        haspositionalorkeyword = False
        for param in sig.parameters.values():
            if (
                typing.get_origin(param.annotation) is Annotated
                and typing.get_args(param.annotation)[0] in allowed_annotations
                and isinstance(typing.get_args(param.annotation)[1], str)
            ):
                continue
            if param.annotation not in allowed_annotations:
                logger.error(
                    'Unknown argument ({}) annotation "{}" for command: "{}". Skipping.'.format(
                        param.name,
                        param.annotation,
                        command.name,
                    )
                )
                return
            if param.kind == inspect._ParameterKind.KEYWORD_ONLY:
                if haskeywordonly:
                    logger.error(
                        'Command "{}" can only have 1 keyword only argument. Skipping.'.format(
                            command.name
                        )
                    )
                    return
                haskeywordonly = True
            if param.kind == inspect._ParameterKind.POSITIONAL_OR_KEYWORD:
                haspositionalorkeyword = True
        if not haspositionalorkeyword:
            logger.error(
                "Command {} must have atlest 1 argument Ctx. Skipping.\n\t{}\n".format(
                    command.name,
                    sig,
                )
            )

        self.commands[command.name] = command.fn
        self.signatures[command.name] = sig
        try:
            parser = self.subparsers.add_parser(
                command.name,
                help=command.fn.__doc__,
                aliases=command.aliases,
            )
            self.add_args(parser, sig, command.name)
            for alias in command.aliases:
                self.signatures[alias] = sig
                self.commands[alias] = command.fn
        except argparse.ArgumentError:
            logger.warn('Overwriting command "{}"'.format(command.name))
            self.remove_command(command.name)
            for alias in command.aliases:
                self.remove_command(alias)
                self.commands[alias] = command.fn
                self.signatures[alias] = sig
            parser = self.subparsers.add_parser(
                command.name,
                help=command.fn.__doc__,
                aliases=command.aliases,
            )
            self.add_args(parser, sig, command.name)

    def add_args(self, parser, sig: inspect.Signature, command_name):
        for i, param in enumerate(sig.parameters.values()):
            if i == 0:
                continue
            default = None if param.default is inspect._empty else param.default
            nargs = "?" if default else 1
            if (
                self.stripped_annotation(param.annotation) is inspect._empty
                or self.stripped_annotation(param.annotation) is str
            ):
                if param.kind == inspect._ParameterKind.KEYWORD_ONLY:
                    parser.add_argument(
                        param.name,
                        type=str,
                        default=default,
                        nargs="...",
                        action=JoinAction,
                    )
                    continue
                parser.add_argument(param.name, type=str, default=default, nargs=nargs)
            elif self.stripped_annotation(param.annotation) is int:
                parser.add_argument(param.name, type=int, default=default, nargs=nargs)
            elif self.stripped_annotation(param.annotation) is float:
                parser.add_argument(
                    param.name, type=float, default=default, nargs=nargs
                )
            elif self.stripped_annotation(param.annotation) is bool:
                if len(param.name) > 1:
                    parser.add_argument(
                        "--" + param.name,
                        default=default or False,
                        action="store_true",
                    )
                else:
                    parser.add_argument(
                        "-" + param.name,
                        default=default or False,
                        action="store_true",
                    )
            elif self.stripped_annotation(param.annotation) is Flag:
                if len(param.name) > 1:
                    parser.add_argument(
                        "--" + param.name,
                        "-" + param.name[0],
                        default=default or False,
                        action="store_true",
                    )
                else:
                    parser.add_argument(
                        "-" + param.name,
                        default=default or False,
                        action="store_true",
                    )
            else:
                logger.warn(
                    'Unknown annotation "{}" in command "{}". Substituting with "str".'.format(
                        param.annotation, command_name
                    )
                )
                if param.kind == inspect._ParameterKind.KEYWORD_ONLY:
                    parser.add_argument(
                        param.name,
                        type=str,
                        default=default,
                        nargs="+",
                        action=JoinAction,
                    )
                    continue
                parser.add_argument(param.name, type=str, default=default, nargs=nargs)

    @staticmethod
    def stripped_annotation(annotation: Any):
        if typing.get_origin(annotation) is Annotated:
            return typing.get_args(annotation)[0]
        return annotation

    async def try_process_command(self, comment: Comment) -> Any:
        prefix = f"@{self.bot.user.username}"
        if comment.content.startswith(prefix):
            to_parse = comment.content[len(prefix) :]
            try:
                namespace = self.parse_args(shlex.split(to_parse))
            except argparse.ArgumentError as e:
                logger.warn(e)
                await self.bot.dispatch("error", e)  # TODO: use correct rtwalk error
                return
            logger.debug(f"Command namespace: {namespace}")
            if command := self.commands.get(namespace.command):
                try:
                    return await self._run(command, namespace, comment)
                except Exception as e:
                    logger.exception(e)
                    await self.bot.dispatch("command_error", e)

    async def _run(
        self,
        command: Union[CoroT, Callable],
        namespace: argparse.Namespace,
        comment: Comment,
    ) -> Any:
        ctx = Ctx(self.bot, comment)
        args = namespace.__dict__
        command_name = args.pop("command")
        binds = self.signatures[command_name].bind(ctx, **args)
        if asyncio.iscoroutinefunction(command):
            return await command(*binds.args, **binds.kwargs)
        else:
            return await asyncio.to_thread(command, *binds.args, **binds.kwargs)

    def remove_command(self, name):
        for action in self._actions:
            if (
                isinstance(action, argparse._SubParsersAction)
                and action.dest == "command"
            ):
                del action.choices[name]


async def help_command(ctx: Ctx):
    """Replies with the default help message"""
    await ctx.reply(ctx.bot.command_manager.format_help())
