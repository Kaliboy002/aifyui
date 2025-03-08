from pyrogram import Client, types, filters, enums
import asyncio
import os
import requests
import re
import json
from pymongo import MongoClient

# MongoDB Connection
client = MongoClient('mongodb+srv://mrshokrullah:L7yjtsOjHzGBhaSR@cluster0.aqxyz.mongodb.net/shah?retryWrites=true&w=majority&appName=Cluster0')  # Use your MongoDB URI here
db = client['shah']  # Create a database
users_collection = db['shm']  # Create a collection for users

# Bot Config Objects
class Config:
    SESSION = "BQG0lX0AqA8ehJYDUzT99Yo_Zh7H4hkEuAc1L9nETnK7pShNlxfCHxFjSCNgNR6a6oik70m8-OD2GgMzTo2F0v-tmONXkPU5qUuAZKDaj0_d6z6zMFQ_nenj0FmbRtpaF_C-ao_7VFdSqCEuPkiDeuTCSg4EK6PZF7iQ5hnuQSVsbAAzLJj_EaWcONGOk-EImSj5Dp_bHkVaXrEMX7FTH_t5qU71SCvNpmHPzQMdag1u9EBdUcMZ_s49pKobk-nNSIDTOUPxtOxUEcQ2XLyqvvweWjXnTXJPdNYa1JJb4P9xDtaS9GpAdQ6GMBItrqOwPCszLc84_GIAKKoEgHHRo1H0Df71PQAAAAGkAOGhAA"
    API_KEY = "7909997145:AAGQaK3G2p_tCQln1eVFaW1tq_-eCGd1tow"
    API_HASH = "e51a3154d2e0c45e5ed70251d68382de"
    API_ID = 15787995
    SUDO = 7046488481
    ADMIN_ID = 7046488481
    CHANNLS = ['Kali_Linux_BOTS']
    FORCE_SUBSCRIBE = True  # Default Force Subscribe Mode

# Ensure required directories and files exist
if not os.path.exists('./.session'):
    os.mkdir('./.session')

if not os.path.exists('./data.json'):
    json.dump({'users': [], 'languages': {}}, open('./data.json', 'w'), indent=3)

# Initialize Pyrogram Client
app = Client(
    "./.session/bot",
    bot_token=Config.API_KEY,
    api_hash=Config.API_HASH,
    api_id=Config.API_ID,
    parse_mode=enums.ParseMode.DEFAULT
)

@app.on_message(filters.private & filters.user(Config.SUDO) & filters.reply & filters.command("broadcast"))
async def broadcast_message(app: Client, message: types.Message):
    # Load users from MongoDB
    users = [user.get("user_id") for user in users_collection.find() if "user_id" in user]

    if not users:
        await message.reply("No users available to broadcast.")
        return

    # The replied message to be broadcasted
    broadcast_content = message.reply_to_message

    # Counter to track successful and failed broadcasts
    success_count, fail_count = 0, 0

    # Broadcast the message to each user
    for index, user_id in enumerate(users):
        try:
            if broadcast_content.text:
                await app.send_message(chat_id=user_id, text=broadcast_content.text)
            elif broadcast_content.photo:
                await app.send_photo(chat_id=user_id, photo=broadcast_content.photo.file_id, caption=broadcast_content.caption or "")
            elif broadcast_content.video:
                await app.send_video(chat_id=user_id, video=broadcast_content.video.file_id, caption=broadcast_content.caption or "")
            elif broadcast_content.document:
                await app.send_document(chat_id=user_id, document=broadcast_content.document.file_id, caption=broadcast_content.caption or "")
            success_count += 1
        except Exception as e:
            fail_count += 1
            continue

        # Periodically update progress to the admin
        if (success_count + fail_count) % 10 == 0:
            await message.reply(f"Progress: {success_count + fail_count}/{len(users)} sent.")

    # Send a summary to the admin
    await message.reply(f"Broadcast completed.\nSuccess: {success_count}\nFailed: {fail_count}")

