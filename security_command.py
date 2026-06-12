bash

cat > /mnt/user-data/outputs/main.py << 'ENDOFFILE'
"""
main.py — Zerith Security
Genel amaçlı çok sunucu destekli Discord botu.
Moderasyon, Ekonomi, Eğlence, Güvenlik ve daha fazlası.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta, datetime, timezone
import random
import asyncio
import json
import os
import sqlite3
import time
import re
import hashlib
import ipaddress
import socket
import urllib.parse
import base64
import string
import secrets
from typing import Optional
from minigames import setup_minigames
from yeni_sistemler import setup_new_systems, antiraid_on_member_join, antiraid_on_message

# ============================================================
#  AYARLAR
# ============================================================
TOKEN = 'MTUxMzE0MTY0MzE1NzU2OTU2Ng.G0-VY2.OTQX_VD2sUGBi9hFQ39TAwvviAkaUZ-niAIUn0'

# ============================================================
#  VERİTABANI
# ============================================================

def db_connect():
    conn = sqlite3.connect("zerith.db")
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        welcome_channel_id TEXT,
        goodbye_channel_id TEXT,
        log_channel_id TEXT,
        mod_role_id TEXT,
        mute_role_id TEXT,
        autorole_id TEXT,
        prefix TEXT DEFAULT '!',
        welcome_message TEXT DEFAULT 'Sunucuya hoş geldin {user}! 🎉',
        goodbye_message TEXT DEFAULT '{user} sunucudan ayrıldı.',
        level_up_channel_id TEXT,
        suggestion_channel_id TEXT,
        ticket_category_id TEXT,
        ticket_log_channel_id TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS xp (
        user_id TEXT,
        guild_id TEXT,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0,
        last_xp_time REAL DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id TEXT,
        moderator_id TEXT,
        reason TEXT,
        timestamp REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS economy (
        user_id TEXT,
        guild_id TEXT,
        coins INTEGER DEFAULT 0,
        bank INTEGER DEFAULT 0,
        last_daily REAL DEFAULT 0,
        last_work REAL DEFAULT 0,
        last_crime REAL DEFAULT 0,
        streak INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventory (
        user_id TEXT,
        guild_id TEXT,
        item_id TEXT,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, guild_id, item_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS afk (
        user_id TEXT,
        guild_id TEXT,
        reason TEXT,
        timestamp REAL,
        PRIMARY KEY (user_id, guild_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        channel_id TEXT,
        user_id TEXT,
        status TEXT DEFAULT 'open',
        created_at REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        channel_id TEXT,
        message_id TEXT,
        prize TEXT,
        winner_count INTEGER DEFAULT 1,
        ends_at REAL,
        host_id TEXT,
        ended INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        channel_id TEXT,
        guild_id TEXT,
        message TEXT,
        remind_at REAL,
        done INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS mod_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id TEXT,
        moderator_id TEXT,
        note TEXT,
        timestamp REAL
    )""")

    conn.commit()
    conn.close()

# ============================================================
#  XP FONKSİYONLARI
# ============================================================
XP_PER_MESSAGE = 15
XP_COOLDOWN = 60

LEVEL_THRESHOLDS = {
    1: 100, 2: 250, 3: 500, 4: 900, 5: 1400,
    6: 2100, 7: 3000, 8: 4200, 9: 5800, 10: 7800,
    15: 15000, 20: 28000, 25: 45000, 30: 70000
}

def get_level(xp):
    level = 0
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if xp >= threshold:
            level = lvl
    return level

def xp_add(user_id, guild_id, amount):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT xp, level, last_xp_time FROM xp WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = c.fetchone()
    now = time.time()
    if row:
        if now - row["last_xp_time"] < XP_COOLDOWN:
            conn.close()
            return row["xp"], row["level"], False
        new_xp = row["xp"] + amount
        old_level = row["level"]
        new_level = get_level(new_xp)
        leveled_up = new_level > old_level
        c.execute("UPDATE xp SET xp=?, level=?, last_xp_time=? WHERE user_id=? AND guild_id=?",
                  (new_xp, new_level, now, str(user_id), str(guild_id)))
    else:
        new_xp = amount
        new_level = get_level(new_xp)
        leveled_up = new_level > 0
        c.execute("INSERT INTO xp VALUES (?,?,?,?,?)", (str(user_id), str(guild_id), new_xp, new_level, now))
    conn.commit()
    conn.close()
    return new_xp, new_level, leveled_up

def xp_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT xp, level FROM xp WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = c.fetchone()
    conn.close()
    if row:
        return {"xp": row["xp"], "level": row["level"]}
    return {"xp": 0, "level": 0}

def xp_leaderboard(guild_id, limit=10):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id, xp, level FROM xp WHERE guild_id=? ORDER BY xp DESC LIMIT ?", (str(guild_id), limit))
    rows = c.fetchall()
    conn.close()
    return [(r["user_id"], r["xp"], r["level"]) for r in rows]

def xp_rank(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*)+1 FROM xp WHERE guild_id=? AND xp > (SELECT COALESCE(xp,0) FROM xp WHERE user_id=? AND guild_id=?)",
              (str(guild_id), str(user_id), str(guild_id)))
    rank = c.fetchone()[0]
    conn.close()
    return rank

# ============================================================
#  UYARI FONKSİYONLARI
# ============================================================

def warn_add(user_id, guild_id, mod_id, reason):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?,?,?,?,?)",
              (str(user_id), str(guild_id), str(mod_id), reason, time.time()))
    conn.commit()
    c.execute("SELECT COUNT(*) FROM warnings WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    count = c.fetchone()[0]
    conn.close()
    return count

def warn_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM warnings WHERE user_id=? AND guild_id=? ORDER BY timestamp DESC", (str(user_id), str(guild_id)))
    rows = c.fetchall()
    conn.close()
    return rows

def warn_remove(warn_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("DELETE FROM warnings WHERE id=? AND guild_id=?", (warn_id, str(guild_id)))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def warn_clear(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("DELETE FROM warnings WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    conn.commit()
    conn.close()

# ============================================================
#  EKONOMİ FONKSİYONLARI
# ============================================================
DAILY_MIN = 200
DAILY_MAX = 500
WORK_MIN = 50
WORK_MAX = 150
CRIME_MIN = 100
CRIME_MAX = 400
CRIME_FAIL_CHANCE = 0.35

WORK_MESSAGES = [
    "Pizzacıda kurye olarak çalıştın", "Kod yazdın ve ödeme aldın",
    "Sunucuda garsonluk yaptın", "Freelance tasarım işi yaptın",
    "Arabalar yıkadın", "Kargo dağıttın", "Mağazada kasiyer oldun"
]

CRIME_SUCCESS = [
    "Birinin cüzdanını çaldın", "Sahte para bastın",
    "Bir bankayı soydum... küçük bir bankayı", "Hırsızlık yaptın"
]

CRIME_FAIL = [
    "Yakalandın ve ceza ödedin", "Kaçarken senin cüzdanın düştü",
    "Polis geldi ve kaçamadın", "Sahte paran sahte çıktı"
]

MARKET_ITEMS = {
    "fishing_rod": {"name": "Olta", "emoji": "🎣", "price": 300, "sell_price": 150, "description": "Balık tutmak için"},
    "pickaxe": {"name": "Kazma", "emoji": "⛏️", "price": 500, "sell_price": 250, "description": "Maden kazmak için"},
    "shield": {"name": "Kalkan", "emoji": "🛡️", "price": 800, "sell_price": 400, "description": "Suç başarısız olunca korutur"},
    "lucky_charm": {"name": "Şans Kolyesi", "emoji": "🍀", "price": 1200, "sell_price": 600, "description": "Suç şansını artırır"},
    "coffee": {"name": "Kahve", "emoji": "☕", "price": 50, "sell_price": 10, "description": "Çalışma bekleme süresini kısaltır"},
    "laptop": {"name": "Laptop", "emoji": "💻", "price": 2000, "sell_price": 1000, "description": "Daha fazla kazanmak için"},
    "sword": {"name": "Kılıç", "emoji": "⚔️", "price": 1500, "sell_price": 750, "description": "Düello için"},
}

def eco_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM economy WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"coins": 0, "bank": 0, "last_daily": 0, "last_work": 0, "last_crime": 0, "streak": 0}

def eco_set_coins(user_id, guild_id, amount):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO economy (user_id, guild_id, coins) VALUES (?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET coins=?",
              (str(user_id), str(guild_id), max(0, amount), max(0, amount)))
    conn.commit()
    conn.close()

def eco_add_coins(user_id, guild_id, amount):
    data = eco_get(user_id, guild_id)
    eco_set_coins(user_id, guild_id, data["coins"] + amount)

def eco_update(user_id, guild_id, **kwargs):
    conn = db_connect()
    c = conn.cursor()
    fields = ", ".join(f"{k}=?" for k in kwargs)
    c.execute(f"INSERT INTO economy (user_id, guild_id) VALUES (?,?) ON CONFLICT(user_id, guild_id) DO NOTHING",
              (str(user_id), str(guild_id)))
    c.execute(f"UPDATE economy SET {fields} WHERE user_id=? AND guild_id=?",
              (*kwargs.values(), str(user_id), str(guild_id)))
    conn.commit()
    conn.close()

def eco_leaderboard(guild_id, limit=10):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id, coins+bank as total FROM economy WHERE guild_id=? ORDER BY total DESC LIMIT ?", (str(guild_id), limit))
    rows = c.fetchall()
    conn.close()
    return [(r["user_id"], r["total"]) for r in rows]

def inv_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT item_id, quantity FROM inventory WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    rows = c.fetchall()
    conn.close()
    return {r["item_id"]: r["quantity"] for r in rows}

def inv_add(user_id, guild_id, item_id, qty=1):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, guild_id, item_id, quantity) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id,item_id) DO UPDATE SET quantity=quantity+?",
              (str(user_id), str(guild_id), item_id, qty, qty))
    conn.commit()
    conn.close()

def inv_remove(user_id, guild_id, item_id, qty=1):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT quantity FROM inventory WHERE user_id=? AND guild_id=? AND item_id=?", (str(user_id), str(guild_id), item_id))
    row = c.fetchone()
    if not row or row["quantity"] < qty:
        conn.close()
        return False
    if row["quantity"] == qty:
        c.execute("DELETE FROM inventory WHERE user_id=? AND guild_id=? AND item_id=?", (str(user_id), str(guild_id), item_id))
    else:
        c.execute("UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND guild_id=? AND item_id=?", (qty, str(user_id), str(guild_id), item_id))
    conn.commit()
    conn.close()
    return True

# ============================================================
#  SUNUCU AYARLARI
# ============================================================

def get_settings(guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM guild_settings WHERE guild_id=?", (str(guild_id),))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

def set_setting(guild_id, key, value):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO guild_settings (guild_id) VALUES (?) ON CONFLICT(guild_id) DO NOTHING", (str(guild_id),))
    c.execute(f"UPDATE guild_settings SET {key}=? WHERE guild_id=?", (str(value) if value else None, str(guild_id)))
    conn.commit()
    conn.close()

# ============================================================
#  AFK
# ============================================================

def afk_set(user_id, guild_id, reason):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO afk (user_id, guild_id, reason, timestamp) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET reason=?, timestamp=?",
              (str(user_id), str(guild_id), reason, time.time(), reason, time.time()))
    conn.commit()
    conn.close()

