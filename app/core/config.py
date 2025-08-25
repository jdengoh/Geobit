from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, BeforeValidator, PostgresDsn, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


def get_env_file_path() -> str | None:
    """
    Returns the file path to the .env file.

    Returns:
        str | None: The file path to the .env file or None if not found.
    """

    possible_paths = [
        ".env",
        # "../.env",
        # "../../.env",
        # "./.env",
    ]

    for path in possible_paths:
        if Path(path).exists():
            abs_path = Path(path).resolve()
            return str(abs_path)

    return None


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str | None

    # Auth Configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # Frontend Configuration
    FRONTEND_HOST: str = "http://localhost:3000"
    ENVIRONMENT: Literal["development", "production"] = "development"

    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = (
        []
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """
        Dynamically calculates CORS origins by combining backend CORS origins with the frontend host.

        Example Input:
        - BACKEND_CORS_ORIGINS = ["http://localhost:8000/", "https://api.myapp.com"]
        - FRONTEND_HOST = "http://localhost:3000"

        Result: ["http://localhost:8000", "https://api.myapp.com", "http://localhost:3000"]
        """
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    # DB Config
    # - Currently, this is configured to use Supabase's PostgreSQL database.
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )


@lru_cache  # builds once, the first time it’s asked for
def get_settings() -> Settings:
    return Settings()
