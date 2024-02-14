import os

from dotenv import load_dotenv
from rtlink import Bot, Comment

load_dotenv()


class SauceGodV3(Bot):
    def __init__(self):
        super().__init__("!", api_url="http://localhost:3758/api/v1/")
        self._rte_options["comment"] = True

    async def _on_login(self):
        print("@{} has logged in to rtwalk".format(self.user.username))
        return await super()._on_login()

    async def _on_comment(self, comment: Comment):
        if comment.content == "ping":
            await comment.reply("Pong! Latency: {:.2f}ms".format(await self.latency()))
        return await super()._on_comment(comment)


bot = SauceGodV3()

if TOKEN := os.getenv("TOKEN"):
    bot.run(TOKEN)
else:
    print("TOKEN environment variable is not set")
