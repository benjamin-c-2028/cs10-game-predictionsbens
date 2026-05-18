"""Pure market helpers for PolyArcade."""

from __future__ import annotations

from collections import deque
import math
import random

from .constants import (
    MARKET_DURATION_SECONDS,
    MAX_PRICE_VELOCITY,
    PRICE_HISTORY_LIMIT,
    RELIABILITY_MOVE_SCALE,
    RESOLVE_MOVE_BASE,
    RESOLVE_MOVE_SCALE,
    ROUND_VOLATILITY_BASE,
    ROUND_VOLATILITY_BIAS,
    ROUND_VOLATILITY_RELIABILITY,
)
from .models import MarketState, NewsCard


def _rebalance_display_reliability(cards: list[NewsCard]) -> list[NewsCard]:
    """Ensure exactly one shown article reliability is above 80%."""
    if not cards:
        return []

    high_index = max(range(len(cards)), key=lambda index: cards[index].reliability)
    normalized_cards: list[NewsCard] = []
    for index, card in enumerate(cards):
        reliability = max(81, card.reliability) if index == high_index else min(80, card.reliability)
        normalized_cards.append(
            NewsCard(
                card.headline,
                card.source,
                card.analysis_label,
                reliability,
                card.price_bias,
            )
        )
    return normalized_cards


def choose_news_cards(news_pool: list[NewsCard]) -> list[NewsCard]:
    cards = random.sample(news_pool, 3)
    for _ in range(12):
        average_bias = sum(card.price_bias for card in cards) / len(cards)
        if abs(average_bias) >= 0.14:
            return _rebalance_display_reliability(cards)
        cards = random.sample(news_pool, 3)
    return _rebalance_display_reliability(cards)


def combined_news_bias(news_cards: list[NewsCard]) -> float:
    return sum(card.price_bias for card in news_cards) / len(news_cards)


def make_opening_history(ending_price: float) -> deque[float]:
    return deque((ending_price for _ in range(80)), maxlen=PRICE_HISTORY_LIMIT)


def build_market(news_cards: list[NewsCard]) -> MarketState:
    starting_price = round(random.uniform(79_750, 80_350), 2)
    history = make_opening_history(starting_price)
    price_bias = combined_news_bias(news_cards)
    average_reliability = sum(max(81, card.reliability) for card in news_cards) / (100 * len(news_cards))
    bias_strength = min(1.0, abs(price_bias))
    resolve_direction = 1 if price_bias >= 0 else -1
    resolve_move = (
        RESOLVE_MOVE_BASE
        + bias_strength * RESOLVE_MOVE_SCALE
        + average_reliability * RELIABILITY_MOVE_SCALE
        + random.uniform(0.8, 6.4)
    )
    resolve_price = round(max(1000, starting_price + resolve_direction * resolve_move), 2)
    volatility = (
        ROUND_VOLATILITY_BASE
        + bias_strength * ROUND_VOLATILITY_BIAS
        + average_reliability * ROUND_VOLATILITY_RELIABILITY
    )
    swing_phase = random.uniform(0.0, math.tau)
    swing_cycles = random.uniform(5.8, 8.8)
    return MarketState(
        target_price=starting_price,
        current_price=starting_price,
        history=history,
        elapsed_seconds=0.0,
        active=False,
        settled=False,
        price_bias=price_bias,
        resolve_price=resolve_price,
        volatility=volatility,
        swing_phase=swing_phase,
        swing_cycles=swing_cycles,
    )


def advance_market_price(market: MarketState, price_velocity: float, delta_time: float) -> tuple[float, float]:
    progress = max(0.0, min(1.0, market.elapsed_seconds / MARKET_DURATION_SECONDS))
    previous = market.current_price
    resolve_delta = market.resolve_price - market.target_price

    # Deterministic drift toward the preset settle level.
    smooth_progress = progress * progress * (3 - 2 * progress)
    drift = resolve_delta * smooth_progress

    # Volatile multi-wave movement (no per-frame randomness) for a "crazy" look.
    envelope = math.sin(math.pi * progress) ** 0.88
    wave_strength = 8.5 + market.volatility * 3.8 + abs(resolve_delta) * 0.18
    primary_wave = math.sin(progress * math.tau * market.swing_cycles + market.swing_phase)
    secondary_wave = math.sin(
        progress * math.tau * (market.swing_cycles * 2.4) - market.swing_phase * 0.66
    )
    tertiary_wave = math.sin(
        progress * math.tau * (market.swing_cycles * 4.8) + market.swing_phase * 1.7
    )
    oscillation = envelope * wave_strength * (
        0.9 * primary_wave + 0.55 * secondary_wave + 0.25 * tertiary_wave
    )

    # Force both-direction action around the target line for stronger visual tension.
    dip_center = 0.30 + 0.05 * math.sin(market.swing_phase * 0.5)
    spike_center = 0.56 + 0.04 * math.cos(market.swing_phase * 0.7)
    dip_width = 0.11
    spike_width = 0.12
    forced_dip = -(8.5 + max(0.0, resolve_delta) * 0.45) * math.exp(
        -((progress - dip_center) / dip_width) ** 2
    )
    forced_spike = (7.5 + max(0.0, -resolve_delta) * 0.45) * math.exp(
        -((progress - spike_center) / spike_width) ** 2
    )

    raw_delta = drift + oscillation + forced_dip + forced_spike

    path_delta = raw_delta

    # Snap cleanly into the predetermined settle result near the end of the round.
    if progress > 0.94:
        settle_blend = (progress - 0.94) / 0.06
        path_delta = path_delta * (1 - settle_blend) + resolve_delta * settle_blend

    current_price = round(max(1000, market.target_price + path_delta), 2)
    derived_velocity = (current_price - previous) / max(delta_time, 1e-6)
    derived_velocity = max(-MAX_PRICE_VELOCITY, min(MAX_PRICE_VELOCITY, derived_velocity))
    return derived_velocity, current_price


def contract_price(market: MarketState, side: str) -> int:
    if market.settled:
        winning_side = "Up" if market.current_price >= market.target_price else "Down"
        return 100 if side == winning_side else 0

    gap = market.current_price - market.target_price
    progress = market.elapsed_seconds / MARKET_DURATION_SECONDS
    expected_move = max(8.0, abs(market.resolve_price - market.target_price) * 0.9)
    price_scale = max(4.8, expected_move * (1 - progress * 0.65))
    score = gap / price_scale
    score = max(-6.0, min(6.0, score))
    up_probability = 1 / (1 + math.exp(-score))
    up_price = max(1, min(99, round(up_probability * 100)))
    if side == "Up":
        return up_price
    return 100 - up_price
