from datetime import datetime
import discord
from dotenv import load_dotenv
import os
from discord.ext import commands
import shelve
from operator import itemgetter
import RPi.GPIO as GPIO
from functools import partial
import pickle as pkl


class DBManager:
    def __init__(self, client):
        self.client = client

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(5, GPIO.IN)

        with open('detectorstate.pkl', 'rb') as f:
            try:
                self.timestamp, self.state = itemgetter("timestamp", "state")(pkl.load(f))
            except KeyError:
                self.timestamp, self.state = str(datetime.now()), bool(GPIO.input(5))

        for guild in self.client.guilds:
            await send_embed(self.state, self.client, guild, self.timestamp, edit=True)

        @client.event
        async def on_message(msg):
            if msg.author != client.user:
                with shelve.open('db') as db:
                    check_result = str(msg.guild.id) in db and msg.channel.id == db[str(msg.guild.id)][
                        "selected_channel"]
                if check_result:
                    await send_embed(self.state, self.client, msg.guild, self.timestamp, edit=False)
            await client.process_commands(msg)

        GPIO.add_event_detect(5, GPIO.RISING, callback=partial(self.state_change, True))
        GPIO.add_event_detect(5, GPIO.FALLING, callback=partial(self.state_change, False))

    def state_change(self, entered):
        self.state = entered
        self.timestamp = str(datetime.now())

        with open('detectorstate.pkl', 'wb') as f:
            pkl.dump({"timestamp": self.timestamp, "state": self.state}, f)

        for guild in self.client.guilds:
            await send_embed(entered, self.client, guild, self.timestamp, edit=True)


async def send_embed(entered, client, guild, timestamp, edit=False):
    with shelve.open('db', writeback=True) as db:
        if str(guild.id) in db:

            if entered is None:
                embed = discord.Embed(title="Unknown state")
            elif entered:
                embed = discord.Embed(title="Siedziba koła otwarta od: ")
            else:
                embed = discord.Embed(title="Siedziba koła zamknięta od: ")

            embed.set_author(name="SKN main bot")
            embed.add_field(name="Data", value=timestamp, inline=False)

            if db[str(guild.id)]["last_message"] is not None:
                channelID, messageID = itemgetter("channel", "message")(db[str(guild.id)]["last_message"])

                if edit:
                    try:
                        channel = await client.fetch_channel(channelID)
                        message = await channel.fetch_message(messageID)
                        await message.edit(embed=embed)
                        return
                    except discord.errors.NotFound as e:
                        pass
                else:
                    try:
                        channel = await client.fetch_channel(channelID)
                        message = await channel.fetch_message(messageID)
                        await message.delete()
                    except discord.errors.NotFound as e:  # we really do not need to handle this, I promise
                        pass
            newMessage = await client.get_channel(db[str(guild.id)]["selected_channel"]).send(embed=embed)
            db[str(guild.id)]["last_message"] = {"channel": newMessage.channel.id, "message": newMessage.id}


def main():
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
        DBManager(client)

    client.run(TOKEN)


if __name__ == '__main__':
    main()
