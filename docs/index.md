# RtLink

RtLink is a wrapper around the [RtWalk](https://github.com/midatindex0/rtwalk) graphql API. Use it to make bots or just interact with the API.

RtWalk API documentation can be found [here](https://github.com/midatindex0/rtwalk).

# Example Codes

Create a bot:

```py
import os

from rtlink import Bot

bot = Bot(api_url="http://localhost:3758")


@bot.on_event("login")
async def login_event():
    print(f"Bot logged in with username: {bot.user.username}")
    print(await bot.fetch_forum("dreamh"))


if TOKEN := os.getenv("TOKEN"):
    bot.run(TOKEN)
else:
    print("TOKEN environment variable is not set")


```

## Installation

Get the stable release using `pip`

```
pip install rtlink
```

Install from github for the latest version:

```
pip install git+https://github.com/midatindex0/rtlink.git
```

