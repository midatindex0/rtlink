# Basic example to shocase events
# Check the event documentation for all events and their uses

import os

# Only here to resolve import issues, exclude in your app
__import__("sys").path.append("../rtlink/")


from rtlink import Bot  # noqa: E402 (ignore this)
from rtlink.types import Comment  # noqa: E402 (ignore this)

# We create a Bot instance passing the RtWalk GQL api api_url
bot = Bot(api_url="http://localhost:3758/api/v1/")


@bot.on_event("login")
async def login_event():
    # This event is fired just after the bot logs into rtwalk.
    # There can be multiple listeners which will be run concurrently.
    # Callbacks can also be non-coro in which case they are called in asyncio.to_thead.
    print("Do something like database initialization here")


@bot.on_event("comment")
async def new_comment(comment: Comment):
    # Event is fired when someone comments on a post.
    if comment.content == "ping":
        await comment.reply("Pong!")


@bot.on_event("logout")
async def logout_event():
    # Called *after* bot has logged out
    print("Close connections here and free up stuff")


# Run the bot. Blocks until bot is stopped.
bot.run(os.getenv("TOKEN"))
