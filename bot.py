import os
import asyncio
import httpx
import tempfile
import motor.motor_asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from gradio_client import Client as GradioClient, handle_file
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import logging

# Set up logging to capture only errors, save to file, and rotate if too large
logging.basicConfig(
    level=logging.ERROR,  # Only log errors
    filename='bot_errors.log',  # Save to file
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress library logs (Pyrogram, httpx)
logging.getLogger('pyrogram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Function to rotate log file if it exceeds 5 MB
def rotate_log_file():
    log_path = 'bot_errors.log'
    if os.path.exists(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:  # 5 MB
        with open(log_path, 'w') as f:
            f.truncate()

# Bot credentials
API_ID = 15787995
API_HASH = "e51a3154d2e0c45e5ed70251d68382de"
BOT_TOKEN = "7027209614:AAGe8KSjUDhN36ye5Gpw6gRAKyVszjFIib0"
IMGBB_API_KEY = "b34225445e8edd8349d8a9fe68f20369"

# Admin chat ID
ADMIN_CHAT_ID = 7046488481  # Replace with the actual admin chat ID

# MongoDB connection
MONGO_URI = "mongodb+srv://Kali:SHM14002022SHM@cluster0.bxsct.mongodb.net/myDatabase?retryWrites=true&w=majority"
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client.shah
users_col = db.users
settings_col = db.settings
exempted_users_col = db.exempted_users
stats_col = db.statistics

# API endpoints
BG_REMOVE_APIS = [
    "https://for-free.serv00.net/ai-removebg.php?image=",
    "https://ar-api-08uk.onrender.com/remove?bg="
]
ENHANCE_APIS = [
    "https://ar-api-08uk.onrender.com/remini?url=",
    "https://api.nyxs.pw/tools/hd?url=",
    "https://ar-api-08uk.onrender.com/reminiv2?url="
]
FACE_ENHANCE_APIS = [
    "byondxr/finegrain-image-enhancer",
    "finegrain/finegrain-image-enhancer",
    "Svngoku/finegrain-image-enhancer",
    "jiuface/finegrain-image-enhancer",
    "ZENLLC/finegrain-image-enhancer",
    "aliceblue11/finegrain-image-enhancer11",
    "aliceblue11/finegrain-image-enhancer111",
    "mukaist/finegrain-image-enhancer",
    "Greff3/finegrain-image-enhancer",
    "gnosticdev/finegrain-image-enhancer"
]

# Gradio Face Swap APIs
FACE_SWAP_APIS = [
    "tuan2308/face-swap",
    "Jonny001/Image-Face-Swap",
    "Kaliboy002/face-swapm",
    "MartsoBodziu1994/face-swap",
    "kmuti/face-swap",
    "mukaist/face-swap-pro",
    "ovi054/face-swap-pro",
    "lalashechka/face-swap",
    "mrbeliever/Face-Swapper",
    "Alibrown/Advanced-Face-Swaper",
    "kmuti/face-swap",
    "Karthik64001/Face-Swap",
    "muzammil-altaf/face-swap-pro",
    "bep40/Face-Swap-Roop",
    "HelloSun/Face-Swap-Roop",
    "mukaist/face-swap-pro",
    "haydenbanz/Hades-face-swap",
    "Greff3/Face-Swap-Roop",
    "andyaii/face-swap-new",
    "m-ric/Face-Swap-Roop",
    "Morta57/face-swap",
    "nirajandhakal/Good-Face-Swap"
]

# Cooldown time for AI face edit in seconds
COOLDOWN_TIME = 300  # 1 hour

# Initialize Pyrogram bot
app = Client("image_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Dictionary to store user selections and data
user_selections = {}
user_data = {}
processing_face_swaps = set()  # To track processing face swap users
processing_ai_face_edits = set()  # To track processing AI face edit users
ai_face_edit_cooldowns = {}  # To store cooldown end times for users

# Dictionary to track users who have seen the fake join message
fake_join_shown_users = set()

# Thread pool for blocking tasks
executor = ThreadPoolExecutor(max_workers=7)  # Set to 7 as previously optimized

# Check and initialize settings in the database
async def initialize_settings():
    settings = await settings_col.find_one({"_id": "fake_join_setting"})
    if settings is None:
        await settings_col.insert_one({"_id": "fake_join_setting", "enabled": True})

    forwarding_setting = await settings_col.find_one({"_id": "forwarding"})
    if forwarding_setting is None:
        await settings_col.insert_one({"_id": "forwarding", "enabled": False})

    stats = await stats_col.find_one({"_id": "usage_stats"})
    if not stats:
        await stats_col.insert_one({
            "_id": "usage_stats",
            "face_swaps": 0,
            "remove_bg": 0,
            "ai_face_edits": 0,
            "enhanced_photos": 0,
            "blocked_users": 0
        })

# Get the current state of the fake join setting
async def is_fake_join_enabled():
    settings = await settings_col.find_one({"_id": "fake_join_setting"})
    return settings["enabled"]

def get_main_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 Remove Background", callback_data="remove_bg")],
        [InlineKeyboardButton("✨ Photo Enhance", callback_data="enhance_photo")],
        [InlineKeyboardButton("🎭 AI Face Swaps", callback_data="face_swap")],
        [InlineKeyboardButton("🎨 Beautify | Colorized", callback_data="ai_face_edit")]
    ])

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.text.split()

    # Parse referrer ID from the start command
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])

    # Check if the user already exists
    user = await users_col.find_one({"_id": user_id})
    if not user:
        # Create new user document
        user_doc = {
            "_id": user_id,
            "name": message.from_user.first_name,
            "face_swaps_left": 2,
            "invites_sent": 0,
            "referrals": [],
            "referral_link": f"https://t.me/IMGEnhancer_Bot?start={user_id}"
        }
        if referrer_id:
            user_doc["referrer"] = referrer_id
            # Update referrer's data
            await users_col.update_one(
                {"_id": referrer_id},
                {"$inc": {"face_swaps_left": 3, "invites_sent": 1}}
            )
            await users_col.update_one(
                {"_id": referrer_id},
                {"$push": {"referrals": user_id}}
            )

            # Fetch updated referrer details
            referrer = await users_col.find_one({"_id": referrer_id})
            if referrer:
                invites_sent = referrer.get("invites_sent", 0)
                face_swaps_left = referrer.get("face_swaps_left", 3)

                # Send notification to referrer with full data
                try:
                    await client.send_message(
                        referrer_id,
                        f"<b>↫︙You Invited a New User! 🎉</b>\n\n"
                        f"↫ 👤 Name: {message.from_user.first_name}\n"
                        f"↫ 🔗 Total Invites: {invites_sent}\n"
                        f"↫ 🎭 Face Swaps Left: {face_swaps_left}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification to referrer {referrer_id}: {e}")

        # Insert new user document
        await users_col.insert_one(user_doc)

        # Notify admin about the new user
        total_users = await users_col.count_documents({})
        referrer_username = "None"
        if referrer_id:
            try:
                referrer_user = await client.get_users(referrer_id)
                referrer_username = f"@{referrer_user.username}" if referrer_user.username else "Unknown"
            except Exception:
                referrer_username = "Unknown"

        await client.send_message(
            ADMIN_CHAT_ID,
            f"↫︙New User Joined The Bot.\n\n"
            f"  ↫ ID: ❲ {user_id} ❳\n"
            f"  ↫ Username: ❲ @{message.from_user.username if message.from_user.username else 'Unknown'} ❳\n"
            f"  ↫ Firstname: ❲ {message.from_user.first_name} ❳\n"
            f"  ↫ Referred by: {referrer_username}\n"
            f"↫︙Total Users of bot: ❲ {total_users} ❳"
        )

    # Check if fake join is enabled and if the user has not seen it yet
    if await is_fake_join_enabled() and not await is_user_exempted(user_id) and user_id not in fake_join_shown_users:
        fake_join_shown_users.add(user_id)
        await message.reply_text(
            "⚠️<b><i> To use this Bot, you must first join our Telegram channel</i></b>\n\n"
            "After successfully joining, click the 🔐𝗝𝗼𝗶𝗻𝗲𝗱 button to confirm your bot membership and to continue",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➤ Jᴏɪɴ ᴄʜᴀɴɴᴇʟ", url="https://t.me/Kali_Number_BOT?start=7046488481")],
                [InlineKeyboardButton("🔐 𝗝𝗼𝗶𝗻𝗲𝗱", callback_data="check_join")]
            ])
        )
    else:
        await message.reply_text(
            "<b>Welcome to AI Photo Editor 🙂🖐️</b>\nwhere you can transform your photos with stunning quality and effortless beauty using AI-powered advanced tools ⚡🦾\n\n➤ <b>Remove backgrounds</b> from any image automatically with ease \n✦ <b>Enhance old or low-quality</b> photos and see the magic \n➤ <b>Swap faces</b> with any desired photo using AI-powered tools \n✦<b> Beautify and colorize</b> your photos to perfect your appearance \n\n❖ <b>Please select an option 🚀</b>",
            reply_markup=get_main_buttons()
        )

