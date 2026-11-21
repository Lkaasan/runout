from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://album:album@localhost:5432/album"
    web_origin: str = "http://localhost:3000"
    admin_password: str = ""


settings = Settings()
