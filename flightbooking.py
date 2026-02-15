import discord
from discord import app_commands
import random
import string
import re
from datetime import datetime
import sqlite3

from database import bc, bookings_db, booking_lock, FLIGHTS

BOT_COMMANDS_CHANNEL = 1468449739388227695
CABINS = ["Economy", "Premium Economy", "Business", "First Class"]

def gen_code():
    with booking_lock:
        for _ in range(10):
            code = "BK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            try:
                bc.execute("SELECT code FROM bookings WHERE code=?", (code,))
                if not bc.fetchone():
                    return code
            except:
                continue
        raise Exception("Failed to generate code")

def valid_roblox(x):
    return bool(re.fullmatch(r"[A-Za-z0-9_]{3,20}", x))

def valid_did(x):
    return x.isdigit() and 17 <= len(x) <= 19

def is_bot_commands_channel(i):
    return i.channel_id == BOT_COMMANDS_CHANNEL

class FlightView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        options = [
            discord.SelectOption(label=f"{k} | {v[0]} | {v[1]} | {v[2]}")
            for k, v in FLIGHTS.items()
        ]

        select = discord.ui.Select(placeholder="Choose flight", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        flight = interaction.data["values"][0].split(" | ")[0]
        await interaction.response.send_message(
            "Who is this booking for?",
            view=WhoView(flight),
            ephemeral=True
        )

class WhoView(discord.ui.View):
    def __init__(self, flight):
        super().__init__(timeout=300)
        self.flight = flight

    @discord.ui.button(label="Myself", style=discord.ButtonStyle.primary)
    async def myself(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyselfModal(self.flight))

    @discord.ui.button(label="Someone Else", style=discord.ButtonStyle.secondary)
    async def other(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OtherModal(self.flight))

class MyselfModal(discord.ui.Modal, title="Booking for Myself"):
    roblox = discord.ui.TextInput(label="Your Roblox Username", max_length=20)

    def __init__(self, flight):
        super().__init__()
        self.flight = flight

    async def on_submit(self, interaction: discord.Interaction):
        if not valid_roblox(self.roblox.value):
            return await interaction.response.send_message("❌ Invalid Roblox username", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Select cabin class:",
            view=CabinView(self.flight, "Myself", self.roblox.value, str(interaction.user.id), interaction.user.id),
            ephemeral=True
        )

class OtherModal(discord.ui.Modal, title="Booking for Someone Else"):
    discord_id = discord.ui.TextInput(label="Discord User ID", placeholder="18-digit ID")
    roblox = discord.ui.TextInput(label="Roblox Username", max_length=20)

    def __init__(self, flight):
        super().__init__()
        self.flight = flight

    async def on_submit(self, interaction: discord.Interaction):
        if not valid_did(self.discord_id.value):
            return await interaction.response.send_message("❌ Invalid Discord ID", ephemeral=True)
        
        if not valid_roblox(self.roblox.value):
            return await interaction.response.send_message("❌ Invalid Roblox username", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Select cabin class:",
            view=CabinView(self.flight, "Other", self.roblox.value, self.discord_id.value, interaction.user.id),
            ephemeral=True
        )

class CabinView(discord.ui.View):
    def __init__(self, flight, who, roblox, did, booker):
        super().__init__(timeout=300)
        self.flight = flight
        self.who = who
        self.roblox = roblox
        self.did = did
        self.booker = booker

        for cabin in CABINS:
            self.add_item(CabinButton(cabin, self))

class CabinButton(discord.ui.Button):
    def __init__(self, cabin, parent):
        super().__init__(label=cabin, style=discord.ButtonStyle.success)
        self.cabin = cabin
        self.p = parent

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.p.booker:
            return await interaction.response.send_message("❌ Not your booking", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            code = gen_code()
            route, aircraft, time = FLIGHTS[self.p.flight]

            with booking_lock:
                bc.execute(
                    "INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (code, self.p.flight, route, aircraft, time, self.cabin,
                    self.p.who, self.p.roblox, self.p.did, self.p.booker)
                )
                bookings_db.commit()
        except sqlite3.IntegrityError:
            return await interaction.followup.send("❌ Code collision. Try again", ephemeral=True)
        except Exception as e:
            print(f"[BOOKING ERROR] {e}")
            return await interaction.followup.send("❌ Database error", ephemeral=True)

        embed = discord.Embed(title="✈️ Booking Confirmed", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="Flight", value=f"**{self.p.flight}**", inline=False)
        embed.add_field(name="Route", value=route, inline=False)
        embed.add_field(name="Aircraft", value=aircraft, inline=False)
        embed.add_field(name="Departure Time", value=time, inline=False)
        embed.add_field(name="Cabin Class", value=f"**{self.cabin}**", inline=False)
        embed.add_field(name="Booking Code", value=f"**{code}**", inline=False)
        embed.add_field(name="Booked For", value=self.p.roblox, inline=True)
        embed.set_footer(text="Thank you for booking!")

        await interaction.followup.send(embed=embed, ephemeral=True)

        
        try:
            from main import bot
            user = await bot.fetch_user(self.p.booker)
            dm_embed = embed.copy()
            dm_embed.title = "✈️ Your Booking is Confirmed!"
            await user.send(embed=dm_embed)
        except:
            pass

def register_flight_commands(bot):
    @bot.tree.command(name="bookflight", description="Book a flight")
    @app_commands.check(is_bot_commands_channel)
    async def bookflight(interaction: discord.Interaction):
        await interaction.response.send_message("Select a flight:", view=FlightView(), ephemeral=True)

    @bookflight.error
    async def bookflight_err(interaction: discord.Interaction, error):
        await interaction.response.send_message("⚠️ Use bot commands channel only", ephemeral=True)