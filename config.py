# config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    bot_token: str
    valid_user_tokens: set[str]
    api_url: str
    timezone: str

def load_config() -> Settings:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")

    tokens_str = os.getenv("VALID_USER_TOKENS", "")
    valid_tokens = set(token.strip() for token in tokens_str.split(','))

    return Settings(
        bot_token=bot_token,
        valid_user_tokens=valid_tokens,
        api_url="https://belarusborder.by/info/monitoring-new?token=test&checkpointId=a9173a85-3fc0-424c-84f0-defa632481e4",
        timezone="Europe/Minsk"
    )

config = load_config()