import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    API_URL = os.getenv("API_URL")
    ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
    API_SHARED_SECRET = os.getenv("API_SHARED_SECRET")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY")

def get_settings():
    return Settings()