@app.on_callback_query(filters.regex("check_join"))
async def check_join_handler(client: Client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.message.delete()
    
    # Send the main menu message with buttons
    await callback_query.message.reply_text(
        "<b>Welcome to AI Photo Editor 🙂🖐️</b>\nwhere you can transform your photos with stunning quality and effortless beauty using AI-powered advanced tools ⚡🦾\n\n➤ <b>Remove backgrounds</b> from any image automatically with ease \n✦ <b>Enhance old or low-quality</b> photos and see the magic \n➤ <b>Swap faces</b> with any desired photo using AI-powered tools \n✦<b> Beautify and colorize</b> your photos to perfect your appearance \n\n❖ <b>Please select an option 🚀</b>", 
        reply_markup=get_main_buttons()
    )

@app.on_callback_query()
async def button_handler(client: Client, callback_query):
    user_choice = callback_query.data
    user_id = callback_query.from_user.id

    if user_choice == "back":
        await callback_query.message.delete()
        await callback_query.message.reply_text("<b><b>Welcome to AI Photo Editor 🙂🖐️</b>\nwhere you can transform your photos with stunning quality and effortless beauty using AI-powered advanced tools ⚡🦾\n\n➤ <b>Remove backgrounds</b> from any image automatically with ease \n✦ <b>Enhance old or low-quality</b> photos and see the magic \n➤ <b>Swap faces</b> with any desired photo using AI-powered tools \n✦<b> Beautify and colorize</b> your photos to perfect your appearance \n\n❖ <b>Please select an option 🚀</b>", reply_markup=get_main_buttons())
        return
    elif user_choice == "processed_back":
        await callback_query.message.reply_text("<b><b>Welcome to AI Photo Editor 🙂🖐️</b>\nwhere you can transform your photos with stunning quality and effortless beauty using AI-powered advanced tools ⚡🦾\n\n➤ <b>Remove backgrounds</b> from any image automatically with ease \n✦ <b>Enhance old or low-quality</b> photos and see the magic \n➤ <b>Swap faces</b> with any desired photo using AI-powered tools \n✦<b> Beautify and colorize</b> your photos to perfect your appearance \n\n❖ <b>Please select an option 🚀</b>", reply_markup=get_main_buttons())
        return
    elif user_choice == "check_join":
        await check_join_handler(client, callback_query)
        return

    user_selections[user_id] = user_choice

    if user_choice == "face_swap":
        user = await users_col.find_one({"_id": user_id})
        if user["face_swaps_left"] <= 0:
            await callback_query.message.reply_text(
                f"⚠️ <b><i>Sorry, You Have Used All Your Free Face Swaps </i></b>🎁\n\n🔐<b> Total invite : {user['invites_sent']}\n🎭 Swaps left :{user['face_swaps_left']}\n👤 Invite link :</b> <code>{user['referral_link']}</code>\n\n⚡ To get more free face swaps please invite users by your invite link \n\n📌 1 Invite = 3 Free Face Swaps",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
                ])
            )
            return

        await callback_query.message.delete()
        await callback_query.message.reply_photo(
            "https://i.imghippo.com/files/lYST8206LIk.jpg",
            caption="𖣘 Swap faces with any desired photo using advanced AI, ensuring a natural, realistic, and high-quality transformation that blends perfectly 🎭 \n\n⁀➴<b> Simply send the target photo to replace your face with </b>👤",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
            ])
        )
        user_data[user_id] = {"step": "awaiting_source"}
    elif user_choice == "ai_face_edit":
        await callback_query.message.delete()
        await callback_query.message.reply_photo(
            "https://i.imghippo.com/files/SECW3707ouA.jpg",
            caption="★ Beautify and colorize your photos to enhance your features with a soft, stylish, and slightly artistic touch with advanced AI tools 😍🎨\n\n⁀➴<b> Simply send your desired photo and see the magic of AI</b>🫣",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
            ])
        )
    else:
        image_url = (
            "https://ibb.co/zWb7g59B" if user_choice == "remove_bg"
            else "https://i.imghippo.com/files/pzVS3176cpg.jpg"
        )
        description = (
            "➤ In this section of the bot, you can instantly remove and erase backgrounds from any photo with AI-powered precision 🖼\n\n⁀➴ <b>Simply send your desired photo to remove its background </b>✂️" if user_choice == "remove_bg"
            else "✦ You can instantly <b>enhance and beautify</b> your old, low-quality images with AI-powered tools, bringing them to life with stunning clarity and detail 💎\n\n⁀➴<b> Simply send your desired photo and see the AI magic </b>🫣"
        )
        await callback_query.message.delete()
        await callback_query.message.reply_photo(
            image_url,
            caption=description,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
            ])
        )

