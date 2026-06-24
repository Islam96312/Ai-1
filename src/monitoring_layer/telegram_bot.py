import requests
import logging
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Sends notifications to a Telegram channel/user.
    """
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    def send_message(self, text: str):
        """
        Sends a text message via Telegram API.
        """
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not set. Skipping notification.")
            return False
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.ok
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False
