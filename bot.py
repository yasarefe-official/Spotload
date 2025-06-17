from telegram.ext import Updater, CommandHandler
import os, zipfile
from utils import download_spotify, can_download_more, increase_count

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def start(update, context):
    update.message.reply_text("Send /get or /playlist with a Spotify link 💿")

def get(update, context):
    if not can_download_more():
        update.message.reply_text("❌ Haftalık 500 şarkı limitine ulaşıldı 😔")
        return

    url = context.args[0]
    paths = download_spotify(url, single=True)
    for path in paths:
        with open(path, 'rb') as song:
            update.message.reply_audio(song)
        os.remove(path)
        increase_count()

def playlist(update, context):
    if not can_download_more():
        update.message.reply_text("❌ Haftalık limit doldu 😭")
        return

    url = context.args[0]
    paths = download_spotify(url, single=False)
    zipname = "playlist.zip"

    with zipfile.ZipFile(zipname, 'w') as zipf:
        for song in paths:
            zipf.write(song)
            increase_count()
            os.remove(song)

    with open(zipname, 'rb') as zf:
        update.message.reply_document(zf)

    os.remove(zipname)

updater = Updater(TOKEN)
updater.dispatcher.add_handler(CommandHandler("start", start))
updater.dispatcher.add_handler(CommandHandler("get", get))
updater.dispatcher.add_handler(CommandHandler("playlist", playlist))

updater.start_polling()