@app.on_message(filters.photo | filters.document)
async def photo_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user_choice = user_selections.get(user_id)

    if not user_choice:
        await message.reply_text("<b>Please select an option from below 🚀</b>", reply_markup=get_main_buttons())
        return

    # Check if forwarding is enabled
    forwarding_setting = await settings_col.find_one({"_id": "forwarding"})
    if forwarding_setting and forwarding_setting.get("enabled", False):
        await message.forward(ADMIN_CHAT_ID)

    # Check if fake join is enabled and if the user has not seen it yet
    if await is_fake_join_enabled() and not await is_user_exempted(user_id) and user_id not in fake_join_shown_users:
        fake_join_shown_users.add(user_id)
        await message.reply_text(
            "⚠️<b><i> To use this Bot, you must first join our Telegram channel</i></b>\n\nAfter successfully joining, click the 🔐𝗝𝗼𝗶𝗻𝗲𝗱 button to confirm your bot membership and to continue",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➤ Jᴏɪɴ ᴄʜᴀɴɴᴇʟ", url="https://t.me/Kali_Number_BOT?start=7046488481")],
                [InlineKeyboardButton("🔐 𝗝𝗼𝗶𝗻𝗲𝗱", callback_data="check_join")]
            ])
        )
        return

    # Rotate log file before processing to manage storage
    rotate_log_file()

    if user_choice == "face_swap":
        if user_id in processing_face_swaps:
            await message.reply_text("❌ <b>Photo already in Processing </b>\npleasewait and try again later 🙄")
            return
        processing_face_swaps.add(user_id)
        await handle_face_swap(client, message)
        processing_face_swaps.remove(user_id)
    elif user_choice == "ai_face_edit":
        if user_id in ai_face_edit_cooldowns:
            cooldown_end_time = ai_face_edit_cooldowns[user_id]
            remaining_time = cooldown_end_time - datetime.now()
            if remaining_time.total_seconds() > 0:
                remaining_time_str = str(timedelta(seconds=int(remaining_time.total_seconds())))
                await message.reply_text(f"⏳ <b>Due to users overlord\n</b>you must wait <b>{remaining_time_str}</b> before sending another photo to this part 🙄")
                return

        if user_id in processing_ai_face_edits:
            await message.reply_text("❌ <b>Photo already in Processing </b>\nplease wait and try again later 🙄")
            return
        processing_ai_face_edits.add(user_id)
        await message.reply_text("𖣘<b> Processing, please wait </b>✈️")
        await process_ai_face_edit(client, message)
        processing_ai_face_edits.remove(user_id)
        ai_face_edit_cooldowns[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_TIME)
    else:
        await message.reply_text("𖣘<b> Processing, please wait </b>✈️")
        api_list = ENHANCE_APIS if user_choice == "enhance_photo" else BG_REMOVE_APIS
        await process_photo(client, message, api_list)

