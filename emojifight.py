# emojifight.py
import os
import pymongo
import datetime
import time
import schedule
from emoji import emoji_count
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, Filters, Dispatcher
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
today_top_users_collection = db["todaytopusers"]
today_top_groups_collection = db["todaytopgroups"]

# Function to clear top collections
def clear_top_collection():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    # Clear today's top users collection
    today_top_users_collection.delete_many({"date": {"$ne": today}})
    # Clear today's top groups collection
    today_top_groups_collection.delete_many({"date": {"$ne": today}})

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if chat_id > 0:  # Private chat
        update.message.reply_text('Hello! I am EmojiFight bot. Use /help to see available commands.')
        # Save user in users collection
        users_collection.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
    else:  # Group chat
        # Save group chat id in groups collection
        groups_collection.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
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
    command_args = context.args

    if "today" in command_args:
        show_today_top_users(update)
    else:
        show_overall_top_users(update)

def top_groups(update: Update, context: CallbackContext) -> None:
    command_args = context.args

    if "today" in command_args:
        show_today_top_groups(update)
    else:
        show_overall_top_groups(update)

def show_today_top_users(update: Update):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    top_users = today_top_users_collection.find({"date": today}).sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 users with most emoji messages today:\n"
    for user in top_users:
        message += f"{user['user_id']} - {user['points']} messages\n"
    update.message.reply_text(message)

def show_overall_top_users(update: Update):
    top_users = top_users_collection.find().sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 users with most emoji messages overall:\n"
    for user in top_users:
        message += f"{user['user_id']} - {user['points']} messages\n"
    update.message.reply_text(message)

def show_today_top_groups(update: Update):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    top_groups = today_top_groups_collection.find({"date": today}).sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 groups with most emoji messages today:\n"
    for group in top_groups:
        message += f"{group['chat_id']} - {group['points']} messages\n"
    update.message.reply_text(message)

def show_overall_top_groups(update: Update):
    top_groups = top_groups_collection.find().sort("points", pymongo.DESCENDING).limit(10)
    message = "Top 10 groups with most emoji messages overall:\n"
    for group in top_groups:
        message += f"{group['chat_id']} - {group['points']} messages\n"
    update.message.reply_text(message)

# ...

def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    update.message.reply_text(f"Your profile: User ID - {user_id}")

# Schedule the clear_top_collection function to run daily
schedule.every().day.at("00:00").do(clear_top_collection)

def top(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    if chat_id > 0:
        update.message.reply_text("This command is only supported in group chats.")
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    top_users = today_top_users_collection.find({"date": today, "chat_id": chat_id}).sort("points", pymongo.DESCENDING).limit(10)

    message = f"Top 10 users with most emoji messages today in this group:\n"
    for user in top_users:
        message += f"{user['user_id']} - {user['points']} messages\n"

    update.message.reply_text(message)

# Function to count emojis in a message
def count_emojis(message: str) -> int:
    return emoji_count(message)

# Function to handle all messages
def handle_messages(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text
    emojis_count = count_emojis(message_text)
    print(f"Number of emojis in the message: {emojis_count}")

# Create a MessageHandler instance
message_handler = MessageHandler(Filters.text & ~Filters.command, handle_messages)

# Create an instance of the Updater class
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
print("Your Bot Started Successfully!")

# Run the bot until you press Ctrl-C
updater.idle()
