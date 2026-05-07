"""Simulated Bitcoin Up/Down prediction market built with Python Arcade."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import arcade

from polymarket_tutorial import SIMPLE_TUTORIAL_ARTICLES, TUTORIAL_CLICK_TARGETS


WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 880
WINDOW_TITLE = "Bitcoin Up or Down Arcade"

MARKET_DURATION_SECONDS = 15
STARTING_BALANCE = 1000
DEFAULT_ORDER_AMOUNT = 25
PRICE_TICK_SECONDS = 1 / 30
PRICE_HISTORY_LIMIT = 180
MARKET_TRANSITION_SPEED = 3.4
MAX_FULL_NAME_CHARS = 32

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
            antialiasing=True,
            samples=4,
            vsync=True,
        )
        arcade.set_background_color(BACKGROUND)

        self.onboarding_active = True
        self.tutorial_active = False
        self.onboarding_name = ""
        self.onboarding_name_active = True
        self.onboarding_message = "Type your full name to create a practice identity."
        self.player_full_name = ""
        self.balance = STARTING_BALANCE
        self.selected_side = "Up"
        self.selected_amount = DEFAULT_ORDER_AMOUNT
        self.position: Position | None = None
        self.trade_history: list[TradeRecord] = []
        self.dashboard_active = False
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
        call_name = self._player_call_name()
        self.status_message = f"{call_name}, read the article. The market starts only after you buy a position."

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
        if self.onboarding_active:
            self._draw_onboarding()
            return
        if self.tutorial_active:
            self._draw_tutorial_page()
            return
        if self.dashboard_active:
            self._draw_dashboard()
            return

        self._draw_header()
        self._draw_market()
        self._draw_ticket()
        self._draw_news_cards()
        self._draw_transition_overlay()

    def on_update(self, delta_time: float) -> None:
        if self.onboarding_active or self.tutorial_active or self.dashboard_active:
            return

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
        call_name = self._player_call_name()
        if self.position is None:
            self.status_message = f"{call_name}, market settled {winning_side}. No position was opened."
            return

        if self.position.side == winning_side:
            payout = round(self.position.shares, 2)
            self.balance += payout
            self.position.resolved_result = "Won"
            self._record_trade(winning_side, round(payout - self.position.amount, 2))
            self.status_message = (
                f"{call_name}, {winning_side} wins. Your ${self.position.amount} position paid ${payout:,.2f}."
            )
        else:
            self.position.resolved_result = "Lost"
            self._record_trade(winning_side, -float(self.position.amount))
            self.status_message = (
                f"{call_name}, {winning_side} wins. Your {self.position.side} position expired at $0."
            )

    def _record_trade(self, winning_side: str, profit_loss: float) -> None:
        if self.position is None:
            return

        self.trade_history.insert(
            0,
            TradeRecord(
                market="BTC Up or Down 15s",
                side=self.position.side,
                amount=self.position.amount,
                entry_price_cents=self.position.entry_price_cents,
                result="Won" if self.position.side == winning_side else "Lost",
                profit_loss=profit_loss,
                balance_after=self.balance,
            ),
        )

    def _buy_position(self) -> None:
        call_name = self._player_call_name()
        if self.position is not None:
            self.status_message = f"{call_name}, you already bought this market. Wait for settlement."
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market."
            return
        if self.selected_amount > self.balance:
            self.status_message = f"{call_name}, not enough balance for that order amount."
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
            f"Nice, {call_name}. Bought {self.selected_side} for ${self.selected_amount} at {entry_price}c. "
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

        if self.onboarding_active:
            self._handle_onboarding_click(clicked_key)
            return
        if self.tutorial_active:
            if clicked_key == "tutorial_continue":
                self.tutorial_active = False
                self.market_transition = 0.0
                self.status_message = (
                    f"Welcome, {self._player_call_name()}. Read the article, choose Up or Down, "
                    "then buy to start the tutorial market."
                )
            return

        if clicked_key == "dashboard_toggle":
            self.dashboard_active = not self.dashboard_active
            return

        if clicked_key == "new_market":
            self.market = self._new_market()
            return

        if self.position is not None:
            self.status_message = f"{self._player_call_name()}, trade is locked. Watch the market settle."
            return

        if clicked_key in ("side_up", "side_down") and not self.market.settled:
            self.selected_side = "Up" if clicked_key == "side_up" else "Down"
            self.status_message = f"{self.selected_side} selected, {self._player_call_name()}. Choose amount, then buy."
        elif clicked_key.startswith("amount_") and not self.market.settled:
            self.selected_amount = int(clicked_key.split("_", 1)[1])
            self.status_message = f"Order amount set to ${self.selected_amount}."
        elif clicked_key == "buy":
            self._buy_position()

    def on_text(self, text: str) -> None:
        if not self.onboarding_active or not self.onboarding_name_active:
            return

        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -'."
        for character in text:
            if character in allowed and len(self.onboarding_name) < MAX_FULL_NAME_CHARS:
                self.onboarding_name += character
        self.onboarding_message = "Click Start Practice Tutorial when your name is ready."

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers
        if not self.onboarding_active:
            return

        if symbol == arcade.key.BACKSPACE:
            self.onboarding_name = self.onboarding_name[:-1]
            self.onboarding_message = "Type your full name to create a practice identity."
        elif symbol in (arcade.key.ENTER, arcade.key.RETURN):
            self.onboarding_message = "Use the Start Practice Tutorial button to continue."
        elif symbol == arcade.key.TAB:
            self.onboarding_name_active = True

    def _handle_onboarding_click(self, clicked_key: str) -> None:
        if clicked_key == "onboard_name":
            self.onboarding_name_active = True
            self.onboarding_message = "Type your full name, like Benjamin Silverman."
        elif clicked_key == "onboard_start":
            self._finish_onboarding()

    def _finish_onboarding(self) -> None:
        full_name = " ".join(self.onboarding_name.strip().split())
        if not full_name:
            self.onboarding_name_active = True
            self.onboarding_message = "Enter your full name first, like Benjamin Silverman."
            return

        self.player_full_name = full_name
        self.onboarding_name = full_name
        self.onboarding_name_active = False
        self.onboarding_active = False
        self.tutorial_active = True
        self.status_message = "Tutorial opened."

    def _player_call_name(self) -> str:
        if not self.player_full_name:
            return "Trader"
        return self.player_full_name.split()[0]

    def _draw_onboarding(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)
        arcade.draw_text("Polymarket Practice", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")
        arcade.draw_text(
            "Tutorial onboarding - fake account only",
            WINDOW_WIDTH - 70,
            WINDOW_HEIGHT - 45,
            MUTED,
            13,
            anchor_x="right",
            anchor_y="center",
        )

        panel_left = 220
        panel_bottom = 142
        panel_width = 1000
        panel_height = 590
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom, panel_width, panel_height, PANEL)
        arcade.draw_lbwh_rectangle_outline(panel_left, panel_bottom, panel_width, panel_height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom + panel_height - 8, panel_width, 8, BLUE)

        arcade.draw_text("Welcome to the market tutorial", panel_left + 48, panel_bottom + 502, TEXT, 34, bold=True)
        arcade.draw_text(
            "Set up a practice identity before the first Bitcoin market opens.",
            panel_left + 50,
            panel_bottom + 466,
            MUTED,
            15,
        )

        steps = [
            ("1", "Enter your full name", "Use your real full name for the practice identity."),
            ("2", "Click Start Practice Tutorial", "The button is the only way to move to the next tutorial page."),
            ("3", "Follow the arrows", "The next page points to the buttons that operate the game."),
        ]
        for index, (number, title, detail) in enumerate(steps):
            y = panel_bottom + 370 - index * 92
            arcade.draw_circle_filled(panel_left + 70, y + 8, 22, PANEL_SOFT)
            arcade.draw_circle_outline(panel_left + 70, y + 8, 22, BLUE, 2)
            arcade.draw_text(number, panel_left + 70, y + 1, TEXT, 15, bold=True, anchor_x="center", anchor_y="center")
            arcade.draw_text(title, panel_left + 110, y + 18, TEXT, 18, bold=True)
            arcade.draw_text(detail, panel_left + 110, y - 10, MUTED, 13, width=390, multiline=True)

        form_left = panel_left + 570
        form_top = panel_bottom + 372
        arcade.draw_text("Create Practice Identity", form_left, form_top + 74, TEXT, 21, bold=True)
        arcade.draw_text("Full Name", form_left, form_top + 38, MUTED, 12, bold=True)

        name_zone = ClickZone("onboard_name", form_left, form_top - 32, 352, 58)
        self.click_zones.append(name_zone)
        name_border = BLUE if self.onboarding_name_active else BORDER
        arcade.draw_lbwh_rectangle_filled(name_zone.left, name_zone.bottom, name_zone.width, name_zone.height, PANEL_SOFT)
        arcade.draw_lbwh_rectangle_outline(name_zone.left, name_zone.bottom, name_zone.width, name_zone.height, name_border, 2)
        if self.onboarding_name:
            name_display = self.onboarding_name
            name_color = TEXT
        else:
            name_display = "Example: Benjamin Silverman"
            name_color = MUTED_DARK
        if self.onboarding_name_active and self.onboarding_name:
            name_display = f"{name_display}|"
        arcade.draw_text(name_display, name_zone.left + 18, name_zone.center_y - 8, name_color, 16, bold=True)

        arcade.draw_text(
            "No password is needed. This tutorial only stores your name in memory for this run.",
            form_left,
            form_top - 78,
            MUTED,
            12,
            width=350,
            multiline=True,
        )

        start_zone = ClickZone("onboard_start", form_left, panel_bottom + 156, 352, 58)
        self.click_zones.append(start_zone)
        can_start = bool(self.onboarding_name.strip())
        start_color = GREEN_DARK if can_start else PANEL_SOFT
        if self.hovered_key == "onboard_start" and can_start:
            start_color = GREEN
        arcade.draw_lbwh_rectangle_filled(start_zone.left, start_zone.bottom, start_zone.width, start_zone.height, start_color)
        arcade.draw_lbwh_rectangle_outline(start_zone.left, start_zone.bottom, start_zone.width, start_zone.height, BORDER, 1)
        arcade.draw_text(
            "Start Practice Tutorial",
            start_zone.center_x,
            start_zone.center_y + 1,
            TEXT if can_start else MUTED,
            17,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )
        arcade.draw_text(self.onboarding_message, form_left, panel_bottom + 122, MUTED, 12, width=350, multiline=True)

    def _draw_tutorial_page(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)
        arcade.draw_text("Polymarket Practice", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text(
            f"Welcome, {self._player_call_name()}",
            WINDOW_WIDTH - 70,
            WINDOW_HEIGHT - 45,
            MUTED,
            13,
            anchor_x="right",
            anchor_y="center",
        )

        panel_left = 70
        panel_bottom = 70
        panel_width = WINDOW_WIDTH - 140
        panel_height = WINDOW_HEIGHT - 190
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom, panel_width, panel_height, PANEL)
        arcade.draw_lbwh_rectangle_outline(panel_left, panel_bottom, panel_width, panel_height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom + panel_height - 8, panel_width, 8, BLUE)

        arcade.draw_text("Tutorial: read, choose, buy", panel_left + 42, panel_bottom + panel_height - 70, TEXT, 31, bold=True)
        arcade.draw_text(
            "Simple articles are practice clues. The arrows show which buttons make the game run.",
            panel_left + 44,
            panel_bottom + panel_height - 106,
            MUTED,
            15,
        )

        article_left = panel_left + 42
        article_top = panel_bottom + panel_height - 152
        for index, article in enumerate(SIMPLE_TUTORIAL_ARTICLES):
            top = article_top - index * 126
            arcade.draw_lbwh_rectangle_filled(article_left, top - 96, 560, 104, PANEL_ALT)
            arcade.draw_lbwh_rectangle_outline(article_left, top - 96, 560, 104, BORDER, 1)
            arcade.draw_lbwh_rectangle_filled(article_left, top - 96, 6, 104, BLUE if index != 1 else RED)
            arcade.draw_text(article.source, article_left + 20, top - 18, MUTED, 10, bold=True)
            arcade.draw_text(article.headline, article_left + 20, top - 45, TEXT, 17, bold=True, width=510, multiline=True)
            arcade.draw_text(article.summary, article_left + 20, top - 76, MUTED, 12, width=510, multiline=True)

        guide_left = panel_left + 680
        guide_bottom = panel_bottom + 132
        arcade.draw_lbwh_rectangle_filled(guide_left, guide_bottom, 540, 410, (18, 23, 30))
        arcade.draw_lbwh_rectangle_outline(guide_left, guide_bottom, 540, 410, BORDER, 1)
        arcade.draw_text("Game buttons to click", guide_left + 32, guide_bottom + 360, TEXT, 22, bold=True)

        up_button = ClickZone("tutorial_up_preview", guide_left + 274, guide_bottom + 286, 102, 46)
        down_button = ClickZone("tutorial_down_preview", guide_left + 388, guide_bottom + 286, 112, 46)
        amount_button = ClickZone("tutorial_amount_preview", guide_left + 326, guide_bottom + 190, 118, 50)
        buy_button = ClickZone("tutorial_buy_preview", guide_left + 274, guide_bottom + 76, 226, 56)
        for zone, label, color in (
            (up_button, "Up", GREEN),
            (down_button, "Down", RED_DARK),
            (amount_button, "$25", PANEL_SOFT),
            (buy_button, "Buy & Start", GREEN_DARK),
        ):
            arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, color)
            arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BORDER, 1)
            arcade.draw_text(label, zone.center_x, zone.center_y + 1, TEXT, 15, bold=True, anchor_x="center", anchor_y="center")

        targets = [
            (TUTORIAL_CLICK_TARGETS[0], up_button.center_x, up_button.center_y),
            (TUTORIAL_CLICK_TARGETS[1], amount_button.center_x, amount_button.center_y),
            (TUTORIAL_CLICK_TARGETS[2], buy_button.center_x, buy_button.center_y),
        ]
        for index, (target, button_x, button_y) in enumerate(targets):
            text_x = guide_left + 32
            text_y = guide_bottom + 302 - index * 100
            arcade.draw_text(target.button_label, text_x, text_y + 30, BLUE, 12, bold=True)
            arcade.draw_text(target.title, text_x, text_y + 7, TEXT, 16, bold=True)
            arcade.draw_text(target.detail, text_x, text_y - 18, MUTED, 12, width=200, multiline=True)
            self._draw_arrow(text_x + 210, text_y + 8, button_x - 12, button_y, BLUE)

        continue_zone = ClickZone("tutorial_continue", panel_left + panel_width - 332, panel_bottom + 28, 290, 54)
        self.click_zones.append(continue_zone)
        button_color = GREEN if self.hovered_key == "tutorial_continue" else GREEN_DARK
        arcade.draw_lbwh_rectangle_filled(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, BORDER, 1)
        arcade.draw_text("Open Practice Market", continue_zone.center_x, continue_zone.center_y + 1, TEXT, 17, bold=True, anchor_x="center", anchor_y="center")

    def _draw_arrow(self, start_x: float, start_y: float, end_x: float, end_y: float, color: tuple[int, int, int]) -> None:
        arcade.draw_line(start_x, start_y, end_x, end_y, color, 3)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        size = 11
        left_angle = angle + math.pi * 0.78
        right_angle = angle - math.pi * 0.78
        left = (end_x + math.cos(left_angle) * size, end_y + math.sin(left_angle) * size)
        right = (end_x + math.cos(right_angle) * size, end_y + math.sin(right_angle) * size)
        arcade.draw_triangle_filled(end_x, end_y, left[0], left[1], right[0], right[1], color)

    def _draw_header(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)

        arcade.draw_text("PolyArcade", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")

        arcade.draw_lbwh_rectangle_filled(310, WINDOW_HEIGHT - 58, 560, 36, PANEL_ALT)
        arcade.draw_text("Search simulated markets...", 334, WINDOW_HEIGHT - 41, MUTED_DARK, 13, anchor_y="center")

        self._draw_dashboard_button("Dashboard")

    def _draw_dashboard_button(self, label: str) -> None:
        zone = ClickZone("dashboard_toggle", WINDOW_WIDTH - 216, WINDOW_HEIGHT - 62, 146, 38)
        self.click_zones.append(zone)
        button_color = BLUE if self.hovered_key == "dashboard_toggle" else PANEL_SOFT
        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BORDER, 1)
        arcade.draw_text(label, zone.center_x, zone.center_y + 1, TEXT, 14, bold=True, anchor_x="center", anchor_y="center")

    def _draw_dashboard(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)
        arcade.draw_text("PolyArcade", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")
        self._draw_dashboard_button("Back")

        left = 96
        top = WINDOW_HEIGHT - 128
        arcade.draw_text("Dashboard", left, top, TEXT, 34, bold=True)
        arcade.draw_text(
            f"{self._player_call_name()}'s practice performance",
            left,
            top - 34,
            MUTED,
            14,
        )

        total_profit = sum(trade.profit_loss for trade in self.trade_history)
        stat_cards = [
            ("Current Balance", self._format_money(self.balance), TEXT),
            ("Total P/L", self._format_delta(total_profit), GREEN if total_profit >= 0 else RED),
            ("Past Trades", str(len(self.trade_history)), TEXT),
        ]
        for index, (label, value, value_color) in enumerate(stat_cards):
            card_left = left + index * 286
            arcade.draw_lbwh_rectangle_filled(card_left, top - 142, 248, 86, PANEL)
            arcade.draw_lbwh_rectangle_outline(card_left, top - 142, 248, 86, BORDER, 1)
            arcade.draw_text(label, card_left + 18, top - 88, MUTED, 12, bold=True)
            arcade.draw_text(value, card_left + 18, top - 122, value_color, 24, bold=True)

        table_left = left
        table_bottom = 92
        table_width = WINDOW_WIDTH - left * 2
        table_height = 450
        arcade.draw_lbwh_rectangle_filled(table_left, table_bottom, table_width, table_height, PANEL)
        arcade.draw_lbwh_rectangle_outline(table_left, table_bottom, table_width, table_height, BORDER, 1)
        arcade.draw_text("Past Trades", table_left + 24, table_bottom + table_height - 42, TEXT, 20, bold=True)

        headers = [("Market", 24), ("Side", 360), ("Stake", 500), ("Entry", 630), ("Result", 760), ("P/L", 900), ("Balance", 1040)]
        header_y = table_bottom + table_height - 82
        arcade.draw_line(table_left, header_y - 12, table_left + table_width, header_y - 12, BORDER, 1)
        for label, offset in headers:
            arcade.draw_text(label, table_left + offset, header_y, MUTED, 11, bold=True)

        if not self.trade_history:
            arcade.draw_text(
                "No settled trades yet. Play a market, wait for it to settle, then come back here.",
                table_left + 24,
                table_bottom + table_height / 2,
                MUTED,
                14,
                width=int(table_width - 48),
                multiline=True,
            )
            return

        for index, trade in enumerate(self.trade_history[:8]):
            row_y = header_y - 52 - index * 42
            row_color = PANEL_ALT if index % 2 == 0 else PANEL
            arcade.draw_lbwh_rectangle_filled(table_left + 1, row_y - 12, table_width - 2, 36, row_color)
            pnl_color = GREEN if trade.profit_loss >= 0 else RED
            arcade.draw_text(trade.market, table_left + 24, row_y, TEXT, 13, bold=True)
            arcade.draw_text(trade.side, table_left + 360, row_y, TEXT, 13, bold=True)
            arcade.draw_text(f"${trade.amount}", table_left + 500, row_y, TEXT, 13)
            arcade.draw_text(f"{trade.entry_price_cents}c", table_left + 630, row_y, TEXT, 13)
            arcade.draw_text(trade.result, table_left + 760, row_y, pnl_color, 13, bold=True)
            arcade.draw_text(self._format_delta(trade.profit_loss), table_left + 900, row_y, pnl_color, 13, bold=True)
            arcade.draw_text(self._format_money(trade.balance_after), table_left + 1040, row_y, TEXT, 13)

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
        arcade.draw_text(f"{self._player_call_name()}'s Balance", left, top, MUTED, 12, bold=True)
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
