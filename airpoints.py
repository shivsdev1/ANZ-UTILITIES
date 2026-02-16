import discord
from discord import app_commands
from datetime import datetime

from database import kc, krispoints_db, krispoints_lock


STAFF_ROLES_IDS = {1468230337900580887}
BOT_COMMANDS_CHANNEL = 1468449739388227695


def staff(interaction: discord.Interaction):
    
    return any(r.id in STAFF_ROLES_IDS for r in interaction.user.roles)


def is_bot_commands_channel(interaction: discord.Interaction):
    return interaction.channel_id == BOT_COMMANDS_CHANNEL


def register_airpoints_commands(bot):

    @bot.tree.command(name="awardairpoints", description="Award Airpoints (Staff)")
    @app_commands.check(staff)
    async def award(interaction: discord.Interaction, user: discord.Member, amount: int, flight: str):
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive", ephemeral=True
            )

        try:
            with krispoints_lock:
                kc.execute(
                    "SELECT balance, flights FROM krispoints WHERE user_id=?",
                    (user.id,)
                )
                row = kc.fetchone()

                current_balance = row[0] if row else 0
                current_flights = row[1] if row else 0

                new_balance = current_balance + amount
                new_flights = current_flights + 1

                kc.execute(
                    "REPLACE INTO krispoints VALUES (?,?,?)",
                    (user.id, new_balance, new_flights)
                )
                krispoints_db.commit()

            embed = discord.Embed(
                title="✅ Airpoints Awarded",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=user.mention, inline=False)
            embed.add_field(name="Points Awarded", value=f"**+{amount}**", inline=True)
            embed.add_field(name="New Balance", value=f"**{new_balance:,}**", inline=True)
            embed.add_field(name="Flight", value=flight, inline=False)
            embed.add_field(name="Total Flights", value=f"**{new_flights}**", inline=True)

            await interaction.response.send_message(embed=embed)
            print(f"[AIRPOINTS] +{amount} → {user} (now {new_balance})")

        except Exception as e:
            print(f"[AIRPOINTS / AWARD] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)

    @award.error
    async def award_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("⚠️ Staff only", ephemeral=True)


    @bot.tree.command(name="airpoints", description="Check Airpoints balance")
    async def airpoints_cmd(interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user

        try:
            kc.execute(
                "SELECT balance, flights FROM krispoints WHERE user_id=?",
                (target.id,)
            )
            row = kc.fetchone()

            if not row:
                return await interaction.response.send_message(
                    f"📊 No record for {target.mention}",
                    ephemeral=True
                )

            embed = discord.Embed(
                title="💳 Airpoints Balance",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=target.mention, inline=False)
            embed.add_field(name="Balance", value=f"**{row[0]:,}** Airpoints", inline=False)
            embed.add_field(name="Flights Completed", value=f"**{row[1]}**", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"[AIRPOINTS / VIEW] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)


    @bot.tree.command(name="deductairpoints", description="Deduct Airpoints (Staff)")
    @app_commands.check(staff)
    @app_commands.check(is_bot_commands_channel)
    async def deduct(interaction: discord.Interaction, user: discord.Member, amount: int, reason: str):
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive", ephemeral=True
            )

        try:
            with krispoints_lock:
                kc.execute(
                    "SELECT balance, flights FROM krispoints WHERE user_id=?",
                    (user.id,)
                )
                row = kc.fetchone()

                if not row:
                    return await interaction.response.send_message(
                        f"❌ No record for {user.mention}",
                        ephemeral=True
                    )

                new_balance = max(0, row[0] - amount)

                kc.execute(
                    "REPLACE INTO krispoints VALUES (?,?,?)",
                    (user.id, new_balance, row[1])
                )
                krispoints_db.commit()

            embed = discord.Embed(
                title="❌ Airpoints Deducted",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=user.mention, inline=False)
            embed.add_field(name="Points Deducted", value=f"**-{amount}**", inline=True)
            embed.add_field(name="New Balance", value=f"**{new_balance:,}**", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)

            await interaction.response.send_message(embed=embed)
            print(f"[AIRPOINTS] -{amount} → {user} (now {new_balance})")

        except Exception as e:
            print(f"[AIRPOINTS / DEDUCT] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)

    @deduct.error
    async def deduct_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("⚠️ Staff only", ephemeral=True)


    @bot.tree.command(name="airpoints_leaderboard", description="Top 10 Airpoints")
    async def leaderboard(interaction: discord.Interaction):
        try:
            kc.execute(
                "SELECT user_id, balance, flights FROM krispoints ORDER BY balance DESC LIMIT 10"
            )
            rows = kc.fetchall()

            if not rows:
                return await interaction.response.send_message(
                    "📊 No records", ephemeral=True
                )

            embed = discord.Embed(
                title="🏆 Airpoints Leaderboard",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            medals = ["🥇", "🥈", "🥉"]
            lines = []

            for i, (uid, bal, fl) in enumerate(rows, start=1):
                prefix = medals[i - 1] if i <= 3 else f"**{i}.**"
                user = bot.get_user(uid)
                name = user.name if user else f"User {uid}"

                lines.append(f"{prefix} {name} — **{bal:,}** pts ({fl} flights)")

            embed.description = "\n".join(lines)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"[AIRPOINTS / LEADERBOARD] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)


    @bot.tree.command(name="resetairpoints", description="Reset airpoints (Staff)")
    @app_commands.check(staff)
    @app_commands.check(is_bot_commands_channel)
    async def reset_krispoints(interaction: discord.Interaction, user: discord.Member):
        try:
            with krispoints_lock:
                kc.execute(
                    "REPLACE INTO krispoints VALUES (?,?,?)",
                    (user.id, 0, 0)
                )
                krispoints_db.commit()

            embed = discord.Embed(
                title="🔄 Airpoints Reset",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=user.mention, inline=False)
            embed.add_field(name="Balance", value="**0**", inline=True)
            embed.add_field(name="Flights", value="**0**", inline=True)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"[AIRPOINTS / RESET] {e}")
            await interaction.response.send_message("❌ Error", ephemeral=True)

    @reset_krispoints.error
    async def reset_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("⚠️ Staff only", ephemeral=True)