# Language Texts (No changes here)
LANGUAGE_TEXTS = {
    "en": {
        "welcome": "<b><i>Welcome to TG Story Downloader!</b></i> \n\n✈️ You can easily download telegram <b>stories and archived posts </b>of any user in high quality and speed⚡\n\n<b>⁀➴ Just simply send me the link of that story or archived post</b> 🖇️🙂",
        "join_channel": "⚠️<b><i> To use this bot, you must first join our Telegram channel</i></b>\n\nAfter successfully joining, click the 🔐𝗝𝗼𝗶𝗻𝗲𝗱 button to confirm your bot membership and to continue\n\n➤ @IMGEnhancer_Bot",
        "verify_join": "🔐𝗝𝗼𝗶𝗻𝗲𝗱",
        "join_channel_btn": "Jᴏɪɴ ᴄʜᴀɴɴᴇʟ⚡️",
        "not_joined": "🤨 You are not a member of our channel. Please join and try again.",
        "downloading": "<b>Downloading, please wait</b>...⏳🙃",
        "download_successful": "<b>Download completed successfully</b> ✈️",
        "error": "✗ Sorry, there was an issue while downloading 💔\nPlease check the link and try again ⚡"
    },
    "fa": {
        "welcome": "<b>به ربات دانلود استوری تلگرام خوش آمدید!</b>\n\n✈️ شما می‌توانید به‌راحتی<b> استوری‌ها و پست‌های آرشیو شده </b>هر کاربری را با کیفیت و سرعت بالا دانلود کنید⚡\n\n<b>✦ کافیست لینک آن استوری یا پست آرشیو شده را برای من ارسال کنید 🖇️🙂</b>",
        "join_channel": (
            "<b>⚠️ برای استفاده از این ربات، نخست شما باید به کانال‌ های زیر عضو گردید</b>.\n\n"
            "در غیر اینصورت این ربات برای شما کار نخواهد کرد. سپس روی دکمه | <b>عضـو شـدم 🔐 | </b>"
            "کنید تا عضویت ربات خود را تأیید کنید.\n\n➤ @IMGEnhancer_Bot"
        ),
        "verify_join": "عضـو شـدم 🔐",
        "join_channel_btn": "عضـو کانال ⚡",
        "not_joined": "🤨 شما عضو کانال ما نیستید. لطفاً عضو شوید و دوباره امتحان کنید.",
        "downloading": "<b>در حال دانلود، لطفاً صبر کنید</b> ...⏳🙃",
        "download_successful": "<b>دانلود با موفقیت انجام شد ✈️</b>",
        "error": "✗ متاسفانه مشکلی در دانلود پیش آمد 💔\nلطفا لینک را بررسی و دوباره تلاش نماید⚡"
    }
}

