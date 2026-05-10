import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters, ConversationHandler
)

BOT_TOKEN = "8752277413:AAEnbO0s3hsjhYKMSr4fVU1pjxuyIehQfZQ"

# Conversation states
ASK_APIKEY, ASK_CHANNEL, ASK_AMOUNT = range(3)

# User data storage: {user_id: {apikey, channel, amount}}
user_configs = {}

used_posts = set()

logging.basicConfig(level=logging.INFO)


# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # পুরনো conversation data ক্লিয়ার করো
    context.user_data.clear()

    await update.message.reply_text(
        "👋 স্বাগতম!\n\nআপনার *API Key* দিন:",
        parse_mode="Markdown"
    )
    return ASK_APIKEY


# ─── API Key সেভ ──────────────────────────────────────────
async def save_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    apikey = update.message.text.strip()

    if user_id not in user_configs:
        user_configs[user_id] = {}
    user_configs[user_id]["apikey"] = apikey

    await update.message.reply_text(
        f"✅ API Key সেভ হয়েছে!\n\nএখন আপনার *চ্যানেল লিংক* দিন (যেমন: https://t.me/yourchannel):",
        parse_mode="Markdown"
    )
    return ASK_CHANNEL


# ─── Channel লিংক সেভ ────────────────────────────────────
async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()

    user_configs[user_id]["channel"] = channel

    await update.message.reply_text(
        "✅ চ্যানেল লিংক সেভ হয়েছে!\n\nএখন *Amount* দিন (কতটি রিঅ্যাকশন/ভিউ চান):",
        parse_mode="Markdown"
    )
    return ASK_AMOUNT


# ─── Amount সেভ ───────────────────────────────────────────
async def save_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount = update.message.text.strip()

    if not amount.isdigit():
        await update.message.reply_text("❌ Amount অবশ্যই সংখ্যা হতে হবে। আবার দিন:")
        return ASK_AMOUNT

    user_configs[user_id]["amount"] = amount

    cfg = user_configs[user_id]
    await update.message.reply_text(
        f"🎉 *সেটআপ সম্পন্ন হয়েছে!*\n\n"
        f"🔑 API Key: `{cfg['apikey']}`\n"
        f"📢 চ্যানেল: {cfg['channel']}\n"
        f"📊 Amount: {cfg['amount']}\n\n"
        f"⚠️ এখন বটকে আপনার চ্যানেলের *Admin* করুন।\n"
        f"তারপর চ্যানেলে যেকোনো পোস্ট করলে অটোমেটিক API রিকোয়েস্ট পাঠানো হবে! ✅\n\n"
        f"🔄 সেটআপ পরিবর্তন করতে আবার /start দিন।",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─── Cancel ───────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ সেটআপ বাতিল করা হয়েছে। /start দিয়ে আবার শুরু করুন।")
    return ConversationHandler.END


# ─── Channel Post Handler ─────────────────────────────────
async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

        chat = message.chat
        message_id = message.message_id

        if not chat.username:
            return

        post_link = f"https://t.me/{chat.username}/{message_id}"
        channel_link = f"https://t.me/{chat.username}"

        if post_link in used_posts:
            return
        used_posts.add(post_link)

        # যেকোনো ইউজারের config-এ এই চ্যানেল আছে কিনা খুঁজি
        matched_config = None
        for uid, cfg in user_configs.items():
            saved_channel = cfg.get("channel", "").rstrip("/")
            if saved_channel == channel_link or saved_channel == f"https://t.me/{chat.username}":
                matched_config = cfg
                break

        if not matched_config:
            # চ্যানেল কনফিগ না থাকলেও যেকোনো available config ব্যবহার করো
            if user_configs:
                matched_config = list(user_configs.values())[-1]
            else:
                print("কোনো কনফিগ নেই, পোস্ট skip করা হলো।")
                return

        apikey = matched_config.get("apikey", "")
        amount = matched_config.get("amount", "20")

        api_url = (
            f"https://smmgem.0web.top/?api=1"
            f"&key={apikey}"
            f"&action=add"
            f"&service=SVC8B26298D"
            f"&link={post_link}"
            f"&quantity={amount}"
        )

        response = requests.get(api_url)
        print(f"Post: {post_link}")
        print(f"API Response: {response.text}")

    except Exception as e:
        print("Error:", e)


# ─── Main ─────────────────────────────────────────────────
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_APIKEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_apikey)],
        ASK_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
        ASK_AMOUNT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, save_amount)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,  # ✅ এটাই মূল সমাধান — বারবার /start কাজ করবে
)

app.add_handler(conv_handler)
app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_post))

print("Bot Running...")
app.run_polling()
