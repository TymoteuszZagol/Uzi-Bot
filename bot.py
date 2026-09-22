import discord
from discord.ext import commands
import asyncio
import json
import os
import re
import io
from datetime import datetime, timezone, timedelta


TOKEN = os.getenv("DISCORD_TOKEN")

PREFIX = "!"

# =========================================================
# EMBED COLOR
# =========================================================

EMBED_COLOR = discord.Color(0x279A08)


# =========================================================
# IDS
# =========================================================

OWNER_ROLE_ID = 1546584318615355403
VERIFIED_ROLE_ID = 1546585369036718180
TT_MOD_ROLE_ID = 1546584450765299864

VERIFICATION_CHANNEL_ID = 1546587855600619650
PAYMENT_CHANNEL_ID = 1546579970040533032
SOCIALS_CHANNEL_ID = 1546582618408230992

LEVELS_CHANNEL_ID = 1546580272227815674
INVITES_CHANNEL_ID = 1546580295849873568

TICKET_PANEL_CHANNEL_ID = 1546579992954273862
TICKET_LOGS_CHANNEL_ID = 1546954575989178538
TICKET_RULES_CHANNEL_ID = 1546957819515764756
STOCK_CHANNEL_ID = 1546579943478136953

REGULAMIN_CHANNEL_ID = 1546579730285854720
FAQ_CHANNEL_ID = 1551661857230819398
GIVEAWAY_CHANNEL_ID = 1551307818022477905
COMMUNITY_CHAT_CHANNEL_ID = 1546580039066460240
LEGITCHECK_CHANNEL_ID = 1546580016534655017

INFORMATION_CATEGORY_ID = 1546577882586026185
LIVE_CHANNEL_ID = 1546579670361706586

SHOP_CATEGORY_ID = 1546580547344531506
COMMUNITY_CATEGORY_ID = 1546580572380471356
VOICE_CATEGORY_ID = 1546580607142727741

BLACKLIST_CATEGORY_ID = 1547264870733316167

# Ticket categories
PURCHASES_CATEGORY_ID = 1546963814854041601
REPORTS_CATEGORY_ID = 1546963863931719690
QUESTIONS_ERRORS_CATEGORY_ID = 1551661373040365679
OTHER_CATEGORY_ID = 1546964017032069210

TICKET_CATEGORY_IDS = [
    PURCHASES_CATEGORY_ID,
    REPORTS_CATEGORY_ID,
    QUESTIONS_ERRORS_CATEGORY_ID,
    OTHER_CATEGORY_ID
]


# =========================================================
# DATA FILES
# =========================================================

DATA_DIR = "/app/data"

os.makedirs(DATA_DIR, exist_ok=True)

TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# =========================================================
# FILE HELPERS
# =========================================================

