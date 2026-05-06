"""Simulated Bitcoin Up/Down prediction market built with Python Arcade."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import arcade


WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 880
WINDOW_TITLE = "Bitcoin Up or Down Arcade"

MARKET_DURATION_SECONDS = 15
STARTING_BALANCE = 1000
DEFAULT_ORDER_AMOUNT = 25
PRICE_TICK_SECONDS = 1 / 30
PRICE_HISTORY_LIMIT = 180
MARKET_TRANSITION_SPEED = 3.4

BACKGROUND = (14, 18, 23)
HEADER = (17, 22, 28)
PANEL = (22, 28, 36)
PANEL_ALT = (27, 35, 44)
PANEL_SOFT = (33, 42, 53)
BORDER = (45, 55, 68)
TEXT = (239, 243, 248)
MUTED = (141, 151, 166)
MUTED_DARK = (100, 112, 128)
ORANGE = (247, 151, 38)
GREEN = (81, 164, 103)
GREEN_DARK = (45, 113, 70)
RED = (221, 83, 78)
RED_DARK = (138, 51, 51)
BLUE = (74, 144, 245)
YELLOW = (238, 191, 72)
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class NewsCard:
    headline: str
    source: str
    analysis_label: str
    reliability: float
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


@dataclass
class Position:
    side: str
    amount: int
    entry_price_cents: int
    shares: float
    resolved_result: str | None = None


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


UPWARD_BIAS_NEWS = [
    NewsCard(
        "Bitcoin ETF desks report steady inflows",
        "Crypto Wire",
        "High-Impact Analysis",
        0.92,
        0.42,
    ),
    NewsCard(
        "Miners slow BTC transfers to exchanges",
        "Block Ledger",
        "Indirect Connections: Bitcoin's Echoes",
        0.76,
        0.34,
    ),
    NewsCard(
        "Risk assets bounce after softer rate comments",
        "Macro Desk",
        "Bitcoin and Beyond: The Subtler Link",
        0.80,
        0.31,
    ),
    NewsCard(
        "Stablecoin liquidity rises across major exchanges",
        "Market Pulse",
        "Indirect Connections: Bitcoin's Echoes",
        0.76,
        0.26,
    ),
]

DOWNWARD_BIAS_NEWS = [
    NewsCard(
        "Exchange wallets receive a burst of BTC deposits",
        "Chain Watch",
        "High-Impact Analysis",
        0.92,
        -0.39,
    ),
    NewsCard(
        "Dollar strength pressures crypto markets",
        "Macro Desk",
        "Bitcoin and Beyond: The Subtler Link",
        0.80,
        -0.33,
    ),
    NewsCard(
        "Leveraged longs face liquidation risk",
        "Derivatives Daily",
        "High-Impact Analysis",
        0.92,
        -0.36,
    ),
    NewsCard(
        "Regulatory headline cools crypto momentum",
        "Policy Wire",
        "Bitcoin and Beyond: The Subtler Link",
        0.80,
        -0.28,
    ),
]

LOW_BIAS_NEWS = [
    NewsCard(
        "Bitcoin trades inside a narrow short-term range",
        "Ticker Desk",
        "Indirect Connections: Bitcoin's Echoes",
        0.76,
        0.02,
    ),
    NewsCard(
        "Options desk says near-term volatility is balanced",
        "Vol Report",
        "Bitcoin and Beyond: The Subtler Link",
        0.80,
        -0.01,
    ),
    NewsCard(
        "Spot volume holds near its daily average",
        "Exchange Beat",
        "Indirect Connections: Bitcoin's Echoes",
        0.76,
        0.00,
    ),
]


class BitcoinPredictionGame(arcade.Window):
    """Polymarket-inspired arcade game with article-driven BTC movement."""

    def __init__(self) -> None:
        super().__init__(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            WINDOW_TITLE,
            resizable=False,
            update_rate=1 / 60,
            draw_rate=1 / 60,
        )
        arcade.set_background_color(BACKGROUND)

        self.balance = STARTING_BALANCE
        self.selected_side = "Up"
        self.selected_amount = DEFAULT_ORDER_AMOUNT
        self.position: Position | None = None
        self.status_message = "Read the article, choose Up or Down, then buy to start the market."
        self.tick_accumulator = 0.0
        self.price_velocity = 0.0
        self.market_transition = 1.0
        self.hovered_key: str | None = None
        self.click_zones: list[ClickZone] = []
        self.news_card = random.choice(UPWARD_BIAS_NEWS + DOWNWARD_BIAS_NEWS + LOW_BIAS_NEWS)
        self.market = self._new_market()

    def _new_market(self) -> MarketState:
        self.tick_accumulator = 0.0
        self.price_velocity = 0.0
        self.market_transition = 0.0
        self.position = None
        self.selected_side = "Up"
        self.selected_amount = DEFAULT_ORDER_AMOUNT
        self.news_card = self._choose_news_card()

        starting_price = round(random.uniform(79_750, 80_350), 2)
        history = self._make_opening_history(starting_price)
        price_bias = self.news_card.price_bias
        self.status_message = "Read the article. The market starts only after you buy a position."

        return MarketState(
            target_price=starting_price,
            current_price=starting_price,
            history=history,
            elapsed_seconds=0.0,
            active=False,
            settled=False,
            price_bias=price_bias,
        )

    def _choose_news_card(self) -> NewsCard:
        return random.choice(UPWARD_BIAS_NEWS + DOWNWARD_BIAS_NEWS + LOW_BIAS_NEWS)

    def _make_opening_history(self, ending_price: float) -> list[float]:
        return [ending_price for _ in range(80)]

    def on_draw(self) -> None:
        self.clear()
        self.click_zones = []
        self._draw_header()
        self._draw_market()
        self._draw_ticket()
        self._draw_news_cards()
        self._draw_transition_overlay()

    def on_update(self, delta_time: float) -> None:
        self.market_transition = min(
            1.0,
            self.market_transition + delta_time * MARKET_TRANSITION_SPEED,
        )

        if not self.market.active or self.market.settled:
            return

        self.market.elapsed_seconds = min(
            MARKET_DURATION_SECONDS,
            self.market.elapsed_seconds + delta_time,
        )
        self._advance_price(delta_time)
        self.tick_accumulator += delta_time

        while self.tick_accumulator >= PRICE_TICK_SECONDS and not self.market.settled:
            self.tick_accumulator -= PRICE_TICK_SECONDS
            self.market.history.append(self.market.current_price)
            if len(self.market.history) > PRICE_HISTORY_LIMIT:
                self.market.history.pop(0)

        if self.market.elapsed_seconds >= MARKET_DURATION_SECONDS and not self.market.settled:
            self._settle_market()

    def _advance_price(self, delta_time: float) -> None:
        progress = self.market.elapsed_seconds / MARKET_DURATION_SECONDS
        previous = self.market.current_price
        trend_force = self.market.price_bias * 7.5
        gravity_force = (self.market.target_price - previous) * 0.045
        wave_force = math.sin(progress * math.tau * 2.4) * 2.6
        random_force = random.uniform(-1.0, 1.0) * 12.0 * math.sqrt(max(delta_time, 0.001))
        damping = self.price_velocity * 1.65

        self.price_velocity += (
            trend_force + gravity_force + wave_force - damping
        ) * delta_time + random_force
        self.price_velocity = max(-38.0, min(38.0, self.price_velocity))

        new_price = previous + self.price_velocity * delta_time
        self.market.current_price = round(max(1000, new_price), 2)

    def _settle_market(self) -> None:
        self.market.active = False
        self.market.settled = True

        winning_side = "Up" if self.market.current_price >= self.market.target_price else "Down"
        if self.position is None:
            self.status_message = f"Market settled {winning_side}. No position was opened."
            return

        if self.position.side == winning_side:
            payout = round(self.position.shares, 2)
            self.balance += payout
            self.position.resolved_result = "Won"
            self.status_message = (
                f"{winning_side} wins. Your ${self.position.amount} position paid ${payout:,.2f}."
            )
        else:
            self.position.resolved_result = "Lost"
            self.status_message = (
                f"{winning_side} wins. Your {self.position.side} position expired at $0."
            )

    def _buy_position(self) -> None:
        if self.position is not None:
            self.status_message = "You already bought this market. Wait for settlement."
            return
        if self.market.settled:
            self.status_message = "This market is settled. Start a new market."
            return
        if self.selected_amount > self.balance:
            self.status_message = "Not enough balance for that order amount."
            return

        entry_price = self._contract_price(self.selected_side)
        shares = self.selected_amount / (entry_price / 100)
        self.balance -= self.selected_amount
        self.position = Position(
            side=self.selected_side,
            amount=self.selected_amount,
            entry_price_cents=entry_price,
            shares=shares,
        )
        self.market.active = True
        self.status_message = (
            f"Bought {self.selected_side} for ${self.selected_amount} at {entry_price}c. "
            "The 15-second market is now live."
        )

    def _contract_price(self, side: str) -> int:
        gap = self.market.current_price - self.market.target_price
        progress = self.market.elapsed_seconds / MARKET_DURATION_SECONDS
        price_scale = max(7.0, 32.0 * (1 - progress * 0.65))
        score = gap / price_scale
        score = max(-6.0, min(6.0, score))
        up_probability = 1 / (1 + math.exp(-score))
        up_price = round(up_probability * 100)
        up_price = max(4, min(96, up_price))
        if side == "Up":
            return up_price
        return 100 - up_price

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        del dx, dy
        self.hovered_key = None
        for zone in self.click_zones:
            if zone.contains(x, y):
                self.hovered_key = zone.key
                break

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del modifiers
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        clicked_key = None
        for zone in self.click_zones:
            if zone.contains(x, y):
                clicked_key = zone.key
                break

        if clicked_key is None:
            return

        if clicked_key == "new_market":
            self.market = self._new_market()
            return

        if self.position is not None:
            self.status_message = "Trade is locked. Watch the market settle."
            return

        if clicked_key in ("side_up", "side_down") and not self.market.settled:
            self.selected_side = "Up" if clicked_key == "side_up" else "Down"
            self.status_message = f"{self.selected_side} selected. Choose amount, then buy."
        elif clicked_key.startswith("amount_") and not self.market.settled:
            self.selected_amount = int(clicked_key.split("_", 1)[1])
            self.status_message = f"Order amount set to ${self.selected_amount}."
        elif clicked_key == "buy":
            self._buy_position()

    def _draw_header(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)

        arcade.draw_text("PolyArcade", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")

        arcade.draw_lbwh_rectangle_filled(310, WINDOW_HEIGHT - 58, 560, 36, PANEL_ALT)
        arcade.draw_text("Search simulated markets...", 334, WINDOW_HEIGHT - 41, MUTED_DARK, 13, anchor_y="center")

        labels = ["Trending", "Crypto", "Breaking", "Macro", "Economy", "Tech", "More"]
        x = 70
        for label in labels:
            color = BLUE if label == "Crypto" else MUTED
            arcade.draw_text(label, x, WINDOW_HEIGHT - 104, color, 13, bold=label == "Crypto")
            x += 124

        arcade.draw_text("Practice mode - no real trading", WINDOW_WIDTH - 70, WINDOW_HEIGHT - 45, MUTED, 13, anchor_x="right", anchor_y="center")

    def _draw_market(self) -> None:
        left = 70
        bottom = 246
        width = 900
        height = 500

        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 74, 64, 64, ORANGE)
        arcade.draw_text("B", left + 32, bottom + height - 42, WHITE, 34, bold=True, anchor_x="center", anchor_y="center")
        arcade.draw_text("BTC Up or Down 15s", left + 88, bottom + height - 31, TEXT, 25, bold=True)
        subtitle = "Read the article, pick a side, then Buy starts the 15-second market"
        if self.market.active:
            subtitle = "Live simulated Bitcoin market"
        elif self.market.settled:
            subtitle = "Settled market"
        arcade.draw_text(subtitle, left + 88, bottom + height - 61, MUTED, 14, bold=True)

        stats_y = bottom + height - 132
        arcade.draw_text("Price To Beat", left, stats_y, MUTED, 12, bold=True)
        arcade.draw_text(self._format_money(self.market.target_price), left, stats_y - 42, TEXT, 27, bold=True)
        arcade.draw_line(left + 240, stats_y - 48, left + 240, stats_y + 14, BORDER, 1)

        current_color = GREEN if self.market.current_price >= self.market.target_price else RED
        arcade.draw_text("Current Price", left + 282, stats_y, ORANGE, 12, bold=True)
        arcade.draw_text(self._format_money(self.market.current_price), left + 282, stats_y - 42, current_color, 27, bold=True)
        arcade.draw_text(
            self._format_delta(self.market.current_price - self.market.target_price),
            left + 505,
            stats_y - 25,
            current_color,
            14,
            bold=True,
        )

        remaining = max(0, MARKET_DURATION_SECONDS - int(self.market.elapsed_seconds))
        minutes, seconds = divmod(remaining, 60)
        timer_color = MUTED if self.market.settled or not self.market.active else RED
        arcade.draw_text(f"{minutes:02d}", left + width - 112, stats_y - 22, timer_color, 30, bold=True, anchor_x="center")
        arcade.draw_text(f"{seconds:02d}", left + width - 54, stats_y - 22, timer_color, 30, bold=True, anchor_x="center")
        arcade.draw_text("MINS", left + width - 112, stats_y - 48, MUTED, 10, bold=True, anchor_x="center")
        arcade.draw_text("SECS", left + width - 54, stats_y - 48, MUTED, 10, bold=True, anchor_x="center")
        if not self.market.active and not self.market.settled:
            arcade.draw_text("WAITING", left + width - 84, stats_y + 15, YELLOW, 12, bold=True, anchor_x="center")

        self._draw_progress_bar(left, bottom + height - 202, width - 24, 6)
        self._draw_chart(left, bottom + 44, width, 252)

    def _draw_progress_bar(self, left: float, bottom: float, width: float, height: float) -> None:
        progress = self.market.elapsed_seconds / MARKET_DURATION_SECONDS
        progress = max(0.0, min(1.0, progress))
        fill_width = width * progress
        fill_color = BLUE if self.market.active else YELLOW if not self.market.settled else MUTED_DARK

        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (27, 35, 44))
        if fill_width > 0:
            arcade.draw_lbwh_rectangle_filled(left, bottom, fill_width, height, fill_color)

    def _draw_chart(self, left: float, bottom: float, width: float, height: float) -> None:
        arcade.draw_lbwh_rectangle_filled(left, bottom, width - 24, height, (12, 16, 20))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width - 24, height, (24, 31, 39), 1)

        for row in range(5):
            y = bottom + row * height / 4
            grid_color = (41, 51, 63) if row in (0, 4) else (27, 35, 44)
            arcade.draw_line(left, y, left + width - 24, y, grid_color, 1)

        prices = self.market.history
        chart_min = min(prices + [self.market.target_price])
        chart_max = max(prices + [self.market.target_price])
        padding = max(8, (chart_max - chart_min) * 0.18)
        low = chart_min - padding
        high = chart_max + padding
        span = max(1, high - low)

        target_y = bottom + ((self.market.target_price - low) / span) * height
        arcade.draw_line(left, target_y, left + width - 24, target_y, (143, 97, 45), 2)
        arcade.draw_text("Target", left + width - 76, target_y + 8, YELLOW, 11, bold=True)

        points: list[tuple[float, float]] = []
        step = (width - 46) / max(1, len(prices) - 1)
        for index, price in enumerate(prices):
            x = left + index * step
            y = bottom + ((price - low) / span) * height
            points.append((x, y))

        if len(points) > 1:
            area_points = [(points[0][0], bottom), *points, (points[-1][0], bottom)]
            arcade.draw_polygon_filled(area_points, (247, 151, 38, 28))
            arcade.draw_line_strip(points, (247, 151, 38, 80), 7)
            arcade.draw_line_strip(points, ORANGE, 3)
            arcade.draw_circle_filled(points[-1][0], points[-1][1], 5, ORANGE)
            arcade.draw_circle_outline(points[-1][0], points[-1][1], 10, (247, 151, 38, 90), 2)

        for index, value in enumerate((low, (low + high) / 2, high)):
            y = bottom + index * height / 2
            arcade.draw_text(self._format_money(value), left + width - 12, y - 8, MUTED_DARK, 11, anchor_x="right")

        arcade.draw_text("Market start", left, bottom - 28, MUTED_DARK, 11)
        right_label = "Live now" if self.market.active else "Paused"
        if self.market.settled:
            right_label = "Settled"
        arcade.draw_text(right_label, left + width - 78, bottom - 28, MUTED_DARK, 11)

    def _draw_ticket(self) -> None:
        left = 1018
        bottom = 96
        width = 352
        height = 650

        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, BORDER, 1)
        arcade.draw_line(left, bottom + height - 54, left + width, bottom + height - 54, BORDER, 1)
        arcade.draw_text("Buy", left + 26, bottom + height - 33, TEXT, 18, bold=True, anchor_y="center")
        arcade.draw_text("One-tap prediction", left + width - 26, bottom + height - 33, MUTED, 12, anchor_x="right", anchor_y="center")

        up_price = self._contract_price("Up")
        down_price = self._contract_price("Down")
        self._draw_side_button("side_up", "Up", up_price, left + 26, bottom + height - 140, 142, 58)
        self._draw_side_button("side_down", "Down", down_price, left + 184, bottom + height - 140, 142, 58)

        arcade.draw_text("Order Amount", left + 26, bottom + height - 190, MUTED, 12, bold=True)
        for index, amount in enumerate((5, 25, 100)):
            x = left + 26 + index * 110
            self._draw_amount_button(amount, x, bottom + height - 282)

        arcade.draw_line(left + 26, bottom + height - 320, left + width - 26, bottom + height - 320, BORDER, 1)
        self._draw_position_summary(left + 26, bottom + height - 338, width - 52)

        buy_key = "new_market" if self.market.settled else "buy"
        buy_zone = ClickZone(buy_key, left + 26, bottom + 26, width - 52, 56)
        self.click_zones.append(buy_zone)
        buy_disabled = self.position is not None and not self.market.settled
        buy_color = PANEL_SOFT if buy_disabled else GREEN_DARK
        if self.hovered_key == buy_key and not buy_disabled:
            buy_color = BLUE if self.market.settled else GREEN
        arcade.draw_lbwh_rectangle_filled(buy_zone.left, buy_zone.bottom, buy_zone.width, buy_zone.height, buy_color)
        button_text = "New Market" if self.market.settled else "Buy & Start"
        arcade.draw_text(button_text, buy_zone.center_x, buy_zone.center_y + 2, TEXT if not buy_disabled else MUTED, 18, bold=True, anchor_x="center", anchor_y="center")

    def _draw_side_button(self, key: str, label: str, price: int, left: float, bottom: float, width: float, height: float) -> None:
        selected = self.selected_side == label
        disabled = self.position is not None or self.market.settled
        zone = ClickZone(key, left, bottom, width, height)
        self.click_zones.append(zone)

        if selected and label == "Up":
            color = GREEN
        elif selected:
            color = RED_DARK
        elif self.hovered_key == key and not disabled:
            color = PANEL_SOFT
        else:
            color = PANEL_ALT

        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, color)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, GREEN if label == "Up" and selected else BORDER, 1)
        text_color = MUTED if disabled and not selected else TEXT
        arcade.draw_text(f"{label} {price}c", left + width / 2, bottom + height / 2 + 2, text_color, 15, bold=True, anchor_x="center", anchor_y="center")

    def _draw_amount_button(self, amount: int, left: float, bottom: float) -> None:
        key = f"amount_{amount}"
        zone = ClickZone(key, left, bottom, 86, 66)
        self.click_zones.append(zone)
        selected = self.selected_amount == amount
        disabled = self.position is not None or self.market.settled

        color = PANEL_SOFT if selected else PANEL_ALT
        if self.hovered_key == key and not disabled:
            color = (41, 52, 65)
        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BLUE if selected else BORDER, 1)
        arcade.draw_text(f"${amount}", zone.center_x, zone.center_y + 9, TEXT if not disabled or selected else MUTED, 20, bold=True, anchor_x="center", anchor_y="center")
        arcade.draw_text("stake", zone.center_x, zone.center_y - 17, MUTED, 10, anchor_x="center", anchor_y="center")

    def _draw_position_summary(self, left: float, top: float, width: float) -> None:
        arcade.draw_text("Balance", left, top, MUTED, 12, bold=True)
        arcade.draw_text(f"${self.balance:,.2f}", left, top - 28, TEXT, 22, bold=True)
        arcade.draw_text(self.status_message, left, top - 74, MUTED, 11, width=int(width), multiline=True)

        if self.position is None:
            price = self._contract_price(self.selected_side)
            shares = self.selected_amount / (price / 100)
            arcade.draw_text("Preview", left, top - 120, MUTED, 12, bold=True)
            arcade.draw_text(f"{self.selected_side}: {price}c per share", left, top - 146, TEXT, 15, bold=True)
            arcade.draw_text(f"Buy starts timer | Max payout ${shares:,.2f}", left, top - 168, MUTED, 11)
            return

        result = self.position.resolved_result or "Open"
        live_price = self._contract_price(self.position.side)
        current_value = self.position.shares * (live_price / 100)
        arcade.draw_text("Current Position", left, top - 120, MUTED, 12, bold=True)
        arcade.draw_text(f"{self.position.side}: ${self.position.amount} at {self.position.entry_price_cents}c", left, top - 146, TEXT, 15, bold=True)
        arcade.draw_text(f"Live share price: {live_price}c | Value ${current_value:,.2f}", left, top - 168, MUTED, 11)
        result_color = GREEN if result == "Won" else RED if result == "Lost" else YELLOW
        arcade.draw_text(f"Status: {result}", left, top - 190, result_color, 11, bold=True)

    def _draw_news_cards(self) -> None:
        left = 70
        bottom = 46
        card_width = 900
        card_height = 152

        arcade.draw_text("Bitcoin article", left, bottom + card_height + 22, TEXT, 17, bold=True)
        arcade.draw_text("Read before choosing. No automatic conclusion is shown.", left + 170, bottom + card_height + 23, MUTED, 12)
        self._draw_news_card(self.news_card, left, bottom, card_width, card_height)

    def _draw_news_card(self, card: NewsCard, left: float, bottom: float, width: float, height: float) -> None:
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 8, width, 8, BLUE)

        arcade.draw_text(card.source, left + 20, bottom + height - 32, MUTED, 10, bold=True)
        arcade.draw_text(
            f"Reliability {card.reliability:.2f}",
            left + width - 20,
            bottom + height - 32,
            MUTED,
            10,
            bold=True,
            anchor_x="right",
        )
        arcade.draw_text(card.analysis_label, left + 20, bottom + height - 64, BLUE, 12, bold=True)
        arcade.draw_text(card.headline, left + 20, bottom + 34, TEXT, 21, bold=True, width=int(width - 40), multiline=True)

    def _draw_transition_overlay(self) -> None:
        if self.market_transition >= 1:
            return

        eased = 1 - (1 - self.market_transition) ** 3
        alpha = int((1 - eased) * 135)
        text_alpha = int((1 - eased) * 210)
        arcade.draw_lbwh_rectangle_filled(
            0,
            0,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            (14, 18, 23, alpha),
        )
        arcade.draw_text(
            "New 15s market",
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2 + 12,
            (239, 243, 248, text_alpha),
            24,
            bold=True,
            anchor_x="center",
        )
        arcade.draw_text(
            "Read the article, choose a side, then start the round",
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2 - 18,
            (141, 151, 166, text_alpha),
            13,
            anchor_x="center",
        )

    def _format_money(self, value: float) -> str:
        return f"${value:,.2f}"

    def _format_delta(self, value: float) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"


def main() -> None:
    BitcoinPredictionGame()
    arcade.run()


if __name__ == "__main__":
    main()
