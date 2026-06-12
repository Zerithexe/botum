# ============================================================
#  main.py — on_message FONKSİYONU DÜZELTİLMİŞ HALİ
#  Sadece on_message fonksiyonunu bu versiyonla değiştir.
#  Geri kalan her şey aynı kalır.
# ============================================================

# ── ADIM 1: En üste şunu ekle ──
# from filtre_muafiyet import filtre_muaf_mi, setup_muafiyet

# ── ADIM 2: on_ready içine ekle (setup_new_systems'ın altına) ──
# await setup_muafiyet(bot, db_connect, get_settings, set_setting)

# ── ADIM 3: on_message'ı aşağıdakiyle değiştir ──

"""
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await antiraid_on_message(message)

    icerik = message.content.lower()

    # AFK kontrolü
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

    # ──────────────────────────────────────────────
    #  MUAFİYET KONTROLÜ — sunucu sahibi, adminler,
    #  moderatörler ve muaf roller filtrelenmez
    # ──────────────────────────────────────────────
    if await filtre_muaf_mi(message.author, message.guild):
        # XP kazanmaya devam eder, sadece filtre uygulanmaz
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
        return
    # ──────────────────────────────────────────────

    # Küfür filtresi
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

    # Reklam filtresi
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

    # XP
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
"""

# ============================================================
#  ÖZET: NE DEĞİŞTİ?
#
#  Eski kod: Herkesin mesajı filtreden geçiyordu.
#
#  Yeni kod: AFK kontrolünden sonra önce muafiyet kontrolü yapılır.
#  Muaf olan kişi (sunucu sahibi / admin / modrole / muafrol):
#    → Filtreler atlanır
#    → XP almaya devam eder
#    → Komutları çalışır
#    → return ile çıkılır, filtre kodlarına hiç girilmez
#
#  YENİ KOMUTLAR:
#    /muafrol ekle   @Rol  → o rolü filtreye takılmaz yapar
#    /muafrol kaldir @Rol  → muafiyeti kaldırır
#    /muafrol liste        → tüm muaf rolleri gösterir
# ============================================================