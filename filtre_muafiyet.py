"""
filtre_muafiyet.py — Zerith Security
Küfür, reklam ve caps lock filtrelerinden muaf tutulacak kişileri belirler.

Muaf olanlar (hiçbiri filtrelenmez):
  • Sunucu sahibi
  • Administrator yetkisi olan herkes
  • Moderatör rolü (/setup modrole ile ayarlanan)
  • Elle eklenen muaf roller (/muafrol ekle ile)

KURULUM — main.py'ye eklenecekler:

  1) En üste import ekle:
       from filtre_muafiyet import filtre_muaf_mi, setup_muafiyet

  2) on_ready içine ekle (setup_yeni_ozellikler satırının altına):
       await setup_muafiyet(bot, db_connect, get_settings, set_setting)

  3) on_message içinde küfür filtresinin hemen ÜSTÜNE şunu ekle:
       if await filtre_muaf_mi(message.author, message.guild):
           await bot.process_commands(message)
           return

  Yani on_message şu şekilde görünmeli:

       # AFK kontrolü
       ...

       # ← BURAYI EKLE
       if await filtre_muaf_mi(message.author, message.guild):
           await bot.process_commands(message)
           return
       # ← BURAYA KADAR

       # Küfür filtresi
       if message.guild.id not in KUFUR_FILTRE_KAPALI:
           ...
"""

import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

_db_connect = None
_get_settings = None
_set_setting = None


# ============================================================
#  VERİTABANI — muaf roller tablosu
# ============================================================

def _muafiyet_db_init():
    conn = _db_connect()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS filtre_muaf_roller (
        guild_id TEXT,
        role_id  TEXT,
        PRIMARY KEY (guild_id, role_id)
    )""")
    conn.commit()
    conn.close()


def _muaf_rol_ekle(guild_id, role_id):
    conn = _db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO filtre_muaf_roller (guild_id, role_id) VALUES (?,?)",
        (str(guild_id), str(role_id))
    )
    conn.commit()
    conn.close()


def _muaf_rol_kaldir(guild_id, role_id):
    conn = _db_connect()
    c = conn.cursor()
    c.execute(
        "DELETE FROM filtre_muaf_roller WHERE guild_id=? AND role_id=?",
        (str(guild_id), str(role_id))
    )
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def _muaf_roller_getir(guild_id):
    conn = _db_connect()
    c = conn.cursor()
    c.execute(
        "SELECT role_id FROM filtre_muaf_roller WHERE guild_id=?",
        (str(guild_id),)
    )
    rows = c.fetchall()
    conn.close()
    return [int(r["role_id"]) for r in rows]


# ============================================================
#  ANA KONTROL FONKSİYONU
# ============================================================

async def filtre_muaf_mi(member: discord.Member, guild: discord.Guild) -> bool:
    """
    True dönerse → bu kişinin mesajına filtre uygulanmaz.
    """
    if member.bot:
        return True   # Botlar zaten filtrelenmez

    # 1. Sunucu sahibi
    if member.id == guild.owner_id:
        return True

    # 2. Administrator yetkisi
    if member.guild_permissions.administrator:
        return True

    # 3. /setup modrole ile ayarlanan moderatör rolü
    settings = _get_settings(guild.id)
    mod_role_id = settings.get("mod_role_id")
    if mod_role_id:
        mod_role = guild.get_role(int(mod_role_id))
        if mod_role and mod_role in member.roles:
            return True

    # 4. Elle eklenen muaf roller (/muafrol ekle)
    muaf_rol_idler = _muaf_roller_getir(guild.id)
    for role in member.roles:
        if role.id in muaf_rol_idler:
            return True

    return False


# ============================================================
#  /muafrol KOMUTLARI
# ============================================================

def _register_muafrol_commands(bot: commands.Bot):

    muaf_group = app_commands.Group(
        name="muafrol",
        description="Filtreden muaf rolleri yönet (Admin)"
    )

    @muaf_group.command(
        name="ekle",
        description="Bu roldekiler küfür/reklam/caps filtrelerinden muaf olur."
    )
    @app_commands.describe(rol="Muaf tutulacak rol")
    @app_commands.checks.has_permissions(administrator=True)
    async def muafrol_ekle(interaction: discord.Interaction, rol: discord.Role):
        _muaf_rol_ekle(interaction.guild.id, rol.id)
        embed = discord.Embed(
            title="✅ Muaf Rol Eklendi",
            description=f"{rol.mention} artık filtrelerden muaf.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Bu roldekiler küfür/reklam/caps filtresine takılmaz.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @muaf_group.command(
        name="kaldir",
        description="Rolün muafiyet iznini kaldır."
    )
    @app_commands.describe(rol="Muafiyeti kaldırılacak rol")
    @app_commands.checks.has_permissions(administrator=True)
    async def muafrol_kaldir(interaction: discord.Interaction, rol: discord.Role):
        if _muaf_rol_kaldir(interaction.guild.id, rol.id):
            await interaction.response.send_message(
                f"✅ {rol.mention} artık filtrelere tabi.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {rol.mention} zaten muaf listesinde değil.", ephemeral=True
            )

    @muaf_group.command(
        name="liste",
        description="Muaf rollerin listesini göster."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def muafrol_liste(interaction: discord.Interaction):
        muaf_idler = _muaf_roller_getir(interaction.guild.id)
        settings = _get_settings(interaction.guild.id)
        mod_role_id = settings.get("mod_role_id")

        embed = discord.Embed(
            title="🛡️ Filtreden Muaf Roller",
            color=discord.Color.blurple()
        )

        # Otomatik muaflar
        otomatik = ["👑 Sunucu Sahibi", "⚙️ Administrator yetkisi olan herkes"]
        if mod_role_id:
            mod_role = interaction.guild.get_role(int(mod_role_id))
            if mod_role:
                otomatik.append(f"🛡️ Moderatör rolü: {mod_role.mention}")
        embed.add_field(
            name="Otomatik Muaflar (değiştirilemez)",
            value="\n".join(otomatik),
            inline=False
        )

        # Elle eklenen muaflar
        if muaf_idler:
            roller = []
            for rid in muaf_idler:
                rol = interaction.guild.get_role(rid)
                roller.append(rol.mention if rol else f"Silinmiş rol (ID: {rid})")
            embed.add_field(
                name="Elle Eklenen Muaflar",
                value="\n".join(roller),
                inline=False
            )
        else:
            embed.add_field(
                name="Elle Eklenen Muaflar",
                value="Yok — `/muafrol ekle @Rol` ile ekle",
                inline=False
            )

        embed.set_footer(text="Muaf kişilerin mesajları hiçbir filtreye takılmaz.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    bot.tree.add_command(muaf_group)


# ============================================================
#  KURULUM
# ============================================================

async def setup_muafiyet(
    bot_instance: commands.Bot,
    db_connect_func,
    get_settings_func,
    set_setting_func
):
    global _db_connect, _get_settings, _set_setting
    _db_connect = db_connect_func
    _get_settings = get_settings_func
    _set_setting = set_setting_func

    _muafiyet_db_init()
    _register_muafrol_commands(bot_instance)

    print("✅ filtre_muafiyet.py yüklendi: Sunucu sahibi ve yetkililer filtreden muaf.")