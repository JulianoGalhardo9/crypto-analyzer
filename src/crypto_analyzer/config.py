from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente ou do arquivo `.env` (nunca commitado)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str


ASSETS_PATH = Path(__file__).parents[2] / "config" / "assets.yaml"


class AssetsConfig(BaseModel):
    quote: str
    assets: list[str]

    @property
    def symbols(self) -> list[str]:
        """Pares no formato da API, ex.: `BTC-BRL`."""
        return [f"{asset}-{self.quote}" for asset in self.assets]


def load_assets(path: Path = ASSETS_PATH) -> AssetsConfig:
    return AssetsConfig.model_validate(yaml.safe_load(path.read_text()))
