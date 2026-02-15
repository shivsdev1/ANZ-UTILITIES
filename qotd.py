import discord
from discord.ext import tasks
import random
from datetime import datetime, timedelta
import asyncio
import pytz

QOTD_CHANNEL = 1378322223965929643
DISCUSSION_CHANNEL = 1378321677578014770

QOTD_QUESTIONS = [
    "What's your favorite food and why?",
    "If you could visit any place in the world, where would it be?",
    "What's your favorite movie or TV show?",
    "If you could have any superpower, what would it be?",
    "What's your favorite hobby?",
    "If you could meet any historical figure, who?",
    "What's the best book you've ever read?",
    "What's your favorite season?",
    "If you could learn any skill instantly, what?",
    "What's your favorite music type?",
    "If you could have dinner with any fictional character?",
    "What's your favorite childhood memory?",
    "Time travel - past or future?",
    "What's your dream job?",
    "Most adventurous thing you've done?",
    "If you could speak any language fluently?",
    "Favorite animal?",
    "If you could invent something?",
    "Favorite weekend activity?",
    "If you could live in any fictional world?",
]

qotd_task = None

@tasks.loop(hours=24)
async def send_qotd(bot):
    try:
        channel = bot.get_channel(QOTD_CHANNEL)
        if not channel:
            return
        
        question = random.choice(QOTD_QUESTIONS)
        
        embed = discord.Embed(
            title="📝 Question of the Day",
            description=question,
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="💬 Discuss",
            value=f"Share thoughts in <#{DISCUSSION_CHANNEL}>!",
            inline=False
        )
        embed.set_footer(text="Daily QOTD")
        
        await channel.send(content="<@&QOTD>", embed=embed)
        print(f"[QOTD] Sent at 5PM GMT")
        
    except Exception as e:
        print(f"[QOTD ERROR] {e}")

@send_qotd.before_loop
async def before_qotd(bot):
    await bot.wait_until_ready()
    
    gmt = pytz.timezone('GMT')
    now = datetime.now(gmt)
    
    target_time = now.replace(hour=17, minute=0, second=0, microsecond=0)
    
    if now >= target_time:
        target_time += timedelta(days=1)
    
    wait_seconds = (target_time - now).total_seconds()
    
    print(f"[QOTD] Waiting {wait_seconds/3600:.2f} hours until 5PM GMT")
    await asyncio.sleep(wait_seconds)

def start_qotd_task(bot):
    global qotd_task
    qotd_task = send_qotd
    send_qotd.start(bot)