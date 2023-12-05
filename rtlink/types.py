from bson import ObjectId
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


class File:
    def __init__(self, loc: str):
        if loc:
            self.loc = loc


@dataclass
class User:
    id: ObjectId
    username: str
    display_name: str
    created_at: datetime
    modified_at: datetime
    bio: Optional[File] = None
    pfp: Optional[File] = None
    banner: Optional[str] = None
    admin: bool = False
    bot: bool = False
