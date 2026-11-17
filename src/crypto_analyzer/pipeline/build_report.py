from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import AssetsConfig, QualityConfig, RegimeConfig, ReportConfig
from crypto_analyzer.infra.repositories import (
    load_closed_candles,
    load_fact_frame,
    load_quality_issues,
)
from crypto_analyzer.infra.tables import FactIndicador, FactRegime
from crypto_analyzer.pipeline.build_analysis import RESOLUTION, build_analysis
from crypto_analyzer.reports.frames import QualityRecord, ReportData


def build_report_data(
    session_factory: sessionmaker[Session],
    assets: AssetsConfig,
    now: datetime,
    quality: QualityConfig,
    regime: RegimeConfig,
    report: ReportConfig,
) -> ReportData:
    """Lê do banco tudo o que a planilha mostra. Levanta `NoDataError` se falta o gold."""
    # A análise de cada ativo é a mesma do comando `analisar` (e valida que há dados).
    analyses = [
        build_analysis(session_factory, assets, asset.symbol, now, quality, regime)
        for asset in assets.assets
    ]
    with session_factory() as session:
        candles = {s: load_closed_candles(session, s, RESOLUTION) for s in assets.symbols}
        indicators = {s: load_fact_frame(session, FactIndicador, s) for s in assets.symbols}
        regimes = {s: load_fact_frame(session, FactRegime, s) for s in assets.symbols}
        issues = [
            QualityRecord(
                row.symbol, row.check_name, row.severity, row.ts_start, row.ts_end, row.detail
            )
            for row in load_quality_issues(session, RESOLUTION)
            if row.symbol in assets.symbols
        ]

    return ReportData(
        assets=assets,
        candles=candles,
        indicators=indicators,
        regimes=regimes,
        quality=issues,
        analyses=analyses,
        generated_at=now,
        window_days=report.window_days,
    )