def initialize_data_file(filename, default):

    if os.path.exists(filename):
        return

    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(
                default,
                file,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:
        print(f"Nie udało się utworzyć {filename}: {e}")


def load_json(filename, default):

    if not os.path.exists(filename):
        initialize_data_file(
            filename,
            default
        )
        return default

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return default


def save_json(filename, data):

    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:
        print(f"Nie udało się zapisać {filename}: {e}")


# =========================================================
# DATA
# =========================================================

tickets_data = load_json(
    TICKETS_FILE,
    {}
)


# =========================================================
# PERMISSION CHECKS
# =========================================================

def has_staff_role(member):

    return (
        any(
            role.id == OWNER_ROLE_ID
            for role in member.roles
        )
        or
        any(
            role.id == TT_MOD_ROLE_ID
            for role in member.roles
        )
    )


def is_owner():

    async def predicate(ctx):

        if ctx.guild is None:
            return False

        role = ctx.guild.get_role(
            OWNER_ROLE_ID
        )

        if role is None:
            return False

        return role in ctx.author.roles

    return commands.check(predicate)


def is_staff():

    async def predicate(ctx):

        if ctx.guild is None:
            return False

        return has_staff_role(
            ctx.author
        )

    return commands.check(predicate)


# =========================================================
# VERIFICATION
# =========================================================

class VerifyView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        custom_id="verify_button"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild

        if guild is None:
            return

        role = guild.get_role(
            VERIFIED_ROLE_ID
        )

        if role is None:

            await interaction.response.send_message(
                "The uzytkownik role could not be found.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.response.send_message(
                "You are already verified.",
                ephemeral=True
            )

            return

        try:

            await interaction.user.add_roles(
                role,
                reason="User verification"
            )

            await interaction.response.send_message(
                "You have been successfully verified.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "I do not have permission to give you the uzytkownik role.",
                ephemeral=True
            )


@bot.command()
@is_owner()
async def weryfikacja(ctx):

    channel = bot.get_channel(
        VERIFICATION_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Verification channel not found."
        )

        return

    embed = discord.Embed(
        title="Uzi Shop Verification",
        description="Click the button below to verify yourself.",
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed,
        view=VerifyView()
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# PAYMENTS
# =========================================================

@bot.command()
@is_owner()
async def platnosc(ctx):

    channel = bot.get_channel(
        PAYMENT_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Payment channel not found."
        )

        return

    embed = discord.Embed(
        description=(
            "**Metody płatności:**\n"
            "BLIK przelew/kod <:blik1:1546610208388808784>\n"
            "(ewentualnie przelew krajowy)\n\n"
            "⚠️ **Paysafecard nie jest akceptowany**"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# MEDIA
# =========================================================

@bot.command()
@is_owner()
async def media(ctx):

    channel = bot.get_channel(
        SOCIALS_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Media channel not found."
        )

        return

    embed = discord.Embed(
        title="Nasze media",
        description=(
            "<:tt:1546623179047305307> **TikTok:** "
            "[uzi.02_](https://www.tiktok.com/@uzi.02_)\n"
            "<:tg:1546623148563107973> **Telegram:** "
            "[uzigoat](https://t.me/uzigoat)"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# CLEAR
# =========================================================

@bot.command()
@is_staff()
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

                target = await commands.MemberConverter().convert(
                    ctx,
                    arg
                )

            except commands.BadArgument:

                await ctx.send(
                    "User not found.",
                    delete_after=3
                )

                return

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    if target is None:

        if amount == "all":

            await ctx.channel.purge(
                limit=None
            )

        elif isinstance(amount, int):

            await ctx.channel.purge(
                limit=amount
            )

        return

    deleted_count = 0

    async for message in ctx.channel.history(
        limit=None
    ):

        if message.author.id == target.id:

            try:

                await message.delete()

                deleted_count += 1

            except discord.Forbidden:
                pass

            if (
                isinstance(amount, int)
                and deleted_count >= amount
            ):
                break


# =========================================================
# MUTE
# =========================================================

@bot.command()
@is_staff()
async def mute(
    ctx,
    member: discord.Member,
    duration: str
):

    if member == ctx.author:

        await ctx.send(
            "You cannot mute yourself.",
            delete_after=3
        )

        return

    if member == ctx.guild.me:

        await ctx.send(
            "I cannot mute myself.",
            delete_after=3
        )

        return

    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        duration.lower()
    )

    if not match:

        await ctx.send(
            "Invalid duration. Use formats such as 5s, 10m, 2h or 3d.",
            delete_after=4
        )

        return

    value = int(
        match.group(1)
    )

    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    seconds = value * multipliers[unit]

    if seconds > 28 * 86400:

        await ctx.send(
            "The maximum timeout duration is 28 days.",
            delete_after=4
        )

        return

    if member.top_role >= ctx.author.top_role:

        await ctx.send(
            "You cannot mute a user with an equal or higher role.",
            delete_after=4
        )

        return

    if member.top_role >= ctx.guild.me.top_role:

        await ctx.send(
            "I cannot mute a user with an equal or higher role than mine.",
            delete_after=4
        )

        return

    try:

        await member.timeout(
            timedelta(seconds=seconds),
            reason=f"Muted by {ctx.author}"
        )

        await ctx.send(
            f"{member.mention} has been muted for **{duration}**.",
            delete_after=4
        )

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    except discord.Forbidden:

        await ctx.send(
            "I do not have permission to timeout this user.",
            delete_after=4
        )


# =========================================================
# INVITE REWARDS
# =========================================================

@bot.command()
@is_owner()
async def invites(ctx):

    embed = discord.Embed(
        title="🎁 • NAGRODY ZA ZAPROSZENIA",
        description=(
            "Każde 10 zaproszeń = 10 zł do wydania na naszym serwerze"
        ),
        color=EMBED_COLOR
    )

    await ctx.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# TICKET SYSTEM
# =========================================================

CATEGORY_INFO = {

    "Zamówienia": {
        "emoji": "🛒",
        "prefix": "zamowienie",
        "category_id": PURCHASES_CATEGORY_ID,
        "subcategories": {
            "Pytanie dotyczące zamówienia": "pytanie",
            "Kupno konta NFA ze stock": "nfa",
            "Kupno konta FA ze stock": "fa",
            "Kupno konta z live": "live",
            "Konto na zamówienie": "custom"
        }
    },

    "Zgłoszenia": {
        "emoji": "🚨",
        "prefix": "zgloszenie",
        "category_id": REPORTS_CATEGORY_ID,
        "subcategories": {
            "Zgłoś użytkownika": "uzytkownik",
            "Zgłoś scam": "scam",
            "Inne zgłoszenie": "inne"
        }
    },

    "Pytanie / Błąd": {
        "emoji": "❓",
        "prefix": "problem",
        "category_id": QUESTIONS_ERRORS_CATEGORY_ID,
        "subcategories": {
            "Pytanie": "pytanie",
            "Błąd serwera": "serwer",
            "Problem z botem": "bot",
            "Inne": "inne"
        }
    },

    "Inne": {
        "emoji": "📌",
        "prefix": "inne",
        "category_id": OTHER_CATEGORY_ID,
        "subcategories": {
            "Współpraca": "wspolpraca",
            "Propozycja": "propozycja",
            "Inne": "inne"
        }
    }
}


SUBCATEGORY_MESSAGES = {

    # ZAMÓWIENIA

    "Pytanie dotyczące zamówienia": (
        "**Pytanie dotyczące zamówienia**\n"
        "Opisz swoje pytanie dotyczące zamówienia."
    ),

    "Kupno konta NFA ze stock": (
        "**Kupno konta NFA**\n"
        "Podaj numer zamówienia produktu, który chcesz kupić.\n"
        f"Numer zamówienia znajdziesz obok produktu na <#{STOCK_CHANNEL_ID}>."
    ),

    "Kupno konta FA ze stock": (
        "**Kupno konta FA**\n"
        "Podaj numer zamówienia produktu, który chcesz kupić.\n"
        f"Numer zamówienia znajdziesz obok produktu na <#{STOCK_CHANNEL_ID}>."
    ),

    "Kupno konta z live": (
        "**Kupno konta z live**\n"
        "Podaj nazwę lub numer produktu, który chcesz kupić z live."
    ),

    "Konto na zamówienie": (
        "**Konto na zamówienie**\n"
        "Opisz dokładnie, jakiego konta potrzebujesz."
    ),

    # ZGŁOSZENIA

    "Zgłoś użytkownika": (
        "**Zgłoszenie użytkownika**\n"
        "Podaj osobę, którą chcesz zgłosić, oraz dokładnie opisz sytuację. "
        "Dodaj dowody, jeśli je posiadasz."
    ),

    "Zgłoś scam": (
        "**Zgłoszenie scamu**\n"
        "Opisz sytuację i dodaj wszystkie posiadane dowody."
    ),

    "Inne zgłoszenie": (
        "**Zgłoszenie**\n"
        "Opisz dokładnie, czego dotyczy zgłoszenie i dodaj dowody, jeśli je posiadasz."
    ),

    # PYTANIE / BŁĄD

    "Pytanie": (
        "**Pytanie**\n"
        "Opisz dokładnie swoje pytanie."
    ),

    "Błąd serwera": (
        "**Błąd serwera**\n"
        "Opisz dokładnie występujący błąd i dodaj dowody, jeśli je posiadasz."
    ),

    "Problem z botem": (
        "**Problem z botem**\n"
        "Opisz dokładnie problem z botem i dodaj dowody, jeśli je posiadasz."
    ),

    "Inne": (
        "**Pytanie / Problem**\n"
        "Opisz dokładnie, w czym potrzebujesz pomocy."
    ),

    # INNE

    "Współpraca": (
        "**Współpraca**\n"
        "Opisz, czego ma dotyczyć współpraca i co masz na myśli."
    ),

    "Propozycja": (
        "**Propozycja**\n"
        "Opisz dokładnie swoją propozycję."
    )
}


def count_open_tickets(user_id):

    user_id = str(user_id)

    return sum(
        1
        for ticket in tickets_data.values()
        if str(ticket.get("author_id")) == user_id
    )


def get_ticket_category(category_name):

    info = CATEGORY_INFO.get(
        category_name
    )

    if info is None:
        return None

    return bot.get_channel(
        info["category_id"]
    )


def build_ticket_name(
    category_name,
    member,
    subcategory=None
):

    info = CATEGORY_INFO[
        category_name
    ]

    sub_slug = info["subcategories"].get(
        subcategory,
        "inne"
    )

    safe_name = re.sub(
        r"[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ_-]",
        "-",
        member.display_name.lower()
    )

    safe_name = safe_name.strip(
        "-"
    )

    if not safe_name:
        safe_name = str(
            member.id
        )

    return (
        f"{info['emoji']}・"
        f"{info['prefix']}-"
        f"{sub_slug}-"
        f"{safe_name}"
    )


# =========================================================
# NORMAL TICKETS
# =========================================================

async def create_ticket(
    interaction,
    category_name,
    subcategory=None
):

    guild = interaction.guild
    member = interaction.user

    if guild is None:
        return

    if count_open_tickets(member.id) >= 2:

        await interaction.response.send_message(
            "You already have 2 open tickets.",
            ephemeral=True
        )

        return

    category = get_ticket_category(
        category_name
    )

    if category is None:

        await interaction.response.send_message(
            "Ticket category not found.",
            ephemeral=True
        )

        return

    ticket_name = build_ticket_name(
        category_name,
        member,
        subcategory
    )

    owner_role = guild.get_role(
        OWNER_ROLE_ID
    )

    tt_mod_role = guild.get_role(
        TT_MOD_ROLE_ID
    )

    overwrites = {

        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True
        )
    }

    if owner_role is not None:

        overwrites[owner_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True
        )

    if tt_mod_role is not None:

        overwrites[tt_mod_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True
        )

    try:

        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            reason="Ticket created"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "I do not have permission to create the ticket.",
            ephemeral=True
        )

        return

    now = datetime.now(
        timezone.utc
    )

    tickets_data[str(channel.id)] = {
        "author_id": member.id,
        "author_name": str(member),
        "category": category_name,
        "subcategory": subcategory,
        "opened_at": now.isoformat()
    }

    save_json(
        TICKETS_FILE,
        tickets_data
    )

    await interaction.response.send_message(
        f"Ticket created: {channel.mention}",
        ephemeral=True
    )

    await channel.send(
        "Ticket created successfully. Please reply to the message below."
    )

    message_data = SUBCATEGORY_MESSAGES.get(
        subcategory
    )

    if message_data is None:

        if category_name == "Zamówienia":

            description = (
                "**Zamówienie**\n"
                "Opisz dokładnie, czego potrzebujesz."
            )

        elif category_name == "Zgłoszenia":

            description = (
                "**Zgłoszenie**\n"
                "Opisz dokładnie sytuację i dodaj dowody, jeśli je posiadasz."
            )

        elif category_name == "Pytanie / Błąd":

            description = (
                "**Pytanie / Problem**\n"
                "Opisz dokładnie, w czym potrzebujesz pomocy."
            )

        else:

            description = (
                "**Inne**\n"
                "Opisz dokładnie, w czym potrzebujesz pomocy."
            )

    else:

        title, text = message_data

        description = (
            f"{title}\n"
            f"{text}"
        )

    embed = discord.Embed(
        title="🎫 Ticket",
        description=description,
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed,
        view=TicketView()
    )

    await channel.send(
        member.mention
    )


# =========================================================
# TICKET PANEL
# =========================================================

class TicketPanelView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Create Ticket",
        emoji="🎟️",
        style=discord.ButtonStyle.success,
        custom_id="ticket_create"
    )
    async def create_ticket_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            view=MainCategoryView(),
            ephemeral=True
        )


class MainCategoryView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=120
        )

        self.select = discord.ui.Select(
            placeholder="Choose a ticket category",
            custom_id="ticket_main_category",
            options=[
                discord.SelectOption(
                    label="Zamówienia",
                    emoji="🛒",
                    value="Zamówienia"
                ),
                discord.SelectOption(
                    label="Zgłoszenia",
                    emoji="🚨",
                    value="Zgłoszenia"
                ),
                discord.SelectOption(
                    label="Pytanie / Błąd",
                    emoji="❓",
                    value="Pytanie / Błąd"
                ),
                discord.SelectOption(
                    label="Inne",
                    emoji="📌",
                    value="Inne"
                )
            ]
        )

        self.select.callback = self.category_selected

        self.add_item(
            self.select
        )

    async def category_selected(
        self,
        interaction: discord.Interaction
    ):

        category = self.select.values[0]

        await interaction.response.edit_message(
            content=None,
            view=SubcategoryView(
                category
            )
        )


