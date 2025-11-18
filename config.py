from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMINS: List[int]
    PG_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()