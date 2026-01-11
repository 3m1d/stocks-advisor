from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.db_models.base import Base


class AssetCandle(Base):
    """Свечи с MOEX"""

    __tablename__ = 'asset_candle'

    # ID
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Тикер
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)

    # Период свечи
    begin: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    end: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    # OHLC
    open: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)

    # Общая стоимость и объем торгов
    value: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Дата создания записи в БД
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text('CURRENT_TIMESTAMP'),
    )

    __table_args__ = (
        UniqueConstraint('ticker', 'begin', name='unique_ticker_begin'),
        Index('idx_asset_candle_ticker', 'ticker'),
        Index('idx_asset_candle_begin', 'begin'),
    )

    def __repr__(self) -> str:
        return f'<AssetCandle(id={self.id}, ticker={self.ticker!r}, begin={self.begin}, close={self.close})>'
