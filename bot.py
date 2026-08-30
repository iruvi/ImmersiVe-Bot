import disnake
from disnake.ext import commands, tasks
from disnake import ui
import aiosqlite
import asyncio
import json
import logging
import os
import time
import aiohttp
import io
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("RoleBot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
MY_DISCORD_ID = 254790373191188481
DATABASE_NAME = "bot_data.db"
GUILD_ID = 1234469703301333044

HUG_GIFS = [
    "https://media.tenor.com/...",
    "https://media.tenor.com/...",
]
KISS_GIFS = [
    "https://media.tenor.com/...",
    "https://media.tenor.com/...",
]

# Создаём папку для баннеров, если её нет
BANNERS_DIR = "banners"
if not os.path.exists(BANNERS_DIR):
    os.makedirs(BANNERS_DIR)
    logger.info(f"Папка {BANNERS_DIR} создана")

# ---------- УТИЛИТЫ ----------
async def check_is_moderator(user: disnake.Member, bot) -> bool:
    if user.guild_permissions.administrator:
        return True
    mod_role_id_raw = await bot.get_config("mod_role_id")
    if mod_role_id_raw:
        try:
            role_id = int(mod_role_id_raw)
            if any(role.id == role_id for role in user.roles):
                return True
        except (ValueError, TypeError):
            pass
    trusted_json = await bot.get_config("trusted_users")
    if trusted_json:
        try:
            trusted_list = json.loads(trusted_json)
            if user.id in trusted_list:
                return True
        except Exception:
            pass
    return False

async def check_command_permission(ctx, command_name: str):
    if ctx.author.guild_permissions.administrator:
        return True
    role_id = await ctx.bot.get_command_permission(command_name)
    if role_id:
        role = ctx.guild.get_role(role_id)
        if role and role in ctx.author.roles:
            return True
    return await check_is_moderator(ctx.author, ctx.bot)

def calculate_lvl_and_remaining(xp: int):
    lvl = 1
    xp_needed = 100
    while xp >= xp_needed:
        xp -= xp_needed
        lvl += 1
        xp_needed += 100
    return lvl, xp, xp_needed

def generate_custom_progress_bar(current_xp: int, needed_xp: int, length: int = 10) -> str:
    if needed_xp <= 0:
        filled = length
    else:
        filled = int(round((current_xp / needed_xp) * length))
    filled = max(0, min(length, filled))

    left_empty = "<:zzz_left_empty:1538886449540366346>"
    left_fill = "<:zzz_left_fill:1538886407416709131>"
    mid_empty = "<:zzz_mid_empty:1538886498252755055>"
    mid_fill = "<:zzz_mid_fill:1538886483342131210>"
    right_empty = "<:zzz_right_empy:1538886432062709790>"
    right_fill = "<:zzz_right_fill:1538886386390933685>"

    if length == 0:
        return ""

    if filled == 0:
        return left_empty + mid_empty * (length - 2) + right_empty if length > 1 else left_empty

    if filled == length:
        return left_fill + mid_fill * (length - 2) + right_fill if length > 1 else left_fill

    parts = []
    for i in range(length):
        if i == 0:
            parts.append(left_fill if filled > 0 else left_empty)
        elif i == length - 1:
            parts.append(right_fill if filled == length else right_empty)
        else:
            parts.append(mid_fill if i < filled else mid_empty)

    return "".join(parts)

def determine_role_category(guild: disnake.Guild, target_role: disnake.Role) -> str:
    category_ids = {
        1524772350728339536: "<@&1524772350728339536>",
        1270787082880548975: "<@&1270787082880548975>",
        1243603279318089739: "<@&1243603279318089739>"
    }
    sorted_roles = sorted(guild.roles, key=lambda r: r.position)
    try:
        start_idx = sorted_roles.index(target_role)
    except ValueError:
        return "*Не определена (Роль не найдена)*"
    for i in range(start_idx + 1, len(sorted_roles)):
        current_role = sorted_roles[i]
        if current_role.id in category_ids:
            return category_ids[current_role.id]
    return "*Не определена (Разделитель не найден выше)*"

async def build_role_info_embed(guild: disnake.Guild, user: disnake.Member, role_id: int) -> disnake.Embed:
    role = guild.get_role(role_id)
    if not role:
        return disnake.Embed(title="❌ Ошибка", description="Роль не найдена.", color=disnake.Color.red())
    category_text = determine_role_category(guild, role)
    members_with_role = [m.mention for m in role.members if m.id != user.id]
    holders_text = ", ".join(members_with_role) if members_with_role else "*Никому, кроме вас, не выдана*"
    perms = []
    if role.permissions.administrator:
        perms.append("Администратор")
    if role.permissions.manage_roles:
        perms.append("Управление ролями")
    if role.permissions.manage_messages:
        perms.append("Управление сообщениями")
    if role.permissions.mention_everyone:
        perms.append("Упоминание @everyone")
    if role.permissions.manage_nicknames:
        perms.append("Управление никнеймами")
    perms_text = f"\n• **Права доступа:** `{', '.join(perms)}`" if perms else ""
    icon_text = f"[Ссылка на иконку]({role.icon.url})" if role.icon else "`Отсутствует`"
    embed = disnake.Embed(title=f"<:zzz_pen:1535105077667303424> Управление ролью: {role.name}")
    embed.color = role.color if role.color.value != 0 else disnake.Color.purple()
    embed.description = (
        f"<a:zzz_crown:1535104585620791306> **КАТЕГОРИЯ РОЛИ:** {category_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Кастомная роль:** {role.mention} *(ID: `{role.id}`)*\n"
        f"• **Цвет роли:** `{str(role.color).upper()}` (RGB: `{role.color.to_rgb()}`)\n"
        f"• **Иконка роли:** {icon_text}{perms_text}\n\n"
        f"<a:imsv_buglol:1535105638965846016> **Участники с вашей ролью:**\n{holders_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**Доступные опции:**\n"
        "• Вы можете редактировать роль или поделиться ею с простолюдинами, которые не были достойны своей роли"
    )
    return embed

def format_clan_name(name: str, tag: str = "") -> str:
    if tag:
        return f"《{tag}》{name}"
    return name

class PrivateView(ui.View):
    def __init__(self, author_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.author_id = author_id

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "⛔ Вы не являетесь автором этого меню. Вызовите своё через `/hub` или `i.hub`!",
                ephemeral=True
            )
            return False
        return True

# ==================== МОДАЛЬНЫЕ ОКНА ====================
class EditRoleModal(ui.Modal):
    def __init__(self, bot, role_id: int):
        self.bot = bot
        self.role_id = int(role_id)
        components = [
            ui.TextInput(label="Новое название роли", custom_id="role_name", required=False, placeholder="Оставьте пустым"),
            ui.TextInput(label="Статичный цвет (HEX)", custom_id="static_color", required=False, placeholder="#ff0000", max_length=7),
            ui.TextInput(label="Градиент (Два HEX через пробел)", custom_id="gradient_colors", required=False, placeholder="#ff0000 #00ff00"),
            ui.TextInput(label="Иконка роли (URL)", custom_id="role_icon_url", required=False, placeholder="https://example.com"),
        ]
        super().__init__(title="Редактирование личной роли", custom_id="edit_role_modal", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        target_role = inter.guild.get_role(self.role_id)
        if not target_role:
            return await inter.followup.send("❌ Роль не найдена.", ephemeral=True)
        if target_role >= inter.guild.me.top_role:
            return await inter.followup.send("❌ Роль бота должна быть ВЫШЕ вашей роли.", ephemeral=True)
        changes = []
        new_name = inter.text_values.get("role_name")
        static_color = inter.text_values.get("static_color")
        gradient_colors = inter.text_values.get("gradient_colors")
        role_icon_url = inter.text_values.get("role_icon_url")
        if new_name:
            try:
                await target_role.edit(name=new_name)
                changes.append(f"название: `{new_name}`")
            except disnake.Forbidden:
                return await inter.followup.send("❌ Нет прав на переименование.", ephemeral=True)
        if role_icon_url:
            url = role_icon_url.strip()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return await inter.followup.send("❌ Не удалось скачать картинку.", ephemeral=True)
                        icon_bytes = await response.read()
                await target_role.edit(display_icon=icon_bytes)
                changes.append("установлена иконка роли")
            except disnake.Forbidden:
                return await inter.followup.send("❌ Нужен Буст сервера 2+ уровня.", ephemeral=True)
            except Exception as e:
                return await inter.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
        if gradient_colors:
            parts = gradient_colors.strip().split()
            if len(parts) != 2:
                return await inter.followup.send("❌ Укажите два HEX через пробел.", ephemeral=True)
            try:
                c1, c2 = int(parts[0].lstrip("#"), 16), int(parts[1].lstrip("#"), 16)
                await self.bot.db.execute("DELETE FROM gradients WHERE role_id = ?", (target_role.id,))
                await self.bot.db.commit()
                await self.bot.set_role_gradient(target_role, c1, c2)
                changes.append("установлен градиент")
            except ValueError:
                return await inter.followup.send("❌ Неверный формат HEX.", ephemeral=True)
        elif static_color:
            try:
                rgb = int(static_color.lstrip("#"), 16)
                await self.bot.db.execute("DELETE FROM gradients WHERE role_id = ?", (target_role.id,))
                await self.bot.db.commit()
                await target_role.edit(color=disnake.Color(rgb))
                changes.append("установлен цвет")
            except ValueError:
                return await inter.followup.send("❌ Неверный формат HEX.", ephemeral=True)
        if changes:
            await inter.followup.send("✅ Роль успешно обновлена!", ephemeral=True)

class LinkCreateManualIDModal(ui.Modal):
    def __init__(self, bot, target_member, return_view_callback):
        self.bot = bot
        self.target_member = target_member
        self.return_view_callback = return_view_callback
        components = [ui.TextInput(label="ID Кастомной Роли", custom_id="role_id_input", required=True)]
        super().__init__(title="⌨️ Ручной ввод ID роли", custom_id="link_manual_id", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            r_id = int(inter.text_values["role_id_input"])
            role = inter.guild.get_role(r_id)
            if not role:
                return await inter.followup.send("❌ Роль не найдена.", ephemeral=True)
            member_obj = self.target_member[0] if isinstance(self.target_member, list) else self.target_member
            await self.bot.db.execute("INSERT OR IGNORE INTO links (user_id, role_id) VALUES (?, ?)", (member_obj.id, r_id))
            await self.bot.db.commit()
            await inter.followup.send(f"✅ Связь успешно добавлена вручную для {member_obj.mention}!", ephemeral=True)
            await self.return_view_callback(inter)
        except ValueError:
            await inter.followup.send("❌ ID должен быть числом.", ephemeral=True)

class ModGiveXPModal(ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        components = [
            ui.TextInput(label="ID Участника", custom_id="user_id_input", required=True),
            ui.TextInput(label="Количество Текстового XP (Сообщения)", custom_id="xp_input", required=True, value="0"),
            ui.TextInput(label="Количество Голосового XP (Войс)", custom_id="voice_xp_input", required=True, value="0"),
        ]
        super().__init__(title="🪙 Управление опытом (XP)", custom_id="mod_give_xp", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            u_id = int(inter.text_values["user_id_input"])
            txp = int(inter.text_values["xp_input"])
            vxp = int(inter.text_values["voice_xp_input"])
            await self.bot.db.execute("INSERT INTO levels (user_id, xp, voice_xp) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = xp + excluded.xp, voice_xp = voice_xp + excluded.voice_xp", (u_id, txp, vxp))
            await self.bot.db.commit()
            await inter.followup.send(f"✅ Баланс опыта <@{u_id}> изменен: +{txp} Text XP, +{vxp} Voice XP!", ephemeral=True)
        except ValueError:
            await inter.followup.send("❌ Вводите только целые числовые значения.", ephemeral=True)

class AddVoiceLinkModal(ui.Modal):
    def __init__(self, bot, author_id, guild):
        self.bot = bot
        self.author_id = author_id
        self.guild = guild
        components = [
            ui.TextInput(label="ID пользователя", custom_id="user_id", required=True),
            ui.TextInput(label="ID канала", custom_id="channel_id", required=True),
            ui.TextInput(label="Может управлять (1/0)", custom_id="can_manage", required=False, value="0"),
        ]
        super().__init__(title="➕ Добавить связь с войсом", custom_id="add_voice_link", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            uid = int(inter.text_values["user_id"].strip())
            cid = int(inter.text_values["channel_id"].strip())
            can_manage = int(inter.text_values.get("can_manage", "0").strip() or "0")
        except ValueError:
            return await inter.followup.send("❌ ID должны быть числами.", ephemeral=True)
        member = self.guild.get_member(uid)
        if not member:
            return await inter.followup.send("❌ Пользователь не найден.", ephemeral=True)
        channel = self.guild.get_channel(cid)
        if not channel or not isinstance(channel, disnake.VoiceChannel):
            return await inter.followup.send("❌ Канал не найден или не голосовой.", ephemeral=True)
        await self.bot.db.execute("INSERT OR REPLACE INTO voice_links (user_id, channel_id, can_manage) VALUES (?, ?, ?)", (uid, cid, can_manage))
        await self.bot.db.commit()
        await inter.followup.send(f"✅ Связь добавлена: {member.mention} ➔ {channel.mention}", ephemeral=True)
        async with self.bot.db.execute("SELECT user_id, channel_id, can_manage FROM voice_links") as cursor:
            rows = await cursor.fetchall()
        view = VoiceLinksView(self.bot, self.author_id, self.guild, rows, 0)
        embed = await view.build_embed(self.guild, rows, 0)
        await inter.edit_original_response(embed=embed, view=view)

class CreateClanModal(ui.Modal):
    def __init__(self, bot, user):
        self.bot = bot
        self.user = user
        components = [
            ui.TextInput(label="Название клана", custom_id="name", required=True, max_length=50),
            ui.TextInput(label="Описание клана", custom_id="description", required=False, max_length=200, style=ui.TextInputStyle.paragraph),
            ui.TextInput(label="URL иконки", custom_id="icon_url", required=False, placeholder="https://example.com/icon.png"),
            ui.TextInput(label="URL баннера", custom_id="banner_url", required=False, placeholder="https://example.com/banner.png"),
            ui.TextInput(label="Тег (3-5 символов)", custom_id="tags", required=False, placeholder="PvP", max_length=5),
        ]
        super().__init__(title="🏰 Создание клана", custom_id="create_clan", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        if await self.bot.is_banned_from_clans(self.user.id):
            return await inter.followup.send("⛔ Вы забанены в клановой системе.", ephemeral=True)
        if await self.bot.get_user_clan(self.user.id):
            return await inter.followup.send("❌ Вы уже состоите в клане.", ephemeral=True)
        tags = inter.text_values.get("tags", "").strip()
        if tags:
            if len(tags) < 3 or len(tags) > 5:
                return await inter.followup.send("❌ Тег должен быть от 3 до 5 символов.", ephemeral=True)
            if not tags.isalnum():
                return await inter.followup.send("❌ Тег должен состоять только из букв и цифр.", ephemeral=True)
        clan_data = {
            'name': inter.text_values["name"].strip(),
            'description': inter.text_values.get("description", "").strip(),
            'icon_url': inter.text_values.get("icon_url", "").strip(),
            'banner_url': inter.text_values.get("banner_url", "").strip(),
            'tags': tags
        }
        linked = await self.bot.get_linked_roles(self.user.id)
        role_options = []
        for role_id in linked:
            role = inter.guild.get_role(role_id[0])
            if role:
                role_options.append(disnake.SelectOption(label=role.name, value=str(role.id), description=f"ID: {role.id}"))
        if self.user.id == MY_DISCORD_ID:
            all_roles = sorted(inter.guild.roles, key=lambda r: r.position, reverse=True)
            for role in all_roles:
                if role.is_default():
                    continue
                if not any(opt.value == str(role.id) for opt in role_options):
                    role_options.append(disnake.SelectOption(label=role.name, value=str(role.id), description=f"ID: {role.id} (создатель)"))
        if not role_options:
            return await inter.followup.send("❌ У вас нет привязанных ролей для создания клана.", ephemeral=True)
        view = ClanRoleSelectView(self.bot, self.user.id, inter.guild, clan_data, role_options, is_edit=False)
        embed = disnake.Embed(title="🏰 Создание клана", description="Выберите роль, которая будет привязана к клану.\nРоль будет выдаваться участникам (если включена автовыдача).", color=disnake.Color.blue())
        await inter.edit_original_response(embed=embed, view=view)

class EditClanModal(ui.Modal):
    def __init__(self, bot, clan_id, current_data):
        self.bot = bot
        self.clan_id = clan_id
        self.current_data = current_data
        components = [
            ui.TextInput(label="Новое название", custom_id="name", required=False, max_length=50, placeholder=current_data.get('name', '')),
            ui.TextInput(label="Новое описание", custom_id="description", required=False, max_length=200, style=ui.TextInputStyle.paragraph, placeholder=current_data.get('description', '')),
            ui.TextInput(label="Новый URL иконки", custom_id="icon_url", required=False, placeholder="https://example.com/icon.png"),
            ui.TextInput(label="Новый URL баннера", custom_id="banner_url", required=False, placeholder="https://example.com/banner.png"),
            ui.TextInput(label="Новый тег (3-5 символов)", custom_id="tags", required=False, placeholder="PvP", max_length=5),
        ]
        super().__init__(title="✏️ Редактирование клана", custom_id="edit_clan", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        updates = {}
        if inter.text_values.get("name"):
            name = inter.text_values["name"].strip()
            existing = await self.bot.get_clan_by_name(name)
            if existing and existing[0] != self.clan_id:
                return await inter.followup.send("❌ Клан с таким названием уже существует.", ephemeral=True)
            updates['name'] = name
        if inter.text_values.get("description"):
            updates['description'] = inter.text_values["description"].strip()
        if inter.text_values.get("icon_url"):
            updates['icon_url'] = inter.text_values["icon_url"].strip()
        if inter.text_values.get("banner_url"):
            updates['banner_url'] = inter.text_values["banner_url"].strip()
        if inter.text_values.get("tags"):
            tags = inter.text_values["tags"].strip()
            if len(tags) < 3 or len(tags) > 5:
                return await inter.followup.send("❌ Тег должен быть от 3 до 5 символов.", ephemeral=True)
            if not tags.isalnum():
                return await inter.followup.send("❌ Тег должен состоять только из букв и цифр.", ephemeral=True)
            updates['tags'] = tags
        if not updates:
            return await inter.followup.send("❌ Не указано ни одного изменения.", ephemeral=True)
        success, msg = await self.bot.update_clan(self.clan_id, **updates)
        if not success:
            return await inter.followup.send(f"❌ {msg}", ephemeral=True)
        linked = await self.bot.get_linked_roles(inter.user.id)
        role_options = []
        for role_id in linked:
            role = inter.guild.get_role(role_id[0])
            if role:
                role_options.append(disnake.SelectOption(label=role.name, value=str(role.id), description=f"ID: {role.id}"))
        if inter.user.id == MY_DISCORD_ID:
            all_roles = sorted(inter.guild.roles, key=lambda r: r.position, reverse=True)
            for role in all_roles:
                if role.is_default():
                    continue
                if not any(opt.value == str(role.id) for opt in role_options):
                    role_options.append(disnake.SelectOption(label=role.name, value=str(role.id), description=f"ID: {role.id} (создатель)"))
        if role_options:
            clan_data = {'clan_id': self.clan_id}
            view = ClanRoleSelectView(self.bot, inter.user.id, inter.guild, clan_data, role_options, is_edit=True)
            embed = disnake.Embed(title="✏️ Изменение роли клана", description="Выберите новую роль для клана (или нажмите «Отмена», чтобы оставить текущую).", color=disnake.Color.blue())
            await inter.edit_original_response(embed=embed, view=view)
        else:
            await inter.followup.send(f"✅ {msg}", ephemeral=True)
            view = ClanPageView(self.bot, inter.user.id, inter.guild, self.clan_id)
            embed = await view.get_embed()
            await inter.edit_original_response(embed=embed, view=view)

class SearchClanModal(ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        components = [ui.TextInput(label="Название клана", custom_id="search", required=True, max_length=50)]
        super().__init__(title="🔍 Поиск клана", custom_id="search_clan", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        if await self.bot.is_banned_from_clans(inter.user.id):
            return await inter.followup.send("⛔ Вы забанены в клановой системе.", ephemeral=True)
        clan = await self.bot.get_clan_by_name(inter.text_values["search"].strip())
        if not clan:
            return await inter.followup.send("❌ Клан с таким названием не найден.", ephemeral=True)
        clan_id = clan[0]
        view = ClanPageView(self.bot, inter.user.id, inter.guild, clan_id)
        embed = await view.get_embed()
        await inter.edit_original_response(embed=embed, view=view)

class BanUserModal(ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        components = [ui.TextInput(label="ID пользователя", custom_id="user_id", required=True)]
        super().__init__(title="🚫 Забанить пользователя в кланах", custom_id="ban_user", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            uid = int(inter.text_values["user_id"].strip())
            await self.bot.ban_from_clans(uid)
            await inter.followup.send(f"✅ Пользователь <@{uid}> забанен в клановой системе.", ephemeral=True)
        except ValueError:
            await inter.followup.send("❌ Введите корректный ID пользователя.", ephemeral=True)

class UnbanUserModal(ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        components = [ui.TextInput(label="ID пользователя", custom_id="user_id", required=True)]
        super().__init__(title="✅ Разбанить пользователя в кланах", custom_id="unban_user", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        try:
            uid = int(inter.text_values["user_id"].strip())
            await self.bot.unban_from_clans(uid)
            await inter.followup.send(f"✅ Пользователь <@{uid}> разбанен в клановой системе.", ephemeral=True)
        except ValueError:
            await inter.followup.send("❌ Введите корректный ID пользователя.", ephemeral=True)

class CreateClanModalFinal(ui.Modal):
    def __init__(self, bot, user_id, role_id, guild):
        self.bot = bot
        self.user_id = user_id
        self.role_id = role_id
        self.guild = guild
        components = [
            ui.TextInput(label="Название клана", custom_id="name", required=True, max_length=50),
            ui.TextInput(label="Описание клана", custom_id="description", required=False, max_length=200, style=ui.TextInputStyle.paragraph),
            ui.TextInput(label="URL иконки", custom_id="icon_url", required=False, placeholder="https://example.com/icon.png"),
            ui.TextInput(label="Теги (через запятую)", custom_id="tags", required=False, placeholder="PvP, PvE, Клан", max_length=100),
        ]
        super().__init__(title="🏰 Создание клана", custom_id="create_clan_final", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        if await self.bot.is_banned_from_clans(self.user_id):
            return await inter.followup.send("⛔ Вы забанены в клановой системе.", ephemeral=True)
        if await self.bot.get_user_clan(self.user_id):
            return await inter.followup.send("❌ Вы уже состоите в клане.", ephemeral=True)
        tags = inter.text_values.get("tags", "").strip()
        clan_id, msg = await self.bot.create_clan(
            self.guild,
            inter.text_values["name"].strip(),
            inter.text_values.get("description", "").strip(),
            self.user_id,
            self.role_id,
            inter.text_values.get("icon_url", "").strip(),
            "",
            tags,
            1
        )
        if clan_id:
            await inter.followup.send(f"✅ {msg}", ephemeral=True)
            view = ClanTopView(self.bot, self.user_id, self.guild, page=0)
            embed = await view.get_embed(self.guild)
            await inter.edit_original_response(embed=embed, view=view)
        else:
            await inter.followup.send(f"❌ {msg}", ephemeral=True)

# ---------- СЕЛЕКТОРЫ И КОМПОНЕНТЫ (View) ----------
class ModUserSelect(disnake.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="👤 Шаг 1: Выберите пользователя...", min_values=1, max_values=1)
    async def callback(self, interaction: disnake.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

class ModRoleSelect(disnake.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="🏷️ Шаг 2: Выберите роль сервера...", min_values=1, max_values=1)
    async def callback(self, interaction: disnake.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

class ModCreateLinkView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, return_view_callback):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.return_view_callback = return_view_callback
        self.user_select = ModUserSelect()
        self.role_select = ModRoleSelect()
        self.add_item(self.user_select)
        self.add_item(self.role_select)
        self.btn_confirm = disnake.ui.Button(label="Создать связь", emoji="🔗", style=disnake.ButtonStyle.success)
        self.btn_confirm.callback = self.confirm_callback
        self.add_item(self.btn_confirm)
        self.btn_manual = disnake.ui.Button(label="ID роли вручную", emoji="⌨️", style=disnake.ButtonStyle.primary)
        self.btn_manual.callback = self.manual_id_callback
        self.add_item(self.btn_manual)
        self.btn_back = disnake.ui.Button(label="Назад к связям", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def confirm_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.user_select.values or not self.role_select.values:
            return await interaction.followup.send("❌ Заполните оба списка выборов!", ephemeral=True)
        target_member = self.user_select.values[0]
        target_role = self.role_select.values[0]
        await self.bot.db.execute("INSERT OR IGNORE INTO links (user_id, role_id) VALUES (?, ?)", (target_member.id, target_role.id))
        await self.bot.db.commit()
        await interaction.followup.send(f"✅ Связь успешно создана: {target_member.mention} ➔ {target_role.mention}", ephemeral=True)
        await self.return_view_callback(interaction)

    async def manual_id_callback(self, interaction: disnake.Interaction):
        if not self.user_select.values:
            return await interaction.followup.send("❌ Выберите пользователя!", ephemeral=True)
        await interaction.response.send_modal(LinkCreateManualIDModal(self.bot, self.user_select.values[0], self.return_view_callback))

    async def back_callback(self, interaction: disnake.Interaction):
        await self.return_view_callback(interaction)

class DropdownDeleteLink(disnake.ui.Select):
    def __init__(self, bot: "RoleBot", options_list):
        super().__init__(placeholder="❌ Выберите связь для удаления...", options=options_list)
        self.bot = bot

    async def callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id, role_id = map(int, self.values[0].split("_"))
        await self.bot.db.execute("DELETE FROM links WHERE user_id = ? AND role_id = ?", (user_id, role_id))
        await self.bot.db.commit()
        await interaction.followup.send("🗑️ Связь успешно удалена.", ephemeral=True)

class DeleteLinkView(PrivateView):
    def __init__(self, bot: "RoleBot", options_list, author_id: int):
        super().__init__(author_id=author_id)
        self.add_item(DropdownDeleteLink(bot, options_list))

class RoleSelectDropdown(disnake.ui.Select):
    def __init__(self, bot: "RoleBot", options_list, author_id: int):
        super().__init__(placeholder="✨ Выберите роль для настройки...", options=options_list, row=0)
        self.bot = bot
        self.author_id = author_id

    async def callback(self, interaction: disnake.Interaction):
        selected_role_id = int(self.values[0])
        is_mod = await check_is_moderator(interaction.user, self.bot)
        user_role_ids = await self.bot.get_linked_roles(interaction.user.id)
        embed = await build_role_info_embed(interaction.guild, interaction.user, selected_role_id)
        view = SettingsControlView(self.bot, is_mod, user_role_ids, interaction.guild, self.author_id, current_selected=selected_role_id)
        await interaction.response.edit_message(embed=embed, view=view)

class UserRoleSelect(disnake.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Выберите участника сервера...", min_values=1, max_values=1)
    async def callback(self, interaction: disnake.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

class ManageUserRoleView(PrivateView):
    def __init__(self, bot: "RoleBot", is_mod: bool, user_role_ids: list, guild: disnake.Guild, target_role_id: int, author_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.is_mod = is_mod
        self.user_role_ids = user_role_ids
        self.guild = guild
        self.target_role_id = target_role_id
        self.user_select = UserRoleSelect()
        self.add_item(self.user_select)
        self.btn_give = disnake.ui.Button(label="Выдать роль", emoji="<:immsv_fire_in_the_hole:1258497918004891748>", style=disnake.ButtonStyle.success)
        self.btn_give.callback = self.give_role_callback
        self.add_item(self.btn_give)
        self.btn_take = disnake.ui.Button(label="Забрать роль", emoji="<:immsv_ragerage:1526225701014081711>", style=disnake.ButtonStyle.danger)
        self.btn_take.callback = self.take_role_callback
        self.add_item(self.btn_take)
        self.btn_back = disnake.ui.Button(label="", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def give_role_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.user_select.values:
            return await interaction.followup.send("❌ Сначала выберите пользователя!", ephemeral=True)
        target_member = self.user_select.values[0]
        role = self.guild.get_role(self.target_role_id)
        if not role:
            return await interaction.followup.send("❌ Роль не найдена.", ephemeral=True)
        try:
            await target_member.add_roles(role)
            await interaction.followup.send(f"✅ Роль {role.mention} успешно выдана {target_member.mention}!", ephemeral=True)
        except disnake.Forbidden:
            await interaction.followup.send("❌ Недостаточно прав у бота.", ephemeral=True)

    async def take_role_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.user_select.values:
            return await interaction.followup.send("❌ Сначала выберите пользователя!", ephemeral=True)
        target_member = self.user_select.values[0]
        role = self.guild.get_role(self.target_role_id)
        if not role:
            return await interaction.followup.send("❌ Роль не найдена.", ephemeral=True)
        try:
            await target_member.remove_roles(role)
            await interaction.followup.send(f"🗑️ Роль {role.mention} успешно забрана у {target_member.mention}!", ephemeral=True)
        except disnake.Forbidden:
            await interaction.followup.send("❌ У бота недостаточно прав.", ephemeral=True)

    async def back_callback(self, interaction: disnake.Interaction):
        view = SettingsControlView(self.bot, self.is_mod, self.user_role_ids, self.guild, self.author_id, current_selected=self.target_role_id)
        embed = await build_role_info_embed(self.guild, interaction.user, self.target_role_id)
        await interaction.response.edit_message(embed=embed, view=view)

class SettingsControlView(PrivateView):
    def __init__(self, bot: "RoleBot", is_mod: bool, user_role_ids: list, guild: disnake.Guild, author_id: int, current_selected: int = None):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.user_role_ids = user_role_ids
        self.is_mod = is_mod
        self.guild = guild
        if current_selected:
            self.active_role_id = int(current_selected)
        else:
            if user_role_ids:
                first_item = user_role_ids[0]
                self.active_role_id = int(first_item[0]) if isinstance(first_item, (tuple, list)) else int(first_item)
            else:
                self.active_role_id = None
        if len(user_role_ids) > 1:
            options = []
            server_roles = []
            for item in user_role_ids:
                r_id = item[0] if isinstance(item, (tuple, list)) else item
                role = guild.get_role(int(r_id))
                if role:
                    server_roles.append(role)
            server_roles.sort(key=lambda r: r.position, reverse=True)
            for idx, role in enumerate(server_roles):
                options.append(disnake.SelectOption(label=role.name, value=str(role.id), description="🌟 Ценнейшая роль" if idx == 0 else "Доп. Роль", default=(role.id == self.active_role_id)))
            self.add_item(RoleSelectDropdown(self.bot, options, self.author_id))
        if self.active_role_id:
            self.btn_edit = disnake.ui.Button(label="Редактировать роль", emoji="<a:imsv_a_yeah:1258496740374347846>", style=disnake.ButtonStyle.primary, custom_id="btn_edit_role", row=1)
            self.btn_edit.callback = self.edit_single_role_callback
            self.add_item(self.btn_edit)
            self.btn_manage_members = disnake.ui.Button(label="Поделиться с бомжами", emoji="<a:imsv_a_huh:1258496808120877107>", style=disnake.ButtonStyle.primary, custom_id="btn_manage_members", row=1)
            self.btn_manage_members.callback = self.manage_members_callback
            self.add_item(self.btn_manage_members)
        if is_mod:
            self.btn_list = disnake.ui.Button(label="Список связей", emoji="<a:imsv_bc_myloveforyou:1257845474904248331>", style=disnake.ButtonStyle.secondary, custom_id="btn_mod_list", row=2)
            self.btn_list.callback = self.mod_list_callback
            self.add_item(self.btn_list)
            self.btn_link_new = disnake.ui.Button(label="Создать новую связь", emoji="<a:imsv_bc_loveletter:1257845439294865429>", style=disnake.ButtonStyle.success, custom_id="btn_mod_new", row=2)
            self.btn_link_new.callback = self.mod_new_callback
            self.add_item(self.btn_link_new)
        self.btn_back = disnake.ui.Button(label="Назад", emoji="⬅️", style=disnake.ButtonStyle.secondary, custom_id="btn_back_to_hub", row=3)
        self.btn_back.callback = self.back_to_hub_callback
        self.add_item(self.btn_back)

    async def back_to_hub_callback(self, interaction: disnake.Interaction):
        hub = self.bot.get_cog("HubCog")
        if hub:
            embed, view = await hub.get_hub_components(interaction)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("Не удалось загрузить хаб.", ephemeral=True)

    async def edit_single_role_callback(self, interaction: disnake.Interaction):
        if self.active_role_id:
            await interaction.response.send_modal(EditRoleModal(self.bot, self.active_role_id))
        else:
            await interaction.response.send_message("❌ Нет активной роли.", ephemeral=True)

    async def manage_members_callback(self, interaction: disnake.Interaction):
        embeds = interaction.message.embeds
        if embeds:
            embed = embeds[0]
            embed.description = (
                "<a:imsv_buglol:1535105638965846016> Управление доступом к вашей личной роли\n\n"
                f"Вы настраиваете роль: <@&{self.active_role_id}>\n"
                "Выберите бомжа в селекторе ниже и нажмите нужную кнопку действия."
            )
            view = ManageUserRoleView(self.bot, self.is_mod, self.user_role_ids, self.guild, self.active_role_id, self.author_id)
            await interaction.response.edit_message(embed=embed, view=view)

    async def mod_list_callback(self, interaction: disnake.Interaction):
        if not await check_is_moderator(interaction.user, self.bot):
            return await interaction.response.send_message("⛔ Отказано в доступе.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return await interaction.followup.send("🗄️ База данных связей пуста.", ephemeral=True)
        view = ModRolePaginationView(self.bot, self.author_id, self.guild, rows, 0)
        embed = await self.bot.render_paginated_embed(self.guild, rows, 0)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def mod_new_callback(self, interaction: disnake.Interaction):
        if not await check_is_moderator(interaction.user, self.bot):
            return await interaction.response.send_message("⛔ Отказано в доступе.", ephemeral=True)
        async def return_cb(inter):
            async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
                r = await cursor.fetchall()
            await inter.message.edit(embed=await self.bot.render_paginated_embed(self.guild, r, 0), view=ModRolePaginationView(self.bot, self.author_id, self.guild, r, 0))
        view = ModCreateLinkView(self.bot, self.author_id, return_cb)
        embed = disnake.Embed(title="➕ Создать новую связь", description="Выберите параметры:")
        await interaction.response.edit_message(embed=embed, view=view)

class ProfilePeriodView(PrivateView):
    def __init__(self, bot: "RoleBot", target_user: disnake.Member, original_embed: disnake.Embed, total_count: int, author_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.target_user = target_user
        self.original_embed = original_embed
        self.total_count = total_count

    async def get_msg_count_period(self, days: int) -> int:
        time_threshold = int(time.time()) - (days * 24 * 60 * 60)
        async with self.bot.db.execute("SELECT COUNT(*) FROM message_logs WHERE user_id = ? AND timestamp >= ?", (self.target_user.id, time_threshold)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    @disnake.ui.button(label="7 дней", emoji="📅", style=disnake.ButtonStyle.secondary)
    async def period_7_days(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        count = await self.get_msg_count_period(7)
        embed = self.original_embed.copy()
        embed.set_field_at(0, name="💬 Текстовая активность (7 дней)", value=f"{count} сообщ.", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="30 дней", emoji="📆", style=disnake.ButtonStyle.secondary)
    async def period_30_days(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        count = await self.get_msg_count_period(30)
        embed = self.original_embed.copy()
        embed.set_field_at(0, name="💬 Текстовая активность (30 дней)", value=f"{count} сообщ.", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="Всего", emoji="📊", style=disnake.ButtonStyle.primary)
    async def period_all_time(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        embed = self.original_embed.copy()
        embed.set_field_at(0, name="💬 Текстовая активность (Всего)", value=f"{self.total_count} сообщ.", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

class ModRolePaginationView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, rows: list, page: int = 0):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.rows = rows
        self.page = page
        items_per_page = 7
        self.max_pages = max(1, (len(rows) + items_per_page - 1) // items_per_page)
        self.current_slice = rows[page * items_per_page: (page + 1) * items_per_page]
        if self.current_slice:
            options = []
            for idx, (u_id, r_id) in enumerate(self.current_slice):
                member = guild.get_member(u_id)
                role = guild.get_role(r_id)
                label_user = member.name if member else f"ID: {u_id}"
                label_role = role.name if role else f"ID: {r_id}"
                options.append(disnake.SelectOption(label=f"Удалить связь #{idx+1}", description=f"{label_role} ➔ {label_user}", emoji="❌", value=f"{u_id}_{r_id}"))
            self.select_del = disnake.ui.Select(placeholder="❌ Выберите связь для удаления...", options=options, row=0)
            self.select_del.callback = self.select_delete_callback
            self.add_item(self.select_del)
        self.btn_prev = disnake.ui.Button(emoji="⬅️", style=disnake.ButtonStyle.secondary, disabled=(page == 0), row=1)
        self.btn_prev.callback = self.prev_page_callback
        self.add_item(self.btn_prev)
        self.btn_stop = disnake.ui.Button(emoji="⏸️", style=disnake.ButtonStyle.primary, row=1)
        self.btn_stop.callback = self.toggle_module_callback
        self.add_item(self.btn_stop)
        self.btn_next = disnake.ui.Button(emoji="➡️", style=disnake.ButtonStyle.secondary, disabled=(page >= self.max_pages - 1), row=1)
        self.btn_next.callback = self.next_page_callback
        self.add_item(self.btn_next)
        self.btn_add_new = disnake.ui.Button(label="Добавление связи", emoji="➕", style=disnake.ButtonStyle.success, row=2)
        self.btn_add_new.callback = self.add_new_link_callback
        self.add_item(self.btn_add_new)
        self.btn_back_hub = disnake.ui.Button(label="Назад к категориям", emoji="↩️", style=disnake.ButtonStyle.secondary, row=2)
        self.btn_back_hub.callback = self.go_back_to_categories
        self.add_item(self.btn_back_hub)

    async def select_delete_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id, role_id = map(int, self.select_del.values[0].split("_"))
        await self.bot.db.execute("DELETE FROM links WHERE user_id = ? AND role_id = ?", (user_id, role_id))
        await self.bot.db.commit()
        await interaction.followup.send("🗑️ Связь успешно удалена!", ephemeral=True)
        await self.refresh_this_page(interaction)

    async def refresh_this_page(self, interaction: disnake.Interaction):
        async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
            new_rows = await cursor.fetchall()
        max_p = max(1, (len(new_rows) + 6) // 7)
        target_page = min(self.page, max_p - 1)
        embed = await self.bot.render_paginated_embed(self.guild, new_rows, target_page)
        view = ModRolePaginationView(self.bot, self.author_id, self.guild, new_rows, target_page)
        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def prev_page_callback(self, interaction: disnake.Interaction):
        self.page -= 1
        await interaction.response.edit_message(embed=await self.bot.render_paginated_embed(self.guild, self.rows, self.page), view=ModRolePaginationView(self.bot, self.author_id, self.guild, self.rows, self.page))

    async def next_page_callback(self, interaction: disnake.Interaction):
        self.page += 1
        await interaction.response.edit_message(embed=await self.bot.render_paginated_embed(self.guild, self.rows, self.page), view=ModRolePaginationView(self.bot, self.author_id, self.guild, self.rows, self.page))

    async def toggle_module_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await self.bot.get_config("module_roles_enabled")
        new_status = "false" if status != "false" else "true"
        await self.bot.set_config("module_roles_enabled", new_status)
        await interaction.followup.send(f"⏸️ Глобальный статус модуля кастомных ролей изменён на: {'Активен' if new_status == 'true' else 'Не активен'}", ephemeral=True)
        await self.refresh_this_page(interaction)

    async def add_new_link_callback(self, interaction: disnake.Interaction):
        async def return_cb(inter: disnake.Interaction):
            async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
                r = await cursor.fetchall()
            embed = await self.bot.render_paginated_embed(self.guild, r, 0)
            view = ModRolePaginationView(self.bot, self.author_id, self.guild, r, 0)
            if inter.response.is_done():
                await inter.message.edit(embed=embed, view=view)
            else:
                await inter.response.edit_message(embed=embed, view=view)
        await interaction.response.edit_message(embed=disnake.Embed(title="🛡️ Добавление связи"), view=ModCreateLinkView(self.bot, self.author_id, return_cb))

    async def go_back_to_categories(self, interaction: disnake.Interaction):
        await interaction.response.edit_message(embed=await self.bot.build_main_mod_embed(), view=ModCategoryControlView(self.bot, self.author_id))

class VoiceLinksView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, rows: list, page: int = 0):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.rows = rows
        self.page = page
        items_per_page = 7
        self.max_pages = max(1, (len(rows) + items_per_page - 1) // items_per_page)
        self.current_slice = rows[page * items_per_page: (page + 1) * items_per_page]
        if self.current_slice:
            options = []
            for idx, (user_id, channel_id, can_manage) in enumerate(self.current_slice):
                member = guild.get_member(user_id)
                channel = guild.get_channel(channel_id)
                label_user = member.display_name if member else f"ID: {user_id}"
                label_channel = channel.name if channel else f"ID: {channel_id}"
                options.append(disnake.SelectOption(label=f"Удалить связь #{idx+1}", description=f"{label_channel} ➔ {label_user}", emoji="❌", value=f"{user_id}_{channel_id}"))
            self.select_del = disnake.ui.Select(placeholder="❌ Выберите связь для удаления...", options=options, row=0)
            self.select_del.callback = self.select_delete_callback
            self.add_item(self.select_del)
        self.btn_prev = disnake.ui.Button(emoji="⬅️", style=disnake.ButtonStyle.secondary, disabled=(page == 0), row=1)
        self.btn_prev.callback = self.prev_page_callback
        self.add_item(self.btn_prev)
        self.btn_next = disnake.ui.Button(emoji="➡️", style=disnake.ButtonStyle.secondary, disabled=(page >= self.max_pages - 1), row=1)
        self.btn_next.callback = self.next_page_callback
        self.add_item(self.btn_next)
        self.btn_add = disnake.ui.Button(label="➕ Добавить связь", style=disnake.ButtonStyle.success, row=2)
        self.btn_add.callback = self.add_link_callback
        self.add_item(self.btn_add)
        self.btn_back = disnake.ui.Button(label="↩️ Назад", style=disnake.ButtonStyle.secondary, row=2)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def select_delete_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id, channel_id = map(int, self.select_del.values[0].split("_"))
        await self.bot.db.execute("DELETE FROM voice_links WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        await self.bot.db.commit()
        await interaction.followup.send("🗑️ Связь удалена.", ephemeral=True)
        await self.refresh(interaction)

    async def refresh(self, interaction: disnake.Interaction):
        async with self.bot.db.execute("SELECT user_id, channel_id, can_manage FROM voice_links") as cursor:
            new_rows = await cursor.fetchall()
        max_p = max(1, (len(new_rows) + 6) // 7)
        target_page = min(self.page, max_p - 1)
        view = VoiceLinksView(self.bot, self.author_id, self.guild, new_rows, target_page)
        embed = await self.build_embed(self.guild, new_rows, target_page)
        await interaction.edit_original_response(embed=embed, view=view)

    async def build_embed(self, guild, rows, page):
        embed = disnake.Embed(title="📢 Связи голосовых каналов", color=disnake.Color.blue())
        if not rows:
            embed.description = "Нет привязанных каналов."
            return embed
        items_per_page = 7
        current_slice = rows[page * items_per_page: (page + 1) * items_per_page]
        desc = ""
        for idx, (user_id, channel_id, can_manage) in enumerate(current_slice):
            member = guild.get_member(user_id)
            channel = guild.get_channel(channel_id)
            u_name = member.mention if member else f"ID: {user_id}"
            c_name = channel.mention if channel else f"ID: {channel_id}"
            desc += f"#{idx+1}: {u_name} ➔ {c_name} (Упр: {'Да' if can_manage else 'Нет'})\n"
        embed.description = desc
        rem = len(rows) - ((page + 1) * items_per_page)
        embed.set_footer(text=f"И еще {rem} связей" if rem > 0 else f"Страница {page+1} из {max(1, (len(rows)+6)//7)}")
        return embed

    async def prev_page_callback(self, interaction: disnake.Interaction):
        self.page -= 1
        await self.refresh(interaction)

    async def next_page_callback(self, interaction: disnake.Interaction):
        self.page += 1
        await self.refresh(interaction)

    async def add_link_callback(self, interaction: disnake.Interaction):
        await interaction.response.send_modal(AddVoiceLinkModal(self.bot, self.author_id, self.guild))

    async def back_callback(self, interaction: disnake.Interaction):
        embed = await self.bot.build_main_mod_embed()
        await interaction.response.edit_message(embed=embed, view=ModCategoryControlView(self.bot, self.author_id))

class ModCategoryControlView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        options = [
            disnake.SelectOption(label="Кастомные роли", emoji="🏷️", value="modcat_roles"),
            disnake.SelectOption(label="Персонализация (Профили)", emoji="🎨", value="modcat_profiles"),
            disnake.SelectOption(label="Ранговая система (XP)", emoji="⭐", value="modcat_ranks"),
            disnake.SelectOption(label="Информация", emoji="📊", value="modcat_info"),
            disnake.SelectOption(label="Связи войсов", emoji="🎙️", value="modcat_voice"),
            disnake.SelectOption(label="Модерирование", emoji="🔨", value="modcat_mod")
        ]
        self.select_cat = disnake.ui.Select(placeholder="🗂️ Выберите категорию для управления...", options=options)
        self.select_cat.callback = self.change_category_callback
        self.add_item(self.select_cat)

    async def change_category_callback(self, interaction: disnake.Interaction):
        cat = self.select_cat.values.replace("modcat_", "")
        if cat == "roles":
            async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
                rows = await cursor.fetchall()
            await interaction.response.edit_message(embed=await self.bot.render_paginated_embed(interaction.guild, rows, 0), view=ModRolePaginationView(self.bot, self.author_id, interaction.guild, rows, 0))
        elif cat == "mod":
            await interaction.response.defer(ephemeral=True)
            k = "module_mod_enabled"
            s = "false" if await self.bot.get_config(k) != "false" else "true"
            await self.bot.set_config(k, s)
            await interaction.message.edit(embed=await self.bot.build_main_mod_embed(), view=self)
            await interaction.followup.send(f"🔨 Модуль глобальных систем модерации изменён на: {'🟢 Активен' if s=='true' else '🔴 Отключен'}", ephemeral=True)
        elif cat == "profiles":
            view = ModProfilePermissionsView(self.bot, self.author_id, interaction.guild)
            await view.populate_roles()
            embed = disnake.Embed(
                title="🎨 Управление правами на профили",
                description="Настройте, какая роль может использовать команду изменения профиля.",
                color=disnake.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        elif cat == "voice":
            async with self.bot.db.execute("SELECT user_id, channel_id, can_manage FROM voice_links") as cursor:
                rows = await cursor.fetchall()
            view = VoiceLinksView(self.bot, self.author_id, interaction.guild, rows, 0)
            embed = await view.build_embed(interaction.guild, rows, 0)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.defer(ephemeral=True)
            k = f"module_{cat}_enabled"
            s = "false" if await self.bot.get_config(k) != "false" else "true"
            await self.bot.set_config(k, s)
            await interaction.message.edit(embed=await self.bot.build_main_mod_embed(), view=self)
            await interaction.followup.send(f"🔄 Статус модуля `{cat}` изменён на: {'Активен' if s=='true' else 'Не активен'}", ephemeral=True)

class ModProfilePermissionsView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.current_command = "profile-edit"

        self.command_select = disnake.ui.Select(
            placeholder="Выберите команду...",
            options=[
                disnake.SelectOption(label="i.profile-edit", value="profile-edit", description="Изменение профиля")
            ],
            row=0
        )
        self.command_select.callback = self.command_select_callback
        self.add_item(self.command_select)

        self.role_select = disnake.ui.Select(
            placeholder="Выберите роль...",
            row=1
        )
        self.role_select.callback = self.role_select_callback
        self.add_item(self.role_select)

        self.btn_save = disnake.ui.Button(label="💾 Сохранить", style=disnake.ButtonStyle.success, row=2)
        self.btn_save.callback = self.save_callback
        self.add_item(self.btn_save)

        self.btn_back = disnake.ui.Button(label="◀️ Назад", style=disnake.ButtonStyle.secondary, row=2)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

        self._populated = False

    async def populate_roles(self):
        if self._populated:
            return
        current_role_id = await self.bot.get_command_permission(self.current_command)
        options = [
            disnake.SelectOption(
                label="❌ Без роли (только модераторы)",
                value="0",
                default=(current_role_id is None)
            )
        ]
        for role in sorted(self.guild.roles, key=lambda r: r.position, reverse=True):
            if role.is_default():
                continue
            options.append(
                disnake.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    default=(role.id == current_role_id)
                )
            )
        self.role_select.options = options[:25]
        self._populated = True

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if not self._populated:
            await self.populate_roles()
        return True

    async def command_select_callback(self, interaction: disnake.MessageInteraction):
        self.current_command = self.command_select.values[0]
        self._populated = False
        await self.populate_roles()
        await interaction.response.edit_message(view=self)

    async def role_select_callback(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)

    async def save_callback(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        selected_role_id = int(self.role_select.values[0]) if self.role_select.values else 0
        if selected_role_id == 0:
            await self.bot.set_command_permission(self.current_command, None)
            msg = f"Право на команду `i.{self.current_command}` снято (только модераторы)."
        else:
            await self.bot.set_command_permission(self.current_command, selected_role_id)
            role = self.guild.get_role(selected_role_id)
            msg = f"Команду `i.{self.current_command}` теперь могут использовать участники с ролью {role.mention}."
        await interaction.followup.send(f"✅ {msg}", ephemeral=True)
        self._populated = False
        await self.populate_roles()
        await interaction.edit_original_response(view=self)

    async def back_callback(self, interaction: disnake.MessageInteraction):
        embed = await self.bot.build_main_mod_embed()
        view = ModCategoryControlView(self.bot, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ModGiveXPView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.selected_amount = 500
        self.selected_type = "text"
        self.user_select = UserRoleSelect()
        self.add_item(self.user_select)
        xp_options = [
            disnake.SelectOption(label="+100 XP", value="100"),
            disnake.SelectOption(label="+500 XP (Стандарт)", value="500", default=True),
            disnake.SelectOption(label="+1000 XP", value="1000"),
            disnake.SelectOption(label="+5000 XP (Много)", value="5000")
        ]
        self.select_amount = disnake.ui.Select(placeholder="🪙 Выберите количество XP...", options=xp_options)
        self.select_amount.callback = self.amount_callback
        self.add_item(self.select_amount)
        type_options = [
            disnake.SelectOption(label="💬 Текстовый опыт (Чат)", value="text", default=True),
            disnake.SelectOption(label="🎙️ Голосовой опыт (Войс)", value="voice")
        ]
        self.select_type = disnake.ui.Select(placeholder="🗂️ Выберите тип опыта...", options=type_options)
        self.select_type.callback = self.type_callback
        self.add_item(self.select_type)
        self.btn_confirm = disnake.ui.Button(label="Начислить опыт", emoji="🔗", style=disnake.ButtonStyle.success)
        self.btn_confirm.callback = self.confirm_xp_callback
        self.add_item(self.btn_confirm)
        self.btn_back = disnake.ui.Button(label="Назад к категориям", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def amount_callback(self, interaction: disnake.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        self.selected_amount = int(self.select_amount.values[0])

    async def type_callback(self, interaction: disnake.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        self.selected_type = self.select_type.values[0]

    async def confirm_xp_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.user_select.values:
            return await interaction.followup.send("❌ Сначала выберите пользователя в верхнем меню!", ephemeral=True)
        target_member = self.user_select.values[0]
        if self.selected_type == "voice":
            await self.bot.db.execute("INSERT INTO levels (user_id, voice_xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET voice_xp = voice_xp + ?", (target_member.id, self.selected_amount, self.selected_amount))
            label = "голосового"
        else:
            await self.bot.db.execute("INSERT INTO levels (user_id, xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?", (target_member.id, self.selected_amount, self.selected_amount))
            label = "текстового"
        await self.bot.db.commit()
        await interaction.followup.send(f"✅ Успешно начислено `{self.selected_amount}` {label} опыта пользователю {target_member.mention}!", ephemeral=True)

    async def back_callback(self, interaction: disnake.Interaction):
        embed = await self.bot.build_main_mod_embed()
        await interaction.response.edit_message(embed=embed, view=ModCategoryControlView(self.bot, self.author_id))

class ModRanksManagementView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot

    @disnake.ui.button(label="Пауза/Старт XP", emoji="⏳", style=disnake.ButtonStyle.primary)
    async def toggle_xp(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        await interaction.response.defer(ephemeral=True)
        status = await self.bot.get_config("module_ranks_enabled")
        new_status = "false" if status != "false" else "true"
        await self.bot.set_config("module_ranks_enabled", new_status)
        embed = disnake.Embed(title="🛡️ Управление Ранговой системой (XP)", color=disnake.Color.red())
        embed.description = f"Текущий статус начисления опыта: {'активен' if new_status == 'true' else 'не активен'}"
        await interaction.message.edit(embed=embed, view=self)

    @disnake.ui.button(label="Выдать опыт участнику", emoji="🪙", style=disnake.ButtonStyle.success)
    async def give_xp_modal(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        await interaction.response.send_modal(ModGiveXPModal(self.bot))

    @disnake.ui.button(label="Назад к категориям", emoji="↩️", style=disnake.ButtonStyle.secondary)
    async def back_to_cats(self, interaction: disnake.Interaction, button: disnake.ui.Button):
        await interaction.response.edit_message(embed=await self.bot.build_main_mod_embed(), view=ModCategoryControlView(self.bot, self.author_id))

# ==================== КЛАССЫ КЛАНОВ ====================
class ClanTopView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, page: int = 0):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.page = page
        self.items_per_page = 5
        self.select_clan = None
        self.btn_prev = disnake.ui.Button(emoji="◀️", style=disnake.ButtonStyle.secondary, disabled=(page == 0), row=1)
        self.btn_prev.callback = self.prev_page
        self.add_item(self.btn_prev)
        self.btn_next = disnake.ui.Button(emoji="▶️", style=disnake.ButtonStyle.secondary, row=1)
        self.btn_next.callback = self.next_page
        self.add_item(self.btn_next)
        self.btn_my_clan = disnake.ui.Button(label="🏠 Мой клан", style=disnake.ButtonStyle.primary, disabled=True, row=2)
        self.btn_my_clan.callback = self.my_clan_callback
        self.add_item(self.btn_my_clan)
        self.btn_invites = disnake.ui.Button(label="📨 Приглашения (0)", style=disnake.ButtonStyle.secondary, disabled=True, row=2)
        self.btn_invites.callback = self.invites_callback
        self.add_item(self.btn_invites)
        self.btn_create = disnake.ui.Button(label="✨ Создать клан", emoji="➕", style=disnake.ButtonStyle.success, row=2)
        self.btn_create.callback = self.create_clan_callback
        self.add_item(self.btn_create)
        self.btn_shop = disnake.ui.Button(label="🏪 Магазин", style=disnake.ButtonStyle.blurple, row=2)
        self.btn_shop.callback = self.shop_callback
        self.add_item(self.btn_shop)

    async def get_embed(self, guild: disnake.Guild):
        if await self.bot.is_banned_from_clans(self.author_id):
            return disnake.Embed(title="⛔ Доступ запрещен", description="Вы были забанены в клановой системе и не можете просматривать кланы.", color=disnake.Color.red())
        total = await self.bot.count_clans(guild.id)
        max_pages = max(1, (total + self.items_per_page - 1) // self.items_per_page)
        if self.page >= max_pages:
            self.page = max_pages - 1
        offset = self.page * self.items_per_page
        clans = await self.bot.get_all_clans(guild.id, self.items_per_page, offset)
        embed = disnake.Embed(title="<:immsv_sword:1535118141791670323> **ТОП КЛАНОВ СЕРВЕРА** <:immsv_sword:1535118141791670323>", color=disnake.Color.from_rgb(255, 215, 0))
        embed.description = "═══════════════════════════════════\n"
        embed.set_footer(text=f"🏆 Всего кланов: {total} • Страница {self.page+1} из {max_pages}", icon_url=guild.icon.url if guild.icon else None)
        if not clans:
            embed.description += "\n🌸 На сервере пока нет кланов.\nСоздайте свой и станьте легендой! 🌸"
        else:
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
            for idx, (clan_id, name, icon_url, leader_id, xp, wins, tags) in enumerate(clans, start=offset+1):
                display_name = format_clan_name(name, tags or "")
                leader = guild.get_member(leader_id)
                leader_name = leader.mention if leader else f"ID: {leader_id}"
                member_count = await self.bot.get_clan_member_count(clan_id)
                lvl, _, _ = calculate_lvl_and_remaining(xp)
                medal = medals[idx-1] if idx <= 5 else "🔹"
                embed.description += (
                    f"\n{medal} **`#{idx}`** **{display_name}**\n"
                    f"┌─ 📊 **Уровень:** `{lvl}` • **XP:** `{xp}`\n"
                    f"├─ 👑 **Лидер:** {leader_name}\n"
                    f"└─ 👥 **Участников:** `{member_count} / 5`\n"
                    "────────────────────────────\n"
                )
        if clans:
            options = []
            for clan_id, name, icon_url, leader_id, xp, wins, tags in clans:
                display_name = format_clan_name(name, tags or "")
                lvl, _, _ = calculate_lvl_and_remaining(xp)
                options.append(disnake.SelectOption(label=display_name, value=str(clan_id), description=f"Уровень {lvl} • {xp} XP", emoji="🏰"))
            if self.select_clan:
                self.remove_item(self.select_clan)
            self.select_clan = disnake.ui.Select(placeholder="🔍 Выберите клан для просмотра...", options=options, row=0)
            self.select_clan.callback = self.select_clan_callback
            self.add_item(self.select_clan)
        user_clan = await self.bot.get_user_clan(self.author_id)
        self.btn_my_clan.disabled = (user_clan is None)
        self.btn_create.disabled = (user_clan is not None or await self.bot.is_banned_from_clans(self.author_id))
        invites = await self.bot.get_user_invites(self.author_id)
        invite_count = len([i for i in invites if i[2] == 'pending'])
        self.btn_invites.disabled = (invite_count == 0)
        self.btn_invites.label = f"📨 Приглашения ({invite_count})"
        return embed

    async def update_message(self, interaction: disnake.Interaction):
        embed = await self.get_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: disnake.Interaction):
        self.page -= 1
        await self.update_message(interaction)

    async def next_page(self, interaction: disnake.Interaction):
        self.page += 1
        await self.update_message(interaction)

    async def my_clan_callback(self, interaction: disnake.Interaction):
        clan_id = await self.bot.get_user_clan(self.author_id)
        if not clan_id:
            return await interaction.response.send_message("❌ Вы не состоите в клане.", ephemeral=True)
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        view = ClanPageView(self.bot, self.author_id, self.guild, clan_id)
        embed = await view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def invites_callback(self, interaction: disnake.Interaction):
        invites = await self.bot.get_user_invites(self.author_id)
        pending = [i for i in invites if i[2] == 'pending']
        if not pending:
            return await interaction.response.send_message("📭 У вас нет приглашений.", ephemeral=True)
        invite_data = []
        for invite_id, clan_id, status, inviter_id, timestamp in pending:
            clan = await self.bot.get_clan(clan_id)
            if clan:
                invite_data.append((invite_id, clan[1], inviter_id, timestamp))
        view = ClanInvitesView(self.bot, self.author_id, self.guild, invite_data)
        embed = disnake.Embed(title="📨 Ваши приглашения в кланы", color=disnake.Color.blue())
        desc = ""
        for invite_id, clan_name, inviter_id, timestamp in invite_data:
            inviter = self.guild.get_member(inviter_id)
            inviter_name = inviter.mention if inviter else f"ID: {inviter_id}"
            desc += f"• **{clan_name}** — пригласил {inviter_name} (<t:{timestamp}:R>)\n"
        embed.description = desc
        await interaction.response.edit_message(embed=embed, view=view)

    async def select_clan_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        clan_id = int(self.select_clan.values[0])
        view = ClanPageView(self.bot, self.author_id, self.guild, clan_id)
        embed = await view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def create_clan_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        if await self.bot.get_user_clan(self.author_id):
            return await interaction.response.send_message("❌ Вы уже состоите в клане!", ephemeral=True)
        await interaction.response.send_modal(CreateClanModal(self.bot, interaction.user))

    async def shop_callback(self, interaction: disnake.Interaction):
        embed = disnake.Embed(title="🏪 Магазин кланов", description="Здесь будут доступны улучшения для клана!\n\n🛒 **В разработке**\n• Расширение участников\n• Улучшение XP\n• Кастомные иконки\n• И многое другое...", color=disnake.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ClanPageView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_id = clan_id
        self.is_owner = (author_id == MY_DISCORD_ID)
        self.btn_back = disnake.ui.Button(label="", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)
        self.btn_members = disnake.ui.Button(label="👥 Участники (0/5)", style=disnake.ButtonStyle.primary)
        self.btn_members.callback = self.members_callback
        self.add_item(self.btn_members)
        self.btn_leave = disnake.ui.Button(label="🚪 Выйти из клана", style=disnake.ButtonStyle.danger, disabled=True)
        self.btn_leave.callback = self.leave_callback
        self.add_item(self.btn_leave)
        self.btn_apply = disnake.ui.Button(label="📩 Подать заявку", style=disnake.ButtonStyle.primary, disabled=True)
        self.btn_apply.callback = self.apply_callback
        self.add_item(self.btn_apply)
        self.btn_requests = disnake.ui.Button(label="📋 Заявки (0)", style=disnake.ButtonStyle.secondary, disabled=True)
        self.btn_requests.callback = self.requests_callback
        self.add_item(self.btn_requests)
        self.btn_edit = disnake.ui.Button(label="✏️ Изменить", style=disnake.ButtonStyle.primary, disabled=True)
        self.btn_edit.callback = self.edit_callback
        self.add_item(self.btn_edit)
        self.btn_delete = disnake.ui.Button(label="🗑️ Удалить клан", style=disnake.ButtonStyle.danger, disabled=True)
        self.btn_delete.callback = self.delete_callback
        self.add_item(self.btn_delete)
        self.btn_auto_role = disnake.ui.Button(label="🔘 Автовыдача роли: Вкл", style=disnake.ButtonStyle.success, disabled=True)
        self.btn_auto_role.callback = self.auto_role_callback
        self.add_item(self.btn_auto_role)
        self.btn_change_role = disnake.ui.Button(label="🎭 Изменить роль клана", style=disnake.ButtonStyle.primary, disabled=True)
        self.btn_change_role.callback = self.change_role_callback
        self.add_item(self.btn_change_role)

    async def get_embed(self):
        if await self.bot.is_banned_from_clans(self.author_id):
            return disnake.Embed(title="⛔ Доступ запрещен", description="Вы были забанены в клановой системе.", color=disnake.Color.red())
        clan = await self.bot.get_clan(self.clan_id)
        if not clan:
            return disnake.Embed(title="❌ Клан не найден", color=disnake.Color.red())
        clan_id, name, description, icon_url, banner_url, leader_id, role_id, guild_id, xp, wins, created_at, tags, auto_role = clan
        display_name = format_clan_name(name, tags or "")
        embed = disnake.Embed(title=f"🏰 {display_name}", color=disnake.Color.from_rgb(100, 149, 237))
        if icon_url:
            embed.set_thumbnail(url=icon_url)
        if banner_url:
            embed.set_image(url=banner_url)
        embed.description = f"*{description or 'Описание отсутствует'}*\n\n"
        lvl, current_xp, needed_xp = calculate_lvl_and_remaining(xp)
        bar = generate_custom_progress_bar(current_xp, needed_xp)
        embed.add_field(name="📊 Прогресс клана", value=f"**Уровень:** `{lvl}`\n{bar} `{current_xp}/{needed_xp}` XP", inline=False)
        coins = await self.bot.get_clan_coins(self.clan_id)
        members = await self.bot.get_clan_members_all(self.clan_id)
        member_count = len(members)
        max_members = 5
        requests_count = await self.bot.get_clan_requests_count(self.clan_id)
        embed.add_field(name="👑 Лидер", value=f"<a:zzz_crown:1535104585620791306> <@{leader_id}>", inline=True)
        embed.add_field(name="👥 Участники", value=f"`{member_count} / {max_members}`", inline=True)
        embed.add_field(name="<:immsv_coinsuka:1251157794980364429> Монеты", value=f"`{coins}`", inline=True)
        embed.add_field(name="🏆 Победы", value=f"`{wins}` *(в разработке)*", inline=True)
        embed.add_field(name="🎭 Роль клана", value=f"<@&{role_id}>", inline=True)
        embed.set_footer(text=f"📅 Создан: <t:{created_at}:R>")
        user_id = self.author_id
        is_leader = (leader_id == user_id)
        user_clan = await self.bot.get_user_clan(user_id)
        is_member = (user_clan == self.clan_id)
        is_owner = self.is_owner
        is_full = member_count >= max_members
        self.btn_members.label = f"👥 Участники ({member_count}/{max_members})"
        self.btn_members.disabled = False
        self.btn_leave.disabled = not is_member or is_leader
        self.btn_leave.label = "🚪 Выйти из клана" if is_member else "❌ Не в клане"
        self.btn_apply.disabled = is_member or is_leader or is_full
        self.btn_apply.label = "📩 Подать заявку" if not is_member else "✅ В клане"
        if is_full and not is_member:
            self.btn_apply.label = "⛔ Клан полон"
        self.btn_requests.disabled = not (is_leader or is_owner)
        self.btn_requests.label = f"📋 Заявки ({requests_count})"
        self.btn_edit.disabled = not (is_leader or is_owner)
        self.btn_delete.disabled = not (is_leader or is_owner)
        can_manage = is_leader or is_owner
        self.btn_auto_role.disabled = not can_manage
        self.btn_auto_role.label = f"🔘 Автовыдача роли: {'Вкл' if auto_role else 'Выкл'}"
        self.btn_auto_role.style = disnake.ButtonStyle.success if auto_role else disnake.ButtonStyle.danger
        self.btn_change_role.disabled = not is_owner
        return embed

    async def change_role_callback(self, interaction: disnake.Interaction):
        if interaction.user.id != MY_DISCORD_ID:
            return await interaction.response.send_message("⛔ Только создатель бота может использовать эту кнопку.", ephemeral=True)
        clan = await self.bot.get_clan(self.clan_id)
        if not clan:
            return await interaction.response.send_message("❌ Клан не найден.", ephemeral=True)
        all_roles = sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True)
        role_options = []
        for role in all_roles:
            if role.is_default():
                continue
            role_options.append(disnake.SelectOption(label=role.name, value=str(role.id), description=f"ID: {role.id}"))
        if not role_options:
            return await interaction.response.send_message("❌ На сервере нет ролей.", ephemeral=True)
        clan_data = {'clan_id': self.clan_id}
        view = ClanRoleSelectView(self.bot, interaction.user.id, interaction.guild, clan_data, role_options, is_edit=True)
        embed = disnake.Embed(title="🎭 Изменение роли клана (создатель)", description="Выберите новую роль для клана.", color=disnake.Color.gold())
        await interaction.response.edit_message(embed=embed, view=view)

    async def auto_role_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        is_leader = (await self.bot.get_clan_leader(self.clan_id) == self.author_id)
        is_owner = (self.author_id == MY_DISCORD_ID)
        if not (is_leader or is_owner):
            return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
        clan = await self.bot.get_clan(self.clan_id)
        if not clan:
            return await interaction.response.send_message("❌ Клан не найден.", ephemeral=True)
        new_auto = 0 if clan[12] else 1
        await self.bot.update_clan(self.clan_id, auto_role=new_auto)
        await interaction.response.send_message(f"✅ Автовыдача роли {'включена' if new_auto else 'выключена'}.", ephemeral=True)
        view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = await view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    async def members_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        members = await self.bot.get_clan_members_all(self.clan_id)
        is_leader = (await self.bot.get_clan_leader(self.clan_id) == self.author_id)
        is_owner = (self.author_id == MY_DISCORD_ID)
        if not members:
            return await interaction.response.send_message("❌ В клане нет участников.", ephemeral=True)
        view = ClanMembersView(self.bot, self.author_id, self.guild, self.clan_id, members, is_leader or is_owner)
        embed = disnake.Embed(title="👥 Участники клана", color=disnake.Color.blue())
        desc = ""
        for user_id, contribution, role in members:
            member = self.guild.get_member(user_id)
            name = member.mention if member else f"ID: {user_id}"
            emoji = "👑" if role == "leader" else "⭐"
            desc += f"{emoji} {name} — **{contribution}** XP\n"
        embed.description = desc
        embed.set_footer(text="Лидер может кикнуть участников через кнопку ниже")
        await interaction.response.edit_message(embed=embed, view=view)

    async def back_callback(self, interaction: disnake.Interaction):
        view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
        embed = await view.get_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    async def apply_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        members = await self.bot.get_clan_members_all(self.clan_id)
        if len(members) >= 5:
            return await interaction.response.send_message("❌ Клан достиг лимита участников (5/5).", ephemeral=True)
        if await self.bot.get_user_clan(self.author_id):
            return await interaction.response.send_message("❌ Вы уже состоите в клане.", ephemeral=True)
        success, msg = await self.bot.create_clan_request(self.clan_id, self.author_id)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = await view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    async def leave_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        user_clan = await self.bot.get_user_clan(self.author_id)
        if user_clan != self.clan_id:
            return await interaction.response.send_message("❌ Вы не состоите в этом клане.", ephemeral=True)
        leader = await self.bot.get_clan_leader(self.clan_id)
        if leader == self.author_id:
            return await interaction.response.send_message("❌ Лидер не может выйти из клана. Используйте кнопку 'Удалить клан'.", ephemeral=True)
        clan = await self.bot.get_clan(self.clan_id)
        if clan:
            role = self.guild.get_role(clan[6])
            if role:
                try:
                    await interaction.user.remove_roles(role)
                except disnake.Forbidden:
                    pass
        await self.bot.remove_clan_member(self.clan_id, self.author_id)
        await self.bot.db.execute("DELETE FROM clan_requests WHERE clan_id = ? AND user_id = ?", (self.clan_id, self.author_id))
        await self.bot.db.commit()
        await interaction.response.send_message("✅ Вы вышли из клана.", ephemeral=True)
        view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
        embed = await view.get_embed(self.guild)
        await interaction.edit_original_response(embed=embed, view=view)

    async def requests_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        requests = await self.bot.get_clan_requests(self.clan_id, 'pending')
        if not requests:
            return await interaction.response.send_message("📭 Нет ожидающих заявок.", ephemeral=True)
        view = ClanRequestsSelectView(self.bot, self.author_id, self.guild, self.clan_id, requests)
        embed = disnake.Embed(title="📋 Заявки на вступление", color=disnake.Color.gold())
        desc = ""
        for req_id, user_id, timestamp in requests:
            member = self.guild.get_member(user_id)
            name = member.mention if member else f"ID: {user_id}"
            desc += f"• {name} (<t:{timestamp}:R>)\n"
        embed.description = desc
        await interaction.response.edit_message(embed=embed, view=view)

    async def edit_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        is_leader = (await self.bot.get_clan_leader(self.clan_id) == self.author_id)
        is_owner = (self.author_id == MY_DISCORD_ID)
        if not (is_leader or is_owner):
            return await interaction.response.send_message("❌ У вас нет прав на редактирование клана.", ephemeral=True)
        clan = await self.bot.get_clan(self.clan_id)
        if not clan:
            return await interaction.response.send_message("❌ Клан не найден.", ephemeral=True)
        current_data = {
            'name': clan[1],
            'description': clan[2],
            'icon_url': clan[3],
            'banner_url': clan[4],
            'tags': clan[11] if len(clan) > 11 else ""
        }
        await interaction.response.send_modal(EditClanModal(self.bot, self.clan_id, current_data))

    async def delete_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        is_leader = (await self.bot.get_clan_leader(self.clan_id) == self.author_id)
        is_owner = (self.author_id == MY_DISCORD_ID)
        if not (is_leader or is_owner):
            return await interaction.response.send_message("❌ У вас нет прав на удаление клана.", ephemeral=True)
        view = ConfirmDeleteView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = disnake.Embed(title="⚠️ Подтверждение удаления", description="Вы уверены, что хотите удалить этот клан? Это действие необратимо!", color=disnake.Color.red())
        await interaction.response.edit_message(embed=embed, view=view)

class ClanMembersView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_id: int, members: list, can_kick: bool):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_id = clan_id
        self.members = members
        self.can_kick = can_kick
        if can_kick:
            options = []
            for user_id, contribution, role in members:
                if role == 'leader':
                    continue
                member = guild.get_member(user_id)
                name = member.display_name if member else f"ID: {user_id}"
                options.append(disnake.SelectOption(label=name, value=str(user_id), description=f"Вклад: {contribution} XP"))
            if options:
                self.select_kick = disnake.ui.Select(placeholder="👤 Выберите участника для кика...", options=options)
                self.select_kick.callback = self.kick_callback
                self.add_item(self.select_kick)
        self.btn_back = disnake.ui.Button(label="Назад", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def kick_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        user_id = int(self.select_kick.values[0])
        member = self.guild.get_member(user_id)
        if not member:
            return await interaction.response.send_message("❌ Пользователь не найден.", ephemeral=True)
        is_leader = (await self.bot.get_clan_leader(self.clan_id) == self.author_id)
        is_owner = (self.author_id == MY_DISCORD_ID)
        if not (is_leader or is_owner):
            return await interaction.response.send_message("❌ У вас нет прав на кик участников.", ephemeral=True)
        success, msg = await self.bot.kick_from_clan(self.clan_id, user_id)
        if success:
            clan = await self.bot.get_clan(self.clan_id)
            if clan:
                role = self.guild.get_role(clan[6])
                if role:
                    try:
                        await member.remove_roles(role)
                    except disnake.Forbidden:
                        pass
            await interaction.response.send_message(f"✅ {member.mention} исключен из клана.", ephemeral=True)
            await self.bot.db.execute("DELETE FROM clan_requests WHERE clan_id = ? AND user_id = ?", (self.clan_id, user_id))
            await self.bot.db.commit()
            new_members = await self.bot.get_clan_members_all(self.clan_id)
            view = ClanMembersView(self.bot, self.author_id, self.guild, self.clan_id, new_members, True)
            embed = disnake.Embed(title="👥 Участники клана", color=disnake.Color.blue())
            desc = ""
            for uid, contribution, role in new_members:
                m = self.guild.get_member(uid)
                name = m.mention if m else f"ID: {uid}"
                emoji = "👑" if role == "leader" else "⭐"
                desc += f"{emoji} {name} — **{contribution}** XP\n"
            embed.description = desc
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def back_callback(self, interaction: disnake.Interaction):
        view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = await view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class ClanRequestsSelectView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_id: int, requests: list):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_id = clan_id
        self.requests = requests
        options = []
        for req_id, user_id, timestamp in requests:
            member = guild.get_member(user_id)
            name = member.display_name if member else f"ID: {user_id}"
            options.append(disnake.SelectOption(label=name, value=str(req_id), description=f"Подана <t:{timestamp}:R>"))
        if options:
            self.select_request = disnake.ui.Select(placeholder="Выберите заявку...", options=options)
            self.select_request.callback = self.select_callback
            self.add_item(self.select_request)
        self.btn_accept_all = disnake.ui.Button(label="✅ Принять все", style=disnake.ButtonStyle.success)
        self.btn_accept_all.callback = self.accept_all_callback
        self.add_item(self.btn_accept_all)
        self.btn_decline_all = disnake.ui.Button(label="❌ Отклонить все", style=disnake.ButtonStyle.danger)
        self.btn_decline_all.callback = self.decline_all_callback
        self.add_item(self.btn_decline_all)
        self.btn_back = disnake.ui.Button(label="Назад", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def select_callback(self, interaction: disnake.Interaction):
        req_id = int(self.select_request.values[0])
        view = SingleRequestActionView(self.bot, self.author_id, self.guild, self.clan_id, req_id)
        embed = disnake.Embed(title="📋 Действие с заявкой", description="Выберите действие для выбранной заявки.", color=disnake.Color.gold())
        await interaction.response.edit_message(embed=embed, view=view)

    async def accept_all_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for req_id, user_id, timestamp in self.requests:
            success, _ = await self.bot.accept_clan_request(req_id, self.guild)
            if success:
                count += 1
        await interaction.followup.send(f"✅ Принято заявок: {count}", ephemeral=True)
        await self.refresh(interaction)

    async def decline_all_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for req_id, user_id, timestamp in self.requests:
            success, _ = await self.bot.decline_clan_request(req_id)
            if success:
                count += 1
        await interaction.followup.send(f"✅ Отклонено заявок: {count}", ephemeral=True)
        await self.refresh(interaction)

    async def refresh(self, interaction: disnake.Interaction):
        requests = await self.bot.get_clan_requests(self.clan_id, 'pending')
        if not requests:
            view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
            embed = await view.get_embed()
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            view = ClanRequestsSelectView(self.bot, self.author_id, self.guild, self.clan_id, requests)
            embed = disnake.Embed(title="📋 Заявки на вступление", color=disnake.Color.gold())
            desc = ""
            for req_id, user_id, timestamp in requests:
                member = self.guild.get_member(user_id)
                name = member.mention if member else f"ID: {user_id}"
                desc += f"• {name} (<t:{timestamp}:R>)\n"
            embed.description = desc
            await interaction.edit_original_response(embed=embed, view=view)

    async def back_callback(self, interaction: disnake.Interaction):
        view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = await view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class SingleRequestActionView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_id: int, req_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_id = clan_id
        self.req_id = req_id
        self.btn_accept = disnake.ui.Button(label="✅ Принять", style=disnake.ButtonStyle.success)
        self.btn_accept.callback = self.accept_callback
        self.add_item(self.btn_accept)
        self.btn_decline = disnake.ui.Button(label="❌ Отклонить", style=disnake.ButtonStyle.danger)
        self.btn_decline.callback = self.decline_callback
        self.add_item(self.btn_decline)
        self.btn_back = disnake.ui.Button(label="Назад к списку", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def accept_callback(self, interaction: disnake.Interaction):
        members = await self.bot.get_clan_members_all(self.clan_id)
        if len(members) >= 5:
            return await interaction.response.send_message("❌ Клан достиг лимита участников (5/5).", ephemeral=True)
        success, msg = await self.bot.accept_clan_request(self.req_id, self.guild)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        await self.refresh(interaction)

    async def decline_callback(self, interaction: disnake.Interaction):
        success, msg = await self.bot.decline_clan_request(self.req_id)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        await self.refresh(interaction)

    async def refresh(self, interaction: disnake.Interaction):
        requests = await self.bot.get_clan_requests(self.clan_id, 'pending')
        if not requests:
            view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
            embed = await view.get_embed()
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            view = ClanRequestsSelectView(self.bot, self.author_id, self.guild, self.clan_id, requests)
            embed = disnake.Embed(title="📋 Заявки на вступление", color=disnake.Color.gold())
            desc = ""
            for req_id, user_id, timestamp in requests:
                member = self.guild.get_member(user_id)
                name = member.mention if member else f"ID: {user_id}"
                desc += f"• {name} (<t:{timestamp}:R>)\n"
            embed.description = desc
            await interaction.edit_original_response(embed=embed, view=view)

    async def back_callback(self, interaction: disnake.Interaction):
        requests = await self.bot.get_clan_requests(self.clan_id, 'pending')
        view = ClanRequestsSelectView(self.bot, self.author_id, self.guild, self.clan_id, requests)
        embed = disnake.Embed(title="📋 Заявки на вступление", color=disnake.Color.gold())
        desc = ""
        for req_id, user_id, timestamp in requests:
            member = self.guild.get_member(user_id)
            name = member.mention if member else f"ID: {user_id}"
            desc += f"• {name} (<t:{timestamp}:R>)\n"
        embed.description = desc
        await interaction.response.edit_message(embed=embed, view=view)

class ClanInvitesView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, invite_data: list):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.invite_data = invite_data
        for invite_id, clan_name, inviter_id, timestamp in invite_data:
            accept_btn = disnake.ui.Button(label=f"✅ Вступить в {clan_name}", style=disnake.ButtonStyle.success, custom_id=f"invite_accept_{invite_id}")
            accept_btn.callback = self.accept_invite_callback
            self.add_item(accept_btn)
            decline_btn = disnake.ui.Button(label="❌ Отклонить", style=disnake.ButtonStyle.danger, custom_id=f"invite_decline_{invite_id}")
            decline_btn.callback = self.decline_invite_callback
            self.add_item(decline_btn)
        self.btn_back = disnake.ui.Button(label="Назад", emoji="⬅️", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def accept_invite_callback(self, interaction: disnake.Interaction):
        invite_id = int(interaction.data["custom_id"].split("_")[2])
        async with self.bot.db.execute("SELECT clan_id FROM clan_invites WHERE id = ?", (invite_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message("❌ Приглашение не найдено.", ephemeral=True)
            clan_id = row[0]
        if await self.bot.get_user_clan(self.author_id):
            return await interaction.response.send_message("❌ Вы уже состоите в клане.", ephemeral=True)
        members = await self.bot.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return await interaction.response.send_message("❌ Клан достиг лимита участников (5/5).", ephemeral=True)
        success, msg = await self.bot.accept_clan_invite(invite_id, self.guild)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        await self.refresh(interaction)

    async def decline_invite_callback(self, interaction: disnake.Interaction):
        invite_id = int(interaction.data["custom_id"].split("_")[2])
        success, msg = await self.bot.decline_clan_invite(invite_id)
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        await self.refresh(interaction)

    async def refresh(self, interaction: disnake.Interaction):
        invites = await self.bot.get_user_invites(self.author_id)
        pending = [i for i in invites if i[2] == 'pending']
        if not pending:
            view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
            embed = await view.get_embed(self.guild)
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            invite_data = []
            for invite_id, clan_id, status, inviter_id, timestamp in pending:
                clan = await self.bot.get_clan(clan_id)
                if clan:
                    invite_data.append((invite_id, clan[1], inviter_id, timestamp))
            view = ClanInvitesView(self.bot, self.author_id, self.guild, invite_data)
            embed = disnake.Embed(title="📨 Ваши приглашения в кланы", color=disnake.Color.blue())
            desc = ""
            for invite_id, clan_name, inviter_id, timestamp in invite_data:
                inviter = self.guild.get_member(inviter_id)
                inviter_name = inviter.mention if inviter else f"ID: {inviter_id}"
                desc += f"• **{clan_name}** — пригласил {inviter_name} (<t:{timestamp}:R>)\n"
            embed.description = desc
            await interaction.edit_original_response(embed=embed, view=view)

    async def back_callback(self, interaction: disnake.Interaction):
        view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
        embed = await view.get_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class ConfirmDeleteView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_id = clan_id
        self.btn_confirm = disnake.ui.Button(label="✅ Да, удалить", style=disnake.ButtonStyle.danger)
        self.btn_confirm.callback = self.confirm_callback
        self.add_item(self.btn_confirm)
        self.btn_cancel = disnake.ui.Button(label="❌ Отмена", style=disnake.ButtonStyle.secondary)
        self.btn_cancel.callback = self.cancel_callback
        self.add_item(self.btn_cancel)

    async def confirm_callback(self, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        clan = await self.bot.get_clan(self.clan_id)
        if clan:
            role = self.guild.get_role(clan[6])
            if role:
                for member in role.members:
                    try:
                        await member.remove_roles(role)
                    except disnake.Forbidden:
                        pass
        success, msg = await self.bot.delete_clan(self.clan_id)
        await interaction.followup.send(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
        view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
        embed = await view.get_embed(self.guild)
        await interaction.edit_original_response(embed=embed, view=view)

    async def cancel_callback(self, interaction: disnake.Interaction):
        view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_id)
        embed = await view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class InviteAcceptView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, clan_id: int, inviter_id: int):
        super().__init__(author_id=author_id, timeout=300)
        self.bot = bot
        self.clan_id = clan_id
        self.inviter_id = inviter_id
        self.btn_accept = disnake.ui.Button(label="✅ Принять приглашение", style=disnake.ButtonStyle.success, emoji="✅")
        self.btn_accept.callback = self.accept_callback
        self.add_item(self.btn_accept)
        self.btn_decline = disnake.ui.Button(label="❌ Отклонить", style=disnake.ButtonStyle.danger, emoji="❌")
        self.btn_decline.callback = self.decline_callback
        self.add_item(self.btn_decline)

    async def accept_callback(self, interaction: disnake.Interaction):
        if await self.bot.is_banned_from_clans(self.author_id):
            return await interaction.response.send_message("⛔ Вы забанены в клановой системе.", ephemeral=True)
        if await self.bot.get_user_clan(self.author_id):
            return await interaction.response.send_message("❌ Вы уже состоите в клане.", ephemeral=True)
        members = await self.bot.get_clan_members_all(self.clan_id)
        if len(members) >= 5:
            return await interaction.response.send_message("❌ Клан достиг лимита участников (5/5).", ephemeral=True)
        success, msg = await self.bot.accept_clan_invite_by_clan(self.clan_id, self.author_id, interaction.guild)
        if success:
            embed = disnake.Embed(title="✅ Приглашение принято!", description=f"{interaction.user.mention} вступил в клан!", color=disnake.Color.green())
            await interaction.response.edit_message(embed=embed, view=None)
            await interaction.followup.send(f"✅ {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def decline_callback(self, interaction: disnake.Interaction):
        embed = disnake.Embed(title="❌ Приглашение отклонено", description=f"{interaction.user.mention} отклонил приглашение.", color=disnake.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
        await self.bot.decline_clan_invite_by_clan(self.clan_id, self.author_id)

class CreateClanRoleSelectView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, linked_roles: list):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.linked_roles = linked_roles
        options = []
        for role_id in linked_roles:
            role = guild.get_role(role_id)
            if role:
                options.append(disnake.SelectOption(label=role.name, value=str(role.id), description="Кастомная роль"))
        if options:
            self.select_role = disnake.ui.Select(placeholder="Выберите роль для клана...", options=options)
            self.select_role.callback = self.select_callback
            self.add_item(self.select_role)
        self.btn_cancel = disnake.ui.Button(label="Отмена", style=disnake.ButtonStyle.secondary)
        self.btn_cancel.callback = self.cancel_callback
        self.add_item(self.btn_cancel)

    async def select_callback(self, interaction: disnake.Interaction):
        role_id = int(self.select_role.values[0])
        await interaction.response.send_modal(CreateClanModalFinal(self.bot, self.author_id, role_id, self.guild))
        await interaction.delete_original_response()

    async def cancel_callback(self, interaction: disnake.Interaction):
        await interaction.response.edit_message(content="❌ Создание клана отменено.", embed=None, view=None)

class ClanOwnerControlView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.btn_ban = disnake.ui.Button(label="🚫 Управление банами", style=disnake.ButtonStyle.danger, custom_id="ban_control")
        self.btn_ban.callback = self.ban_control_callback
        self.add_item(self.btn_ban)
        self.btn_back = disnake.ui.Button(label="⬅️ Назад к кланам", style=disnake.ButtonStyle.secondary)
        self.btn_back.callback = self.back_callback
        self.add_item(self.btn_back)

    async def ban_control_callback(self, interaction: disnake.Interaction):
        embed = disnake.Embed(title="🚫 Управление банами в клановой системе", description="Выберите действие ниже:", color=disnake.Color.gold())
        view = disnake.ui.View()
        ban_btn = disnake.ui.Button(label="🔨 Забанить пользователя", style=disnake.ButtonStyle.danger, custom_id="ban_user")
        ban_btn.callback = self.ban_user_callback
        view.add_item(ban_btn)
        unban_btn = disnake.ui.Button(label="🔓 Разбанить пользователя", style=disnake.ButtonStyle.success, custom_id="unban_user")
        unban_btn.callback = self.unban_user_callback
        view.add_item(unban_btn)
        list_btn = disnake.ui.Button(label="📋 Список забаненных", style=disnake.ButtonStyle.primary, custom_id="list_banned")
        list_btn.callback = self.list_banned_callback
        view.add_item(list_btn)
        back_btn = disnake.ui.Button(label="⬅️ Назад", style=disnake.ButtonStyle.secondary, custom_id="back_from_ban")
        back_btn.callback = self.back_callback
        view.add_item(back_btn)
        await interaction.response.edit_message(embed=embed, view=view)

    async def ban_user_callback(self, interaction: disnake.Interaction):
        await interaction.response.send_modal(BanUserModal(self.bot))

    async def unban_user_callback(self, interaction: disnake.Interaction):
        await interaction.response.send_modal(UnbanUserModal(self.bot))

    async def list_banned_callback(self, interaction: disnake.Interaction):
        banned = await self.bot.get_banned_users()
        if not banned:
            return await interaction.response.send_message("📭 Нет забаненных пользователей.", ephemeral=True)
        embed = disnake.Embed(title="📋 Забаненные пользователи", color=disnake.Color.red())
        desc = ""
        for (user_id,) in banned:
            member = self.guild.get_member(user_id)
            name = member.mention if member else f"ID: {user_id}"
            desc += f"• {name}\n"
        embed.description = desc
        await interaction.response.edit_message(embed=embed)

    async def back_callback(self, interaction: disnake.Interaction):
        view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
        embed = await view.get_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class ClanRoleSelectView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, clan_data: dict, role_options: list, is_edit: bool = False):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.clan_data = clan_data
        self.is_edit = is_edit
        if not role_options:
            self.add_item(disnake.ui.Button(label="❌ Нет доступных ролей", disabled=True, style=disnake.ButtonStyle.danger))
            return
        self.select = disnake.ui.Select(placeholder="Выберите роль для клана...", options=role_options[:25])
        self.select.callback = self.select_callback
        self.add_item(self.select)
        self.btn_cancel = disnake.ui.Button(label="Отмена", style=disnake.ButtonStyle.secondary, emoji="❌")
        self.btn_cancel.callback = self.cancel_callback
        self.add_item(self.btn_cancel)

    async def select_callback(self, interaction: disnake.Interaction):
        selected_role_id = int(self.select.values[0])
        self.clan_data['role_id'] = selected_role_id
        if self.is_edit:
            success, msg = await self.bot.update_clan(self.clan_data['clan_id'], role_id=selected_role_id)
            await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)
            view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_data['clan_id'])
            embed = await view.get_embed()
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            clan_id, msg = await self.bot.create_clan(
                self.guild,
                self.clan_data['name'],
                self.clan_data['description'],
                self.author_id,
                selected_role_id,
                self.clan_data.get('icon_url', ''),
                self.clan_data.get('banner_url', ''),
                self.clan_data.get('tags', ''),
                1
            )
            if clan_id:
                await interaction.response.send_message(f"✅ {msg}", ephemeral=True)
                view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
                embed = await view.get_embed(self.guild)
                await interaction.edit_original_response(embed=embed, view=view)
            else:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def cancel_callback(self, interaction: disnake.Interaction):
        if self.is_edit:
            view = ClanPageView(self.bot, self.author_id, self.guild, self.clan_data['clan_id'])
            embed = await view.get_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            view = ClanTopView(self.bot, self.author_id, self.guild, page=0)
            embed = await view.get_embed(self.guild)
            await interaction.response.edit_message(embed=embed, view=view)

# ==================== ХАБ И ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ ====================
class TopLeaderboardView(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int, guild: disnake.Guild, sort_type: str = "total", page: int = 0):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.guild = guild
        self.sort_type = sort_type
        self.page = page
        self.items_per_page = 10
        self.btn_total = disnake.ui.Button(label="Общий Топ", emoji="🏆", style=disnake.ButtonStyle.primary if sort_type == "total" else disnake.ButtonStyle.secondary, row=0)
        self.btn_total.callback = self.set_sort_total
        self.add_item(self.btn_total)
        self.btn_text = disnake.ui.Button(label="Топ Чата", emoji="💬", style=disnake.ButtonStyle.primary if sort_type == "text" else disnake.ButtonStyle.secondary, row=0)
        self.btn_text.callback = self.set_sort_text
        self.add_item(self.btn_text)
        self.btn_voice = disnake.ui.Button(label="Топ Войса", emoji="🎙️", style=disnake.ButtonStyle.primary if sort_type == "voice" else disnake.ButtonStyle.secondary, row=0)
        self.btn_voice.callback = self.set_sort_voice
        self.add_item(self.btn_voice)
        self.btn_prev = disnake.ui.Button(emoji="◀️", style=disnake.ButtonStyle.secondary, disabled=(page == 0), row=1)
        self.btn_prev.callback = self.prev_page
        self.add_item(self.btn_prev)
        self.btn_next = disnake.ui.Button(emoji="▶️", style=disnake.ButtonStyle.secondary, row=1)
        self.btn_next.callback = self.next_page
        self.add_item(self.btn_next)

    async def update_top_message(self, interaction_or_ctx):
        if self.sort_type == "text":
            query = "SELECT user_id, xp, voice_xp FROM levels ORDER BY xp DESC"
            title = "🏆 Таблица Лидеров (Топ по сообщениям)"
        elif self.sort_type == "voice":
            query = "SELECT user_id, xp, voice_xp FROM levels ORDER BY voice_xp DESC"
            title = "🏆 Таблица Лидеров (Топ по активности в Войсе)"
        else:
            query = "SELECT user_id, xp, voice_xp FROM levels ORDER BY (xp + voice_xp) DESC"
            title = "🏆 Таблица Лидеров Сервера (Общий Топ по XP)"
        async with self.bot.db.execute(query) as cursor:
            rows = await cursor.fetchall()
        max_pages = max(1, (len(rows) + self.items_per_page - 1) // self.items_per_page)
        self.page = min(self.page, max_pages - 1)
        self.btn_next.disabled = (self.page >= max_pages - 1)
        self.btn_prev.disabled = (self.page == 0)
        embed = disnake.Embed(title=title, color=disnake.Color.gold())
        if self.guild.icon:
            embed.set_thumbnail(url=self.guild.icon.url)
        if not rows:
            embed.description = "‿︵‿︵‿︵‿︵‿୨♡୧‿︵‿︵‿︵‿︵‿\n\n*Данные в этой категории отсутствуют.*"
            if isinstance(interaction_or_ctx, disnake.Interaction):
                await interaction_or_ctx.response.edit_message(embed=embed, view=self)
            else:
                return embed
        current_slice = rows[self.page * self.items_per_page : (self.page + 1) * self.items_per_page]
        desc = "‿︵‿︵‿︵‿︵‿୨♡୧‿︵‿︵‿︵‿︵‿\n\n"
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅"]
        for idx, (u_id, txp, vxp) in enumerate(current_slice):
            global_idx = (self.page * self.items_per_page) + idx
            medal = medals[global_idx] if global_idx < len(medals) else "🏅"
            member = self.guild.get_member(u_id)
            m_text = member.mention if member else f"Участник [ID: {u_id}]"
            total = txp + vxp
            if self.sort_type == "text":
                desc += f"{medal} **#{global_idx+1}** — {m_text} ➔ **`{txp}` XP** *(Войс: {vxp})*\n\n"
            elif self.sort_type == "voice":
                desc += f"{medal} **#{global_idx+1}** — {m_text} ➔ **`{vxp}` XP** *(Чат: {txp})*\n\n"
            else:
                desc += f"{medal} **#{global_idx+1}** — {m_text} ➔ **`{total}` XP**\n   └─ 💬 Чат: `{txp}` | 🎙️ Войс: `{vxp}`\n\n"
        embed.description = desc
        embed.set_footer(text=f"Страница {self.page+1} из {max_pages}")
        if isinstance(interaction_or_ctx, disnake.Interaction):
            if not interaction_or_ctx.response.is_done():
                await interaction_or_ctx.response.edit_message(embed=embed, view=self)
            else:
                await interaction_or_ctx.message.edit(embed=embed, view=self)
        else:
            return embed

    async def set_sort_total(self, interaction: disnake.Interaction):
        self.sort_type = "total"
        self.page = 0
        await self.update_top_message(interaction)

    async def set_sort_text(self, interaction: disnake.Interaction):
        self.sort_type = "text"
        self.page = 0
        await self.update_top_message(interaction)

    async def set_sort_voice(self, interaction: disnake.Interaction):
        self.sort_type = "voice"
        self.page = 0
        await self.update_top_message(interaction)

    async def prev_page(self, interaction: disnake.Interaction):
        self.page -= 1
        await self.update_top_message(interaction)

    async def next_page(self, interaction: disnake.Interaction):
        self.page += 1
        await self.update_top_message(interaction)

# ==================== КОГ ОСНОВНОЙ (HUB) ====================
class HubCog(commands.Cog):
    def __init__(self, bot: "RoleBot"):
        self.bot = bot
        self.help_categories = {
            "ГЛАВНЫЕ": [
                "`i.hub` — Открыть хаб",
                "`i.help` — Эта справка",
                "`i.profile [@user]` — Показать профиль",
                "`i.profile-edit [описание] [#цвет] (баннер файлом или remove)` — Изменить профиль"
            ],
            "РАНГИ": ["`i.lvl` — Мой уровень", "`i.top` — Топ сервера"],
            "МОДЕРАЦИЯ": ["`i.lvl-set` — Установить уровень", "`i.xp-add` — Добавить опыт", "`/modrole_set` — Роль модератора", "`i.profile-edit` — Изменить профиль (доступ ограничен ролью в настройках)"],
            "КЛАНЫ": ["`i.req` — Подать заявку", "`i.accept` — Принять заявку", "`i.decline` — Отклонить заявку", "`i.invite` — Пригласить", "`i.clan-money-set` — Установить монеты", "`i.clan-money-add` — Добавить монеты"],
            "РАЗВЛЕЧЕНИЯ": ["`i.clone-emoji` — Клонировать эмодзи"]
        }
        logger.info("✅ HubCog успешно загружен!")

    async def get_hub_components(self, interaction_or_ctx):
        header_emojis = (
            "<:1_immsv:1536837791764324362>"
            "<:2_immsv:1536837801989898403>"
            "<:3_immsv:1536837811473227847>"
            "<:4_immsv:1536837820339982436>"
            "<:5_immsv:1536837827566899331>"
            "<:6_immsv:1536837836408623194>"
            "<:7_immsv:1536837843073368125>"
            "<:8_immsv:1536837869665128688>"
            "<:9_immsv:1536837901604622416>"
        )
        embed = disnake.Embed(
            title="🏠 Центральный хаб",
            description=(
                f"{header_emojis}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "<a:imsv_BongoCat:1258500185089249411> **ДОБРО ПОЖАЛОВАТЬ В ЦЕНТРАЛЬНЫЙ ХАБ**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "<a:imsv_pinkarrow3:1286674447759310940> **О Боте & Уникальность**\n"
                "Это полностью **кастомный бот**, написанный специально для нашего сервера! "
                "Он абсолютно бесплатный и предоставляет эксклюзивный функционал управления ролями и профилями. <a:imsv_2RainbowCat2:1258497122593148999>\n\n"
                "<a:imsv_blue_bow:1244283695674687551> **Поддержка Проекта**\n"
                "Бот развивается на чистом энтузиазме. Если вы хотите ускорить выход обновлений "
                "или просто сказать «спасибо», вы можете **поддержать создателя финансово**! Любой донат помогает "
                "оплачивать стабильный хостинг. <a:imsv_hearts4:1292492376194945044>\n\n"
                "<a:zzz_voskl:1530628292342972536> **Важная Информация**\n"
                "• Возникли вопросы по функционалу? Используйте команду `i.help`\n"
                "• Не знаете с чего начать? Разверните меню навигации прямо под этим сообщением! <a:imsv_pinkarrow2:1251194238260084856>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=disnake.Color.from_rgb(255, 105, 180)
        )
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1287816387754201108/1535781712808906843/8xh12p9.png?ex=6a81956d&is=6a8043ed&hm=00e6eb901d0ddf792ac57aab3fe48156ca0a8d432bc759b9f2af06091ca77dd3&"
        )

        view = disnake.ui.View()
        view.add_item(
            disnake.ui.Button(
                label="Профиль",
                custom_id="hub_profile",
                style=disnake.ButtonStyle.primary,
                emoji="<:zzz_pen:1535105077667303424>"
            )
        )
        view.add_item(
            disnake.ui.Button(
                label="Кастомные роли",
                custom_id="hub_roles",
                style=disnake.ButtonStyle.primary,
                emoji="<a:zzz_crown:1535104585620791306>"
            )
        )
        view.add_item(
            disnake.ui.Button(
                label="Кастомные войсы",
                custom_id="hub_voice",
                style=disnake.ButtonStyle.primary,
                emoji="<a:imsv_pinkwarn:1278812955764457562>"
            )
        )
        view.add_item(
            disnake.ui.Button(
                label="Клановые битвы",
                custom_id="hub_clans",
                style=disnake.ButtonStyle.primary,
                emoji="<:immsv_sword:1535118141791670323>"
            )
        )
        view.add_item(
            disnake.ui.Button(
                label="Развлечения",
                custom_id="hub_entertainment",
                style=disnake.ButtonStyle.primary,
                emoji="🎮"
            )
        )
        author = interaction_or_ctx.author if hasattr(interaction_or_ctx, 'author') else interaction_or_ctx.user
        if await check_is_moderator(author, self.bot):
            view.add_item(
                disnake.ui.Button(
                    label="Настройки модерации",
                    custom_id="hub_settings",
                    style=disnake.ButtonStyle.danger,
                    emoji="<a:imsv_pinkwarn:1278812955764457562>"
                )
            )
        return embed, view

    @commands.command(name="hub")
    async def txt_hub(self, ctx: commands.Context):
        embed, view = await self.get_hub_components(ctx)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="help")
    async def txt_help(self, ctx: commands.Context):
        banner_path = os.path.join(BANNERS_DIR, "serverbanner.png")
        banner_file = None
        banner_url = None
        if os.path.exists(banner_path):
            banner_file = disnake.File(banner_path, filename="serverbanner.png")
            banner_url = f"attachment://serverbanner.png"

        components = [
            ui.TextDisplay(content="## 📖 Доступные команды\nВыберите категорию, чтобы увидеть список команд.")
        ]
        for cat, commands_list in self.help_categories.items():
            components.append(
                ui.Section(
                    ui.TextDisplay(
                        content=(
                            f"🎮 {cat}" if cat == "ГЛАВНЫЕ" else
                            f"📊 {cat}" if cat == "РАНГИ" else
                            f"🛡️ {cat}" if cat == "МОДЕРАЦИЯ" else
                            f"🏰 {cat}" if cat == "КЛАНЫ" else
                            f"🎭 {cat}"
                        )
                    ),
                    accessory=ui.Button(
                        label="Показать",
                        custom_id=f"help_{cat}",
                        style=disnake.ButtonStyle.secondary
                    )
                )
            )

        if banner_url:
            components.append(
                ui.MediaGallery(
                    disnake.MediaGalleryItem(media=banner_url)
                )
            )

        container = ui.Container(
            *components,
            accent_colour=disnake.Colour.blue()
        )

        if banner_file:
            await ctx.send(components=[container], file=banner_file)
        else:
            await ctx.send(components=[container])

    @commands.command(name="profile")
    async def txt_profile(self, ctx: commands.Context, member: disnake.Member = None):
        target = member or ctx.author
        container, banner_file = await self.get_profile_container(target, ctx.guild, ctx.author.id)
        if banner_file:
            await ctx.send(components=[container], file=banner_file)
        else:
            await ctx.send(components=[container])

    @commands.command(name="mod_old")
    async def txt_mod_old(self, ctx: commands.Context):
        if ctx.author.id != MY_DISCORD_ID:
            return await ctx.send("⛔ Только создатель бота может использовать эту команду.")
        embed = disnake.Embed(
            title="🛠️ Старая панель модерации",
            description="Нажмите кнопку, чтобы открыть панель управления (без модуля профилей).",
            color=disnake.Color.gold()
        )
        view = disnake.ui.View()
        view.add_item(
            disnake.ui.Button(
                label="Открыть старую панель",
                custom_id="mod_old_open",
                style=disnake.ButtonStyle.primary
            )
        )
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if isinstance(inter.component, disnake.ui.Select):
            cid = inter.values[0]
        else:
            cid = inter.component.custom_id
        logger.info(f"🔘 Нажата кнопка/выбран пункт: {cid}")

        try:
            if cid == "hub_back":
                embed, view = await self.get_hub_components(inter)
                await inter.response.edit_message(embed=embed, view=view)
                return

            if cid == "help_back":
                embed = disnake.Embed(
                    title="📖 Доступные команды",
                    description="Выберите категорию в меню ниже.",
                    color=disnake.Color.blue()
                )
                view = disnake.ui.View()
                select = disnake.ui.Select(
                    placeholder="Выберите категорию...",
                    options=[
                        disnake.SelectOption(label="🎮 Главные", value="help_main"),
                        disnake.SelectOption(label="📊 Ранги", value="help_ranks"),
                        disnake.SelectOption(label="🛡️ Модерация", value="help_mod"),
                        disnake.SelectOption(label="🏰 Кланы", value="help_clans"),
                        disnake.SelectOption(label="🎭 Развлечения", value="help_entertainment"),
                    ]
                )
                view.add_item(select)
                await inter.response.edit_message(embed=embed, view=view)
                return

            await inter.response.defer(ephemeral=True)

            if cid == "hub_profile":
                container, banner_file = await self.get_profile_container(inter.author, inter.guild, inter.author.id)
                if banner_file:
                    await inter.followup.send(components=[container], file=banner_file, ephemeral=True)
                else:
                    await inter.followup.send(components=[container], ephemeral=True)
                logger.info("Профиль отправлен")

            elif cid == "hub_roles":
                await inter.followup.send("Кастомные роли (в разработке)", ephemeral=True)

            elif cid == "hub_voice":
                await inter.followup.send("Кастомные войсы (в разработке)", ephemeral=True)

            elif cid == "hub_clans":
                await inter.followup.send("Клановые битвы (в разработке)", ephemeral=True)

            elif cid == "hub_entertainment":
                await inter.followup.send("Развлечения (в разработке)", ephemeral=True)

            elif cid == "hub_settings":
                if not await check_is_moderator(inter.author, self.bot):
                    return await inter.followup.send("⛔ У вас нет прав доступа.", ephemeral=True)
                embed = await self.bot.build_main_mod_embed()
                view = ModCategoryControlView(self.bot, inter.author.id)
                await inter.followup.send(embed=embed, view=view, ephemeral=True)

            elif cid == "mod_old_open":
                embed = await self.bot.build_main_mod_embed()
                view = ModCategoryControlViewOld(self.bot, inter.author.id)
                await inter.response.edit_message(embed=embed, view=view)

            elif cid.startswith("help_"):
                category = cid.replace("help_", "")
                commands_list = self.help_categories.get(category, ["Нет команд в этой категории."])
                text = "\n".join(commands_list)
                embed = disnake.Embed(title=f"📂 {category}", description=text, color=disnake.Color.green())
                await inter.followup.send(embed=embed, ephemeral=True)

            elif cid.startswith("clan_go_"):
                clan_id = int(cid.replace("clan_go_", ""))
                view = ClanPageView(self.bot, inter.author.id, inter.guild, clan_id)
                embed = await view.get_embed()
                await inter.followup.send(embed=embed, view=view, ephemeral=True)

            else:
                await inter.followup.send("🛠️ Эта категория в разработке.", ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Ошибка в on_button_click: {e}", exc_info=True)
            try:
                if not inter.response.is_done():
                    await inter.response.send_message("Произошла ошибка.", ephemeral=True)
                else:
                    await inter.followup.send("Произошла ошибка.", ephemeral=True)
            except Exception as e2:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e2}")

    async def get_profile_container(self, user: disnake.Member, guild: disnake.Guild, current_user_id: int):
        async with self.bot.db.execute(
            "SELECT embed_color, status_text, banner_url FROM profiles WHERE user_id = ?",
            (user.id,)
        ) as cursor:
            row = await cursor.fetchone()
        async with self.bot.db.execute(
            "SELECT xp, voice_xp FROM levels WHERE user_id = ?",
            (user.id,)
        ) as cursor:
            lvl_row = await cursor.fetchone()

        emb, st, bn = (row[0], row[1], row[2]) if row else ("#7289da", "Участник сервера", "")
        txp, vxp = (lvl_row[0], lvl_row[1]) if lvl_row else (0, 0)

        text_lvl, text_cxp, text_nxp = calculate_lvl_and_remaining(txp)
        voice_lvl, voice_cxp, voice_nxp = calculate_lvl_and_remaining(vxp)

        text_bar = generate_custom_progress_bar(text_cxp, text_nxp)
        voice_bar = generate_custom_progress_bar(voice_cxp, voice_nxp)

        try:
            col = disnake.Color(int(emb.lstrip("#"), 16))
        except Exception:
            col = disnake.Color.blue()

        clan_tag_suffix = ""
        clan_position = None
        clan_level = None
        clan_name_display = None
        clan_member_count = 0
        clan_id = await self.bot.get_user_clan(user.id)
        if clan_id:
            clan = await self.bot.get_clan(clan_id)
            if clan:
                clan_name_display = format_clan_name(clan[1], clan[11] or "")
                clan_tag_suffix = f"《{clan[11]}》" if clan[11] else ""
                clan_level, _, _ = calculate_lvl_and_remaining(clan[8])
                clan_member_count = await self.bot.get_clan_member_count(clan_id)
                async with self.bot.db.execute(
                    "SELECT COUNT(*) FROM clans WHERE guild_id = ? AND xp > ?",
                    (guild.id, clan[8])
                ) as cur:
                    pos_row = await cur.fetchone()
                    clan_position = (pos_row[0] if pos_row else 0) + 1

        async with self.bot.db.execute(
            "SELECT COUNT(*) FROM message_logs WHERE user_id = ?",
            (user.id,)
        ) as cursor:
            total_msgs_row = await cursor.fetchone()
        total_msgs = total_msgs_row[0] if total_msgs_row else 0

        user_role_ids = await self.bot.get_linked_roles(user.id)
        roles_text = ", ".join(
            f"<@&{r_id[0]}>" for r_id in user_role_ids
        ) if user_role_ids else "Нет личных ролей"

        attached_file = None
        gif_path = os.path.join(BANNERS_DIR, f"{user.id}.gif")
        png_path = os.path.join(BANNERS_DIR, f"{user.id}.png")
        if os.path.exists(gif_path):
            active_path = gif_path
            filename_banner = f"profile_banner_{user.id}.gif"
        elif os.path.exists(png_path):
            active_path = png_path
            filename_banner = f"profile_banner_{user.id}.png"
        else:
            active_path = None

        components = []

        components.append(
            ui.TextDisplay(content=f"## 👤 Профиль — {user.name}{clan_tag_suffix}")
        )

        components.append(
            ui.TextDisplay(
                content=(
                    f"<a:imsv_bc_hatory_work:1257845094535532604> **Текстовый ранг:** Уровень `{text_lvl}`\n"
                    f"{text_bar}\n`{text_cxp} / {text_nxp}` XP\n\n"
                    f"<a:imsv_butterfly:1526225899995922514> **Голосовой ранг:** Уровень `{voice_lvl}`\n"
                    f"{voice_bar}\n`{voice_cxp} / {voice_nxp}` XP\n\n"
                    f"📊 **Всего сообщений:** {total_msgs}"
                )
            )
        )

        components.append(
            ui.Section(
                ui.TextDisplay(
                    content=(
                        f"📅 **Заход на сервер**\n<t:{int(user.joined_at.timestamp())}:R>\n\n"
                        f"📝 **Статус**\n{st}\n\n"
                        f"🏷️ **Ролей:** {len(user_role_ids)}"
                    )
                ),
                accessory=ui.Thumbnail(
                    media=user.display_avatar.url,
                    description="Аватар"
                )
            )
        )

        if user_role_ids:
            components.append(
                ui.TextDisplay(
                    content=f"🎭 **Привязанные роли**\n{roles_text}"
                )
            )

        components.append(
            ui.TextDisplay(
                content="‿︵‿︵‿︵‿︵‿୨♡୧‿︵‿︵‿︵‿︵‿\n**ДАННЫЕ КЛАНА**"
            )
        )

        if clan_id and clan:
            clan_info = (
                f"**{clan_name_display}**\n"
                f"📊 Уровень: `{clan_level}`  |  👥 Участников: `{clan_member_count}`"
            )
            if clan_position:
                clan_info += f"\n🏅 Позиция в топе: `#{clan_position}`"

            components.append(
                ui.Section(
                    ui.TextDisplay(content=clan_info),
                    accessory=ui.Button(
                        label="➡️ Перейти в клан",
                        custom_id=f"clan_go_{clan_id}",
                        style=disnake.ButtonStyle.success,
                        emoji="<a:zzz_red_arrow_animated:1537916823029157939>"
                    )
                )
            )
        else:
            components.append(
                ui.TextDisplay(content="❌ Не состоит в клане")
            )

        if active_path:
            try:
                attached_file = disnake.File(active_path, filename=filename_banner)
                components.append(
                    ui.MediaGallery(
                        disnake.MediaGalleryItem(media=f"attachment://{filename_banner}")
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка чтения локального баннера: {e}")

        if user.id == current_user_id:
            components.append(
                ui.TextDisplay(
                    content=(
                        "\n✏ *Изменить профиль:* используйте команду `i.profile-edit`\n"
                        "с параметрами `описание` и `#цвет`, а баннер приложите файлом."
                    )
                )
            )

        container = ui.Container(
            *components,
            accent_colour=disnake.Colour.from_rgb(255, 105, 180)
        )

        return container, attached_file

    @commands.command(name="profile-edit")
    async def txt_profile_edit(self, ctx: commands.Context, *, args: str = None):
        if not await check_command_permission(ctx, "profile-edit"):
            return await ctx.send("⛔ У вас нет прав на изменение профиля.")

        logger.info(f"profile-edit вызвана с args: {args}")
        if not args and not ctx.message.attachments:
            return await ctx.send("❌ Укажите хотя бы один параметр: описание, цвет, прикрепите файл с баннером или 'remove' для удаления баннера.")

        if args and args.strip().lower() == "remove":
            banner_action = "remove"
            about = None
            hex_color = None
        else:
            parts = args.split() if args else []
            hex_color = None
            about_parts = []
            for part in reversed(parts):
                if part.startswith("#") and len(part) in (4, 7) and all(c in "0123456789ABCDEFabcdef" for c in part[1:]):
                    hex_color = part
                    break
                else:
                    about_parts.insert(0, part)
            about = " ".join(about_parts) if about_parts else None
            banner_action = None

        logger.info(f"Парсинг: about={about}, hex_color={hex_color}, banner_action={banner_action}")

        if hex_color:
            if not hex_color.startswith("#"):
                hex_color = "#" + hex_color
            try:
                int(hex_color.lstrip("#"), 16)
            except ValueError:
                return await ctx.send("❌ Неверный формат HEX-цвета. Используйте #RRGGBB или RRGGBB.")

        async with self.bot.db.execute(
            "SELECT embed_color, status_text, banner_url FROM profiles WHERE user_id = ?",
            (ctx.author.id,)
        ) as cursor:
            row = await cursor.fetchone()
        current_color, current_status, current_banner = row if row else ("#7289da", "Участник сервера", "")
        logger.info(f"Текущие: цвет={current_color}, статус={current_status}, баннер={current_banner}")

        final_color = hex_color if hex_color else current_color
        final_about = about if about else current_status
        final_banner = current_banner

        if banner_action == "remove":
            for ext in ["png", "gif", "jpg", "jpeg"]:
                old_path = os.path.join(BANNERS_DIR, f"{ctx.author.id}.{ext}")
                if os.path.exists(old_path):
                    os.remove(old_path)
            logger.info(f"Баннер удалён для {ctx.author.id}")
            final_banner = ""
        elif ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                return await ctx.send("❌ Прикреплённый файл не является изображением.")
            is_gif = "gif" in attachment.content_type or attachment.filename.lower().endswith(".gif")
            file_ext = "gif" if is_gif else "png"
            for ext in ["png", "gif", "jpg", "jpeg"]:
                old_path = os.path.join(BANNERS_DIR, f"{ctx.author.id}.{ext}")
                if os.path.exists(old_path):
                    os.remove(old_path)
            banner_path = os.path.join(BANNERS_DIR, f"{ctx.author.id}.{file_ext}")
            await attachment.save(banner_path)
            logger.info(f"Баннер сохранён с расширением {file_ext} для {ctx.author.id}")
            final_banner = ""

        logger.info(f"Итоговые: цвет={final_color}, статус={final_about}, баннер={final_banner}")

        await self.bot.db.execute("""
            INSERT INTO profiles (user_id, embed_color, status_text, banner_url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET embed_color=excluded.embed_color,
            status_text=excluded.status_text, banner_url=excluded.banner_url
        """, (ctx.author.id, final_color, final_about, final_banner))

        await self.bot.db.execute("INSERT OR IGNORE INTO levels (user_id, xp, voice_xp) VALUES (?, 0, 0)", (ctx.author.id,))
        await self.bot.db.commit()

        try:
            await ctx.message.delete()
        except:
            pass

        await ctx.send("✅ Ваш профиль обновлён!", delete_after=5)

    @commands.command(name="lvl")
    async def txt_lvl(self, ctx: commands.Context, member: disnake.Member = None):
        target = member or ctx.author
        async with self.bot.db.execute("SELECT xp, voice_xp FROM levels WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
        txp = row[0] if row else 0
        vxp = row[1] if row else 0
        lvl, cxp, nxp = calculate_lvl_and_remaining(txp)
        v_lvl, v_cxp, v_nxp = calculate_lvl_and_remaining(vxp)
        def make_bar(current, needed):
            slices = 10
            filled = int((current / max(1, needed)) * slices)
            filled = max(0, min(slices, filled))
            return "🟩" * filled + "⬜" * (slices - filled)
        text_bar = make_bar(cxp, nxp)
        voice_bar = make_bar(v_cxp, v_nxp)
        embed = disnake.Embed(color=disnake.Color.gold())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.description = (
            "‿︵‿︵‿︵‿︵‿୨♡୧‿︵‿︵‿︵‿︵‿\n\n"
            f"⭐ **РАНГОВАЯ КАРТОЧКА УЧАСТНИКА: {target.name}**\n\n"
            f"💬 **Текстовый уровень: `{lvl}`**\n"
            f"Прогресс: `{cxp} / {nxp}` XP\n"
            f"|{text_bar}|\n\n"
            f"🎙️ **Голосовой уровень: `{v_lvl}`**\n"
            f"Прогресс: `{v_cxp} / {v_nxp}` XP\n"
            f"|{voice_bar}|\n\n"
            f"🏆 *Суммарный набранный опыт: `{txp + vxp}` XP.*"
        )
        await ctx.send(embed=embed)

    @commands.command(name="top")
    async def txt_top(self, ctx: commands.Context):
        view = TopLeaderboardView(self.bot, ctx.author.id, ctx.guild, sort_type="total", page=0)
        embed = await view.update_top_message(ctx)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="lvl-set")
    async def txt_lvl_set(self, ctx: commands.Context, member: disnake.Member, level: int, xp_type: str = "text"):
        if not await check_is_moderator(ctx.author, self.bot):
            return await ctx.send("⛔ У вас нет прав модератора для использования этой команды.")
        if level <= 0:
            return await ctx.send("❌ Уровень должен быть больше 0.")
        total_xp = 0
        for lvl in range(1, level):
            total_xp += lvl * 100
        if xp_type.lower() == "voice":
            await self.bot.db.execute("INSERT INTO levels (user_id, voice_xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET voice_xp = ?", (member.id, total_xp, total_xp))
            type_label = "голосовой"
        else:
            await self.bot.db.execute("INSERT INTO levels (user_id, xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = ?", (member.id, total_xp, total_xp))
            type_label = "текстовый"
        await self.bot.db.commit()
        await ctx.send(f"✅ Успешно установлен **{type_label}** уровень `{level}` для пользователя {member.mention}!")

    @commands.command(name="xp-add")
    async def txt_xp_add(self, ctx: commands.Context, member: disnake.Member, xp_amount: int, xp_type: str = "text"):
        if not await check_is_moderator(ctx.author, self.bot):
            return await ctx.send("⛔ У вас нет прав модератора для использования этой команды.")
        if xp_amount <= 0:
            return await ctx.send("❌ Количество XP должно быть положительным.")
        if xp_type.lower() == "voice":
            await self.bot.db.execute("INSERT INTO levels (user_id, voice_xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET voice_xp = voice_xp + ?", (member.id, xp_amount, xp_amount))
            type_label = "голосового"
        else:
            await self.bot.db.execute("INSERT INTO levels (user_id, xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?", (member.id, xp_amount, xp_amount))
            type_label = "текстового"
        await self.bot.db.commit()
        await ctx.send(f"✅ Успешно добавлено `{xp_amount}` XP {type_label} опыта пользователю {member.mention}!")

    @commands.command(name="modrole_set")
    async def txt_modrole_set(self, ctx: commands.Context, role: disnake.Role):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("⛔ Только Администратор.")
        await self.bot.set_config("mod_role_id", str(role.id))
        await ctx.send(f"✅ Установлена: {role.mention}")

class ModCategoryControlViewOld(PrivateView):
    def __init__(self, bot: "RoleBot", author_id: int):
        super().__init__(author_id=author_id)
        self.bot = bot
        options = [
            disnake.SelectOption(label="Кастомные роли", emoji="🏷️", value="modcat_roles"),
            disnake.SelectOption(label="Ранговая система (XP)", emoji="⭐", value="modcat_ranks"),
            disnake.SelectOption(label="Информация", emoji="📊", value="modcat_info"),
            disnake.SelectOption(label="Связи войсов", emoji="🎙️", value="modcat_voice"),
            disnake.SelectOption(label="Модерирование", emoji="🔨", value="modcat_mod")
        ]
        self.select_cat = disnake.ui.Select(placeholder="🗂️ Выберите категорию для управления...", options=options)
        self.select_cat.callback = self.change_category_callback
        self.add_item(self.select_cat)

    async def change_category_callback(self, interaction: disnake.Interaction):
        cat = self.select_cat.values.replace("modcat_", "")
        if cat == "roles":
            async with self.bot.db.execute("SELECT user_id, role_id FROM links") as cursor:
                rows = await cursor.fetchall()
            await interaction.response.edit_message(embed=await self.bot.render_paginated_embed(interaction.guild, rows, 0), view=ModRolePaginationView(self.bot, self.author_id, interaction.guild, rows, 0))
        elif cat == "mod":
            await interaction.response.defer(ephemeral=True)
            k = "module_mod_enabled"
            s = "false" if await self.bot.get_config(k) != "false" else "true"
            await self.bot.set_config(k, s)
            await interaction.message.edit(embed=await self.bot.build_main_mod_embed(), view=self)
            await interaction.followup.send(f"🔨 Модуль глобальных систем модерации изменён на: {'🟢 Активен' if s=='true' else '🔴 Отключен'}", ephemeral=True)
        elif cat == "voice":
            async with self.bot.db.execute("SELECT user_id, channel_id, can_manage FROM voice_links") as cursor:
                rows = await cursor.fetchall()
            view = VoiceLinksView(self.bot, self.author_id, interaction.guild, rows, 0)
            embed = await view.build_embed(interaction.guild, rows, 0)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.defer(ephemeral=True)
            k = f"module_{cat}_enabled"
            s = "false" if await self.bot.get_config(k) != "false" else "true"
            await self.bot.set_config(k, s)
            await interaction.message.edit(embed=await self.bot.build_main_mod_embed(), view=self)
            await interaction.followup.send(f"🔄 Статус модуля `{cat}` изменён на: {'Активен' if s=='true' else 'Не активен'}", ephemeral=True)

# ==================== КОГ КЛАНОВ ====================
class ClanCog(commands.Cog):
    def __init__(self, bot: RoleBot):
        self.bot = bot

    @commands.command(name="req")
    async def req_clan(self, ctx: commands.Context, *, clan_name: str):
        if await self.bot.is_banned_from_clans(ctx.author.id):
            return await ctx.send("⛔ Вы забанены в клановой системе.")
        if await self.bot.get_user_clan(ctx.author.id):
            return await ctx.send("❌ Вы уже состоите в клане.")
        clan = await self.bot.get_clan_by_name(clan_name)
        if not clan:
            return await ctx.send("❌ Клан с таким названием не найден.")
        clan_id = clan[0]
        members = await self.bot.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return await ctx.send("❌ Клан достиг лимита участников (5/5).")
        async with self.bot.db.execute("SELECT id FROM clan_requests WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, ctx.author.id)) as cursor:
            if await cursor.fetchone():
                return await ctx.send("❌ Вы уже подали заявку в этот клан.")
        success, msg = await self.bot.create_clan_request(clan_id, ctx.author.id)
        await ctx.send(f"{'✅' if success else '❌'} {msg}")

    @commands.command(name="accept")
    async def accept_req(self, ctx: commands.Context, member: disnake.Member):
        if await self.bot.is_banned_from_clans(ctx.author.id):
            return await ctx.send("⛔ Вы забанены в клановой системе.")
        clan_id = await self.bot.get_user_clan(ctx.author.id)
        if not clan_id:
            return await ctx.send("❌ Вы не состоите в клане.")
        leader = await self.bot.get_clan_leader(clan_id)
        if leader != ctx.author.id:
            return await ctx.send("❌ Только лидер клана может принимать заявки.")
        members = await self.bot.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return await ctx.send("❌ Клан достиг лимита участников (5/5).")
        async with self.bot.db.execute("SELECT id FROM clan_requests WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, member.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send("❌ У этого пользователя нет ожидающей заявки в ваш клан.")
        request_id = row[0]
        success, msg = await self.bot.accept_clan_request(request_id, ctx.guild)
        await ctx.send(f"{'✅' if success else '❌'} {msg}")

    @commands.command(name="decline")
    async def decline_req(self, ctx: commands.Context, member: disnake.Member):
        if await self.bot.is_banned_from_clans(ctx.author.id):
            return await ctx.send("⛔ Вы забанены в клановой системе.")
        clan_id = await self.bot.get_user_clan(ctx.author.id)
        if not clan_id:
            return await ctx.send("❌ Вы не состоите в клане.")
        leader = await self.bot.get_clan_leader(clan_id)
        if leader != ctx.author.id:
            return await ctx.send("❌ Только лидер клана может отклонять заявки.")
        async with self.bot.db.execute("SELECT id FROM clan_requests WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, member.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send("❌ У этого пользователя нет ожидающей заявки в ваш клан.")
        request_id = row[0]
        success, msg = await self.bot.decline_clan_request(request_id)
        await ctx.send(f"{'✅' if success else '❌'} {msg}")

    @commands.command(name="invite")
    async def invite_user(self, ctx: commands.Context, member: disnake.Member):
        if await self.bot.is_banned_from_clans(ctx.author.id):
            return await ctx.send("⛔ Вы забанены в клановой системе.")
        clan_id = await self.bot.get_user_clan(ctx.author.id)
        if not clan_id:
            return await ctx.send("❌ Вы не состоите в клане.")
        leader = await self.bot.get_clan_leader(clan_id)
        is_owner = (ctx.author.id == MY_DISCORD_ID)
        if leader != ctx.author.id and not is_owner:
            return await ctx.send("❌ Только лидер клана или создатель могут приглашать.")
        if await self.bot.get_user_clan(member.id):
            return await ctx.send("❌ Этот пользователь уже состоит в клане.")
        members = await self.bot.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return await ctx.send("❌ Клан достиг лимита участников (5/5).")
        success, msg = await self.bot.create_clan_invite(clan_id, member.id, ctx.author.id)
        if success:
            clan = await self.bot.get_clan(clan_id)
            clan_name = clan[1] if clan else "Клан"
            embed = disnake.Embed(title=f"📨 Приглашение в клан {clan_name}", description=f"{ctx.author.mention} пригласил вас вступить в клан **{clan_name}**!", color=disnake.Color.green())
            embed.add_field(name="⏰ Время", value="Приглашение истекает через 5 минут", inline=False)
            embed.set_footer(text="Нажмите кнопку ниже, чтобы принять приглашение")
            view = InviteAcceptView(self.bot, member.id, clan_id, ctx.author.id)
            await ctx.send(f"{member.mention}, вас пригласили в клан!", embed=embed, view=view)
        else:
            await ctx.send(f"❌ {msg}")

    @commands.command(name="clone-emoji")
    async def clone_emoji(self, ctx: commands.Context, emoji: disnake.PartialEmoji, name: str):
        if not await check_is_moderator(ctx.author, self.bot):
            return await ctx.send("⛔ У вас нет прав.")
        async with aiohttp.ClientSession() as session:
            async with session.get(emoji.url) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Не удалось скачать эмодзи.")
                data = await resp.read()
        try:
            new_emoji = await ctx.guild.create_custom_emoji(name=name, image=data)
            await ctx.send(f"✅ Эмодзи создан: {new_emoji}")
        except disnake.Forbidden:
            await ctx.send("❌ У бота нет прав на создание эмодзи.")
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}")

    @commands.command(name="clan-money-set")
    async def clan_money_set(self, ctx: commands.Context, clan_name: str, amount: int):
        if ctx.author.id != MY_DISCORD_ID:
            return await ctx.send("⛔ Только создатель бота может использовать эту команду.")
        clan = await self.bot.get_clan_by_name(clan_name)
        if not clan:
            return await ctx.send("❌ Клан с таким названием не найден.")
        await self.bot.db.execute("INSERT OR REPLACE INTO clan_coins (clan_id, coins) VALUES (?, ?)", (clan[0], amount))
        await self.bot.db.commit()
        await ctx.send(f"✅ Баланс клана **{clan_name}** установлен на `{amount}` монет.")

    @commands.command(name="clan-money-add")
    async def clan_money_add(self, ctx: commands.Context, clan_name: str, amount: int):
        if ctx.author.id != MY_DISCORD_ID:
            return await ctx.send("⛔ Только создатель бота может использовать эту команду.")
        clan = await self.bot.get_clan_by_name(clan_name)
        if not clan:
            return await ctx.send("❌ Клан с таким названием не найден.")
        current = await self.bot.get_clan_coins(clan[0])
        new_amount = current + amount
        if new_amount < 0:
            new_amount = 0
        await self.bot.db.execute("INSERT OR REPLACE INTO clan_coins (clan_id, coins) VALUES (?, ?)", (clan[0], new_amount))
        await self.bot.db.commit()
        action = "добавлено" if amount > 0 else "отнято"
        await ctx.send(f"✅ {action.capitalize()} `{abs(amount)}` монет у клана **{clan_name}**. Новый баланс: `{new_amount}` монет.")

# ==================== КОГ РАЗВЛЕЧЕНИЙ ====================
class EntertainmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.check_achievements_loop())

    async def check_achievements_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.check_all_achievements()
            await asyncio.sleep(3600)

    async def check_all_achievements(self):
        async with self.bot.db.execute("SELECT id, user1_id, user2_id, since, voice_channel_id, role_id, xp FROM marriages WHERE status = 'active'") as cursor:
            marriages = await cursor.fetchall()
        for marriage in marriages:
            await self.check_marriage_achievements(marriage)

    async def check_marriage_achievements(self, marriage):
        mid, u1, u2, since, voice_channel_id, role_id, xp = marriage
        days = int((time.time() - since) / 86400)
        updates = []
        guild = self.bot.get_guild(GUILD_ID)
        if not guild and self.bot.guilds:
            guild = self.bot.guilds[0]
        if not guild:
            return
        if days >= 30 and not voice_channel_id:
            category_id = 1537376952191549480
            category = guild.get_channel(category_id)
            if category:
                try:
                    overwrites = {
                        guild.default_role: disnake.PermissionOverwrite(view_channel=False),
                        guild.get_member(u1): disnake.PermissionOverwrite(view_channel=True, connect=True),
                        guild.get_member(u2): disnake.PermissionOverwrite(view_channel=True, connect=True)
                    }
                    channel = await guild.create_voice_channel(f"💞 {u1}-{u2}", category=category, overwrites=overwrites, reason="Свадебный канал (30 дней)")
                    await self.bot.db.execute("UPDATE marriages SET voice_channel_id = ? WHERE id = ?", (channel.id, mid))
                    updates.append(f"Создан голосовой канал {channel.mention}")
                except Exception as e:
                    updates.append(f"Не удалось создать канал: {e}")
        if days >= 100 and not role_id:
            updates.append("💝 Вы получили в конверте кастомную роль <:immsv_kizturuncu:1258498297602113556> (свяжитесь с администратором для активации)")
            await self.bot.db.execute("UPDATE marriages SET role_id = -1 WHERE id = ?", (mid,))
        if days >= 365:
            xp_to_add = 10000
            for uid in (u1, u2):
                await self.bot.db.execute("INSERT INTO levels (user_id, xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?", (uid, xp_to_add, xp_to_add))
            await self.bot.db.execute("UPDATE marriages SET xp = xp + ? WHERE id = ?", (xp_to_add, mid))
            updates.append("🎉 Годовщина! Вам начислено по 10000 XP каждому!")
        if updates:
            await self.bot.db.commit()
            for uid in (u1, u2):
                user = self.bot.get_user(uid)
                if user:
                    try:
                        await user.send(f"📢 Достижение в браке!\n" + "\n".join(updates))
                    except:
                        pass

    @commands.command(name="marry")
    async def marry_cmd(self, ctx: commands.Context, member: disnake.Member):
        if member == ctx.author:
            return await ctx.send("❌ Нельзя жениться на себе.")
        async with self.bot.db.execute("SELECT id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            if await cursor.fetchone():
                return await ctx.send("❌ Вы уже состоите в браке.")
        async with self.bot.db.execute("SELECT id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (member.id, member.id)) as cursor:
            if await cursor.fetchone():
                return await ctx.send("❌ Этот пользователь уже состоит в браке.")
        embed = disnake.Embed(title="💍 Предложение руки и сердца", description=f"{ctx.author.mention} делает предложение {member.mention}!", color=disnake.Color.pink())
        embed.set_footer(text="У вас есть 60 секунд, чтобы ответить")
        class MarryView(disnake.ui.View):
            def __init__(self, author_id, target_id, ctx):
                super().__init__(timeout=60)
                self.author_id = author_id
                self.target_id = target_id
                self.ctx = ctx
                self.answered = False
            async def disable_buttons(self, interaction):
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(view=self)
            @disnake.ui.button(label="💍 Согласиться", style=disnake.ButtonStyle.success)
            async def accept(self, interaction: disnake.Interaction, button: disnake.ui.Button):
                if interaction.user.id != self.target_id:
                    return await interaction.response.send_message("❌ Это предложение не вам.", ephemeral=True)
                self.answered = True
                await self.disable_buttons(interaction)
                now = int(time.time())
                async with interaction.client.db.execute("INSERT INTO marriages (user1_id, user2_id, since, status) VALUES (?, ?, ?, 'active')", (self.author_id, self.target_id, now)) as cursor:
                    marriage_id = cursor.lastrowid
                await interaction.client.db.commit()
                await interaction.followup.send("💞 Вы согласились! Брак заключён!", ephemeral=True)
                await self.ctx.send(f"🎉 Поздравляем! {interaction.user.mention} и <@{self.author_id}> теперь в браке!")
            @disnake.ui.button(label="❌ Отказать", style=disnake.ButtonStyle.danger)
            async def decline(self, interaction: disnake.Interaction, button: disnake.ui.Button):
                if interaction.user.id != self.target_id:
                    return await interaction.response.send_message("❌ Это предложение не вам.", ephemeral=True)
                self.answered = True
                await self.disable_buttons(interaction)
                await interaction.followup.send("💔 Отказ принят.", ephemeral=True)
                await self.ctx.send(f"❌ {interaction.user.mention} отказал(а) <@{self.author_id}>.")
            async def on_timeout(self):
                if not self.answered:
                    await self.ctx.send("⏰ Время вышло. Предложение отклонено.")
        view = MarryView(ctx.author.id, member.id)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="marry-set-days")
    @commands.has_permissions(administrator=True)
    async def marry_set_days(self, ctx: commands.Context, user1: disnake.Member, user2: disnake.Member, days: int):
        if days < 0:
            return await ctx.send("❌ Количество дней не может быть отрицательным.")
        async with self.bot.db.execute("SELECT id FROM marriages WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?) AND status = 'active'", (user1.id, user2.id, user2.id, user1.id)) as cursor:
            marriage = await cursor.fetchone()
        if not marriage:
            return await ctx.send("❌ Эти пользователи не состоят в браке.")
        new_since = int(time.time()) - (days * 86400)
        await self.bot.db.execute("UPDATE marriages SET since = ? WHERE id = ?", (new_since, marriage[0]))
        await self.bot.db.commit()
        await ctx.send(f"✅ Количество дней брака для {user1.mention} и {user2.mention} установлено на {days}.")

    @commands.command(name="marry-name")
    async def marry_name_cmd(self, ctx: commands.Context, *, name: str):
        async with self.bot.db.execute("SELECT id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            marriage = await cursor.fetchone()
        if not marriage:
            return await ctx.send("❌ Вы не состоите в браке.")
        if len(name) > 50:
            return await ctx.send("❌ Название не должно превышать 50 символов.")
        await self.bot.db.execute("UPDATE marriages SET name = ? WHERE id = ?", (name, marriage[0]))
        await self.bot.db.commit()
        await ctx.send(f"✅ Название брака установлено: «{name}»")

    @commands.command(name="divorce")
    async def divorce_cmd(self, ctx: commands.Context):
        async with self.bot.db.execute("SELECT id, user1_id, user2_id, voice_channel_id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            marriage = await cursor.fetchone()
        if not marriage:
            return await ctx.send("❌ Вы не состоите в браке.")
        mid, u1, u2, voice_channel_id = marriage
        if voice_channel_id:
            channel = ctx.guild.get_channel(voice_channel_id)
            if channel:
                try:
                    await channel.delete(reason="Развод")
                except:
                    pass
        await self.bot.db.execute("UPDATE marriages SET status = 'divorced' WHERE id = ?", (mid,))
        await self.bot.db.commit()
        await self.bot.db.execute("DELETE FROM voice_links WHERE user_id = ? OR user_id = ?", (u1, u2))
        await self.bot.db.commit()
        embed = disnake.Embed(title="💔 Развод", description=f"{ctx.author.mention} расторг(ла) брак. Сердце разбито...", color=disnake.Color.dark_red())
        await ctx.send(embed=embed)

    @commands.command(name="love-profile")
    async def love_profile_cmd(self, ctx: commands.Context):
        async with self.bot.db.execute("SELECT id, user1_id, user2_id, since, xp, love_status, level FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            marriage = await cursor.fetchone()
        if not marriage:
            return await ctx.send("❌ Вы не состоите в браке.")
        mid, u1, u2, since, xp, love_status, level = marriage
        days = int((time.time() - since) / 86400)
        user1 = self.bot.get_user(u1)
        user2 = self.bot.get_user(u2)
        if not user1 or not user2:
            return await ctx.send("❌ Один из супругов не найден.")
        embed = disnake.Embed(title="💞 Карточка брака", color=disnake.Color.magenta())
        embed.set_thumbnail(url=user1.display_avatar.url)
        embed.set_image(url=user2.display_avatar.url)
        embed.add_field(name="💑 Супруги", value=f"{user1.mention} ❤️ {user2.mention}", inline=False)
        embed.add_field(name="📅 Дата свадьбы", value=f"<t:{since}:D>", inline=True)
        embed.add_field(name="⏳ Дней вместе", value=f"{days} дн.", inline=True)
        embed.add_field(name="📊 Уровень пары", value=f"{level}", inline=True)
        embed.add_field(name="⭐ Опыт пары", value=f"{xp} XP", inline=True)
        embed.add_field(name="💬 Статус", value=love_status or "Не установлен", inline=False)
        embed.set_footer(text="💖 Любовь живёт в мелочах")
        await ctx.send(embed=embed)

    @commands.command(name="love-status")
    async def love_status_cmd(self, ctx: commands.Context, *, status: str = None):
        async with self.bot.db.execute("SELECT id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            marriage = await cursor.fetchone()
        if not marriage:
            return await ctx.send("❌ Вы не состоите в браке.")
        if not status:
            return await ctx.send("❌ Укажите статус: i.love-status <текст>")
        await self.bot.db.execute("UPDATE marriages SET love_status = ? WHERE id = ?", (status, marriage[0]))
        await self.bot.db.commit()
        await ctx.send(f"✅ Статус обновлён: {status}")

    @commands.command(name="hug")
    async def hug_cmd(self, ctx: commands.Context, member: disnake.Member):
        gif = random.choice(HUG_GIFS)
        embed = disnake.Embed(title=f"{ctx.author.name} обнимает {member.name} 🤗", color=disnake.Color.blue())
        embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.command(name="kiss")
    async def kiss_cmd(self, ctx: commands.Context, member: disnake.Member):
        gif = random.choice(KISS_GIFS)
        embed = disnake.Embed(title=f"{ctx.author.name} целует {member.name} 😘", color=disnake.Color.red())
        embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.command(name="family")
    async def family_cmd(self, ctx: commands.Context):
        embed = disnake.Embed(title="🌳 Семейное древо", description="Функция в разработке. Скоро вы сможете создавать семьи и усыновлять участников!", color=disnake.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="room-name")
    async def room_name_cmd(self, ctx: commands.Context, *, name: str):
        async with self.bot.db.execute("SELECT voice_channel_id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
        if not row or not row[0]:
            return await ctx.send("❌ У вас нет свадебного канала (достигните 30 дней).")
        channel = ctx.guild.get_channel(row[0])
        if not channel:
            return await ctx.send("❌ Канал не найден.")
        await channel.edit(name=name)
        await ctx.send(f"✅ Название канала изменено на {name}")

    @commands.command(name="room-limit")
    async def room_limit_cmd(self, ctx: commands.Context, limit: int):
        async with self.bot.db.execute("SELECT voice_channel_id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
        if not row or not row[0]:
            return await ctx.send("❌ У вас нет свадебного канала (достигните 30 дней).")
        channel = ctx.guild.get_channel(row[0])
        if not channel:
            return await ctx.send("❌ Канал не найден.")
        await channel.edit(user_limit=limit)
        await ctx.send(f"✅ Лимит канала установлен на {limit}")

    @commands.command(name="room-access")
    async def room_access_cmd(self, ctx: commands.Context, member: disnake.Member):
        async with self.bot.db.execute("SELECT voice_channel_id FROM marriages WHERE (user1_id = ? OR user2_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
        if not row or not row[0]:
            return await ctx.send("❌ У вас нет свадебного канала (достигните 30 дней).")
        channel = ctx.guild.get_channel(row[0])
        if not channel:
            return await ctx.send("❌ Канал не найден.")
        await channel.set_permissions(member, view_channel=True, connect=True)
        await ctx.send(f"✅ {member.mention} получил доступ к каналу {channel.mention}")

    @commands.command(name="voice-link")
    @commands.has_permissions(administrator=True)
    async def voice_link_cmd(self, ctx: commands.Context, member: disnake.Member, channel: disnake.VoiceChannel):
        await self.bot.db.execute("INSERT OR REPLACE INTO voice_links (user_id, channel_id, can_manage) VALUES (?, ?, 1)", (member.id, channel.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ {member.mention} привязан к {channel.mention}")

    @commands.command(name="voice-unlink")
    @commands.has_permissions(administrator=True)
    async def voice_unlink_cmd(self, ctx: commands.Context, member: disnake.Member):
        await self.bot.db.execute("DELETE FROM voice_links WHERE user_id = ?", (member.id,))
        await self.bot.db.commit()
        await ctx.send(f"✅ Привязка для {member.mention} удалена.")

# ==================== ГОЛОСОВОЙ ТРЕКЕР ====================
class VoiceXPTracker:
    def __init__(self, bot: RoleBot):
        self.bot = bot
        self.active_users = {}

    def setup(self):
        @self.bot.listen("on_voice_state_update")
        async def handle_voice(member, before, after):
            if member.bot:
                return
            if before.channel is None and after.channel is not None:
                if after.self_mute or after.mute:
                    return
                self.active_users[member.id] = int(time.time())
            elif before.channel is not None and after.channel is None:
                if member.id in self.active_users:
                    duration = int(time.time()) - self.active_users.pop(member.id, time.time())
                    await self.award_voice_xp(member.id, duration)
            elif before.channel is not None and after.channel is not None:
                if after.self_mute or after.mute:
                    if member.id in self.active_users:
                        duration = int(time.time()) - self.active_users.pop(member.id, time.time())
                        await self.award_voice_xp(member.id, duration)
                else:
                    if member.id not in self.active_users:
                        self.active_users[member.id] = int(time.time())

    async def award_voice_xp(self, user_id: int, duration_seconds: int):
        minutes = duration_seconds // 60
        if minutes <= 0:
            return
        status = await self.bot.get_config("module_ranks_enabled")
        if status == "false":
            return
        xp_to_add = minutes * 5
        await self.bot.db.execute("INSERT INTO levels (user_id, xp, voice_xp) VALUES (?, 0, ?) ON CONFLICT(user_id) DO UPDATE SET voice_xp = voice_xp + excluded.voice_xp", (user_id, xp_to_add))
        clan_id = await self.bot.get_user_clan(user_id)
        if clan_id:
            await self.bot.add_clan_xp(clan_id, xp_to_add, user_id)
        await self.bot.db.commit()
        logger.info(f"Пользователю {user_id} начислено {xp_to_add} войс-опыта за {minutes} мин. в канале.")

# ==================== ОСНОВНОЙ КЛАСС БОТА ====================
class RoleBot(commands.Bot):
    def __init__(self):
        intents = disnake.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="i.", intents=intents)
        self.db: aiosqlite.Connection | None = None
        self.voice_times = {}
        self.remove_command('help')

    async def setup_db(self):
        await self.db.execute("CREATE TABLE IF NOT EXISTS links (user_id INTEGER, role_id INTEGER, PRIMARY KEY (user_id, role_id))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS gradients (role_id INTEGER PRIMARY KEY, colors TEXT, speed REAL DEFAULT 1.0, current_index INTEGER DEFAULT 0)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, embed_color TEXT DEFAULT '#7289da', status_text TEXT DEFAULT 'Участник сервера', banner_url TEXT DEFAULT '', messages_count INTEGER DEFAULT 0)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS message_logs (user_id INTEGER, timestamp INTEGER)")
        try:
            await self.db.execute("ALTER TABLE levels ADD COLUMN voice_xp INTEGER DEFAULT 0")
        except Exception:
            pass
        await self.db.execute("CREATE TABLE IF NOT EXISTS clans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, icon_url TEXT, banner_url TEXT, leader_id INTEGER NOT NULL, role_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, xp INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, created_at INTEGER NOT NULL)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS clan_members (clan_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp_contribution INTEGER DEFAULT 0, joined_at INTEGER NOT NULL, role TEXT CHECK(role IN ('leader', 'member')) DEFAULT 'member', PRIMARY KEY (clan_id, user_id))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS clan_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER NOT NULL, user_id INTEGER NOT NULL, status TEXT CHECK(status IN ('pending', 'accepted', 'declined')) DEFAULT 'pending', timestamp INTEGER NOT NULL, UNIQUE(clan_id, user_id))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS clan_bans (user_id INTEGER PRIMARY KEY)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS clan_coins (clan_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS clan_invites (id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER NOT NULL, user_id INTEGER NOT NULL, inviter_id INTEGER NOT NULL, status TEXT CHECK(status IN ('pending', 'accepted', 'declined')) DEFAULT 'pending', timestamp INTEGER NOT NULL)")
        await self.db.execute("CREATE TABLE IF NOT EXISTS marriages (id INTEGER PRIMARY KEY AUTOINCREMENT, user1_id INTEGER NOT NULL, user2_id INTEGER NOT NULL, since INTEGER NOT NULL, status TEXT CHECK(status IN ('active', 'divorced')) DEFAULT 'active', level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, love_status TEXT DEFAULT '', voice_channel_id INTEGER DEFAULT NULL, role_id INTEGER DEFAULT NULL, UNIQUE(user1_id, user2_id))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS marriage_achievements (marriage_id INTEGER NOT NULL, achievement TEXT NOT NULL, unlocked_at INTEGER NOT NULL, PRIMARY KEY (marriage_id, achievement))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS family (parent_id INTEGER NOT NULL, child_id INTEGER NOT NULL, since INTEGER NOT NULL, PRIMARY KEY (parent_id, child_id))")
        await self.db.execute("CREATE TABLE IF NOT EXISTS voice_links (user_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, can_manage INTEGER DEFAULT 0, PRIMARY KEY (user_id, channel_id))")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS command_permissions (
                command_name TEXT PRIMARY KEY,
                role_id INTEGER
            )
        """)
        try:
            await self.db.execute("ALTER TABLE marriages ADD COLUMN name TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            await self.db.execute("ALTER TABLE clans ADD COLUMN tags TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            await self.db.execute("ALTER TABLE clans ADD COLUMN auto_role INTEGER DEFAULT 1")
        except Exception:
            pass
        await self.db.commit()

    async def build_main_mod_embed(self) -> disnake.Embed:
        embed = disnake.Embed(title="Панель управления ботом", color=disnake.Color.red())
        roles_s = "активен" if await self.get_config("module_roles_enabled") != "false" else "не активен"
        prof_s = "активен" if await self.get_config("module_profiles_enabled") != "false" else "не активен"
        ranks_s = "активен" if await self.get_config("module_ranks_enabled") != "false" else "не активен"
        info_s = "активен" if await self.get_config("module_info_enabled") != "false" else "не активен"
        mod_s = "активен" if await self.get_config("module_mod_enabled") != "false" else "не активен"
        embed.description = (
            f"Кастомные роли\nУправление связями, просмотр всех связей...\nСтатус модуля: {roles_s}\n"
            "‿︵‿︵‿︵‿︵‿\n\n"
            f"Персонализация\nУправление командами...\nСтатус модуля: {prof_s}\n"
            "‿︵‿︵‿︵‿︵‿\n\n"
            f"Ранговая система\nУправление опытом...\nСтатус модуля: {ranks_s}\n"
            "‿︵‿︵‿︵‿︵‿\n\n"
            f"Информация\nУправление командами...\nСтатус модуля: {info_s}\n"
            "‿︵‿︵‿︵‿︵‿\n\n"
            f"Модерирование\nУправление командами...\nСтатус модуля: {mod_s}\n"
            "‿︵‿︵‿︵‿︵‿"
        )
        return embed

    async def render_paginated_embed(self, guild: disnake.Guild, rows: list, page: int) -> disnake.Embed:
        embed = disnake.Embed(title="СПИСОК всех связей.", color=disnake.Color.red())
        if not rows:
            embed.description = "Связи в базе данных отсутствуют."
            return embed
        items_per_page = 7
        current_slice = rows[page * items_per_page: (page + 1) * items_per_page]
        description = ""
        for idx, (u_id, r_id) in enumerate(current_slice):
            role = guild.get_role(r_id)
            r_text = role.mention if role else f"ID: {r_id}"
            description += f"#{idx+1}\nРоль: {r_text}\nВладелец: <@{u_id}>\n\n"
        embed.description = description
        rem = len(rows) - ((page + 1) * items_per_page)
        embed.set_footer(text=f"И еще {rem} связей" if rem > 0 else f"Страница {page+1} из {max(1, (len(rows)+6)//7)}")
        return embed

    async def get_config(self, key: str):
        async with self.db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_config(self, key: str, value: str):
        await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        await self.db.commit()

    async def get_linked_roles(self, user_id: int):
        async with self.db.execute("SELECT role_id FROM links WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
        return rows if rows else []

    async def get_command_permission(self, command_name: str):
        async with self.db.execute("SELECT role_id FROM command_permissions WHERE command_name = ?", (command_name,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_command_permission(self, command_name: str, role_id: int = None):
        if role_id is None:
            await self.db.execute("DELETE FROM command_permissions WHERE command_name = ?", (command_name,))
        else:
            await self.db.execute("INSERT OR REPLACE INTO command_permissions (command_name, role_id) VALUES (?, ?)", (command_name, role_id))
        await self.db.commit()

    async def create_clan(self, guild: disnake.Guild, name: str, description: str, leader_id: int, role_id: int, icon_url: str = "", banner_url: str = "", tags: str = "", auto_role: int = 1):
        if await self.is_banned_from_clans(leader_id):
            return None, "Вы забанены в клановой системе."
        async with self.db.execute("SELECT id FROM clans WHERE name = ?", (name,)) as cursor:
            if await cursor.fetchone():
                return None, "Клан с таким названием уже существует."
        async with self.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ? AND role = 'leader'", (leader_id,)) as cursor:
            if await cursor.fetchone():
                return None, "Вы уже являетесь лидером другого клана."
        async with self.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (leader_id,)) as cursor:
            if await cursor.fetchone():
                return None, "Вы уже состоите в клане."
        now = int(time.time())
        async with self.db.execute("INSERT INTO clans (name, description, leader_id, role_id, guild_id, icon_url, banner_url, created_at, tags, auto_role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, description, leader_id, role_id, guild.id, icon_url, banner_url, now, tags, auto_role)) as cursor:
            clan_id = cursor.lastrowid
        await self.db.execute("INSERT INTO clan_members (clan_id, user_id, role, joined_at) VALUES (?, ?, 'leader', ?)", (clan_id, leader_id, now))
        if auto_role:
            role = guild.get_role(role_id)
            if role:
                member = guild.get_member(leader_id)
                if member:
                    try:
                        await member.add_roles(role)
                    except disnake.Forbidden:
                        pass
        await self.db.commit()
        return clan_id, "Клан успешно создан!"

    async def get_clan(self, clan_id: int):
        async with self.db.execute("SELECT * FROM clans WHERE id = ?", (clan_id,)) as cursor:
            return await cursor.fetchone()

    async def get_clan_by_name(self, name: str):
        async with self.db.execute("SELECT * FROM clans WHERE name = ?", (name,)) as cursor:
            return await cursor.fetchone()

    async def get_clan_members_all(self, clan_id: int):
        async with self.db.execute("SELECT user_id, xp_contribution, role FROM clan_members WHERE clan_id = ? ORDER BY role DESC, xp_contribution DESC", (clan_id,)) as cursor:
            return await cursor.fetchall()

    async def get_clan_member_count(self, clan_id: int):
        async with self.db.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (clan_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def add_clan_member(self, clan_id: int, user_id: int, xp_contribution: int = 0):
        now = int(time.time())
        await self.db.execute("INSERT INTO clan_members (clan_id, user_id, xp_contribution, joined_at, role) VALUES (?, ?, ?, ?, 'member')", (clan_id, user_id, xp_contribution, now))

    async def remove_clan_member(self, clan_id: int, user_id: int):
        await self.db.execute("DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?", (clan_id, user_id))
        await self.db.commit()

    async def add_clan_xp(self, clan_id: int, xp: int, user_id: int = None):
        await self.db.execute("UPDATE clans SET xp = xp + ? WHERE id = ?", (xp, clan_id))
        if user_id:
            await self.db.execute("UPDATE clan_members SET xp_contribution = xp_contribution + ? WHERE clan_id = ? AND user_id = ?", (xp, clan_id, user_id))
        clan = await self.get_clan(clan_id)
        if clan:
            current_xp = clan[8]
            old_xp = current_xp - xp
            old_level = await self.calculate_level_from_xp(old_xp)
            new_level = await self.calculate_level_from_xp(current_xp)
            if new_level > old_level:
                coins_to_add = sum(range(old_level + 1, new_level + 1))
                await self.db.execute("INSERT INTO clan_coins (clan_id, coins) VALUES (?, ?) ON CONFLICT(clan_id) DO UPDATE SET coins = coins + ?", (clan_id, coins_to_add, coins_to_add))
        await self.db.commit()

    async def get_user_clan(self, user_id: int):
        async with self.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def get_clan_leader(self, clan_id: int):
        async with self.db.execute("SELECT user_id FROM clan_members WHERE clan_id = ? AND role = 'leader'", (clan_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def get_clan_requests_count(self, clan_id: int):
        async with self.db.execute("SELECT COUNT(*) FROM clan_requests WHERE clan_id = ? AND status = 'pending'", (clan_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def create_clan_request(self, clan_id: int, user_id: int):
        if await self.get_user_clan(user_id):
            return False, "Вы уже состоите в клане."
        await self.db.execute("DELETE FROM clan_requests WHERE clan_id = ? AND user_id = ?", (clan_id, user_id))
        now = int(time.time())
        await self.db.execute("INSERT INTO clan_requests (clan_id, user_id, status, timestamp) VALUES (?, ?, 'pending', ?)", (clan_id, user_id, now))
        await self.db.commit()
        return True, "Заявка отправлена."

    async def accept_clan_request(self, request_id: int, guild: disnake.Guild):
        async with self.db.execute("SELECT clan_id, user_id FROM clan_requests WHERE id = ? AND status = 'pending'", (request_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Заявка не найдена или уже обработана."
            clan_id, user_id = row
        members = await self.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return False, "Клан достиг лимита участников (5/5)."
        await self.add_clan_member(clan_id, user_id)
        await self.db.execute("UPDATE clan_requests SET status = 'accepted' WHERE id = ?", (request_id,))
        await self.db.commit()
        clan = await self.get_clan(clan_id)
        if clan and clan[12]:
            role = guild.get_role(clan[6])
            if role:
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.add_roles(role)
                    except disnake.Forbidden:
                        pass
        return True, "Заявка принята."

    async def decline_clan_request(self, request_id: int):
        async with self.db.execute("SELECT id FROM clan_requests WHERE id = ? AND status = 'pending'", (request_id,)) as cursor:
            if not await cursor.fetchone():
                return False, "Заявка не найдена или уже обработана."
        await self.db.execute("UPDATE clan_requests SET status = 'declined' WHERE id = ?", (request_id,))
        await self.db.commit()
        return True, "Заявка отклонена."

    async def get_all_clans(self, guild_id: int, limit: int = 10, offset: int = 0):
        async with self.db.execute("SELECT id, name, icon_url, leader_id, xp, wins, tags FROM clans WHERE guild_id = ? ORDER BY xp DESC LIMIT ? OFFSET ?", (guild_id, limit, offset)) as cursor:
            return await cursor.fetchall()

    async def count_clans(self, guild_id: int):
        async with self.db.execute("SELECT COUNT(*) FROM clans WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_clan(self, clan_id: int, name: str = None, description: str = None, icon_url: str = None, banner_url: str = None, role_id: int = None, tags: str = None, auto_role: int = None):
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if icon_url is not None:
            updates.append("icon_url = ?")
            params.append(icon_url)
        if banner_url is not None:
            updates.append("banner_url = ?")
            params.append(banner_url)
        if role_id is not None:
            updates.append("role_id = ?")
            params.append(role_id)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        if auto_role is not None:
            updates.append("auto_role = ?")
            params.append(auto_role)
        if not updates:
            return False, "Нет изменений"
        params.append(clan_id)
        await self.db.execute(f"UPDATE clans SET {', '.join(updates)} WHERE id = ?", params)
        await self.db.commit()
        return True, "Клан обновлен"

    async def delete_clan(self, clan_id: int):
        await self.db.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
        await self.db.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
        await self.db.execute("DELETE FROM clan_requests WHERE clan_id = ?", (clan_id,))
        await self.db.commit()
        return True, "Клан удален"

    async def kick_from_clan(self, clan_id: int, user_id: int):
        leader = await self.get_clan_leader(clan_id)
        if leader == user_id:
            return False, "Нельзя кикнуть лидера клана"
        await self.db.execute("DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?", (clan_id, user_id))
        await self.db.commit()
        return True, "Участник исключен из клана"

    async def get_clan_coins(self, clan_id: int):
        async with self.db.execute("SELECT coins FROM clan_coins WHERE clan_id = ?", (clan_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def calculate_level_from_xp(self, xp: int) -> int:
        level = 1
        needed = 100
        while xp >= needed:
            xp -= needed
            level += 1
            needed += 100
        return level

    async def is_banned_from_clans(self, user_id: int):
        async with self.db.execute("SELECT user_id FROM clan_bans WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def ban_from_clans(self, user_id: int):
        await self.db.execute("INSERT OR IGNORE INTO clan_bans (user_id) VALUES (?)", (user_id,))
        await self.db.commit()

    async def unban_from_clans(self, user_id: int):
        await self.db.execute("DELETE FROM clan_bans WHERE user_id = ?", (user_id,))
        await self.db.commit()

    async def get_banned_users(self):
        async with self.db.execute("SELECT user_id FROM clan_bans") as cursor:
            return await cursor.fetchall()

    async def create_clan_invite(self, clan_id: int, user_id: int, inviter_id: int):
        if await self.get_user_clan(user_id):
            return False, "Пользователь уже состоит в клане."
        async with self.db.execute("SELECT id FROM clan_invites WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, user_id)) as cursor:
            if await cursor.fetchone():
                return False, "Приглашение уже отправлено этому пользователю."
        now = int(time.time())
        await self.db.execute("INSERT INTO clan_invites (clan_id, user_id, inviter_id, status, timestamp) VALUES (?, ?, ?, 'pending', ?)", (clan_id, user_id, inviter_id, now))
        await self.db.commit()
        return True, "Приглашение отправлено."

    async def get_user_invites(self, user_id: int):
        async with self.db.execute("SELECT id, clan_id, status, inviter_id, timestamp FROM clan_invites WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)) as cursor:
            return await cursor.fetchall()

    async def accept_clan_invite(self, invite_id: int, guild: disnake.Guild):
        async with self.db.execute("SELECT clan_id, user_id FROM clan_invites WHERE id = ? AND status = 'pending'", (invite_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Приглашение не найдено или уже обработано."
            clan_id, user_id = row
        members = await self.get_clan_members_all(clan_id)
        if len(members) >= 5:
            return False, "Клан достиг лимита участников (5/5)."
        await self.add_clan_member(clan_id, user_id)
        await self.db.execute("UPDATE clan_invites SET status = 'accepted' WHERE id = ?", (invite_id,))
        await self.db.commit()
        clan = await self.get_clan(clan_id)
        if clan and clan[12]:
            role = guild.get_role(clan[6])
            if role:
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.add_roles(role)
                    except disnake.Forbidden:
                        pass
        return True, "Вы вступили в клан!"

    async def accept_clan_invite_by_clan(self, clan_id: int, user_id: int, guild: disnake.Guild):
        async with self.db.execute("SELECT id FROM clan_invites WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Приглашение не найдено или уже обработано."
        return await self.accept_clan_invite(row[0], guild)

    async def decline_clan_invite(self, invite_id: int):
        async with self.db.execute("SELECT id FROM clan_invites WHERE id = ? AND status = 'pending'", (invite_id,)) as cursor:
            if not await cursor.fetchone():
                return False, "Приглашение не найдено или уже обработано."
        await self.db.execute("UPDATE clan_invites SET status = 'declined' WHERE id = ?", (invite_id,))
        await self.db.commit()
        return True, "Приглашение отклонено."

    async def decline_clan_invite_by_clan(self, clan_id: int, user_id: int):
        async with self.db.execute("SELECT id FROM clan_invites WHERE clan_id = ? AND user_id = ? AND status = 'pending'", (clan_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
        return await self.decline_clan_invite(row[0])

    async def setup_hook(self):
        logger.info("=== setup_hook начат ===")
        self.db = await aiosqlite.connect(DATABASE_NAME)
        await self.setup_db()
        logger.info("База данных готова")
        self.add_cog(HubCog(self))
        self.add_cog(ClanCog(self))
        self.add_cog(EntertainmentCog(self))
        self.voice_tracker = VoiceXPTracker(self)
        self.voice_tracker.setup()
        logger.info("=== setup_hook завершён ===")

    async def on_ready(self):
        if self.db is None:
            logger.info("=== Резервная инициализация в on_ready ===")
            self.db = await aiosqlite.connect(DATABASE_NAME)
            await self.setup_db()
            self.add_cog(HubCog(self))
            self.add_cog(ClanCog(self))
            self.add_cog(EntertainmentCog(self))
            self.voice_tracker = VoiceXPTracker(self)
            self.voice_tracker.setup()
            logger.info("Резервная инициализация завершена")
        logger.info(f"Бот авторизован как {self.user.name}")
        if not self.garland_loop.is_running():
            self.garland_loop.start()

    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return
        logger.info(f"Получено сообщение: {message.content}")
        if self.db is None:
            logger.warning("База данных не инициализирована, пропускаем обработку")
            return
        ct = int(time.time())
        await self.db.execute("INSERT INTO message_logs (user_id, timestamp) VALUES (?, ?)", (message.author.id, ct))
        if await self.get_config("module_ranks_enabled") != "false":
            await self.db.execute("INSERT INTO levels (user_id, xp, voice_xp) VALUES (?, 15, 0) ON CONFLICT(user_id) DO UPDATE SET xp = xp + 15", (message.author.id,))
            clan_id = await self.get_user_clan(message.author.id)
            if clan_id:
                await self.add_clan_xp(clan_id, 15, message.author.id)
        await self.db.execute("INSERT INTO profiles (user_id, embed_color, status_text, banner_url, messages_count) VALUES (?, '#7289da', 'Участник сервера', '', 1) ON CONFLICT(user_id) DO UPDATE SET messages_count = messages_count + 1", (message.author.id,))
        await self.db.commit()
        await self.process_commands(message)

    async def on_voice_state_update(self, member: disnake.Member, before: disnake.VoiceState, after: disnake.VoiceState):
        if member.bot:
            return
        if before.channel is None and after.channel is not None:
            self.voice_times[member.id] = time.time()
        elif before.channel is not None and after.channel is None:
            join_time = self.voice_times.pop(member.id, None)
            if join_time and await self.get_config("module_ranks_enabled") != "false":
                minutes_spent = int((time.time() - join_time) // 60)
                if minutes_spent > 0:
                    voice_xp_to_add = minutes_spent * 20
                    await self.db.execute("INSERT INTO levels (user_id, xp, voice_xp) VALUES (?, 0, ?) ON CONFLICT(user_id) DO UPDATE SET voice_xp = voice_xp + excluded.voice_xp", (member.id, voice_xp_to_add))
                    clan_id = await self.get_user_clan(member.id)
                    if clan_id:
                        await self.add_clan_xp(clan_id, voice_xp_to_add, member.id)
                    await self.db.commit()

    @tasks.loop(seconds=5)
    async def garland_loop(self):
        if self.db is None:
            return
        async with self.db.execute("SELECT role_id, colors, current_index FROM gradients") as cursor:
            rows = await cursor.fetchall()
        for role_id, colors_json, current_index in rows:
            role = self.get_role(role_id)
            if not role:
                continue
            colors = json.loads(colors_json)
            if not colors:
                continue
            try:
                new_index = (current_index + 1) % len(colors)
                await role.edit(color=disnake.Color(colors[new_index]))
                await self.db.execute("UPDATE gradients SET current_index = ? WHERE role_id = ?", (new_index, role_id))
                await self.db.commit()
                await asyncio.sleep(0.5)
            except Exception:
                continue

    async def set_role_gradient(self, role: disnake.Role, color1: int, color2: int):
        payload = {"colors": {"primary_color": color1, "secondary_color": color2}}
        await self.http.request(disnake.http.Route("PATCH", "/guilds/{guild_id}/roles/{role_id}", guild_id=role.guild.id, role_id=role.id), json=payload)

# ---------- ЗАПУСК ----------
async def main():
    bot = RoleBot()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())