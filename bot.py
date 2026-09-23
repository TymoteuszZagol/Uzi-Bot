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
EMBED_COLOR = discord.Color(0x279A08)

STAFF_ROLE_ID = 1546584318615355403
VERIFIED_ROLE_ID = 1546585369036718180
TT_MOD_ROLE_ID = 1546584450765299864
TECHNIK_ROLE_ID = 1551677652321046721
ORDER_PING_ROLE_ID = 1551678224734359595

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

# Kategorie ticketów
PURCHASES_CATEGORY_ID = 1546963814854041601
REPORTS_CATEGORY_ID = 1546963924572971009
QUESTIONS_ERRORS_CATEGORY_ID = 1551661373040365679
OTHER_CATEGORY_ID = 1546964017032069210

TICKET_CATEGORY_IDS = {
    PURCHASES_CATEGORY_ID,
    REPORTS_CATEGORY_ID,
    QUESTIONS_ERRORS_CATEGORY_ID,
    OTHER_CATEGORY_ID,
}

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
    help_command=None,
)


# =========================================================
# PLIKI JSON
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
                ensure_ascii=False,
            )
    except OSError as exc:
        print(f"Nie udało się utworzyć pliku {filename}: {exc}")


def load_json(filename, default):
    if not os.path.exists(filename):
        initialize_data_file(filename, default)
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
                ensure_ascii=False,
            )
    except OSError as exc:
        print(f"Nie udało się zapisać pliku {filename}: {exc}")


tickets_data = load_json(TICKETS_FILE, {})


# =========================================================
# UPRAWNIENIA
# =========================================================

def has_role(member, role_id):
    return any(role.id == role_id for role in member.roles)


def is_staff_member(member):
    return (
        has_role(member, STAFF_ROLE_ID)
        or has_role(member, TT_MOD_ROLE_ID)
        or has_role(member, TECHNIK_ROLE_ID)
    )


def command_check(role_ids):
    async def predicate(ctx):
        if ctx.guild is None:
            return False

        return any(
            has_role(ctx.author, role_id)
            for role_id in role_ids
        )

    return commands.check(predicate)


staff_only = command_check({
    STAFF_ROLE_ID,
    TECHNIK_ROLE_ID,
})

staff_mod_only = command_check({
    STAFF_ROLE_ID,
    TT_MOD_ROLE_ID,
    TECHNIK_ROLE_ID,
})


# =========================================================
# WERYFIKACJA
# =========================================================

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Zweryfikuj",
        style=discord.ButtonStyle.success,
        custom_id="verify_button",
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        if guild is None:
            return

        role = guild.get_role(VERIFIED_ROLE_ID)

        if role is None:
            await interaction.response.send_message(
                "Nie znaleziono roli użytkownika.",
                ephemeral=True,
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "Jesteś już zweryfikowany.",
                ephemeral=True,
            )
            return

        try:
            await interaction.user.add_roles(
                role,
                reason="Weryfikacja użytkownika",
            )

            await interaction.response.send_message(
                "Pomyślnie się zweryfikowałeś.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot nie ma uprawnień do nadania roli użytkownika.",
                ephemeral=True,
            )


