from pathlib import Path

import pydantic

PKG_DIR = Path(__file__).parent.parent


class Settings(pydantic.BaseSettings):
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_TOKEN_SECRET: str = ""
    TWITTER_CONSUMER_KEY: str = ""
    TWITTER_CONSUMER_SECRET: str = ""

    class Config:
        env_file = PKG_DIR / ".env"


CFG = Settings()
