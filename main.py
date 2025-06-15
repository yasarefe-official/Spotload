# -*- coding: utf-8 -*-

"""
Gelişmiş Spotify Downloader Telegram Botu v2.0

Bu bot, Spotify parça, albüm ve playlist linklerini MP3 olarak indirir.
Ayrıca '/search' komutuyla isimle arama yapma özelliğine de sahiptir.
Render.com üzerinde 7/24 çalışmak üzere tasarlanmıştır.

Kurulum:
1. Bu kodu main.py olarak kaydedin.
2. requirements.txt dosyası oluşturup içine aşağıdaki iki satırı ekleyin:
   python-telegram-bot
   spotdl
3. Bu iki dosyayı bir GitHub repository'sine yükleyin.
4. Render.com'da "Background Worker" olarak bu repository'yi bağlayın.
5. Gerekli Environment Variable'ları (Secrets) Render'da ayarlayın.
"""

import os
import asyncio
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from spotdl import Spotdl
from spotdl.types.song import Song

# 1. Logging (Günlük Kaydı) Ayarları
# Botun çalışırken ne yaptığını ve olası hataları görmek için kullanılır.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. Ortam Değişkenlerini (Secrets) Yükleme
# Bu değişkenler Render.com'un "Environment" sekmesinden okunur.
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Değişkenlerin varlığını kontrol et, yoksa botu başlatma.
if not all([TELEGRAM_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET]):
    logger.critical("Kritik Hata: Lütfen Render 'Environment' bölümünde gerekli tüm değişkenleri ayarlayın (TELEGRAM_BOT_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET).")
    raise ValueError("Ortam değişkenleri eksik. Bot başlatılamıyor.")

# 3. Genel Ayarlar ve spotdl İstemcisini Başlatma
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

try:
    spotdl_client = Spotdl(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user_auth=False,
        output=str(DOWNLOAD_DIR),
        log_level=logging.ERROR  # spotdl'ın kendi loglarını azaltır, sadece hataları gösterir.
    )
    logger.info("Spotdl istemcisi başarıyla başlatıldı.")
except Exception as e:
    logger.critical(f"Spotdl istemcisi başlatılamadı! Hata: {e}")
    # spotdl başlatılamazsa botun bir anlamı kalmaz, None olarak ayarlıyoruz.
    spotdl_client = None