@bot.command(name="weryfikacja")
@staff_only
async def weryfikacja(ctx):
    channel = bot.get_channel(VERIFICATION_CHANNEL_ID)

    if channel is None:
        await ctx.send("Nie znaleziono kanału weryfikacji.")
        return

    embed = discord.Embed(
        title="Weryfikacja",
        description="Kliknij przycisk poniżej, aby się zweryfikować.",
        color=EMBED_COLOR,
    )

    await channel.send(
        embed=embed,
        view=VerifyView(),
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# PŁATNOŚCI
# =========================================================

@bot.command(name="payments")
@staff_only
async def payments(ctx):
    channel = bot.get_channel(PAYMENT_CHANNEL_ID)

    if channel is None:
        await ctx.send("Nie znaleziono kanału płatności.")
        return

    embed = discord.Embed(
        description=(
            "**Metody płatności:**\n"
            "BLIK przelew/kod <:blik1:1546610208388808784>\n"
            "(ewentualnie przelew krajowy)\n\n"
            "⚠️ **Paysafecard nie jest akceptowany**"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(embed=embed)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# MEDIA
# =========================================================

@bot.command(name="media")
@staff_only
async def media(ctx):
    channel = bot.get_channel(SOCIALS_CHANNEL_ID)

    if channel is None:
        await ctx.send("Nie znaleziono kanału social media.")
        return

    embed = discord.Embed(
        title="Nasze media",
        description=(
            "<:tt:1546623179047305307> **TikTok:** "
            "[uzi.02_](https://www.tiktok.com/@uzi.02_)\n"
            "<:tg:1546623148563107973> **Telegram:** "
            "[uzigoat](https://t.me/uzigoat)"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(embed=embed)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# CLEAR
# =========================================================

@bot.command(name="clear")
@staff_mod_only
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
                    arg,
                )
            except commands.BadArgument:
                await ctx.send(
                    "Nie znaleziono użytkownika.",
                    delete_after=3,
                )
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

            if (
                isinstance(amount, int)
                and deleted_count >= amount
            ):
                break

    except discord.Forbidden:
        await ctx.send(
            "Bot nie ma uprawnień do usuwania wiadomości.",
            delete_after=4,
        )


# =========================================================
# MUTE
# =========================================================

@bot.command(name="mute")
@staff_mod_only
async def mute(ctx, member: discord.Member, duration: str):
    if member == ctx.author:
        await ctx.send(
            "Nie możesz wyciszyć siebie.",
            delete_after=3,
        )
        return

    if member == ctx.guild.me:
        await ctx.send(
            "Nie mogę wyciszyć siebie.",
            delete_after=3,
        )
        return

    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        duration.lower(),
    )

    if not match:
        await ctx.send(
            "Nieprawidłowy czas. Użyj np. 5s, 10m, 2h albo 3d.",
            delete_after=4,
        )
        return

    value = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    seconds = value * multipliers[unit]

    if seconds > 28 * 86400:
        await ctx.send(
            "Maksymalny czas timeoutu to 28 dni.",
            delete_after=4,
        )
        return

    if member.top_role >= ctx.author.top_role:
        await ctx.send(
            "Nie możesz wyciszyć osoby z równą lub wyższą rolą.",
            delete_after=4,
        )
        return

    bot_member = ctx.guild.me

    if bot_member is None:
        return

    if member.top_role >= bot_member.top_role:
        await ctx.send(
            "Bot nie może wyciszyć osoby z równą lub wyższą rolą od swojej.",
            delete_after=4,
        )
        return

    try:
        await member.timeout(
            timedelta(seconds=seconds),
            reason=f"Wyciszenie przez {ctx.author}",
        )

        await ctx.send(
            f"{member.mention} został wyciszony na **{duration}**.",
            delete_after=4,
        )

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await ctx.send(
            "Bot nie ma uprawnień do timeoutu tej osoby.",
            delete_after=4,
        )


# =========================================================
# NAGRODY ZA ZAPROSZENIA
# =========================================================

@bot.command(name="invites")
@staff_only
async def invites(ctx):
    embed = discord.Embed(
        title="🎁 • NAGRODY ZA ZAPROSZENIA",
        description=(
            "Każde 10 zaproszeń = 10 zł do wydania na naszym serwerze"
        ),
        color=EMBED_COLOR,
    )

    await ctx.send(embed=embed)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# MYSTERY BOXY
# =========================================================

@bot.command(name="mysterybox")
@staff_only
async def mysterybox(ctx):
    channel = bot.get_channel(STOCK_CHANNEL_ID)

    if channel is None:
        await ctx.send(
            "Nie znaleziono kanału stock.",
            delete_after=4,
        )
        return

    embed = discord.Embed(
        title="🎁 MYSTERY BOXY",
        description=(
            "**Mystery Box** to paczka losowych kont **NFA** "
            "wybranych z naszej dostępnej puli. Każdy box jest niespodzianką.\n\n"
            
            "📦 **MYSTERY BOX・x5** → **5x kont NFA** • 💰 **50 PLN**\n"
            "📦 **MYSTERY BOX・x10** → **10x kont NFA + 1 BONUSOWE** • 💰 **100 PLN**\n"
            "📦 **MYSTERY BOX・x15** → **15x kont NFA + 2 BONUSOWE** • 💰 **150 PLN**\n"
            "📦 **MYSTERY BOX・x20** → **20x kont NFA + 3 BONUSOWE** • 💰 **200 PLN**\n\n"
            
            "🎲 **Im większy box, tym więcej bonusowych kont otrzymujesz**"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(embed=embed)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# TICKETY
# =========================================================

CATEGORY_INFO = {
    "Zamówienia": {
        "category_id": PURCHASES_CATEGORY_ID,
        "subcategories": {
            "Pytanie dotyczące zamówienia": {
                "name": "pytanie",
                "message": (
                    "**Pytanie dotyczące zamówienia**\n"
                    "Opisz dokładnie, czego potrzebujesz."
                ),
                "ping_role": True,
            },
            "Kupno konta NFA ze stock": {
                "name": "nfa",
                "message": (
                    "**Kupno konta NFA ze stock**\n"
                    "Napisz, jakie konto NFA chcesz kupić."
                ),
                "ping_role": False,
            },
            "Kupno konta FA ze stock": {
                "name": "fa",
                "message": (
                    "**Kupno konta FA ze stock**\n"
                    "Napisz, jakie konto FA chcesz kupić."
                ),
                "ping_role": False,
            },
            "Kupno konta z live": {
                "name": "live",
                "message": (
                    "**Kupno konta z live**\n"
                    "Napisz, jakie konto chcesz kupić z live."
                ),
                "ping_role": False,
            },
            "Konto na zamówienie": {
                "name": "custom",
                "message": (
                    "**Konto na zamówienie**\n"
                    "Opisz dokładnie, jakie konto chcesz zamówić."
                ),
                "ping_role": False,
            },
        },
    },

    "Zgłoszenia": {
        "category_id": REPORTS_CATEGORY_ID,
        "subcategories": {
            "Zgłoś użytkownika": {
                "name": "uzytkownik",
                "message": (
                    "**Zgłoś użytkownika**\n"
                    "Opisz, kogo chcesz zgłosić i dodaj dowody, "
                    "jeśli je posiadasz."
                ),
                "ping_role": True,
            },
            "Zgłoś scam": {
                "name": "scam",
                "message": (
                    "**Zgłoś scam**\n"
                    "Opisz dokładnie sytuację i dodaj dowody."
                ),
                "ping_role": True,
            },
            "Inne zgłoszenie": {
                "name": "inne",
                "message": (
                    "**Inne zgłoszenie**\n"
                    "Opisz dokładnie, czego dotyczy zgłoszenie."
                ),
                "ping_role": True,
            },
        },
    },

    "Pytanie / Błąd": {
        "category_id": QUESTIONS_ERRORS_CATEGORY_ID,
        "subcategories": {
            "Pytanie": {
                "name": "pytanie",
                "message": (
                    "**Pytanie**\n"
                    "Opisz dokładnie swoje pytanie."
                ),
                "ping_role": True,
            },
            "Błąd serwera": {
                "name": "serwer",
                "message": (
                    "**Błąd serwera**\n"
                    "Opisz dokładnie występujący błąd "
                    "i dodaj dowody, jeśli je posiadasz."
                ),
                "ping_role": True,
            },
            "Problem z botem": {
                "name": "bot",
                "message": (
                    "**Problem z botem**\n"
                    "Opisz dokładnie problem z botem "
                    "i dodaj dowody, jeśli je posiadasz."
                ),
                "ping_role": True,
            },
            "Inne": {
                "name": "inne",
                "message": (
                    "**Inne**\n"
                    "Opisz dokładnie, czego potrzebujesz."
                ),
                "ping_role": True,
            },
        },
    },

    "Inne": {
        "category_id": OTHER_CATEGORY_ID,
        "subcategories": {
            "Współpraca": {
                "name": "wspolpraca",
                "message": (
                    "**Współpraca**\n"
                    "Opisz, czego ma dotyczyć współpraca."
                ),
                "ping_role": True,
            },
            "Propozycja": {
                "name": "propozycja",
                "message": (
                    "**Propozycja**\n"
                    "Opisz dokładnie swoją propozycję."
                ),
                "ping_role": True,
            },
            "Inne": {
                "name": "inne",
                "message": (
                    "**Inne**\n"
                    "Opisz dokładnie, czego potrzebujesz."
                ),
                "ping_role": True,
            },
        },
    },
}


def count_open_tickets(user_id):
    user_id = str(user_id)

    return sum(
        1
        for ticket in tickets_data.values()
        if str(ticket.get("author_id")) == user_id
        and ticket.get("open", True)
    )


def get_ticket_category(category_name):
    info = CATEGORY_INFO.get(category_name)

    if info is None:
        return None

    category = bot.get_channel(info["category_id"])

    if isinstance(category, discord.CategoryChannel):
        return category

    return None


def clean_username(username):
    username = username.lower()

    username = re.sub(
        r"[^a-z0-9ąćęłńóśźż_-]",
        "-",
        username,
    )

    username = re.sub(
        r"-+",
        "-",
        username,
    )

    username = username.strip("-_")

    if not username:
        username = "uzytkownik"

    return username[:70]


def build_ticket_name(subcategory_name, member):
    subcategory_info = None

    for category in CATEGORY_INFO.values():
        if subcategory_name in category["subcategories"]:
            subcategory_info = category["subcategories"][subcategory_name]
            break

    if subcategory_info is None:
        prefix = "ticket"
    else:
        prefix = subcategory_info["name"]

    username = clean_username(member.name)

    return f"{prefix}-{username}"[:100]


def can_manage_ticket(member):
    return (
        has_role(member, STAFF_ROLE_ID)
        or has_role(member, TT_MOD_ROLE_ID)
        or has_role(member, TECHNIK_ROLE_ID)
    )


async def send_ticket_message(
    channel,
    member,
    category_name,
    subcategory_name,
):
    category_info = CATEGORY_INFO.get(category_name)

    if category_info is None:
        return

    subcategory_info = category_info["subcategories"].get(
        subcategory_name
    )

    if subcategory_info is None:
        return

    embed = discord.Embed(
        title="Ticket",
        description=subcategory_info["message"],
        color=EMBED_COLOR,
    )

    ping_content = member.mention

    if subcategory_info["ping_role"]:
        role = channel.guild.get_role(ORDER_PING_ROLE_ID)

        if role is not None:
            ping_content += f" {role.mention}"

    await channel.send(
        content=ping_content,
        embed=embed,
        view=TicketView(),
        allowed_mentions=discord.AllowedMentions(
            users=True,
            roles=True,
        ),
    )


async def create_ticket(
    interaction,
    category_name,
    subcategory_name,
):
    guild = interaction.guild
    member = interaction.user

    if guild is None:
        await interaction.response.send_message(
            "Nie udało się utworzyć ticketu.",
            ephemeral=True,
        )
        return

    if count_open_tickets(member.id) >= 1:
        await interaction.response.send_message(
            "Masz już otwarty ticket.",
            ephemeral=True,
        )
        return

    category = get_ticket_category(category_name)

    if category is None:
        await interaction.response.send_message(
            "Nie znaleziono kategorii ticketu.",
            ephemeral=True,
        )
        return

    if subcategory_name not in CATEGORY_INFO[category_name]["subcategories"]:
        await interaction.response.send_message(
            "Nie znaleziono wybranej podkategorii.",
            ephemeral=True,
        )
        return

    ticket_name = build_ticket_name(
        subcategory_name,
        member,
    )

    staff_role = guild.get_role(STAFF_ROLE_ID)
    tt_mod_role = guild.get_role(TT_MOD_ROLE_ID)
    technik_role = guild.get_role(TECHNIK_ROLE_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False,
        ),

        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
        ),
    }

    for role in (
        staff_role,
        tt_mod_role,
        technik_role,
    ):
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
            )

    try:
        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            reason="Utworzenie ticketu",
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "Bot nie ma uprawnień do utworzenia ticketu.",
            ephemeral=True,
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Nie udało się utworzyć ticketu.",
            ephemeral=True,
        )
        return

    now = datetime.now(timezone.utc)

    tickets_data[str(channel.id)] = {
        "author_id": member.id,
        "author_name": str(member),
        "category": category_name,
        "subcategory": subcategory_name,
        "opened_at": now.isoformat(),
        "open": True,
    }

    save_json(
        TICKETS_FILE,
        tickets_data,
    )

    await interaction.response.send_message(
        f"Ticket został utworzony: {channel.mention}",
        ephemeral=True,
    )

    try:
        await send_ticket_message(
            channel,
            member,
            category_name,
            subcategory_name,
        )
    except discord.HTTPException:
        pass


# =========================================================
# PANEL GŁÓWNY TICKETÓW
# =========================================================

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Stwórz ticket",
        style=discord.ButtonStyle.success,
        custom_id="ticket_create",
    )
    async def create_ticket_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Wybierz kategorię:",
            view=MainCategoryView(),
            ephemeral=True,
        )


