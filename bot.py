import telebot
import json
import random
import string
import threading
import re # Imported for regex matching
from io import BytesIO
from telebot import types
from dotenv import load_dotenv
import os
import datetime
import time

# Load bot token from .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# --- MODIFIED: Renamed ADMINS to OWNERS for clarity ---
# Owner list (Full permissions)
OWNERS = [6609574645, 5960749063]  # Replace with real IDs

# --- NEW: Create a directory for file uploads ---
if not os.path.exists("uploaded_files"):
    os.makedirs("uploaded_files")

# Data file to store accounts, user data, admins, and their status
DATA_FILE = 'data.json'
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as file:
        # --- MODIFIED: Added 'admins' list to the data structure ---
        json.dump({"accounts": [], "users": [], "giveaways": [], "admins": []}, file)

# Thread lock for data access
data_lock = threading.Lock()

# In-memory storage for cooldowns and rate limiting
user_cooldowns = {}  # Format: {user_id: {"last_redeem": timestamp, "command_count": count, "last_command": timestamp}}
# NEW: Global dictionary to manage file upload sessions
file_upload_sessions = {}

# Channel IDs and names
CHANNELS = {
    -1002191851646: "KeyShareBD",
    -1002007364394: "House Of Vale"
}

def load_data():
    with data_lock:
        with open(DATA_FILE, "r") as file:
            return json.load(file)

def save_data(data):
    with data_lock:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)

# --- NEW: Permission check functions ---
def is_owner(user_id):
    """Checks if a user is a bot owner."""
    return user_id in OWNERS

def is_admin(user_id):
    """Checks if a user is an admin or an owner."""
    if is_owner(user_id):
        return True
    data = load_data()
    return user_id in data.get("admins", [])

def is_banned(user_id):
    data = load_data()
    return user_id in data.get("banned", [])

