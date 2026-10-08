from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sei_base_url: str = "https://sei.exemplo.gov.br/sei"
    sei_usuario: str = ""
    sei_senha: str = ""
    sei_orgao: str = ""

    headless: bool = True
    nav_timeout_ms: int = 30_000
    # pool de contextos: quantos "navegadores lógicos" simultâneos
    pool_size: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