class SubcategoryView(discord.ui.View):

    def __init__(
        self,
        category_name
    ):

        super().__init__(
            timeout=120
        )

        self.category_name = category_name

        subcategories = CATEGORY_INFO[
            category_name
        ]["subcategories"]

        options = []

        for name in subcategories:

            options.append(
                discord.SelectOption(
                    label=name,
                    value=name
                )
            )

        self.select = discord.ui.Select(
            placeholder="Choose a subcategory",
            options=options
        )

        self.select.callback = self.subcategory_selected

        self.add_item(
            self.select
        )

        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_back"
        )

        back_button.callback = self.back

        self.add_item(
            back_button
        )

    async def subcategory_selected(
        self,
        interaction: discord.Interaction
    ):

        subcategory = self.select.values[0]

        await create_ticket(
            interaction,
            self.category_name,
            subcategory
        )

    async def back(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.edit_message(
            content=None,
            view=MainCategoryView()
        )


# =========================================================
# TICKET CLOSE
# =========================================================

class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild

        if guild is None:
            return

        owner_role = guild.get_role(
            OWNER_ROLE_ID
        )

        if (
            owner_role is None
            or owner_role not in interaction.user.roles
        ):

            await interaction.response.send_message(
                "Only the Owner can close this ticket.",
                ephemeral=True
            )

            return

        channel = interaction.channel

        if channel is None:
            return

        ticket_info = tickets_data.get(
            str(channel.id)
        )

        if ticket_info is None:

            await interaction.response.send_message(
                "Ticket data could not be found.",
                ephemeral=True
            )

            return

        opened_at = datetime.fromisoformat(
            ticket_info["opened_at"]
        )

        closed_at = datetime.now(
            timezone.utc
        )

        transcript_lines = []

        transcript_lines.append(
            "Uzi Shop Ticket Transcript"
        )

        transcript_lines.append(
            "========================================"
        )

        transcript_lines.append(
            f"Channel: {channel.name}"
        )

        transcript_lines.append(
            f"Opened by: {ticket_info['author_name']}"
        )

        transcript_lines.append(
            f"Opened at: {opened_at.strftime('%d.%m.%Y %H:%M:%S UTC')}"
        )

        transcript_lines.append(
            f"Closed by: {interaction.user}"
        )

        transcript_lines.append(
            f"Closed at: {closed_at.strftime('%d.%m.%Y %H:%M:%S UTC')}"
        )

        transcript_lines.append(
            f"Category: {ticket_info['category']}"
        )

        if ticket_info.get("subcategory"):

            transcript_lines.append(
                f"Subcategory: {ticket_info['subcategory']}"
            )

        transcript_lines.append(
            "========================================"
        )

        transcript_lines.append("")

        async for message in channel.history(
            limit=None,
            oldest_first=True
        ):

            timestamp = message.created_at.strftime(
                "%d.%m.%Y %H:%M:%S UTC"
            )

            transcript_lines.append(
                f"[{timestamp}] {message.author} ({message.author.id}):"
            )

            if message.content:

                transcript_lines.append(
                    message.content
                )

            if message.attachments:

                for attachment in message.attachments:

                    transcript_lines.append(
                        f"Attachment: {attachment.url}"
                    )

            transcript_lines.append("")

        transcript_text = "\n".join(
            transcript_lines
        )

        transcript_file = discord.File(
            io.BytesIO(
                transcript_text.encode("utf-8")
            ),
            filename=(
                f"ticket-"
                f"{closed_at.strftime('%d%m%y')}-"
                f"{channel.id}.txt"
            )
        )

        logs_channel = guild.get_channel(
            TICKET_LOGS_CHANNEL_ID
        )

        if logs_channel is not None:

            await logs_channel.send(
                content=(
                    f"Ticket transcript: **{channel.name}**\n"
                    f"Opened by: {ticket_info['author_name']}\n"
                    f"Closed by: {interaction.user}"
                ),
                file=transcript_file
            )

        await interaction.response.send_message(
            "Ticket closed. This channel will be deleted in 15 seconds."
        )

        button.disabled = True

        try:

            await interaction.message.edit(
                view=self
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException
        ):
            pass

        await asyncio.sleep(
            15
        )

        tickets_data.pop(
            str(channel.id),
            None
        )

        save_json(
            TICKETS_FILE,
            tickets_data
        )

        try:

            await channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )

        except (
            discord.Forbidden,
            discord.NotFound
        ):
            pass


