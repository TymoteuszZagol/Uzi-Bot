import asyncio
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

# =========================================================
# KONFIGURACJA
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
EMBED_COLOR = discord.Color(0x660F0F)

STAFF_ROLE_ID = 1546584318615355403
SUPPORT_ROLE_ID = 1546584450765299864  # dawne TT Mod
TECHNIK_ROLE_ID = 1551677652321046721
TICKET_LOGS_CHANNEL_ID = 1546954575989178538
OPEN_TICKETS_CATEGORY_ID = 1547332001961607268
CLOSED_TICKETS_CATEGORY_ID = 1563565970377678971

DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")

# =========================================================
# BOT
# =========================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


def load_json(filename, default):
    if not os.path.exists(filename):
        save_json(filename, default)
        return default
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else default
    except (json.JSONDecodeError, OSError):
        return default


def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
    except OSError as exc:
        print(f"Nie udało się zapisać pliku {filename}: {exc}")


tickets_data = load_json(TICKETS_FILE, {})
MOD_ROLE_IDS = {STAFF_ROLE_ID, SUPPORT_ROLE_ID, TECHNIK_ROLE_ID}


def has_any_role(member, role_ids=MOD_ROLE_IDS):
    return any(role.id in role_ids for role in getattr(member, "roles", []))


def command_check(role_ids):
    async def predicate(ctx):
        return ctx.guild is not None and has_any_role(ctx.author, role_ids)
    return commands.check(predicate)


staff_only = command_check({STAFF_ROLE_ID, TECHNIK_ROLE_ID})
moderator_only = command_check(MOD_ROLE_IDS)


def clean_username(username):
    username = username.lower()
    username = re.sub(r"[^a-z0-9ąćęłńóśźż_-]", "-", username)
    username = re.sub(r"-+", "-", username).strip("-_")
    return (username or "uzytkownik")[:80]


def ticket_open_count(user_id):
    return sum(
        1 for item in tickets_data.values()
        if str(item.get("author_id")) == str(user_id) and item.get("open", True)
    )


def get_category(guild, category_id):
    category = guild.get_channel(category_id)
    return category if isinstance(category, discord.CategoryChannel) else None


def can_manage_ticket(member):
    return has_any_role(member, MOD_ROLE_IDS)


async def make_transcript(channel, ticket_info, deleted_by):
    opened_at = ticket_info.get("opened_at", "Nieznana data")
    lines = [
        "Sicario - transkrypcja ticketu",
        "=" * 45,
        f"Kanał: {channel.name}",
        f"Autor: {ticket_info.get('author_name', 'Nieznany')}",
        f"ID autora: {ticket_info.get('author_id', 'Nieznane')}",
        f"Data otwarcia: {opened_at}",
        f"Usunął: {deleted_by} ({deleted_by.id})",
        f"Data eksportu: {datetime.now(timezone.utc).isoformat()}",
        "=" * 45,
        "",
    ]
    try:
        async for message in channel.history(limit=None, oldest_first=True):
            stamp = message.created_at.strftime("%d.%m.%Y %H:%M:%S UTC")
            lines.append(f"[{stamp}] {message.author} ({message.author.id}):")
            if message.content:
                lines.append(message.content)
            for attachment in message.attachments:
                lines.append(f"Załącznik: {attachment.url}")
            for embed in message.embeds:
                if embed.title:
                    lines.append(f"Embed - tytuł: {embed.title}")
                if embed.description:
                    lines.append(f"Embed - treść: {embed.description}")
            lines.append("")
    except discord.HTTPException:
        lines.append("[Nie udało się pobrać pełnej historii kanału]")
    content = "\n".join(lines)
    filename = f"ticket-{datetime.now(timezone.utc).strftime('%d%m%y')}-{channel.id}.txt"
    return discord.File(io.BytesIO(content.encode("utf-8")), filename=filename)


