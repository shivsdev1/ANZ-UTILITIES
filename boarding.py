import discord
from discord import app_commands
from datetime import datetime, timezone

from database import ac, announcements_db, announcements_lock

STAFF_ROLES_IDS = {1468230337900580887}
BOT_COMMANDS_CHANNEL = 1468449739388227695
ANNOUNCEMENT_CHANNEL = 1468436846123155496

def staff(i):
    return any(role.id in STAFF_ROLES_IDS for role in i.user.roles)

def is_bot_commands_channel(i):
    return i.channel_id == BOT_COMMANDS_CHANNEL

class BoardingModal1(discord.ui.Modal, title="Boarding Announcement (1/3)"):
    flight = discord.ui.TextInput(label="Flight Number", placeholder="SQ-2148")
    dep_airport = discord.ui.TextInput(label="Departure Airport", placeholder="IPPH")
    dep_time = discord.ui.TextInput(label="Departure Time (HH:MM UTC)", placeholder="16:15")
    dep_terminal = discord.ui.TextInput(label="Terminal", placeholder="T2")
    dep_gate = discord.ui.TextInput(label="Gate", placeholder="A5")

    async def on_submit(self, interaction: discord.Interaction):
        temp_data = {
            'flight': self.flight.value,
            'dep_airport': self.dep_airport.value,
            'dep_time': self.dep_time.value,
            'dep_terminal': self.dep_terminal.value,
            'dep_gate': self.dep_gate.value
        }
        
        await interaction.response.defer(ephemeral=True)
        
        modal2 = BoardingModal2(
            temp_data['flight'], temp_data['dep_airport'], temp_data['dep_time'],
            temp_data['dep_terminal'], temp_data['dep_gate']
        )
        
        await interaction.followup.send("Continue:", view=ContinueModalView(modal2), ephemeral=True)

class ContinueModalView(discord.ui.View):
    def __init__(self, modal):
        super().__init__(timeout=300)
        self.modal = modal
    
    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary)
    async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)

class BoardingModal2(discord.ui.Modal, title="Boarding Announcement (2/3)"):
    arr_airport = discord.ui.TextInput(label="Arrival Airport", placeholder="WSSS")
    arr_time = discord.ui.TextInput(label="Arrival Time (HH:MM UTC)", placeholder="18:45")
    arr_gate = discord.ui.TextInput(label="Arrival Gate", placeholder="B12")
    date = discord.ui.TextInput(label="Date", placeholder="17 Jan 2026")

    def __init__(self, flight, dep_airport, dep_time, dep_terminal, dep_gate):
        super().__init__()
        self.flight = flight
        self.dep_airport = dep_airport
        self.dep_time = dep_time
        self.dep_terminal = dep_terminal
        self.dep_gate = dep_gate

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        modal3 = BoardingModal3(
            self.flight, self.dep_airport, self.dep_time, self.dep_terminal, self.dep_gate,
            self.arr_airport.value, self.arr_time.value, self.arr_gate.value, self.date.value
        )
        
        await interaction.followup.send("Final step:", view=ContinueModalView(modal3), ephemeral=True)