# =========================================================
# TICKET COMMAND
# =========================================================

@bot.command()
@is_owner()
async def ticket(ctx):

    channel = bot.get_channel(
        TICKET_PANEL_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Ticket panel channel not found."
        )

        return

    embed = discord.Embed(
        title="Stwórz ticket",
        description=(
            "Wybierz kategorię poniżej, aby utworzyć ticket"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed,
        view=TicketPanelView()
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# TICKET RULES
# =========================================================

@bot.command()
async def zasadyticket(ctx):

    channel = bot.get_channel(
        TICKET_RULES_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Ticket rules channel not found."
        )

        return

    embed = discord.Embed(
        title="REGULAMIN TICKETÓW",
        description=(
            "**01 ・ REALIZACJA ZAMÓWIENIA**\n"
            "Zamówienie zostanie dostarczone w ciągu **24 godzin od zakupu**\n\n"

            "**02 ・ ODPOWIEDZIALNOŚĆ**\n"
            "Po sprzedaży konta **nie ponosimy odpowiedzialności za jego dalsze działanie**\n"
            "Nie odpowiadamy za blokady, odebranie konta przez właściciela ani inne problemy powstałe po sprzedaży\n\n"

            "**03 ・ TICKETY**\n"
            "Wszystkie sprawy dotyczące zamówień, współpracy lub innych problemów należy zgłaszać **tylko i wyłącznie przez ticket**\n\n"

            "**04 ・ ZAMYKANIE TICKETÓW**\n"
            "Ticket __może zostać zamknięty__, jeśli:\n"
            "• nie odpowiadasz przez **24 godziny**\n"
            "• po zakupie nie wyślesz **legitki w ciągu 1 godziny**\n"
            "• otworzysz ticket i nie opiszesz sprawy przez **1 godzinę**\n"
            "• otworzysz ticket w **nieodpowiedniej kategorii**\n\n"

            "_(Przykład: chcesz współpracę, ale wybierasz ticket dotyczący zamówienia. Czytanie nie jest trudne)_\n\n"

            "**05 ・ KARY**\n"
            "Za niestosowanie się do regulaminu mogą zostać nałożone **kary według naszego uznania**\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "**Dokonując zakupu lub otwierając ticket, potwierdzasz, że zapoznałeś się z regulaminem i go akceptujesz.**\n\n"

            "**Uzi Stock**"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# REGULAMIN
# =========================================================

@bot.command()
@is_owner()
async def regulamin(ctx):

    channel = bot.get_channel(
        REGULAMIN_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Regulamin channel not found."
        )

        return

    embed = discord.Embed(
        title="REGULAMIN SERWERA",
        description=(
            "**01 ・ ZACHOWANIE**\n"
            "Zakaz wyzywania i prowokowania\n"
            "Szanuj innych użytkowników i administrację\n\n"

            "**02 ・ SPAM**\n"
            "Zakaz spamu, floodu i celowego zaśmiecania kanałów\n\n"

            "**03 ・ REKLAMY**\n"
            "Zakaz reklamowania innych serwerów, sklepów i usług bez zgody administracji\n\n"

            "**04 ・ OSZUSTWA**\n"
            "Zakaz scamów, wyłudzeń i prób oszukiwania innych użytkowników\n\n"

            "**05 ・ NSFW**\n"
            "Zakaz treści NSFW i nieodpowiednich materiałów\n\n"

            "**06 ・ KARY**\n"
            "Za łamanie regulaminu mogą zostać nałożone kary według uznania administracji\n\n"

            "**07 ・ BŁĘDY**\n"
            "Wykorzystywanie błędów serwera lub bota w celu uzyskania korzyści jest zabronione"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# FAQ
# =========================================================

@bot.command()
@is_owner()
async def faq(ctx):

    channel = bot.get_channel(
        FAQ_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "FAQ channel not found."
        )

        return

    embed = discord.Embed(
        description=(
            "## **01 ・INFORMACJE**\n"
            f"• <#{REGULAMIN_CHANNEL_ID}>  → zasady serwera\n"
            f"• <#{TICKET_RULES_CHANNEL_ID}>  → zasady dotyczące ticketów\n"
            f"• <#{FAQ_CHANNEL_ID}>  → tutaj jesteś\n"
            f"• <#{PAYMENT_CHANNEL_ID}>  → dostępne metody płatności\n"
            f"• <#{SOCIALS_CHANNEL_ID}>  → nasze social media\n"
            f"• <#{1546579824401977364}>  → lista zaufanych klientów i osób\n\n"

            "## **02 ・OGŁOSZENIA**\n"
            "• <#1546579637709312121>  → ważne informacje i aktualizacje\n"
            f"• <#{LIVE_CHANNEL_ID}>  → informacje o live i powiadomienia\n"
            f"• <#{GIVEAWAY_CHANNEL_ID}>  → informacje o giveawayach\n\n"

            "## **03 ・COMMUNITY**\n"
            f"• <#{COMMUNITY_CHAT_CHANNEL_ID}>  → rozmowy użytkowników\n"
            f"• <#{LEVELS_CHANNEL_ID}>  → informacje o levelach i expie\n"
            f"• <#{INVITES_CHANNEL_ID}>  → informacje o zaproszeniach\n\n"

            "## **04 ・SKLEP**\n"
            f"• <#{STOCK_CHANNEL_ID}>  → dostępne konta nfa\n"
            f"• <#{TICKET_PANEL_CHANNEL_ID}>  → zakup lub pomoc\n"
            f"• <#{LEGITCHECK_CHANNEL_ID}>  → legitchecki"
        ),
        color=EMBED_COLOR
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# SERVER PERMISSIONS
# =========================================================

async def set_everyone_hidden(channel):

    everyone = channel.guild.default_role

    try:

        await channel.set_permissions(
            everyone,
            view_channel=False,
            send_messages=False,
            connect=False,
            speak=False
        )

    except discord.Forbidden:
        pass


async def set_verified_view(
    channel,
    verified_role
):

    try:

        await channel.set_permissions(
            verified_role,
            view_channel=True
        )

    except discord.Forbidden:
        pass


async def set_owner_access(
    channel,
    owner_role
):

    try:

        await channel.set_permissions(
            owner_role,
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
            connect=True,
            speak=True
        )

    except discord.Forbidden:
        pass


async def hide_category_completely(category):

    await set_everyone_hidden(
        category
    )

    for channel in category.channels:

        await set_everyone_hidden(
            channel
        )


async def apply_server_permissions(guild):

    everyone = guild.default_role

    verified_role = guild.get_role(
        VERIFIED_ROLE_ID
    )

    owner_role = guild.get_role(
        OWNER_ROLE_ID
    )

    tt_mod_role = guild.get_role(
        TT_MOD_ROLE_ID
    )

    if verified_role is None:
        return

    # General categories
    for category in guild.categories:

        if category.id in TICKET_CATEGORY_IDS:
            continue

        if category.id == BLACKLIST_CATEGORY_ID:
            continue

        await hide_category_completely(
            category
        )

        try:

            await category.set_permissions(
                verified_role,
                view_channel=True
            )

        except discord.Forbidden:
            pass

        if owner_role is not None:

            await set_owner_access(
                category,
                owner_role
            )

        for channel in category.channels:

            if channel.id == VERIFICATION_CHANNEL_ID:
                continue

            await set_verified_view(
                channel,
                verified_role
            )

            if owner_role is not None:

                await set_owner_access(
                    channel,
                    owner_role
                )

    # Community
    community_category = guild.get_channel(
        COMMUNITY_CATEGORY_ID
    )

    if community_category is not None:

        await hide_category_completely(
            community_category
        )

        await set_verified_view(
            community_category,
            verified_role
        )

        if owner_role is not None:

            await set_owner_access(
                community_category,
                owner_role
            )

        for channel in community_category.channels:

            await set_everyone_hidden(
                channel
            )

            await set_verified_view(
                channel,
                verified_role
            )

            if owner_role is not None:

                await set_owner_access(
                    channel,
                    owner_role
                )

    # Voice
    voice_category = guild.get_channel(
        VOICE_CATEGORY_ID
    )

    if voice_category is not None:

        await hide_category_completely(
            voice_category
        )

        await set_verified_view(
            voice_category,
            verified_role
        )

        if owner_role is not None:

            await set_owner_access(
                voice_category,
                owner_role
            )

        for channel in voice_category.channels:

            await set_everyone_hidden(
                channel
            )

            await set_verified_view(
                channel,
                verified_role
            )

            if owner_role is not None:

                await set_owner_access(
                    channel,
                    owner_role
                )

    # Information
    information_category = guild.get_channel(
        INFORMATION_CATEGORY_ID
    )

    if information_category is not None:

        try:

            await information_category.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False
            )

            await information_category.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if owner_role is not None:

                await information_category.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass

        for channel in information_category.channels:

            try:

                await channel.set_permissions(
                    everyone,
                    view_channel=False,
                    send_messages=False
                )

                await channel.set_permissions(
                    verified_role,
                    view_channel=True,
                    send_messages=False
                )

                if owner_role is not None:

                    await channel.set_permissions(
                        owner_role,
                        view_channel=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True
                    )

            except discord.Forbidden:
                pass

    # Live
    live_channel = guild.get_channel(
        LIVE_CHANNEL_ID
    )

    if live_channel is not None:

        try:

            await live_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False
            )

            await live_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if tt_mod_role is not None:

                await live_channel.set_permissions(
                    tt_mod_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

            if owner_role is not None:

                await live_channel.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass

    # Shop
    shop_category = guild.get_channel(
        SHOP_CATEGORY_ID
    )

    if shop_category is not None:

        try:

            await shop_category.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False
            )

            await shop_category.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if owner_role is not None:

                await shop_category.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass

        for channel in shop_category.channels:

            try:

                await channel.set_permissions(
                    everyone,
                    view_channel=False,
                    send_messages=False
                )

                await channel.set_permissions(
                    verified_role,
                    view_channel=True,
                    send_messages=False
                )

                if owner_role is not None:

                    await set_owner_access(
                        channel,
                        owner_role
                    )

            except discord.Forbidden:
                pass

    # Levels info channel
    levels_channel = guild.get_channel(
        LEVELS_CHANNEL_ID
    )

    if levels_channel is not None:

        try:

            await levels_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False
            )

            await levels_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if owner_role is not None:

                await levels_channel.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass

    # Invites info channel
    invites_channel = guild.get_channel(
        INVITES_CHANNEL_ID
    )

    if invites_channel is not None:

        try:

            await invites_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False
            )

            await invites_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if owner_role is not None:

                await invites_channel.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass

    # Verification
    verification_channel = guild.get_channel(
        VERIFICATION_CHANNEL_ID
    )

    if verification_channel is not None:

        try:

            await verification_channel.set_permissions(
                everyone,
                view_channel=True,
                send_messages=False,
                read_message_history=True
            )

            await verification_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False
            )

            if owner_role is not None:

                await verification_channel.set_permissions(
                    owner_role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        except discord.Forbidden:
            pass


@bot.command()
@is_owner()
async def setpermissions(ctx):

    await apply_server_permissions(
        ctx.guild
    )

    await ctx.send(
        "Server permissions have been configured successfully.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# READY
# =========================================================

views_added = False


@bot.event
async def on_ready():

    global views_added

    if not views_added:

        bot.add_view(
            VerifyView()
        )

        bot.add_view(
            TicketPanelView()
        )

        bot.add_view(
            TicketView()
        )

        views_added = True

    print(
        f"Logged in as {bot.user}"
    )

    print(
        f"Connected to {len(bot.guilds)} server(s)"
    )


# =========================================================
# TOKEN CHECK
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "Bot token is not set."
    )


# =========================================================
# RUN
# =========================================================

bot.run(
    TOKEN
)