import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file in the same directory
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to search path

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Binance Configuration
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com").rstrip("/")

# Allowed Group ID Configuration (Optional)
ALLOWED_GROUP_ID_RAW = os.getenv("ALLOWED_GROUP_ID")
ALLOWED_GROUP_ID = None

if ALLOWED_GROUP_ID_RAW:
    try:
        ALLOWED_GROUP_ID = int(ALLOWED_GROUP_ID_RAW)
    except ValueError:
        print(f"Warning: ALLOWED_GROUP_ID '{ALLOWED_GROUP_ID_RAW}' is not a valid integer. Group restriction will be bypassed.")

# Validate Required Configurations
missing_configs = []
if not TELEGRAM_BOT_TOKEN:
    missing_configs.append("TELEGRAM_BOT_TOKEN")
if not BINANCE_API_KEY:
    missing_configs.append("BINANCE_API_KEY")
if not BINANCE_API_SECRET:
    missing_configs.append("BINANCE_API_SECRET")

if missing_configs:
    raise ValueError(
        f"Missing required environment variables: {', '.join(missing_configs)}. "
        "Please check your .env file or environment variables."
    )
