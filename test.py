import json
from common.poll import Poll
from flask import Flask, request
from dotenv import load_dotenv
from datetime import datetime
import os

from common.utils import create_webhook
from webexpythonsdk import WebexAPI, Webhook

# Load environment variables from .env file
load_dotenv()

# Get the bot access token from the environment variable
WEBEX_TEAMS_ACCESS_TOKEN = os.getenv('WEBEX_TEAMS_ACCESS_TOKEN')
if not WEBEX_TEAMS_ACCESS_TOKEN:
    raise ValueError("WEBEX_TEAMS_ACCESS_TOKEN1 is not set correctly in the environment variables")

teams_api = None
all_polls = {}

app = Flask(__name__)
reminders = {}  # Dictionary to store reminders with roomId as key

@app.route('/messages_webhook', methods=['POST'])
def messages_webhook():
    if request.method == 'POST':
        webhook_obj = Webhook(request.json)
        return process_message(webhook_obj.data)

def send_message_in_room(room_id, message):
    teams_api.messages.create(roomId=room_id, text=message)

def create_reminder(command, sender, roomId):
    try:
        parts = command.split(maxsplit=4)
        if len(parts) < 5:
            send_message_in_room(roomId, "Invalid format. Use: create reminder YYYY-MM-DD HH:MM Description")
            return

        date_str, time_str, description = parts[2], parts[3], parts[4]
        reminder_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        if roomId not in reminders:
            reminders[roomId] = []
        
        reminders[roomId].append((reminder_time, description))
        send_message_in_room(roomId, f"Reminder set for {reminder_time} - {description}")
    except ValueError:
        send_message_in_room(roomId, "Error: Incorrect date or time format. Use YYYY-MM-DD HH:MM")

def list_reminders(roomId, sender):
    if roomId in reminders and reminders[roomId]:
        message = "Upcoming reminders:\n"
        for idx, (reminder_time, description) in enumerate(reminders[roomId], 1):
            message += f"{idx}. {reminder_time}: {description}\n"
        send_message_in_room(roomId, message)
    else:
        send_message_in_room(roomId, "No reminders set.")

def delete_reminder(command, roomId, sender):
    try:
        _, reminder_number = command.split(maxsplit=2)
        reminder_index = int(reminder_number) - 1
        
        if roomId in reminders and 0 <= reminder_index < len(reminders[roomId]):
            removed = reminders[roomId].pop(reminder_index)
            send_message_in_room(roomId, f"Removed reminder: {removed[1]} at {removed[0]}")
        else:
            send_message_in_room(roomId, "Invalid reminder number.")
    except (ValueError, IndexError):
        send_message_in_room(roomId, "Error: Use 'delete reminder <number>'")

def process_message(data):
    if data.personId == teams_api.people.me().id:
        # Message sent by bot, do not respond
        return '200'
    else:
        message = teams_api.messages.get(data.id).text
        print(message)
        commands_split = (message.split())[1:]
        command = ' '.join(commands_split)
        parse_message(command, data.personEmail, data.roomId)
        return '200'

def parse_message(command, sender, roomId):
    if command.startswith("create reminder"):
        create_reminder(command, sender, roomId)
    elif command == "list reminders":
        list_reminders(roomId, sender)
    elif command.startswith("delete reminder"):
        delete_reminder(command, roomId, sender)
    elif command == "help":
        help(roomId, sender)
    else:
        send_message_in_room(roomId, "Unknown command. Type 'help' for a list of valid commands.")
    return

def send_direct_message(person_email, message):
    teams_api.messages.create(toPersonEmail=person_email, text=message)

def help(roomId, sender):
    help_text = """
    What would you like help with?
    1) create reminder YYYY-MM-DD HH:MM Description
    2) list reminders
    3) delete reminder <number>
    """
    send_message_in_room(roomId, help_text)

if __name__ == '__main__':
    teams_api = WebexAPI(access_token=WEBEX_TEAMS_ACCESS_TOKEN)
    create_webhook(teams_api, 'messages_webhook', '/messages_webhook', 'messages')
    create_webhook(teams_api, 'attachmentActions_webhook', '/attachmentActions_webhook', 'attachmentActions')
    app.run(host='0.0.0.0', port=12000)