class BoardingModal3(discord.ui.Modal, title="Boarding Announcement (3/3)"):
    meal = discord.ui.TextInput(label="Meal Service", placeholder="Yes / No")
    host = discord.ui.TextInput(label="Host", placeholder="@crew")
    status = discord.ui.TextInput(label="Status", placeholder="On Time / Boarding / Delayed")
    alerts = discord.ui.TextInput(label="Alerts (optional)", required=False, style=discord.TextStyle.paragraph)
    server = discord.ui.TextInput(label="Server Link (optional)", required=False)

    def __init__(self, flight, dep_airport, dep_time, dep_terminal, dep_gate,
                arr_airport, arr_time, arr_gate, date):
        super().__init__()
        self.flight = flight
        self.dep_airport = dep_airport
        self.dep_time = dep_time
        self.dep_terminal = dep_terminal
        self.dep_gate = dep_gate
        self.arr_airport = arr_airport
        self.arr_time = arr_time
        self.arr_gate = arr_gate
        self.date = date

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from main import bot
            
            dep_dt = datetime.strptime(self.dep_time, "%H:%M").replace(
                year=datetime.utcnow().year, month=datetime.utcnow().month,
                day=datetime.utcnow().day, tzinfo=timezone.utc
            )
            arr_dt = datetime.strptime(self.arr_time, "%H:%M").replace(
                year=datetime.utcnow().year, month=datetime.utcnow().month,
                day=datetime.utcnow().day, tzinfo=timezone.utc
            )
            dep_ts = f"<t:{int(dep_dt.timestamp())}:t>"
            arr_ts = f"<t:{int(arr_dt.timestamp())}:t>"

            embed = discord.Embed(
                title=f"✈️ Boarding Announcement — {self.flight}",
                color=discord.Color.blue() if "on time" in self.status.value.lower() else discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="📅 Date", value=self.date, inline=False)
            embed.add_field(
                name="🛫 Departure",
                value=f"**Airport:** {self.dep_airport}\n**Time:** {dep_ts}\n**Terminal:** {self.dep_terminal}\n**Gate:** {self.dep_gate}",
                inline=True
            )
            embed.add_field(
                name="🛬 Arrival",
                value=f"**Airport:** {self.arr_airport}\n**Time:** {arr_ts}\n**Gate:** {self.arr_gate}",
                inline=True
            )
            embed.add_field(name="🍽️ Meal", value=self.meal.value, inline=True)
            embed.add_field(name="👨‍✈️ Host", value=self.host.value, inline=True)
            embed.add_field(name="📊 Status", value=f"**{self.status.value}**", inline=True)
            
            if self.alerts.value:
                embed.add_field(name="⚠️ Alerts", value=self.alerts.value, inline=False)
            if self.server.value:
                embed.add_field(name="🔗 Server Link", value=self.server.value, inline=False)
            
            embed.set_footer(text="Times auto-adjust to viewer timezone")

            channel = bot.get_channel(ANNOUNCEMENT_CHANNEL)
            msg = await channel.send(embed=embed, view=EditAnnouncementView())

            with announcements_lock:
                ac.execute("""
                    INSERT INTO announcements VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    self.flight, self.dep_airport, self.dep_time, self.dep_gate, self.dep_terminal,
                    self.arr_airport, self.arr_time, self.arr_gate, self.date,
                    self.meal.value, self.host.value, self.alerts.value or "",
                    self.server.value or "", self.status.value, msg.id
                ))
                announcements_db.commit()

            await interaction.followup.send("✅ Announcement created!", ephemeral=True)
        except Exception as e:
            print(f"[BOARDING ERROR] {e}")
            await interaction.followup.send("❌ Error", ephemeral=True)

class EditAnnouncementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Edit Status & Link", style=discord.ButtonStyle.primary, custom_id="edit_announcement")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        from main import bot
        
        if not any(role.id in STAFF_ROLES_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        ac.execute("SELECT * FROM announcements WHERE message_id=?", (interaction.message.id,))
        row = ac.fetchone()
        
        if not row:
            return await interaction.response.send_message("❌ Not found", ephemeral=True)

        await interaction.response.send_modal(EditAnnouncementModal(row))

class EditAnnouncementModal(discord.ui.Modal, title="Edit Announcement"):
    server_link = discord.ui.TextInput(label="Server Link", required=False)
    status = discord.ui.TextInput(label="Status")

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.server_link.default = data[13]
        self.status.default = data[14]

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ac.execute("UPDATE announcements SET server_link=?, status=? WHERE id=?",
            (self.server_link.value, self.status.value, self.data[0]))
        announcements_db.commit()

        embed = interaction.message.embeds[0]
        fields = {f.name: f.value for f in embed.fields}
        fields["📊 Status"] = f"**{self.status.value}**"

        new_embed = discord.Embed(
            title=embed.title,
            color=discord.Color.blue() if "on time" in self.status.value.lower() else discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        for name, value in fields.items():
            new_embed.add_field(name=name, value=value, inline=True if name in ["🛫 Departure","🛬 Arrival","🍽️ Meal","👨‍✈️ Host","📊 Status"] else False)

        if self.server_link.value:
            new_embed.add_field(name="🔗 Server Link", value=self.server_link.value, inline=False)
        
        new_embed.set_footer(text="Updated")

        await interaction.message.edit(embed=new_embed, view=EditAnnouncementView())
        await interaction.followup.send("✅ Updated!", ephemeral=True)

def register_boarding_commands(bot):
    @bot.tree.command(name="boardingannouncement", description="Create boarding announcement (Staff)")
    @app_commands.check(staff)
    @app_commands.check(is_bot_commands_channel)
    async def boarding_announcement(interaction: discord.Interaction):
        await interaction.response.send_modal(BoardingModal1())

    @boarding_announcement.error
    async def boarding_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("⚠️ Staff only", ephemeral=True)