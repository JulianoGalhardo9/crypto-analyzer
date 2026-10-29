from crypto_analyzer.config import load_assets


def test_assets_config_builds_api_symbols() -> None:
    config = load_assets()

    assert config.symbols == ["BTC-BRL", "ETH-BRL", "SOL-BRL"]


def test_assets_config_has_names_and_the_benchmark_among_the_assets() -> None:
    config = load_assets()

    assert [asset.name for asset in config.assets] == ["Bitcoin", "Ethereum", "Solana"]
    assert config.benchmark_symbol == "BTC-BRL"
    assert config.benchmark_symbol in config.symbols