def is_member(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

def get_missing_channels(user_id):
    missing = []
    for ch_id, name in CHANNELS.items():
        if not is_member(ch_id, user_id):
            missing.append((ch_id, name))
    return missing

def generate_redeem_code(prefix):
    return (
        f"{prefix}-"
        f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-"
        f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-"
        f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    )

def escape_markdown(text):
    special_chars = "_*[]()~>#+-=|{}.!\\"
    return ''.join(f'\\{c}' if c in special_chars else c for c in text)

def parse_duration(duration_str):
    try:
        num, unit = duration_str.split()
        num = int(num)
        unit = unit.lower()
        if unit in ["sec", "second", "seconds"]:
            return num
        elif unit in ["min", "minute", "minutes"]:
            return num * 60
        elif unit in ["hour", "hours"]:
            return num * 3600
    except:
        return None

def format_giveaway_name(name):
    """Convert giveaway name (e.g., netflix_premium) to user-friendly format (Netflix Premium)."""
    return name.replace("_", " ").title()

def format_remaining_time(start_time, duration_sec):
    """Calculate and format remaining time as 'X min Y sec'."""
    try:
        elapsed = (datetime.datetime.now() - datetime.datetime.fromisoformat(start_time)).total_seconds()
        remaining_sec = max(0, int(duration_sec - elapsed))
        minutes = remaining_sec // 60
        seconds = remaining_sec % 60
        return f"{minutes} min {seconds} sec" if minutes > 0 else f"{seconds} sec"
    except:
        return "Unknown"

def check_rate_limit(user_id):
    """Check if user exceeds 10 commands per minute."""
    current_time = time.time()
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {"last_redeem": 0, "command_count": 0, "last_command": 0}

    if current_time - user_cooldowns[user_id]["last_command"] > 60:
        user_cooldowns[user_id]["command_count"] = 0
        user_cooldowns[user_id]["last_command"] = current_time

    user_cooldowns[user_id]["command_count"] += 1
    if user_cooldowns[user_id]["command_count"] > 10:
        return False, current_time - user_cooldowns[user_id]["last_command"]
    user_cooldowns[user_id]["last_command"] = current_time
    return True, 0

def check_redeem_cooldown(user_id):
    """Check if user is within 5-minute redeem cooldown."""
    current_time = time.time()
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {"last_redeem": 0, "command_count": 0, "last_command": 0}

    elapsed = current_time - user_cooldowns[user_id]["last_redeem"]
    if elapsed < 300:
        return False, 300 - elapsed
    return True, 0

# --- NEW: Centralized redeem logic ---
def process_redeem_code_logic(message, redeem_code):
    """Handles the logic for redeeming a code for both commands and auto-detection."""
    data = load_data()
    for entry in data["accounts"]:
        if entry["redeem_code"] == redeem_code:
            if entry["redeemed"]:
                unredeemed_codes = [acc for acc in data.get("accounts", []) if not acc.get("redeemed", False)]
                if unredeemed_codes:
                    remaining_codes_message = "🎟️ Kindly try another code — There are some unredeemed codes available."
                else:
                    remaining_codes_message = "🎟️ All the codes have already been redeemed, Please Wait for our next giveaway."
                bot.send_message(
                    message.chat.id,
                    f"❌ Sorry, this code was already redeemed by someone else.\n{remaining_codes_message}",
                    parse_mode="Markdown"
                )
                return True # Indicate that a code was found but already used

            # Mark as redeemed and deliver prize
            user_cooldowns[message.from_user.id]["last_redeem"] = time.time()
            entry["redeemed"] = True
            entry["user"] = message.from_user.username or str(message.from_user.id)
            save_data(data)

            item_type = entry.get("type", "account")
            if item_type == "account":
                bot.send_message(
                    message.chat.id,
                    f"🎉 Congratulations! You are the winner! 🎉\n\n"
                    f"Account: \n`{entry['account']}`\n\n"
                    f"⚠️ Send a screenshot after login.\n"
                    f"This is mandatory — otherwise, you will be banned from the bot and will no longer be able to join giveaways!\n\n"
                    f"⏳ Wait 5 min before redeeming again.",
                    parse_mode="Markdown"
                )
            elif item_type == "file":
                try:
                    with open(entry['file_path'], 'rb') as file_doc:
                        bot.send_document(message.chat.id, file_doc, caption=f"🎉 Congratulations! Here is your file! 🎉")
                    os.remove(entry['file_path']) # Delete file after sending
                except Exception as e:
                    bot.send_message(message.chat.id, "❌ Error sending your file. Please contact an admin.")
                    print(f"Error sending file {entry['file_path']}: {e}")

            # Notify admins
            user_name = escape_markdown(message.from_user.first_name or "No Name")
            user_username = f"@{escape_markdown(message.from_user.username)}" if message.from_user.username else "No Username"
            notification_message = (
                "🎁 Code Redeemed!\n\n"
                f"• ┌ Name: {user_name}\n"
                f"• ├ Username: {user_username}\n"
                f"• ├ UserID: {message.from_user.id}\n"
                f"• ├ Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• ├ Code: {redeem_code}"
            )
            all_admins = OWNERS + data.get("admins", [])
            for admin_id in all_admins:
                try:
                    bot.send_message(admin_id, notification_message, parse_mode="Markdown")
                except Exception as e:
                    print(f"Failed to notify admin {admin_id}: {e}")

            return True # Indicate that a code was successfully processed

    # If code is not found after checking all entries
    unredeemed_codes = [acc for acc in data.get("accounts", []) if not acc.get("redeemed", False)]
    if unredeemed_codes:
        remaining_codes_message = "🎟️ Kindly try another code — There are some unredeemed codes available."
    else:
        remaining_codes_message = "🎟️ All the codes have already been redeemed, Please Wait for our next giveaway."

    bot.send_message(
        message.chat.id,
        f"❌ Invalid or expired code. Try again!\n\n{remaining_codes_message}",
        parse_mode="Markdown"
    )
    return False # Indicate code was not found

def end_giveaway(giveaway_name):
    data = load_data()
    now = datetime.datetime.now()

    for giveaway in data.get("giveaways", []):
        if giveaway.get("name") == giveaway_name and giveaway.get("is_active", False):
            giveaway["is_active"] = False
            participants = giveaway.get("participants", [])
            accounts = giveaway.get("accounts", [])
            winners = []

            if not participants or not accounts:
                save_data(data)
                return

            winners = random.sample(participants, min(len(participants), len(accounts)))

            for i, winner in enumerate(winners):
                winner["account"] = accounts[i]

            giveaway["winners"] = winners
            save_data(data)

            winner_usernames = [
                f"@{escape_markdown(w['username'])}" if w.get("username") else f"`{w['id']}`"
                for w in winners
            ]
            winner_list = "\n".join(winner_usernames) if winner_usernames else "No winners"

            for winner in winners:
                try:
                    bot.send_message(
                        winner["id"],
                        f"🎉 You won the *{format_giveaway_name(giveaway_name)}*!  \n"
                        f"🎁 Gift: `{winner['account']}`",
                        parse_mode="Markdown"
                    )
                    bot.send_message(
                        winner["id"],
                        f"📣 *{format_giveaway_name(giveaway_name)}* ended.\n"
                        f"👥 Total Participants: {len(participants)}\n"
                        f"🏆 Winners:\n{winner_list}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❌ Failed to send winner message to {winner['id']}: {e}")

            winner_ids = [w["id"] for w in winners]
            for user in participants:
                if user["id"] not in winner_ids:
                    try:
                        bot.send_message(
                            user["id"],
                            f"❌ *{format_giveaway_name(giveaway_name)}* ended.\nBetter luck next time!",
                            parse_mode="Markdown"
                        )
                    except:
                        continue

            summary = (
                f"📣 *{format_giveaway_name(giveaway_name)}* ended.\n"
                f"👥 Total Participants: {len(participants)}\n"
                f"🏆 Winners:\n{winner_list}"
            )
            all_admins = OWNERS + data.get("admins", [])
            for admin_id in all_admins:
                try:
                    bot.send_message(admin_id, summary, parse_mode="Markdown")
                except:
                    continue
            break

    cleaned_giveaways = []
    for g in data.get("giveaways", []):
        if g.get("is_active", False):
            cleaned_giveaways.append(g)
        else:
            end_time = datetime.datetime.fromisoformat(g.get("start_time", now.isoformat()))
            if (now - end_time).total_seconds() < 86400:
                cleaned_giveaways.append(g)

    data["giveaways"] = cleaned_giveaways
    save_data(data)

def reschedule_giveaways():
    """Reschedule active giveaways on bot startup."""
    data = load_data()
    now = datetime.datetime.now()
    for giveaway in data.get("giveaways", []):
        if giveaway.get("is_active", False):
            start_time = datetime.datetime.fromisoformat(giveaway.get("start_time"))
            duration_sec = giveaway.get("duration_sec")
            elapsed = (now - start_time).total_seconds()
            remaining_sec = max(0, duration_sec - elapsed)
            if remaining_sec > 0:
                threading.Timer(remaining_sec, end_giveaway, args=[giveaway["name"]]).start()
                if remaining_sec > 60:
                    threading.Timer(remaining_sec - 60, send_progress_notification, args=[giveaway["name"]]).start()

def send_progress_notification(giveaway_name):
    """Send progress notification to participants at 1 minute remaining."""
    data = load_data()
    for giveaway in data.get("giveaways", []):
        if giveaway.get("name") == giveaway_name and giveaway.get("is_active", False):
            participants = giveaway.get("participants", [])
            total = len(participants)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("View Status", callback_data="view_status"))
            for participant in participants:
                try:
                    bot.send_message(
                        participant["id"],
                        f"📢 *{format_giveaway_name(giveaway_name)} Update* \n"
                        f"👥 Now {total} participants!  \n"
                        f"⏰ Time remaining: 1 min",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except Exception as e:
                    print(f"Failed to send progress notification to {participant['id']}: {e}")
            break

@bot.message_handler(commands=["start"])
def start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌ You are banned from using this bot.\n👉 Contact @Saimom_Sami or @hossain_sugar to request unban.")
        return
    missing = get_missing_channels(message.from_user.id)
    if missing:
        text = "Join both channels to use the bot."
        markup = types.InlineKeyboardMarkup()
        for ch_id, name in missing:
            invite_link = bot.export_chat_invite_link(ch_id)
            markup.add(types.InlineKeyboardButton(f"Join {name}", url=invite_link))
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return
    allowed, wait_time = check_rate_limit(message.from_user.id)
    if not allowed:
        bot.send_message(message.chat.id, f"⏳ Too many commands! Wait {int(wait_time)} sec.")
        return

    data = load_data()
    if "users" not in data:
        data["users"] = []

    if message.from_user.id not in [user["id"] for user in data["users"]]:
        data["users"].append({
            "id": message.from_user.id,
            "username": message.from_user.username
        })
        save_data(data)

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Join Giveaways", callback_data="join_giveaways"),
        types.InlineKeyboardButton("Redeem Code", callback_data="redeem_code")
    )
    guide_text = "Guide"
    guide_callback = "show_guide"
    if is_admin(message.from_user.id):
        guide_text = "Admin Guide"
        guide_callback = "admin_guide"
    
    row2 = [
        types.InlineKeyboardButton("Check Status", callback_data="check_status"),
        types.InlineKeyboardButton(guide_text, callback_data=guide_callback)
    ]
    markup.row(*row2)

    if is_owner(message.from_user.id):
        markup.add(types.InlineKeyboardButton("👑 Add New Admin", callback_data="add_new_admin"))

    bot.send_message(
        message.chat.id,
        "🎉 Welcome to *Reward Rush Bot*! 🎉\n"
        "Win exciting accounts through giveaways and redeem codes!\n\n"
        "🚀 Get started:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=["cmd"])
def cmd(message):
    if is_banned(message.from_user.id): return
    missing = get_missing_channels(message.from_user.id)
    if missing:
        text = "Join both channels to use the bot."
        markup = types.InlineKeyboardMarkup()
        for ch_id, name in missing:
            invite_link = bot.export_chat_invite_link(ch_id)
            markup.add(types.InlineKeyboardButton(f"Join {name}", url=invite_link))
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))

    if is_admin(message.from_user.id):
        owner_commands = ""
        if is_owner(message.from_user.id):
            owner_commands = (
                "👑 *Owner Commands:*\n"
                "📢 */broadcast* — Send a message to all users.\n"
                "🚫 */ban <user_id>* — Ban a user.\n"
                "✅ */unban <user_id>* — Unban a user.\n"
                "➕ */addadmin <user_id>* — Add a new admin.\n\n"
            )

        admin_commands = (
            "🛠️ *Admin Commands:*\n"
            "➕ */add <prefix>* — Add accounts and generate codes.\n"
            "📄 */addfile <prefix>* — Add a text file and generate a code.\n"
            "🎲 */random <name> <duration>* — Start a timed giveaway.\n"
            "👥 */tuser* — View total number of users.\n"
            "📂 */backup* — Get a backup of the database.\n"
            "🧹 */clear* — Clear all accounts and giveaway history.\n"
            "📩 *Reply to forwarded user message* — Send a reply to the user.\n\n"
        )

        user_commands = (
            "🔄 *Everyone's Commands:*\n"
            "🎯 */join <giveaway_name>* — Join an ongoing giveaway.\n"
            "📈 */status* — View active giveaways.\n"
            "🎁 */redeem <code>* — Redeem a code."
        )

        response_text = f"{owner_commands}{admin_commands}{user_commands}"
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(
            message.chat.id,
            "📖 *Reward Rush Bot Guide* \n"
            "- Click \"Join Giveaways\" to enter contests.  \n"
            "- Use \"Redeem Code\" to claim rewards.  \n"
            "- Check \"Status\" for updates.  \n"
            "- Need help? Contact @hossain_sugar or @Saimom_Sami.",
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.message_handler(commands=["redeem"])
def redeem(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌ You are banned from using this bot.\n👉 Contact @Saimom_Sami or @hossain_sugar to request unban.")
        return
    missing = get_missing_channels(message.from_user.id)
    if missing:
        text = "Join both channels to use the bot."
        markup = types.InlineKeyboardMarkup()
        for ch_id, name in missing:
            invite_link = bot.export_chat_invite_link(ch_id)
            markup.add(types.InlineKeyboardButton(f"Join {name}", url=invite_link))
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return
    allowed, wait_time = check_rate_limit(message.from_user.id)
    if not allowed:
        bot.send_message(message.chat.id, f"⏳ Too many commands! Wait {int(wait_time)} sec.")
        return
    allowed, wait_time = check_redeem_cooldown(message.from_user.id)
    if not allowed:
        bot.send_message(message.chat.id, f"⏳ Wait {int(wait_time)} sec before redeeming again.")
        return

    try:
        redeem_code = message.text.split()[1]
        process_redeem_code_logic(message, redeem_code)
    except IndexError:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
        bot.send_message(
            message.chat.id,
            "❌ Please provide a redeem code after the /redeem command. \n /redeem <Your_Redeem_code>",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "❌ This command is for owners only.")
        return
    try:
        user_id = int(message.text.split()[1])
        data = load_data()
        if user_id not in data.get("admins", []):
            data["admins"].append(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User `{user_id}` has been promoted to admin.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"⚠️ User `{user_id}` is already an admin.", parse_mode="Markdown")
    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ Usage: /addadmin <user_id>")

def process_add_admin(message):
    try:
        user_id = int(message.text.strip())
        data = load_data()
        if "admins" not in data:
            data["admins"] = []
        if user_id in data["admins"]:
            bot.send_message(message.chat.id, f"⚠️ User `{user_id}` is already an admin.", parse_mode="Markdown")
            return
        data["admins"].append(user_id)
        save_data(data)
        bot.send_message(message.chat.id, f"✅ User `{user_id}` has been successfully added as an admin.", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a valid numeric user ID.")

@bot.message_handler(commands=["addfile"])
def add_files(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    # End any previous session
    if message.from_user.id in file_upload_sessions:
        del file_upload_sessions[message.from_user.id]

    try:
        prefix = message.text.split()[1] if len(message.text.split()) > 1 else "File"
    except:
        prefix = "File"

    if not prefix.replace("-", "").isalnum():
        bot.reply_to(message, "Invalid prefix. Only alphanumeric characters and hyphens are allowed.")
        return
        
    # Start a new session
    file_upload_sessions[message.from_user.id] = {"prefix": prefix, "files": []}
    bot.send_message(message.chat.id, "✅ Session started. Please upload your text files now. Send /done when you are finished.")

@bot.message_handler(content_types=['document'], func=lambda message: message.from_user.id in file_upload_sessions)
def handle_file_uploads(message):
    session = file_upload_sessions[message.from_user.id]

    if not message.document or not message.document.mime_type == 'text/plain':
        bot.reply_to(message, "That's not a text file. Please upload a `.txt` file.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_path = os.path.join("uploaded_files", message.document.file_id + ".txt")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        session["files"].append(file_path)
        bot.reply_to(message, f"✅ File #{len(session['files'])} received. Upload more or send /done.")

    except Exception as e:
        bot.reply_to(message, f"An error occurred while saving the file: {e}")
        print(f"Error in handle_file_uploads: {e}")

@bot.message_handler(commands=['done'], func=lambda message: message.from_user.id in file_upload_sessions)
def handle_done_upload(message):
    session = file_upload_sessions[message.from_user.id]
    
    if not session["files"]:
        bot.send_message(message.chat.id, "No files were uploaded. Session cancelled.")
        del file_upload_sessions[message.from_user.id]
        return

    data = load_data()
    redeem_codes = []
    prefix = session["prefix"]

    for file_path in session["files"]:
        redeem_code = generate_redeem_code(prefix)
        data["accounts"].append({
            "type": "file",
            "file_path": file_path,
            "redeem_code": redeem_code,
            "redeemed": False,
            "user": None
        })
        redeem_codes.append(redeem_code)
    
    save_data(data)

    response = f"✅ Processed {len(redeem_codes)} files. The redeem codes are:\n" + "\n".join([f"`{code}`" for code in redeem_codes])
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

    # Clean up the session
    del file_upload_sessions[message.from_user.id]

@bot.message_handler(commands=["add"])
def add_accounts(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "You are not authorized to use this command.")
        return
    try:
        prefix = message.text.split()[1] if len(message.text.split()) > 1 else "KeyShareBD"
    except:
        prefix = "KeyShareBD"
    bot.send_message(message.chat.id, "Please send the accounts in the required format.")
    bot.register_next_step_handler(message, lambda m: process_accounts(m, prefix))

def process_accounts(message, prefix):
    accounts = [acc.strip() for acc in message.text.split("\n") if acc.strip()]
    data = load_data()
    redeem_codes = []
    for account in accounts:
        redeem_code = generate_redeem_code(prefix)
        data["accounts"].append({
            "type": "account",
            "account": account,
            "redeem_code": redeem_code,
            "redeemed": False,
            "user": None
        })
        redeem_codes.append(redeem_code)
    save_data(data)
    response = "The redeem codes are:\n" + "\n".join([f"`{code}`" for code in redeem_codes])
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(commands=["tuser"])
def total_users(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "You are not authorized to use this command.")
        return
    data = load_data()
    bot.send_message(message.chat.id, f"📊 The Total Users is: {len(data.get('users', []))}")

@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "You are not authorized to use this command.")
        return
    bot.send_message(message.chat.id, "Please send the message you want to broadcast to all users.")
    bot.register_next_step_handler(message, send_broadcast)

def send_broadcast(message):
    data = load_data()
    broadcast_message = message.text
    total_users = len(data.get("users", []))
    active_users = 0
    banned_users = 0

    for user in data.get("users", []):
        try:
            bot.send_message(user["id"], broadcast_message)
            active_users += 1
        except Exception as e:
            print(f"Failed to send message to {user['id']}: {e}")
            banned_users += 1

    report = (
        f"✅ Broadcast completed!\n\n"
        f"📊 Statistics:\n"
        f"Total Users: {total_users}\n"
        f"Active Users (received): {active_users}\n"
        f"Banned or Unreachable Users: {banned_users}"
    )
    bot.send_message(message.chat.id, report)

@bot.message_handler(commands=['clear'])
def clear_data_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("✅ Confirm Clear", callback_data="confirm_clear")
    markup.add(confirm_button)

    bot.reply_to(message, "⚠️ Are you sure you want to clear all accounts and giveaway data?\n\nThis will NOT delete user data.", reply_markup=markup)

@bot.message_handler(commands=["backup"])
def backup_data_json(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "🚫 You are not allowed to use this command.")
        return
    try:
        with open('data.json', 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📂 Here is your latest data.json backup.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed to send backup: {e}")

@bot.message_handler(commands=["random"])
def random_giveaway(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "⚠️ Usage: /random <giveaway_name> <duration>\nExample: /random netflix 2 min")
        return

    giveaway_name = parts[1].lower()
    duration_str = " ".join(parts[2:])
    duration_sec = parse_duration(duration_str)

    if duration_sec is None:
        bot.send_message(message.chat.id, "❌ Invalid time format. Use formats like 10 sec, 5 min, or 2 hour.")
        return

    data = load_data()
    data.setdefault("giveaways", [])

    now = datetime.datetime.now().isoformat()
    data["giveaways"].append({
        "name": giveaway_name,
        "accounts": [],
        "participants": [],
        "is_active": True,
        "start_time": now,
        "duration_sec": duration_sec
    })
    save_data(data)
    bot.send_message(
        message.chat.id,
        f"✅ Giveaway *{format_giveaway_name(giveaway_name)}* started for {duration_str}.\nNow send the accounts.",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, lambda m: process_giveaway_accounts(m, giveaway_name, duration_sec))

def process_giveaway_accounts(message, giveaway_name, duration_sec):
    if not message.text:
        bot.reply_to(message, "No accounts provided.")
        return

    accounts = [acc.strip() for acc in message.text.split("\n") if acc.strip()]
    if not accounts:
        bot.reply_to(message, "No valid accounts found.")
        return

    data = load_data()
    for giveaway in data.get("giveaways", []):
        if giveaway.get("name") == giveaway_name and giveaway.get("is_active", False):
            giveaway["accounts"].extend(accounts)
            save_data(data)
            bot.send_message(
                message.chat.id,
                f"✅ Added {len(accounts)} account(s).\n⏳ Winners will be selected in {duration_sec} seconds.",
                parse_mode="Markdown"
            )
            threading.Timer(duration_sec, end_giveaway, args=[giveaway_name]).start()
            if duration_sec > 60:
                threading.Timer(duration_sec - 60, send_progress_notification, args=[giveaway_name]).start()
            return
    bot.send_message(message.chat.id, "❌ Giveaway not found or already ended.")

@bot.message_handler(commands=["ban", "unban"])
def ban_unban_user(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    command = message.text.split()[0].lower()
    data = load_data()
    if "banned" not in data: data["banned"] = []

    user_id = None
    if message.reply_to_message and message.reply_to_message.forward_from:
        user_id = message.reply_to_message.forward_from.id
    else:
        try:
            user_id = int(message.text.split()[1])
        except:
            bot.reply_to(message, f"⚠️ Usage: {command} <user_id> or reply to a message.")
            return

    if command == "/ban":
        if user_id not in data["banned"]:
            data["banned"].append(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User `{user_id}` has been banned.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"⚠️ User `{user_id}` is already banned.", parse_mode="Markdown")
    elif command == "/unban":
        if user_id in data["banned"]:
            data["banned"].remove(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User `{user_id}` has been unbanned.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"⚠️ User `{user_id}` is not in the ban list.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.reply_to_message is not None and is_admin(message.from_user.id))
def handle_admin_reply(message):
    if not message.reply_to_message.forward_from:
        bot.reply_to(message, "⚠️ This message wasn't forwarded from a user or the user has restricted forwarding.")
        return

    user_id = message.reply_to_message.forward_from.id
    try:
        bot.forward_message(user_id, message.chat.id, message.message_id)
        bot.reply_to(message, f"✅ Sent your reply to user `{user_id}`.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to send reply to user `{user_id}`: {e}", parse_mode="Markdown")

@bot.message_handler(content_types=["text", "photo", "video", "audio", "document", "sticker", "animation", "voice", "video_note"])
def main_message_handler(message):
    # This handler now manages auto-redeem and message forwarding
    if is_admin(message.from_user.id):
        return
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌ You are banned from using this bot.\n👉 Contact @Saimom_Sami or @hossain_sugar to request unban.")
        return
    missing = get_missing_channels(message.from_user.id)
    if missing:
        text = "Join both channels to use the bot."
        markup = types.InlineKeyboardMarkup()
        for ch_id, name in missing:
            invite_link = bot.export_chat_invite_link(ch_id)
            markup.add(types.InlineKeyboardButton(f"Join {name}", url=invite_link))
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return

    if message.text:
        code_pattern = re.compile(r'^[a-zA-Z0-9\-]+-([A-Z0-9]{4}-){2}[A-Z0-9]{4}$')
        if code_pattern.match(message.text.strip()):
            allowed, wait_time = check_redeem_cooldown(message.from_user.id)
            if not allowed:
                bot.send_message(message.chat.id, f"⏳ Wait {int(wait_time)} sec before redeeming again.")
                return
            process_redeem_code_logic(message, message.text.strip())
            return

    data = load_data()
    all_admins = OWNERS + data.get("admins", [])
    for admin_id in all_admins:
        try:
            bot.forward_message(admin_id, message.chat.id, message.message_id)
        except Exception as e:
            print(f"Failed to forward message to admin {admin_id}: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    if is_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "You are banned.", show_alert=True)
        return
    missing = get_missing_channels(call.from_user.id)
    if missing:
        text = "Join both channels to use the bot."
        markup = types.InlineKeyboardMarkup()
        for ch_id, name in missing:
            invite_link = bot.export_chat_invite_link(ch_id)
            markup.add(types.InlineKeyboardButton(f"Join {name}", url=invite_link))
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
        bot.answer_callback_query(call.id)
        return
    
    data = load_data()

    if call.data == "redeem_code":
        unredeemed_codes = [acc for acc in data.get("accounts", []) if not acc.get("redeemed", False)]
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
        if unredeemed_codes:
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text="🎟️ There are remaining codes. Please paste your code directly in the chat to redeem it.",
                parse_mode="Markdown", reply_markup=markup
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text="🎟️ All the codes have already been redeemed. Please wait for our next giveaway.",
                parse_mode="Markdown", reply_markup=markup
            )
    
    elif call.data == "add_new_admin":
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owners only.", show_alert=True)
            return
        bot.send_message(call.message.chat.id, "👤 Please send the User ID of the new admin.")
        bot.register_next_step_handler(call.message, process_add_admin)

    elif call.data == "back_to_menu":
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Join Giveaways", callback_data="join_giveaways"),
            types.InlineKeyboardButton("Redeem Code", callback_data="redeem_code")
        )
        guide_text = "Guide"
        guide_callback = "show_guide"
        if is_admin(call.from_user.id):
            guide_text = "Admin Guide"
            guide_callback = "admin_guide"
        markup.row(
            types.InlineKeyboardButton("Check Status", callback_data="check_status"),
            types.InlineKeyboardButton(guide_text, callback_data=guide_callback)
        )
        if is_owner(call.from_user.id):
            markup.add(types.InlineKeyboardButton("👑 Add New Admin", callback_data="add_new_admin"))
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text="🎉 Welcome to *Reward Rush Bot*! 🎉\nWin exciting accounts through giveaways and redeem codes!\n\n🚀 Get started:",
            parse_mode="Markdown", reply_markup=markup
        )

    elif call.data == "join_giveaways":
        active_giveaways = [g for g in data.get("giveaways", []) if g.get("is_active", False)]
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not active_giveaways:
            markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🚫 No active giveaways running currently.", reply_markup=markup)
        else:
            for giveaway in active_giveaways:
                name = format_giveaway_name(giveaway["name"])
                markup.add(types.InlineKeyboardButton(f"Join {name}", callback_data=f"join_{giveaway['name']}"))
            markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🎁 Choose a giveaway to join:", reply_markup=markup)

    elif call.data in ["check_status", "view_status"]:
        active_giveaways = [g for g in data.get("giveaways", []) if g.get("is_active", False)]
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
        if active_giveaways:
            response = "🎉 *Active Giveaways* 🎉\n\n"
            for g in active_giveaways:
                response += f"*{format_giveaway_name(g['name'])}*\n👥 Participants: {len(g.get('participants',[]))}\n⏰ Remaining: {format_remaining_time(g.get('start_time'), g.get('duration_sec'))}\n\n"
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🚫 No active giveaways running currently.", reply_markup=markup)

    elif call.data == "show_guide":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Back to Menu", callback_data="back_to_menu"))
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text="📖 *Reward Rush Bot Guide* \n- Click \"Join Giveaways\" to enter contests.  \n- Use \"Redeem Code\" to claim rewards.  \n- Check \"Status\" for updates.  \n- Need help? Contact @hossain_sugar or @Saimom_Sami.",
            parse_mode="Markdown", reply_markup=markup
        )

    elif call.data == "admin_guide":
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id, "Please use the /cmd command for a full list.", show_alert=True)

    elif call.data.startswith("join_"):
        giveaway_name = call.data[5:].lower()
        for giveaway in data.get("giveaways", []):
            if giveaway.get("name") == giveaway_name and giveaway.get("is_active", False):
                if call.from_user.id in [p['id'] for p in giveaway.get("participants", [])]:
                    bot.answer_callback_query(call.id, "❗ You've already joined this giveaway!", show_alert=True)
                    return
                giveaway["participants"].append({"id": call.from_user.id, "username": call.from_user.username})
                save_data(data)
                bot.answer_callback_query(call.id, f"✅ You have successfully joined the {format_giveaway_name(giveaway_name)} giveaway!", show_alert=True)
                return
        bot.answer_callback_query(call.id, "❌ This giveaway doesn't exist or has ended.", show_alert=True)

    elif call.data == "confirm_clear":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return
        
        data = load_data()
        backup_buffer = BytesIO()
        backup_buffer.write(json.dumps(data, indent=4).encode('utf-8'))
        backup_buffer.seek(0)
        backup_buffer.name = "data_backup.json"
        
        try:
            bot.send_document(call.from_user.id, backup_buffer, caption="📦 Here is the backup before clearing.")
        except Exception as e:
            print(f"Failed to send backup to admin {call.from_user.id}: {e}")

        data['accounts'] = []
        data['giveaways'] = []
        save_data(data)
        bot.edit_message_text("✅ Data cleared.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Database cleared successfully ✅")

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.chat_join_request_handler(func=lambda chat_join_request: True)
def auto_approve(chat_join_request):
    bot.approve_chat_join_request(chat_join_request.chat.id, chat_join_request.from_user.id)

reschedule_giveaways()
bot.infinity_polling()