# 4. Yardımcı Fonksiyonlar
async def send_song(update: Update, context: ContextTypes.DEFAULT_TYPE, song: Song) -> bool:
    """
    Tek bir şarkıyı indirir, kullanıcıya gönderir ve sunucudan temizler.
    Bu fonksiyon, kod tekrarını önlemek için kullanılır.
    Başarılı olursa True, başarısız olursa False döndürür.
    """
    message = await update.effective_chat.send_message(
        text=f"⬇️ İndiriliyor: *{song.name} - {song.artist}*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        # spotdl.download bloklayan bir işlem olduğu için ayrı bir thread'de çalıştırılır.
        # Bu, botun indirme sırasında donmasını engeller.
        result = await asyncio.to_thread(spotdl_client.download, song)
        
        if not result or not result[0][1] or not result[0][1].exists():
            await message.edit_text(f"❌ İndirme başarısız oldu: *{song.name}*", parse_mode=ParseMode.MARKDOWN)
            return False

        file_path = result[0][1]

        if file_path.stat().st_size > 50 * 1024 * 1024: # 50 MB Telegram limiti
            await message.edit_text(f"⚠️ Dosya çok büyük (>50MB): *{song.name}*", parse_mode=ParseMode.MARKDOWN)
            file_path.unlink()
            return False

        await message.edit_text(f"📤 Yükleniyor: *{song.name}*", parse_mode=ParseMode.MARKDOWN)
        
        with open(file_path, 'rb') as audio_file:
            await update.effective_chat.send_audio(
                audio=audio_file,
                title=song.name,
                performer=song.artist,
                duration=int(song.duration)
            )
        
        await message.delete()
        file_path.unlink()  # Dosyayı sunucudan sil
        return True

    except Exception as e:
        logger.error(f"send_song fonksiyonunda hata oluştu: {song.name} - {e}", exc_info=True)
        await message.edit_text(f"❌ '{song.name}' gönderilirken bir hata oluştu.", parse_mode=ParseMode.MARKDOWN)
        return False

# 5. Telegram Komut İşleyicileri (Handlers)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutuna hoş geldin mesajı ile yanıt verir."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Merhaba {user.mention_html()}!",
        text=(
            "🎵 Spotify İndirme Botuna Hoş Geldin!\n\n"
            "Bana bir Spotify **parça, albüm veya playlist** linki gönder.\n\n"
            "Veya bir şarkı aramak için `/search <şarkı adı>` komutunu kullan."
        )
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help komutuna yardım menüsü ile yanıt verir."""
    await update.message.reply_text(
        "ℹ️ **YARDIM MENÜSÜ**\n\n"
        "1. **Link ile İndirme:**\n"
        "İndirmek istediğiniz Spotify parça, albüm veya playlist linkini kopyalayıp sohbete yapıştırın. Gerisini ben hallederim.\n\n"
        "2. **Arama Yaparak İndirme:**\n"
        "`/search sanatçı - şarkı adı` şeklinde bir komut göndererek arama yapabilirsiniz.\n\n"
        "*Örnek:* `/search Tarkan - Kuzu Kuzu`",
        parse_mode=ParseMode.MARKDOWN
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/search komutu ile verilen metni Spotify'da arar ve ilk sonucu indirir."""
    if not context.args:
        await update.message.reply_text("Lütfen aramak istediğiniz şarkının adını girin.\n*Örnek:* `/search Duman - Senden Daha Güzel`", parse_mode=ParseMode.MARKDOWN)
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔎 Aranıyor: *{query}*", parse_mode=ParseMode.MARKDOWN)

    try:
        songs = spotdl_client.search([query])
        if not songs:
            await update.message.reply_text("❌ Bu arama için sonuç bulunamadı.")
            return

        await send_song(update, context, songs[0])

    except Exception as e:
        logger.error(f"Arama komutunda hata: {e}", exc_info=True)
        await update.message.reply_text("❌ Arama sırasında beklenmedik bir hata oluştu.")

async def handle_link_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Spotify linki içeren mesajları işler."""
    if not spotdl_client:
        await update.message.reply_text("❌ Bot hatası: İndirme servisi şu an aktif değil. Lütfen daha sonra tekrar deneyin.")
        return

    url = update.message.text.strip()
    await update.message.reply_text("🔗 Link algılandı, içerik aranıyor...")

    try:
        songs = spotdl_client.search([url])
        if not songs:
            await update.message.reply_text("❌ Link içeriği bulunamadı veya link geçersiz.")
            return

        count = len(songs)
        item_type = "şarkı"
        if count > 1:
            item_type = "şarkı (playlist/albüm)"
            
        await update.message.reply_text(f"✅ Toplam {count} adet {item_type} bulundu. Şarkılar sırayla gönderilecek, bu işlem biraz sürebilir...")
        
        success_count = 0
        for i, song in enumerate(songs, 1):
            logger.info(f"İşleniyor: {i}/{count} - {song.name}")
            if await send_song(update, context, song):
                success_count += 1
            await asyncio.sleep(1) # Telegram API limitlerine takılmamak için 1 saniye bekle
        
        await update.message.reply_text(f"✅ İşlem tamamlandı! Toplam {count} şarkıdan {success_count} tanesi başarıyla gönderildi.")

    except Exception as e:
        logger.error(f"Link işleme hatası: {e}", exc_info=True)
        await update.message.reply_text("❌ Link işlenirken beklenmedik bir hata oluştu.")

# 6. Ana Fonksiyon: Botu Başlatma ve Çalıştırma
def main() -> None:
    """Botu başlatır ve gelen isteklere göre ilgili fonksiyonları çalıştırır."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Farklı komutlar için handler'ları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))

    # Spotify linki içeren (ama komut olmayan) mesajlar için handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.Entity("url") | filters.Entity("text_link")), handle_link_message))
    
    # Yukarıdaki filtrelere uymayan diğer tüm metin mesajları için kullanıcıya yardım menüsünü göster
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, help_command))

    logger.info("Bot poling modunda başlatılıyor...")
    # Botu başlat ve yeni mesajlar için dinlemeye başla
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
