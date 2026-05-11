"""Pure market helpers for PolyArcade."""

from __future__ import annotations

from collections import deque
import math
import random

from .constants import (
    ARTICLE_FORCE,
    PRICE_HISTORY_LIMIT,
    ENDGAME_PULL,
    MARKET_DURATION_SECONDS,
    MAX_PRICE_VELOCITY,
    PRICE_GRAVITY,
    PRICE_NOISE,
    PRICE_STEP_DOLLARS,
    PRICE_WAVE_FORCE,
    RELIABILITY_MOVE_SCALE,
    RESOLVE_MOVE_BASE,
    RESOLVE_MOVE_SCALE,
    RESOLVE_PULL,
    ROUND_VOLATILITY_BASE,
    ROUND_VOLATILITY_BIAS,
    ROUND_VOLATILITY_RELIABILITY,
    SECONDARY_WAVE_FORCE,
    VELOCITY_DAMPING,
)
from .models import MarketState, NewsCard


def choose_news_cards(news_pool: list[NewsCard]) -> list[NewsCard]:
    cards = random.sample(news_pool, 3)
    for _ in range(12):
        average_bias = sum(card.price_bias for card in cards) / len(cards)
        if abs(average_bias) >= 0.22:
            return cards
        cards = random.sample(news_pool, 3)
    return cards


def combined_news_bias(news_cards: list[NewsCard]) -> float:
    return sum(card.price_bias for card in news_cards) / len(news_cards)


def make_opening_history(ending_price: float) -> deque[float]:
    return deque((ending_price for _ in range(80)), maxlen=PRICE_HISTORY_LIMIT)


def build_market(news_cards: list[NewsCard]) -> MarketState:
    starting_price = round(random.uniform(79_750, 80_350), 2)
    history = make_opening_history(starting_price)
    price_bias = combined_news_bias(news_cards)
    average_reliability = sum(card.reliability for card in news_cards) / (100 * len(news_cards))
    bias_strength = min(1.0, abs(price_bias))
    resolve_direction = 1 if price_bias >= 0 else -1
    resolve_move = (
        RESOLVE_MOVE_BASE
        + bias_strength * RESOLVE_MOVE_SCALE
        + average_reliability * RELIABILITY_MOVE_SCALE
        + random.uniform(20.0, 65.0)
    )
    resolve_move = round(resolve_move / PRICE_STEP_DOLLARS) * PRICE_STEP_DOLLARS
    resolve_price = round(max(1000, starting_price + resolve_direction * resolve_move), 2)
    volatility = (
        ROUND_VOLATILITY_BASE
        + bias_strength * ROUND_VOLATILITY_BIAS
        + average_reliability * ROUND_VOLATILITY_RELIABILITY
    )
    swing_phase = random.uniform(0.0, math.tau)
    swing_cycles = random.uniform(2.1, 3.8)
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
    distance_to_resolve = market.resolve_price - previous
    anchor_price = market.target_price + (market.resolve_price - market.target_price) * 0.35
    article_force = math.copysign(
        ARTICLE_FORCE * (0.8 + market.volatility * 0.4),
        market.price_bias or 1.0,
    )
    closing_pull = distance_to_resolve * (RESOLVE_PULL + progress * ENDGAME_PULL)
    gravity_force = (anchor_price - previous) * PRICE_GRAVITY
    primary_wave = math.sin(progress * math.tau * market.swing_cycles + market.swing_phase)
    primary_wave *= PRICE_WAVE_FORCE * market.volatility
    cross_wave = math.sin(
        progress * math.tau * (market.swing_cycles * 2.15) - market.swing_phase * 0.55
    )
    cross_wave *= SECONDARY_WAVE_FORCE * market.volatility
    smooth_noise = math.sin(progress * math.tau * (market.swing_cycles * 3.6) + market.swing_phase * 1.4)
    smooth_noise += math.sin(progress * math.tau * (market.swing_cycles * 5.2) - market.swing_phase * 0.95) * 0.55
    smooth_noise *= PRICE_NOISE * market.volatility
    jitter_force = random.uniform(-1.0, 1.0) * PRICE_NOISE * 0.22 * market.volatility
    jitter_force *= math.sqrt(max(delta_time, 0.001))
    damping = price_velocity * VELOCITY_DAMPING

    price_velocity += (
        article_force + closing_pull + gravity_force + primary_wave + cross_wave + smooth_noise - damping
    ) * delta_time + jitter_force
    price_velocity = max(-MAX_PRICE_VELOCITY, min(MAX_PRICE_VELOCITY, price_velocity))

    new_price = previous + price_velocity * delta_time
    if progress > 0.82:
        settle_blend = (progress - 0.82) / 0.18
        new_price += distance_to_resolve * settle_blend * 0.25
    current_price = round(max(1000, new_price), 2)
    return price_velocity, current_price


def contract_price(market: MarketState, side: str) -> int:
    gap = market.current_price - market.target_price
    progress = market.elapsed_seconds / MARKET_DURATION_SECONDS
    expected_move = max(55.0, abs(market.resolve_price - market.target_price) * 0.55)
    price_scale = max(28.0, expected_move * (1 - progress * 0.4))
    score = gap / price_scale
    score = max(-6.0, min(6.0, score))
    up_probability = 1 / (1 + math.exp(-score))
    up_price = max(4, min(96, round(up_probability * 100)))
    if side == "Up":
        return up_price
    return 100 - up_price
