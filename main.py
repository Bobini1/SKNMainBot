import discord
from dotenv import load_dotenv
import os
from discord.ext import commands
import shelve
import asyncio
import random
from operator import itemgetter


class DBManager:
    def __init__(self, client):
        self.client = client
        self.timestamp = "19:29"

    async def update_timestamp(self):
        await asyncio.sleep(10)
        return f"{random.randint(1, 24)}:{random.randint(0, 59)}"

    async def run(self):
        for guild in self.client.guilds:
            await send_embed(self.client, guild, self.timestamp)
        while True:
            self.timestamp = await self.update_timestamp()
            for guild in self.client.guilds:
                await send_embed(self.client, guild, self.timestamp)


async def send_embed(client, guild, timestamp):
    with shelve.open('db', writeback=True) as db:
        if str(guild.id) in db:
            if db[str(guild.id)]["last_message"] is not None:
                channel, message = itemgetter("channel", "message")(db[str(guild.id)]["last_message"])
                try:
                    await client.http.delete_message(channel, message)
                except discord.errors.NotFound as e:  # we really do not need to handle this, I promise
                    pass

            embed = discord.Embed(title="Ostatnia wizyta w siedzibie koła")
            embed.set_author(name="SKN main bot")
            embed.add_field(name="Godzina", value=timestamp, inline=False)

            newMessage = await client.get_channel(db[str(guild.id)]["selected_channel"]).send(embed=embed)
            db[str(guild.id)]["last_message"] = {"channel": newMessage.channel.id, "message": newMessage.id}


def main():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    client = commands.Bot(command_prefix="!")

    @client.event
    async def on_message(msg):
        if msg.author != client.user:
            with shelve.open('db') as db:
                check_result = str(msg.guild.id) in db and msg.channel.id == db[str(msg.guild.id)]["selected_channel"]
            if check_result:
                await send_embed(client, msg.guild, "test")
        await client.process_commands(msg)

    @client.command(name="setchannel")
    async def set_channel(ctx, arg):
        with shelve.open('db', writeback=True) as db:
            if str(ctx.guild.id) in db:
                db[str(ctx.guild.id)]["selected_channel"] = client.get_channel(int(arg))
            else:
                db[str(ctx.guild.id)] = {"last_message": None, "selected_channel": client.get_channel(int(arg)).id}

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')
        manager = DBManager(client)
        asyncio.create_task(manager.run())

    client.run(TOKEN)


if __name__ == '__main__':
    main()
