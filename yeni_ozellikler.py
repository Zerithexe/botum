"""
yeni_ozellikler.py — Zerith Security
Yeni özellikler:
  1. Caps Lock Filtresi  → büyük harfli mesajı küçük harfe çevirir
  2. Detaylı Log Sistemi → her log türü için ayrı kanal ayarlanabilir
  3. Çekiliş Rolü        → sadece belirli rol çekiliş başlatabilir

Bu dosyayı ana klasörüne koy, sonra:
  main.py içine şunu ekle:
    from yeni_ozellikler import setup_yeni_ozellikler
  on_ready fonksiyonuna şunu ekle:
    await setup_yeni_ozellikler(bot, db_connect, get_settings, set_setting)
  on_message fonksiyonunda, await bot.process_commands(message) satırının
  hemen ÜSTÜNE şunu ekle:
    await caps_lock_kontrol(message)
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
import time

# Bu değişkenler setup_yeni_ozellikler() tarafından doldurulur
_bot = None
_db_connect = None
_get_settings = None
_set_setting = None

# ============================================================
#  LOG KANAL TÜRLERİ
#  Her tür için guild_settings tablosuna ayrı bir sütun ekliyoruz.
#  Tabloya ALTER TABLE ile sütunlar eklenir (yoksa eklenir).
# ============================================================

LOG_TURLERI = {
    "ban":        ("log_ban_ch",        "🔨 Ban/Unban logları"),
    "kick":       ("log_kick_ch",       "👢 Kick logları"),
    "mute":       ("log_mute_ch",       "🔇 Mute/Unmute logları"),
    "uyari":      ("log_uyari_ch",      "⚠️ Uyarı logları"),
    "mesaj":      ("log_mesaj_ch",      "✏️ Mesaj sil/düzenle logları"),
    "uye":        ("log_uye_ch",        "👥 Üye giriş/çıkış logları"),
    "kanal":      ("log_kanal_ch",      "🔒 Kanal kilit/açma logları"),
    "kufur":      ("log_kufur_ch",      "🚫 Küfür & reklam filtre logları"),
    "caps":       ("log_caps_ch",       "🔤 Caps lock filtre logları"),
    "raid":       ("log_raid_ch",       "🚨 Anti-raid logları"),
    "cekilisrol": ("cekilisrol_id",     None),   # kanal değil, rol ID'si
}

# Genel log kanalı anahtarı (eski sistem — fallback olarak kullanılır)
GENEL_LOG_KEY = "log_channel_id"


def _db_log_init():
    """Eksik sütunları guild_settings tablosuna ekler."""
    conn = _db_connect()
    c = conn.cursor()
    for tur, (key, _) in LOG_TURLERI.items():
        try:
            c.execute(f"ALTER TABLE guild_settings ADD COLUMN {key} TEXT")
        except Exception:
            pass   # Sütun zaten varsa hata vermez, devam et
    conn.commit()
    conn.close()


async def log_gonder(guild: discord.Guild, embed: discord.Embed, log_turu: str = None):
    """
    Belirli bir log türü için ayarlı kanala embed gönderir.
    Ayarlı değilse genel log kanalına düşer.
    log_turu: "ban", "kick", "mute", "uyari", "mesaj", "uye",
              "kanal", "kufur", "caps", "raid"
    """
    settings = _get_settings(guild.id)

    kanal_id = None
    if log_turu and log_turu in LOG_TURLERI:
        key = LOG_TURLERI[log_turu][0]
        kanal_id = settings.get(key)

    # Fallback: genel log kanalı
    if not kanal_id:
        kanal_id = settings.get(GENEL_LOG_KEY)

    if not kanal_id:
        return

    ch = guild.get_channel(int(kanal_id))
    if ch:
        try:
            await ch.send(embed=embed)
        except Exception:
            pass


# ============================================================
#  1. CAPS LOCK FİLTRESİ
# ============================================================

CAPS_ESIK = 0.70          # Mesajın %70'i büyük harfse devreye girer
CAPS_MIN_UZUNLUK = 6      # En az 6 karakter olmalı (kısa "LOL" gibi şeyler ignore)

async def caps_lock_kontrol(message: discord.Message):
    """
    on_message içinde çağır → büyük harfli mesajı küçük harfe çevirir.
    """
    if message.author.bot or not message.guild:
        return

    icerik = message.content

    # Komutları, linkleri ve çok kısa mesajları atla
    if icerik.startswith(("!", "/", "http://", "https://")):
        return
    if len(icerik) < CAPS_MIN_UZUNLUK:
        return

    # Sadece harfleri say
    harfler = [c for c in icerik if c.isalpha()]
    if len(harfler) < CAPS_MIN_UZUNLUK:
        return

    buyuk_oran = sum(1 for c in harfler if c.isupper()) / len(harfler)

    if buyuk_oran >= CAPS_ESIK:
        # Mesajı sil ve küçük harfli versiyonunu gönder
        kucuk = icerik.lower()
        try:
            await message.delete()
        except Exception:
            return

        try:
            donusulen = await message.channel.send(
                f"🔤 **{message.author.display_name}:** {kucuk}"
            )
        except Exception:
            return

        # Log gönder
        settings = _get_settings(message.guild.id)
        caps_log_id = settings.get(LOG_TURLERI["caps"][0]) or settings.get(GENEL_LOG_KEY)
        if caps_log_id:
            embed = discord.Embed(
                title="🔤 Caps Lock Filtresi",
                color=discord.Color.yellow()
            )
            embed.add_field(name="Kullanıcı", value=f"{message.author} ({message.author.id})")
            embed.add_field(name="Kanal", value=message.channel.mention)
            embed.add_field(name="Orijinal", value=f"```{icerik[:300]}```", inline=False)
            embed.add_field(name="Düzeltildi", value=f"```{kucuk[:300]}```", inline=False)
            embed.set_footer(text=f"Büyük harf oranı: %{int(buyuk_oran*100)}")
            embed.timestamp = discord.utils.utcnow()
            await log_gonder(message.guild, embed, "caps")


# ============================================================
#  2. DETAYLI LOG SİSTEMİ — /logkanal komutu
# ============================================================

def _register_log_commands(bot: commands.Bot):

    log_group = app_commands.Group(
        name="logkanal",
        description="Log kanallarını türlere göre ayarla (Admin)"
    )

    # ── /logkanal ayarla ──
    @log_group.command(
        name="ayarla",
        description="Bir log türü için kanal ata."
    )
    @app_commands.describe(
        tur="Log türü",
        kanal="Log mesajlarının gönderileceği kanal"
    )
    @app_commands.choices(tur=[
        app_commands.Choice(name="🔨 Ban/Unban",            value="ban"),
        app_commands.Choice(name="👢 Kick",                  value="kick"),
        app_commands.Choice(name="🔇 Mute/Unmute",           value="mute"),
        app_commands.Choice(name="⚠️ Uyarı",                 value="uyari"),
        app_commands.Choice(name="✏️ Mesaj Sil/Düzenle",     value="mesaj"),
        app_commands.Choice(name="👥 Üye Giriş/Çıkış",      value="uye"),
        app_commands.Choice(name="🔒 Kanal Kilit/Açma",      value="kanal"),
        app_commands.Choice(name="🚫 Küfür & Reklam",        value="kufur"),
        app_commands.Choice(name="🔤 Caps Lock",             value="caps"),
        app_commands.Choice(name="🚨 Anti-Raid",             value="raid"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def logkanal_ayarla(
        interaction: discord.Interaction,
        tur: str,
        kanal: discord.TextChannel
    ):
        key = LOG_TURLERI[tur][0]
        _set_setting(interaction.guild.id, key, kanal.id)

        tur_isim = LOG_TURLERI[tur][1] or tur
        embed = discord.Embed(
            title="✅ Log Kanalı Ayarlandı",
            color=discord.Color.green()
        )
        embed.add_field(name="Tür", value=tur_isim)
        embed.add_field(name="Kanal", value=kanal.mention)
        embed.set_footer(text="Artık bu tür loglar bu kanala gidecek.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /logkanal kaldir ──
    @log_group.command(
        name="kaldir",
        description="Bir log türünün özel kanalını kaldır (genel log kanalına döner)."
    )
    @app_commands.describe(tur="Log türü")
    @app_commands.choices(tur=[
        app_commands.Choice(name="🔨 Ban/Unban",            value="ban"),
        app_commands.Choice(name="👢 Kick",                  value="kick"),
        app_commands.Choice(name="🔇 Mute/Unmute",           value="mute"),
        app_commands.Choice(name="⚠️ Uyarı",                 value="uyari"),
        app_commands.Choice(name="✏️ Mesaj Sil/Düzenle",     value="mesaj"),
        app_commands.Choice(name="👥 Üye Giriş/Çıkış",      value="uye"),
        app_commands.Choice(name="🔒 Kanal Kilit/Açma",      value="kanal"),
        app_commands.Choice(name="🚫 Küfür & Reklam",        value="kufur"),
        app_commands.Choice(name="🔤 Caps Lock",             value="caps"),
        app_commands.Choice(name="🚨 Anti-Raid",             value="raid"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def logkanal_kaldir(interaction: discord.Interaction, tur: str):
        key = LOG_TURLERI[tur][0]
        _set_setting(interaction.guild.id, key, None)
        await interaction.response.send_message(
            f"✅ **{LOG_TURLERI[tur][1] or tur}** log kanalı kaldırıldı. Genel log kanalına dönecek.",
            ephemeral=True
        )

    # ── /logkanal goruntule ──
    @log_group.command(
        name="goruntule",
        description="Tüm log kanalı ayarlarını göster."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def logkanal_goruntule(interaction: discord.Interaction):
        settings = _get_settings(interaction.guild.id)

        def ch_str(ch_id):
            if not ch_id:
                return "Ayarlanmamış → Genel log kanalına düşer"
            ch = interaction.guild.get_channel(int(ch_id))
            return ch.mention if ch else f"Silinmiş (ID: {ch_id})"

        genel_log = settings.get(GENEL_LOG_KEY)

        embed = discord.Embed(
            title="📋 Log Kanalı Ayarları",
            description=(
                f"**Genel Log Kanalı (fallback):** "
                f"{ch_str(genel_log) if genel_log else '❌ Ayarlanmamış!'}"
            ),
            color=discord.Color.blurple()
        )

        for tur, (key, aciklama) in LOG_TURLERI.items():
            if aciklama is None:
                continue   # cekilisrol → ayrı gösterilecek
            kanal_id = settings.get(key)
            embed.add_field(
                name=aciklama,
                value=ch_str(kanal_id),
                inline=False
            )

        embed.set_footer(text="/logkanal ayarla komutuyla düzenle • /setup log ile genel log kanalını ayarla")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    bot.tree.add_command(log_group)


# ============================================================
#  3. ÇEKİLİŞ ROLÜ — /cekilisrol
# ============================================================

def _register_cekilisrol_command(bot: commands.Bot):

    @bot.tree.command(
        name="cekilisrol",
        description="Çekiliş başlatabilecek rolü ayarla (Admin)"
    )
    @app_commands.describe(rol="Bu rol çekiliş başlatabilir (boş bırakırsan kaldırılır)")
    @app_commands.checks.has_permissions(administrator=True)
    async def cekilisrol_ayarla(interaction: discord.Interaction, rol: discord.Role = None):
        key = LOG_TURLERI["cekilisrol"][0]
        _set_setting(interaction.guild.id, key, rol.id if rol else None)

        if rol:
            await interaction.response.send_message(
                f"✅ Artık sadece **{rol.mention}** rolüne sahip kişiler çekiliş başlatabilir.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ Çekiliş rol kısıtı kaldırıldı. `manage_guild` izni olan herkes çekiliş başlatabilir.",
                ephemeral=True
            )

    # Çekiliş başlatma yetkisini kontrol eden yardımcı fonksiyon
    # main.py'deki cekilisac komutunu bu fonksiyonla güncelliyoruz
    async def cekilisrol_kontrol(ctx_or_interaction) -> bool:
        """
        True döndürürse kişi çekiliş başlatabilir.
        Bu fonksiyonu kullanmak için aşağıdaki adımları izle.
        """
        if isinstance(ctx_or_interaction, commands.Context):
            guild = ctx_or_interaction.guild
            author = ctx_or_interaction.author
        else:
            guild = ctx_or_interaction.guild
            author = ctx_or_interaction.user

        if author.guild_permissions.administrator:
            return True

        settings = _get_settings(guild.id)
        key = LOG_TURLERI["cekilisrol"][0]
        cekilisrol_id = settings.get(key)

        # Rol ayarlı değilse manage_guild yeterliydi (eski davranış)
        if not cekilisrol_id:
            return author.guild_permissions.manage_guild

        # Rol ayarlıysa o role sahip olmalı
        rol = guild.get_role(int(cekilisrol_id))
        if rol and rol in author.roles:
            return True

        return False

    # bot nesnesine ekle (main.py'den ulaşabilmek için)
    bot.cekilisrol_kontrol = cekilisrol_kontrol


# ============================================================
#  KURULUM FONKSİYONU — main.py'de çağrılır
# ============================================================

async def setup_yeni_ozellikler(
    bot_instance: commands.Bot,
    db_connect_func,
    get_settings_func,
    set_setting_func
):
    """
    main.py → on_ready içine ekle:
        from yeni_ozellikler import setup_yeni_ozellikler, caps_lock_kontrol
        await setup_yeni_ozellikler(bot, db_connect, get_settings, set_setting)

    main.py → on_message içinde, await bot.process_commands(message) ÜSTÜNE:
        await caps_lock_kontrol(message)
    """
    global _bot, _db_connect, _get_settings, _set_setting
    _bot = bot_instance
    _db_connect = db_connect_func
    _get_settings = get_settings_func
    _set_setting = set_setting_func

    _db_log_init()
    _register_log_commands(bot_instance)
    _register_cekilisrol_command(bot_instance)

    print("✅ yeni_ozellikler.py yüklendi: Caps Lock Filtresi, Detaylı Log Sistemi, Çekiliş Rolü")