def afk_remove(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("DELETE FROM afk WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    conn.commit()
    conn.close()

def afk_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT reason, timestamp FROM afk WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = c.fetchone()
    conn.close()
    if row:
        return {"reason": row["reason"], "timestamp": row["timestamp"]}
    return None

# ============================================================
#  MOD NOTLARI
# ============================================================

def note_add(user_id, guild_id, mod_id, note):
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO mod_notes (user_id, guild_id, moderator_id, note, timestamp) VALUES (?,?,?,?,?)",
              (str(user_id), str(guild_id), str(mod_id), note, time.time()))
    conn.commit()
    conn.close()

def note_get(user_id, guild_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM mod_notes WHERE user_id=? AND guild_id=? ORDER BY timestamp DESC", (str(user_id), str(guild_id)))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================================
#  YARDIMCILAR
# ============================================================

def format_time(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}dk {int(seconds%60)}s"
    else:
        return f"{int(seconds//3600)}sa {int((seconds%3600)//60)}dk"

def time_ago(timestamp):
    diff = time.time() - timestamp
    return format_time(diff) + " önce"

async def log_send(guild, embed):
    settings = get_settings(guild.id)
    log_id = settings.get("log_channel_id")
    if log_id:
        ch = guild.get_channel(int(log_id))
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

def has_mod_role():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        settings = get_settings(ctx.guild.id)
        mod_role_id = settings.get("mod_role_id")
        if mod_role_id:
            role = ctx.guild.get_role(int(mod_role_id))
            if role and role in ctx.author.roles:
                return True
        raise commands.MissingPermissions(["manage_messages"])
    return commands.check(predicate)

# ============================================================
#  BOT KURULUMU
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ============================================================
#  KÜFÜR & REKLAM FİLTRESİ
# ============================================================

KUFUR_LISTESI = [
    "orospu", "piç", "siktir", "göt", "yarrak", "oç",
    "ananı sikerim", "orospu evladı", "siktir git", "sikerim",
    "porno", "pirno", "sikiş", "sikeceğim", "sikicem",
    "ananın", "babanın", "sülaleni", "amını", "orospu çocuğu"
]

KUFUR_FILTRE_KAPALI = set()

REKLAM_IFADELERI = [
    "discord.gg/", "discord.com/invite/", "discordapp.com/invite/",
    "dsc.gg/", "disboard.org/"
]

def kufur_kontrol(icerik: str) -> bool:
    temiz = re.sub(r"[^\w\s]", " ", icerik.lower())
    kelimeler = temiz.split()
    for kufur in KUFUR_LISTESI:
        if " " in kufur:
            if kufur in icerik.lower():
                return True
        else:
            if kufur in kelimeler:
                return True
    return False

# ============================================================
#  ZAMANLI GÖREVLER
# ============================================================

@tasks.loop(minutes=1)
async def check_reminders():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE done=0 AND remind_at<=?", (time.time(),))
    rows = c.fetchall()
    for row in rows:
        channel = bot.get_channel(int(row["channel_id"]))
        if channel:
            user = bot.get_user(int(row["user_id"]))
            if user:
                embed = discord.Embed(
                    title="⏰ Hatırlatıcı!",
                    description=row["message"],
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"ID: {row['id']}")
                try:
                    await channel.send(user.mention, embed=embed)
                except Exception:
                    pass
        c.execute("UPDATE reminders SET done=1 WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()

@tasks.loop(minutes=1)
async def check_giveaways():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM giveaways WHERE ended=0 AND ends_at<=?", (time.time(),))
    rows = c.fetchall()
    for row in rows:
        guild = bot.get_guild(int(row["guild_id"]))
        if not guild:
            continue
        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            continue
        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            reaction = discord.utils.get(msg.reactions, emoji="🎉")
            users = []
            if reaction:
                async for user in reaction.users():
                    if not user.bot:
                        users.append(user)
            embed = discord.Embed(title=f"🎉 Çekiliş Sona Erdi: {row['prize']}", color=discord.Color.gold())
            if users:
                winners = random.sample(users, min(row["winner_count"], len(users)))
                embed.description = f"**Kazananlar:** {', '.join(w.mention for w in winners)}"
                await channel.send(f"Tebrikler {', '.join(w.mention for w in winners)}! **{row['prize']}** kazandınız! 🎉", embed=embed)
            else:
                embed.description = "Katılımcı olmadığı için kazanan yok."
                await channel.send(embed=embed)
            await msg.edit(embed=embed)
        except Exception:
            pass
        c.execute("UPDATE giveaways SET ended=1 WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()

# ============================================================
#  BOT HAZIR
# ============================================================

@bot.event
async def on_ready():
    db_init()
    await setup_minigames(bot)
    await setup_new_systems(bot, db_connect, get_settings, log_send, warn_add)
    check_reminders.start()
    check_giveaways.start()
    try:
        synced = await bot.tree.sync()
        print(f'✅ {bot.user} | {len(synced)} slash komutu senkronize edildi.')
    except Exception as e:
        print(f'❌ Senkronizasyon hatası: {e}')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} sunucu | !yardım"
    ))
    print(f'✅ {bot.user} hazır! {len(bot.guilds)} sunucu, {sum(g.member_count for g in bot.guilds)} üye')


@bot.command(name="sync")
@commands.is_owner()
async def sync_cmd(ctx):
    msg = await ctx.send("⏳ Senkronize ediliyor...")
    synced = await bot.tree.sync()
    await msg.edit(content=f"✅ {len(synced)} komut senkronize edildi.")


# ============================================================
#  MESAJ OLAYI
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await antiraid_on_message(message)

    icerik = message.content.lower()

    afk_data = afk_get(message.author.id, message.guild.id)
    if afk_data and not message.content.startswith("!afk"):
        afk_remove(message.author.id, message.guild.id)
        gone_for = format_time(time.time() - afk_data["timestamp"])
        await message.channel.send(
            f"👋 {message.author.mention} AFK modundan çıktın! _(Süre: {gone_for})_",
            delete_after=8
        )

    for mention in message.mentions:
        if mention.bot:
            continue
        bilgi = afk_get(mention.id, message.guild.id)
        if bilgi:
            gone_for = format_time(time.time() - bilgi["timestamp"])
            embed = discord.Embed(
                title=f"💤 {mention.display_name} AFK!",
                description=f"**Sebep:** {bilgi['reason']}\n**Gittiği süre:** {gone_for}",
                color=discord.Color.greyple()
            )
            await message.channel.send(embed=embed, delete_after=10)

    if message.guild.id not in KUFUR_FILTRE_KAPALI:
        if kufur_kontrol(icerik):
            await message.delete()
            count = warn_add(message.author.id, message.guild.id, bot.user.id, "Otomatik: Küfür")
            await message.channel.send(
                f"⚠️ {message.author.mention} küfür yasaktır! Uyarı: **{count}/3**",
                delete_after=6
            )
            embed = discord.Embed(title="🚫 Küfür Engellendi", color=discord.Color.red())
            embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
            embed.add_field(name="Kanal", value=message.channel.mention)
            embed.add_field(name="Toplam Uyarı", value=f"{count}/3")
            embed.timestamp = discord.utils.utcnow()
            await log_send(message.guild, embed)
            if count >= 3:
                try:
                    await message.author.timeout(timedelta(minutes=10), reason="3 uyarı — küfür")
                    await message.channel.send(
                        f"🔇 {message.author.mention} 3 uyarı sonucu 10 dakika susturuldu.",
                        delete_after=8
                    )
                    warn_clear(message.author.id, message.guild.id)
                except Exception:
                    pass
            return

    for ifade in REKLAM_IFADELERI:
        if ifade in icerik:
            await message.delete()
            count = warn_add(message.author.id, message.guild.id, bot.user.id, "Otomatik: Reklam")
            await message.channel.send(
                f"📢 {message.author.mention} reklam yasaktır! Uyarı: **{count}/3**",
                delete_after=6
            )
            embed = discord.Embed(title="📢 Reklam Engellendi", color=discord.Color.orange())
            embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
            embed.add_field(name="Kanal", value=message.channel.mention)
            embed.timestamp = discord.utils.utcnow()
            await log_send(message.guild, embed)
            return

    new_xp, new_level, leveled_up = xp_add(message.author.id, message.guild.id, XP_PER_MESSAGE)
    if leveled_up:
        settings = get_settings(message.guild.id)
        lvl_ch_id = settings.get("level_up_channel_id")
        target_ch = message.guild.get_channel(int(lvl_ch_id)) if lvl_ch_id else message.channel
        if target_ch:
            embed = discord.Embed(
                title="🎉 Seviye Atladı!",
                description=f"{message.author.mention} **{new_level}. seviyeye** ulaştı!",
                color=discord.Color.gold()
            )
            await target_ch.send(embed=embed, delete_after=15)

    await bot.process_commands(message)


# ============================================================
#  GELEN / GİDEN
# ============================================================

@bot.event
async def on_member_join(member: discord.Member):
    await antiraid_on_member_join(member)
    settings = get_settings(member.guild.id)
    autorole_id = settings.get("autorole_id")
    if autorole_id:
        rol = member.guild.get_role(int(autorole_id))
        if rol:
            try:
                await member.add_roles(rol, reason="Oto-rol")
            except Exception:
                pass
    welcome_id = settings.get("welcome_channel_id")
    if welcome_id:
        ch = member.guild.get_channel(int(welcome_id))
        if ch:
            msg = settings.get("welcome_message", "Sunucuya hoş geldin {user}! 🎉")
            msg = msg.replace("{user}", member.mention)
            msg = msg.replace("{username}", member.display_name)
            msg = msg.replace("{server}", member.guild.name)
            msg = msg.replace("{count}", str(member.guild.member_count))
            embed = discord.Embed(title="✅ Yeni Üye!", description=msg, color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Hesap Oluşturma", value=member.created_at.strftime("%d/%m/%Y"))
            embed.add_field(name="Üye Sayısı", value=str(member.guild.member_count))
            embed.timestamp = discord.utils.utcnow()
            await ch.send(embed=embed)
    embed = discord.Embed(title="📥 Üye Katıldı", description=f"{member.mention}", color=discord.Color.green())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Hesap Yaşı", value=member.created_at.strftime("%d/%m/%Y"))
    embed.timestamp = discord.utils.utcnow()
    await log_send(member.guild, embed)


@bot.event
async def on_member_remove(member: discord.Member):
    settings = get_settings(member.guild.id)
    goodbye_id = settings.get("goodbye_channel_id")
    if goodbye_id:
        ch = member.guild.get_channel(int(goodbye_id))
        if ch:
            msg = settings.get("goodbye_message", "{user} sunucudan ayrıldı.")
            msg = msg.replace("{user}", str(member))
            msg = msg.replace("{username}", member.display_name)
            msg = msg.replace("{server}", member.guild.name)
            embed = discord.Embed(title="🚪 Üye Ayrıldı", description=msg, color=discord.Color.red())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()
            await ch.send(embed=embed)
    embed = discord.Embed(title="📤 Üye Ayrıldı", description=f"{member} ({member.id})", color=discord.Color.red())
    embed.timestamp = discord.utils.utcnow()
    await log_send(member.guild, embed)


@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    embed = discord.Embed(title="🗑️ Mesaj Silindi", color=discord.Color.dark_red())
    embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
    embed.add_field(name="Kanal", value=message.channel.mention)
    embed.add_field(name="İçerik", value=message.content[:1024] or "(boş)", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await log_send(message.guild, embed)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild:
        return
    if before.content == after.content:
        return
    embed = discord.Embed(title="✏️ Mesaj Düzenlendi", color=discord.Color.blue())
    embed.add_field(name="Kullanıcı", value=f"{before.author} ({before.author.id})")
    embed.add_field(name="Kanal", value=before.channel.mention)
    embed.add_field(name="Önce", value=before.content[:512] or "(boş)", inline=False)
    embed.add_field(name="Sonra", value=after.content[:512] or "(boş)", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await log_send(before.guild, embed)


# ============================================================
#  KURULUM KOMUTLARI — /setup
# ============================================================

setup_group = app_commands.Group(name="setup", description="Bot kurulum komutları (Admin)")

@setup_group.command(name="welcome", description="Karşılama kanalını ayarla.")
@app_commands.describe(kanal="Karşılama mesajının gönderileceği kanal", mesaj="Özel mesaj ({user} {username} {server} {count} kullanılabilir)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_welcome(interaction: discord.Interaction, kanal: discord.TextChannel, mesaj: str = None):
    set_setting(interaction.guild.id, "welcome_channel_id", kanal.id)
    if mesaj:
        set_setting(interaction.guild.id, "welcome_message", mesaj)
    await interaction.response.send_message(f"✅ Karşılama kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="goodbye", description="Veda kanalını ayarla.")
@app_commands.describe(kanal="Veda mesajının gönderileceği kanal", mesaj="Özel mesaj")
@app_commands.checks.has_permissions(administrator=True)
async def setup_goodbye(interaction: discord.Interaction, kanal: discord.TextChannel, mesaj: str = None):
    set_setting(interaction.guild.id, "goodbye_channel_id", kanal.id)
    if mesaj:
        set_setting(interaction.guild.id, "goodbye_message", mesaj)
    await interaction.response.send_message(f"✅ Veda kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="log", description="Log kanalını ayarla.")
@app_commands.describe(kanal="Log mesajlarının gönderileceği kanal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_log(interaction: discord.Interaction, kanal: discord.TextChannel):
    set_setting(interaction.guild.id, "log_channel_id", kanal.id)
    await interaction.response.send_message(f"✅ Log kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="modrole", description="Moderatör rolünü ayarla.")
@app_commands.describe(rol="Moderatör rolü")
@app_commands.checks.has_permissions(administrator=True)
async def setup_modrole(interaction: discord.Interaction, rol: discord.Role):
    set_setting(interaction.guild.id, "mod_role_id", rol.id)
    await interaction.response.send_message(f"✅ Moderatör rolü {rol.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="autorole", description="Yeni üyelere otomatik verilecek rolü ayarla.")
@app_commands.describe(rol="Oto-rol")
@app_commands.checks.has_permissions(administrator=True)
async def setup_autorole(interaction: discord.Interaction, rol: discord.Role = None):
    set_setting(interaction.guild.id, "autorole_id", rol.id if rol else None)
    if rol:
        await interaction.response.send_message(f"✅ Oto-rol {rol.mention} olarak ayarlandı.", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Oto-rol kapatıldı.", ephemeral=True)

@setup_group.command(name="levelup", description="Seviye atlama mesajlarının gönderileceği kanalı ayarla.")
@app_commands.describe(kanal="Seviye atlama kanalı")
@app_commands.checks.has_permissions(administrator=True)
async def setup_levelup(interaction: discord.Interaction, kanal: discord.TextChannel):
    set_setting(interaction.guild.id, "level_up_channel_id", kanal.id)
    await interaction.response.send_message(f"✅ Seviye atlama kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="suggestion", description="Öneri kanalını ayarla.")
@app_commands.describe(kanal="Öneri kanalı")
@app_commands.checks.has_permissions(administrator=True)
async def setup_suggestion(interaction: discord.Interaction, kanal: discord.TextChannel):
    set_setting(interaction.guild.id, "suggestion_channel_id", kanal.id)
    await interaction.response.send_message(f"✅ Öneri kanalı {kanal.mention} olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="ticket", description="Ticket kategorisi ve log kanalını ayarla.")
@app_commands.describe(kategori="Ticket'ların açılacağı kategori", log_kanal="Ticket loglarının gönderileceği kanal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction, kategori: discord.CategoryChannel, log_kanal: discord.TextChannel = None):
    set_setting(interaction.guild.id, "ticket_category_id", kategori.id)
    if log_kanal:
        set_setting(interaction.guild.id, "ticket_log_channel_id", log_kanal.id)
    await interaction.response.send_message(f"✅ Ticket kategorisi **{kategori.name}** olarak ayarlandı.", ephemeral=True)

@setup_group.command(name="görüntüle", description="Tüm bot ayarlarını göster.")
@app_commands.checks.has_permissions(administrator=True)
async def setup_view(interaction: discord.Interaction):
    settings = get_settings(interaction.guild.id)
    embed = discord.Embed(title="⚙️ Bot Ayarları", color=discord.Color.blurple())
    def ch_str(ch_id):
        if not ch_id: return "Ayarlanmamış"
        ch = interaction.guild.get_channel(int(ch_id))
        return ch.mention if ch else f"Silinmiş ({ch_id})"
    def role_str(role_id):
        if not role_id: return "Ayarlanmamış"
        r = interaction.guild.get_role(int(role_id))
        return r.mention if r else f"Silinmiş ({role_id})"
    embed.add_field(name="📥 Karşılama Kanalı", value=ch_str(settings.get("welcome_channel_id")))
    embed.add_field(name="📤 Veda Kanalı", value=ch_str(settings.get("goodbye_channel_id")))
    embed.add_field(name="📋 Log Kanalı", value=ch_str(settings.get("log_channel_id")))
    embed.add_field(name="🎭 Oto-Rol", value=role_str(settings.get("autorole_id")))
    embed.add_field(name="🛡️ Moderatör Rolü", value=role_str(settings.get("mod_role_id")))
    embed.add_field(name="⭐ Seviye Kanalı", value=ch_str(settings.get("level_up_channel_id")))
    embed.add_field(name="💡 Öneri Kanalı", value=ch_str(settings.get("suggestion_channel_id")))
    embed.add_field(name="🎫 Ticket Kategorisi", value=ch_str(settings.get("ticket_category_id")))
    embed.add_field(name="🎫 Ticket Log", value=ch_str(settings.get("ticket_log_channel_id")))
    embed.add_field(name="💬 Karşılama Mesajı", value=settings.get("welcome_message", "Varsayılan") or "Varsayılan", inline=False)
    embed.add_field(name="💬 Veda Mesajı", value=settings.get("goodbye_message", "Varsayılan") or "Varsayılan", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(setup_group)


# ============================================================
#  MODERASYON — PREFIX
# ============================================================

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    if uye == ctx.author:
        return await ctx.send("❌ Kendinizi banlayamazsınız.")
    if uye.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Bu kullanıcıyı banlayacak yetkiniz yok.")
    await uye.ban(reason=f"{ctx.author}: {sebep}")
    embed = discord.Embed(title="🔨 Kullanıcı Banlandı", color=discord.Color.red())
    embed.add_field(name="Kullanıcı", value=f"{uye} ({uye.id})")
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, kullanici: str):
    bans = [entry async for entry in ctx.guild.bans()]
    for entry in bans:
        if str(entry.user) == kullanici or str(entry.user.id) == kullanici:
            await ctx.guild.unban(entry.user)
            embed = discord.Embed(title="✅ Ban Kaldırıldı", color=discord.Color.green())
            embed.add_field(name="Kullanıcı", value=str(entry.user))
            embed.add_field(name="Yetkili", value=ctx.author.mention)
            await ctx.send(embed=embed)
            await log_send(ctx.guild, embed)
            return
    await ctx.send("❌ Kullanıcı banlılar listesinde bulunamadı.")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    if uye.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Bu kullanıcıyı atma yetkiniz yok.")
    await uye.kick(reason=f"{ctx.author}: {sebep}")
    embed = discord.Embed(title="👢 Kullanıcı Atıldı", color=discord.Color.orange())
    embed.add_field(name="Kullanıcı", value=f"{uye} ({uye.id})")
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, uye: discord.Member, dakika: int = 10, *, sebep: str = "Sebep belirtilmedi"):
    await uye.timeout(timedelta(minutes=dakika), reason=sebep)
    embed = discord.Embed(title="🔇 Kullanıcı Susturuldu", color=discord.Color.blue())
    embed.add_field(name="Kullanıcı", value=f"{uye} ({uye.id})")
    embed.add_field(name="Süre", value=f"{dakika} dakika")
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, uye: discord.Member):
    await uye.timeout(None)
    await ctx.send(f"🔊 {uye.mention} kullanıcısının susturması kaldırıldı.")


@bot.command(name="uyar")
@commands.has_permissions(manage_messages=True)
async def uyar(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    count = warn_add(uye.id, ctx.guild.id, ctx.author.id, sebep)
    embed = discord.Embed(title="⚠️ Uyarı Verildi", color=discord.Color.yellow())
    embed.add_field(name="Kullanıcı", value=uye.mention)
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.add_field(name="Toplam Uyarı", value=str(count))
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)
    try:
        await uye.send(f"⚠️ **{ctx.guild.name}** sunucusunda uyarı aldın!\n**Sebep:** {sebep}\n**Toplam uyarı:** {count}")
    except Exception:
        pass


@bot.command(name="uyariler", aliases=["uyarılar"])
@commands.has_permissions(manage_messages=True)
async def uyariler(ctx, uye: discord.Member):
    rows = warn_get(uye.id, ctx.guild.id)
    embed = discord.Embed(title=f"📋 {uye.display_name} — Uyarı Kayıtları", color=discord.Color.yellow())
    if not rows:
        embed.description = "Uyarı kaydı yok."
    else:
        for row in rows[:10]:
            mod = ctx.guild.get_member(int(row["moderator_id"]))
            mod_name = mod.display_name if mod else f"ID:{row['moderator_id']}"
            embed.add_field(
                name=f"#{row['id']} — {time_ago(row['timestamp'])}",
                value=f"**Sebep:** {row['reason']}\n**Yetkili:** {mod_name}",
                inline=False
            )
    await ctx.send(embed=embed)


@bot.command(name="uyarisil")
@commands.has_permissions(manage_messages=True)
async def uyarisil(ctx, warn_id: int):
    if warn_remove(warn_id, ctx.guild.id):
        await ctx.send(f"✅ #{warn_id} numaralı uyarı silindi.")
    else:
        await ctx.send("❌ Bu uyarı bulunamadı.")


@bot.command(name="uyarisifirla")
@commands.has_permissions(administrator=True)
async def uyarisifirla(ctx, uye: discord.Member):
    warn_clear(uye.id, ctx.guild.id)
    await ctx.send(f"✅ {uye.mention} kullanıcısının tüm uyarıları silindi.")


@bot.command(name="temizle", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
async def temizle(ctx, miktar: int = 10, uye: discord.Member = None):
    if uye:
        deleted = await ctx.channel.purge(limit=min(miktar, 100), check=lambda m: m.author == uye)
    else:
        deleted = await ctx.channel.purge(limit=min(miktar, 100) + 1)
    await ctx.send(f"✅ {len(deleted)} mesaj silindi.", delete_after=4)


@bot.command(name="yavaşmod", aliases=["slowmode"])
@commands.has_permissions(manage_channels=True)
async def yavasmod(ctx, saniye: int = 0):
    await ctx.channel.edit(slowmode_delay=saniye)
    if saniye == 0:
        await ctx.send("✅ Yavaş mod kapatıldı.")
    else:
        await ctx.send(f"✅ Yavaş mod **{saniye} saniye** olarak ayarlandı.")


@bot.command(name="kilitle")
@commands.has_permissions(manage_channels=True)
async def kilitle(ctx, kanal: discord.TextChannel = None):
    kanal = kanal or ctx.channel
    overwrite = kanal.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await kanal.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(title="🔒 Kanal Kilitlendi", description=f"{kanal.mention} kilitlendi.", color=discord.Color.red())
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="kilitsiz")
@commands.has_permissions(manage_channels=True)
async def kilitsiz(ctx, kanal: discord.TextChannel = None):
    kanal = kanal or ctx.channel
    overwrite = kanal.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await kanal.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(title="🔓 Kanal Açıldı", description=f"{kanal.mention} kilidi açıldı.", color=discord.Color.green())
    embed.add_field(name="Yetkili", value=ctx.author.mention)
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="sunucu", aliases=["serverinfo"])
async def sunucu_bilgi(ctx):
    guild = ctx.guild
    text_ch = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_ch = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    bots = sum(1 for m in guild.members if m.bot)
    humans = guild.member_count - bots
    embed = discord.Embed(title=f"🏠 {guild.name}", color=discord.Color.blurple())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if guild.banner:
        embed.set_image(url=guild.banner.url)
    embed.add_field(name="👑 Kurucu", value=guild.owner.mention)
    embed.add_field(name="📅 Oluşturulma", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="🆔 ID", value=str(guild.id))
    embed.add_field(name="👥 Üyeler", value=f"**{humans}** insan · **{bots}** bot")
    embed.add_field(name="📝 Kanallar", value=f"**{text_ch}** metin · **{voice_ch}** ses")
    embed.add_field(name="🎭 Rol Sayısı", value=str(len(guild.roles)))
    embed.add_field(name="🔒 Doğrulama", value=str(guild.verification_level).capitalize())
    embed.add_field(name="💎 Boost", value=f"Seviye {guild.premium_tier} ({guild.premium_subscription_count} boost)")
    await ctx.send(embed=embed)


@bot.command(name="kullanici", aliases=["whois", "userinfo"])
async def kullanici_bilgi(ctx, uye: discord.Member = None):
    uye = uye or ctx.author
    embed = discord.Embed(title=f"👤 {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_thumbnail(url=uye.display_avatar.url)
    embed.add_field(name="Kullanıcı Adı", value=str(uye))
    embed.add_field(name="ID", value=str(uye.id))
    embed.add_field(name="Sunucuya Katılma", value=uye.joined_at.strftime("%d/%m/%Y %H:%M"))
    embed.add_field(name="Hesap Oluşturma", value=uye.created_at.strftime("%d/%m/%Y %H:%M"))
    embed.add_field(name="Bot", value="✅ Evet" if uye.bot else "❌ Hayır")
    xp_data = xp_get(uye.id, ctx.guild.id)
    embed.add_field(name="⭐ Seviye", value=f"{xp_data['level']} ({xp_data['xp']:,} XP)")
    warn_count = len(warn_get(uye.id, ctx.guild.id))
    embed.add_field(name="⚠️ Uyarılar", value=str(warn_count))
    roller = [r.mention for r in uye.roles if r.name != "@everyone"]
    embed.add_field(name=f"Roller ({len(roller)})", value=" ".join(roller[:15]) if roller else "Yok", inline=False)
    afk_data = afk_get(uye.id, ctx.guild.id)
    if afk_data:
        embed.add_field(name="💤 AFK", value=f"{afk_data['reason']} ({time_ago(afk_data['timestamp'])})", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx):
    gecikme = round(bot.latency * 1000)
    renk = discord.Color.green() if gecikme < 100 else discord.Color.orange() if gecikme < 200 else discord.Color.red()
    embed = discord.Embed(title="📡 Ping", color=renk)
    embed.add_field(name="Gecikme", value=f"**{gecikme}ms**")
    await ctx.send(embed=embed)


@bot.command(name="botbilgi")
async def botbilgi(ctx):
    embed = discord.Embed(title="🤖 Zerith Security", color=discord.Color.blurple())
    embed.add_field(name="Prefix", value="`!` ve `/`")
    embed.add_field(name="Sunucu Sayısı", value=str(len(bot.guilds)))
    embed.add_field(name="Üye Sayısı", value=str(sum(g.member_count for g in bot.guilds)))
    embed.add_field(name="Gecikme", value=f"{round(bot.latency*1000)}ms")
    embed.add_field(name="Kütüphane", value="discord.py")
    await ctx.send(embed=embed)


@bot.command(name="avatar")
async def avatar(ctx, uye: discord.Member = None):
    uye = uye or ctx.author
    embed = discord.Embed(title=f"🖼️ {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_image(url=uye.display_avatar.url)
    await ctx.send(embed=embed)


# ============================================================
#  !KENDİNİ TANIT — SADECE ADMİN
# ============================================================

@bot.command(name="kendinitanıt", aliases=["kendinitanit", "tanit", "tanitim"])
@commands.has_permissions(administrator=True)
async def kendinitanit(ctx):
    embed = discord.Embed(
        title="🛡️ Zerith Security — Kendini Tanıtıyor",
        description=(
            "Merhaba! Ben **Zerith Security**, bu sunucuyu korumak ve yönetmek için "
            "tasarlanmış çok amaçlı bir Discord botuyum. İşte yapabileceklerim:"
        ),
        color=discord.Color.from_rgb(88, 101, 242)
    )

    embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)

    embed.add_field(
        name="🔒 Güvenlik & Analiz",
        value=(
            "`/scan` — URL/IP/domain zafiyet taraması\n"
            "`/portscan` — Açık port ve ağ güvenlik taraması\n"
            "`/hash` — Hash türü tespiti ve şifre analizi\n"
            "`/log` — Log dosyası güvenlik analizi\n"
            "`/encode` — Base64/Hex encode & decode\n"
            "`/password` — Güçlü şifre üretici\n"
            "`/ipinfo` — IP adresi detaylı sorgu"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ Moderasyon",
        value=(
            "`!ban` `!kick` `!mute` `!unmute` — Üye yönetimi\n"
            "`!uyar` `!uyariler` `!uyarisil` — Uyarı sistemi\n"
            "`!temizle` `!kilitle` `!kilitsiz` — Kanal yönetimi\n"
            "`!küfürfiltre` — Otomatik küfür & reklam filtresi\n"
            "`!not` `!notlar` — Gizli moderatör notları"
        ),
        inline=False
    )

    embed.add_field(
        name="⭐ Seviye & XP",
        value=(
            "Mesaj attıkça XP kazan, seviyeleri atla!\n"
            "`!rank` — Seviye kartın\n"
            "`!leaderboard` — Aktivite sıralaması"
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Ekonomi",
        value=(
            "`!daily` `!çalış` `!suç` — Para kazan\n"
            "`!market` `!satın` `!envanter` — Alışveriş\n"
            "`!yatır` `!çek` `!gönder` — Banka sistemi"
        ),
        inline=False
    )

    embed.add_field(
        name="🎮 Mini Oyunlar & Eğlence",
        value=(
            "`!trivia` `!hangman` `!wordle` `!yaz` — Ödüllü oyunlar\n"
            "`!zar` `!yazıtura` `!8top` `!ship` `!rps` — Eğlence\n"
            "`!hack` `!sayım` — Sahte araçlar"
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ Yönetim & Araçlar",
        value=(
            "`!duyuru` `!anket` `!embed` — Sunucu yönetimi\n"
            "`!çekiliş` — Çekiliş sistemi\n"
            "`!hatırlat` — Hatırlatıcı\n"
            "`!ticket_panel` — Destek ticket sistemi\n"
            "`/setup` — Bot kurulum paneli (Admin)"
        ),
        inline=False
    )

    embed.add_field(
        name="📌 Prefix & Kullanım",
        value=(
            "Tüm komutlar hem `!` (ünlem) hem de `/` (slash) ile çalışır.\n"
            "Yardım için: `!yardım` veya `/yardım`"
        ),
        inline=False
    )

    embed.set_footer(
        text=f"Zerith Security • {len(bot.guilds)} sunucuda aktif • !yardım ile tüm komutları gör",
        icon_url=ctx.bot.user.display_avatar.url
    )
    embed.timestamp = discord.utils.utcnow()

    await ctx.send(embed=embed)


# ============================================================
#  MOD NOTU
# ============================================================

@bot.command(name="not")
@commands.has_permissions(manage_messages=True)
async def mod_not(ctx, uye: discord.Member, *, metin: str):
    note_add(uye.id, ctx.guild.id, ctx.author.id, metin)
    await ctx.send(f"✅ {uye.mention} için not eklendi.")

@bot.command(name="notlar")
@commands.has_permissions(manage_messages=True)
async def mod_notlar(ctx, uye: discord.Member):
    notes = note_get(uye.id, ctx.guild.id)
    embed = discord.Embed(title=f"📝 {uye.display_name} — Mod Notları", color=discord.Color.blurple())
    if not notes:
        embed.description = "Not yok."
    else:
        for n in notes[:10]:
            mod = ctx.guild.get_member(int(n["moderator_id"]))
            mod_name = mod.display_name if mod else f"ID:{n['moderator_id']}"
            embed.add_field(
                name=f"#{n['id']} — {time_ago(n['timestamp'])} ({mod_name})",
                value=n["note"],
                inline=False
            )
    await ctx.send(embed=embed)


# ============================================================
#  AFK KOMUTLARI
# ============================================================

@bot.command(name="afk")
async def afk_cmd(ctx, *, sebep: str = "AFK"):
    afk_set(ctx.author.id, ctx.guild.id, sebep)
    embed = discord.Embed(title="💤 AFK Modu", description=f"{ctx.author.mention} AFK'ya geçti.", color=discord.Color.greyple())
    embed.add_field(name="Sebep", value=sebep)
    embed.set_footer(text="Mesaj attığında otomatik kapanır.")
    await ctx.send(embed=embed)


# ============================================================
#  XP / SEVİYE
# ============================================================

@bot.command(name="rank")
async def rank(ctx, uye: discord.Member = None):
    uye = uye or ctx.author
    veri = xp_get(uye.id, ctx.guild.id)
    xp = veri["xp"]
    level = veri["level"]
    sira = xp_rank(uye.id, ctx.guild.id)
    sonraki_xp = None
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if lvl > level:
            sonraki_xp = threshold
            break
    embed = discord.Embed(title=f"📊 {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_thumbnail(url=uye.display_avatar.url)
    embed.add_field(name="⭐ Seviye", value=str(level))
    embed.add_field(name="✨ XP", value=f"{xp:,}")
    embed.add_field(name="🏆 Sıralama", value=f"#{sira}")
    if sonraki_xp:
        ilerleme = min(int((xp / sonraki_xp) * 10), 10)
        bar = "▓" * ilerleme + "░" * (10 - ilerleme)
        embed.add_field(name="Sonraki Seviye", value=f"`{bar}` {xp:,}/{sonraki_xp:,}", inline=False)
    else:
        embed.add_field(name="🏆", value="Maksimum seviye!", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "siralama"])
async def leaderboard(ctx):
    rows = xp_leaderboard(ctx.guild.id, 10)
    embed = discord.Embed(title="🏆 Aktivite Sıralaması", color=discord.Color.gold())
    madalyalar = ["🥇", "🥈", "🥉"]
    satirlar = []
    for i, (uid, xp, level) in enumerate(rows, 1):
        uye = ctx.guild.get_member(int(uid))
        isim = uye.display_name if uye else f"Kullanıcı ({uid})"
        madalya = madalyalar[i-1] if i <= 3 else f"**{i}.**"
        satirlar.append(f"{madalya} {isim} — {xp:,} XP | Lv.{level}")
    embed.description = "\n".join(satirlar) if satirlar else "Henüz kayıt yok."
    await ctx.send(embed=embed)


# ============================================================
#  EKONOMİ
# ============================================================

@bot.command(name="para", aliases=["coin", "bakiye", "wallet"])
async def para(ctx, uye: discord.Member = None):
    uye = uye or ctx.author
    veri = eco_get(uye.id, ctx.guild.id)
    embed = discord.Embed(title=f"💰 {uye.display_name} — Bakiye", color=discord.Color.gold())
    embed.add_field(name="👛 Cüzdan", value=f"{veri['coins']:,} 🪙")
    embed.add_field(name="🏦 Banka", value=f"{veri['bank']:,} 🪙")
    embed.add_field(name="💎 Toplam", value=f"{veri['coins']+veri['bank']:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="daily")
async def daily(ctx):
    veri = eco_get(ctx.author.id, ctx.guild.id)
    kalan = veri["last_daily"] + 86400 - time.time()
    if kalan > 0:
        await ctx.send(f"⏳ Günlük ödülünü zaten aldın! **{format_time(kalan)}** bekle.")
        return
    streak = veri["streak"] + 1
    odul = random.randint(DAILY_MIN, DAILY_MAX)
    bonus = 0
    if streak >= 7:
        bonus = int(odul * 0.5)
    elif streak >= 3:
        bonus = int(odul * 0.2)
    toplam = odul + bonus
    eco_add_coins(ctx.author.id, ctx.guild.id, toplam)
    eco_update(ctx.author.id, ctx.guild.id, last_daily=time.time(), streak=streak)
    embed = discord.Embed(title="🎁 Günlük Ödül", color=discord.Color.gold())
    embed.add_field(name="💰 Kazanılan", value=f"**{odul} 🪙**")
    if bonus:
        embed.add_field(name=f"🔥 {streak} Gün Serisi Bonusu", value=f"**+{bonus} 🪙**")
    embed.add_field(name="📅 Seri", value=f"**{streak}** gün")
    embed.add_field(name="💼 Bakiye", value=f"{eco_get(ctx.author.id, ctx.guild.id)['coins']:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="çalış", aliases=["calis", "work"])
@commands.cooldown(1, 3600, commands.BucketType.user)
async def calis(ctx):
    inv = inv_get(ctx.author.id, ctx.guild.id)
    multiplier = 1.5 if "laptop" in inv else 1.0
    kazanilan = int(random.randint(WORK_MIN, WORK_MAX) * multiplier)
    mesaj = random.choice(WORK_MESSAGES)
    eco_add_coins(ctx.author.id, ctx.guild.id, kazanilan)
    embed = discord.Embed(title="💼 Çalışma", color=discord.Color.green())
    embed.description = f"**{mesaj}** ve **{kazanilan} 🪙** kazandın!"
    if multiplier > 1:
        embed.set_footer(text="💻 Laptop bonusu aktif!")
    await ctx.send(embed=embed)

@calis.error
async def calis_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Çalışmak için **{format_time(error.retry_after)}** bekle.", delete_after=8)


@bot.command(name="suç", aliases=["suc", "crime"])
@commands.cooldown(1, 7200, commands.BucketType.user)
async def suc(ctx):
    inv = inv_get(ctx.author.id, ctx.guild.id)
    fail_chance = CRIME_FAIL_CHANCE
    if "lucky_charm" in inv:
        fail_chance = 0.15
    if "shield" in inv:
        fail_chance = max(0, fail_chance - 0.1)
    if random.random() < fail_chance:
        ceza = random.randint(50, 200)
        eco_add_coins(ctx.author.id, ctx.guild.id, -ceza)
        embed = discord.Embed(title="🚔 Yakalandın!", color=discord.Color.red())
        embed.description = f"**{random.choice(CRIME_FAIL)}!**\n**{ceza} 🪙** ceza ödedin."
    else:
        kazanilan = random.randint(CRIME_MIN, CRIME_MAX)
        eco_add_coins(ctx.author.id, ctx.guild.id, kazanilan)
        embed = discord.Embed(title="💰 Suç Başarılı!", color=discord.Color.dark_green())
        embed.description = f"**{random.choice(CRIME_SUCCESS)}!**\n**{kazanilan} 🪙** kazandın."
    await ctx.send(embed=embed)

@suc.error
async def suc_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Suç için **{format_time(error.retry_after)}** bekle.", delete_after=8)


@bot.command(name="yatır", aliases=["deposit", "yatir"])
async def yatir(ctx, miktar: str):
    veri = eco_get(ctx.author.id, ctx.guild.id)
    if miktar.lower() in ("hepsi", "all"):
        miktar = veri["coins"]
    else:
        try:
            miktar = int(miktar)
        except ValueError:
            return await ctx.send("❌ Geçersiz miktar.")
    if miktar <= 0:
        return await ctx.send("❌ 0'dan büyük bir miktar gir.")
    if veri["coins"] < miktar:
        return await ctx.send(f"❌ Yeterli bakiye yok! Cüzdanda: **{veri['coins']:,} 🪙**")
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO economy (user_id, guild_id, coins, bank) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET coins=coins-?, bank=bank+?",
              (str(ctx.author.id), str(ctx.guild.id), -miktar, miktar, miktar, miktar))
    conn.commit()
    conn.close()
    veri2 = eco_get(ctx.author.id, ctx.guild.id)
    embed = discord.Embed(title="🏦 Para Yatırıldı", color=discord.Color.green())
    embed.add_field(name="Yatırılan", value=f"{miktar:,} 🪙")
    embed.add_field(name="👛 Cüzdan", value=f"{veri2['coins']:,} 🪙")
    embed.add_field(name="🏦 Banka", value=f"{veri2['bank']:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="çek", aliases=["withdraw", "cek"])
async def cek(ctx, miktar: str):
    veri = eco_get(ctx.author.id, ctx.guild.id)
    if miktar.lower() in ("hepsi", "all"):
        miktar = veri["bank"]
    else:
        try:
            miktar = int(miktar)
        except ValueError:
            return await ctx.send("❌ Geçersiz miktar.")
    if miktar <= 0:
        return await ctx.send("❌ 0'dan büyük bir miktar gir.")
    if veri["bank"] < miktar:
        return await ctx.send(f"❌ Bankada yeterli para yok! Bankada: **{veri['bank']:,} 🪙**")
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO economy (user_id, guild_id) VALUES (?,?) ON CONFLICT DO NOTHING", (str(ctx.author.id), str(ctx.guild.id)))
    c.execute("UPDATE economy SET coins=coins+?, bank=bank-? WHERE user_id=? AND guild_id=?",
              (miktar, miktar, str(ctx.author.id), str(ctx.guild.id)))
    conn.commit()
    conn.close()
    veri2 = eco_get(ctx.author.id, ctx.guild.id)
    embed = discord.Embed(title="🏦 Para Çekildi", color=discord.Color.blue())
    embed.add_field(name="Çekilen", value=f"{miktar:,} 🪙")
    embed.add_field(name="👛 Cüzdan", value=f"{veri2['coins']:,} 🪙")
    embed.add_field(name="🏦 Banka", value=f"{veri2['bank']:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="gönder", aliases=["transfer", "gonder"])
async def gonder(ctx, hedef: discord.Member, miktar: int):
    if hedef.bot or hedef == ctx.author:
        return await ctx.send("❌ Geçersiz hedef.")
    if miktar <= 0:
        return await ctx.send("❌ 0'dan büyük bir miktar gir.")
    veri = eco_get(ctx.author.id, ctx.guild.id)
    if veri["coins"] < miktar:
        return await ctx.send(f"❌ Yeterli bakiye yok!")
    vergi = int(miktar * 0.05)
    net = miktar - vergi
    eco_add_coins(ctx.author.id, ctx.guild.id, -miktar)
    eco_add_coins(hedef.id, ctx.guild.id, net)
    embed = discord.Embed(title="💸 Para Transferi", color=discord.Color.green())
    embed.add_field(name="Gönderen", value=ctx.author.mention)
    embed.add_field(name="Alan", value=hedef.mention)
    embed.add_field(name="Gönderilen", value=f"{miktar:,} 🪙")
    embed.add_field(name="Vergi (%5)", value=f"{vergi:,} 🪙")
    embed.add_field(name="Alınan", value=f"{net:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="market")
async def market(ctx):
    embed = discord.Embed(title="🏪 Market", description="Satın almak için `!satın <ürün_id>` kullan.", color=discord.Color.dark_blue())
    for item_id, item in MARKET_ITEMS.items():
        embed.add_field(
            name=f"{item['emoji']} {item['name']} — {item['price']:,} 🪙",
            value=f"`{item_id}` — {item['description']}\n💰 Satış: {item['sell_price']:,} 🪙",
            inline=True
        )
    await ctx.send(embed=embed)


@bot.command(name="satın", aliases=["buy", "satin"])
async def satin(ctx, *, urun_id: str):
    urun_id = urun_id.lower().strip()
    item = MARKET_ITEMS.get(urun_id)
    if not item:
        return await ctx.send("❌ Böyle bir ürün yok. `!market` ile listeyi gör.")
    veri = eco_get(ctx.author.id, ctx.guild.id)
    if veri["coins"] < item["price"]:
        return await ctx.send(f"❌ Yetersiz bakiye! Gerekli: **{item['price']:,} 🪙**")
    eco_add_coins(ctx.author.id, ctx.guild.id, -item["price"])
    inv_add(ctx.author.id, ctx.guild.id, urun_id)
    embed = discord.Embed(title="✅ Satın Alındı", description=f"{item['emoji']} **{item['name']}**", color=discord.Color.green())
    embed.add_field(name="Ödenen", value=f"{item['price']:,} 🪙")
    embed.add_field(name="Kalan", value=f"{eco_get(ctx.author.id, ctx.guild.id)['coins']:,} 🪙")
    await ctx.send(embed=embed)


@bot.command(name="sat", aliases=["sell"])
async def sat(ctx, *, urun_id: str):
    urun_id = urun_id.lower().strip()
    item = MARKET_ITEMS.get(urun_id)
    if not item:
        return await ctx.send("❌ Böyle bir ürün yok.")
    if not inv_remove(ctx.author.id, ctx.guild.id, urun_id):
        return await ctx.send(f"❌ Envanterinde **{item['name']}** yok.")
    eco_add_coins(ctx.author.id, ctx.guild.id, item["sell_price"])
    await ctx.send(f"✅ {item['emoji']} **{item['name']}** **{item['sell_price']:,} 🪙** karşılığında satıldı.")


@bot.command(name="envanter", aliases=["inv", "inventory"])
async def envanter(ctx, uye: discord.Member = None):
    uye = uye or ctx.author
    inv = inv_get(uye.id, ctx.guild.id)
    embed = discord.Embed(title=f"🎒 {uye.display_name} — Envanter", color=discord.Color.dark_gray())
    if not inv:
        embed.description = "Envanter boş."
    else:
        satirlar = []
        for item_id, qty in inv.items():
            item = MARKET_ITEMS.get(item_id)
            if item:
                satirlar.append(f"{item['emoji']} **{item['name']}** × {qty}")
            else:
                satirlar.append(f"❓ {item_id} × {qty}")
        embed.description = "\n".join(satirlar)
    await ctx.send(embed=embed)


@bot.command(name="zenginler", aliases=["econlb"])
async def zenginler(ctx):
    rows = eco_leaderboard(ctx.guild.id, 10)
    embed = discord.Embed(title="💰 En Zenginler", color=discord.Color.gold())
    madalyalar = ["🥇", "🥈", "🥉"]
    satirlar = []
    for i, (uid, total) in enumerate(rows, 1):
        uye = ctx.guild.get_member(int(uid))
        isim = uye.display_name if uye else f"Kullanıcı ({uid})"
        madalya = madalyalar[i-1] if i <= 3 else f"**{i}.**"
        satirlar.append(f"{madalya} {isim} — {total:,} 🪙")
    embed.description = "\n".join(satirlar) if satirlar else "Henüz kayıt yok."
    await ctx.send(embed=embed)


# ============================================================
#  ÇEKİLİŞ
# ============================================================

@bot.command(name="çekiliş", aliases=["giveaway", "cekilisac"])
@commands.has_permissions(manage_guild=True)
async def cekilisac(ctx, sure: str, kazanan: int, *, odul: str):
    match = re.match(r"(\d+)([smhd])", sure)
    if not match:
        return await ctx.send("❌ Geçersiz süre! Örnek: `30m`, `2h`, `1d`")
    sayi, birim = int(match.group(1)), match.group(2)
    seconds = sayi * {"s": 1, "m": 60, "h": 3600, "d": 86400}[birim]
    ends_at = time.time() + seconds
    embed = discord.Embed(title="🎉 ÇEKİLİŞ", description=f"**{odul}**\n\nKatılmak için 🎉 tepkisini ekle!", color=discord.Color.gold())
    ends_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)
    embed.add_field(name="⏰ Bitiş", value=f"<t:{int(ends_at)}:R>")
    embed.add_field(name="🏆 Kazanan Sayısı", value=str(kazanan))
    embed.add_field(name="🎟️ Düzenleyen", value=ctx.author.mention)
    embed.set_footer(text="Zerith Security Çekiliş Sistemi")
    embed.timestamp = ends_dt
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winner_count, ends_at, host_id) VALUES (?,?,?,?,?,?,?)",
              (str(ctx.guild.id), str(ctx.channel.id), str(msg.id), odul, kazanan, ends_at, str(ctx.author.id)))
    conn.commit()
    conn.close()
    await ctx.message.delete()


@bot.command(name="çekilişsil", aliases=["giveawaycancel"])
@commands.has_permissions(manage_guild=True)
async def cekilissil(ctx, mesaj_id: int):
    conn = db_connect()
    c = conn.cursor()
    c.execute("UPDATE giveaways SET ended=1 WHERE message_id=? AND guild_id=?", (str(mesaj_id), str(ctx.guild.id)))
    conn.commit()
    conn.close()
    await ctx.send("✅ Çekiliş iptal edildi.")


# ============================================================
#  HATIRLATICI
# ============================================================

@bot.command(name="hatırlat", aliases=["remind", "hatirla"])
async def hatirla(ctx, sure: str, *, mesaj: str):
    match = re.match(r"(\d+)([smhd])", sure)
    if not match:
        return await ctx.send("❌ Geçersiz süre! Örnek: `30m`, `2h`, `1d`")
    sayi, birim = int(match.group(1)), match.group(2)
    seconds = sayi * {"s": 1, "m": 60, "h": 3600, "d": 86400}[birim]
    remind_at = time.time() + seconds
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO reminders (user_id, channel_id, guild_id, message, remind_at) VALUES (?,?,?,?,?)",
              (str(ctx.author.id), str(ctx.channel.id), str(ctx.guild.id), mesaj, remind_at))
    rid = c.lastrowid
    conn.commit()
    conn.close()
    embed = discord.Embed(title="⏰ Hatırlatıcı Ayarlandı", color=discord.Color.blue())
    embed.add_field(name="Mesaj", value=mesaj)
    embed.add_field(name="Süre", value=f"<t:{int(remind_at)}:R>")
    embed.add_field(name="ID", value=f"#{rid}")
    await ctx.send(embed=embed)


@bot.command(name="hatırlatmalar", aliases=["reminders"])
async def hatirlatmalar(ctx):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE user_id=? AND done=0 ORDER BY remind_at ASC", (str(ctx.author.id),))
    rows = c.fetchall()
    conn.close()
    embed = discord.Embed(title="⏰ Hatırlatıcılarım", color=discord.Color.blue())
    if not rows:
        embed.description = "Aktif hatırlatıcı yok."
    else:
        for row in rows[:10]:
            embed.add_field(
                name=f"#{row['id']}",
                value=f"**{row['message'][:100]}**\n<t:{int(row['remind_at'])}:R>",
                inline=False
            )
    await ctx.send(embed=embed)


# ============================================================
#  ÖNERİ SİSTEMİ
# ============================================================

@bot.command(name="öneri", aliases=["suggest", "oneri"])
async def oneri(ctx, *, metin: str):
    settings = get_settings(ctx.guild.id)
    suggest_id = settings.get("suggestion_channel_id")
    if not suggest_id:
        return await ctx.send("❌ Öneri kanalı ayarlanmamış. Admin `/setup suggestion` kullanmalı.")
    ch = ctx.guild.get_channel(int(suggest_id))
    if not ch:
        return await ctx.send("❌ Öneri kanalı bulunamadı.")
    embed = discord.Embed(title="💡 Yeni Öneri", description=metin, color=discord.Color.blurple())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"ID: {ctx.author.id}")
    embed.timestamp = discord.utils.utcnow()
    msg = await ch.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    try:
        await ctx.message.delete()
        await ctx.author.send(f"✅ Önerin **{ctx.guild.name}** sunucusuna iletildi!")
    except Exception:
        await ctx.send("✅ Önerin iletildi!", delete_after=5)


# ============================================================
#  TİCKET SİSTEMİ
# ============================================================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ticket Aç", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = get_settings(interaction.guild.id)
        cat_id = settings.get("ticket_category_id")
        if not cat_id:
            return await interaction.response.send_message("❌ Ticket kategorisi ayarlanmamış.", ephemeral=True)
        category = interaction.guild.get_channel(int(cat_id))
        if not category:
            return await interaction.response.send_message("❌ Kategori bulunamadı.", ephemeral=True)
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
                  (str(interaction.guild.id), str(interaction.user.id)))
        existing = c.fetchone()
        conn.close()
        if existing:
            ch = interaction.guild.get_channel(int(existing["channel_id"]))
            if ch:
                return await interaction.response.send_message(f"❌ Zaten açık bir ticket'ın var: {ch.mention}", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        mod_role_id = settings.get("mod_role_id")
        if mod_role_id:
            mod_role = interaction.guild.get_role(int(mod_role_id))
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        ticket_ch = await category.create_text_channel(
            f"ticket-{interaction.user.name}",
            overwrites=overwrites,
            topic=f"Ticket: {interaction.user.id}"
        )
        conn = db_connect()
        c = conn.cursor()
        c.execute("INSERT INTO tickets (guild_id, channel_id, user_id, created_at) VALUES (?,?,?,?)",
                  (str(interaction.guild.id), str(ticket_ch.id), str(interaction.user.id), time.time()))
        tid = c.lastrowid
        conn.commit()
        conn.close()
        embed = discord.Embed(
            title=f"🎫 Ticket #{tid}",
            description=f"Merhaba {interaction.user.mention}!\nSorununu veya isteğini yaz, ekibimiz en kısa sürede yardımcı olacak.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Ticket'ı kapatmak için aşağıdaki butonu kullan.")
        await ticket_ch.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket'ın açıldı: {ticket_ch.mention}", ephemeral=True)
        log_id = settings.get("ticket_log_channel_id")
        if log_id:
            log_ch = interaction.guild.get_channel(int(log_id))
            if log_ch:
                log_embed = discord.Embed(title="🎫 Ticket Açıldı", color=discord.Color.green())
                log_embed.add_field(name="Kullanıcı", value=f"{interaction.user} ({interaction.user.id})")
                log_embed.add_field(name="Kanal", value=ticket_ch.mention)
                log_embed.timestamp = discord.utils.utcnow()
                await log_ch.send(embed=log_embed)


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Ticket'ı Kapat", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db_connect()
        c = conn.cursor()
        c.execute("UPDATE tickets SET status='closed' WHERE channel_id=? AND guild_id=?",
                  (str(interaction.channel.id), str(interaction.guild.id)))
        conn.commit()
        conn.close()
        embed = discord.Embed(title="🔒 Ticket Kapatıldı", description=f"{interaction.user.mention} tarafından kapatıldı. Kanal 5 saniye içinde silinecek.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket kapatıldı")


@bot.command(name="ticket_panel")
@commands.has_permissions(administrator=True)
async def ticket_panel(ctx):
    embed = discord.Embed(
        title="🎫 Destek Ticket Sistemi",
        description="Yardım almak için aşağıdaki butona tıklayarak ticket açabilirsin.\nEkibimiz en kısa sürede yardımcı olacak.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Zerith Security | Destek Sistemi")
    await ctx.send(embed=embed, view=TicketView())
    await ctx.message.delete()


# ============================================================
#  EĞLENCE
# ============================================================

@bot.command(name="zar")
async def zar(ctx, yuz: int = 6):
    if yuz < 2 or yuz > 100:
        return await ctx.send("❌ 2-100 arası bir sayı gir.")
    sonuc = random.randint(1, yuz)
    embed = discord.Embed(title="🎲 Zar", color=discord.Color.blurple())
    embed.description = f"**1d{yuz}** → **{sonuc}**"
    await ctx.send(embed=embed)


@bot.command(name="yazıtura", aliases=["flip", "yazi"])
async def yazıtura(ctx):
    sonuc = random.choice(["🪙 Yazı", "⭕ Tura"])
    await ctx.send(f"**{sonuc}**!")


@bot.command(name="8top", aliases=["8ball"])
async def sekiz_top(ctx, *, soru: str):
    cevaplar = [
        "✅ Kesinlikle evet!", "✅ Evet.", "✅ Muhtemelen.",
        "🤔 Belirsiz.", "🤔 Şu an söyleyemem.", "🤔 Biraz bekle.",
        "❌ Hayır.", "❌ Muhtemelen hayır.", "⛔ Kesinlikle hayır."
    ]
    embed = discord.Embed(title="🎱 Sihirli 8 Top", color=discord.Color.dark_purple())
    embed.add_field(name="Soru", value=soru, inline=False)
    embed.add_field(name="Cevap", value=random.choice(cevaplar), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="ship")
async def ship(ctx, kisi1: discord.Member, kisi2: discord.Member):
    random.seed(kisi1.id + kisi2.id)
    oran = random.randint(0, 100)
    random.seed()
    dolgu = int(oran / 10)
    renk = discord.Color.red() if oran >= 70 else discord.Color.orange() if oran >= 40 else discord.Color.dark_gray()
    embed = discord.Embed(title="💘 Uyumluluk Testi", color=renk)
    embed.add_field(name="Çift", value=f"{kisi1.mention} ❤️ {kisi2.mention}", inline=False)
    bar = "❤️" * dolgu + "🖤" * (10 - dolgu)
    embed.add_field(name=f"Uyumluluk: **%{oran}**", value=bar, inline=False)
    await ctx.send(embed=embed)


@bot.command(name="hack")
async def hack(ctx, hedef: discord.Member):
    adimlar = [
        "🔍 Hedef tespit edildi...",
        "🔓 Güvenlik duvarı bypass ediliyor...",
        "💉 SQL enjeksiyonu deneniyor...",
        "📡 Bağlantı kuruldu!",
        "✅ Erişim sağlandı."
    ]
    mesaj = await ctx.send("💻 Sistem başlatılıyor...")
    for adim in adimlar:
        await asyncio.sleep(1.0)
        await mesaj.edit(content=adim)
    ip = ".".join(str(random.randint(10, 254)) for _ in range(4))
    embed = discord.Embed(title=f"💻 {hedef.display_name} Hacklendi!", color=discord.Color.dark_green())
    embed.add_field(name="🌐 IP", value=f"`{ip}`")
    embed.add_field(name="📍 Konum", value=f"`{random.choice(['İstanbul, TR', 'Ankara, TR', 'İzmir, TR', 'Antalya, TR'])}`")
    embed.add_field(name="📱 Cihaz", value=f"`{random.choice(['iPhone 15', 'Samsung S24', 'MacBook Pro', 'Windows PC'])}`")
    embed.set_footer(text="⚠️ Bu tamamen sahtedir, eğlencelik!")
    await mesaj.edit(content="", embed=embed)


@bot.command(name="rps", aliases=["taştiraağaç"])
async def rps(ctx, secim: str):
    emojis = {"taş": "🪨", "kağıt": "📄", "makas": "✂️"}
    kazanir = {"taş": "makas", "kağıt": "taş", "makas": "kağıt"}
    secim = secim.lower()
    if secim not in emojis:
        return await ctx.send("❌ `taş`, `kağıt` veya `makas` seç!")
    bot_secim = random.choice(list(emojis.keys()))
    embed = discord.Embed(title="🎮 Taş Kağıt Makas", color=discord.Color.blurple())
    embed.add_field(name="Sen", value=f"{emojis[secim]} {secim.capitalize()}")
    embed.add_field(name="Bot", value=f"{emojis[bot_secim]} {bot_secim.capitalize()}")
    if secim == bot_secim:
        embed.add_field(name="Sonuç", value="🤝 **Berabere!**", inline=False)
        embed.color = discord.Color.yellow()
    elif kazanir[secim] == bot_secim:
        embed.add_field(name="Sonuç", value="🎉 **Kazandın!**", inline=False)
        embed.color = discord.Color.green()
    else:
        embed.add_field(name="Sonuç", value="😔 **Kaybettin!**", inline=False)
        embed.color = discord.Color.red()
    await ctx.send(embed=embed)


@bot.command(name="sayım", aliases=["sayim", "countdown"])
async def sayim(ctx, baslangic: int = 10):
    if baslangic < 1 or baslangic > 30:
        return await ctx.send("❌ 1-30 arası bir sayı gir.")
    msg = await ctx.send(f"**{baslangic}**...")
    for i in range(baslangic - 1, -1, -1):
        await asyncio.sleep(1)
        if i == 0:
            await msg.edit(content="💥 **0! — PATLADI!**")
        else:
            await msg.edit(content=f"**{i}**...")


# ============================================================
#  DUYURU & YÖNETİM
# ============================================================

@bot.command(name="duyuru")
@commands.has_permissions(manage_guild=True)
async def duyuru(ctx, kanal: discord.TextChannel, *, metin: str):
    metin = metin.replace("\\n", "\n")
    embed = discord.Embed(title="📣 Duyuru", description=metin, color=discord.Color.red())
    embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"Gönderen: {ctx.author.display_name}")
    embed.timestamp = discord.utils.utcnow()
    await kanal.send("@everyone", embed=embed)
    await ctx.send(f"✅ Duyuru {kanal.mention} kanalına gönderildi.", delete_after=5)
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="embed")
@commands.has_permissions(manage_messages=True)
async def embed_gonder(ctx, kanal: discord.TextChannel, baslik: str, renk: str, *, icerik: str):
    renkler = {
        "kirmizi": discord.Color.red(), "yesil": discord.Color.green(),
        "mavi": discord.Color.blue(), "sari": discord.Color.yellow(),
        "mor": discord.Color.purple(), "altin": discord.Color.gold(),
        "turuncu": discord.Color.orange()
    }
    icerik = icerik.replace("\\n", "\n")
    embed = discord.Embed(title=baslik, description=icerik, color=renkler.get(renk.lower(), discord.Color.blurple()))
    embed.set_footer(text=f"{ctx.guild.name}")
    embed.timestamp = discord.utils.utcnow()
    await kanal.send(embed=embed)
    await ctx.send(f"✅ Embed {kanal.mention} kanalına gönderildi.", delete_after=5)


@bot.command(name="yetkili")
async def yetkili(ctx, *, sebep: str):
    settings = get_settings(ctx.guild.id)
    mod_role_id = settings.get("mod_role_id")
    embed = discord.Embed(title="🚨 ACİL YETKİLİ ÇAĞRISI", color=discord.Color.red())
    embed.add_field(name="Çağıran", value=f"{ctx.author.mention} ({ctx.author})", inline=False)
    embed.add_field(name="Kanal", value=ctx.channel.mention, inline=False)
    embed.add_field(name="Durum", value=sebep, inline=False)
    embed.timestamp = discord.utils.utcnow()
    ping = ctx.guild.get_role(int(mod_role_id)).mention if mod_role_id and ctx.guild.get_role(int(mod_role_id)) else "⚠️ Yetkililer"
    await ctx.send(ping, embed=embed)


@bot.command(name="anket")
@commands.has_permissions(manage_messages=True)
async def anket(ctx, *, soru: str):
    embed = discord.Embed(title="📊 Anket", description=f"**{soru}**", color=discord.Color.blurple())
    embed.set_footer(text=f"Başlatan: {ctx.author.display_name}")
    embed.timestamp = discord.utils.utcnow()
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")


# ============================================================
#  KÜFÜR FİLTRE KOMUTLARI
# ============================================================

@bot.command(name="küfürfiltre", aliases=["kufurfiltre", "swearfilter"])
@commands.has_permissions(administrator=True)
async def kufur_filtre(ctx, durum: str):
    if durum.lower() in ("kapat", "off"):
        KUFUR_FILTRE_KAPALI.add(ctx.guild.id)
        embed = discord.Embed(title="🔓 Küfür Filtresi Kapatıldı", description="Artık küfür engellenmeyecek.", color=discord.Color.red())
    elif durum.lower() in ("aç", "ac", "on"):
        KUFUR_FILTRE_KAPALI.discard(ctx.guild.id)
        embed = discord.Embed(title="🔒 Küfür Filtresi Açıldı", description="Küfürler tekrar engellenecek.", color=discord.Color.green())
    else:
        return await ctx.send("❌ Kullanım: `!küfürfiltre aç` veya `!küfürfiltre kapat`")
    await ctx.send(embed=embed)
    await log_send(ctx.guild, embed)


@bot.command(name="filtredurum", aliases=["filterdurum", "filtrestatus"])
@commands.has_permissions(manage_messages=True)
async def filtre_durum(ctx):
    kapali = ctx.guild.id in KUFUR_FILTRE_KAPALI
    embed = discord.Embed(
        title="🔍 Küfür Filtresi Durumu",
        description="🔒 **Aktif** — Küfürler engelleniyor" if not kapali else "🔓 **Kapalı** — Küfürler serbest",
        color=discord.Color.green() if not kapali else discord.Color.red()
    )
    await ctx.send(embed=embed)


# ============================================================
#  GÜVENLİK — YARDIMCI FONKSİYONLAR
# ============================================================

def analyze_hash(value: str) -> dict:
    value = value.strip()
    length_map = {32: ["MD5", "NTLM"], 40: ["SHA-1"], 56: ["SHA-224"],
                  64: ["SHA-256"], 96: ["SHA-384"], 128: ["SHA-512"]}
    security_ratings = {
        "MD5":     ("⛔ Kırılabilir",      "MD5 çakışma saldırılarına karşı savunmasız. Parola için KESİNLİKLE kullanmayın."),
        "NTLM":    ("⛔ Tehlikeli",         "NTLM pass-the-hash saldırılarına açık. Modern sistemlerde kullanmayın."),
        "SHA-1":   ("⚠️ Zayıf",            "SHA-1 çakışma saldırıları mümkün. Güvenlik için yetersiz."),
        "SHA-224": ("🟡 Orta",             "SHA-2 ailesinden, kabul edilebilir ama SHA-256+ tercih edilmeli."),
        "SHA-256": ("✅ Güvenli",           "Şu an için güvenli kabul edilen standart hash."),
        "SHA-384": ("✅ Güvenli",           "SHA-2 ailesi, yüksek güvenlik."),
        "SHA-512": ("✅ Çok Güvenli",       "Yüksek güvenlikli hash, kritik veriler için uygun."),
        "bcrypt":  ("✅ Parola İçin İdeal", "Tuzlama (salt) içerir, parola hashleme için en iyi seçim."),
    }
    if value.startswith("$2"):
        detected = ["bcrypt"]
    else:
        detected = length_map.get(len(value), [])
    is_hex = bool(re.match(r'^[a-fA-F0-9]+$', value))
    own_hashes = {}
    if not is_hex and len(value) < 100:
        encoded = value.encode('utf-8')
        own_hashes = {
            "MD5":     hashlib.md5(encoded).hexdigest(),
            "SHA-1":   hashlib.sha1(encoded).hexdigest(),
            "SHA-256": hashlib.sha256(encoded).hexdigest(),
            "SHA-512": hashlib.sha512(encoded).hexdigest(),
        }
    return {
        "value": value, "length": len(value),
        "detected_types": detected, "security_ratings": security_ratings,
        "own_hashes": own_hashes, "is_hex": is_hex,
    }


def analyze_log_content(content: str) -> dict:
    lines = content.split('\n')
    threats, warnings = [], []
    stats = {
        "total_lines": len(lines), "threat_count": 0, "warning_count": 0,
        "unique_ips": set(), "failed_logins": 0, "sql_attempts": 0,
        "xss_attempts": 0, "brute_force_ips": {},
    }
    sql_patterns = [
        r"('|\")(.*?)(union|select|insert|update|delete|drop|create|alter)(.*?)('|\")",
        r"\b(union|select|insert|update|delete|drop|exec|execute)\b.*\b(from|into|table|where)\b",
        r"(--|\#|\/\*.*\*\/)", r"\b(or|and)\b\s+\d+\s*=\s*\d+",
        r"sleep\s*\(\s*\d+\s*\)", r"benchmark\s*\(",
    ]
    xss_patterns = [
        r"<script[^>]*>", r"javascript:", r"on(load|click|error|mouseover|focus)\s*=",
        r"<iframe[^>]*>", r"eval\s*\(", r"document\.(cookie|location|write)",
    ]
    bruteforce_patterns = [
        r"failed\s+(password|login|auth)", r"authentication\s+failure",
        r"invalid\s+user", r"failed\s+attempt", r"login\s+failed",
        r"access\s+denied", r"unauthorized",
    ]
    path_traversal = [r"\.\./", r"\.\.\\", r"%2e%2e", r"etc/passwd", r"etc/shadow", r"win/system32"]
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        line_lower = line.lower()
        ips = ip_pattern.findall(line)
        for ip in ips:
            stats["unique_ips"].add(ip)
        for pattern in sql_patterns:
            if re.search(pattern, line_lower):
                stats["sql_attempts"] += 1
                threats.append({"line": i, "type": "🔴 SQL Injection", "content": line.strip()[:150], "ips": ips})
                break
        for pattern in xss_patterns:
            if re.search(pattern, line_lower):
                stats["xss_attempts"] += 1
                threats.append({"line": i, "type": "🔴 XSS Saldırısı", "content": line.strip()[:150], "ips": ips})
                break
        for pattern in path_traversal:
            if re.search(pattern, line_lower):
                threats.append({"line": i, "type": "🔴 Path Traversal", "content": line.strip()[:150], "ips": ips})
                break
        for pattern in bruteforce_patterns:
            if re.search(pattern, line_lower):
                stats["failed_logins"] += 1
                for ip in ips:
                    stats["brute_force_ips"][ip] = stats["brute_force_ips"].get(ip, 0) + 1
                warnings.append({"line": i, "type": "⚠️ Başarısız Giriş", "content": line.strip()[:150], "ips": ips})
                break
    for ip, count in stats["brute_force_ips"].items():
        if count >= 5:
            threats.append({"line": 0, "type": f"🔴 Brute Force ({count} deneme)",
                            "content": f"IP: {ip} — {count} başarısız giriş denemesi", "ips": [ip]})
    stats["threat_count"] = len(threats)
    stats["warning_count"] = len(warnings)
    stats["unique_ips"] = list(stats["unique_ips"])
    return {"threats": threats[:15], "warnings": warnings[:10], "stats": stats}


def quick_scan_target(target: str) -> dict:
    target = target.strip()
    result = {"target": target, "type": "unknown", "risks": [], "info": [], "score": 0}
    if target.startswith("http://") or target.startswith("https://"):
        result["type"] = "URL"
        parsed = urllib.parse.urlparse(target)
        result["host"] = parsed.netloc
        if parsed.scheme == "http":
            result["risks"].append("⚠️ HTTP kullanılıyor — şifreleme yok, MITM saldırısına açık")
            result["score"] += 30
        query = parsed.query.lower()
        for param in ["exec", "cmd", "shell", "system", "eval", "base64", "union", "select"]:
            if param in query:
                result["risks"].append(f"🔴 URL'de şüpheli parametre: `{param}` — Injection riski!")
                result["score"] += 40
        if "../" in target or "%2e%2e" in target.lower():
            result["risks"].append("🔴 Path traversal girişimi tespit edildi!")
            result["score"] += 50
        result["info"].append(f"Host: `{parsed.netloc}`")
        result["info"].append(f"Şema: `{parsed.scheme.upper()}`")
        if parsed.path and parsed.path != "/":
            result["info"].append(f"Yol: `{parsed.path}`")
    else:
        try:
            ip_obj = ipaddress.ip_address(target)
            result["type"] = "IP Adresi"
            result["info"].append(f"Versiyon: IPv{ip_obj.version}")
            result["info"].append(f"Özel: {'Evet ✅' if ip_obj.is_private else 'Hayır — Genel IP'}")
            if not ip_obj.is_private:
                result["risks"].append("⚠️ Genel IP — İnternetten erişilebilir")
                result["score"] += 20
        except ValueError:
            result["type"] = "Domain"
            result["info"].append(f"Domain: `{target}`")
            for tld in [".xyz", ".tk", ".ml", ".ga", ".cf", ".gq"]:
                if target.endswith(tld):
                    result["risks"].append(f"⚠️ Şüpheli TLD: `{tld}` — Phishing'de sık kullanılır")
                    result["score"] += 25
            if len(target) > 50:
                result["risks"].append("⚠️ Çok uzun domain adı — Phishing göstergesi olabilir")
                result["score"] += 20
            try:
                ip = socket.gethostbyname(target)
                result["info"].append(f"Çözümlenen IP: `{ip}`")
                result["resolved_ip"] = ip
            except socket.gaierror:
                result["risks"].append("❌ DNS çözümlemesi başarısız — Domain mevcut olmayabilir")
                result["score"] += 10
    result["score"] = min(result["score"], 100)
    if result["score"] == 0 and not result["risks"]:
        result["info"].append("✅ Belirgin güvenlik riski tespit edilmedi.")
    return result


def _sync_check_port(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


async def check_port(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, lambda: _sync_check_port(host, port, timeout))
        return await asyncio.wait_for(fut, timeout=timeout + 0.5)
    except (asyncio.TimeoutError, Exception):
        return False


COMMON_PORTS = {
    21:    ("FTP",        "⚠️ FTP şifresiz veri aktarır, SFTP/FTPS tercih et"),
    22:    ("SSH",        "✅ Güvenli uzak bağlantı — Brute force riski var"),
    23:    ("Telnet",     "🔴 KULLANMA! Telnet şifresiz iletişim kurar"),
    25:    ("SMTP",       "⚠️ Mail sunucusu — Açık relay riski"),
    53:    ("DNS",        "ℹ️ DNS sunucusu — DNS amplification riski"),
    80:    ("HTTP",       "⚠️ Şifresiz web — HTTPS'e yönlendirme önerilir"),
    110:   ("POP3",       "⚠️ Mail protokolü — Şifresiz olabilir"),
    143:   ("IMAP",       "⚠️ Mail protokolü — TLS zorunlu olmalı"),
    443:   ("HTTPS",      "✅ Şifreli web — SSL sertifikası kontrol et"),
    445:   ("SMB",        "🔴 Windows dosya paylaşımı — WannaCry gibi saldırılara hedef"),
    1433:  ("MSSQL",      "🔴 SQL Server — İnternete açık olmamalı!"),
    1521:  ("Oracle DB",  "🔴 Oracle DB — İnternete açık olmamalı!"),
    3306:  ("MySQL",      "🔴 MySQL — İnternete açık olmamalı!"),
    3389:  ("RDP",        "🔴 Uzak masaüstü — Brute force ve exploit riski yüksek"),
    5432:  ("PostgreSQL", "🔴 PostgreSQL — İnternete açık olmamalı!"),
    5900:  ("VNC",        "🔴 Uzak ekran — Şifreleme zayıf, açık olmamalı"),
    6379:  ("Redis",      "🔴 Redis — Varsayılan ayarlarla auth yok, kritik risk"),
    8080:  ("HTTP Alt",   "⚠️ Alternatif HTTP portu — Proxy/uygulama sunucusu"),
    8443:  ("HTTPS Alt",  "ℹ️ Alternatif HTTPS"),
    27017: ("MongoDB",    "🔴 MongoDB — Varsayılan ayarlarla auth yok, kritik risk"),
}


# ============================================================
#  GÜVENLİK — SLASH KOMUTLARI
# ============================================================

@bot.tree.command(name="scan", description="Hedef URL, IP veya domain için güvenlik analizi yap.")
@app_commands.describe(hedef="Analiz edilecek URL, IP adresi veya domain")
async def slash_scan(interaction: discord.Interaction, hedef: str):
    await interaction.response.defer()
    try:
        result = quick_scan_target(hedef)
    except Exception as e:
        return await interaction.followup.send(f"❌ Analiz sırasında hata: `{e}`", ephemeral=True)
    score = result["score"]
    if score >= 70:
        color, risk_label = discord.Color.red(), "🔴 YÜKSEK RİSK"
    elif score >= 40:
        color, risk_label = discord.Color.orange(), "🟠 ORTA RİSK"
    elif score >= 10:
        color, risk_label = discord.Color.yellow(), "🟡 DÜŞÜK RİSK"
    else:
        color, risk_label = discord.Color.green(), "🟢 TEMİZ"
    embed = discord.Embed(title="🔍 Zafiyet Tarama Raporu", color=color)
    embed.add_field(name="🎯 Hedef", value=f"`{hedef}`", inline=False)
    embed.add_field(name="📋 Tür", value=result["type"], inline=True)
    embed.add_field(name="⚡ Risk Skoru", value=f"**{score}/100** — {risk_label}", inline=True)
    if result["info"]:
        embed.add_field(name="ℹ️ Bilgi", value="\n".join(result["info"][:6]), inline=False)
    if result["risks"]:
        embed.add_field(name="🚨 Tespit Edilen Riskler", value="\n".join(result["risks"][:5]), inline=False)
    else:
        embed.add_field(name="✅ Güvenlik", value="Belirgin risk tespit edilmedi.", inline=False)
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    embed.add_field(name="Risk Göstergesi", value=f"`[{bar}] {score}%`", inline=False)
    embed.set_footer(text="Zerith Security | Zafiyet Tarayıcı")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed)
    log_embed = discord.Embed(title="🔍 Tarama Yapıldı", color=color)
    log_embed.add_field(name="Yapan", value=f"{interaction.user} ({interaction.user.id})")
    log_embed.add_field(name="Hedef", value=f"`{hedef}`")
    log_embed.add_field(name="Risk", value=f"{score}/100 — {risk_label}")
    log_embed.timestamp = discord.utils.utcnow()
    await log_send(interaction.guild, log_embed)


@bot.tree.command(name="hash", description="Hash değerini analiz et veya metin hashle.")
@app_commands.describe(deger="Hash değeri veya hashlenecek metin")
async def slash_hash(interaction: discord.Interaction, deger: str):
    await interaction.response.defer()
    result = analyze_hash(deger)
    embed = discord.Embed(title="🔑 Hash & Şifre Analizi", color=discord.Color.purple())
    embed.add_field(name="📥 Girdi", value=f"`{deger[:80]}{'...' if len(deger)>80 else ''}`", inline=False)
    embed.add_field(name="📏 Uzunluk", value=f"{result['length']} karakter", inline=True)
    embed.add_field(name="🔢 Hex mi?", value="✅ Evet" if result["is_hex"] else "❌ Hayır", inline=True)
    if result["detected_types"]:
        type_lines = []
        for t in result["detected_types"]:
            rating, desc = result["security_ratings"].get(t, ("❓ Bilinmiyor", ""))
            type_lines.append(f"**{t}** — {rating}\n└ _{desc}_")
        embed.add_field(name="🔎 Tespit Edilen Hash Türleri", value="\n\n".join(type_lines), inline=False)
    if result["own_hashes"]:
        hash_lines = "\n".join(f"**{alg}:** `{val}`" for alg, val in result["own_hashes"].items())
        embed.add_field(name="🔄 Hesaplanan Hash Değerleri", value=hash_lines, inline=False)
        embed.add_field(name="💡 Öneri", value="Parola saklama için **bcrypt**, **scrypt** veya **Argon2** kullanın!", inline=False)
    embed.set_footer(text="Zerith Security | Hash Analiz Modülü")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="log", description="Log dosyasını güvenlik açısından analiz et.")
@app_commands.describe(dosya="Analiz edilecek log dosyası (.txt, .log)")
async def slash_log(interaction: discord.Interaction, dosya: discord.Attachment):
    await interaction.response.defer()
    if dosya.size > 500_000:
        return await interaction.followup.send("❌ Dosya çok büyük! Maksimum 500KB desteklenir.", ephemeral=True)
    if not any(dosya.filename.endswith(ext) for ext in [".txt", ".log", ".csv"]):
        return await interaction.followup.send("❌ Sadece `.txt`, `.log` ve `.csv` desteklenir.", ephemeral=True)
    try:
        content = await dosya.read()
        text = content.decode("utf-8", errors="ignore")
    except Exception as e:
        return await interaction.followup.send(f"❌ Dosya okunamadı: `{e}`", ephemeral=True)
    result = analyze_log_content(text)
    stats = result["stats"]
    if stats["threat_count"] >= 5:
        color, durum = discord.Color.red(), "🔴 KRİTİK"
    elif stats["threat_count"] >= 1:
        color, durum = discord.Color.orange(), "🟠 UYARI"
    elif stats["warning_count"] >= 3:
        color, durum = discord.Color.yellow(), "🟡 DİKKAT"
    else:
        color, durum = discord.Color.green(), "🟢 TEMİZ"
    embed = discord.Embed(title=f"📋 Log Analiz Raporu — {dosya.filename}", color=color)
    embed.add_field(name="📊 Durum", value=durum, inline=True)
    embed.add_field(name="📄 Satır", value=f"{stats['total_lines']:,}", inline=True)
    embed.add_field(name="🌐 Benzersiz IP", value=str(len(stats['unique_ips'])), inline=True)
    embed.add_field(name="🔴 Tehdit", value=str(stats["threat_count"]), inline=True)
    embed.add_field(name="⚠️ Uyarı", value=str(stats["warning_count"]), inline=True)
    embed.add_field(name="🔑 Başarısız Giriş", value=str(stats["failed_logins"]), inline=True)
    if stats["sql_attempts"]:
        embed.add_field(name="💉 SQL Injection", value=f"{stats['sql_attempts']} girişim", inline=True)
    if stats["xss_attempts"]:
        embed.add_field(name="⚡ XSS", value=f"{stats['xss_attempts']} girişim", inline=True)
    if result["threats"]:
        threat_lines = []
        for t in result["threats"][:5]:
            line_info = f"Satır {t['line']}: " if t["line"] > 0 else ""
            threat_lines.append(f"{t['type']}\n`{line_info}{t['content'][:80]}{'...' if len(t['content'])>80 else ''}`")
        embed.add_field(name=f"🚨 Tehditler (ilk 5/{stats['threat_count']})", value="\n\n".join(threat_lines), inline=False)
    bf_ips = {ip: cnt for ip, cnt in stats["brute_force_ips"].items() if cnt >= 5}
    if bf_ips:
        ip_lines = "\n".join(f"`{ip}` — {cnt} deneme" for ip, cnt in sorted(bf_ips.items(), key=lambda x: -x[1])[:5])
        embed.add_field(name="🔒 Brute Force Şüphelileri", value=ip_lines, inline=False)
    embed.set_footer(text="Zerith Security | Log Analiz Modülü")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed)
    log_embed = discord.Embed(title="📋 Log Analizi Yapıldı", color=color)
    log_embed.add_field(name="Yapan", value=f"{interaction.user} ({interaction.user.id})")
    log_embed.add_field(name="Dosya", value=dosya.filename)
    log_embed.add_field(name="Tehdit", value=str(stats["threat_count"]))
    log_embed.timestamp = discord.utils.utcnow()
    await log_send(interaction.guild, log_embed)


@bot.tree.command(name="portscan", description="Bir IP veya domain üzerinde yaygın portları tara.")
@app_commands.describe(ip="Taranacak IP adresi veya domain")
async def slash_portscan(interaction: discord.Interaction, ip: str):
    await interaction.response.defer()
    ip = ip.strip()
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_loopback:
            return await interaction.followup.send("❌ Loopback adresini tarayamazsın.", ephemeral=True)
    except ValueError:
        try:
            socket.gethostbyname(ip)
        except socket.gaierror:
            return await interaction.followup.send(f"❌ `{ip}` çözümlenemedi.", ephemeral=True)
    status_msg = await interaction.followup.send(f"🔍 `{ip}` taranıyor... ({len(COMMON_PORTS)} port kontrol ediliyor)")
    open_ports, critical_open = [], []
    results = {}
    for port in COMMON_PORTS:
        results[port] = await check_port(ip, port)
    for port, is_open in results.items():
        if is_open:
            service, risk_note = COMMON_PORTS[port]
            open_ports.append((port, service, risk_note))
            if "🔴" in risk_note:
                critical_open.append(port)
    if len(open_ports) == 0:
        color, durum = discord.Color.green(), "🟢 Güvenli — Açık port bulunamadı"
    elif critical_open:
        color, durum = discord.Color.red(), f"🔴 KRİTİK — {len(critical_open)} kritik port açık!"
    else:
        color, durum = discord.Color.orange(), f"🟠 DİKKAT — {len(open_ports)} port açık"
    embed = discord.Embed(title="🌐 Port Tarama Raporu", color=color)
    embed.add_field(name="🎯 Hedef", value=f"`{ip}`", inline=True)
    embed.add_field(name="📊 Durum", value=durum, inline=True)
    embed.add_field(name="🔢 Taranan", value=str(len(COMMON_PORTS)), inline=True)
    embed.add_field(name="🟢 Açık", value=str(len(open_ports)), inline=True)
    embed.add_field(name="🔴 Kritik", value=str(len(critical_open)), inline=True)
    if open_ports:
        port_lines = []
        for port, service, risk in open_ports:
            port_lines.append(f"**:{port}** ({service})\n└ {risk}")
        embed.add_field(name="📋 Açık Portlar", value="\n\n".join(port_lines[:8]), inline=False)
    if critical_open:
        embed.add_field(name="⚠️ Acil Önlem Alınmalı", value=", ".join(f"`{p}`" for p in critical_open), inline=False)
    embed.add_field(name="📌 Not", value="Sadece kendi sistemlerinizi tarayın.", inline=False)
    embed.set_footer(text="Zerith Security | Ağ Güvenlik Tarayıcısı")
    embed.timestamp = discord.utils.utcnow()
    await status_msg.edit(content="", embed=embed)
    log_embed = discord.Embed(title="🌐 Port Taraması Yapıldı", color=color)
    log_embed.add_field(name="Yapan", value=f"{interaction.user} ({interaction.user.id})")
    log_embed.add_field(name="Hedef", value=f"`{ip}`")
    log_embed.add_field(name="Açık Port", value=str(len(open_ports)))
    log_embed.timestamp = discord.utils.utcnow()
    await log_send(interaction.guild, log_embed)


@bot.tree.command(name="encode", description="Metni Base64 veya Hex ile şifrele/çöz.")
@app_commands.describe(
    metin="İşlenecek metin veya kod",
    islem="encode (şifrele) veya decode (çöz)",
    format="base64 veya hex"
)
@app_commands.choices(
    islem=[app_commands.Choice(name="Şifrele (encode)", value="encode"),
           app_commands.Choice(name="Çöz (decode)", value="decode")],
    format=[app_commands.Choice(name="Base64", value="base64"),
            app_commands.Choice(name="Hex", value="hex")]
)
async def slash_encode(interaction: discord.Interaction, metin: str, islem: str, format: str):
    await interaction.response.defer()
    try:
        if format == "base64":
            if islem == "encode":
                sonuc = base64.b64encode(metin.encode("utf-8")).decode("utf-8")
                aciklama = "Base64 ile şifrelendi"
            else:
                sonuc = base64.b64decode(metin.encode("utf-8")).decode("utf-8")
                aciklama = "Base64 çözüldü"
        else:  # hex
            if islem == "encode":
                sonuc = metin.encode("utf-8").hex()
                aciklama = "Hex ile şifrelendi"
            else:
                sonuc = bytes.fromhex(metin).decode("utf-8")
                aciklama = "Hex çözüldü"
        embed = discord.Embed(title="🔐 Encode / Decode", color=discord.Color.teal())
        embed.add_field(name="📥 Girdi", value=f"```{metin[:200]}```", inline=False)
        embed.add_field(name=f"📤 Çıktı ({aciklama})", value=f"```{sonuc[:500]}```", inline=False)
        embed.add_field(name="🔧 Yöntem", value=f"`{format.upper()}` — `{islem.upper()}`", inline=True)
        embed.set_footer(text="Zerith Security | Encode/Decode Modülü")
        embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: `{e}` — Girdiğin veri `{format}` formatında çözülemiyor olabilir.", ephemeral=True)


@bot.tree.command(name="password", description="Güçlü ve rastgele şifre üret.")
@app_commands.describe(
    uzunluk="Şifre uzunluğu (8-64)",
    buyuk="Büyük harf kullan",
    rakam="Rakam kullan",
    ozel="Özel karakter kullan"
)
async def slash_password(interaction: discord.Interaction,
                          uzunluk: int = 16,
                          buyuk: bool = True,
                          rakam: bool = True,
                          ozel: bool = True):
    await interaction.response.defer(ephemeral=True)
    uzunluk = max(8, min(64, uzunluk))
    charset = string.ascii_lowercase
    if buyuk:
        charset += string.ascii_uppercase
    if rakam:
        charset += string.digits
    if ozel:
        charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    sifre = ''.join(secrets.choice(charset) for _ in range(uzunluk))

    # Güç hesapla
    entropi = len(charset) ** uzunluk
    if uzunluk >= 20 and ozel:
        guc, guc_emoji = "Çok Güçlü", "🟢"
    elif uzunluk >= 14:
        guc, guc_emoji = "Güçlü", "✅"
    elif uzunluk >= 10:
        guc, guc_emoji = "Orta", "🟡"
    else:
        guc, guc_emoji = "Zayıf", "🔴"

    embed = discord.Embed(title="🔐 Şifre Üretici", color=discord.Color.green())
    embed.add_field(name="🔑 Üretilen Şifre", value=f"```{sifre}```", inline=False)
    embed.add_field(name="📏 Uzunluk", value=str(uzunluk), inline=True)
    embed.add_field(name="💪 Güç", value=f"{guc_emoji} {guc}", inline=True)
    embed.add_field(name="🔠 Karakter Seti",
                    value=f"Küçük harf ✅ | Büyük harf {'✅' if buyuk else '❌'} | Rakam {'✅' if rakam else '❌'} | Özel {'✅' if ozel else '❌'}",
                    inline=False)
    embed.add_field(name="💡 Öneri", value="Bu şifreyi not edin ve güvenli bir yerde saklayın. Kimseyle paylaşmayın!", inline=False)
    embed.set_footer(text="Zerith Security | Şifre Üretici • Sadece siz görüyorsunuz")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="ipinfo", description="Bir IP adresi hakkında detaylı bilgi al.")
@app_commands.describe(ip="Sorgulanacak IP adresi")
async def slash_ipinfo(interaction: discord.Interaction, ip: str):
    await interaction.response.defer()
    ip = ip.strip()
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return await interaction.followup.send("❌ Geçersiz IP adresi formatı.", ephemeral=True)

    embed = discord.Embed(title=f"🌐 IP Bilgisi — `{ip}`", color=discord.Color.blue())
    embed.add_field(name="📌 IP Adresi", value=f"`{ip}`", inline=True)
    embed.add_field(name="🔢 Versiyon", value=f"IPv{ip_obj.version}", inline=True)

    ozellikler = []
    if ip_obj.is_private:
        ozellikler.append("🔵 Özel (LAN) ağ adresi")
    if ip_obj.is_loopback:
        ozellikler.append("🔄 Loopback adresi")
    if ip_obj.is_multicast:
        ozellikler.append("📡 Multicast adresi")
    if ip_obj.is_global:
        ozellikler.append("🌍 Global (genel internet) adresi")
    if ip_obj.is_link_local:
        ozellikler.append("🔗 Link-local adresi")
    if ip_obj.is_reserved:
        ozellikler.append("⚙️ Rezerve edilmiş adres")
    if not ozellikler:
        ozellikler.append("❓ Bilinmeyen tür")

    embed.add_field(name="🏷️ Tür", value="\n".join(ozellikler), inline=False)

    # Risk değerlendirmesi
    if ip_obj.is_private:
        risk = "🟢 Düşük — Yerel ağ adresi"
    elif ip_obj.is_loopback:
        risk = "🟢 Yok — Loopback"
    elif ip_obj.is_global:
        risk = "🟠 Orta — İnternetten erişilebilir genel IP"
    else:
        risk = "🟡 Belirsiz"

    embed.add_field(name="⚡ Risk", value=risk, inline=True)

    # Bilinen özel aralıklar
    if ip_obj.version == 4:
        ip_str = str(ip_obj)
        if ip_str.startswith("10."):
            embed.add_field(name="📋 Aralık", value="RFC1918 — `10.0.0.0/8`", inline=True)
        elif ip_str.startswith("192.168."):
            embed.add_field(name="📋 Aralık", value="RFC1918 — `192.168.0.0/16`", inline=True)
        elif ip_str.startswith("172."):
            second = int(ip_str.split(".")[1])
            if 16 <= second <= 31:
                embed.add_field(name="📋 Aralık", value="RFC1918 — `172.16.0.0/12`", inline=True)
        elif ip_str.startswith("127."):
            embed.add_field(name="📋 Aralık", value="Loopback — `127.0.0.0/8`", inline=True)

    embed.set_footer(text="Zerith Security | IP Analiz Modülü")
    embed.timestamp = discord.utils.utcnow()
    await interaction.followup.send(embed=embed)


# ============================================================
#  SLASH KOMUTLARI (DİĞER)
# ============================================================

@bot.tree.command(name="rank", description="Seviye kartını göster.")
@app_commands.describe(uye="Kullanıcı")
async def slash_rank(interaction: discord.Interaction, uye: discord.Member = None):
    uye = uye or interaction.user
    veri = xp_get(uye.id, interaction.guild.id)
    sira = xp_rank(uye.id, interaction.guild.id)
    sonraki_xp = None
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if lvl > veri["level"]:
            sonraki_xp = threshold
            break
    embed = discord.Embed(title=f"📊 {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_thumbnail(url=uye.display_avatar.url)
    embed.add_field(name="⭐ Seviye", value=str(veri["level"]))
    embed.add_field(name="✨ XP", value=f"{veri['xp']:,}")
    embed.add_field(name="🏆 Sıra", value=f"#{sira}")
    if sonraki_xp:
        ilerleme = min(int((veri["xp"] / sonraki_xp) * 10), 10)
        bar = "▓" * ilerleme + "░" * (10 - ilerleme)
        embed.add_field(name="İlerleme", value=f"`{bar}` {veri['xp']:,}/{sonraki_xp:,}", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="para", description="Bakiyeni göster.")
@app_commands.describe(uye="Kullanıcı")
async def slash_para(interaction: discord.Interaction, uye: discord.Member = None):
    uye = uye or interaction.user
    veri = eco_get(uye.id, interaction.guild.id)
    embed = discord.Embed(title=f"💰 {uye.display_name}", color=discord.Color.gold())
    embed.add_field(name="👛 Cüzdan", value=f"{veri['coins']:,} 🪙")
    embed.add_field(name="🏦 Banka", value=f"{veri['bank']:,} 🪙")
    embed.add_field(name="💎 Toplam", value=f"{veri['coins']+veri['bank']:,} 🪙")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="kullanici", description="Kullanıcı bilgilerini göster.")
@app_commands.describe(uye="Kullanıcı")
async def slash_kullanici(interaction: discord.Interaction, uye: discord.Member = None):
    uye = uye or interaction.user
    embed = discord.Embed(title=f"👤 {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_thumbnail(url=uye.display_avatar.url)
    embed.add_field(name="Kullanıcı", value=str(uye))
    embed.add_field(name="ID", value=str(uye.id))
    embed.add_field(name="Sunucuya Katılma", value=uye.joined_at.strftime("%d/%m/%Y %H:%M"))
    embed.add_field(name="Hesap Oluşturma", value=uye.created_at.strftime("%d/%m/%Y %H:%M"))
    xp_data = xp_get(uye.id, interaction.guild.id)
    embed.add_field(name="⭐ Seviye", value=f"{xp_data['level']} ({xp_data['xp']:,} XP)")
    roller = [r.mention for r in uye.roles if r.name != "@everyone"]
    embed.add_field(name=f"Roller ({len(roller)})", value=" ".join(roller[:10]) if roller else "Yok", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ban", description="Kullanıcıyı banla.")
@app_commands.describe(uye="Kullanıcı", sebep="Sebep")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep belirtilmedi"):
    if uye.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Yetkiniz yok.", ephemeral=True)
    await uye.ban(reason=f"{interaction.user}: {sebep}")
    embed = discord.Embed(title="🔨 Banlandı", color=discord.Color.red())
    embed.add_field(name="Kullanıcı", value=f"{uye} ({uye.id})")
    embed.add_field(name="Sebep", value=sebep)
    await interaction.response.send_message(embed=embed)
    await log_send(interaction.guild, embed)


@bot.tree.command(name="kick", description="Kullanıcıyı at.")
@app_commands.describe(uye="Kullanıcı", sebep="Sebep")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep belirtilmedi"):
    await uye.kick(reason=sebep)
    embed = discord.Embed(title="👢 Atıldı", color=discord.Color.orange())
    embed.add_field(name="Kullanıcı", value=f"{uye}")
    embed.add_field(name="Sebep", value=sebep)
    await interaction.response.send_message(embed=embed)
    await log_send(interaction.guild, embed)


@bot.tree.command(name="mute", description="Kullanıcıyı sustur.")
@app_commands.describe(uye="Kullanıcı", dakika="Kaç dakika", sebep="Sebep")
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_mute(interaction: discord.Interaction, uye: discord.Member, dakika: int = 10, sebep: str = "Sebep belirtilmedi"):
    await uye.timeout(timedelta(minutes=dakika), reason=sebep)
    embed = discord.Embed(title="🔇 Susturuldu", color=discord.Color.blue())
    embed.add_field(name="Kullanıcı", value=uye.mention)
    embed.add_field(name="Süre", value=f"{dakika}dk")
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await interaction.response.send_message(embed=embed)
    await log_send(interaction.guild, embed)


@bot.tree.command(name="uyar", description="Kullanıcıyı uyar.")
@app_commands.describe(uye="Kullanıcı", sebep="Sebep")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_uyar(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep belirtilmedi"):
    count = warn_add(uye.id, interaction.guild.id, interaction.user.id, sebep)
    embed = discord.Embed(title="⚠️ Uyarı", color=discord.Color.yellow())
    embed.add_field(name="Kullanıcı", value=uye.mention)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.add_field(name="Uyarı", value=str(count))
    await interaction.response.send_message(embed=embed)
    await log_send(interaction.guild, embed)


@bot.tree.command(name="temizle", description="Mesajları sil.")
@app_commands.describe(miktar="Kaç mesaj")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_temizle(interaction: discord.Interaction, miktar: int = 10):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(miktar, 100))
    await interaction.followup.send(f"✅ {len(deleted)} mesaj silindi.", ephemeral=True)


@bot.tree.command(name="afk", description="AFK moduna geç.")
@app_commands.describe(sebep="Sebep")
async def slash_afk(interaction: discord.Interaction, sebep: str = "AFK"):
    afk_set(interaction.user.id, interaction.guild.id, sebep)
    embed = discord.Embed(title="💤 AFK", description=f"{interaction.user.mention} AFK'ya geçti.", color=discord.Color.greyple())
    embed.add_field(name="Sebep", value=sebep)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="öneri", description="Sunucuya öneri gönder.")
@app_commands.describe(metin="Önerin")
async def slash_oneri(interaction: discord.Interaction, metin: str):
    settings = get_settings(interaction.guild.id)
    suggest_id = settings.get("suggestion_channel_id")
    if not suggest_id:
        return await interaction.response.send_message("❌ Öneri kanalı ayarlanmamış.", ephemeral=True)
    ch = interaction.guild.get_channel(int(suggest_id))
    if not ch:
        return await interaction.response.send_message("❌ Kanal bulunamadı.", ephemeral=True)
    embed = discord.Embed(title="💡 Öneri", description=metin, color=discord.Color.blurple())
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    msg = await ch.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("✅ Önerin iletildi!", ephemeral=True)


@bot.tree.command(name="avatar", description="Profil fotoğrafını göster.")
@app_commands.describe(uye="Kullanıcı")
async def slash_avatar(interaction: discord.Interaction, uye: discord.Member = None):
    uye = uye or interaction.user
    embed = discord.Embed(title=f"🖼️ {uye.display_name}", color=uye.color or discord.Color.blurple())
    embed.set_image(url=uye.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="zar", description="Zar at.")
@app_commands.describe(yuz="Kaç yüzlü (2-100)")
async def slash_zar(interaction: discord.Interaction, yuz: int = 6):
    if yuz < 2 or yuz > 100:
        return await interaction.response.send_message("❌ 2-100 arası.", ephemeral=True)
    await interaction.response.send_message(f"🎲 **1d{yuz}** → **{random.randint(1, yuz)}**")


@bot.tree.command(name="8top", description="Sihirli 8 top.")
@app_commands.describe(soru="Sorun")
async def slash_8top(interaction: discord.Interaction, soru: str):
    cevaplar = ["✅ Kesinlikle evet!", "✅ Evet.", "✅ Muhtemelen.", "🤔 Belirsiz.", "❌ Hayır.", "⛔ Kesinlikle hayır."]
    embed = discord.Embed(title="🎱 Sihirli 8 Top", color=discord.Color.dark_purple())
    embed.add_field(name="Soru", value=soru, inline=False)
    embed.add_field(name="Cevap", value=random.choice(cevaplar), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="hatırlat", description="Hatırlatıcı kur.")
@app_commands.describe(sure="Süre (örn: 30m, 2h, 1d)", mesaj="Ne hatırlatalım?")
async def slash_hatirla(interaction: discord.Interaction, sure: str, mesaj: str):
    match = re.match(r"(\d+)([smhd])", sure)
    if not match:
        return await interaction.response.send_message("❌ Geçersiz süre!", ephemeral=True)
    sayi, birim = int(match.group(1)), match.group(2)
    seconds = sayi * {"s": 1, "m": 60, "h": 3600, "d": 86400}[birim]
    remind_at = time.time() + seconds
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT INTO reminders (user_id, channel_id, guild_id, message, remind_at) VALUES (?,?,?,?,?)",
              (str(interaction.user.id), str(interaction.channel.id), str(interaction.guild.id), mesaj, remind_at))
    conn.commit()
    conn.close()
    embed = discord.Embed(title="⏰ Hatırlatıcı Ayarlandı", color=discord.Color.blue())
    embed.add_field(name="Mesaj", value=mesaj)
    embed.add_field(name="Süre", value=f"<t:{int(remind_at)}:R>")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="daily", description="Günlük ödülünü al.")
async def slash_daily(interaction: discord.Interaction):
    veri = eco_get(interaction.user.id, interaction.guild.id)
    kalan = veri["last_daily"] + 86400 - time.time()
    if kalan > 0:
        return await interaction.response.send_message(f"⏳ **{format_time(kalan)}** bekle.", ephemeral=True)
    streak = veri["streak"] + 1
    odul = random.randint(DAILY_MIN, DAILY_MAX)
    bonus = int(odul * 0.5) if streak >= 7 else int(odul * 0.2) if streak >= 3 else 0
    eco_add_coins(interaction.user.id, interaction.guild.id, odul + bonus)
    eco_update(interaction.user.id, interaction.guild.id, last_daily=time.time(), streak=streak)
    embed = discord.Embed(title="🎁 Günlük Ödül", color=discord.Color.gold())
    embed.add_field(name="Kazanılan", value=f"**{odul} 🪙**")
    if bonus:
        embed.add_field(name=f"🔥 {streak}g Serisi", value=f"+{bonus} 🪙")
    await interaction.response.send_message(embed=embed)


# ============================================================
#  YARDIM SİSTEMİ
# ============================================================

HELP_CATEGORIES = {
    "⚙️ Kurulum": {
        "desc": "Bot kurulum komutları (Sadece Admin)",
        "commands": [
            ("/setup welcome", "Karşılama kanalını ayarla"),
            ("/setup goodbye", "Veda kanalını ayarla"),
            ("/setup log", "Log kanalını ayarla"),
            ("/setup modrole", "Moderatör rolünü ayarla"),
            ("/setup autorole", "Oto-rolü ayarla"),
            ("/setup levelup", "Seviye atlama kanalını ayarla"),
            ("/setup suggestion", "Öneri kanalını ayarla"),
            ("/setup ticket", "Ticket sistemini ayarla"),
            ("/setup görüntüle", "Tüm ayarları göster"),
        ]
    },
    "🛡️ Moderasyon": {
        "desc": "Sunucu yönetim komutları",
        "commands": [
            ("ban @kullanıcı [sebep]", "Kullanıcıyı banla"),
            ("unban kullanıcı#1234", "Banı kaldır"),
            ("kick @kullanıcı [sebep]", "Kullanıcıyı at"),
            ("mute @kullanıcı [dakika] [sebep]", "Sustur"),
            ("unmute @kullanıcı", "Susturmayı kaldır"),
            ("uyar @kullanıcı [sebep]", "Uyarı ver"),
            ("uyariler @kullanıcı", "Uyarıları listele"),
            ("uyarisil <id>", "Uyarıyı sil"),
            ("uyarisifirla @kullanıcı", "Tüm uyarıları sil"),
            ("temizle [sayı] [@kullanıcı]", "Mesaj temizle"),
            ("kilitle [#kanal]", "Kanalı kilitle"),
            ("kilitsiz [#kanal]", "Kanalı aç"),
            ("yavaşmod [saniye]", "Yavaş mod"),
            ("not @kullanıcı <metin>", "Gizli mod notu ekle"),
            ("notlar @kullanıcı", "Mod notlarını gör"),
            ("küfürfiltre aç/kapat", "Küfür filtresini aç/kapat"),
            ("filtredurum", "Filtre durumunu göster"),
        ]
    },
    "🔒 Güvenlik": {
        "desc": "Güvenlik analizi ve zafiyet tespiti",
        "commands": [
            ("/scan <hedef>",    "URL/IP/domain güvenlik analizi"),
            ("/portscan <ip>",   "Açık port ve ağ güvenlik taraması"),
            ("/hash <değer>",    "Hash türü tespiti ve şifre analizi"),
            ("/log <dosya>",     "Log dosyası güvenlik taraması"),
            ("/encode <metin>",  "Base64/Hex encode & decode"),
            ("/password",        "Güçlü rastgele şifre üret"),
            ("/ipinfo <ip>",     "IP adresi detaylı analizi"),
        ]
    },
    "⭐ Seviye & XP": {
        "desc": "Aktivite ve seviye sistemi",
        "commands": [
            ("rank [@kullanıcı]", "Seviye kartını göster"),
            ("leaderboard", "Aktivite sıralaması"),
        ]
    },
    "💰 Ekonomi": {
        "desc": "Para ve eşya sistemi",
        "commands": [
            ("para [@kullanıcı]", "Bakiye göster"),
            ("daily", "Günlük ödül al (seri bonusu!)"),
            ("çalış", "Para kazan (1sa bekleme)"),
            ("suç", "Riskli ama kazançlı (2sa bekleme)"),
            ("yatır <miktar/hepsi>", "Bankaya yatır"),
            ("çek <miktar/hepsi>", "Bankadan çek"),
            ("gönder @kullanıcı <miktar>", "Para transfer et (%5 vergi)"),
            ("market", "Ürünleri listele"),
            ("satın <ürün_id>", "Ürün satın al"),
            ("sat <ürün_id>", "Ürün sat"),
            ("envanter [@kullanıcı]", "Envanter göster"),
            ("zenginler", "En zenginler sıralaması"),
        ]
    },
    "🎮 Mini Oyunlar": {
        "desc": "Eğlenceli mini oyunlar (ödüllü!)",
        "commands": [
            ("trivia [kategori]", "Bilgi yarışması (+50 🪙)"),
            ("hangman [kategori]", "Adam asmaca (+100 🪙)"),
            ("wordle", "5 harfli kelime bul (+50-150 🪙)"),
            ("yaz", "Hızlı yazma yarışması (+75 🪙)"),
            ("oyunlar", "Tüm oyunları listele"),
        ]
    },
    "🎉 Eğlence": {
        "desc": "Eğlence ve oyun komutları",
        "commands": [
            ("zar [yüz]", "Zar at"),
            ("yazıtura", "Yazı-tura at"),
            ("8top <soru>", "Sihirli 8 top"),
            ("ship @k1 @k2", "Uyumluluk testi"),
            ("hack @kullanıcı", "Sahte hack"),
            ("rps <taş/kağıt/makas>", "Taş Kağıt Makas"),
            ("sayım [sayı]", "Geri sayım"),
        ]
    },
    "🛠️ Araçlar": {
        "desc": "Yardımcı araçlar",
        "commands": [
            ("hatırlat <süre> <mesaj>", "Hatırlatıcı kur (30m, 2h, 1d)"),
            ("hatırlatmalar", "Hatırlatıcılarını listele"),
            ("öneri <metin>", "Öneri gönder"),
            ("afk [sebep]", "AFK moduna geç"),
            ("ping", "Bot gecikmesini göster"),
            ("avatar [@kullanıcı]", "Profil fotoğrafı"),
            ("kullanici [@kullanıcı]", "Kullanıcı bilgisi"),
            ("sunucu", "Sunucu bilgisi"),
            ("botbilgi", "Bot bilgisi"),
            ("kendinitanıt", "Botu tanıt (Admin)"),
        ]
    },
    "📢 Yönetim": {
        "desc": "Sunucu yönetim araçları (Yetkili)",
        "commands": [
            ("duyuru #kanal <metin>", "Duyuru gönder"),
            ("embed #kanal <başlık> <renk> <metin>", "Özel embed gönder"),
            ("anket <soru>", "Anket başlat"),
            ("yetkili <sebep>", "Yetkiliye çağrı"),
            ("çekiliş <süre> <kazanan> <ödül>", "Çekiliş başlat"),
            ("çekilişsil <mesaj_id>", "Çekilişi iptal et"),
            ("ticket_panel", "Ticket paneli kur"),
        ]
    },
}

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cat, description=data["desc"][:100], emoji=cat.split()[0])
            for cat, data in HELP_CATEGORIES.items()
        ]
        super().__init__(placeholder="📚 Kategori seç...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        data = HELP_CATEGORIES[cat]
        embed = discord.Embed(title=f"{cat}", description=data["desc"], color=discord.Color.blurple())
        cmd_list = "\n".join(f"`!{cmd}` — {desc}" for cmd, desc in data["commands"])
        embed.add_field(name="Komutlar", value=cmd_list, inline=False)
        embed.set_footer(text="! ve / ile kullanılabilir • Köşeli parantez = opsiyonel")
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())

    @discord.ui.button(label="Ana Sayfa", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_help_home()
        await interaction.response.edit_message(embed=embed, view=self)


def build_help_home():
    embed = discord.Embed(
        title="📚 Zerith Security — Yardım",
        description="Aşağıdan bir kategori seçerek komutları görüntüle.\n\nTüm komutlar hem `!` hem de `/` ile kullanılabilir.",
        color=discord.Color.blurple()
    )
    for cat, data in HELP_CATEGORIES.items():
        cmd_count = len(data["commands"])
        embed.add_field(name=cat, value=f"{data['desc']}\n`{cmd_count} komut`", inline=True)
    embed.set_footer(text="Zerith Security | Güvenilir, Hızlı, Güçlü.")
    return embed


@bot.command(name="yardım", aliases=["yardim", "help", "komutlar"])
async def yardim(ctx):
    embed = build_help_home()
    await ctx.send(embed=embed, view=HelpView())


@bot.tree.command(name="yardım", description="Komut listesini göster.")
async def slash_yardim(interaction: discord.Interaction):
    embed = build_help_home()
    await interaction.response.send_message(embed=embed, view=HelpView())


# ============================================================
#  HATA YÖNETİMİ
# ============================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komut için yetkin yok.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Kullanıcı bulunamadı.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik argüman: `{error.param.name}`. `!yardım` ile kontrol et.", delete_after=8)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Geçersiz argüman. `!yardım` ile kontrol et.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.CommandOnCooldown):
        pass
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Bu komutu kullanma yetkin yok.", delete_after=5)
    else:
        print(f"Beklenmeyen hata: {type(error).__name__}: {error}")
        await ctx.send(f"❌ Bir hata oluştu: `{type(error).__name__}`", delete_after=8)


@bot.tree.error
async def slash_error(interaction: discord.Interaction, error):
    msg = "❌ Bir hata oluştu."
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Bu komut için yetkin yok."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ {format_time(error.retry_after)} bekle."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ============================================================
#  BOTU BAŞLAT
# ============================================================

bot.run(TOKEN)
ENDOFFILE
echo "Done"