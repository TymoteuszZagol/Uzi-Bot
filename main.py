import os
import discord

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}")


@bot.event
async def on_message(message):
    # Bot nie odpowiada sam sobie
    if message.author == bot.user:
        return

    await message.channel.send(f"echo: {message.content}")


if not TOKEN:
    raise ValueError("Nie znaleziono zmiennej DISCORD_TOKEN!")

bot.run(TOKEN)
