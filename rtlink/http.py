from __future__ import annotations

import logging
from typing import Union, List, Optional, Any
from datetime import datetime

import aiohttp
from aiocache import Cache, BaseCache
from gql import Client, gql
from gql.transport.exceptions import TransportQueryError
from gql.transport.aiohttp import AIOHTTPTransport

from .types import Comment, User, File, Forum
from .errors import TransportQueryError as _TransportQueryError


class HTTPClient:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.cookie_jar = aiohttp.CookieJar()
        self.client = Client(
            transport=AIOHTTPTransport(
                api_url, client_session_args={"cookie_jar": self.cookie_jar}
            ),
            fetch_schema_from_transport=True,
        )
        self.user: Optional[User] = None
        self._cache: BaseCache = Cache()

    async def login(self, email: str, password: str):
        try:
            async with self.client as session:
                res = await session.execute(
                    gql(
                        """
                    mutation($email: String!, $password: String!) {
                        login(email: $email, password: $password) {
                            id
                            username
                            displayName
                            bio
                            pfp {
                                loc
                            }
                            banner  {
                                loc
                            }
                            createdAt
                            modifiedAt
                            admin
                            bot
                        }
                    }
                    """
                    ),
                    variable_values={
                        "email": email,
                        "password": password,
                    },
                )
        except TransportQueryError as e:
            logging.error(e)
            raise _TransportQueryError(e)
        self.user: User = User(
            id=res["login"]["id"],
            username=res["login"]["username"],
            display_name=res["login"]["displayName"],
            created_at=datetime.fromtimestamp(res["login"]["createdAt"]),
            modified_at=datetime.fromtimestamp(res["login"]["modifiedAt"]),
            bio=res["login"]["bio"],
            pfp=File(res["login"]["pfp"]["loc"]) if res["login"]["pfp"] else None,
            banner=File(res["login"]["banner"]["loc"])
            if res["login"]["banner"]
            else None,
            admin=res["login"]["admin"],
            bot=res["login"]["bot"],
        )

    async def fetch_forum(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        ids: Optional[List[str]] = None,
        names: Optional[List[str]] = None,
    ) -> Union[Optional[Forum], List[Forum]]:
        try:
            async with self.client as session:
                if id or name:
                    res = await session.execute(
                        gql(
                            """
                        query($id: String, $name: String) {
                            getForum(id: $id, name: $name) {
                                id
                                name
                                displayName
                                description
                                icon {
                                    loc
                                }
                                banner {
                                    loc
                                }
                                postCount
                                createdAt
                                modifiedAt
                                ownerId
                                moderators
                                bannedMembers
                                locked
                            }
                        }
                        """
                        ),
                        variable_values={
                            "id": id,
                            "name": name,
                        },
                    )
        except TransportQueryError as e:
            logging.error(e)
            raise _TransportQueryError(e)
        if id or name:
            if not res["getForum"]:
                return None
            f = Forum(
                id=res["getForum"]["id"],
                name=res["getForum"]["name"],
                display_name=res["getForum"]["displayName"],
                description=res["getForum"]["description"],
                icon=File(res["getForum"]["icon"]["loc"])
                if res["getForum"]["icon"]
                else None,
                banner=File(res["getForum"]["banner"]["loc"])
                if res["getForum"]["banner"]
                else None,
                post_count=res["getForum"]["postCount"],
                created_at=datetime.fromtimestamp(res["getForum"]["createdAt"]),
                modified_at=datetime.fromtimestamp(res["getForum"]["modifiedAt"]),
                owner_id=res["getForum"]["ownerId"],
                moderators=res["getForum"]["moderators"],
                banned_members=res["getForum"]["bannedMembers"],
                locked=res["getForum"]["locked"],
            )
            await self.cache(id or name, f)
            return f

    async def create_comment(
        self, post_id: str, content: str, reply_to: Optional[str] = None
    ) -> Comment:
        try:
            async with self.client as session:
                res = await session.execute(
                    gql(
                        """
                    mutation($postId: String!, $content: String!, $replyTo: String) {
                        createComment(postId: $postId, content: $content, replyTo: $replyTo) {
                            id
                            content
                            commenterId
                            replyTo
                            postId
                            createdAt
                            modifiedAt
                            replyCount
                            upvotes
                            downvotes
                            upvotedBy
                            downvotedBy
                        }
                    }
                    """
                    ),
                    variable_values={
                        "postId": post_id,
                        "content": content,
                        "replyTo": reply_to,
                    },
                )
        except TransportQueryError as e:
            logging.error(e)
            raise _TransportQueryError(e)

        comment = Comment._populate(res["createComment"])
        comment._client = self
        return comment

    async def logout(self):
        try:
            res = await self.client.execute_async(
                gql(
                    """
                mutation {
                    logout {
                        msg
                    }
                }
                """
                )
            )
        except TransportQueryError as e:
            logging.error(e)
            raise _TransportQueryError(e)
        self.user = None

    async def cache(
        self,
        key: Union[str, List[str]],
        item: Any,
    ):
        if isinstance(key, list) and isinstance(item, list):
            items = zip(key, item)
            await self._cache.multi_set(items)
        else:
            await self._cache.set(key, item)

    async def get_cache(
        self, id: Optional[Union[str, List[str]]], tp: type = Any
    ) -> Optional[Any]:
        if not id:
            return None
        if isinstance(id, list):
            return await self._cache.multi_get(id)
        else:
            return await self._cache.get(id)

    def __del__(self):
        if self.user:
            logging.warn("User not logged out: Session will be hanging")
