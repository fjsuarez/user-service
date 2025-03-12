from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    PORT: int
    DATABASE_URL: str
    FIREBASE_API_KEY: str

    model_config = ConfigDict(env_file='.env')

settings = Settings()