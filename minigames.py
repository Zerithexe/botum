"""
minigames.py — Zerith Security
Mini Oyun Sistemi: Trivia, Hangman, Wordle, Hızlı Yazma
main.py içine dahil etmek için: from minigames import setup_minigames
on_ready içinde: await setup_minigames(bot) veya bot.add_cog(MinigamesCog(bot))
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import time
from typing import Optional

# ============================================================
#  TRİVİA VERİSİ
# ============================================================

TRIVIA_SORULARI = {
    "🌍 Genel Kültür": [
        {"soru": "Türkiye'nin başkenti neresidir?", "cevap": "ankara", "secenekler": ["İstanbul", "Ankara", "İzmir", "Bursa"]},
        {"soru": "Dünyanın en büyük okyanusu hangisidir?", "cevap": "pasifik", "secenekler": ["Atlantik", "Hint", "Pasifik", "Arktik"]},
        {"soru": "Kaç renk gökkuşağında bulunur?", "cevap": "7", "secenekler": ["5", "6", "7", "8"]},
        {"soru": "Güneş Sistemi'nde kaç gezegen vardır?", "cevap": "8", "secenekler": ["7", "8", "9", "10"]},
        {"soru": "En büyük kıta hangisidir?", "cevap": "asya", "secenekler": ["Afrika", "Asya", "Amerika", "Avrupa"]},
        {"soru": "DNA'nın açılımı nedir?", "cevap": "deoksiribonükleik asit", "secenekler": ["Deoksiribonükleik Asit", "Dinitrojen Asetat", "Dikarboksilik Asit", "Dinükleotid Asidi"]},
        {"soru": "Hangisi bir gezegen değildir?", "cevap": "plüton", "secenekler": ["Mars", "Venüs", "Plüton", "Satürn"]},
        {"soru": "Dünyanın en uzun nehri hangisidir?", "cevap": "nil", "secenekler": ["Amazon", "Nil", "Yangtze", "Mississippi"]},
        {"soru": "Işık hızı yaklaşık kaç km/s'dir?", "cevap": "300.000", "secenekler": ["150.000", "200.000", "300.000", "500.000"]},
        {"soru": "Osmanlı İmparatorluğu hangi yıl kurulmuştur?", "cevap": "1299", "secenekler": ["1071", "1299", "1453", "1517"]},
    ],
    "🎮 Teknoloji": [
        {"soru": "Python hangi yıl geliştirilmeye başlandı?", "cevap": "1989", "secenekler": ["1985", "1989", "1991", "1995"]},
        {"soru": "HTML'nin açılımı nedir?", "cevap": "hypertext markup language", "secenekler": ["Hypertext Markup Language", "High Transfer Markup Link", "Hyper Transfer Mode Language", "Hyperlink Text Making Language"]},
        {"soru": "Discord hangi programlama dili ile yazılmıştır? (arka uç)", "cevap": "elixir", "secenekler": ["Python", "JavaScript", "Elixir", "Go"]},
        {"soru": "İlk iPhone hangi yıl tanıtıldı?", "cevap": "2007", "secenekler": ["2005", "2006", "2007", "2008"]},
        {"soru": "WWW'yi kim icat etti?", "cevap": "tim berners-lee", "secenekler": ["Bill Gates", "Steve Jobs", "Tim Berners-Lee", "Linus Torvalds"]},
        {"soru": "Hangi şirket Android'i geliştirdi?", "cevap": "google", "secenekler": ["Apple", "Microsoft", "Google", "Samsung"]},
        {"soru": "Git'i kim yarattı?", "cevap": "linus torvalds", "secenekler": ["Guido van Rossum", "Linus Torvalds", "James Gosling", "Brendan Eich"]},
        {"soru": "Python'ın yaratıcısı kimdir?", "cevap": "guido van rossum", "secenekler": ["James Gosling", "Guido van Rossum", "Dennis Ritchie", "Bjarne Stroustrup"]},
    ],
    "🎬 Sinema & Dizi": [
        {"soru": "Avengers: Endgame hangi yıl çıktı?", "cevap": "2019", "secenekler": ["2017", "2018", "2019", "2020"]},
        {"soru": "Breaking Bad'de Walter White kim tarafından canlandırılıyor?", "cevap": "bryan cranston", "secenekler": ["Aaron Paul", "Bryan Cranston", "Bob Odenkirk", "Dean Norris"]},
        {"soru": "Titanic filminde Rose'u kim oynuyor?", "cevap": "kate winslet", "secenekler": ["Cate Blanchett", "Kate Winslet", "Natalie Portman", "Julia Roberts"]},
        {"soru": "Game of Thrones kaç sezon sürdü?", "cevap": "8", "secenekler": ["6", "7", "8", "9"]},
        {"soru": "The Dark Knight'ta Joker'i kim oynuyor?", "cevap": "heath ledger", "secenekler": ["Joaquin Phoenix", "Jack Nicholson", "Heath Ledger", "Jared Leto"]},
    ],
    "⚽ Spor": [
        {"soru": "Futbol Dünya Kupası kaç yılda bir düzenlenir?", "cevap": "4", "secenekler": ["2", "3", "4", "5"]},
        {"soru": "En fazla Dünya Kupası kazanan ülke hangisidir?", "cevap": "brezilya", "secenekler": ["Almanya", "İtalya", "Brezilya", "Arjantin"]},
        {"soru": "NBA'de bir takımda kaç oyuncu sahada olur?", "cevap": "5", "secenekler": ["4", "5", "6", "7"]},
        {"soru": "Türkiye'nin en çok şampiyonluk kazanan futbol kulübü hangisidir?", "cevap": "galatasaray", "secenekler": ["Fenerbahçe", "Galatasaray", "Beşiktaş", "Trabzonspor"]},
        {"soru": "Olimpiyat Oyunları kaç yılda bir yapılır?", "cevap": "4", "secenekler": ["2", "3", "4", "5"]},
    ],
    "🔬 Bilim": [
        {"soru": "Suyun kimyasal formülü nedir?", "cevap": "h2o", "secenekler": ["H2O", "CO2", "NaCl", "H2SO4"]},
        {"soru": "Periyodik tabloda demir elementi hangi sembolle gösterilir?", "cevap": "fe", "secenekler": ["Ir", "Fe", "De", "Im"]},
        {"soru": "Işık bir yılda kaç km yol alır? (ışık yılı)", "cevap": "9,46 trilyon km", "secenekler": ["9,46 Trilyon km", "1 Milyar km", "100 Milyar km", "1 Trilyon km"]},
        {"soru": "İnsan vücudunda kaç kemik vardır?", "cevap": "206", "secenekler": ["180", "195", "206", "215"]},
        {"soru": "Hangi element en hafif elementtir?", "cevap": "hidrojen", "secenekler": ["Helyum", "Lityum", "Hidrojen", "Berilyum"]},
    ],
}

# ============================================================
#  HANGMAN VERİSİ
# ============================================================

HANGMAN_KELIMELER = {
    "🐾 Hayvanlar": [
        ("aslan", "Afrika savanalarının kralı"),
        ("yunus", "Zeki ve sosyal bir deniz memelisi"),
        ("kartal", "Gökyüzünün hükümdarı"),
        ("timsah", "Nil nehrinin tehlikeli sakini"),
        ("penguen", "Güney Kutbu'nun şık yerlisi"),
        ("kanguru", "Avustralya'nın zıplayan ikonu"),
        ("zürafa", "Dünyanın en uzun boyunlu hayvanı"),
        ("ahtapot", "Sekiz kollu zeki deniz canlısı"),
        ("leopar", "Süratli ve benekli büyük kedi"),
        ("bufalo", "Step ve ovalarda yaşayan iri memeli"),
    ],
    "🍕 Yiyecekler": [
        ("lahmacun", "Türk mutfağının ince hamurlu lezzeti"),
        ("baklava", "Şerbetli ve fıstıklı tatlı"),
        ("mantı", "Küçük hamur işi, yoğurtla servis"),
        ("kebap", "Izgara et yemeği"),
        ("sarma", "Yaprak içinde pilav ve et"),
        ("börek", "Yufkadan yapılan çıtır hamur işi"),
        ("pilav", "Temel Türk garnitürü"),
        ("çorba", "Sıcak ve besleyici sıvı yemek"),
        ("kadayıf", "Tel tel şerbetli tatlı"),
        ("lokma", "Yağda kızartılmış şerbetli hamur"),
    ],
    "🌍 Ülkeler": [
        ("japonya", "Güneşin doğduğu ülke"),
        ("brezilya", "Samba ve futbolun ülkesi"),
        ("avustralya", "Kanguru ve koala yurdu"),
        ("norveç", "Kuzey ışıklarının ülkesi"),
        ("meksika", "Tacos ve mariachi"),
        ("hindistan", "Baharat ve Tac Mahal"),
        ("misir", "Piramitler ve firavunlar"),
        ("arjantin", "Tango ve Messi'nin ülkesi"),
        ("isviçre", "Çikolata ve saatler"),
        ("portekiz", "Kristiano'nun ülkesi"),
    ],
    "💻 Teknoloji": [
        ("algoritma", "Bir problemi çözme adımları"),
        ("veritabanı", "Verilerin organize edildiği sistem"),
        ("yazılım", "Bilgisayar programları bütünü"),
        ("internet", "Küresel ağ sistemi"),
        ("siber", "Dijital dünyayla ilgili sıfat"),
        ("sunucu", "Hizmet sunan bilgisayar sistemi"),
        ("şifreleme", "Veriyi gizli hale getirme"),
        ("ağ", "Birbirine bağlı sistemler"),
        ("uygulama", "Belirli amaçlı program"),
        ("donanım", "Bilgisayarın fiziksel parçaları"),
    ],
}

HANGMAN_ASAMALARI = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]

# ============================================================
#  WORDLE VERİSİ (5 harfli Türkçe kelimeler)
# ============================================================

WORDLE_KELIMELER = [
    "kalem", "kitap", "araba", "köpek", "kuzey",
    "deniz", "bulut", "şeker", "güneş", "yıldız",
    "çiçek", "ağaç", "taşıt", "bilgi", "sanat",
    "müzik", "resim", "oyun", "spor", "yazı",
    "renk", "ışık", "hava", "toprak", "ateş",
    "kılıç", "kalın", "uzak", "yakın", "erken",
    "geç", "hızlı", "yavaş", "büyük", "küçük",
    "soğuk", "sıcak", "tatlı", "acı", "tuzlu",
    "yukarı", "aşağı", "sağ", "sol", "orta",
    "başlık", "sayfa", "kelime", "cümle", "paragraf",
]

# ============================================================
#  HIZLI YAZMA VERİSİ
# ============================================================

YAZMACUMLELER = [
    "Hızlı kahverengi tilki tembel köpeğin üzerinden atladı",
    "Discord botları sunucu yönetimini kolaylaştırır",
    "Python öğrenmek programcılık yolculuğunun başlangıcıdır",
    "Zerith Security sunucunuzu güvende tutar",
    "Türkiye güzel bir ülkedir ve tarihi çok zengindir",
    "Bilgisayarlar insanların hayatını kolaylaştırmaktadır",
    "Oyun oynamak hem eğlenceli hem de yetenekleri geliştirir",
    "Discord sunucularında moderasyon çok önemlidir",
    "Yazılım geliştirme sabır ve pratik gerektiren bir beceridir",
    "İnternet dünyayı küçük bir köye dönüştürmüştür",
]

# ============================================================
#  AKTİF OYUN TAKİBİ
# ============================================================

aktif_oyunlar = {}  # channel_id -> oyun bilgisi

# ============================================================
#  TRİVİA KOMUTLARI
# ============================================================

class TriviaView(discord.ui.View):
    def __init__(self, soru_data: dict, dogru_cevap: str, oyun_id: str):
        super().__init__(timeout=20)
        self.dogru_cevap = dogru_cevap
        self.oyun_id = oyun_id
        self.cevap_verenler = set()
        self.bitti = False

        emojiler = ["🇦", "🇧", "🇨", "🇩"]
        secenekler = soru_data["secenekler"][:]
        random.shuffle(secenekler)
        self.secenekler = secenekler

        for i, secenek in enumerate(secenekler):
            btn = discord.ui.Button(
                label=f"{emojiler[i]} {secenek}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_{i}"
            )
            btn.callback = self.make_callback(secenek, emojiler[i])
            self.add_item(btn)

    def make_callback(self, secenek: str, emoji: str):
        async def callback(interaction: discord.Interaction):
            if self.bitti:
                return await interaction.response.send_message("⏱️ Süre doldu!", ephemeral=True)
            if interaction.user.id in self.cevap_verenler:
                return await interaction.response.send_message("❌ Zaten cevap verdin!", ephemeral=True)

            self.cevap_verenler.add(interaction.user.id)
            dogru = secenek.lower() == self.dogru_cevap.lower()

            if dogru:
                try:
                    from __main__ import eco_add_coins
                    eco_add_coins(interaction.user.id, interaction.guild.id, 50)
                except Exception:
                    pass
                await interaction.response.send_message(
                    f"✅ **Doğru!** {emoji} `{secenek}` — **+50 🪙** kazandın!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **Yanlış!** Seçtiğin: {emoji} `{secenek}`",
                    ephemeral=True
                )
        return callback


async def trivia_gonder(ctx_or_channel, kategori: str = None):
    """Trivia sorusu gönder"""
    if kategori and kategori not in TRIVIA_SORULARI:
        kategori = None

    if not kategori:
        kategori = random.choice(list(TRIVIA_SORULARI.keys()))

    soru_data = random.choice(TRIVIA_SORULARI[kategori])

    embed = discord.Embed(
        title=f"🎯 Trivia — {kategori}",
        description=f"## {soru_data['soru']}",
        color=discord.Color.blurple()
    )
    embed.set_footer(text="⏱️ 20 saniyeniz var! Doğru cevap = +50 🪙")

    oyun_id = str(time.time())
    view = TriviaView(soru_data, soru_data["cevap"], oyun_id)

    if isinstance(ctx_or_channel, commands.Context):
        msg = await ctx_or_channel.send(embed=embed, view=view)
    else:
        msg = await ctx_or_channel.send(embed=embed, view=view)

    await asyncio.sleep(20)
    view.bitti = True
    view.stop()

    result_embed = discord.Embed(
        title=f"⏰ Süre Doldu — {kategori}",
        description=f"**Soru:** {soru_data['soru']}\n**✅ Doğru Cevap:** `{soru_data['secenekler'][0] if soru_data['cevap'].lower() == soru_data['secenekler'][0].lower() else next(s for s in soru_data['secenekler'] if s.lower() == soru_data['cevap'].lower())}`",
        color=discord.Color.green()
    )
    result_embed.add_field(name="Katılımcı Sayısı", value=str(len(view.cevap_verenler)))

    for item in view.children:
        if hasattr(item, 'label') and soru_data["cevap"].lower() in item.label.lower():
            item.style = discord.ButtonStyle.success
        else:
            item.style = discord.ButtonStyle.danger
        item.disabled = True

    try:
        await msg.edit(embed=result_embed, view=view)
    except Exception:
        pass


# ============================================================
#  HANGMAN OYUNU
# ============================================================

class HangmanGame:
    def __init__(self, kelime: str, ipucu: str, kategori: str):
        self.kelime = kelime.lower()
        self.ipucu = ipucu
        self.kategori = kategori
        self.tahminler = set()
        self.yanlis = 0
        self.max_yanlis = 6

    @property
    def bitti_mi(self):
        return self.kazandi_mi or self.kaybetti_mi

    @property
    def kazandi_mi(self):
        return all(h in self.tahminler for h in self.kelime if h != " ")

    @property
    def kaybetti_mi(self):
        return self.yanlis >= self.max_yanlis

    @property
    def gosterge(self):
        return " ".join(
            h if (h in self.tahminler or h == " ") else "\_"
            for h in self.kelime
        )

    def tahmin_et(self, harf: str) -> str:
        harf = harf.lower()
        if harf in self.tahminler:
            return "tekrar"
        self.tahminler.add(harf)
        if harf not in self.kelime:
            self.yanlis += 1
            return "yanlis"
        return "dogru"

    def embed_olustur(self) -> discord.Embed:
        if self.kazandi_mi:
            renk = discord.Color.green()
            baslik = "🎉 Kazandın!"
        elif self.kaybetti_mi:
            renk = discord.Color.red()
            baslik = "💀 Kaybettin!"
        else:
            renk = discord.Color.blurple()
            baslik = f"🪢 Adam Asmaca — {self.kategori}"

        embed = discord.Embed(title=baslik, color=renk)
        embed.add_field(name="Adam", value=HANGMAN_ASAMALARI[self.yanlis], inline=False)
        embed.add_field(name="Kelime", value=f"`{self.gosterge}`", inline=False)
        embed.add_field(name="💡 İpucu", value=self.ipucu)
        embed.add_field(name=f"❌ Yanlış ({self.yanlis}/{self.max_yanlis})",
                        value=" ".join(f"`{h}`" for h in sorted(self.tahminler) if h not in self.kelime) or "—")

        if self.kaybetti_mi:
            embed.add_field(name="Kelime", value=f"**{self.kelime.upper()}**", inline=False)

        embed.set_footer(text="Harf tahmin etmek için mesaj yaz!")
        return embed


# ============================================================
#  WORDLE OYUNU
# ============================================================

class WordleGame:
    def __init__(self, kelime: str):
        self.kelime = kelime.lower()
        self.tahminler = []
        self.max_tahmin = 6
        self.bitti = False
        self.kazandi = False

    def tahmin_et(self, tahmin: str) -> list:
        tahmin = tahmin.lower()
        if len(tahmin) != len(self.kelime):
            return None

        sonuc = []
        kelime_list = list(self.kelime)

        for i, harf in enumerate(tahmin):
            if harf == self.kelime[i]:
                sonuc.append(("✅", harf))
                kelime_list[i] = None
            elif harf in kelime_list:
                sonuc.append(("🟨", harf))
                kelime_list[kelime_list.index(harf)] = None
            else:
                sonuc.append(("⬛", harf))

        self.tahminler.append((tahmin, sonuc))

        if tahmin == self.kelime:
            self.kazandi = True
            self.bitti = True
        elif len(self.tahminler) >= self.max_tahmin:
            self.bitti = True

        return sonuc

    def embed_olustur(self) -> discord.Embed:
        if self.kazandi:
            renk = discord.Color.green()
            baslik = f"🎉 Kazandın! ({len(self.tahminler)}/{self.max_tahmin})"
        elif self.bitti:
            renk = discord.Color.red()
            baslik = f"💀 Kaybettin! Kelime: **{self.kelime.upper()}**"
        else:
            renk = discord.Color.blurple()
            baslik = f"🟩 Wordle ({len(self.tahminler)}/{self.max_tahmin})"

        embed = discord.Embed(title=baslik, color=renk)

        tahmin_satirlari = []
        for tahmin, sonuc in self.tahminler:
            satir = " ".join(emoji for emoji, _ in sonuc)
            harfler = " ".join(f"`{h.upper()}`" for _, h in sonuc)
            tahmin_satirlari.append(f"{satir}\n{harfler}")

        for _ in range(self.max_tahmin - len(self.tahminler)):
            tahmin_satirlari.append("⬜ ⬜ ⬜ ⬜ ⬜")

        embed.description = "\n\n".join(tahmin_satirlari)
        embed.add_field(name="Efsane", value="✅ Doğru  🟨 Yanlış yer  ⬛ Yok", inline=False)

        if not self.bitti:
            embed.set_footer(text=f"5 harfli bir kelime yaz! ({self.max_tahmin - len(self.tahminler)} hakkın kaldı)")

        return embed


# ============================================================
#  HIZLI YAZMA OYUNU
# ============================================================

class HizliYazmaGame:
    def __init__(self, cumle: str):
        self.cumle = cumle
        self.baslangi_zamani = None
        self.bitti = False
        self.ilk_bitiren = None
        self.sure = None

    def baslat(self):
        self.baslangi_zamani = time.time()

    def kontrol_et(self, metin: str, user) -> bool:
        if metin.strip().lower() == self.cumle.lower():
            if not self.bitti:
                self.bitti = True
                self.ilk_bitiren = user
                self.sure = round(time.time() - self.baslangi_zamani, 2)
                return True
        return False


# ============================================================
#  COG SINIFI
# ============================================================

class MinigamesCog(commands.Cog, name="Mini Oyunlar"):
    def __init__(self, bot):
        self.bot = bot
        self.aktif_hangman = {}   # channel_id -> HangmanGame
        self.aktif_wordle = {}    # (channel_id, user_id) -> WordleGame
        self.aktif_yazi = {}      # channel_id -> HizliYazmaGame

    # --------------------------------------------------------
    #  TRİVİA
    # --------------------------------------------------------

    @commands.command(name="trivia", aliases=["quiz"])  # "bilgi" alias'ı kaldırıldı — çakışma vardı
    async def trivia_cmd(self, ctx, *, kategori: str = None):
        """Trivia sorusu başlat. Kategori: genel, teknoloji, sinema, spor, bilim"""
        kat_map = {
            "genel": "🌍 Genel Kültür",
            "teknoloji": "🎮 Teknoloji",
            "sinema": "🎬 Sinema & Dizi",
            "spor": "⚽ Spor",
            "bilim": "🔬 Bilim",
        }
        if kategori:
            kategori = kat_map.get(kategori.lower())

        await trivia_gonder(ctx, kategori)

    @commands.command(name="triviakatego", aliases=["triviacat"])
    async def trivia_kategoriler(self, ctx):
        """Trivia kategorilerini listele"""
        embed = discord.Embed(title="🎯 Trivia Kategorileri", color=discord.Color.blurple())
        for kat, sorular in TRIVIA_SORULARI.items():
            embed.add_field(name=kat, value=f"`{len(sorular)} soru`")
        embed.set_footer(text="Kullanım: !trivia [kategori]  •  Örnek: !trivia teknoloji")
        await ctx.send(embed=embed)

    # --------------------------------------------------------
    #  HANGMAN
    # --------------------------------------------------------

    @commands.command(name="hangman", aliases=["adamasmaca", "asmaca"])
    async def hangman_cmd(self, ctx, *, kategori: str = None):
        """Adam asmaca oyunu başlat"""
        if ctx.channel.id in self.aktif_hangman:
            oyun = self.aktif_hangman[ctx.channel.id]
            if not oyun.bitti_mi:
                return await ctx.send("❌ Bu kanalda zaten aktif bir hangman oyunu var! Önce onu bitirin.")

        kat_map = {
            "hayvan": "🐾 Hayvanlar",
            "yiyecek": "🍕 Yiyecekler",
            "ülke": "🌍 Ülkeler",
            "teknoloji": "💻 Teknoloji",
        }
        seçilen_kat = kat_map.get(kategori.lower() if kategori else "", None)
        if not seçilen_kat:
            seçilen_kat = random.choice(list(HANGMAN_KELIMELER.keys()))

        kelime, ipucu = random.choice(HANGMAN_KELIMELER[seçilen_kat])
        oyun = HangmanGame(kelime, ipucu, seçilen_kat)
        self.aktif_hangman[ctx.channel.id] = oyun

        embed = oyun.embed_olustur()
        embed.set_author(name=f"{ctx.author.display_name} başlattı", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Hangman harf kontrolü
        if message.channel.id in self.aktif_hangman:
            oyun = self.aktif_hangman[message.channel.id]
            if not oyun.bitti_mi:
                icerik = message.content.strip().lower()
                if len(icerik) == 1 and icerik.isalpha():
                    sonuc = oyun.tahmin_et(icerik)

                    if sonuc == "tekrar":
                        await message.add_reaction("🔄")
                        return

                    embed = oyun.embed_olustur()
                    embed.set_author(
                        name=f"{message.author.display_name} → '{icerik.upper()}'",
                        icon_url=message.author.display_avatar.url
                    )

                    if sonuc == "yanlis":
                        await message.add_reaction("❌")
                    else:
                        await message.add_reaction("✅")

                    await message.channel.send(embed=embed)

                    if oyun.kazandi_mi:
                        try:
                            from __main__ import eco_add_coins
                            eco_add_coins(message.author.id, message.guild.id, 100)
                        except Exception:
                            pass
                        await message.channel.send(
                            f"🎉 {message.author.mention} kelimeyi buldu: **{oyun.kelime.upper()}** — **+100 🪙**!"
                        )
                        del self.aktif_hangman[message.channel.id]

                    elif oyun.kaybetti_mi:
                        await message.channel.send(
                            f"💀 Kimse bulamadı! Kelime: **{oyun.kelime.upper()}**"
                        )
                        del self.aktif_hangman[message.channel.id]

        # Wordle tahmin kontrolü
        key = (message.channel.id, message.author.id)
        if key in self.aktif_wordle:
            oyun = self.aktif_wordle[key]
            if not oyun.bitti:
                icerik = message.content.strip().lower()
                if len(icerik) == 5 and icerik.isalpha():
                    sonuc = oyun.tahmin_et(icerik)
                    if sonuc is not None:
                        embed = oyun.embed_olustur()
                        await message.channel.send(embed=embed)

                        if oyun.bitti:
                            if oyun.kazandi:
                                odul = max(150 - (len(oyun.tahminler) - 1) * 20, 50)
                                try:
                                    from __main__ import eco_add_coins
                                    eco_add_coins(message.author.id, message.guild.id, odul)
                                except Exception:
                                    pass
                                await message.channel.send(
                                    f"🎉 {message.author.mention} **{len(oyun.tahminler)}** tahminde buldu! **+{odul} 🪙**"
                                )
                            del self.aktif_wordle[key]

        # Hızlı yazma kontrolü
        if message.channel.id in self.aktif_yazi:
            oyun = self.aktif_yazi[message.channel.id]
            if not oyun.bitti and oyun.baslangi_zamani:
                if oyun.kontrol_et(message.content, message.author):
                    try:
                        from __main__ import eco_add_coins
                        eco_add_coins(message.author.id, message.guild.id, 75)
                    except Exception:
                        pass
                    embed = discord.Embed(
                        title="⌨️ Yarış Bitti!",
                        description=f"🏆 {message.author.mention} kazandı!\n**Süre:** {oyun.sure} saniye\n**+75 🪙** kazandı!",
                        color=discord.Color.gold()
                    )
                    hiz = len(oyun.cumle.split()) / (oyun.sure / 60)
                    embed.add_field(name="⚡ Yazma Hızı", value=f"{hiz:.0f} kelime/dakika")
                    await message.channel.send(embed=embed)
                    del self.aktif_yazi[message.channel.id]

    # --------------------------------------------------------
    #  WORDLE
    # --------------------------------------------------------

    @commands.command(name="wordle")
    async def wordle_cmd(self, ctx):
        """Wordle oyunu başlat (5 harfli kelime bul)"""
        key = (ctx.channel.id, ctx.author.id)
        if key in self.aktif_wordle and not self.aktif_wordle[key].bitti:
            oyun = self.aktif_wordle[key]
            embed = oyun.embed_olustur()
            embed.set_footer(text="Zaten aktif bir oyunun var! Devam ediyor...")
            return await ctx.send(embed=embed)

        kelime = random.choice(WORDLE_KELIMELER)
        oyun = WordleGame(kelime)
        self.aktif_wordle[key] = oyun

        embed = discord.Embed(
            title="🟩 Wordle Başladı!",
            description="⬜ ⬜ ⬜ ⬜ ⬜\n⬜ ⬜ ⬜ ⬜ ⬜\n⬜ ⬜ ⬜ ⬜ ⬜\n⬜ ⬜ ⬜ ⬜ ⬜\n⬜ ⬜ ⬜ ⬜ ⬜\n⬜ ⬜ ⬜ ⬜ ⬜",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Nasıl oynanır?", value="5 harfli bir kelime yaz!\n✅ Doğru harf, doğru yer\n🟨 Doğru harf, yanlış yer\n⬛ Harf yok", inline=False)
        embed.add_field(name="Efsane", value="✅ Doğru  🟨 Yanlış yer  ⬛ Yok", inline=False)
        embed.set_footer(text="6 hakkın var! Ödül: 150🪙 (1. tahmin) → 50🪙 (6. tahmin)")
        await ctx.send(embed=embed)

    @commands.command(name="wordleiptal", aliases=["wordlecancel"])
    async def wordle_iptal(self, ctx):
        """Aktif Wordle oyununu iptal et"""
        key = (ctx.channel.id, ctx.author.id)
        if key in self.aktif_wordle:
            oyun = self.aktif_wordle[key]
            del self.aktif_wordle[key]
            await ctx.send(f"🛑 Wordle iptal edildi. Kelime: **{oyun.kelime.upper()}**")
        else:
            await ctx.send("❌ Aktif Wordle oyunun yok.")

    # --------------------------------------------------------
    #  HIZLI YAZMA
    # --------------------------------------------------------

    @commands.command(name="yaz", aliases=["hızlıyaz", "yazma", "typing"])
    async def hizli_yazma(self, ctx):
        """Hızlı yazma yarışması başlat"""
        if ctx.channel.id in self.aktif_yazi:
            return await ctx.send("❌ Bu kanalda zaten aktif bir yazma yarışması var!")

        cumle = random.choice(YAZMACUMLELER)
        oyun = HizliYazmaGame(cumle)
        self.aktif_yazi[ctx.channel.id] = oyun

        embed = discord.Embed(
            title="⌨️ Hızlı Yazma Yarışması!",
            description="Hazır olun...",
            color=discord.Color.orange()
        )
        embed.set_footer(text="3 saniye sonra cümle gösterilecek!")
        msg = await ctx.send(embed=embed)

        for i in range(3, 0, -1):
            await asyncio.sleep(1)
            await msg.edit(embed=discord.Embed(
                title="⌨️ Hazır mısın?",
                description=f"**{i}...**",
                color=discord.Color.orange()
            ))

        oyun.baslat()
        embed = discord.Embed(
            title="⌨️ YAZI!",
            description=f"```\n{cumle}\n```",
            color=discord.Color.green()
        )
        embed.set_footer(text="Tam olarak yukarıdaki cümleyi yaz! • Ödül: +75 🪙")
        await msg.edit(embed=embed)

        await asyncio.sleep(60)
        if ctx.channel.id in self.aktif_yazi and not oyun.bitti:
            del self.aktif_yazi[ctx.channel.id]
            await ctx.send("⏰ Süre doldu! Kimse yazamadı.")

    # --------------------------------------------------------
    #  SLASH KOMUTLARI
    # --------------------------------------------------------

    @app_commands.command(name="trivia", description="Trivia sorusu başlat.")
    @app_commands.describe(kategori="Kategori (genel/teknoloji/sinema/spor/bilim)")
    @app_commands.choices(kategori=[
        app_commands.Choice(name="🌍 Genel Kültür", value="genel"),
        app_commands.Choice(name="🎮 Teknoloji", value="teknoloji"),
        app_commands.Choice(name="🎬 Sinema & Dizi", value="sinema"),
        app_commands.Choice(name="⚽ Spor", value="spor"),
        app_commands.Choice(name="🔬 Bilim", value="bilim"),
    ])
    async def slash_trivia(self, interaction: discord.Interaction, kategori: str = None):
        kat_map = {
            "genel": "🌍 Genel Kültür",
            "teknoloji": "🎮 Teknoloji",
            "sinema": "🎬 Sinema & Dizi",
            "spor": "⚽ Spor",
            "bilim": "🔬 Bilim",
        }
        await interaction.response.send_message("🎯 Trivia başlatılıyor...", ephemeral=True)
        await trivia_gonder(interaction.channel, kat_map.get(kategori) if kategori else None)

    @app_commands.command(name="hangman", description="Adam asmaca oyunu başlat.")
    @app_commands.describe(kategori="Kategori (hayvan/yiyecek/ülke/teknoloji)")
    @app_commands.choices(kategori=[
        app_commands.Choice(name="🐾 Hayvanlar", value="hayvan"),
        app_commands.Choice(name="🍕 Yiyecekler", value="yiyecek"),
        app_commands.Choice(name="🌍 Ülkeler", value="ülke"),
        app_commands.Choice(name="💻 Teknoloji", value="teknoloji"),
    ])
    async def slash_hangman(self, interaction: discord.Interaction, kategori: str = None):
        ctx = await commands.Context.from_interaction(interaction)
        await self.hangman_cmd(ctx, kategori=kategori)

    @app_commands.command(name="wordle", description="Wordle oyunu başlat (5 harfli kelime bul).")
    async def slash_wordle(self, interaction: discord.Interaction):
        ctx = await commands.Context.from_interaction(interaction)
        await self.wordle_cmd(ctx)

    @app_commands.command(name="yaz", description="Hızlı yazma yarışması başlat.")
    async def slash_yaz(self, interaction: discord.Interaction):
        ctx = await commands.Context.from_interaction(interaction)
        await self.hizli_yazma(ctx)

    # --------------------------------------------------------
    #  OYUNLAR YARDIM
    # --------------------------------------------------------

    @commands.command(name="oyunlar", aliases=["games", "minigames"])
    async def oyunlar_yardim(self, ctx):
        """Mini oyunlar listesi"""
        embed = discord.Embed(
            title="🎮 Mini Oyunlar",
            description="Tüm oyunlar hem `!` hem `/` ile kullanılabilir.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🎯 Trivia — Bilgi Yarışması",
            value="`!trivia [kategori]` — Çoktan seçmeli soru\nKategoriler: `genel` `teknoloji` `sinema` `spor` `bilim`\n💰 Ödül: +50 🪙",
            inline=False
        )
        embed.add_field(
            name="🪢 Hangman — Adam Asmaca",
            value="`!hangman [kategori]` — Harf harf kelime bul\nKategoriler: `hayvan` `yiyecek` `ülke` `teknoloji`\n💰 Ödül: +100 🪙 (bulan kişiye)",
            inline=False
        )
        embed.add_field(
            name="🟩 Wordle — Kelime Bul",
            value="`!wordle` — 6 tahminde 5 harfli kelimeyi bul\n`!wordleiptal` — Oyunu iptal et\n💰 Ödül: 50-150 🪙 (tahmin sayısına göre)",
            inline=False
        )
        embed.add_field(
            name="⌨️ Hızlı Yazma",
            value="`!yaz` — Cümleyi en hızlı kim yazar?\n💰 Ödül: +75 🪙",
            inline=False
        )
        embed.set_footer(text="Tüm oyunlar ekonomi sistemiyle entegre!")
        await ctx.send(embed=embed)


# ============================================================
#  KURULUM FONKSİYONU
# ============================================================

async def setup_minigames(bot: commands.Bot):
    """main.py'deki on_ready içinde çağır: await setup_minigames(bot)"""
    await bot.add_cog(MinigamesCog(bot))
    print("✅ Mini oyunlar modülü yüklendi!")