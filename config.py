from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).parent / ".env")


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-5.4-mini"
    tavily_api_key: str
    codebase_path: str = "/Users/ilirgruda/Repo/Python/ai-learning"
    gh_repo: str = ""

    # DataForSEO (replaces the prior SerpAPI + pytrends tooling).
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_max_cost_per_run: float = 1.00
    dataforseo_max_calls_per_run: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