# =========================================================
# WYBÓR KATEGORII
# =========================================================

class MainCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        self.select = discord.ui.Select(
            placeholder="Wybierz kategorię ticketu",
            custom_id="ticket_main_category",
            options=[
                discord.SelectOption(
                    label="Zamówienia",
                    emoji="🛒",
                    value="Zamówienia",
                ),
                discord.SelectOption(
                    label="Zgłoszenia",
                    emoji="🚨",
                    value="Zgłoszenia",
                ),
                discord.SelectOption(
                    label="Pytanie / Błąd",
                    emoji="❓",
                    value="Pytanie / Błąd",
                ),
                discord.SelectOption(
                    label="Inne",
                    emoji="📌",
                    value="Inne",
                ),
            ],
        )

        self.select.callback = self.category_selected
        self.add_item(self.select)

    async def category_selected(
        self,
        interaction: discord.Interaction,
    ):
        category_name = self.select.values[0]

        await interaction.response.edit_message(
            content="Wybierz podkategorię:",
            view=SubcategoryView(category_name),
        )


# =========================================================
# WYBÓR PODKATEGORII
# =========================================================

class SubcategoryView(discord.ui.View):
    def __init__(self, category_name):
        super().__init__(timeout=120)

        self.category_name = category_name

        subcategories = CATEGORY_INFO[
            category_name
        ]["subcategories"]

        options = [
            discord.SelectOption(
                label=name,
                value=name,
            )
            for name in subcategories
        ]

        self.select = discord.ui.Select(
            placeholder="Wybierz podkategorię",
            options=options,
            custom_id="ticket_subcategory",
        )

        self.select.callback = self.subcategory_selected
        self.add_item(self.select)

        back_button = discord.ui.Button(
            label="Wróć",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_back",
        )

        back_button.callback = self.back
        self.add_item(back_button)

    async def subcategory_selected(
        self,
        interaction: discord.Interaction,
    ):
        subcategory_name = self.select.values[0]

        await create_ticket(
            interaction,
            self.category_name,
            subcategory_name,
        )

    async def back(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.edit_message(
            content="Wybierz kategorię:",
            view=MainCategoryView(),
        )


# =========================================================
# ZAMYKANIE TICKETU
# =========================================================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Zamknij ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        if guild is None:
            return

        if not can_manage_ticket(interaction.user):
            await interaction.response.send_message(
                "Nie masz uprawnień do zamknięcia tego ticketu.",
                ephemeral=True,
            )
            return

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        ticket_info = tickets_data.get(
            str(channel.id)
        )

        if ticket_info is None:
            await interaction.response.send_message(
                "Nie znaleziono danych tego ticketu.",
                ephemeral=True,
            )
            return

        if not ticket_info.get("open", True):
            await interaction.response.send_message(
                "Ten ticket jest już zamykany.",
                ephemeral=True,
            )
            return

        ticket_info["open"] = False

        closed_at = datetime.now(timezone.utc)

        ticket_info["closed_by"] = interaction.user.id
        ticket_info["closed_by_name"] = str(interaction.user)
        ticket_info["closed_at"] = closed_at.isoformat()

        save_json(
            TICKETS_FILE,
            tickets_data,
        )

        await interaction.response.send_message(
            "Ticket został zamknięty. Kanał zostanie usunięty za 15 sekund."
        )

        button.disabled = True

        try:
            await interaction.message.edit(
                view=self
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

        opened_at_text = ticket_info.get(
            "opened_at",
            "Nieznana data",
        )

        try:
            opened_at = datetime.fromisoformat(
                opened_at_text
            )

            opened_at_display = opened_at.strftime(
                "%d.%m.%Y %H:%M:%S UTC"
            )

        except (ValueError, TypeError):
            opened_at_display = "Nieznana data"

        transcript_lines = [
            "UZi Shop - Transkrypcja ticketu",
            "========================================",
            f"Kanał: {channel.name}",
            f"Autor: {ticket_info.get('author_name', 'Nieznany')}",
            f"Data otwarcia: {opened_at_display}",
            f"Zamknął: {interaction.user}",
            f"Data zamknięcia: {closed_at.strftime('%d.%m.%Y %H:%M:%S UTC')}",
            f"Kategoria: {ticket_info.get('category', 'Nieznana')}",
            f"Podkategoria: {ticket_info.get('subcategory', 'Nieznana')}",
            "========================================",
            "",
        ]

        try:
            async for message in channel.history(
                limit=None,
                oldest_first=True,
            ):
                timestamp = message.created_at.strftime(
                    "%d.%m.%Y %H:%M:%S UTC"
                )

                transcript_lines.append(
                    f"[{timestamp}] {message.author} "
                    f"({message.author.id}):"
                )

                if message.content:
                    transcript_lines.append(
                        message.content
                    )

                for attachment in message.attachments:
                    transcript_lines.append(
                        f"Załącznik: {attachment.url}"
                    )

                if message.embeds:
                    transcript_lines.append(
                        "[Wiadomość zawierała osadzoną wiadomość]"
                    )

                transcript_lines.append("")

        except discord.HTTPException:
            transcript_lines.append(
                "[Nie udało się pobrać pełnej historii kanału]"
            )

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
            ),
        )

        logs_channel = guild.get_channel(
            TICKET_LOGS_CHANNEL_ID
        )

        if logs_channel is not None:
            try:
                await logs_channel.send(
                    content=(
                        f"**Transkrypcja ticketu**\n"
                        f"**Kanał:** {channel.name}\n"
                        f"**Autor:** "
                        f"{ticket_info.get('author_name', 'Nieznany')}\n"
                        f"**Zamknął:** {interaction.user}"
                    ),
                    file=transcript_file,
                )

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        await asyncio.sleep(15)

        tickets_data.pop(
            str(channel.id),
            None,
        )

        save_json(
            TICKETS_FILE,
            tickets_data,
        )

        try:
            await channel.delete(
                reason=f"Ticket zamknięty przez {interaction.user}",
            )
        except (
            discord.Forbidden,
            discord.NotFound,
            discord.HTTPException,
        ):
            pass


