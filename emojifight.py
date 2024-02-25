# emojifight.py
import os
import pymongo
import datetime
import time
import schedule
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from dotenv import load_dotenv
from config import *

# Load environment variables
load_dotenv()

# Connect to MongoDB
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["EmojiFight"]
groups_collection = db["groups"]
users_collection = db["users"]
top_users_collection = db["topusers"]
top_groups_collection = db["topgroups"]
blocked_users_collection = db["blockedusers"]

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! I am EmojiFight bot. Use /help to see available commands.')

def is_owner(update: Update) -> bool:
    return update.message.from_user.id == OWNER_ID

def broadcast(update: Update, context: CallbackContext) -> None:
    if not is_owner(update):
        update.message.reply_text("You don't have permission to use this command.")
        return

    message = " ".join(context.args)
    if not message:
        update.message.reply_text("Please provide a message to broadcast.")
        return

    groups = groups_collection.find()
    for group in groups:
        context.bot.send_message(chat_id=group["chat_id"], text=message)

def stats(update: Update, context: CallbackContext) -> None:
    if not is_owner(update):
        update.message.reply_text("You don't have permission to use this command.")
        return

    num_groups = groups_collection.count_documents({})
    num_users = users_collection.count_documents({})
    update.message.reply_text(f"Number of groups: {num_groups}\nNumber of users: {num_users}")

def top_users(update: Update, context: CallbackContext) -> None:
    top_users = top_users_collection.find().sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 users with most emoji messages:\n"
    for user in top_users:
        message += f"{user['user_id']} - {user['points']} messages\n"
    update.message.reply_text(message)

def top_groups(update: Update, context: CallbackContext) -> None:
    top_groups = top_groups_collection.find().sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 groups with most emoji messages:\n"
    for group in top_groups:
        message += f"{group['chat_id']} - {group['points']} messages\n"
    update.message.reply_text(message)

def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    user_points = top_users_collection.find_one({"user_id": user_id})
    if user_points:
        update.message.reply_text(f"Your total points: {user_points['points']} messages")

    user_points_today = top_users_collection.find_one({"user_id": user_id, "date": today})
    if user_points_today:
        update.message.reply_text(f"Your points today: {user_points_today['points']} messages")
    else:
        update.message.reply_text("You haven't sent any emoji messages today.")

def top(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    top_users_group = top_users_collection.find_one({"chat_id": chat_id})
    
    if top_users_group:
        message = "Top 10 users in this group with most emoji messages:\n"
        for user in top_users_group["users"]:
            message += f"{user['user_id']} - {user['points']} messages\n"
        update.message.reply_text(message)
    else:
        update.message.reply_text("No data available for top users in this group.")

def count_emojis(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Check if the user is blocked
    if is_user_blocked(user_id):
        return

    # Update user points
    top_users_collection.update_one({"user_id": user_id}, {"$inc": {"points": 1}}, upsert=True)
    top_users_collection.update_one({"user_id": user_id, "date": today}, {"$inc": {"points": 1}}, upsert=True)

    # Update group points
    chat_id = update.message.chat_id
    top_groups_collection.update_one({"chat_id": chat_id}, {"$inc": {"points": 1}}, upsert=True)

    # Update top users for the group
    top_users_group = top_users_collection.find_one({"chat_id": chat_id})
    if not top_users_group:
        top_users_group = {"chat_id": chat_id, "users": []}

    user_entry = next((user for user in top_users_group["users"] if user["user_id"] == user_id), None)
    if user_entry:
        user_entry["points"] += 1
    else:
        user_entry = {"user_id": user_id, "points": 1}
        top_users_group["users"].append(user_entry)

    top_users_collection.update_one({"chat_id": chat_id}, {"$set": top_users_group}, upsert=True)

    # Check for spamming and block user if necessary
    check_and_block_spam(update, user_id, chat_id)

def is_user_blocked(user_id):
    blocked_user = blocked_users_collection.find_one({"user_id": user_id})
    if blocked_user and blocked_user["expiry_time"] > time.time():
        return True
    return False

def block_user(user_id):
    expiry_time = time.time() + 600  # 10 minutes
    blocked_users_collection.update_one({"user_id": user_id}, {"$set": {"expiry_time": expiry_time}}, upsert=True)

def check_and_block_spam(update, user_id, chat_id):
    # Check if user sent 5 messages in a row within a short time
    recent_messages = context.user_data.get("recent_messages", [])
    recent_messages.append(time.time())
    context.user_data["recent_messages"] = recent_messages[-5:]

    if len(recent_messages) == 5 and all(recent_messages[i] - recent_messages[i - 1] < 5 for i in range(1, 5)):
        context.bot.send_message(chat_id=chat_id, text=f"@{update.message.from_user.username} you have been blocked for 10 minutes due to spamming.")
        block_user(user_id)

def clear_top_collection():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    top_users_collection.delete_many({"date": {"$ne": today}})
    top_groups_collection.delete_many({"date": {"$ne": today}})

# Schedule the clear_top_collection function to run daily
schedule.every().day.at("00:00").do(clear_top_collection)

# Message handler for counting emojis
message_handler = MessageHandler(Filters.TEXT & Filters.EMOJI, count_emojis)

# Create the Updater and pass it your bot's token
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("broadcast", broadcast, pass_args=True))
dispatcher.add_handler(CommandHandler("stats", stats))
dispatcher.add_handler(CommandHandler("topusers", top_users))
dispatcher.add_handler(CommandHandler("topgroups", top_groups))
dispatcher.add_handler(CommandHandler("profile", profile))
dispatcher.add_handler(CommandHandler("top", top))
dispatcher.add_handler(message_handler)

# Start the Bot
updater.start_polling()

# Run the bot until you press Ctrl-C
updater.idle()