# On Start and Language Selection
@app.on_message(filters.private & filters.regex('^/start$'))
async def ON_START_BOT(app: Client, message: types.Message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        # Insert new user into MongoDB
        users_collection.insert_one({
            "user_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name
        })

        # Notify admin about new user
        await app.send_message(
            chat_id=Config.SUDO,
            text=f"↫︙New User Joined The Bot.\n\n  ↫ ID: ❲ {user_id} ❳\n  ↫ Username: ❲ @{message.from_user.username or 'None'} ❳\n  ↫ Firstname: ❲ {message.from_user.first_name} ❳\n\n↫︙Total Members: ❲ {users_collection.count_documents({})} ❳"
        )

    # Send language selection keyboard
    keyboard = [
        [types.InlineKeyboardButton("فارسـی 🇮🇷", callback_data="lang_fa"), types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await message.reply("🇺🇸 <b>Select the language of your preference from below to continue</b>\n"
                        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                        "🇮🇷 <b>برای ادامه، لطفا نخست زبان مورد نظر خود را از گزینه زیر انتخاب کنید</b>", 
                        reply_markup=types.InlineKeyboardMarkup(keyboard))

# Handle Language Selection
@app.on_callback_query(filters.regex('^lang_'))
async def language_selection(app: Client, callback_query: types.CallbackQuery):
    language = callback_query.data.split('_')[1]
    user_id = str(callback_query.from_user.id)

    data = json.load(open('./data.json'))
    data['languages'][user_id] = language
    json.dump(data, open('./data.json', 'w'), indent=3)

    if Config.FORCE_SUBSCRIBE:
        join_message = LANGUAGE_TEXTS[language]["join_channel"].format(Config.CHANNLS[0])
        join_button = types.InlineKeyboardButton(LANGUAGE_TEXTS[language]["join_channel_btn"], url=f"https://t.me/{Config.CHANNLS[0]}")
        verify_button = types.InlineKeyboardButton(LANGUAGE_TEXTS[language]["verify_join"], callback_data="check_join")
        await callback_query.message.edit(
            text=join_message,
            reply_markup=types.InlineKeyboardMarkup([[join_button], [verify_button]])
        )
    else:
        await callback_query.message.edit(text=LANGUAGE_TEXTS[language]["welcome"])

# Check Join Method
async def CHECK_JOIN_MEMBER(user_id: int, channels: list, api_key: str):
    states = ['administrator', 'creator', 'member', 'restricted']
    for channel in channels:
        try:
            api_url = f"https://api.telegram.org/bot{api_key}/getChatMember?chat_id=@{channel}&user_id={user_id}"
            response = requests.get(api_url).json()
            if response.get('ok') and response['result']['status'] in states:
                continue
            else:
                return False, channel
        except Exception:
            return False, channel
    return True, None

# Story Downloader Method
async def GET_STORES_DATA(chat_id: str, story_id: int):
    client = Client(":memory:", api_hash=Config.API_HASH, api_id=Config.API_ID, session_string=Config.SESSION, workers=2, no_updates=True)
    try:
        await client.connect()
        story = await client.get_stories(chat_id=chat_id, story_ids=[story_id])
        if not story:
            return False, None, None
        media = await client.download_media(story[0], in_memory=True)
        description = story[0].caption if story[0].caption else "No description available."
        # Add "Saved by @Tgstorybot" to the description
        description += "\n\n<b>Saved By ➣ @TGStoryXBot"
    except Exception:
        return False, None, None
    finally:
        await client.disconnect()
    return True, media, description

@app.on_message(filters.private & filters.user(Config.SUDO) & filters.command("subscribe"))
async def handle_subscribe_command(app: Client, message: types.Message):
    # Ask admin to send the user ID
    await message.reply("Please send the user ID of the person you want to disable the subscription requirement for.")
    
    # Set up the next step to receive the user ID
    async def disable_subscription(client, message):
        user_input = message.text.strip()

        # Check if the user input is numeric (valid user ID) and not a URL
        if not user_input.isdigit():
            await message.reply("Invalid input! Please send a valid numeric user ID, not a link or invalid data.")
            return
        
        user_id_to_disable = int(user_input)
        user = users_collection.find_one({"user_id": user_id_to_disable})

        if not user:
            await message.reply(f"User ID {user_id_to_disable} not found in the database.")
            return

        # Disable the subscribe requirement (force_subscribe field)
        users_collection.update_one(
            {"user_id": user_id_to_disable},
            {"$set": {"force_subscribe": False}}  # Disable the subscription requirement
        )

        await message.reply(f"Subscription requirement for User ID {user_id_to_disable} has been disabled.")

        # Stop listening for the user ID input after this action is performed
        app.remove_handler(disable_subscription)

    # Register the handler for user ID input
    app.add_handler(disable_subscription, filters.private)

# Verify Channel Join (Force Subscribe)
@app.on_callback_query(filters.regex('^check_join$'))
async def check_join(app: Client, callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = json.load(open('./data.json'))
    language = data['languages'].get(str(user_id), 'en')

    # Force subscribe mode check
    if Config.FORCE_SUBSCRIBE:
        status, channel = await CHECK_JOIN_MEMBER(user_id, Config.CHANNLS, Config.API_KEY)
        if not status:
            await callback_query.answer(LANGUAGE_TEXTS[language]["not_joined"], show_alert=True)
            return
        else:
            await callback_query.message.edit(text=LANGUAGE_TEXTS[language]["welcome"])
    else:
        await callback_query.message.edit(text=LANGUAGE_TEXTS[language]["welcome"])

# Toggle Force Subscribe Mode
@app.on_message(filters.private & filters.user(Config.SUDO) & filters.command(['toggle_subscribe']))
async def toggle_force_subscribe(app: Client, message: types.Message):
    Config.FORCE_SUBSCRIBE = not Config.FORCE_SUBSCRIBE
    status = "enabled" if Config.FORCE_SUBSCRIBE else "disabled"
    await message.reply(f"Force-Subscribe mode has been {status}!")

# On Send Story URL
@app.on_message(filters.private & filters.text & ~filters.command("broadcast"))
async def ON_URL(app: Client, message: types.Message):
    user_id = str(message.from_user.id)
    data = json.load(open('./data.json'))
    language = data['languages'].get(user_id, 'en')

    if Config.FORCE_SUBSCRIBE:
        status, channel = await CHECK_JOIN_MEMBER(message.from_user.id, Config.CHANNLS, Config.API_KEY)
        if not status:
            join_message = LANGUAGE_TEXTS[language]["join_channel"].format(channel)
            join_button = types.InlineKeyboardButton(LANGUAGE_TEXTS[language]["join_channel_btn"], url=f"https://t.me/{channel}")
            verify_button = types.InlineKeyboardButton(LANGUAGE_TEXTS[language]["verify_join"], callback_data="check_join")
            await message.reply(join_message, reply_markup=types.InlineKeyboardMarkup([[join_button], [verify_button]]))
            return

    downloading_message = await message.reply(LANGUAGE_TEXTS[language]["downloading"])

    url = message.text
    if not url.startswith('https://t.me/'):
        await downloading_message.edit(LANGUAGE_TEXTS[language]["error"])
        return

    try:
        chat_id = url.split('/')[-3]
        story_id = int(url.split('/')[-1])
    except:
        await downloading_message.edit(LANGUAGE_TEXTS[language]["error"])
        return

    status, story_data, description = await GET_STORES_DATA(chat_id, story_id)
    if not status:
        await downloading_message.edit(LANGUAGE_TEXTS[language]["error"])
        return

    await downloading_message.edit(LANGUAGE_TEXTS[language]["download_successful"])

    # Send the media without file method
    if isinstance(story_data, bytes):  # If it's an image
        await app.send_photo(chat_id=message.chat.id, photo=story_data, caption=description)
    else:  # If it's a video or other media
        await app.send_video(chat_id=message.chat.id, video=story_data, caption=description)

# Run the bot
asyncio.run(app.run())
