"""
yeni_sistemler.py — Zerith Security
Düzeltme: db_connect ve yardımcı fonksiyonlar artık setup_new_systems üzerinden enjekte ediliyor.
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import re
import json
import urllib.request
import urllib.parse
from datetime import timedelta, datetime, timezone
from collections import defaultdict
import io

# Bu değişkenler setup_new_systems() tarafından doldurulur
bot = None
db_connect = None
get_settings = None
log_send = None
warn_add = None


# ============================================================
#  1. TİCKET SİSTEMİ
# ============================================================

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎫 Destek Talebi Aç",
        style=discord.ButtonStyle.primary,
        custom_id="zerith_ticket_open_v2"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        settings = get_settings(interaction.guild.id)
        cat_id = settings.get("ticket_category_id")
        if not cat_id:
            return await interaction.followup.send(
                "❌ Ticket kategorisi ayarlanmamış. Admin `/setup ticket` kullanmalı.", ephemeral=True
            )

        category = interaction.guild.get_channel(int(cat_id))
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.followup.send("❌ Ticket kategorisi bulunamadı.", ephemeral=True)

        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            (str(interaction.guild.id), str(interaction.user.id))
        )
        existing = c.fetchone()
        conn.close()

        if existing:
            ch = interaction.guild.get_channel(int(existing["channel_id"]))
            if ch:
                return await interaction.followup.send(
                    f"❌ Zaten açık bir ticket'ın var: {ch.mention}", ephemeral=True
                )
            conn = db_connect()
            c = conn.cursor()
            c.execute(
                "UPDATE tickets SET status='closed' WHERE guild_id=? AND user_id=? AND status='open'",
                (str(interaction.guild.id), str(interaction.user.id))
            )
            conn.commit()
            conn.close()

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, read_message_history=True
            ),
        }
        mod_role_id = settings.get("mod_role_id")
        if mod_role_id:
            mod_role = interaction.guild.get_role(int(mod_role_id))
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        safe_name = re.sub(r'[^a-z0-9-]', '', interaction.user.name.lower())[:20] or "kullanici"
        channel_name = f"ticket-{safe_name}"

        try:
            ticket_ch = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket sahibi: {interaction.user.id}",
                reason="Zerith Ticket Sistemi"
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ Kanal oluşturma iznim yok.", ephemeral=True
            )
        except Exception as e:
            return await interaction.followup.send(f"❌ Kanal oluşturulamadı: {e}", ephemeral=True)

        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, created_at) VALUES (?,?,?,?)",
            (str(interaction.guild.id), str(ticket_ch.id), str(interaction.user.id), time.time())
        )
        tid = c.lastrowid
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title=f"🎫 Ticket #{tid}",
            description=(
                f"Merhaba {interaction.user.mention}! 👋\n\n"
                f"Sorununu veya isteğini detaylıca açıkla.\n"
                f"Ekibimiz en kısa sürede yardımcı olacak.\n\n"
                f"📎 Ekran görüntüsü ekleyebilirsin.\n"
                f"🔒 Ticket'ı kapatmak için aşağıdaki butonu kullan."
            ),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Kullanıcı", value=f"{interaction.user.mention} ({interaction.user.id})")
        embed.add_field(name="📅 Açılış", value=f"<t:{int(time.time())}:F>")
        embed.set_footer(text=f"Zerith Security | Ticket #{tid}")

        await ticket_ch.send(
            content=f"{interaction.user.mention}",
            embed=embed,
            view=TicketControlView()
        )
        await interaction.followup.send(f"✅ Ticket'ın açıldı: {ticket_ch.mention}", ephemeral=True)

        log_embed = discord.Embed(title="🎫 Ticket Açıldı", color=discord.Color.green())
        log_embed.add_field(name="Kullanıcı", value=f"{interaction.user} ({interaction.user.id})")
        log_embed.add_field(name="Kanal", value=ticket_ch.mention)
        log_embed.add_field(name="ID", value=f"#{tid}")
        log_embed.timestamp = discord.utils.utcnow()
        await log_send(interaction.guild, log_embed)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Kapat", style=discord.ButtonStyle.danger, custom_id="zerith_ticket_close_v2")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = get_settings(interaction.guild.id)
        mod_role_id = settings.get("mod_role_id")
        is_mod = interaction.user.guild_permissions.manage_channels
        if mod_role_id:
            mod_role = interaction.guild.get_role(int(mod_role_id))
            if mod_role and mod_role in interaction.user.roles:
                is_mod = True

        owner_id = None
        if interaction.channel.topic:
            m = re.search(r'Ticket sahibi: (\d+)', interaction.channel.topic)
            if m:
                owner_id = int(m.group(1))

        if not is_mod and (owner_id is None or interaction.user.id != owner_id):
            return await interaction.response.send_message(
                "❌ Sadece ticket sahibi veya yetkililer kapatabilir.", ephemeral=True
            )

        await interaction.response.defer()

        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "UPDATE tickets SET status='closed' WHERE channel_id=? AND guild_id=?",
            (str(interaction.channel.id), str(interaction.guild.id))
        )
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🔒 Ticket Kapatıldı",
            description=f"{interaction.user.mention} tarafından kapatıldı.\nKanal **5 saniye** içinde silinecek.",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed)

        log_embed = discord.Embed(title="🔒 Ticket Kapatıldı", color=discord.Color.red())
        log_embed.add_field(name="Kapatan", value=f"{interaction.user} ({interaction.user.id})")
        log_embed.add_field(name="Kanal", value=interaction.channel.name)
        log_embed.timestamp = discord.utils.utcnow()
        await log_send(interaction.guild, log_embed)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket kapatıldı — {interaction.user}")
        except Exception:
            pass

    @discord.ui.button(label="📋 Transkript", style=discord.ButtonStyle.secondary, custom_id="zerith_ticket_transcript_v2")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        messages = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                ts = msg.created_at.strftime("%d/%m/%Y %H:%M")
                messages.append(f"[{ts}] {msg.author.display_name}: {msg.content}")

        if not messages:
            return await interaction.followup.send("❌ Transkript için mesaj yok.", ephemeral=True)

        content = "\n".join(messages)
        filename = f"transkript-{interaction.channel.name}-{int(time.time())}.txt"
        file = discord.File(fp=io.BytesIO(content.encode('utf-8')), filename=filename)
        await interaction.followup.send("📋 Transkript hazırlandı:", file=file, ephemeral=True)

        settings = get_settings(interaction.guild.id)
        log_id = settings.get("ticket_log_channel_id") or settings.get("log_channel_id")
        if log_id:
            log_ch = interaction.guild.get_channel(int(log_id))
            if log_ch:
                file2 = discord.File(fp=io.BytesIO(content.encode('utf-8')), filename=filename)
                log_embed = discord.Embed(title="📋 Ticket Transkripti", color=discord.Color.blue())
                log_embed.add_field(name="İsteyen", value=interaction.user.mention)
                log_embed.add_field(name="Kanal", value=interaction.channel.name)
                await log_ch.send(embed=log_embed, file=file2)


# ============================================================
#  2. ROL SİSTEMİ
# ============================================================

ROL_PANEL_DATA: dict = {}


class RolSecimView(discord.ui.View):
    def __init__(self, roller: list):
        super().__init__(timeout=None)
        for label, emoji, role_id in roller[:20]:
            self.add_item(RolButon(label=label, emoji=emoji, role_id=role_id))


class RolButon(discord.ui.Button):
    def __init__(self, label: str, emoji: str, role_id: int):
        super().__init__(
            label=label,
            emoji=emoji or None,
            style=discord.ButtonStyle.secondary,
            custom_id=f"zerith_rol_{role_id}"
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ Rol bulunamadı.", ephemeral=True)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Rol paneli")
            await interaction.response.send_message(f"✅ **{role.name}** rolü kaldırıldı.", ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason="Rol paneli")
            await interaction.response.send_message(f"✅ **{role.name}** rolü verildi.", ephemeral=True)


# ============================================================
#  3. ETKİNLİK SİSTEMİ
# ============================================================

def event_db_init():
    conn = db_connect()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT, channel_id TEXT, message_id TEXT,
        title TEXT, description TEXT,
        location TEXT DEFAULT 'Discord',
        starts_at REAL, ends_at REAL,
        host_id TEXT,
        max_participants INTEGER DEFAULT 0,
        participants TEXT DEFAULT '[]',
        status TEXT DEFAULT 'active'
    )""")
    conn.commit()
    conn.close()


