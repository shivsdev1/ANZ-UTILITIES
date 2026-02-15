import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from datetime import datetime
import time

# load environment stuff
load_dotenv()


STAFF_ROLES_IDS = 
BOT_COMMANDS_CHANNEL = 
ANNOUNCEMENT_CHANNEL = 
GENERAL_CHANNEL_ID = 
WELCOME_CHANNEL_ID = 
IMAGE_URL = "https://media.discordapp.net/attachments/1468204609620279560/1469633927248482305/image.png?ex=69890780&is=6987b600&hm=77cdb2f5d66fba81c5bdd5b385aef7496b33837595a5c21ea3b9e902c230912e&=&format=webp&quality=lossless&width=1839&height=449"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

start_time = time.time()

# import all the modules
from database import setup_databases
from flight_booking import register_flight_commands
from boarding import register_boarding_commands
from airpoints import register_airpoints_commands
from tickets import register_ticket_commands, setup_ticket_views
from qotd import start_qotd_task
from departure_board import start_departure_board, cleanup_task

def staff(i):
    return any(role.id in STAFF_ROLES_IDS for role in i.user.roles)

def is_bot_commands_channel(i):
    return i.channel_id == BOT_COMMANDS_CHANNEL

@bot.event
async def on_ready():
    setup_databases()
    setup_ticket_views(bot)
    
    # register all commands
    register_flight_commands(bot)
    register_boarding_commands(bot)
    register_airpoints_commands(bot)
    register_ticket_commands(bot)
    
    # start background tasks
    start_qotd_task(bot)
    start_departure_board(bot)
    cleanup_task(bot)
    
    try:
        await bot.tree.sync()
        print(f" Bot ready as {bot.user}")
        print("Systems online")
    except Exception as e:
        print(f"❌ : {e}")

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return

    general = f"<#{GENERAL_CHANNEL_ID}>"
    
    embed = discord.Embed(
        title="Welcome to Air New Zealand!",
        description=f"Kia Ora {member.mention}!\n\nWelcome to Air New Zealand | PTFS family!",
        color=41370
    )

    embed2 = discord.Embed(
        title="New to Air New Zealand | PTFS?",
        description=f"Looking for flights? Check out our departure board!\n\nChat with others in {general}",
        color=41370
    )
    embed2.set_image(url=IMAGE_URL)

    await channel.send(member.mention, embeds=[embed, embed2])

@bot.command()
async def stats(ctx):
    api_latency = round(bot.latency * 1000)
    
    start_msg = time.perf_counter()
    message = await ctx.send("Calculating...")
    end_msg = time.perf_counter()
    msg_latency = round((end_msg - start_msg) * 1000)
    
    current_time = time.time()
    difference = int(round(current_time - start_time))
    uptime = str(datetime.timedelta(seconds=difference))

    embed = discord.Embed(title="Bot Statistics", color=discord.Color.blue())
    embed.add_field(name="📶 API Latency", value=f"{api_latency}ms", inline=True)
    embed.add_field(name="📩 Message Latency", value=f"{msg_latency}ms", inline=True)
    embed.add_field(name="⏳ Uptime", value=uptime, inline=False)

    await message.edit(content=None, embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set!")
        exit(1)
    
    print("[STARTUP] Starting bot...")
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopped")
    except Exception as e:
        print(f"[ERROR] {e}")