from __future__ import annotations

import asyncio
import logging
from typing import ClassVar
from bson import ObjectId
from datetime import datetime

import aiohttp
from gql import Client, gql
from gql.transport.exceptions import TransportQueryError
from gql.transport.aiohttp import AIOHTTPTransport

from .types import User, File


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
        self.user = None

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
            return
        self.user = User(
            id=ObjectId(res["login"]["id"]),
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
        self.user = None

    def __del__(self):
        if self.user:
            logging.warn("User not logged out: Session will be hanging")
