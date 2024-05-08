# GlobalConfig/config.py
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Accessing variables from .env
config = {
    "ws_url": os.getenv("WS_URL", "ws://66.114.112.70:40391/ws?clientId="),
    # "db_password": os.getenv("DB_PASSWORD", "default_password"),
    # "secret_key": os.getenv("SECRET_KEY", "your_default_secret_key"),
    # "another_config": os.getenv("ANOTHER_CONFIG", "default_value")
}