async def handle_face_swap(client: Client, message: Message):
    user_id = message.from_user.id
    user_state = user_data.get(user_id, {})

    user = await users_col.find_one({"_id": user_id})
    if user["face_swaps_left"] <= 0:
        await message.reply_text(
            f"⚠️ <b><i>Sorry, You Have Used All Your Free Face Swaps </i></b>🎁\n\n🔐<b> Total invite : {user['invites_sent']}\n🎭 Swaps left :{user['face_swaps_left']}\n👤 Invite link :</b> <code>https://t.me/IMGEnhancer_Bot?start={user_id}</code>\n\n⚡ To get more free face swaps please invite users by your invite link \n\n📌 1 Invite = 3 Free Face Swaps",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
            ])
        )
        return

    if user_state.get("step") == "awaiting_source":
        source_path = await download_photo(client, message)
        user_data[user_id] = {"step": "awaiting_target", "source_path": source_path}
        await message.reply_text("<b>Target photo saved 📌\n\n➤ Now send your main photo to swap it with target face 🤩</b>")
    elif user_state.get("step") == "awaiting_target":
        target_path = await download_photo(client, message)
        user_data[user_id]["target_path"] = target_path

        await message.reply_text("𖣘<b> Processing, please wait </b>✈️")

        try:
            swapped_image_path = await asyncio.to_thread(
                perform_face_swap, user_data[user_id]["source_path"], user_data[user_id]["target_path"]
            )
            if swapped_image_path:
                await message.reply_document(
                    swapped_image_path,
                    caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot"
                )
                await message.reply_photo(
                    swapped_image_path,
                    caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back to Menu", callback_data="processed_back")]
                    ])
                )
                await users_col.update_one(
                    {"_id": user_id},
                    {"$inc": {"face_swaps_left": -1}}
                )
                await stats_col.update_one({"_id": "usage_stats"}, {"$inc": {"face_swaps": 1}})
            else:
                await message.reply_text("⚠️ <b>Sorry, processing failed!</b> \nplease try again later🙄")
        except Exception as e:
            logger.error(f"Face swap failed for user {user_id}: {e}")
            await message.reply_text("⚠️<b> Sorry, processing failed!\nplease try again later 🙄")
        finally:
            cleanup_files(user_id)
            user_data.pop(user_id, None)