class ClosedTicketView(discord.ui.View):
    """Po zamknięciu dostępny jest wyłącznie przycisk usunięcia."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Usuń Ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_ticket_action(interaction)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        if guild is None or not isinstance(channel, discord.TextChannel):
            return
        if not can_manage_ticket(interaction.user):
            await interaction.response.send_message("Nie masz uprawnień do zamknięcia tego ticketu.", ephemeral=True)
            return
        info = tickets_data.get(str(channel.id))
        if info is None:
            await interaction.response.send_message("Nie znaleziono danych tego ticketu.", ephemeral=True)
            return
        if not info.get("open", True):
            await interaction.response.send_message("Ten ticket jest już zamknięty.", ephemeral=True)
            return

        closed_category = get_category(guild, CLOSED_TICKETS_CATEGORY_ID)
        if closed_category is None:
            await interaction.response.send_message("Nie znaleziono kategorii CLOSED TICKETS.", ephemeral=True)
            return

        creator = guild.get_member(int(info.get("author_id", 0)))
        overwrites = channel.overwrites
        if creator is not None:
            overwrites[creator] = discord.PermissionOverwrite(view_channel=False, read_message_history=False, send_messages=False)
        for role_id in MOD_ROLE_IDS:
            role = guild.get_role(role_id)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

        new_name = f"closed-{clean_username(info.get('username', info.get('author_name', 'uzytkownik')))}"[:100]
        try:
            await channel.edit(category=closed_category, name=new_name, overwrites=overwrites, reason=f"Ticket zamknięty przez {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("Bot nie ma uprawnień do przeniesienia lub zmiany uprawnień kanału.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("Nie udało się zamknąć ticketu.", ephemeral=True)
            return

        info["open"] = False
        info["closed_by"] = interaction.user.id
        info["closed_at"] = datetime.now(timezone.utc).isoformat()
        save_json(TICKETS_FILE, tickets_data)
        await interaction.response.send_message("Ticket został zamknięty. Autor nie ma już dostępu do kanału.", ephemeral=True)
        try:
            await interaction.message.edit(view=ClosedTicketView())
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @discord.ui.button(label="Usuń Ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_ticket_action(interaction)


async def delete_ticket_action(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel
    if guild is None or not isinstance(channel, discord.TextChannel):
        return
    if not can_manage_ticket(interaction.user):
        await interaction.response.send_message("Nie masz uprawnień do usunięcia tego ticketu.", ephemeral=True)
        return
    info = tickets_data.get(str(channel.id))
    if info is None:
        await interaction.response.send_message("Nie znaleziono danych tego ticketu.", ephemeral=True)
        return

    await interaction.response.send_message("Tworzę transkrypcję i usuwam ticket.", ephemeral=True)
    transcript = await make_transcript(channel, info, interaction.user)
    logs_channel = guild.get_channel(TICKET_LOGS_CHANNEL_ID)
    if isinstance(logs_channel, discord.TextChannel):
        try:
            await logs_channel.send(
                content=(f"**Transkrypcja ticketu**\nKanał: `{channel.name}`\n"
                         f"Autor: {info.get('author_name', 'Nieznany')}\nUsunął: {interaction.user.name}"),
                file=transcript,
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    tickets_data.pop(str(channel.id), None)
    save_json(TICKETS_FILE, tickets_data)
    try:
        await channel.delete(reason=f"Ticket usunięty przez {interaction.user}")
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Stwórz ticket", style=discord.ButtonStyle.success, custom_id="ticket_create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("Ticket można utworzyć tylko na serwerze.", ephemeral=True)
            return
        if ticket_open_count(member.id) >= 1:
            await interaction.response.send_message("Masz już otwarty ticket.", ephemeral=True)
            return
        category = get_category(guild, OPEN_TICKETS_CATEGORY_ID)
        if category is None:
            await interaction.response.send_message("Nie znaleziono kategorii TICKETS.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
        }
        for role_id in MOD_ROLE_IDS:
            role = guild.get_role(role_id)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
        bot_member = guild.me
        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True)

        username = clean_username(member.name)  # Discord username, nie nick serwerowy
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{username}"[:100],
                category=category,
                overwrites=overwrites,
                reason=f"Ticket utworzony przez {member}",
            )
        except discord.Forbidden:
            await interaction.response.send_message("Bot nie ma uprawnień do utworzenia ticketu.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("Nie udało się utworzyć ticketu.", ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        tickets_data[str(channel.id)] = {
            "author_id": member.id,
            "author_name": str(member),
            "username": member.name,
            "opened_at": now.isoformat(),
            "open": True,
        }
        save_json(TICKETS_FILE, tickets_data)

        try:
            # Instrukcja i przyciski w embedzie z kolorem używanym w pozostałych embedach.
            ticket_embed = discord.Embed(
                description="Napisz czego potrzebujesz i czekaj na odpowiedź!",
                color=EMBED_COLOR,
            )
            await channel.send(embed=ticket_embed, view=TicketView())
            # Osobna wiadomość poza embedem; pingowany jest tylko autor ticketu.
            await channel.send(
                f"{member.mention} NIE PINGUJ OWNERA",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except discord.HTTPException:
            pass
        await interaction.response.send_message(f"Ticket został utworzony: {channel.mention}", ephemeral=True)


# =========================================================
# KOMENDY
# =========================================================
@bot.command(name="ticket")
@staff_only
async def ticket(ctx):
    embed = discord.Embed(
        title="Stwórz ticket",
        description="Jeśli chcesz kupić konto, vdolce lub usługi albo potrzebujesz pomocy - kliknij przycisk poniżej!",
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed, view=TicketPanelView())
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass


@bot.command(name="clear")
@moderator_only
async def clear(ctx, *args):
    if not args:
        return
    amount = None
    target = None
    for arg in args:
        if arg.lower() == "all":
            amount = "all"
        elif arg.isdigit():
            amount = int(arg)
        elif arg.startswith("<@"):
            try:
                target = await commands.MemberConverter().convert(ctx, arg)
            except commands.BadArgument:
                await ctx.send("Nie znaleziono użytkownika.", delete_after=3)
                return
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    try:
        if target is None:
            if amount == "all":
                await ctx.channel.purge(limit=None)
            elif isinstance(amount, int):
                await ctx.channel.purge(limit=amount)
            return
        deleted_count = 0
        async for message in ctx.channel.history(limit=None):
            if message.author.id != target.id:
                continue
            try:
                await message.delete()
                deleted_count += 1
            except discord.Forbidden:
                pass
            if isinstance(amount, int) and deleted_count >= amount:
                break
    except discord.Forbidden:
        await ctx.send("Bot nie ma uprawnień do usuwania wiadomości.", delete_after=4)


@bot.command(name="mute")
@moderator_only
async def mute(ctx, member: discord.Member, duration: str):
    if member == ctx.author:
        await ctx.send("Nie możesz wyciszyć siebie.", delete_after=3)
        return
    if member == ctx.guild.me:
        await ctx.send("Nie mogę wyciszyć siebie.", delete_after=3)
        return
    match = re.fullmatch(r"(\d+)(s|m|h|d)", duration.lower())
    if not match:
        await ctx.send("Nieprawidłowy czas. Użyj np. 5s, 10m, 2h albo 3d.", delete_after=4)
        return
    value = int(match.group(1))
    seconds = value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    if seconds <= 0 or seconds > 28 * 86400:
        await ctx.send("Czas timeoutu musi wynosić od 1 sekundy do 28 dni.", delete_after=4)
        return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("Nie możesz wyciszyć osoby z równą lub wyższą rolą.", delete_after=4)
        return
    bot_member = ctx.guild.me
    if bot_member is None or member.top_role >= bot_member.top_role:
        await ctx.send("Bot nie może wyciszyć osoby z równą lub wyższą rolą od swojej.", delete_after=4)
        return
    try:
        await member.timeout(timedelta(seconds=seconds), reason=f"Wyciszenie przez {ctx.author}")
        await ctx.send(f"{member.mention} został wyciszony na **{duration}**.", delete_after=4)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await ctx.send("Bot nie ma uprawnień do timeoutu tej osoby.", delete_after=4)


@bot.command(name="ban")
@moderator_only
async def ban(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send("Nie możesz zbanować siebie.", delete_after=4)
        return
    if member == ctx.guild.me:
        await ctx.send("Nie możesz zbanować bota.", delete_after=4)
        return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("Nie możesz zbanować osoby z równą lub wyższą rolą.", delete_after=4)
        return
    if ctx.guild.me is None or member.top_role >= ctx.guild.me.top_role:
        await ctx.send("Bot nie może zbanować osoby z równą lub wyższą rolą od swojej.", delete_after=4)
        return
    try:
        await member.ban(reason=f"Permanentny ban przez {ctx.author}")
        await ctx.send(f"Użytkownik **{member}** został zbanowany na stałe.", delete_after=5)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await ctx.send("Bot nie ma uprawnień do zbanowania tej osoby.", delete_after=4)
    except discord.HTTPException:
        await ctx.send("Nie udało się zbanować tego użytkownika.", delete_after=4)


@bot.command(name="kick")
@moderator_only
async def kick(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send("Nie możesz wyrzucić siebie.", delete_after=4)
        return
    if member == ctx.guild.me:
        await ctx.send("Nie możesz wyrzucić bota.", delete_after=4)
        return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("Nie możesz wyrzucić osoby z równą lub wyższą rolą.", delete_after=4)
        return
    if ctx.guild.me is None or member.top_role >= ctx.guild.me.top_role:
        await ctx.send("Bot nie może wyrzucić osoby z równą lub wyższą rolą od swojej.", delete_after=4)
        return
    try:
        name = str(member)
        await member.kick(reason=f"Wyrzucony przez {ctx.author}")
        await ctx.send(f"Użytkownik **{name}** został wyrzucony z serwera.", delete_after=5)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await ctx.send("Bot nie ma uprawnień do wyrzucenia tej osoby.", delete_after=4)
    except discord.HTTPException:
        await ctx.send("Nie udało się wyrzucić tego użytkownika.", delete_after=4)


# =========================================================
# BŁĘDY I URUCHOMIENIE
# =========================================================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, (commands.CheckFailure, commands.MissingPermissions)):
        await ctx.send("Nie masz uprawnień do tej komendy.", delete_after=4)
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Brakuje wymaganych argumentów.", delete_after=4)
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("Nieprawidłowy argument.", delete_after=4)
        return
    print(f"[BŁĄD KOMENDY] {type(error).__name__}: {error}")


@bot.event
async def on_ready():
    if not getattr(bot, "_persistent_views_added", False):
        bot.add_view(TicketPanelView())
        bot.add_view(TicketView())
        bot.add_view(ClosedTicketView())
        bot._persistent_views_added = True
    print(f"Zalogowano jako {bot.user}")
    print(f"Połączono z {len(bot.guilds)} serwerami")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN nie jest ustawiony w zmiennych środowiskowych.")

bot.run(TOKEN)
