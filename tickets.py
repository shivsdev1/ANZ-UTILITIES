import discord
from discord import app_commands
from datetime import datetime
import tempfile
import os

from database import tc, tickets_db, tickets_lock

HELPDESK_CHANNEL = 1468889471675273247
TICKETS_CATEGORY_ID = 1468889195471700038
STAFF_ROLES_IDS = {1468230337900580887}

helpdesk_embed_sent = False

class TicketCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Partnership Inquiry", style=discord.ButtonStyle.primary, custom_id="ticket_partnership")
    async def partnership(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Partnership Inquiry", "ptn-ship"))

    @discord.ui.button(label="General Support", style=discord.ButtonStyle.secondary, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("General Support", "gnrl"))

    @discord.ui.button(label="Flight Booking Issue", style=discord.ButtonStyle.danger, custom_id="ticket_flight")
    async def flight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Flight Booking Issue", "fbking"))

class TicketModal(discord.ui.Modal):
    title_input = discord.ui.TextInput(label="Issue Title", placeholder="Brief description", max_length=100)

    def __init__(self, category, prefix):
        super().__init__(title=f"Create Ticket - {category}")
        self.category = category
        self.prefix = prefix

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            
            with tickets_lock:
                tc.execute("SELECT COUNT(*) FROM tickets WHERE category=?", (self.category,))
                count = tc.fetchone()[0] + 1
            
            ticket_number = f"{self.prefix}-{count:03d}"
            
            ticket_category = guild.get_channel(TICKETS_CATEGORY_ID)
            
            if not ticket_category:
                return await interaction.followup.send("❌ Category not found", ephemeral=True)
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            channel = await guild.create_text_channel(
                ticket_number, category=ticket_category, overwrites=overwrites,
                topic=f"Ticket: {ticket_number} | User: {interaction.user.mention} | Category: {self.category}"
            )

            with tickets_lock:
                tc.execute("""
                    INSERT INTO tickets (ticket_number, channel_id, user_id, category, title, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ticket_number, channel.id, interaction.user.id, self.category, self.title_input.value, datetime.now().isoformat(), 'open'))
                tickets_db.commit()

            embed = discord.Embed(
                title=f"🎫 Support Ticket #{ticket_number}",
                description="Thank you! Our team will assist you shortly.",
                color=discord.Color.blue(), timestamp=datetime.now()
            )
            embed.add_field(name="Category", value=self.category, inline=True)
            embed.add_field(name="Status", value="🟢 Open", inline=True)
            embed.add_field(name="User", value=interaction.user.mention, inline=True)
            embed.add_field(name="Issue", value=self.title_input.value, inline=False)
            embed.set_footer(text="Use buttons below to close ticket")

            await channel.send(embed=embed, view=TicketActionView())
            await interaction.followup.send(f"✅ Ticket created! {channel.mention}", ephemeral=True)

        except Exception as e:
            print(f"[TICKET ERROR] {e}")
            await interaction.followup.send("❌ Error creating ticket", ephemeral=True)

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚠️ Close Ticket?",
            description="Are you sure? This cannot be undone.",
            color=discord.Color.orange(), timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(interaction.channel), ephemeral=True)

class ConfirmCloseView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=300)
        self.channel = channel

    @discord.ui.button(label="Yes, Close Ticket", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            from main import bot
            
            tc.execute("SELECT ticket_number, user_id FROM tickets WHERE channel_id=?", (self.channel.id,))
            ticket_row = tc.fetchone()
            
            if not ticket_row:
                return await interaction.followup.send("❌ Ticket not found", ephemeral=True)

            ticket_number, user_id = ticket_row

            # create transcript
            transcript_text = f"{'='*60}\nTICKET TRANSCRIPT\n{'='*60}\n"
            transcript_text += f"Ticket Number: {ticket_number}\n"
            transcript_text += f"Channel: {self.channel.name}\n"
            transcript_text += f"Closed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            transcript_text += f"{'='*60}\n\n"

            try:
                async for message in self.channel.history(limit=None, oldest_first=True):
                    if message.author.bot and message.author.name == "APP":
                        continue
                    
                    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    content = message.content if message.content else "[Embed/Media]"
                    transcript_text += f"[{timestamp}] {message.author.name}: {content}\n\n"
            except:
                pass

            with tickets_lock:
                tc.execute("UPDATE tickets SET status=?, transcript=? WHERE channel_id=?",
                    ('closed', transcript_text, self.channel.id))
                tickets_db.commit()

            # send transcript to user
            try:
                user = await bot.fetch_user(user_id)
                
                transcript_filename = f"{ticket_number}_transcript.txt"
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
                    tmp.write(transcript_text)
                    tmp_path = tmp.name
                
                with open(tmp_path, 'rb') as f:
                    transcript_file = discord.File(f, filename=transcript_filename)
                    
                    embed = discord.Embed(
                        title=f"🎫 Ticket Closed: {ticket_number}",
                        description="Your ticket has been closed. See transcript attached.",
                        color=discord.Color.green(), timestamp=datetime.now()
                    )
                    embed.set_footer(text="Thank you!")
                    
                    await user.send(embed=embed, file=transcript_file)
                
                os.remove(tmp_path)
            except:
                print(f"[TRANSCRIPT] Could not DM user {user_id}")

            await interaction.followup.send(f"✅ Ticket {ticket_number} closed", ephemeral=True)
            await self.channel.delete(reason=f"Ticket {ticket_number} closed")

        except Exception as e:
            print(f"[CLOSE TICKET ERROR] {e}")
            await interaction.followup.send("❌ Error closing ticket", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Cancelled", ephemeral=True)

async def send_helpdesk_message(bot):
    global helpdesk_embed_sent
    
    if helpdesk_embed_sent:
        return
    
    try:
        channel = bot.get_channel(HELPDESK_CHANNEL)
        if not channel:
            return
        
        # check if exists
        async for message in channel.history(limit=10):
            if message.author == bot.user and message.embeds:
                if "Support Service" in message.embeds[0].title:
                    helpdesk_embed_sent = True
                    return
        
        embed = discord.Embed(
            title=" ANZ | SUPPORT SERVICE",
            description="Welcome to Air New Zealand Support.\n\nSelect a category below.\n\nFor small questions, use #general-chat.",
            color=discord.Color.blue(), timestamp=datetime.now()
        )
        embed.add_field(
            name="📋 Categories",
            value="**Partnership Inquiry** - Want to partner?\n**General Support** - Have a question?\n**Flight Booking Issue** - Booking problems?",
            inline=False
        )
        embed.set_footer(text="Thank you")
        
        await channel.send(embed=embed, view=TicketCategoryView())
        helpdesk_embed_sent = True
        print("[HELPDESK] Message sent")
        
    except Exception as e:
        print(f"[HELPDESK ERROR] {e}")

def setup_ticket_views(bot):
    bot.add_view(TicketCategoryView())
    bot.add_view(TicketActionView())

def register_ticket_commands(bot):
    
    @bot.tree.command(name="resend_helpdesk", description="Resend helpdesk (Staff)")
    async def resend_helpdesk(interaction: discord.Interaction):
        if not any(role.id in STAFF_ROLES_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)
            
        try:
            channel = bot.get_channel(HELPDESK_CHANNEL)
            if not channel:
                return await interaction.response.send_message("❌ Channel not found", ephemeral=True)
            
            embed = discord.Embed(
                title=" ANZ | Support Service",
                description="Welcome to Air New Zealand Support.\n\nSelect a category below.",
                color=discord.Color.blue(), timestamp=datetime.now()
            )
            embed.add_field(
                name="📋 Categories",
                value="**Partnership** / **Support** / **Booking Issue**",
                inline=False
            )
            
            await channel.send(embed=embed, view=TicketCategoryView())
            await interaction.response.send_message("✅ Sent!", ephemeral=True)
            
        except Exception as e:
            print(f"[RESEND ERROR] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)