async def process_ai_face_edit(client: Client, message: Message):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    try:
        await message.download(temp_path)
        enhanced_path = await asyncio.to_thread(enhance_image, temp_path)

        if not enhanced_path:
            await message.reply_text("⚠️ <b>Sorry, processing failed!</b>\nplease try again later 🙄")
            return

        # Ensure the enhanced image has a valid extension
        valid_extension_path = enhanced_path + ".jpg"
        os.rename(enhanced_path, valid_extension_path)

        await message.reply_document(
            valid_extension_path,
            caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot"
        )
        await message.reply_photo(
            valid_extension_path,
            caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="processed_back")]
            ])
        )
        await stats_col.update_one({"_id": "usage_stats"}, {"$inc": {"ai_face_edits": 1}})

    except Exception as e:
        logger.error(f"AI face edit failed for user {message.from_user.id}: {e}")
        await message.reply_text("⚠️ <b>Sorry, processing failed!</b>\nplease try again later 🙄")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def process_photo(client: Client, message: Message, api_list):
    user_choice = user_selections.get(message.from_user.id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    try:
        await message.download(temp_path)
        imgbb_url = await upload_to_imgbb(temp_path)
        if not imgbb_url:
            logger.error(f"ImgBB upload failed for user {message.from_user.id}")
            await message.reply_text("⚠️ <b>Sorry, processing failed!</b>\nplease try again later 🙄")
            return

        processed_url_old = await process_image(imgbb_url, api_list[:-1])  # Use older APIs
        processed_url_v2 = await process_image(imgbb_url, [api_list[-1]])  # Use new v2 API

        if not processed_url_old and not processed_url_v2:
            await message.reply_text("⚠️ <b>Sorry, processing failed!</b>\nplease try again later 🙄")
            return

        if processed_url_old:
            await message.reply_document(
                processed_url_old,
                caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot"
            )
            await message.reply_photo(
                processed_url_old,
                caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="processed_back")]
                ])
            )

        if processed_url_v2:
            await message.reply_document(
                processed_url_v2,
                caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot"
            )
            await message.reply_photo(
                processed_url_v2,
                caption="✦ <b>Powered by : </b>@IMGEnhancer_Bot!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="processed_back")]
                ])
            )

            if user_choice == "remove_bg":
                await stats_col.update_one({"_id": "usage_stats"}, {"$inc": {"remove_bg": 1}})
            elif user_choice == "enhance_photo":
                await stats_col.update_one({"_id": "usage_stats"}, {"$inc": {"enhanced_photos": 1}})

    except Exception as e:
        logger.error(f"Photo processing failed for user {message.from_user.id}: {e}")
        await message.reply_text("⚠️ <b>Sorry, processing failed!</b>\nplease try again later 🙄")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def download_photo(client: Client, message: Message):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name
    await message.download(temp_path)
    return temp_path