# =========================================================
# KOMENDA PANELU TICKETÓW
# =========================================================

@bot.command(name="ticket")
@staff_only
async def ticket(ctx):
    channel = bot.get_channel(
        TICKET_PANEL_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Nie znaleziono kanału panelu ticketów."
        )
        return

    embed = discord.Embed(
        title="Stwórz ticket",
        description=(
            "Wybierz kategorię poniżej, "
            "aby utworzyć ticket"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(
        embed=embed,
        view=TicketPanelView(),
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# REGULAMIN TICKETÓW
# =========================================================

@bot.command(name="zasadyticket")
@staff_only
async def zasadyticket(ctx):
    channel = bot.get_channel(
        TICKET_RULES_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Nie znaleziono kanału regulaminu ticketów."
        )
        return

    embed = discord.Embed(
        title="REGULAMIN TICKETÓW",
        description=(
            "**01 ・ REALIZACJA ZAMÓWIENIA**\n"
            "Zamówienie zostanie dostarczone w ciągu "
            "**24 godzin od zakupu**\n\n"

            "**02 ・ ODPOWIEDZIALNOŚĆ**\n"
            "Po sprzedaży konta **nie ponosimy odpowiedzialności "
            "za jego dalsze działanie**\n"
            "Nie odpowiadamy za blokady, odebranie konta przez "
            "właściciela ani inne problemy powstałe po sprzedaży\n\n"

            "**03 ・ TICKETY**\n"
            "Wszystkie sprawy dotyczące zamówień, współpracy "
            "lub innych problemów należy zgłaszać "
            "**tylko i wyłącznie przez ticket**\n\n"

            "**04 ・ ZAMYKANIE TICKETÓW**\n"
            "Ticket __może zostać zamknięty__, jeśli:\n"
            "• nie odpowiadasz przez **24 godziny**\n"
            "• po zakupie nie wyślesz **legitki w ciągu 1 godziny**\n"
            "• otworzysz ticket i nie opiszesz sprawy przez "
            "**1 godzinę**\n"
            "• otworzysz ticket w **nieodpowiedniej kategorii**\n\n"

            "**05 ・ KARY**\n"
            "Za niestosowanie się do regulaminu mogą zostać "
            "nałożone **kary według naszego uznania**\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "**Dokonując zakupu lub otwierając ticket, "
            "potwierdzasz, że zapoznałeś się z regulaminem "
            "i go akceptujesz.**\n\n"

            "**Uzi Stock**"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# REGULAMIN SERWERA
# =========================================================

@bot.command(name="regulamin")
@staff_only
async def regulamin(ctx):
    channel = bot.get_channel(
        REGULAMIN_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Nie znaleziono kanału regulaminu."
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
            "Zakaz reklamowania innych serwerów, sklepów "
            "i usług bez zgody administracji\n\n"

            "**04 ・ OSZUSTWA**\n"
            "Zakaz scamów, wyłudzeń i prób oszukiwania "
            "innych użytkowników\n\n"

            "**05 ・ NSFW**\n"
            "Zakaz treści NSFW i nieodpowiednich materiałów\n\n"

            "**06 ・ KARY**\n"
            "Za łamanie regulaminu mogą zostać nałożone "
            "kary według uznania administracji\n\n"

            "**07 ・ BŁĘDY**\n"
            "Wykorzystywanie błędów serwera lub bota "
            "w celu uzyskania korzyści jest zabronione"
        ),
        color=EMBED_COLOR,
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

@bot.command(name="faq")
@staff_only
async def faq(ctx):
    channel = bot.get_channel(
        FAQ_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Nie znaleziono kanału FAQ."
        )
        return

    embed = discord.Embed(
        description=(
            "## **01 ・ INFORMACJE**\n"
            f"• <#{REGULAMIN_CHANNEL_ID}> → zasady serwera\n"
            f"• <#{TICKET_RULES_CHANNEL_ID}> → zasady dotyczące ticketów\n"
            f"• <#{FAQ_CHANNEL_ID}> → tutaj jesteś\n"
            f"• <#{PAYMENT_CHANNEL_ID}> → dostępne metody płatności\n"
            f"• <#{SOCIALS_CHANNEL_ID}> → nasze social media\n"
            "• <#1546579824401977364> → lista zaufanych klientów i osób\n\n"

            "## **02 ・ OGŁOSZENIA**\n"
            "• <#1546579637709312121> → ważne informacje i aktualizacje\n"
            f"• <#{LIVE_CHANNEL_ID}> → informacje o live i powiadomienia\n"
            f"• <#{GIVEAWAY_CHANNEL_ID}> → informacje o giveawayach\n\n"

            "## **03 ・ COMMUNITY**\n"
            f"• <#{COMMUNITY_CHAT_CHANNEL_ID}> → rozmowy użytkowników\n"
            f"• <#{LEVELS_CHANNEL_ID}> → informacje o levelach i expie\n"
            f"• <#{INVITES_CHANNEL_ID}> → informacje o zaproszeniach\n\n"

            "## **04 ・ SKLEP**\n"
            f"• <#{STOCK_CHANNEL_ID}> → dostępne konta NFA\n"
            f"• <#{TICKET_PANEL_CHANNEL_ID}> → zakup lub pomoc\n"
            f"• <#{LEGITCHECK_CHANNEL_ID}> → legitchecki"
        ),
        color=EMBED_COLOR,
    )

    await channel.send(
        embed=embed
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# UPRAWNIENIA SERWERA
# =========================================================

async def set_everyone_hidden(channel):
    everyone = channel.guild.default_role

    try:
        await channel.set_permissions(
            everyone,
            view_channel=False,
            send_messages=False,
            connect=False,
            speak=False,
        )
    except discord.Forbidden:
        pass


async def set_role_access(
    channel,
    role,
    *,
    send_messages=True,
):
    if role is None:
        return

    try:
        await channel.set_permissions(
            role,
            view_channel=True,
            send_messages=send_messages,
            attach_files=send_messages,
            embed_links=send_messages,
            read_message_history=True,
            connect=True,
            speak=send_messages,
        )
    except discord.Forbidden:
        pass


async def set_verified_view(
    channel,
    verified_role,
):
    if verified_role is None:
        return

    try:
        await channel.set_permissions(
            verified_role,
            view_channel=True,
        )
    except discord.Forbidden:
        pass


async def hide_category_completely(category):
    await set_everyone_hidden(category)

    for channel in category.channels:
        await set_everyone_hidden(channel)


async def apply_server_permissions(guild):
    everyone = guild.default_role

    verified_role = guild.get_role(
        VERIFIED_ROLE_ID
    )

    staff_role = guild.get_role(
        STAFF_ROLE_ID
    )

    tt_mod_role = guild.get_role(
        TT_MOD_ROLE_ID
    )

    technik_role = guild.get_role(
        TECHNIK_ROLE_ID
    )

    if verified_role is None:
        return

    staff_roles = [
        role
        for role in (
            staff_role,
            tt_mod_role,
            technik_role,
        )
        if role is not None
    ]

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
                view_channel=True,
            )
        except discord.Forbidden:
            pass

        for role in staff_roles:
            await set_role_access(
                category,
                role,
            )

        for channel in category.channels:
            if channel.id == VERIFICATION_CHANNEL_ID:
                continue

            await set_verified_view(
                channel,
                verified_role,
            )

            for role in staff_roles:
                await set_role_access(
                    channel,
                    role,
                )

    information_category = guild.get_channel(
        INFORMATION_CATEGORY_ID
    )

    if information_category is not None:
        try:
            await information_category.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False,
            )

            await information_category.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await information_category.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass

        for channel in information_category.channels:
            try:
                await channel.set_permissions(
                    everyone,
                    view_channel=False,
                    send_messages=False,
                )

                await channel.set_permissions(
                    verified_role,
                    view_channel=True,
                    send_messages=False,
                )

                for role in staff_roles:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True,
                    )

            except discord.Forbidden:
                pass

    live_channel = guild.get_channel(
        LIVE_CHANNEL_ID
    )

    if live_channel is not None:
        try:
            await live_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False,
            )

            await live_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await live_channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass

    shop_category = guild.get_channel(
        SHOP_CATEGORY_ID
    )

    if shop_category is not None:
        try:
            await shop_category.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False,
            )

            await shop_category.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await shop_category.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass

        for channel in shop_category.channels:
            try:
                await channel.set_permissions(
                    everyone,
                    view_channel=False,
                    send_messages=False,
                )

                await channel.set_permissions(
                    verified_role,
                    view_channel=True,
                    send_messages=False,
                )

                for role in staff_roles:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True,
                    )

            except discord.Forbidden:
                pass

    levels_channel = guild.get_channel(
        LEVELS_CHANNEL_ID
    )

    if levels_channel is not None:
        try:
            await levels_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False,
            )

            await levels_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await levels_channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass

    invites_channel = guild.get_channel(
        INVITES_CHANNEL_ID
    )

    if invites_channel is not None:
        try:
            await invites_channel.set_permissions(
                everyone,
                view_channel=False,
                send_messages=False,
            )

            await invites_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await invites_channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass

    verification_channel = guild.get_channel(
        VERIFICATION_CHANNEL_ID
    )

    if verification_channel is not None:
        try:
            await verification_channel.set_permissions(
                everyone,
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

            await verification_channel.set_permissions(
                verified_role,
                view_channel=True,
                send_messages=False,
            )

            for role in staff_roles:
                await verification_channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        except discord.Forbidden:
            pass


@bot.command(name="setpermissions")
@staff_only
async def setpermissions(ctx):
    if ctx.guild is None:
        return

    await apply_server_permissions(
        ctx.guild
    )

    await ctx.send(
        "Uprawnienia serwera zostały skonfigurowane.",
        delete_after=5,
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# OBSŁUGA BŁĘDÓW
# =========================================================

@bot.event
async def on_command_error(
    ctx,
    error,
):
    if isinstance(
        error,
        commands.CommandNotFound,
    ):
        return

    if isinstance(
        error,
        (
            commands.CheckFailure,
            commands.MissingPermissions,
        ),
    ):
        await ctx.send(
            "Nie masz uprawnień do tej komendy.",
            delete_after=4,
        )
        return

    if isinstance(
        error,
        commands.MissingRequiredArgument,
    ):
        await ctx.send(
            "Brakuje wymaganych argumentów.",
            delete_after=4,
        )
        return

    if isinstance(
        error,
        commands.BadArgument,
    ):
        await ctx.send(
            "Nieprawidłowy argument.",
            delete_after=4,
        )
        return

    print(
        f"[BŁĄD KOMENDY] "
        f"{type(error).__name__}: {error}"
    )


# =========================================================
# GOTOWOŚĆ BOTA
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
        f"Zalogowano jako {bot.user}"
    )

    print(
        f"Połączono z {len(bot.guilds)} serwerami"
    )


# =========================================================
# TOKEN
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN nie jest ustawiony "
        "w zmiennych środowiskowych."
    )


# =========================================================
# URUCHOMIENIE
# =========================================================

bot.run(TOKEN)
