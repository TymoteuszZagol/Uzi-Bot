import discord
import discord.ext
import asyncio
import json
import os
import random
import re
import io
from datetime import datetime, timezone, timedelta


TOKEN = os.getenv("DISCORD_TOKEN")

PREFIX = "!"

# =========================================================
# EMBED COLOR
# =========================================================

EMBED_COLOR = discord.Color(0xFF8CB1)


# =========================================================
# IDS
# =========================================================

OWNER_ROLE_ID = 1546584318615355403
VERIFIED_ROLE_ID = 1546585369036718180
BLACKLIST_ROLE_ID = 1547265693907419266

VERIFICATION_CHANNEL_ID = 1546587855600619650
TRUST_CHANNEL_ID = 1546579824401977364
PAYMENT_CHANNEL_ID = 1546579970040533032
SOCIALS_CHANNEL_ID = 1546582618408230992

LEVELS_CHANNEL_ID = 1546580272227815674
INVITES_CHANNEL_ID = 1546580295849873568

TICKET_PANEL_CHANNEL_ID = 1546579992954273862
TICKET_LOGS_CHANNEL_ID = 1546954575989178538
TICKET_RULES_CHANNEL_ID = 1546957819515764756
STOCK_CHANNEL_ID = 1546579943478136953

INFORMATION_CATEGORY_ID = 1546577882586026185
LIVE_CHANNEL_ID = 1546579670361706586
TT_MOD_ROLE_ID = 1546584450765299864

SHOP_CATEGORY_ID = 1546580547344531506

COMMUNITY_CATEGORY_ID = 1546580572380471356
VOICE_CATEGORY_ID = 1546580607142727741

BLACKLIST_CATEGORY_ID = 1547264870733316167

TICKET_CATEGORY_IDS = [
    1546963814854041601,
    1546963863931719690,
    1546963924572971009,
    1546963979832655932,
    1546964017032069210,
    BLACKLIST_CATEGORY_ID
]


LEVEL_XP_FILE = "levels.json"
LEVEL_ROLES_FILE = "level_roles.json"
INVITES_FILE = "invites.json"
TICKETS_FILE = "tickets.json"
TRUST_FILE = "trust_votes.json"


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

def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# =========================================================
# OWNER CHECK
# =========================================================

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
                "The Verified role could not be found.",
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
                "I do not have permission to give you the Verified role.",
                ephemeral=True
            )


@bot.command()
@is_owner()
async def verification(ctx):

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
# TRUST SYSTEM
# =========================================================

trust_votes = load_json(
    TRUST_FILE,
    {
        "users": {}
    }
)

if not isinstance(trust_votes, dict):
    trust_votes = {
        "users": {}
    }

if not isinstance(
    trust_votes.get("users"),
    dict
):
    trust_votes["users"] = {}


def get_trust_counts():

    yes_count = 0
    no_count = 0

    for vote in trust_votes["users"].values():

        if vote == "yes":
            yes_count += 1

        elif vote == "no":
            no_count += 1

    return yes_count, no_count


def save_trust_votes():

    yes_count, no_count = get_trust_counts()

    trust_votes["yes"] = yes_count
    trust_votes["no"] = no_count

    save_json(
        TRUST_FILE,
        trust_votes
    )


save_trust_votes()


# =========================================================
# TRUST EMBEDS
# =========================================================

def build_trust_embed():

    embed = discord.Embed(
        title="Are we legit?",
        description=(
            "make the right choice.\n\n"
            "*Selecting \"no\" without a valid reason may result in a blacklist.*"
        ),
        color=EMBED_COLOR
    )

    embed.set_footer(
        text="Uzi Shop • Trust System"
    )

    return embed


def build_trust_confirmation_embed():

    embed = discord.Embed(
        title="Are you sure about your choice?",
        description=(
            "You selected **no**.\n\n"
            "Are you sure about your choice?\n\n"
            "If you confirm, you will be required to explain your decision "
            "in a trust review ticket."
        ),
        color=EMBED_COLOR
    )

    embed.set_footer(
        text="Uzi Shop • Trust System"
    )

    return embed


# =========================================================
# UPDATE TRUST PANEL
# =========================================================

async def update_trust_panel(guild):

    panel = trust_votes.get(
        "panel"
    )

    if not panel:
        return

    try:
        channel_id = int(
            panel["channel_id"]
        )

        message_id = int(
            panel["message_id"]
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):
        return

    channel = guild.get_channel(
        channel_id
    )

    if channel is None:
        return

    try:
        message = await channel.fetch_message(
            message_id
        )

        await message.edit(
            embed=build_trust_embed(),
            view=TrustView()
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):
        pass


# =========================================================
# TRUST CONFIRMATION
# =========================================================

