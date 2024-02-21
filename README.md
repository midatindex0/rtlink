Rtlink is the API wrapper for [Rtwalk](https://github.com/midatindex0/rtwalk).

## Basic Usage
```py
from rtlink import Bot, Ctx

bot = Bot(api_url="https://rtwalk.dreamh.net/api/v1/")

@bot.command()
async def say_hello(ctx: Ctx, *, your_name):
    await ctx.reply(f"Hello! {your_name}")

bot.run('YOUR BOT TOKEN')
```

More examples can be found [here](./examples/)
