from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime


class File:
    def __init__(self, loc: str):
        if loc:
            self.loc = loc


@dataclass
class User:
    id: str
    username: str
    display_name: str
    created_at: datetime
    modified_at: datetime
    bio: Optional[str]
    pfp: Optional[File]
    banner: Optional[File]
    admin: bool
    bot: bool

    @property
    def _client(self):
        return self.__client

    @_client.setter
    def _client(self, v):
        self.__client = v

    @classmethod
    def _populate(cls, res):
        return cls(
            id=res.get("id"),
            username=res.get("username"),
            display_name=res.get("displayName"),
            created_at=res.get("createdAt"),
            modified_at=res.get("modifiedAt"),
            bio=res.get("bio"),
            pfp=File(res.get("pfp")) if res.get("pfp") else None,
            banner=File(res.get("banner")) if res.get("banner") else None,
            admin=res.get("admin"),
            bot=res.get("bot"),
        )


@dataclass
class Forum:
    id: str
    name: str
    display_name: str
    description: Optional[str]
    icon: Optional[File]
    banner: Optional[File]
    post_count: int
    created_at: int
    modified_at: int
    owner_id: str
    moderators: List[str]
    banned_members: List[str]
    locked: bool


@dataclass
class Comment:
    id: str
    content: str
    commenter_id: str
    reply_to: Optional[str]
    post_id: str
    forum_id: str
    commenter: User
    created_at: int
    modified_at: int
    reply_count: int
    upvotes: int
    downvotes: int
    upvoted_by: List[str]
    downvoted_by: List[str]

    @property
    def _client(self):
        return self.__client

    @_client.setter
    def _client(self, v):
        self.__client = v

    @classmethod
    def _populate(cls, res):
        return cls(
            id=res.get("id"),
            content=res.get("content"),
            commenter_id=res.get("commenterId"),
            reply_to=res.get("replyTo"),
            post_id=res.get("postId"),
            forum_id=res.get("forumId"),
            commenter=User._populate(res.get("commenter")),
            created_at=res.get("createdAt"),
            modified_at=res.get("modifiedAt"),
            reply_count=res.get("replyCount"),
            upvotes=res.get("upvotes"),
            downvotes=res.get("downvotes"),
            upvoted_by=res.get("upvotedBy"),
            downvoted_by=res.get("downvotedBy"),
        )

    async def reply(self, content: str) -> "Comment":
        return await self._client.create_comment(self.post_id, content, self.id)
