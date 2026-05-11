"""Shared data models for PolyArcade."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsCard:
    headline: str
    source: str
    analysis_label: str
    reliability: int
    price_bias: float


@dataclass
class MarketState:
    target_price: float
    current_price: float
    history: list[float]
    elapsed_seconds: float
    active: bool
    settled: bool
    price_bias: float
    resolve_price: float
    volatility: float
    swing_phase: float
    swing_cycles: float


@dataclass
class Position:
    side: str
    amount: int
    entry_price_cents: int
    shares: float
    resolved_result: str | None = None


@dataclass(frozen=True)
class TradeRecord:
    market: str
    side: str
    amount: int
    entry_price_cents: int
    result: str
    profit_loss: float
    balance_after: float


@dataclass(frozen=True)
class ClickZone:
    key: str
    left: float
    bottom: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.left + self.width and self.bottom <= y <= self.bottom + self.height

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.bottom + self.height / 2


@dataclass(frozen=True)
class TutorialArticle:
    source: str
    headline: str
    summary: str


@dataclass(frozen=True)
class TutorialClickTarget:
    button_label: str
    title: str
    detail: str
