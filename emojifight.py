# emojifight.py
import os
import pymongo
import datetime
import time
import schedule
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, Filters
from dotenv import load_dotenv
from emoji import UNICODE_EMOJI  # Make sure to install emoji package with "pip install emoji"
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

# Other command handlers...

# Function to handle all messages
def handle_messages(update: Update, context: CallbackContext) -> None:
    # Check if the message contains emojis
    message_text = update.message.text
    emojis = [char for char in message_text if char in UNICODE_EMOJI]

    if emojis:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Update points for the user
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"points": len(emojis)}},
            upsert=True
        )

        # Update points for the group
        groups_collection.update_one(
            {"chat_id": chat_id},
            {"$inc": {"points": len(emojis)}},
            upsert=True
        )

        # Update today's top users
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_top_users_collection.update_one(
            {"user_id": user_id, "date": today},
            {"$inc": {"points": len(emojis)}},
            upsert=True
        )

        # Update today's top groups
        today_top_groups_collection.update_one(
            {"chat_id": chat_id, "date": today},
            {"$inc": {"points": len(emojis)}},
            upsert=True
        )

# Schedule the clear_top_collection function to run daily
schedule.every().day.at("00:00").do(clear_top_collection)

# Create an instance of the Updater class
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
# Add other command handlers...
# Create a MessageHandler instance
message_handler = MessageHandler(Filters.all, handle_messages)
dispatcher.add_handler(message_handler)

# Start the Bot
updater.start_polling()
print("Your Bot Started Successfully!")

# Run the bot until you press Ctrl-C
updater.idle()
