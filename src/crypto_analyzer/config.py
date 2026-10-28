from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente ou do arquivo `.env` (nunca commitado)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
