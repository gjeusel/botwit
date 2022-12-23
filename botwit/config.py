from pathlib import Path

import pydantic
from pydantic import SecretStr

PKG_DIR = Path(__file__).parent.parent


class Settings(pydantic.BaseSettings):
    TWITTER_CONSUMER_KEY: SecretStr = SecretStr("")
    TWITTER_CONSUMER_SECRET: SecretStr = SecretStr("")

    NOTION_SECRET_KEY: SecretStr = SecretStr("")
    NOTION_DATABASE_ID: str = "da6fbd029f4342f781703542e1afb6a0"
    NOTION_PAGE_ID: str = "e51313db-8f4d-4e17-a4ff-2eae07d67e56"

    class Config:
        env_file = PKG_DIR / ".env"


CFG = Settings()