class EtkinlikKatilView(discord.ui.View):
    def __init__(self, event_id: int):
        super().__init__(timeout=None)
        self.event_id = event_id

    @discord.ui.button(label="✅ Katıl", style=discord.ButtonStyle.success, custom_id="zerith_event_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE id=? AND guild_id=?", (self.event_id, str(interaction.guild.id)))
        row = c.fetchone()
        if not row:
            conn.close()
            return await interaction.response.send_message("❌ Etkinlik bulunamadı.", ephemeral=True)
        participants = json.loads(row["participants"])
        uid = str(interaction.user.id)
        max_p = row["max_participants"]
        if uid in participants:
            conn.close()
            return await interaction.response.send_message("❌ Zaten katıldın.", ephemeral=True)
        if max_p > 0 and len(participants) >= max_p:
            conn.close()
            return await interaction.response.send_message("❌ Etkinlik dolu!", ephemeral=True)
        participants.append(uid)
        c.execute("UPDATE events SET participants=? WHERE id=?", (json.dumps(participants), self.event_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ **{row['title']}** etkinliğine katıldın!", ephemeral=True)
        await _update_event_message(interaction.guild, row, participants)

    @discord.ui.button(label="❌ Ayrıl", style=discord.ButtonStyle.danger, custom_id="zerith_event_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE id=? AND guild_id=?", (self.event_id, str(interaction.guild.id)))
        row = c.fetchone()
        if not row:
            conn.close()
            return await interaction.response.send_message("❌ Etkinlik bulunamadı.", ephemeral=True)
        participants = json.loads(row["participants"])
        uid = str(interaction.user.id)
        if uid not in participants:
            conn.close()
            return await interaction.response.send_message("❌ Etkinliğe katılmamışsın.", ephemeral=True)
        participants.remove(uid)
        c.execute("UPDATE events SET participants=? WHERE id=?", (json.dumps(participants), self.event_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message("✅ Etkinlikten ayrıldın.", ephemeral=True)
        await _update_event_message(interaction.guild, row, participants)


async def _update_event_message(guild, row, participants):
    try:
        ch = guild.get_channel(int(row["channel_id"]))
        if not ch:
            return
        msg = await ch.fetch_message(int(row["message_id"]))
        embed = _build_event_embed(row, participants)
        await msg.edit(embed=embed)
    except Exception:
        pass


def _build_event_embed(row, participants=None):
    if participants is None:
        participants = json.loads(row["participants"])
    max_p = row["max_participants"]
    embed = discord.Embed(title=f"🎉 {row['title']}", description=row["description"], color=discord.Color.blue())
    embed.add_field(name="📍 Konum", value=row["location"] or "Discord", inline=True)
    embed.add_field(name="🕐 Başlangıç", value=f"<t:{int(row['starts_at'])}:F>", inline=True)
    embed.add_field(name="🕐 Bitiş", value=f"<t:{int(row['ends_at'])}:F>" if row["ends_at"] else "Belirtilmedi", inline=True)
    katilimci_str = f"{len(participants)}" + (f"/{max_p}" if max_p > 0 else "")
    embed.add_field(name="👥 Katılımcı", value=katilimci_str, inline=True)
    if participants:
        preview = ", ".join(f"<@{uid}>" for uid in participants[:5])
        if len(participants) > 5:
            preview += f" +{len(participants)-5} kişi"
        embed.add_field(name="✅ Katılanlar", value=preview, inline=False)
    embed.set_footer(text=f"Etkinlik ID: {row['id']} • Zerith Security")
    return embed


# ============================================================
#  4. GELİŞMİŞ ANTİ-RAID SİSTEMİ
# ============================================================

RAID_JOIN_LOG: dict = defaultdict(list)
RECENT_MESSAGES: dict = defaultdict(lambda: defaultdict(list))
RAID_CONFIG = {
    "join_threshold": 8,
    "join_window": 10,
    "new_account_days": 7,
    "mass_mention_threshold": 5,
    "duplicate_msg_threshold": 4,
    "auto_lockdown": True,
}


async def antiraid_on_member_join(member: discord.Member):
    gid = str(member.guild.id)
    now = time.time()
    RAID_JOIN_LOG[gid].append(now)
    RAID_JOIN_LOG[gid] = [t for t in RAID_JOIN_LOG[gid] if now - t <= RAID_CONFIG["join_window"]]

    account_age_days = (datetime.now(timezone.utc) - member.created_at).days
    if len(RAID_JOIN_LOG[gid]) >= RAID_CONFIG["join_threshold"]:
        await _trigger_raid_alert(member.guild, len(RAID_JOIN_LOG[gid]), "Toplu Katılım")

    if account_age_days < RAID_CONFIG["new_account_days"]:
        log_embed = discord.Embed(title="⚠️ Şüpheli Yeni Üye", color=discord.Color.orange())
        log_embed.add_field(name="Kullanıcı", value=f"{member} ({member.id})")
        log_embed.add_field(name="Hesap Yaşı", value=f"{account_age_days} gün")
        log_embed.add_field(name="Oluşturulma", value=member.created_at.strftime("%d/%m/%Y"))
        log_embed.set_thumbnail(url=member.display_avatar.url)
        log_embed.timestamp = discord.utils.utcnow()
        await log_send(member.guild, log_embed)


async def antiraid_on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    gid = str(message.guild.id)
    uid = str(message.author.id)
    now = time.time()

    mention_count = len(message.mentions) + len(message.role_mentions)
    if mention_count >= RAID_CONFIG["mass_mention_threshold"]:
        await message.delete()
        try:
            await message.author.timeout(timedelta(minutes=30), reason="Mass mention spam")
        except Exception:
            pass
        warn_add(message.author.id, message.guild.id, 0, f"Otomatik: Mass mention ({mention_count})")
        embed = discord.Embed(title="🚨 Mass Mention Engellendi", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
        embed.add_field(name="Mention Sayısı", value=str(mention_count))
        embed.add_field(name="Kanal", value=message.channel.mention)
        embed.timestamp = discord.utils.utcnow()
        await log_send(message.guild, embed)
        await message.channel.send(
            f"🚨 {message.author.mention} mass mention yaptığı için 30 dakika susturuldu!", delete_after=8
        )
        return

    content = message.content.lower().strip()
    if content:
        msgs = RECENT_MESSAGES[gid][uid]
        msgs.append((now, content))
        RECENT_MESSAGES[gid][uid] = [(t, c) for t, c in msgs if now - t <= 10]
        recent_contents = [c for _, c in RECENT_MESSAGES[gid][uid]]
        if recent_contents.count(content) >= RAID_CONFIG["duplicate_msg_threshold"]:
            await message.channel.purge(
                limit=20,
                check=lambda m: m.author == message.author and m.content.lower().strip() == content
            )
            try:
                await message.author.timeout(timedelta(minutes=10), reason="Mesaj spam")
            except Exception:
                pass
            RECENT_MESSAGES[gid][uid] = []
            embed = discord.Embed(title="🚨 Mesaj Spam Engellendi", color=discord.Color.red())
            embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
            embed.add_field(name="Kanal", value=message.channel.mention)
            embed.timestamp = discord.utils.utcnow()
            await log_send(message.guild, embed)


async def _trigger_raid_alert(guild: discord.Guild, join_count: int, raid_type: str):
    embed = discord.Embed(
        title="🚨 RAİD TESPİT EDİLDİ",
        description=f"**{join_count}** kişi {RAID_CONFIG['join_window']} saniyede katıldı!",
        color=discord.Color.red()
    )
    embed.add_field(name="Tür", value=raid_type)
    embed.add_field(name="Sunucu", value=guild.name)
    embed.timestamp = discord.utils.utcnow()
    await log_send(guild, embed)
    if RAID_CONFIG["auto_lockdown"]:
        try:
            await guild.edit(verification_level=discord.VerificationLevel.high, reason="Anti-Raid: Otomatik")
            embed2 = discord.Embed(
                title="🔒 Otomatik Raid Kilidi",
                description="Raid tespit edildi! Doğrulama seviyesi **YÜKSEK** yapıldı.\n`/antiraid unlock` ile geri al.",
                color=discord.Color.dark_red()
            )
            await log_send(guild, embed2)
        except Exception:
            pass
    RAID_JOIN_LOG[str(guild.id)] = []


# ============================================================
#  5. FORM / BAŞVURU SİSTEMİ
# ============================================================

def form_db_init():
    conn = db_connect()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS forms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT, title TEXT, description TEXT,
        questions TEXT DEFAULT '[]',
        log_channel_id TEXT, role_on_accept_id TEXT,
        active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS form_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id INTEGER, guild_id TEXT, user_id TEXT,
        answers TEXT DEFAULT '{}',
        status TEXT DEFAULT 'pending',
        submitted_at REAL, reviewed_by TEXT
    )""")
    conn.commit()
    conn.close()


class BasvuruModal(discord.ui.Modal):
    def __init__(self, form_id: int, title: str, questions: list):
        super().__init__(title=title[:45])
        self.form_id = form_id
        self.questions = questions
        for i, soru in enumerate(questions[:5]):
            self.add_item(discord.ui.TextInput(
                label=soru[:45],
                placeholder="Cevabını buraya yaz...",
                style=discord.TextStyle.paragraph if i >= 2 else discord.TextStyle.short,
                required=True, max_length=500, custom_id=f"soru_{i}"
            ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        answers = {}
        for item in self.children:
            idx = int(item.custom_id.split("_")[1])
            if idx < len(self.questions):
                answers[self.questions[idx]] = item.value

        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "SELECT id, status FROM form_responses WHERE form_id=? AND user_id=? AND guild_id=?",
            (self.form_id, str(interaction.user.id), str(interaction.guild.id))
        )
        existing = c.fetchone()
        if existing:
            conn.close()
            status_tr = {"pending": "beklemede", "accepted": "kabul edildi", "rejected": "reddedildi"}.get(existing["status"], existing["status"])
            return await interaction.followup.send(f"❌ Bu forma zaten başvurdun! Durumun: **{status_tr}**", ephemeral=True)

        c.execute(
            "INSERT INTO form_responses (form_id, guild_id, user_id, answers, submitted_at) VALUES (?,?,?,?,?)",
            (self.form_id, str(interaction.guild.id), str(interaction.user.id),
             json.dumps(answers, ensure_ascii=False), time.time())
        )
        resp_id = c.lastrowid
        c.execute("SELECT * FROM forms WHERE id=?", (self.form_id,))
        form = c.fetchone()
        conn.commit()
        conn.close()

        await interaction.followup.send(
            f"✅ **{form['title']}** başvurun alındı! (ID: #{resp_id})\nYetkililer inceleyecek.", ephemeral=True
        )

        if form["log_channel_id"]:
            log_ch = interaction.guild.get_channel(int(form["log_channel_id"]))
            if log_ch:
                embed = discord.Embed(title=f"📝 Yeni Başvuru — {form['title']}", color=discord.Color.blue())
                embed.set_author(name=f"{interaction.user.display_name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
                embed.add_field(name="Başvuran", value=interaction.user.mention, inline=True)
                embed.add_field(name="ID", value=f"#{resp_id}", inline=True)
                for soru, cevap in answers.items():
                    embed.add_field(name=soru[:256], value=cevap[:1024], inline=False)
                embed.timestamp = discord.utils.utcnow()
                await log_ch.send(embed=embed, view=BasvuruOnayView(resp_id=resp_id, form_id=self.form_id))


class BasvuruOnayView(discord.ui.View):
    def __init__(self, resp_id: int, form_id: int):
        super().__init__(timeout=None)
        self.resp_id = resp_id
        self.form_id = form_id

    @discord.ui.button(label="✅ Kabul Et", style=discord.ButtonStyle.success, custom_id="zerith_form_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Yetkin yok.", ephemeral=True)
        conn = db_connect()
        c = conn.cursor()
        c.execute("UPDATE form_responses SET status='accepted', reviewed_by=? WHERE id=?",
                  (str(interaction.user.id), self.resp_id))
        c.execute("SELECT user_id FROM form_responses WHERE id=?", (self.resp_id,))
        resp = c.fetchone()
        c.execute("SELECT role_on_accept_id, title FROM forms WHERE id=?", (self.form_id,))
        form = c.fetchone()
        conn.commit()
        conn.close()

        if resp and form and form["role_on_accept_id"]:
            member = interaction.guild.get_member(int(resp["user_id"]))
            if member:
                role = interaction.guild.get_role(int(form["role_on_accept_id"]))
                if role:
                    try:
                        await member.add_roles(role, reason=f"Başvuru kabul — {form['title']}")
                    except Exception:
                        pass
        if resp:
            member = interaction.guild.get_member(int(resp["user_id"]))
            if member:
                try:
                    await member.send(f"✅ **{interaction.guild.name}** sunucusundaki başvurun **kabul edildi**! 🎉")
                except Exception:
                    pass

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.green()
        embed.set_footer(text=f"✅ {interaction.user.display_name} tarafından kabul edildi")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ Başvuru kabul edildi.", ephemeral=True)

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.danger, custom_id="zerith_form_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Yetkin yok.", ephemeral=True)
        conn = db_connect()
        c = conn.cursor()
        c.execute("UPDATE form_responses SET status='rejected', reviewed_by=? WHERE id=?",
                  (str(interaction.user.id), self.resp_id))
        c.execute("SELECT user_id FROM form_responses WHERE id=?", (self.resp_id,))
        resp = c.fetchone()
        conn.commit()
        conn.close()

        if resp:
            member = interaction.guild.get_member(int(resp["user_id"]))
            if member:
                try:
                    await member.send(f"❌ **{interaction.guild.name}** sunucusundaki başvurun maalesef **reddedildi**.")
                except Exception:
                    pass

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.red()
        embed.set_footer(text=f"❌ {interaction.user.display_name} tarafından reddedildi")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("✅ Başvuru reddedildi.", ephemeral=True)


class BasvuruAcView(discord.ui.View):
    def __init__(self, form_id: int, sorular: list, form_title: str):
        super().__init__(timeout=None)
        self.form_id = form_id

    @discord.ui.button(label="📝 Başvur", style=discord.ButtonStyle.primary, custom_id="zerith_form_apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM forms WHERE id=? AND active=1", (self.form_id,))
        form = c.fetchone()
        conn.close()
        if not form:
            return await interaction.response.send_message("❌ Form artık aktif değil.", ephemeral=True)
        sorular = json.loads(form["questions"])
        modal = BasvuruModal(form_id=self.form_id, title=form["title"], questions=sorular)
        await interaction.response.send_modal(modal)


# ============================================================
#  6. ÇEVİRİ SİSTEMİ
# ============================================================

DILLER = {
    "tr": "Türkçe", "en": "İngilizce", "de": "Almanca",
    "fr": "Fransızca", "es": "İspanyolca", "it": "İtalyanca",
    "ru": "Rusça", "ja": "Japonca", "ko": "Korece",
    "zh": "Çince", "ar": "Arapça", "pt": "Portekizce",
    "nl": "Hollandaca", "pl": "Polonyaca", "sv": "İsveççe",
}


async def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    if len(text) > 500:
        text = text[:500]
    lang_pair = f"{source_lang}|{target_lang}"
    url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair={lang_pair}"
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            with urllib.request.urlopen(url, timeout=10) as resp:
                return json.loads(resp.read().decode())
        data = await loop.run_in_executor(None, _fetch)
        if data.get("responseStatus") == 200:
            return data["responseData"]["translatedText"]
        return None
    except Exception as e:
        print(f"CEVIRI HATASI: {e}")
        return None


# ============================================================
#  KOMUTLARI KAYDET — bot hazır olduktan sonra çağrılır
# ============================================================

def _register_commands(b: commands.Bot):

    # ── Ticket panel ──
    @b.command(name="ticket_panel_v2")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_new(ctx):
        embed = discord.Embed(
            title="🎫 Destek Merkezi",
            description=(
                "Yardım almak için aşağıdaki butona tıklayarak bir destek talebi oluşturabilirsin.\n\n"
                "📌 **Kurallar:**\n"
                "• Sadece gerçek sorunlar için ticket aç\n"
                "• Aynı anda yalnızca 1 açık ticket olabilir\n"
                "• Sorununuzu detaylı açıklayın\n\n"
                "⏱️ Ekibimiz en kısa sürede yardımcı olacak."
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Zerith Security | Destek Sistemi")
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed, view=TicketOpenView())
        try:
            await ctx.message.delete()
        except Exception:
            pass

    # ── Rol grubu ──
    rol_group = app_commands.Group(name="rol", description="Rol sistemi komutları")

    @rol_group.command(name="panel", description="Butonlu rol seçim paneli oluştur.")
    @app_commands.describe(baslik="Panel başlığı", aciklama="Panel açıklaması")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rol_panel(interaction: discord.Interaction, baslik: str = "🎭 Rol Seçimi", aciklama: str = "İstediğin rolleri aşağıdan seç:"):
        embed = discord.Embed(title=baslik, description=aciklama, color=discord.Color.blurple())
        embed.set_footer(text="Zerith Security | Rol Paneli")
        msg = await interaction.channel.send(embed=embed)
        gid = str(interaction.guild.id)
        if gid not in ROL_PANEL_DATA:
            ROL_PANEL_DATA[gid] = {}
        ROL_PANEL_DATA[gid][str(msg.id)] = {"baslik": baslik, "aciklama": aciklama, "roller": []}
        await interaction.response.send_message(
            f"✅ Panel oluşturuldu! Mesaj ID: `{msg.id}`\nRol eklemek için: `/rol ekle mesaj_id:{msg.id} rol:@Rol`",
            ephemeral=True
        )

    @rol_group.command(name="ekle", description="Rol paneline rol ekle.")
    @app_commands.describe(mesaj_id="Panelin mesaj ID'si", rol="Eklenecek rol", emoji="Emoji (opsiyonel)", label="Buton yazısı (opsiyonel)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rol_ekle(interaction: discord.Interaction, mesaj_id: str, rol: discord.Role, emoji: str = "", label: str = ""):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        if gid not in ROL_PANEL_DATA or mesaj_id not in ROL_PANEL_DATA[gid]:
            return await interaction.followup.send("❌ Panel bulunamadı.", ephemeral=True)
        panel = ROL_PANEL_DATA[gid][mesaj_id]
        label = label or rol.name
        for r in panel["roller"]:
            if r["role_id"] == rol.id:
                return await interaction.followup.send("❌ Bu rol zaten panelde.", ephemeral=True)
        panel["roller"].append({"label": label, "emoji": emoji, "role_id": rol.id})
        try:
            msg = await interaction.channel.fetch_message(int(mesaj_id))
            roller_list = [(r["label"], r["emoji"], r["role_id"]) for r in panel["roller"]]
            embed = discord.Embed(title=panel["baslik"], description=panel["aciklama"], color=discord.Color.blurple())
            embed.set_footer(text="Zerith Security | Rol Paneli")
            await msg.edit(embed=embed, view=RolSecimView(roller=roller_list))
            await interaction.followup.send(f"✅ **{rol.name}** eklendi.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Mesaj bulunamadı.", ephemeral=True)

    @rol_group.command(name="sil", description="Rol panelinden rol çıkar.")
    @app_commands.describe(mesaj_id="Panel mesaj ID'si", rol="Çıkarılacak rol")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rol_sil(interaction: discord.Interaction, mesaj_id: str, rol: discord.Role):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        panel = ROL_PANEL_DATA.get(gid, {}).get(mesaj_id)
        if not panel:
            return await interaction.followup.send("❌ Panel bulunamadı.", ephemeral=True)
        panel["roller"] = [r for r in panel["roller"] if r["role_id"] != rol.id]
        try:
            msg = await interaction.channel.fetch_message(int(mesaj_id))
            roller_list = [(r["label"], r["emoji"], r["role_id"]) for r in panel["roller"]]
            view = RolSecimView(roller=roller_list) if roller_list else discord.ui.View()
            embed = discord.Embed(title=panel["baslik"], description=panel["aciklama"], color=discord.Color.blurple())
            await msg.edit(embed=embed, view=view)
            await interaction.followup.send(f"✅ **{rol.name}** kaldırıldı.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Mesaj bulunamadı.", ephemeral=True)

    @rol_group.command(name="hepsinever", description="Tüm üyelere bir rol ver.")
    @app_commands.describe(rol="Verilecek rol")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rol_hepsine(interaction: discord.Interaction, rol: discord.Role):
        await interaction.response.defer(ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if not member.bot and rol not in member.roles:
                try:
                    await member.add_roles(rol, reason=f"Toplu rol — {interaction.user}")
                    count += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
        await interaction.followup.send(f"✅ **{count}** üyeye **{rol.name}** rolü verildi.", ephemeral=True)

    b.tree.add_command(rol_group)

    # ── Etkinlik grubu ──
    etkinlik_group = app_commands.Group(name="etkinlik", description="Etkinlik sistemi")

    @etkinlik_group.command(name="olustur", description="Yeni etkinlik oluştur.")
    @app_commands.describe(baslik="Başlık", aciklama="Açıklama", baslangic="Başlangıç (2024-12-25 20:00)",
                           bitis="Bitiş (opsiyonel)", konum="Konum", max_katilimci="Maks katılımcı (0=sınırsız)")
    @app_commands.checks.has_permissions(manage_events=True)
    async def etkinlik_olustur(interaction: discord.Interaction, baslik: str, aciklama: str, baslangic: str,
                                bitis: str = None, konum: str = "Discord", max_katilimci: int = 0):
        await interaction.response.defer()
        try:
            starts_at = datetime.strptime(baslangic, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return await interaction.followup.send("❌ Geçersiz tarih. Örn: `2024-12-25 20:00`", ephemeral=True)
        ends_at = None
        if bitis:
            try:
                ends_at = datetime.strptime(bitis, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return await interaction.followup.send("❌ Geçersiz bitiş tarihi.", ephemeral=True)

        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO events (guild_id, channel_id, message_id, title, description, location, starts_at, ends_at, host_id, max_participants) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(interaction.guild.id), str(interaction.channel.id), "0",
             baslik, aciklama, konum, starts_at, ends_at or 0, str(interaction.user.id), max_katilimci)
        )
        eid = c.lastrowid
        conn.commit()
        conn.close()

        row_mock = {"id": eid, "title": baslik, "description": aciklama, "location": konum,
                    "starts_at": starts_at, "ends_at": ends_at, "max_participants": max_katilimci,
                    "participants": "[]", "channel_id": str(interaction.channel.id), "message_id": "0"}
        embed = _build_event_embed(row_mock, [])
        embed.set_author(name=f"Düzenleyen: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        msg = await interaction.followup.send(embed=embed, view=EtkinlikKatilView(event_id=eid))
        conn = db_connect()
        c = conn.cursor()
        c.execute("UPDATE events SET message_id=? WHERE id=?", (str(msg.id), eid))
        conn.commit()
        conn.close()

    @etkinlik_group.command(name="liste", description="Aktif etkinlikleri listele.")
    async def etkinlik_liste(interaction: discord.Interaction):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE guild_id=? AND status='active' ORDER BY starts_at ASC LIMIT 10",
                  (str(interaction.guild.id),))
        rows = c.fetchall()
        conn.close()
        embed = discord.Embed(title="📅 Aktif Etkinlikler", color=discord.Color.blue())
        if not rows:
            embed.description = "Aktif etkinlik yok."
        else:
            for row in rows:
                p = json.loads(row["participants"])
                p_str = f"{len(p)}" + (f"/{row['max_participants']}" if row["max_participants"] > 0 else "")
                embed.add_field(name=f"#{row['id']} — {row['title']}",
                                value=f"📍 {row['location']} | 🕐 <t:{int(row['starts_at'])}:R> | 👥 {p_str}", inline=False)
        await interaction.response.send_message(embed=embed)

    @etkinlik_group.command(name="iptal", description="Etkinliği iptal et.")
    @app_commands.describe(id="Etkinlik ID'si")
    @app_commands.checks.has_permissions(manage_events=True)
    async def etkinlik_iptal(interaction: discord.Interaction, id: int):
        conn = db_connect()
        c = conn.cursor()
        c.execute("UPDATE events SET status='cancelled' WHERE id=? AND guild_id=?", (id, str(interaction.guild.id)))
        ok = c.rowcount > 0
        conn.commit()
        conn.close()
        if ok:
            await interaction.response.send_message(f"✅ Etkinlik #{id} iptal edildi.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Etkinlik bulunamadı.", ephemeral=True)

    b.tree.add_command(etkinlik_group)

    # ── Anti-Raid grubu ──
    antiraid_group = app_commands.Group(name="antiraid", description="Anti-Raid yönetimi (Admin)")

    @antiraid_group.command(name="durum", description="Anti-Raid durumunu göster.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antiraid_durum(interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        embed = discord.Embed(title="🛡️ Anti-Raid Durumu", color=discord.Color.blurple())
        embed.add_field(name="Katılım Eşiği", value=f"{RAID_CONFIG['join_threshold']} üye/{RAID_CONFIG['join_window']}sn")
        embed.add_field(name="Yeni Hesap Eşiği", value=f"{RAID_CONFIG['new_account_days']} günden genç")
        embed.add_field(name="Mass Mention Eşiği", value=f"{RAID_CONFIG['mass_mention_threshold']}+ mention")
        embed.add_field(name="Spam Eşiği", value=f"{RAID_CONFIG['duplicate_msg_threshold']}x aynı mesaj")
        embed.add_field(name="Otomatik Kilit", value="✅ Aktif" if RAID_CONFIG["auto_lockdown"] else "❌ Kapalı")
        embed.add_field(name="Son 10sn Katılım", value=str(len(RAID_JOIN_LOG[gid])))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @antiraid_group.command(name="unlock", description="Raid kilidini kaldır.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antiraid_unlock(interaction: discord.Interaction):
        try:
            await interaction.guild.edit(verification_level=discord.VerificationLevel.low,
                                         reason=f"Kilidi kaldırıldı — {interaction.user}")
            await interaction.response.send_message("✅ Doğrulama seviyesi normale döndürüldü.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Hata: {e}", ephemeral=True)

    @antiraid_group.command(name="ayar", description="Anti-Raid ayarlarını değiştir.")
    @app_commands.describe(katilim_esigi="Raid eşiği", pencere="Zaman penceresi (sn)", oto_kilit="Otomatik kilit")
    @app_commands.checks.has_permissions(administrator=True)
    async def antiraid_ayar(interaction: discord.Interaction, katilim_esigi: int = None,
                             pencere: int = None, oto_kilit: bool = None):
        if katilim_esigi is not None:
            RAID_CONFIG["join_threshold"] = max(3, katilim_esigi)
        if pencere is not None:
            RAID_CONFIG["join_window"] = max(5, pencere)
        if oto_kilit is not None:
            RAID_CONFIG["auto_lockdown"] = oto_kilit
        embed = discord.Embed(title="⚙️ Anti-Raid Güncellendi", color=discord.Color.green())
        embed.add_field(name="Katılım Eşiği", value=str(RAID_CONFIG["join_threshold"]))
        embed.add_field(name="Pencere", value=f"{RAID_CONFIG['join_window']}sn")
        embed.add_field(name="Oto Kilit", value="✅" if RAID_CONFIG["auto_lockdown"] else "❌")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    b.tree.add_command(antiraid_group)

    # ── Form grubu ──
    form_group = app_commands.Group(name="form", description="Başvuru formu sistemi")

    @form_group.command(name="olustur", description="Yeni başvuru formu oluştur.")
    @app_commands.describe(baslik="Form başlığı", log_kanal="Başvuruların kanalı", kabul_rolu="Kabul rolü (opsiyonel)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def form_olustur(interaction: discord.Interaction, baslik: str,
                            log_kanal: discord.TextChannel, kabul_rolu: discord.Role = None):
        conn = db_connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO forms (guild_id, title, description, log_channel_id, role_on_accept_id) VALUES (?,?,?,?,?)",
            (str(interaction.guild.id), baslik, baslik,
             str(log_kanal.id), str(kabul_rolu.id) if kabul_rolu else None)
        )
        fid = c.lastrowid
        conn.commit()
        conn.close()
        await interaction.response.send_message(
            f"✅ **{baslik}** formu oluşturuldu! ID: `{fid}`\n"
            f"Soru ekle: `/form soruekle form_id:{fid} soru:...`\n"
            f"Panel kur: `/form panel form_id:{fid}`", ephemeral=True
        )

    @form_group.command(name="soruekle", description="Forma soru ekle (maks 5).")
    @app_commands.describe(form_id="Form ID", soru="Soru metni")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def form_soruekle(interaction: discord.Interaction, form_id: int, soru: str):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT questions FROM forms WHERE id=? AND guild_id=?", (form_id, str(interaction.guild.id)))
        row = c.fetchone()
        if not row:
            conn.close()
            return await interaction.response.send_message("❌ Form bulunamadı.", ephemeral=True)
        questions = json.loads(row["questions"])
        if len(questions) >= 5:
            conn.close()
            return await interaction.response.send_message("❌ Maksimum 5 soru.", ephemeral=True)
        questions.append(soru)
        c.execute("UPDATE forms SET questions=? WHERE id=?", (json.dumps(questions, ensure_ascii=False), form_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ Soru eklendi! Toplam: {len(questions)}/5", ephemeral=True)

    @form_group.command(name="panel", description="Başvuru panelini yayınla.")
    @app_commands.describe(form_id="Form ID", aciklama="Panel açıklaması")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def form_panel(interaction: discord.Interaction, form_id: int, aciklama: str = ""):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM forms WHERE id=? AND guild_id=?", (form_id, str(interaction.guild.id)))
        form = c.fetchone()
        conn.close()
        if not form:
            return await interaction.response.send_message("❌ Form bulunamadı.", ephemeral=True)
        questions = json.loads(form["questions"])
        if not questions:
            return await interaction.response.send_message("❌ Önce soru ekle!", ephemeral=True)
        embed = discord.Embed(title=f"📝 {form['title']}",
                              description=aciklama or "Aşağıdaki butona tıklayarak başvurunu tamamla.",
                              color=discord.Color.blue())
        embed.add_field(name="❓ Sorular", value="\n".join(f"{i+1}. {q}" for i, q in enumerate(questions)), inline=False)
        embed.set_footer(text="Zerith Security | Başvuru Sistemi")
        await interaction.channel.send(embed=embed, view=BasvuruAcView(form_id=form_id, sorular=questions, form_title=form["title"]))
        await interaction.response.send_message("✅ Panel yayınlandı!", ephemeral=True)

    @form_group.command(name="liste", description="Başvuruları listele.")
    @app_commands.describe(form_id="Form ID", durum="Durum filtresi")
    @app_commands.choices(durum=[
        app_commands.Choice(name="Bekleyen", value="pending"),
        app_commands.Choice(name="Kabul Edilmiş", value="accepted"),
        app_commands.Choice(name="Reddedilmiş", value="rejected"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def form_liste(interaction: discord.Interaction, form_id: int, durum: str = "pending"):
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT * FROM form_responses WHERE form_id=? AND guild_id=? AND status=? ORDER BY submitted_at DESC LIMIT 20",
                  (form_id, str(interaction.guild.id), durum))
        rows = c.fetchall()
        c.execute("SELECT title FROM forms WHERE id=?", (form_id,))
        form = c.fetchone()
        conn.close()
        durum_emoji = {"pending": "⏳", "accepted": "✅", "rejected": "❌"}
        embed = discord.Embed(title=f"📋 {form['title'] if form else 'Form'} — Başvurular", color=discord.Color.blurple())
        if not rows:
            embed.description = f"Bu durumda başvuru yok."
        else:
            for row in rows:
                member = interaction.guild.get_member(int(row["user_id"]))
                name = member.display_name if member else f"ID:{row['user_id']}"
                ts = datetime.fromtimestamp(row["submitted_at"]).strftime("%d/%m/%Y %H:%M")
                embed.add_field(name=f"#{row['id']} — {name}", value=f"{durum_emoji.get(row['status'], '?')} {ts}", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    b.tree.add_command(form_group)

    # ── Çeviri komutları ──
    dil_choices = [app_commands.Choice(name=f"{v} ({k})", value=k) for k, v in list(DILLER.items())[:25]]

    @b.tree.command(name="çevir", description="Metni başka bir dile çevir.")
    @app_commands.describe(metin="Çevrilecek metin", hedef_dil="Hedef dil", kaynak_dil="Kaynak dil (varsayılan: auto)")
    @app_commands.choices(hedef_dil=dil_choices)
    async def slash_cevir(interaction: discord.Interaction, metin: str, hedef_dil: str, kaynak_dil: str = "auto"):
        await interaction.response.defer()
        if len(metin) > 500:
            return await interaction.followup.send("❌ Maksimum 500 karakter.", ephemeral=True)
        sonuc = await translate_text(metin, hedef_dil, kaynak_dil)
        if not sonuc:
            return await interaction.followup.send("❌ Çeviri başarısız.", ephemeral=True)
        embed = discord.Embed(title="🌍 Çeviri", color=discord.Color.blue())
        embed.add_field(name=f"📥 Kaynak ({DILLER.get(kaynak_dil, 'Otomatik')})", value=f"```{metin[:900]}```", inline=False)
        embed.add_field(name=f"📤 {DILLER.get(hedef_dil, hedef_dil)}", value=f"```{sonuc[:900]}```", inline=False)
        embed.set_footer(text="Zerith Security | Çeviri • MyMemory API")
        await interaction.followup.send(embed=embed)

    @b.command(name="çevir", aliases=["cevir", "translate"])
    async def prefix_cevir(ctx, hedef_dil: str, *, metin: str):
        """!çevir <dil_kodu> <metin>"""
        if hedef_dil not in DILLER:
            return await ctx.send(f"❌ Geçersiz dil. Desteklenen: {', '.join(f'`{k}`' for k in DILLER)}")
        async with ctx.typing():
            sonuc = await translate_text(metin, hedef_dil)
        if not sonuc:
            return await ctx.send("❌ Çeviri başarısız.")
        embed = discord.Embed(title="🌍 Çeviri", color=discord.Color.blue())
        embed.add_field(name="📥 Orijinal", value=f"```{metin[:900]}```", inline=False)
        embed.add_field(name=f"📤 {DILLER[hedef_dil]}", value=f"```{sonuc[:900]}```", inline=False)
        await ctx.send(embed=embed)

    @b.tree.command(name="diller", description="Desteklenen çeviri dillerini listele.")
    async def slash_diller(interaction: discord.Interaction):
        embed = discord.Embed(title="🌍 Desteklenen Diller", color=discord.Color.blue())
        embed.description = "\n".join(f"`{k}` — {v}" for k, v in DILLER.items())
        embed.set_footer(text="Kullanım: /çevir metin:... hedef_dil:en")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
#  KURULUM FONKSİYONU
# ============================================================

async def setup_new_systems(bot_instance: commands.Bot,
                             db_connect_func=None,
                             get_settings_func=None,
                             log_send_func=None,
                             warn_add_func=None):
    """
    main.py on_ready içine ekle:
        await setup_new_systems(bot, db_connect, get_settings, log_send, warn_add)
    """
    global bot, db_connect, get_settings, log_send, warn_add
    bot = bot_instance
    db_connect = db_connect_func
    get_settings = get_settings_func
    log_send = log_send_func
    warn_add = warn_add_func

    event_db_init()
    form_db_init()
    _register_commands(bot_instance)

    bot_instance.add_view(TicketOpenView())
    bot_instance.add_view(TicketControlView())

    print("✅ Yeni sistemler başlatıldı: Ticket, Rol, Etkinlik, Anti-Raid, Form, Çeviri")