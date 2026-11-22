from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://album:album@localhost:5432/album"
    web_origin: str = "http://localhost:3000"
    admin_password: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key_path: Path | None = None
    content_dir: Path = Path(__file__).resolve().parents[3] / "content" / "albums"
    # Fetched pages and API responses for the information finder (never served, gitignored).
    research_cache_dir: Path = Path(__file__).resolve().parents[3] / ".research-cache"
    # Information finder model (a Claude Code alias or full name) and thinking effort.
    research_model: str = "sonnet"
    research_effort: str = "medium"


settings = Settings()
