# Basic example for a ping bot.

import os

# Only here to resolve import issues, exclude in your app
__import__("sys").path.append("../rtlink/")

from rtlink import Bot, Ctx  # noqa: E402 (ignore this)

# We create a Bot instance passing the RtWalk GQL api url
bot = Bot(api_url="http://localhost:3758/api/v1/")


# Defining command is pretty self explanatory
# Multiple commands with same name not allowed, but aliases are
@bot.command(name="ping", aliases=["latency"])
async def ping_command(ctx: Ctx):
    """Replies with the RTE websocket latency."""
    await ctx.reply(f"Pong! Latency: **{await bot.latency():.2f}ms**")


# Run the bot. Blocks until bot is stopped.
bot.run(os.getenv("TOKEN"))
