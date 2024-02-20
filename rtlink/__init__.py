"""
RTWalk API wrapper
"""

__title__ = "rtlink"
__author__ = "midfirefly"
__license__ = "MIT"
__version__ = "0.1.0"

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .http import HTTPClient as RtWalk
from .bot import Bot
from .types import User, Forum, File, Comment
from .commands import Ctx
