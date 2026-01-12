import discord
from discord.ext import commands
import asyncio
import random
import re
from datetime import datetime, timedelta
import aiohttp
import os   # ✅ ADDED

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

afk_users = {}

# giveaway state
active_giveaways = set()
ended_giveaways = set()

# ================= ON READY =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ================= AFK COMMAND =================
@bot.command()
async def afk(ctx, *, reason="AFK"):
    afk_users[ctx.author.id] = reason
    await ctx.send(f"💤 {ctx.author.mention} is now AFK: **{reason}**")

# ================= ON MESSAGE =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in afk_users:
        del afk_users[message.author.id]
        await message.channel.send(
            f"👋 Welcome back {message.author.mention}, AFK removed!"
        )

    for user in message.mentions:
        if user.id in afk_users:
            await message.channel.send(
                f"💤 {user.mention} is AFK: **{afk_users[user.id]}**"
            )

    await bot.process_commands(message)

# ================= TIME PARSER =================
def parse_time(time_str):
    match = re.match(r"(\d+)(s|m|h|d)$", time_str.lower())
    if not match:
        return None

    amount, unit = match.groups()
    amount = int(amount)

    return {
        "s": amount,
        "m": amount * 60,
        "h": amount * 3600,
        "d": amount * 86400
    }.get(unit)

# ================= GIVEAWAY COMMAND =================
@bot.command()
@commands.has_permissions(administrator=True)
async def gw(ctx, time: str, winners: int, *, prize: str):
    seconds = parse_time(time)
    if seconds is None:
        await ctx.send("❌ Invalid time format! Example: `10s`, `5m`, `2h`, `1d`")
        return

    gift = "<:417787gift:1458057966363214007>"
    dot = "<:gigachad_dot:1458124691058458644>"
    party = "<a:Party:1458109878370570446>"

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    end_timestamp = f"<t:{int(end_time.timestamp())}:F>"

    embed = discord.Embed(
        description=(
            f"{gift} **{prize}** {gift}\n\n"
            f"{dot} **Winners:** {winners}\n"
            f"{dot} **Ends:** in {time} ({end_timestamp})\n"
            f"{dot} **Hosted by:** {ctx.author.mention}\n\n"
            f"{dot} React with {party} to participate!"
        ),
        color=discord.Color.purple()
    )

    embed.set_footer(
        text=f"Ends at • {end_time.strftime('%I:%M %p')}",
        icon_url=ctx.author.display_avatar.url
    )

    msg = await ctx.send(
        content=f"{party} **New Giveaway** {party}",
        embed=embed
    )

    await msg.add_reaction(
        discord.PartialEmoji(name="Party", id=1458109878370570446)
    )

    active_giveaways.add(msg.id)

    await asyncio.sleep(seconds)

    # ❌ skip auto end if already ended manually
    if msg.id in ended_giveaways:
        return

    await end_giveaway(ctx.channel, msg.id)

# ================= END GIVEAWAY FUNCTION =================
async def end_giveaway(channel, message_id):
    if message_id in ended_giveaways:
        return

    ended_giveaways.add(message_id)

    msg = await channel.fetch_message(message_id)
    if not msg.embeds:
        return

    embed = msg.embeds[0]

    prize_match = re.search(r"\*\*(.*?)\*\*", embed.description)
    prize = prize_match.group(1) if prize_match else "Unknown"

    host_match = re.search(r"<@!?(\d+)>", embed.description)
    host_id = host_match.group(1) if host_match else None

    reaction = discord.utils.get(
        msg.reactions,
        emoji=discord.PartialEmoji(name="Party", id=1458109878370570446)
    )

    if not reaction:
        await channel.send("❌ No participants.")
        return

    users = [u async for u in reaction.users() if not u.bot]
    if not users:
        await channel.send("❌ No participants.")
        return

    winner = random.choice(users)

    await channel.send(
        f"🎉 Congrats, {winner.mention} you have won **{prize}**, "
        f"hosted by <@!{host_id}>"
    )

# ================= MANUAL END =================
@bot.command()
@commands.has_permissions(administrator=True)
async def gend(ctx, message_id: int):
    await end_giveaway(ctx.channel, message_id)

# ================= PURGE =================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1:
        await ctx.send("❌ Amount must be greater than 0")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(
        f"🧹 Deleted **{len(deleted)-1}** messages",
        delete_after=5
    )

# ================= STEAL EMOJI =================
@bot.command()
@commands.has_permissions(manage_emojis=True)
async def steal(ctx, name: str = None):
    if not ctx.message.reference:
        await ctx.send("❌ Emoji wale message ko reply karke `!steal` use karo.")
        return

    replied = await ctx.channel.fetch_message(
        ctx.message.reference.message_id
    )

    pattern = r"<(a?):(\w+):(\d+)>"
    match = re.search(pattern, replied.content)

    if not match:
        await ctx.send("❌ Reply message me koi custom emoji nahi mila.")
        return

    animated, emoji_name, emoji_id = match.groups()
    emoji_name = name if name else emoji_name

    ext = "gif" if animated == "a" else "png"
    emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"

    async with aiohttp.ClientSession() as session:
        async with session.get(emoji_url) as resp:
            image = await resp.read()

    new_emoji = await ctx.guild.create_custom_emoji(
        name=emoji_name,
        image=image
    )

    await ctx.send(f"✅ Successfully created emoji {new_emoji}")

# ================= ERROR HANDLER =================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            "❌ Wrong format.\n"
            "`!gw <time> <winners> <prize>`\n"
            "Example: `!gw 2m 1 Nitro`"
        )
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(error)

# ================= RUN BOT =================
TOKEN = os.getenv("TOKEN")   # ✅ ENV VARIABLE
bot.run(TOKEN)
