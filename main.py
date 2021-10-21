from datetime import datetime
import discord
from dotenv import load_dotenv
from discord.ext import commands
import shelve
from operator import itemgetter
import RPi.GPIO as GPIO
import pickle as pkl
import asyncio
import os.path


class DBManager:
    def __init__(self, client):
        self.client = client
        self.loop = asyncio.get_event_loop()
        self.timestamp = None
        self.state = None

    async def run(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(5, GPIO.IN)

        with open('detectorstate.pkl', 'rb') as f:
            try:
                self.timestamp, self.state = itemgetter("timestamp", "state")(pkl.load(f))
            except (KeyError, EOFError):
                self.timestamp, self.state = str(datetime.now()), bool(GPIO.input(5))

        for guild in self.client.guilds:
            await send_embed(self.state, self.client, guild, self.timestamp, edit=True)

        @self.client.event
        async def on_message(msg):
            if msg.author != self.client.user:
                with shelve.open('db') as db:
                    check_result = str(msg.guild.id) in db and msg.channel.id == db[str(msg.guild.id)][
                        "selected_channel"]
                if check_result:
                    await send_embed(self.state, self.client, msg.guild, self.timestamp, edit=False)
            await self.client.process_commands(msg)

        GPIO.add_event_detect(5, GPIO.BOTH, callback=lambda x: self.GPIO_callback())

    def GPIO_callback(self):
        asyncio.run_coroutine_threadsafe(self.state_change(GPIO.input(5)), loop=self.loop)

    async def state_change(self, entered):
        self.state = entered
        self.timestamp = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        with open('detectorstate.pkl', 'wb') as f:
            pkl.dump({"timestamp": self.timestamp, "state": self.state}, f)

        for guild in self.client.guilds:
            await send_embed(entered, self.client, guild, self.timestamp, edit=True)


async def send_embed(entered, client, guild, timestamp, edit=False):
    with shelve.open('db', writeback=True) as db:
        if str(guild.id) in db:
            embed = discord.Embed(title="Siedziba koła otwarta od: " if entered else "Siedziba koła zamknięta od: ")
            embed.set_author(name="SKN main bot")
            embed.add_field(name="Data", value=timestamp, inline=False)

            if db[str(guild.id)]["last_message"] is not None:
                channelID, messageID = itemgetter("channel", "message")(db[str(guild.id)]["last_message"])
                try:
                    channel = await client.fetch_channel(channelID)
                    message = await channel.fetch_message(messageID)
                    if edit:
                        await message.edit(embed=embed)
                        return
                    else:
                        await message.delete()
                except discord.errors.NotFound as e:
                    pass
            newMessage = await client.get_channel(db[str(guild.id)]["selected_channel"]).send(embed=embed)
            db[str(guild.id)]["last_message"] = {"channel": newMessage.channel.id, "message": newMessage.id}


if __name__ == '__main__':
    if not os.path.isfile('detectorstate.pkl'):
        with open('detectorstate.pkl', 'wb') as f:
            pkl.dump({"timestamp": None, "state": None}, f)

    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    client = commands.Bot(command_prefix="!")


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
        await DBManager(client).run()


    client.run(TOKEN)
