from dotenv import load_dotenv

load_dotenv()
import os

from rtlink import Bot


bot = Bot(api_url="http://localhost:8000/api/v1")


@bot.on_event("login")
async def login_event():
    print(f"Bot logged in with username: {bot.user.username}")


bot.run(os.getenv("TOKEN"))
