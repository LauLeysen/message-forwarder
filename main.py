import requests
import os
import logging
import re
from dotenv import load_dotenv
from colorlog import ColoredFormatter
from time import sleep
import json
import threading

load_dotenv()
FILTER_WORDS = ["Binance", "Futures", "Kucoin", "ByBit"]

log = logging.getLogger("discord_logger")
log.setLevel(logging.DEBUG)
formatter = ColoredFormatter(
    "%(log_color)s[%(levelname)s]%(reset)s %(message_log_color)s%(message)s",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    },
    secondary_log_colors={
        'message': {
            'INFO': 'white',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red'
        }
    },
)
ch = logging.StreamHandler()
ch.setFormatter(formatter)
log.addHandler(ch)

channelids = os.getenv("CHANNEL_IDS").split(",")
token = os.getenv("DISCORD_TOKEN")
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

headers = {"Authorization": token}


def load_last_message(channelid):
    last_message_file = f'last_message_{channelid}.json'
    if os.path.exists(last_message_file):
        with open(last_message_file, 'r') as file:
            data = json.load(file)
            return data.get('last_message_id')
    return None


def save_last_message(channelid, message_id):
    last_message_file = f'last_message_{channelid}.json'
    with open(last_message_file, 'w') as file:
        json.dump({'last_message_id': message_id}, file)


def checkStatus(response):
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 403:
        log.warning("Access is locked (403 Forbidden).")
        return "locked"
    elif response.status_code == 429:
        log.warning("Rate limited (429 Too Many Requests).")
        return "rate limited"
    else:
        log.error("Invalid token or unexpected error.")
        return "invalid token"


def checkToken():
    log.info("Checking token validity...")
    response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
    data = checkStatus(response)
    # Check if data is valid and return username if available
    if isinstance(data, dict) and 'username' in data:
        log.info(f"Token is valid. Username: {data['username']}")
        return data['username']
    else:
        return data


def getMessages(channelid):
    response = requests.get(f"https://discord.com/api/channels/{channelid}/messages", headers=headers)
    return checkStatus(response)


def getChannel(channelid):
    log.info(f"Getting channel information for channel {channelid}...")
    response = requests.get(f"https://discord.com/api/channels/{channelid}", headers=headers)
    data = checkStatus(response)
    if isinstance(data, dict) and 'name' in data:
        log.info(f"Monitoring channel: {data['name']} (ID: {channelid})")
        return data['name']
    else:
        log.error(f"Failed to retrieve channel information for channel {channelid}.")
        return None


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        'chat_id': telegram_chat_id,
        'text': message
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        log.info("Message forwarded to Telegram successfully.")
    else:
        log.error(f"Failed to send message to Telegram. Status code: {response.status_code}")


def monitorFirstMessage(channelid, channel_name):
    log.info(f"Monitoring for new messages in channel {channel_name} (ID: {channelid})...")
    last_message_id = load_last_message(channelid)
    first_run = True
    while True:
        messages = getMessages(channelid)
        if isinstance(messages, list) and len(messages) > 0:
            first_message = messages[0]
            message_id = first_message['id']
            if last_message_id is None or message_id != last_message_id:
                content = first_message.get('content', '')
                original_content = content

                # Build regex pattern for the filtered words
                pattern = r'\b(?:' + '|'.join(map(re.escape, FILTER_WORDS)) + r')\b'
                content = re.sub(pattern, '', content, flags=re.IGNORECASE).strip()

                if content != original_content.strip():
                    log.debug(f"Removed filtered words from content.")

                author_name = first_message.get('author', {}).get('global_name', 'Unknown')
                log.info(f"New message from {author_name} in channel {channel_name}")
                log.info(content)
                last_message_id = message_id
                save_last_message(channelid, message_id)
                send_telegram_message(content)
                first_run = False
            elif first_run:
                log.info(f"No new messages in channel {channel_name}.")
                first_run = False
        elif messages == "rate limited":
            log.warning("Rate limited, waiting before retrying...")
        else:
            log.error(f"Unable to retrieve messages for channel {channel_name}.")
        sleep(1)


if __name__ == "__main__":
    username = checkToken()
    if username != "invalid token" and username != "locked" and username != "rate limited":
        threads = []
        for channelid in channelids:
            channel_name = getChannel(channelid)
            if channel_name:
                log.info(f"Starting monitoring for channel {channel_name} (ID: {channelid})")
                t = threading.Thread(target=monitorFirstMessage, args=(channelid, channel_name))
                t.start()
                threads.append(t)
            else:
                log.error(f"Skipping channel {channelid} due to failure in retrieving channel name.")
        # Keep the main thread alive
        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down...")
    else:
        log.error("Could not verify token or fetch messages.")