class TrustConfirmationView(discord.ui.View):

    def __init__(self):
        super().__init__(
            timeout=120
        )

    @discord.ui.button(
        label="Back",
        style=discord.ButtonStyle.secondary,
        custom_id="trust_confirmation_back"
    )
    async def back(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content=None,
            embed=build_trust_embed(),
            view=TrustView()
        )

    @discord.ui.button(
        label="Yes",
        style=discord.ButtonStyle.danger,
        custom_id="trust_confirmation_yes"
    )
    async def confirm_no(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = str(
            interaction.user.id
        )

        if user_id in trust_votes["users"]:

            await interaction.response.edit_message(
                content="You have already voted.",
                embed=None,
                view=None
            )

            return

        ticket_channel = await create_blacklist_ticket(
            interaction
        )

        if ticket_channel is None:
            return

        trust_votes["users"][user_id] = "no"

        save_trust_votes()

        await interaction.response.edit_message(
            content=(
                f"Your **no** vote has been recorded.\n\n"
                f"Trust review ticket: {ticket_channel.mention}"
            ),
            embed=None,
            view=None
        )

        await update_trust_panel(
            interaction.guild
        )


# =========================================================
# TRUST MAIN VIEW
# =========================================================

class TrustView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        yes_count, no_count = get_trust_counts()

        self.yes_counter.label = (
            f"votes: {yes_count}"
        )

        self.no_counter.label = (
            f"votes: {no_count}"
        )

    @discord.ui.button(
        label="YEAHH",
        style=discord.ButtonStyle.success,
        custom_id="trust_yes",
        row=0
    )
    async def yes_vote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = str(
            interaction.user.id
        )

        if user_id in trust_votes["users"]:

            await interaction.response.send_message(
                "You have already voted.",
                ephemeral=True
            )

            return

        trust_votes["users"][user_id] = "yes"

        save_trust_votes()

        await interaction.response.send_message(
            "Your vote has been recorded.",
            ephemeral=True
        )

        await update_trust_panel(
            interaction.guild
        )

    @discord.ui.button(
        label="votes: 0",
        style=discord.ButtonStyle.secondary,
        disabled=True,
        custom_id="trust_yes_counter",
        row=1
    )
    async def yes_counter(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        pass

    @discord.ui.button(
        label="no",
        style=discord.ButtonStyle.danger,
        custom_id="trust_no",
        row=0
    )
    async def no_vote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = str(
            interaction.user.id
        )

        if user_id in trust_votes["users"]:

            await interaction.response.send_message(
                "You have already voted.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            embed=build_trust_confirmation_embed(),
            view=TrustConfirmationView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="votes: 0",
        style=discord.ButtonStyle.secondary,
        disabled=True,
        custom_id="trust_no_counter",
        row=1
    )
    async def no_counter(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        pass


# =========================================================
# TRUST COMMAND
# =========================================================

@bot.command()
@is_owner()
async def trust(ctx):

    channel = bot.get_channel(
        TRUST_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Trust channel not found."
        )
        return

    save_trust_votes()

    message = await channel.send(
        embed=build_trust_embed(),
        view=TrustView()
    )

    trust_votes["panel"] = {
        "channel_id": channel.id,
        "message_id": message.id
    }

    save_trust_votes()

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# PAYMENTS
# =========================================================

@bot.command()
@is_owner()
async def payments(ctx):

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
            "**Payment methods:** BLIK <:blik1:1546610208388808784>\n"
            "(in case of necessity, domestic bank transfer)\n\n"
            "⚠️  **Paysafecard (psc) is not accepted**"
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
# SOCIALS
# =========================================================

@bot.command()
@is_owner()
async def socials(ctx):

    channel = bot.get_channel(
        SOCIALS_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "Socials channel not found."
        )
        return

    embed = discord.Embed(
        title="My Socials",
        description=(
            "<:tt:1546623179047305307>  **TikTok:** "
            "[podpiszsie](https://www.tiktok.com/@podpiszsie)\n"
            "<:tg:1546623148563107973>  **Telegram:** "
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
@is_owner()
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

        else:
            return

        return

    if amount == "all":

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

    elif isinstance(amount, int):

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

                if deleted_count >= amount:
                    break


# =========================================================
# MUTE
# =========================================================

@bot.command()
@is_owner()
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
# LEVELING
# =========================================================

level_data = load_json(
    LEVEL_XP_FILE,
    {}
)

level_roles = load_json(
    LEVEL_ROLES_FILE,
    {}
)

xp_cooldowns = {}

MAX_LEVEL = 100


def get_total_xp_for_level(level):

    total_xp = 0

    for current_level in range(
        1,
        level
    ):

        total_xp += 50 * (
            current_level + 1
        )

    return total_xp


def get_level_from_xp(xp):

    level = 1
    total_required = 0

    while level < MAX_LEVEL:

        next_level_xp = 50 * (
            level + 1
        )

        if xp < total_required + next_level_xp:
            break

        total_required += next_level_xp
        level += 1

    return level


async def assign_level_role(
    member,
    level
):

    guild = member.guild

    old_roles = []

    for role_id in level_roles.values():

        role = guild.get_role(
            int(role_id)
        )

        if role is not None and role in member.roles:
            old_roles.append(role)

    if old_roles:

        try:
            await member.remove_roles(
                *old_roles,
                reason="Level role update"
            )

        except discord.Forbidden:
            pass

    role_id = level_roles.get(
        str(level)
    )

    if role_id is None:
        return

    role = guild.get_role(
        int(role_id)
    )

    if role is None:
        return

    try:

        await member.add_roles(
            role,
            reason=f"Reached level {level}"
        )

    except discord.Forbidden:
        pass


@bot.command()
@is_owner()
async def createroles(ctx):

    guild = ctx.guild

    if guild is None:
        return

    created = 0

    for level in range(
        1,
        MAX_LEVEL + 1
    ):

        role_name = f"lvl {level}"

        existing_role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        if existing_role is None:

            try:

                existing_role = await guild.create_role(
                    name=role_name,
                    hoist=False,
                    mentionable=False,
                    color=discord.Color.default(),
                    reason="Level system"
                )

                created += 1

            except discord.Forbidden:

                await ctx.send(
                    "I do not have permission to create roles."
                )

                return

        level_roles[str(level)] = existing_role.id

    save_json(
        LEVEL_ROLES_FILE,
        level_roles
    )

    await ctx.send(
        f"Level roles are ready. Created: **{created}**."
    )


@bot.command()
@is_owner()
async def resetlvl(ctx, member: discord.Member):

    user_id = str(
        member.id
    )

    level_data[user_id] = {
        "xp": 0,
        "level": 1
    }

    save_json(
        LEVEL_XP_FILE,
        level_data
    )

    guild = ctx.guild

    if guild is not None:

        old_roles = []

        for role_id in level_roles.values():

            role = guild.get_role(
                int(role_id)
            )

            if role is not None and role in member.roles:
                old_roles.append(role)

        if old_roles:

            try:

                await member.remove_roles(
                    *old_roles,
                    reason=f"Level reset by {ctx.author}"
                )

            except discord.Forbidden:
                pass

    await ctx.send(
        f"{member.mention}'s level has been reset to **level 1** with **0 XP**.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# INVITES
# =========================================================

invite_data = load_json(
    INVITES_FILE,
    {
        "counts": {},
        "history": {},
        "cached_invites": {}
    }
)

if "counts" not in invite_data:
    invite_data["counts"] = {}

if "history" not in invite_data:
    invite_data["history"] = {}

if "cached_invites" not in invite_data:
    invite_data["cached_invites"] = {}

save_json(
    INVITES_FILE,
    invite_data
)


async def refresh_invite_cache(guild):

    try:
        invites = await guild.invites()

    except discord.Forbidden:
        return

    invite_data["cached_invites"][str(guild.id)] = {
        invite.code: invite.uses
        for invite in invites
    }

    save_json(
        INVITES_FILE,
        invite_data
    )


def find_used_invite(
    before,
    after
):

    for code, uses in after.items():

        old_uses = before.get(
            code,
            0
        )

        if uses > old_uses:
            return code

    return None


def can_count_invite(
    guild_id,
    member_id
):

    history = invite_data["history"].get(
        str(member_id),
        []
    )

    now = datetime.now(
        timezone.utc
    )

    for entry in history:

        joined_at = datetime.fromisoformat(
            entry["joined_at"]
        )

        if now - joined_at < timedelta(
            days=30
        ):
            return False

    return True


def add_invite(
    guild_id,
    inviter_id
):

    inviter_id = str(
        inviter_id
    )

    if inviter_id not in invite_data["counts"]:
        invite_data["counts"][inviter_id] = 0

    invite_data["counts"][inviter_id] += 1

    save_json(
        INVITES_FILE,
        invite_data
    )

    return invite_data["counts"][inviter_id]


def save_invite_history(
    member_id,
    inviter_id
):

    member_id = str(
        member_id
    )

    if member_id not in invite_data["history"]:
        invite_data["history"][member_id] = []

    invite_data["history"][member_id].append(
        {
            "inviter_id": str(
                inviter_id
            ),
            "joined_at": datetime.now(
                timezone.utc
            ).isoformat()
        }
    )

    save_json(
        INVITES_FILE,
        invite_data
    )


@bot.command()
async def checkinvites(ctx):

    user_id = str(
        ctx.author.id
    )

    total = invite_data["counts"].get(
        user_id,
        0
    )

    await ctx.send(
        f"{ctx.author.mention}, you currently have **{total} invites**.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command()
async def checklvl(ctx):

    user_id = str(
        ctx.author.id
    )

    if user_id not in level_data:
        level = 1

    else:
        level = level_data[user_id].get(
            "level",
            1
        )

    await ctx.send(
        f"{ctx.author.mention}, you are currently **level {level}**.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command()
@is_owner()
async def invites(ctx):

    embed = discord.Embed(
        title="🎁 • INVITE REWARDS",
        description=(
            "**Every 10 invites = 10 PLN** to spend on our server.\n\n"
            "You can check your invite count using:\n"
            "`!checkinvites`\n\n"
            "Use the command in <#1547321609289859203>."
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


@bot.event
async def on_invite_create(invite):

    await refresh_invite_cache(
        invite.guild
    )


@bot.event
async def on_invite_delete(invite):

    await refresh_invite_cache(
        invite.guild
    )


@bot.event
async def on_member_join(member):

    guild = member.guild

    before = invite_data["cached_invites"].get(
        str(guild.id),
        {}
    )

    try:
        invites = await guild.invites()

    except discord.Forbidden:
        return

    after = {
        invite.code: invite.uses
        for invite in invites
    }

    used_code = find_used_invite(
        before,
        after
    )

    invite_data["cached_invites"][str(guild.id)] = after

    if used_code is None:

        save_json(
            INVITES_FILE,
            invite_data
        )

        return

    used_invite = discord.utils.get(
        invites,
        code=used_code
    )

    if used_invite is None:

        save_json(
            INVITES_FILE,
            invite_data
        )

        return

    inviter = used_invite.inviter

    if inviter is None:

        save_json(
            INVITES_FILE,
            invite_data
        )

        return

    if can_count_invite(
        guild.id,
        member.id
    ):

        total = add_invite(
            guild.id,
            inviter.id
        )

        save_invite_history(
            member.id,
            inviter.id
        )

        channel = guild.get_channel(
            INVITES_CHANNEL_ID
        )

        if channel is not None:

            await channel.send(
                f"{inviter.mention} invited {member.mention} to the server!\n"
                f"They have **{total} invites**"
            )

    else:

        save_json(
            INVITES_FILE,
            invite_data
        )


# =========================================================
# TICKET SYSTEM
# =========================================================

tickets_data = load_json(
    TICKETS_FILE,
    {}
)


CATEGORY_INFO = {

    "Purchases": {
        "emoji": "🛒",
        "prefix": "purchase",
        "category_id": 1546963814854041601,
        "subcategories": {}
    },

    "Reports": {
        "emoji": "🚨",
        "prefix": "report",
        "category_id": 1546963863931719690,
        "subcategories": {
            "User Report": "user",
            "Scam Report": "scam",
            "Other Report": "other"
        }
    },

    "Order Problems": {
        "emoji": "📦",
        "prefix": "order",
        "category_id": 1546963924572971009,
        "subcategories": {
            "Wrong Product": "wrong",
            "Complaint": "complaint",
            "Other Problem": "other"
        }
    },

    "Questions / Errors": {
        "emoji": "❓",
        "prefix": "error",
        "category_id": 1546963979832655932,
        "subcategories": {
            "Question": "question",
            "Server Error": "server",
            "Bot Problem": "bot",
            "Other": "other"
        }
    },

    "Other": {
        "emoji": "📌",
        "prefix": "other",
        "category_id": 1546964017032069210,
        "subcategories": {
            "Cooperation": "cooperation",
            "Suggestion": "suggestion",
            "Server Matter": "server",
            "Other Matter": "matter"
        }
    }
}


SUBCATEGORY_MESSAGES = {

    "User Report": (
        "**Report**",
        "Please describe the issue and provide any evidence you have."
    ),

    "Scam Report": (
        "**Report**",
        "Please describe the issue and provide any evidence you have."
    ),

    "Other Report": (
        "**Report**",
        "Please describe the issue and provide any evidence you have."
    ),

    "Wrong Product": (
        "**Order Problem**",
        "Please describe the problem and attach proof. "
        "Tickets without proof will not be considered."
    ),

    "Complaint": (
        "**Order Problem**",
        "Please describe the problem and attach proof. "
        "Tickets without proof will not be considered."
    ),

    "Other Problem": (
        "**Order Problem**",
        "Please describe the problem and attach proof. "
        "Tickets without proof will not be considered."
    ),

    "Question": (
        "**Question / Error**",
        "Please describe your problem and attach any proof you have."
    ),

    "Server Error": (
        "**Question / Error**",
        "Please describe your problem and attach any proof you have."
    ),

    "Bot Problem": (
        "**Question / Error**",
        "Please describe your problem and attach any proof you have."
    ),

    "Other": (
        "**Question / Error**",
        "Please describe your problem and attach any proof you have."
    ),

    "Cooperation": (
        "**Cooperation**",
        "Please explain what the cooperation would be about and what you have in mind."
    ),

    "Suggestion": (
        "**Suggestion**",
        "Please describe your suggestion in detail."
    ),

    "Server Matter": (
        "**Server Issue**",
        "Please describe the issue in detail and explain what it is about."
    ),

    "Other Matter": (
        "**Other**",
        "Please describe what you need help with."
    )
}


def count_open_tickets(user_id):

    user_id = str(
        user_id
    )

    return sum(
        1
        for ticket in tickets_data.values()
        if str(ticket.get("author_id")) == user_id
    )


def get_ticket_category(
    category_name
):

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

    if category_name == "Purchases":

        return (
            f"{info['emoji']}・"
            f"purchase-"
            f"{member.display_name.lower()}"
        )

    sub_slug = info["subcategories"].get(
        subcategory,
        "other"
    )

    return (
        f"{info['emoji']}・"
        f"{info['prefix']}-"
        f"{sub_slug}-"
        f"{member.display_name.lower()}"
    )


# =========================================================
# BLACKLIST TRUST TICKET
# =========================================================

async def create_blacklist_ticket(
    interaction
):

    guild = interaction.guild
    member = interaction.user

    if guild is None:
        return None

    category = guild.get_channel(
        BLACKLIST_CATEGORY_ID
    )

    if category is None:

        await interaction.response.send_message(
            "Blacklist category not found.",
            ephemeral=True
        )

        return None

    owner_role = guild.get_role(
        OWNER_ROLE_ID
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

    safe_name = re.sub(
        r"[^a-zA-Z0-9_-]",
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

    ticket_name = (
        f"blacklist-{safe_name}"
    )

    try:

        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            reason="Blacklist review ticket"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "I do not have permission to create the blacklist ticket.",
            ephemeral=True
        )

        return None

    now = datetime.now(
        timezone.utc
    )

    tickets_data[str(channel.id)] = {
        "author_id": member.id,
        "author_name": str(member),
        "category": "Blacklist",
        "subcategory": None,
        "opened_at": now.isoformat(),
        "ticket_type": "blacklist_review"
    }

    save_json(
        TICKETS_FILE,
        tickets_data
    )

    embed = discord.Embed(
        title="Blacklist Review",
        description=(
            "Please explain why you selected **no** in the trust system.\n\n"
            "You are required to provide a valid explanation for your choice.\n\n"
            "Failure to provide a valid justification will result in a "
            "**blacklist until appeal**."
        ),
        color=EMBED_COLOR
    )

    embed.set_footer(
        text="Uzi Shop • Blacklist Review"
    )

    await channel.send(
        embed=embed,
        view=BlacklistTicketView()
    )

    await channel.send(
        member.mention
    )

    return channel


# =========================================================
# BLACKLIST TICKET VIEW
# =========================================================

class BlacklistTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Remove Vote",
        style=discord.ButtonStyle.danger,
        custom_id="blacklist_remove_vote"
    )
    async def remove_vote(
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
                "Only the Owner can remove this vote.",
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

        member = guild.get_member(
            int(ticket_info["author_id"])
        )

        if member is None:

            await interaction.response.send_message(
                "The ticket creator could not be found.",
                ephemeral=True
            )

            return

        blacklist_role = guild.get_role(
            BLACKLIST_ROLE_ID
        )

        if blacklist_role is None:

            await interaction.response.send_message(
                "The blacklist role could not be found.",
                ephemeral=True
            )

            return

        try:

            await member.add_roles(
                blacklist_role,
                reason="Blacklist trust vote review"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "I do not have permission to give the Blacklist role.",
                ephemeral=True
            )

            return

        user_id = str(
            member.id
        )

        if user_id in trust_votes["users"]:

            trust_votes["users"].pop(
                user_id,
                None
            )

            save_trust_votes()

            await update_trust_panel(
                guild
            )

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
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

        new_channel_name = (
            f"vote-{safe_name}"
        )

        try:

            await channel.edit(
                name=new_channel_name,
                reason="Blacklist vote removed"
            )

        except discord.Forbidden:
            pass

        closed_at = datetime.now(
            timezone.utc
        )

        opened_at = datetime.fromisoformat(
            ticket_info["opened_at"]
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
            "Category: Blacklist"
        )

        transcript_lines.append(
            "Reason for closure: Blacklist vote removed"
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
                transcript_text.encode(
                    "utf-8"
                )
            ),
            filename=(
                f"vote-"
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
                    f"Blacklist vote removed: **{channel.name}**\n"
                    f"User: {member.mention}\n"
                    f"Removed by: {interaction.user.mention}"
                ),
                file=transcript_file
            )

        await interaction.response.send_message(
            "The vote has been removed and the user has been blacklisted.\n"
            "This channel will be deleted in **15 seconds**."
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
                reason=f"Blacklist vote removed by {interaction.user}"
            )

        except (
            discord.Forbidden,
            discord.NotFound
        ):
            pass


# =========================================================
# NORMAL TICKETS
# =========================================================

async def create_ticket(
    interaction,
    category_name,
    subcategory=None,
    custom_description=None
):

    guild = interaction.guild
    member = interaction.user

    if guild is None:
        return

    if count_open_tickets(
        member.id
    ) >= 2:

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

    overwrites = {

        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
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

    channel = await guild.create_text_channel(
        name=ticket_name,
        category=category,
        overwrites=overwrites,
        reason="Ticket created"
    )

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

    if custom_description is not None:

        description = custom_description

    elif category_name == "Purchases":

        description = (
            "**Purchase**\n"
            "Please provide the **order number** of the product you want to buy.\n"
            f"You can find the order number next to the product in <#{STOCK_CHANNEL_ID}>."
        )

    elif category_name == "Reports":

        description = (
            "**Report**\n"
            "Please describe the issue and provide any evidence you have."
        )

    elif category_name == "Order Problems":

        description = (
            "**Order Problem**\n"
            "Please describe the problem and attach proof. "
            "Tickets without proof will not be considered."
        )

    elif category_name == "Questions / Errors":

        description = (
            "**Question / Error**\n"
            "Please describe your problem and attach any proof you have."
        )

    elif subcategory == "Cooperation":

        description = (
            "**Cooperation**\n"
            "Please explain what the cooperation would be about and what you have in mind."
        )

    elif subcategory == "Suggestion":

        description = (
            "**Suggestion**\n"
            "Please describe your suggestion in detail."
        )

    elif subcategory == "Server Matter":

        description = (
            "**Server Issue**\n"
            "Please describe the issue in detail and explain what it is about."
        )

    else:

        description = (
            "**Other**\n"
            "Please describe what you need help with."
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
            timeout=None
        )

        self.select = discord.ui.Select(
            placeholder="Choose a ticket category",
            custom_id="ticket_main_category",
            options=[
                discord.SelectOption(
                    label="Purchases",
                    emoji="🛒",
                    value="Purchases"
                ),
                discord.SelectOption(
                    label="Reports",
                    emoji="🚨",
                    value="Reports"
                ),
                discord.SelectOption(
                    label="Order Problems",
                    emoji="📦",
                    value="Order Problems"
                ),
                discord.SelectOption(
                    label="Questions / Errors",
                    emoji="❓",
                    value="Questions / Errors"
                ),
                discord.SelectOption(
                    label="Other",
                    emoji="📌",
                    value="Other"
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

        if category == "Purchases":

            await create_ticket(
                interaction,
                category
            )

            return

        await interaction.response.edit_message(
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
            timeout=None
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

        if ticket_info.get(
            "subcategory"
        ):

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
                transcript_text.encode(
                    "utf-8"
                )
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

        except discord.Forbidden:
            pass


# =========================================================
# TICKETS COMMAND
# =========================================================

@bot.command()
@is_owner()
async def tickets(ctx):

    channel = bot.get_channel(
        TICKET_PANEL_CHANNEL_ID
    )

    if channel is None:

        await ctx.send(
            "Ticket panel channel not found."
        )

        return

    embed = discord.Embed(
        title="Uzi Shop | Tickets",
        description=(
            "**Need help?**\n"
            "Click **Create Ticket** below and choose the category that matches your issue.\n\n"
            f"Before creating a ticket, please read <#{TICKET_RULES_CHANNEL_ID}>. "
            "Breaking its rules may result in the ticket being closed immediately "
            "and the case being dismissed."
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
# SERVER PERMISSIONS
# =========================================================

async def set_everyone_hidden(
    channel
):

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


async def hide_category_completely(
    category
):

    await set_everyone_hidden(
        category
    )

    for channel in category.channels:

        await set_everyone_hidden(
            channel
        )


async def apply_server_permissions(
    guild
):

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

    for category in guild.categories:

        if category.id in TICKET_CATEGORY_IDS:
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
# MESSAGE / XP SYSTEM
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is not None:

        user_id = str(
            message.author.id
        )

        now = datetime.now(
            timezone.utc
        )

        last_xp = xp_cooldowns.get(
            user_id
        )

        if (
            last_xp is None
            or now - last_xp >= timedelta(
                seconds=20
            )
        ):

            xp_cooldowns[user_id] = now

            if user_id not in level_data:

                level_data[user_id] = {
                    "xp": 0,
                    "level": 1
                }

            old_level = level_data[user_id]["level"]

            gained_xp = random.randint(
                4,
                7
            )

            level_data[user_id]["xp"] += gained_xp

            new_level = get_level_from_xp(
                level_data[user_id]["xp"]
            )

            level_data[user_id]["level"] = new_level

            save_json(
                LEVEL_XP_FILE,
                level_data
            )

            if new_level > old_level:

                await assign_level_role(
                    message.author,
                    new_level
                )

                levels_channel = bot.get_channel(
                    LEVELS_CHANNEL_ID
                )

                if levels_channel is not None:

                    await levels_channel.send(
                        f"{message.author.mention} reached **level {new_level}**!"
                    )

    await bot.process_commands(
        message
    )


# =========================================================
# REMOVE VOTE
# =========================================================

@bot.command()
@is_owner()
async def removevote(
    ctx,
    member: discord.Member
):

    user_id = str(
        member.id
    )

    if user_id not in trust_votes.get(
        "users",
        {}
    ):

        await ctx.send(
            f"{member.mention} does not have a vote to remove.",
            delete_after=5
        )

        return

    old_vote = trust_votes["users"][user_id]

    del trust_votes["users"][user_id]

    save_trust_votes()

    await update_trust_panel(
        ctx.guild
    )

    await ctx.send(
        f"Removed {member.mention}'s **{old_vote.upper()}** vote from Trust.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


# =========================================================
# RULES PL
# =========================================================

@bot.command()
@commands.has_role(OWNER_ROLE_ID)
async def rulespl(ctx):

    embed1 = discord.Embed(
        title="UZI SHOP • REGULAMIN",
        description=(
            "-# Polska wersja • Wersja 1.0 • 2026\n\n"
            "**§1 • Postanowienia ogólne**\n"
            "1. Niniejszy Regulamin określa zasady korzystania z serwera Discord **Uzi Shop**, zwanego dalej „Serwerem”.\n"
            "2. Regulamin obowiązuje wszystkich użytkowników Serwera, niezależnie od posiadanej rangi, stanowiska, stażu lub poziomu aktywności.\n"
            "3. Dołączenie do Serwera oraz korzystanie z jego funkcjonalności oznacza zapoznanie się z Regulaminem i zobowiązanie do jego przestrzegania.\n"
            "4. Administracja Serwera jest uprawniona do podejmowania działań niezbędnych do zapewnienia bezpieczeństwa, porządku oraz prawidłowego funkcjonowania Serwera.\n"
            "5. Regulamin stanowi zbiór zasad obowiązujących wewnątrz społeczności Uzi Shop i nie zastępuje przepisów prawa powszechnie obowiązującego.\n\n"

            "**§2 • Podstawy prawne**\n"
            "1. Użytkownicy zobowiązani są do przestrzegania przepisów prawa Rzeczypospolitej Polskiej oraz przepisów prawa Unii Europejskiej mających zastosowanie do ich działalności.\n"
            "2. W szczególności, w zakresie odpowiednim do charakteru danej sprawy, uwzględnia się:\n"
            "• [Konstytucję Rzeczypospolitej Polskiej](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=wdu19970780483)\n"
            "• [Kodeks karny](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=wdu19970880553)\n"
            "• [Kodeks cywilny](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19640160093)\n"
            "• [Kodeks wykroczeń](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19710120114&type=2)\n"
            "• [Ustawę o świadczeniu usług drogą elektroniczną](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=wdu20021441204)\n"
            "• [Ustawę o prawie autorskim i prawach pokrewnych](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20250000024)\n"
            "• [Ustawę o zwalczaniu nieuczciwej konkurencji](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260000085)\n"
            "• [Ustawę o ochronie konkurencji i konsumentów](https://isap.sejm.gov.pl/isap.nsf/ByKeyword.xsp?key=konkurencja)\n"
            "• [RODO – Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679](https://uodo.gov.pl/pl/404/539)\n"
            "3. Powyższe akty prawne stanowią zewnętrzne źródła prawa i mają zastosowanie wyłącznie w zakresie wynikającym z obowiązujących przepisów.\n"
            "4. Niniejszy Regulamin nie nadaje administracji uprawnień przysługujących organom państwowym ani sądom.\n\n"

            "**§3 • Prawa i obowiązki użytkowników**\n"
            "1. Każdy użytkownik ma prawo do korzystania z Serwera zgodnie z jego przeznaczeniem.\n"
            "2. Użytkownik zobowiązany jest do przestrzegania Regulaminu, obowiązującego prawa, respektowania innych użytkowników oraz administracji, przekazywania prawdziwych informacji i stosowania się do uzasadnionych poleceń administracji.\n"
            "3. Nieznajomość Regulaminu nie zwalnia z obowiązku jego przestrzegania.\n\n"

            "**§4 • Działania zabronione**\n"
            "1. Na Serwerze zabrania się podejmowania działań sprzecznych z prawem, Regulaminem lub zasadami bezpieczeństwa.\n"
            "2. W szczególności zabronione są:\n"
            "• oszustwa, wyłudzenia i próby oszustwa,\n"
            "• kradzież lub przywłaszczenie cudzych środków albo przedmiotów,\n"
            "• przedstawianie fałszywych potwierdzeń płatności,\n"
            "• podszywanie się pod inne osoby lub administrację,\n"
            "• bezprawne uzyskiwanie dostępu do cudzych kont, systemów lub danych,\n"
            "• wykorzystywanie błędów technicznych Serwera w celu uzyskania korzyści,\n"
            "• rozpowszechnianie cudzych danych osobowych bez odpowiedniej podstawy,\n"
            "• naruszanie praw autorskich lub innych praw własności intelektualnej,\n"
            "• celowe zakłócanie działania Serwera, botów lub innych systemów,\n"
            "• obchodzenie nałożonych ograniczeń lub sankcji.\n"
            "3. Zabronione jest wykorzystywanie Serwera do działań mogących narazić innych użytkowników lub Uzi Shop na szkodę."
        ),
        color=EMBED_COLOR
    )

    embed2 = discord.Embed(
        title="UZI SHOP • REGULAMIN",
        description=(
            "-# Polska wersja • §5–§8\n\n"

            "**§5 • Transakcje i działalność handlowa**\n"
            "1. Transakcje prowadzone za pośrednictwem Uzi Shop powinny być wykonywane zgodnie z obowiązującym prawem oraz zasadami określonymi przez administrację.\n"
            "2. Zabrania się podawania nieprawdziwych informacji dotyczących produktów, usług, płatności lub przebiegu transakcji.\n"
            "3. Próby oszustwa, fałszowania dowodów płatności lub celowego wprowadzania innych użytkowników w błąd mogą skutkować natychmiastowym ograniczeniem dostępu do Serwera.\n"
            "4. W przypadku sporu administracja może poprosić strony o przedstawienie informacji lub dowodów niezbędnych do wyjaśnienia sprawy.\n"
            "5. Administracja może odmówić dalszej obsługi transakcji, jeżeli istnieją uzasadnione przesłanki wskazujące na naruszenie Regulaminu lub prawa.\n\n"

            "**§6 • System sankcji**\n"
            "1. W przypadku naruszenia Regulaminu administracja może zastosować odpowiednią sankcję serwerową.\n"
            "2. Sankcje mogą obejmować ostrzeżenie, ograniczenie dostępu do kanałów lub funkcji, odebranie rangi lub uprawnień, czasową lub trwałą blokadę dostępu do Serwera oraz umieszczenie użytkownika na wewnętrznej liście osób objętych ograniczeniami.\n"
            "3. Rodzaj sankcji może zależeć od charakteru, skutków oraz powtarzalności naruszenia.\n"
            "4. Sankcje serwerowe mają charakter wyłącznie wewnętrzny i obowiązują w ramach Uzi Shop.\n"
            "5. Sankcja serwerowa nie jest karą przewidzianą przez Kodeks karny ani inną ustawę.\n"
            "6. Jeżeli zachowanie użytkownika może stanowić naruszenie prawa, administracja może podjąć odpowiednie działania zgodne z prawem, w tym przekazać posiadane informacje właściwym organom, jeżeli istnieje ku temu podstawa prawna.\n\n"

            "**§7 • System ticketów**\n"
            "1. System ticketów służy do kontaktu z administracją, zgłaszania problemów, składania raportów oraz rozwiązywania spraw związanych z Uzi Shop.\n"
            "2. Użytkownik zobowiązany jest do przedstawiania w tickecie informacji zgodnych ze stanem faktycznym.\n"
            "3. Zabrania się tworzenia fałszywych zgłoszeń, celowego spamowania ticketami oraz wykorzystywania systemu ticketów do działań niezwiązanych z jego przeznaczeniem.\n"
            "4. Szczegółowe zasady korzystania z systemu ticketów określa odrębny Regulamin Ticketów Uzi Shop.\n"
            "5. Administracja może przechowywać dokumentację dotyczącą ticketów w zakresie niezbędnym do zapewnienia bezpieczeństwa oraz rozpatrywania spraw.\n\n"

            "**§8 • Ochrona danych i prywatność**\n"
            "1. Użytkownicy zobowiązani są do poszanowania prywatności innych osób.\n"
            "2. Zabrania się publikowania lub rozpowszechniania cudzych danych osobowych bez odpowiedniej podstawy prawnej.\n"
            "3. Zabrania się bezprawnego udostępniania prywatnej korespondencji, materiałów lub informacji dotyczących innych użytkowników.\n"
            "4. Informacje przekazywane administracji mogą być wykorzystywane wyłącznie w zakresie uzasadnionym celem ich zebrania oraz zgodnie z obowiązującymi przepisami.\n"
            "5. W sprawach dotyczących danych osobowych zastosowanie mają właściwe przepisy dotyczące ochrony danych, w tym RODO."
        ),
        color=EMBED_COLOR
    )

    embed3 = discord.Embed(
        title="UZI SHOP • REGULAMIN",
        description=(
            "-# Polska wersja • §9–§11\n\n"

            "**§9 • Odpowiedzialność użytkowników**\n"
            "1. Każdy użytkownik odpowiada za działania podejmowane przy użyciu swojego konta.\n"
            "2. Użytkownik ponosi odpowiedzialność za informacje przekazywane administracji oraz innym użytkownikom.\n"
            "3. Administracja nie ponosi odpowiedzialności za działania użytkowników podejmowane poza oficjalnymi kanałami Uzi Shop, z zastrzeżeniem obowiązków wynikających z bezwzględnie obowiązujących przepisów prawa.\n"
            "4. Użytkownik nie może powoływać się na brak znajomości Regulaminu jako uzasadnienie naruszenia jego postanowień.\n\n"

            "**§10 • Odwołania i rozpatrywanie spraw**\n"
            "1. Użytkownik może zgłosić administracji zastrzeżenia dotyczące nałożonej sankcji lub sposobu rozpatrzenia sprawy.\n"
            "2. Odwołanie powinno zawierać opis sytuacji oraz, w miarę możliwości, informacje pozwalające na jej zweryfikowanie.\n"
            "3. Administracja może ponownie przeanalizować sprawę, jeżeli przedstawione zostaną nowe lub wcześniej niedostępne informacje.\n"
            "4. Ostateczna decyzja dotycząca sankcji serwerowej należy do administracji Uzi Shop, z zastrzeżeniem praw wynikających z obowiązujących przepisów prawa.\n\n"

            "**§11 • Postanowienia końcowe**\n"
            "1. Administracja zastrzega sobie możliwość zmiany Regulaminu w przypadku zmian organizacyjnych, technicznych lub prawnych.\n"
            "2. Zmiany Regulaminu zostają opublikowane na Serwerze.\n"
            "3. W sprawach nieuregulowanych niniejszym dokumentem zastosowanie mają właściwe przepisy prawa Rzeczypospolitej Polskiej oraz prawa Unii Europejskiej, jeżeli mają zastosowanie.\n"
            "4. W przypadku rozbieżności pomiędzy niniejszym Regulaminem a przepisami prawa, pierwszeństwo mają przepisy prawa.\n"
            "5. Regulamin wchodzi w życie z dniem jego publikacji.\n"
            "6. Aktualna wersja Regulaminu obowiązuje do momentu jej zastąpienia kolejną wersją.\n\n"

            "**UZI SHOP**\n"
            "*Regulamin Serwera Discord • Wersja 1.0 | 2026*\n\n"
            "||Nie bierzcie wszystkiego na 100% poważnie ;P||"
        ),
        color=EMBED_COLOR
    )

    embed1.set_footer(
        text="UZI SHOP • REGULAMIN • 1/3"
    )

    embed2.set_footer(
        text="UZI SHOP • REGULAMIN • 2/3"
    )

    embed3.set_footer(
        text="UZI SHOP • REGULAMIN • 3/3"
    )

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(
        embed=embed1
    )

    await ctx.send(
        embed=embed2
    )

    await ctx.send(
        embed=embed3
    )

    await ctx.send(
        "@everyone",
        allowed_mentions=discord.AllowedMentions(
            everyone=True
        )
    )


# =========================================================
# RULES EN
# =========================================================

@bot.command()
@commands.has_role(OWNER_ROLE_ID)
async def rulesang(ctx):

    embed = discord.Embed(
        title="UZI SHOP • RULES",
        description=(
            "-# English version • Version 1.0 • 2026\n\n"
            "**01 • Respect**\n"
            "Respect all users and staff.\n\n"
            "**02 • Follow the rules**\n"
            "Follow Polish law and Uzi Shop rules.\n\n"
            "**03 • No scams**\n"
            "Scams, fraud, fake payments and stealing are forbidden.\n\n"
            "**04 • Privacy**\n"
            "Do not share private or personal information without permission.\n\n"
            "**05 • Server systems**\n"
            "Do not abuse tickets, bots or server systems.\n\n"
            "**06 • Sanctions**\n"
            "Breaking the rules may result in a warning, restriction or ban.\n\n"
            "**07 • Official version**\n"
            "The full Polish version is the official Uzi Shop rules."
        ),
        color=EMBED_COLOR
    )

    embed.set_footer(
        text="UZI SHOP • RULES"
    )

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(
        embed=embed
    )

    await ctx.send(
        "@everyone",
        allowed_mentions=discord.AllowedMentions(
            everyone=True
        )
    )


# =========================================================
# TICKET PURCHASE RULES
# =========================================================

@bot.command()
async def rulesticket(ctx):

    embed = discord.Embed(
        title="TICKET PURCHASE RULES",
        description=(
            "**1. ORDER DELIVERY**\n"
            "Orders are delivered within **48 hours** of purchase. "
            "Delivery time may vary depending on the current number of orders.\n\n"

            "**2. CONTACT**\n"
            "All questions regarding orders, account issues or complaints "
            "must be handled **exclusively through a ticket**.\n\n"

            "**3. WARRANTY**\n"
            "After receiving the account, you have **1 hour of warranty** "
            "to check whether the account works correctly and report any issues.\n\n"

            "**4. COMPLAINTS**\n"
            "Any issue with the account must be reported within **1 hour "
            "of receiving the account**, together with appropriate proof.\n\n"

            "**5. ACCOUNT ACCESS**\n"
            "If someone changes the email or password of the account after purchase, "
            "a refund will not be provided if the issue was not reported within "
            "the warranty period.\n\n"

            "**6. PROOF**\n"
            "When submitting a complaint, you must provide appropriate proof "
            "confirming the reported issue.\n\n"

            "**7. FRAUD**\n"
            "Fake evidence, refund abuse or intentionally misleading staff "
            "may result in a blacklist.\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "By making a purchase, you confirm that you have read and accepted "
            "these rules."
        ),
        color=EMBED_COLOR
    )

    embed.set_footer(
        text="Uzi Shop"
    )

    await ctx.send(
        embed=embed
    )


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
            TrustView()
        )

        bot.add_view(
            TicketPanelView()
        )

        bot.add_view(
            TicketView()
        )

        bot.add_view(
            BlacklistTicketView()
        )

        views_added = True

    for guild in bot.guilds:

        await refresh_invite_cache(
            guild
        )

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