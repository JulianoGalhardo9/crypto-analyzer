from crypto_analyzer.config import load_assets


def test_assets_config_builds_api_symbols() -> None:
    config = load_assets()

    assert config.symbols == ["BTC-BRL", "ETH-BRL", "SOL-BRL"]
