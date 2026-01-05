from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    # Prefer DATABASE_URL if present; otherwise build from POSTGRES_* vars
    DATABASE_URL: str | None = Field(default=None, alias="DATABASE_URL")

    POSTGRES_DB: str = Field(default="locksum", alias="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="locksum", alias="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="locksum_dev_password", alias="POSTGRES_PASSWORD")
    POSTGRES_HOST: str = Field(default="db", alias="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, alias="POSTGRES_PORT")

    # --- Security ---
    API_SECRET_KEY: str = Field(default="super-secret-change-me-now", alias="API_SECRET_KEY")
    API_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10080, alias="API_ACCESS_TOKEN_EXPIRE_MINUTES")

    # --- CORS ---
    # .env uses: API_CORS_ORIGINS=http://localhost:5173,http://localhost
    API_CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost", alias="API_CORS_ORIGINS")

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.API_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        # build default docker url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