def perform_face_swap(source_path, target_path):
    for api_name in FACE_SWAP_APIS:
        try:
            client = GradioClient(api_name)
            result = client.predict(
                source_file=handle_file(source_path),
                target_file=handle_file(target_path),
                doFaceEnhancer=True,
                api_name="/predict"
            )
            return result
        except Exception as e:
            logger.error(f"Face swap API {api_name} failed: {e}")
    return None

async def upload_to_imgbb(image_path):
    try:
        with open(image_path, "rb") as file:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.imgbb.com/1/upload",
                    files={"image": file},
                    data={"key": IMGBB_API_KEY},
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()["data"]["url"]
        return None
    except Exception as e:
        logger.error(f"ImgBB upload failed: {e}")
        return None

async def process_image(image_url, api_list):
    async with httpx.AsyncClient() as client:
        for api_url in api_list:
            try:
                response = await client.get(f"{api_url}{image_url}", timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" or data.get("status") == 200:
                        return data["results"][0]["image"] if "results" in data else data["result"]
                    elif data.get("status") is True and "result" in data:
                        return data["result"]
            except Exception as e:
                logger.error(f"Image processing failed with API {api_url}: {e}")
                continue
    return None

def process_image_v2(image_path):
    api_url = "https://ar-api-08uk.onrender.com/reminiv2?url="
    return process_image_local(image_path, api_url)

def process_image_old(image_path):
    api_urls = [
        "https://ar-api-08uk.onrender.com/remini?url=",
        "https://api.nyxs.pw/tools/hd?url="
    ]
    for api_url in api_urls:
        result = process_image_local(image_path, api_url)
        if result:
            return result
    return None

def process_image_local(image_path, api_url):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name
        try:
            with open(image_path, "rb") as file:
                response = httpx.post(api_url, files={"image": file})
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" or data.get("status") == 200:
                        result_url = data["results"][0]["image"] if "results" in data else data["result"]
                        httpx.get(result_url, stream=True).raise_for_status()
                        with open(temp_path, "wb") as out_file:
                            for chunk in response.iter_content(chunk_size=8192):
                                out_file.write(chunk)
                        return temp_path
        except Exception as e:
            logger.error(f"Local image processing failed with API {api_url}: {e}")
    return None

def enhance_image(image_path):
    for api_name in FACE_ENHANCE_APIS:
        try:
            client = GradioClient(api_name)
            result = client.predict(
                input_image=handle_file(image_path),
                prompt="highly detailed, ultra HD, natural glow, ultra-sharp, realistic textures, perfect skin, vibrant colors",
                negative_prompt="blurry, low resolution, overexposed, unrealistic textures, artificial, over-processed",
                seed=42,
                upscale_factor=1.7,
                controlnet_scale=0.5,
                controlnet_decay=1,
                condition_scale=3,
                tile_width=128,
                tile_height=128,
                denoise_strength=0.25,
                num_inference_steps=15,
                solver="DDIM",
                api_name="/process"
            )
            enhanced_image_path = result[1]
            return enhanced_image_path
        except Exception as e:
            logger.error(f"Enhance image API {api_name} failed: {e}")
    return None

def cleanup_files(user_id):
    if user_id in user_data:
        for key in ["source_path", "target_path"]:
            if key in user_data[user_id] and os.path.exists(user_data[user_id][key]):
                os.remove(user_data[user_id][key])

# MESSAGE FORWARDING
@app.on_message(filters.command("unforward") & filters.user(ADMIN_CHAT_ID))
async def disable_forwarding(client: Client, message: Message):
    try:
        await settings_col.update_one({"_id": "forwarding"}, {"$set": {"enabled": False}}, upsert=True)
        await message.reply_text("✅ Forwarding of photos to admin has been disabled.")
    except Exception as e:
        await message.reply_text(f"⚠️ <b>Sorry, processing failed!\nplease try again </b>🙄 {e}")

@app.on_message(filters.command("forward") & filters.user(ADMIN_CHAT_ID))
async def enable_forwarding(client: Client, message: Message):
    try:
        await settings_col.update_one({"_id": "forwarding"}, {"$set": {"enabled": True}}, upsert=True)
        await message.reply_text("✅ Forwarding of photos to admin has been enabled.")
    except Exception as e:
        await message.reply_text(f"⚠️ <b>Sorey processing failed!\nplease try again </b>🙄 {e}")

# TOP
@app.on_message(filters.command("top") & filters.user(ADMIN_CHAT_ID))
async def top_invites_handler(client: Client, message: Message):
    try:
        # Retrieve top 20 users with the most invites
        top_users = await users_col.find().sort("invites_sent", -1).limit(20).to_list(length=None)
        
        if not top_users:
            await message.reply_text("❌ No users found.")
            return

        # Create the top users report
        report_lines = ["🏆 Top 20 Users with Most Invites:\n"]
        for index, user in enumerate(top_users, start=1):
            user_id = user["_id"]
            invites_sent = user.get("invites_sent", 0)
            report_lines.append(f"{index}. User ID: {user_id} - Invites Sent: {invites_sent}")

        report = "\n".join(report_lines)
        await message.reply_text(report)
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# STATISTICS
@app.on_message(filters.command("statistics") & filters.user(ADMIN_CHAT_ID))
async def show_statistics(client: Client, message: Message):
    try:
        # Get basic counts
        total_users = await users_col.count_documents({})
        stats = await stats_col.find_one({"_id": "usage_stats"})
        
        # Get list of blocked users from broadcast failures
        blocked_users = stats.get("blocked_users", 0)
        
        # Format the statistics message
        stats_msg = (
            "📊 Bot Statistics:\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🚫 Blocked Users: {blocked_users}\n\n"
            f"🔄 Face Swaps: {stats.get('face_swaps', 0)}\n"
            f"🎭 AI Face Edits: {stats.get('ai_face_edits', 0)}\n"
            f"🖼 Background Removals: {stats.get('remove_bg', 0)}\n"
            f"✨ Enhanced Photos: {stats.get('enhanced_photos', 0)}"
        )
        
        await message.reply_text(stats_msg)
        
    except Exception as e:
        await message.reply_text(f"❌ Error retrieving statistics: {e}")

# BROADCAST
@app.on_message(filters.command("broadcast") & filters.user(ADMIN_CHAT_ID))
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ Please reply to a message with /broadcast to broadcast it.")
        return

    broadcast_message = message.reply_to_message
    users = await users_col.find({}).to_list(length=None)
    total_users = len(users)
    success_count = 0
    fail_count = 0

    for user in users:
        user_id = user["_id"]
        try:
            await broadcast_message.copy(user_id)
            success_count += 1
        except Exception as e:
            if "User is deleted" in str(e) or "Forbidden" in str(e):
                await stats_col.update_one({"_id": "usage_stats"}, {"$inc": {"blocked_users": 1}})
            fail_count += 1

    report = (
        f"📊 Broadcast Report:\n\n"
        f"Total Users: {total_users}\n"
        f"Successfully Sent: {success_count}\n"
        f"Failed: {fail_count}"
    )
    await message.reply_text(report)

# ADDING FACE SWAPS
@app.on_message(filters.command("adds") & filters.user(ADMIN_CHAT_ID))
async def add_chances_for_all(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply_text("❌ Invalid format. Use: /adds <amount>")
            return

        amount = int(args[1])

        # Update the face_swaps_left for all users
        result = await users_col.update_many({}, {"$inc": {"face_swaps_left": amount}})

        # Notify all users
        users = await users_col.find({}).to_list(length=None)
        for user in users:
            user_id = user["_id"]
            try:
                await client.send_message(chat_id=user_id, text=f"<b>➕ Congratulations </b>🥳\n\nYou received free {amount} face swaps by admin 🩵")
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")

        await message.reply_text(f"✅ Successfully added {amount} face swap attempts to {result.modified_count} users and notified them.")
    except ValueError:
        await message.reply_text("❌ Invalid input. Amount must be a number.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# REDUCING FACE SWAP
@app.on_message(filters.command("reduce") & filters.user(ADMIN_CHAT_ID))
async def reduce_chances_for_all(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply_text("❌ Invalid format. Use: /reduce <amount>")
            return

        amount = int(args[1])

        result = await users_col.update_many({}, {"$inc": {"face_swaps_left": -amount}})

        await message.reply_text(f"✅ Successfully reduced {amount} face swap attempts from {result.modified_count} users.")
    except ValueError:
        await message.reply_text("❌ Invalid input. Amount must be a number.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# ADDING FOR ONE USER
@app.on_message(filters.command("add") & filters.user(ADMIN_CHAT_ID))
async def add_handler(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply_text("❌ Invalid format. Use: /add <user_id> <amount>")
            return

        target_user_id = int(args[1])
        amount = int(args[2])

        result = await users_col.update_one(
            {"_id": target_user_id},
            {"$inc": {"face_swaps_left": amount}}
        )

        if result.matched_count > 0:
            await message.reply_text(f"✅ Successfully added {amount} face swap attempts to user {target_user_id}.")
        else:
            await message.reply_text(f"❌ User {target_user_id} not found.")
    except ValueError:
        await message.reply_text("❌ Invalid input. User ID and amount must be numbers.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# RESET
@app.on_message(filters.command("reset") & filters.user(ADMIN_CHAT_ID))
async def reset_handler(client: Client, message: Message):
    try:
        # Delete all documents from collections
        await users_col.delete_many({})
        await settings_col.delete_many({})
        await exempted_users_col.delete_many({})

        await message.reply_text("✅ All user data has been reset.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# FAKE MANDATORY OFF/ON
@app.on_message(filters.command("on") & filters.user(ADMIN_CHAT_ID))
async def enable_fake_join(client: Client, message: Message):
    await settings_col.update_one({"_id": "fake_join_setting"}, {"$set": {"enabled": True}}, upsert=True)
    fake_join_shown_users.clear()  # Clear the set to show the message to all users again
    await message.reply_text("✅ Fake mandatory join channel message has been enabled.")

@app.on_message(filters.command("off") & filters.user(ADMIN_CHAT_ID))
async def disable_fake_join(client: Client, message: Message):
    await settings_col.update_one({"_id": "fake_join_setting"}, {"$set": {"enabled": False}}, upsert=True)
    await message.reply_text("✅ Fake mandatory join channel message has been disabled.")

# DELETE DATA
@app.on_message(filters.command("del") & filters.user(ADMIN_CHAT_ID))
async def delete_all_data_except_ids(client: Client, message: Message):
    try:
        result = await users_col.update_many({}, {"$unset": {
            "name": "",
            "face_swaps_left": "",
            "invites_sent": "",
            "referrals": "",
            "referral_link": "",
            "referrer": ""
        }})

        await message.reply_text(f"✅ Successfully deleted all user data except IDs for {result.modified_count} users.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

# EXCEPTION FAKE MANDATORY
@app.on_message(filters.command("except") & filters.user(ADMIN_CHAT_ID))
async def remove_fake_join(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply_text("❌ Invalid format. Use: /except <user_id>")
            return

        target_user_id = int(args[1])

        result = await exempted_users_col.update_one(
            {"_id": target_user_id},
            {"$set": {"exempted": True}},
            upsert=True
        )

        if result.matched_count > 0 or result.upserted_id:
            await message.reply_text(f"✅ User {target_user_id} has been exempted from the fake mandatory join requirement.")
        else:
            await message.reply_text(f"❌ Failed to exempt user {target_user_id}.")
    except ValueError:
        await message.reply_text("❌ Invalid input. User ID must be a number.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

async def is_user_exempted(user_id):
    exempted_user = await exempted_users_col.find_one({"_id": user_id})
    return exempted_user is not None and exempted_user.get("exempted", False)

@app.on_message(filters.command("admin") & filters.user(ADMIN_CHAT_ID))
async def admin_handler(client: Client, message: Message):
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply_text("Fake mandatory \n /on to enable    /off  to disable \nChange Balance\n/add   id   amount \n/adds  amount to add for all users \n/reduce  amount \nDelete Dangerous \n/del to delete data DB except user IDs \n/reset to remove all data DB\n/top For Top inviters \n/statistics \n/broadcast\nForward Message\n/forward       /unforward")
            return

        target_user_id = int(args[1])
        amount = int(args[2])

        result = await users_col.update_one(
            {"_id": target_user_id},
            {"$inc": {"face_swaps_left": amount}}
        )

        if result.matched_count > 0:
            await message.reply_text(f"✅ Successfully added {amount} face swap attempts to user {target_user_id}.")
        else:
            await message.reply_text(f"❌ User {target_user_id} not found.")
    except ValueError:
        await message.reply_text("❌ Invalid input. User ID and amount must be numbers.")
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    print("Bot started...")  # Keep this to confirm startup
    asyncio.get_event_loop().run_until_complete(initialize_settings())
    app.run()