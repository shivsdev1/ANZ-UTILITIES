import discord
from discord.ext import tasks
from datetime import datetime, timezone, timedelta

from database import fc, flights_db, bc, flights_lock, FLIGHTS

DEPARTURE_BOARD_CHANNEL = 1469359444692570122

departure_board_message_id = None

async def send_departure_board(bot):
    global departure_board_message_id
    
    try:
        channel = bot.get_channel(DEPARTURE_BOARD_CHANNEL)
        if not channel:
            return
        
        now_utc = datetime.now(timezone.utc)
        
        fc.execute("""
            SELECT flight_code, route, aircraft, departure_time, departure_date 
            FROM flights 
            ORDER BY departure_date, departure_time
        """)
        flights = fc.fetchall()
        
        if not flights:
            board_text = "```\n📋 No scheduled flights\n```"
        else:
            board_text = "```\n"
            board_text += "FLIGHT    DEST         DATE/TIME         STATUS      PAX\n"
            board_text += "=" * 65 + "\n"
            
            for flight_code, route, aircraft, dep_time, dep_date in flights:
                if not dep_date:
                    continue
                    
                dest = route.split("->")[1] if "->" in route else route
                dest = dest[:12].ljust(12)
                
                bc.execute("SELECT COUNT(*) FROM bookings WHERE flight=?", (flight_code,))
                pax_count = bc.fetchone()[0]
                
                try:
                    dep_datetime = datetime.strptime(
                        f"{dep_date} {dep_time}", 
                        "%d/%m/%Y %H:%M"
                    ).replace(tzinfo=timezone.utc)
                    
                    time_diff = (dep_datetime - now_utc).total_seconds() / 60
                    
                    if time_diff < -30:
                        status = "DEPARTED"
                    elif time_diff < 0:
                        status = "DEPARTING"
                    elif time_diff < 30:
                        status = "BOARDING"
                    elif time_diff < 120:
                        status = "CHECK-IN"
                    else:
                        status = "SCHEDULED"
                    
                    date_time_str = f"{dep_date} {dep_time}"
                    
                except:
                    date_time_str = f"{dep_date} {dep_time}"
                    status = "SCHEDULED"
                
                pax_str = f"{pax_count}/15"
                board_text += f"{flight_code:<9} {dest} {date_time_str:<17} {status:<11} {pax_str}\n"
            
            board_text += "```"
        
        embed = discord.Embed(
            title="🛫 AIR NEW ZEALAND DEPARTURES",
            description=f"**✈️ LIVE DEPARTURE BOARD**\n{board_text}",
            color=discord.Color.blue(),
            timestamp=now_utc
        )
        embed.set_footer(text="All times UTC • Updates every 5 min")
        
        if departure_board_message_id:
            try:
                message = await channel.fetch_message(departure_board_message_id)
                await message.edit(embed=embed)
            except discord.NotFound:
                msg = await channel.send(embed=embed)
                departure_board_message_id = msg.id
        else:
            msg = await channel.send(embed=embed)
            departure_board_message_id = msg.id
        
    except Exception as e:
        print(f"[DEPARTURE BOARD ERROR] {e}")

@tasks.loop(minutes=2)
async def update_departure_board(bot):
    await send_departure_board(bot)

@update_departure_board.before_loop
async def before_update(bot):
    await bot.wait_until_ready()

@tasks.loop(minutes=10)
async def cleanup_departed_flights():
    try:
        now_utc = datetime.now(timezone.utc)
        
        fc.execute("SELECT flight_code, departure_date, departure_time FROM flights")
        flights = fc.fetchall()
        
        deleted_count = 0
        for flight_code, dep_date, dep_time in flights:
            if not dep_date:
                continue
                
            try:
                dep_dt = datetime.strptime(
                    f"{dep_date} {dep_time}",
                    "%d/%m/%Y %H:%M"
                ).replace(tzinfo=timezone.utc)
                
                if (now_utc - dep_dt).total_seconds() > 7200:  # 2 hours
                    with flights_lock:
                        fc.execute("DELETE FROM flights WHERE flight_code=?", (flight_code,))
                        flights_db.commit()
                    
                    if flight_code in FLIGHTS:
                        del FLIGHTS[flight_code]
                    
                    deleted_count += 1
                    print(f"[CLEANUP] Deleted {flight_code}")
                    
            except:
                continue
        
        if deleted_count > 0:
            print(f"[CLEANUP] Removed {deleted_count} flights")
            
    except Exception as e:
        print(f"[CLEANUP ERROR] {e}")

def start_departure_board(bot):
    update_departure_board.start(bot)
    send_departure_board(bot)

def cleanup_task(bot):
    cleanup_departed_flights.start()