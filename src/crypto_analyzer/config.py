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


QUALITY_PATH = Path(__file__).parents[2] / "config" / "quality.yaml"


class QualityConfig(BaseModel):
    outlier_threshold: float
    max_age_hours: dict[str, float]


def load_quality_config(path: Path = QUALITY_PATH) -> QualityConfig:
    return QualityConfig.model_validate(yaml.safe_load(path.read_text()))


REGIMES_PATH = Path(__file__).parents[2] / "config" / "regimes.yaml"


class RegimeConfig(BaseModel):
    volatility_window: int
    percentile_window: int
    min_history: int
    calm_below: float
    high_above: float
    confirm_days: int


def load_regime_config(path: Path = REGIMES_PATH) -> RegimeConfig:
    return RegimeConfig.model_validate(yaml.safe_load(path.read_text()))
