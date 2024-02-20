import os

from dotenv import load_dotenv
from rtlink import Bot, Ctx
from rtlink.vc import VcClient

from aiortc.contrib.media import MediaPlayer

load_dotenv()


bot = Bot(api_url="http://localhost:3758/api/v1/")

player = MediaPlayer("./m.m4a")
vc = VcClient(
    url="ws://localhost:3001/ws?user=saucegod",
    player=player,
)


@bot.on_event("login")
async def login():
    await vc.run()


@bot.on_event("logout")
async def logout():
    await vc.close()


@bot.command(name="ping", aliases=["latency"])
async def ping_command(ctx: Ctx):
    """Replies with the RTE websocket latency."""
    await ctx.reply(f"Pong! Latency: **{await bot.latency():.2f}ms**")


if TOKEN := os.getenv("TOKEN"):
    bot.run(TOKEN)
else:
    print("TOKEN environment variable is not set")
