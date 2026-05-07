from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path
import random
from dataclasses import dataclass

import arcade

from polymarket_tutorial import SIMPLE_TUTORIAL_ARTICLES, TUTORIAL_CLICK_TARGETS

WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 780
WINDOW_TITLE = "Arcade Prediction Market"
BUY_SOUND_PATH = Path(__file__).resolve().parent / "asset-game" / "sounds" / "buy_cash_register.ogg"
STARTING_CASH = 1000
MAX_FULL_NAME_CHARS = 32


def hex_color(value: str) -> arcade.types.Color:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected 6-digit hex color, got {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


@dataclass
class Rect:
    left: float
    right: float
    bottom: float
    top: float

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.bottom <= y <= self.top

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.bottom + self.top) / 2


@dataclass(frozen=True)
class TradeRecord:
    action: str
    side: str
    amount: int
    price_cents: int
    profit_loss: float
    balance_after: float


class PredictionMarketWindow(arcade.Window):
    def __init__(self) -> None:
        super().__init__(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            WINDOW_TITLE,
            resizable=True,
            update_rate=1 / 60,
            draw_rate=1 / 60,
            antialiasing=True,
            samples=4,
            vsync=True,
        )
        self.set_minimum_size(1100, 680)

        self.colors = {
            "bg": hex_color("#101418"),
            "panel": hex_color("#151B22"),
            "panel_alt": hex_color("#1B232D"),
            "panel_soft": hex_color("#202A35"),
            "panel_border": hex_color("#283240"),
            "text": hex_color("#F2F4F8"),
            "muted": hex_color("#93A0B3"),
            "muted_soft": hex_color("#6E7B90"),
            "line": hex_color("#DFE3E8"),
            "grid": hex_color("#2A333F"),
            "accent_blue": hex_color("#1E90FF"),
            "accent_green": hex_color("#3CA361"),
            "accent_red": hex_color("#F04E4E"),
            "chip": hex_color("#242E3A"),
            "chip_active": hex_color("#35485E"),
            "search": hex_color("#1A222C"),
        }
        arcade.set_background_color(self.colors["bg"])

        self.font_primary = "Arial"
        self.onboarding_active = True
        self.tutorial_active = False
        self.onboarding_name = ""
        self.onboarding_name_active = True
        self.onboarding_message = "Type your full name to create a practice identity."
        self.onboarding_name_rect = Rect(0, 0, 0, 0)
        self.onboarding_start_rect = Rect(0, 0, 0, 0)
        self.tutorial_continue_rect = Rect(0, 0, 0, 0)
        self.player_full_name = ""
        self.market_title = "WTI Daily Up or Down"
        self.base_price = 105.10
        self.chart_length = 75
        self.market_clock = datetime(2026, 5, 4, 10, 28, 32)
        self.elapsed_market_seconds = 0.0
        self.market_tick_seconds = 0.35
        self.market_tick_accumulator = 0.0
        self.countdown_seconds = 3 * 3600 + 31 * 60

        self.trade_mode = "Buy"
        self.trade_side = "Up"
        self.amount = 0
        self.cash_balance = STARTING_CASH
        self.purchased_total = 0
        self.trade_history: list[TradeRecord] = []
        self.dashboard_active = False
        self.status_message = "Live demo is updating. Select a side and build a mock position."

        self.amount_steps = [1, 5, 10, 100]
        self.trade_mode_buttons: dict[str, Rect] = {}
        self.trade_side_buttons: dict[str, Rect] = {}
        self.amount_buttons: dict[int, Rect] = {}
        self.amount_input_rect = Rect(0, 0, 0, 0)
        self.trade_button_rect = Rect(0, 0, 0, 0)
        self.dashboard_button_rect = Rect(0, 0, 0, 0)
        self.amount_input_text = ""
        self.amount_input_active = False
        self.buy_sound = arcade.load_sound(str(BUY_SOUND_PATH)) if BUY_SOUND_PATH.exists() else None

        self.chart_points = self._generate_chart_points()
        self.price_to_beat = round(self.chart_points[0] - random.uniform(0.35, 1.6), 2)
        self._derive_market_stats()

    def _generate_chart_points(self) -> list[float]:
        current = self.base_price + random.uniform(-0.02, 0.02)
        points = [current]

        for index in range(self.chart_length - 1):
            drift = 0.004 * math.sin(index / 7)
            shock = random.uniform(-0.018, 0.018)
            if index in (6, 29, 57):
                shock += random.uniform(0.02, 0.035)
            if index in (43, 67):
                shock -= random.uniform(0.02, 0.03)
            current += drift + shock
            current = max(self.base_price - 0.14, min(self.base_price + 0.18, current))
            points.append(round(current, 3))

        points[-1] = round(points[-1], 2)
        return points

    def _derive_market_stats(self) -> None:
        self.current_price = round(self.chart_points[-1], 2)
        self.price_delta = round(self.current_price - self.price_to_beat, 2)

        chart_min = min(self.chart_points)
        chart_max = max(self.chart_points)
        padding = 0.03
        self.chart_floor = math.floor((chart_min - padding) * 100) / 100
        self.chart_ceiling = math.ceil((chart_max + padding) * 100) / 100
        self.y_axis_labels = [
            round(self.chart_floor + index * (self.chart_ceiling - self.chart_floor) / 4, 2)
            for index in range(5)
        ]

        delta_strength = max(-2.5, min(2.5, self.price_delta))
        up_price = int(round(50 + delta_strength * 16 + random.uniform(-2, 2)))
        up_price = max(7, min(94, up_price))
        down_price = max(6, min(93, 100 - up_price + random.randint(-2, 2)))
        self.contract_prices = {"Up": up_price, "Down": down_price}

    def _countdown_triplet(self) -> tuple[int, int, int]:
        hours, remainder = divmod(self.countdown_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return hours, minutes, seconds

    def _advance_market(self) -> None:
        previous = self.chart_points[-1]
        drift = (self.base_price - previous) * 0.08
        wave = 0.006 * math.sin(self.elapsed_market_seconds / 4.0)
        shock = random.uniform(-0.012, 0.012)
        next_price = previous + drift + wave + shock
        next_price = max(self.base_price - 0.16, min(self.base_price + 0.2, next_price))

        self.chart_points.append(round(next_price, 3))
        if len(self.chart_points) > self.chart_length:
            self.chart_points.pop(0)

        self.elapsed_market_seconds += self.market_tick_seconds
        self.market_clock += timedelta(seconds=self.market_tick_seconds)
        self.countdown_seconds = max(0, self.countdown_seconds - 1)
        self._derive_market_stats()

    def _chart_timestamps(self) -> list[str]:
        latest = self.market_clock
        offsets = [27, 23, 19, 15, 11, 7, 0]
        return [
            (latest - timedelta(seconds=offset)).strftime("%I:%M:%S %p").lstrip("0")
            for offset in offsets
        ]

    def on_update(self, delta_time: float) -> None:
        if self.onboarding_active or self.tutorial_active or self.dashboard_active:
            return

        self.market_tick_accumulator += delta_time
        while self.market_tick_accumulator >= self.market_tick_seconds:
            self.market_tick_accumulator -= self.market_tick_seconds
            self._advance_market()

    def on_draw(self) -> None:
        self.clear()
        self.trade_mode_buttons.clear()
        self.trade_side_buttons.clear()
        self.amount_buttons.clear()

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
        self._draw_main_layout()

    def _draw_onboarding(self) -> None:
        arcade.draw_rect_filled(
            arcade.XYWH(self.width / 2, self.height / 2, self.width, self.height),
            self.colors["bg"],
        )
        header_height = 84
        arcade.draw_rect_filled(
            arcade.XYWH(self.width / 2, self.height - header_height / 2, self.width, header_height),
            self.colors["panel"],
        )
        arcade.draw_line(0, self.height - header_height, self.width, self.height - header_height, self.colors["panel_border"], 1)
        arcade.draw_text(
            "Polymarket Practice",
            36,
            self.height - 55,
            self.colors["text"],
            22,
            font_name=self.font_primary,
            bold=True,
        )
        arcade.draw_text(
            "Tutorial onboarding - fake account only",
            self.width - 42,
            self.height - 55,
            self.colors["muted"],
            13,
            font_name=self.font_primary,
            anchor_x="right",
        )

        panel_width = min(980, self.width - 120)
        panel_height = min(530, self.height - 170)
        panel = Rect(
            (self.width - panel_width) / 2,
            (self.width + panel_width) / 2,
            (self.height - panel_height) / 2 - 10,
            (self.height + panel_height) / 2 - 10,
        )
        self._draw_rounded_panel(panel, self.colors["panel"], border_color=self.colors["panel_border"])
        arcade.draw_rect_filled(
            arcade.XYWH(panel.center_x, panel.top - 4, panel.width, 8),
            self.colors["accent_blue"],
        )

        arcade.draw_text(
            "Welcome to the market tutorial",
            panel.left + 42,
            panel.top - 76,
            self.colors["text"],
            30,
            font_name=self.font_primary,
            bold=True,
        )
        arcade.draw_text(
            "Create a practice identity before the first simulated market opens.",
            panel.left + 44,
            panel.top - 112,
            self.colors["muted"],
            15,
            font_name=self.font_primary,
        )

        steps = [
            ("Step 1", "Enter your full name", "Use your real full name for the practice identity."),
            ("Step 2", "Click Start Practice Tutorial", "The button is the only way to move to the next tutorial page."),
            ("Step 3", "Follow the arrows", "The next page points to the buttons that operate the game."),
        ]
        for index, (step, title, detail) in enumerate(steps):
            y = panel.top - 188 - index * 82
            arcade.draw_text(step, panel.left + 48, y + 14, self.colors["accent_blue"], 12, font_name=self.font_primary, bold=True)
            arcade.draw_text(title, panel.left + 48, y - 10, self.colors["text"], 17, font_name=self.font_primary, bold=True)
            arcade.draw_text(detail, panel.left + 48, y - 34, self.colors["muted"], 12, font_name=self.font_primary, width=390, multiline=True)

        form_left = panel.left + panel.width - 396
        form_top = panel.top - 194
        arcade.draw_text("Create Practice Identity", form_left, form_top + 66, self.colors["text"], 20, font_name=self.font_primary, bold=True)
        arcade.draw_text("Full Name", form_left, form_top + 30, self.colors["muted"], 12, font_name=self.font_primary, bold=True)

        self.onboarding_name_rect = Rect(form_left, form_left + 332, form_top - 44, form_top + 14)
        name_border = self.colors["accent_blue"] if self.onboarding_name_active else self.colors["panel_border"]
        self._draw_rounded_panel(self.onboarding_name_rect, self.colors["panel_soft"], border_color=name_border)
        if self.onboarding_name:
            name_display = self.onboarding_name
            name_color = self.colors["text"]
        else:
            name_display = "Example: Benjamin Silverman"
            name_color = self.colors["muted_soft"]
        if self.onboarding_name_active and self.onboarding_name:
            name_display = f"{name_display}|"
        arcade.draw_text(name_display, self.onboarding_name_rect.left + 16, self.onboarding_name_rect.center_y - 8, name_color, 15, font_name=self.font_primary, bold=True)

        arcade.draw_text(
            "No password is needed. This tutorial only stores your name in memory for this run.",
            form_left,
            form_top - 84,
            self.colors["muted"],
            12,
            font_name=self.font_primary,
            width=332,
            multiline=True,
        )

        self.onboarding_start_rect = Rect(form_left, form_left + 332, panel.bottom + 96, panel.bottom + 150)
        can_start = bool(self.onboarding_name.strip())
        button_color = self.colors["accent_green"] if can_start else self.colors["panel_soft"]
        self._draw_rounded_panel(self.onboarding_start_rect, button_color, border_color=self.colors["panel_border"])
        arcade.draw_text(
            "Start Practice Tutorial",
            self.onboarding_start_rect.center_x,
            self.onboarding_start_rect.center_y - 7,
            self.colors["text"] if can_start else self.colors["muted"],
            16,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )
        arcade.draw_text(self.onboarding_message, form_left, panel.bottom + 62, self.colors["muted"], 12, font_name=self.font_primary, width=332, multiline=True)

    def _draw_tutorial_page(self) -> None:
        arcade.draw_rect_filled(
            arcade.XYWH(self.width / 2, self.height / 2, self.width, self.height),
            self.colors["bg"],
        )
        header_height = 84
        arcade.draw_rect_filled(
            arcade.XYWH(self.width / 2, self.height - header_height / 2, self.width, header_height),
            self.colors["panel"],
        )
        arcade.draw_line(0, self.height - header_height, self.width, self.height - header_height, self.colors["panel_border"], 1)
        arcade.draw_text("Polymarket Practice", 36, self.height - 55, self.colors["text"], 22, font_name=self.font_primary, bold=True)
        arcade.draw_text(
            f"Welcome, {self._player_call_name()}",
            self.width - 42,
            self.height - 55,
            self.colors["muted"],
            13,
            font_name=self.font_primary,
            anchor_x="right",
        )

        panel_width = min(1160, self.width - 80)
        panel_height = min(580, self.height - 150)
        panel = Rect(
            (self.width - panel_width) / 2,
            (self.width + panel_width) / 2,
            (self.height - panel_height) / 2 - 14,
            (self.height + panel_height) / 2 - 14,
        )
        self._draw_rounded_panel(panel, self.colors["panel"], border_color=self.colors["panel_border"])
        arcade.draw_rect_filled(
            arcade.XYWH(panel.center_x, panel.top - 4, panel.width, 8),
            self.colors["accent_blue"],
        )

        arcade.draw_text("Tutorial: read, choose, buy", panel.left + 36, panel.top - 66, self.colors["text"], 30, font_name=self.font_primary, bold=True)
        arcade.draw_text(
            "Simple articles are practice clues. The arrows show which buttons make the game run.",
            panel.left + 38,
            panel.top - 102,
            self.colors["muted"],
            15,
            font_name=self.font_primary,
        )

        article_left = panel.left + 36
        article_top = panel.top - 150
        for index, article in enumerate(SIMPLE_TUTORIAL_ARTICLES):
            top = article_top - index * 116
            card = Rect(article_left, article_left + 520, top - 88, top + 8)
            self._draw_rounded_panel(card, self.colors["panel_alt"], border_color=self.colors["panel_border"])
            bar_color = self.colors["accent_red"] if index == 1 else self.colors["accent_blue"]
            arcade.draw_rect_filled(arcade.XYWH(card.left + 3, card.center_y, 6, card.height), bar_color)
            arcade.draw_text(article.source, card.left + 20, top - 12, self.colors["muted"], 10, font_name=self.font_primary, bold=True)
            arcade.draw_text(article.headline, card.left + 20, top - 38, self.colors["text"], 16, font_name=self.font_primary, bold=True, width=470, multiline=True)
            arcade.draw_text(article.summary, card.left + 20, top - 68, self.colors["muted"], 12, font_name=self.font_primary, width=470, multiline=True)

        guide = Rect(panel.right - 540, panel.right - 36, panel.bottom + 90, panel.top - 128)
        self._draw_rounded_panel(guide, self.colors["bg"], border_color=self.colors["panel_border"])
        arcade.draw_text("Buttons to click", guide.left + 30, guide.top - 46, self.colors["text"], 22, font_name=self.font_primary, bold=True)

        up_button = Rect(guide.right - 226, guide.right - 132, guide.top - 110, guide.top - 64)
        down_button = Rect(guide.right - 120, guide.right - 26, guide.top - 110, guide.top - 64)
        amount_button = Rect(guide.right - 182, guide.right - 70, guide.top - 214, guide.top - 164)
        buy_button = Rect(guide.right - 226, guide.right - 26, guide.bottom + 44, guide.bottom + 98)
        buttons = [
            (up_button, "Up", self.colors["accent_green"]),
            (down_button, "Down", self.colors["accent_red"]),
            (amount_button, "$25", self.colors["panel_soft"]),
            (buy_button, "Buy", self.colors["accent_green"]),
        ]
        for rect, label, color in buttons:
            self._draw_rounded_panel(rect, color, border_color=self.colors["panel_border"])
            arcade.draw_text(label, rect.center_x, rect.center_y - 7, self.colors["text"], 15, font_name=self.font_primary, anchor_x="center", bold=True)

        targets = [
            (TUTORIAL_CLICK_TARGETS[0], up_button.center_x, up_button.center_y),
            (TUTORIAL_CLICK_TARGETS[1], amount_button.center_x, amount_button.center_y),
            (TUTORIAL_CLICK_TARGETS[2], buy_button.center_x, buy_button.center_y),
        ]
        for index, (target, button_x, button_y) in enumerate(targets):
            text_x = guide.left + 30
            text_y = guide.top - 90 - index * 96
            arcade.draw_text(target.button_label, text_x, text_y + 30, self.colors["accent_blue"], 12, font_name=self.font_primary, bold=True)
            arcade.draw_text(target.title, text_x, text_y + 7, self.colors["text"], 16, font_name=self.font_primary, bold=True)
            arcade.draw_text(target.detail, text_x, text_y - 18, self.colors["muted"], 12, font_name=self.font_primary, width=190, multiline=True)
            self._draw_arrow(text_x + 204, text_y + 8, button_x - 10, button_y, self.colors["accent_blue"])

        self.tutorial_continue_rect = Rect(panel.right - 326, panel.right - 36, panel.bottom + 22, panel.bottom + 76)
        self._draw_rounded_panel(self.tutorial_continue_rect, self.colors["accent_green"], border_color=self.colors["panel_border"])
        arcade.draw_text(
            "Open Practice Market",
            self.tutorial_continue_rect.center_x,
            self.tutorial_continue_rect.center_y - 7,
            self.colors["text"],
            16,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )

    def _draw_arrow(self, start_x: float, start_y: float, end_x: float, end_y: float, color: arcade.Color) -> None:
        arcade.draw_line(start_x, start_y, end_x, end_y, color, 3)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        size = 10
        left_angle = angle + math.pi * 0.78
        right_angle = angle - math.pi * 0.78
        left = (end_x + math.cos(left_angle) * size, end_y + math.sin(left_angle) * size)
        right = (end_x + math.cos(right_angle) * size, end_y + math.sin(right_angle) * size)
        arcade.draw_triangle_filled(end_x, end_y, left[0], left[1], right[0], right[1], color)

    def _draw_header(self) -> None:
        width = self.width
        header_height = 84

        arcade.draw_rect_filled(
            arcade.XYWH(width / 2, self.height - header_height / 2, width, header_height),
            self.colors["panel"],
        )
        arcade.draw_line(
            0,
            self.height - header_height,
            width,
            self.height - header_height,
            self.colors["panel_border"],
            1,
        )

        arcade.draw_text(
            "Consensus Market",
            36,
            self.height - 55,
            self.colors["text"],
            21,
            font_name=self.font_primary,
            bold=True,
        )
        arcade.draw_text(
            "<>",
            16,
            self.height - 56,
            self.colors["text"],
            19,
            font_name=self.font_primary,
            bold=True,
        )

        search_rect = Rect(230, min(width - 330, 840), self.height - 72, self.height - 24)
        self._draw_rounded_panel(search_rect, self.colors["search"])
        arcade.draw_text(
            "Search markets...",
            search_rect.left + 28,
            search_rect.center_y - 9,
            self.colors["muted_soft"],
            16,
            font_name=self.font_primary,
        )

        self._draw_dashboard_button("Dashboard")

    def _draw_dashboard_button(self, label: str) -> None:
        self.dashboard_button_rect = Rect(self.width - 178, self.width - 40, self.height - 72, self.height - 26)
        button_color = self.colors["accent_blue"]
        self._draw_rounded_panel(self.dashboard_button_rect, button_color, border_color=self.colors["panel_border"])
        arcade.draw_text(
            label,
            self.dashboard_button_rect.center_x,
            self.dashboard_button_rect.center_y - 8,
            self.colors["text"],
            15,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )

    def _draw_dashboard(self) -> None:
        width = self.width
        header_height = 84
        arcade.draw_rect_filled(arcade.XYWH(width / 2, self.height / 2, width, self.height), self.colors["bg"])
        arcade.draw_rect_filled(
            arcade.XYWH(width / 2, self.height - header_height / 2, width, header_height),
            self.colors["panel"],
        )
        arcade.draw_line(0, self.height - header_height, width, self.height - header_height, self.colors["panel_border"], 1)
        arcade.draw_text("Consensus Market", 36, self.height - 55, self.colors["text"], 21, font_name=self.font_primary, bold=True)
        arcade.draw_text("<>", 16, self.height - 56, self.colors["text"], 19, font_name=self.font_primary, bold=True)
        self._draw_dashboard_button("Back")

        left = 54
        top = self.height - 126
        arcade.draw_text("Dashboard", left, top, self.colors["text"], 32, font_name=self.font_primary, bold=True)
        arcade.draw_text(
            f"{self._player_call_name()}'s mock trading history",
            left,
            top - 32,
            self.colors["muted"],
            14,
            font_name=self.font_primary,
        )

        total_profit = sum(trade.profit_loss for trade in self.trade_history)
        cards = [
            ("Current Balance", self._format_whole_dollars(self.cash_balance), self.colors["text"]),
            ("Total P/L", self._format_signed_dollars(total_profit), self.colors["accent_green"] if total_profit >= 0 else self.colors["accent_red"]),
            ("Purchased", self._format_whole_dollars(self.purchased_total), self.colors["text"]),
            ("Trades", str(len(self.trade_history)), self.colors["text"]),
        ]
        card_width = (self.width - left * 2 - 42) / 4
        for index, (label, value, value_color) in enumerate(cards):
            card = Rect(left + index * (card_width + 14), left + index * (card_width + 14) + card_width, top - 136, top - 54)
            self._draw_rounded_panel(card, self.colors["panel"], border_color=self.colors["panel_border"])
            arcade.draw_text(label, card.left + 16, card.top - 28, self.colors["muted"], 12, font_name=self.font_primary, bold=True)
            arcade.draw_text(value, card.left + 16, card.bottom + 18, value_color, 23, font_name=self.font_primary, bold=True)

        table = Rect(left, self.width - left, 62, top - 174)
        self._draw_rounded_panel(table, self.colors["panel"], border_color=self.colors["panel_border"])
        arcade.draw_text("Past Trades", table.left + 22, table.top - 40, self.colors["text"], 20, font_name=self.font_primary, bold=True)

        columns = [("Action", 22), ("Side", 164), ("Amount", 288), ("Price", 424), ("P/L", 552), ("Balance", 708)]
        header_y = table.top - 82
        arcade.draw_line(table.left, header_y - 14, table.right, header_y - 14, self.colors["panel_border"], 1)
        for label, offset in columns:
            arcade.draw_text(label, table.left + offset, header_y, self.colors["muted"], 11, font_name=self.font_primary, bold=True)

        if not self.trade_history:
            arcade.draw_text(
                "No filled mock trades yet. Return to the market, choose a side and amount, then click Buy.",
                table.left + 22,
                table.center_y,
                self.colors["muted"],
                14,
                font_name=self.font_primary,
                width=int(table.width - 44),
                multiline=True,
            )
            return

        for index, trade in enumerate(self.trade_history[:9]):
            row_y = header_y - 52 - index * 38
            row = Rect(table.left + 1, table.right - 1, row_y - 12, row_y + 22)
            if index % 2 == 0:
                self._draw_rounded_panel(row, self.colors["panel_alt"])
            pnl_color = self.colors["accent_green"] if trade.profit_loss >= 0 else self.colors["accent_red"]
            arcade.draw_text(trade.action, table.left + 22, row_y, self.colors["text"], 13, font_name=self.font_primary, bold=True)
            arcade.draw_text(trade.side, table.left + 164, row_y, self.colors["text"], 13, font_name=self.font_primary)
            arcade.draw_text(self._format_whole_dollars(trade.amount), table.left + 288, row_y, self.colors["text"], 13, font_name=self.font_primary)
            arcade.draw_text(f"{trade.price_cents}c", table.left + 424, row_y, self.colors["text"], 13, font_name=self.font_primary)
            arcade.draw_text(self._format_signed_dollars(trade.profit_loss), table.left + 552, row_y, pnl_color, 13, font_name=self.font_primary, bold=True)
            arcade.draw_text(self._format_whole_dollars(trade.balance_after), table.left + 708, row_y, self.colors["text"], 13, font_name=self.font_primary)

    def _draw_main_layout(self) -> None:
        content_top = self.height - 104
        left_margin = 28
        gap = 18
        sidebar_width = 360
        content_width = self.width - left_margin * 2
        main_width = content_width - sidebar_width - gap

        chart_rect = Rect(left_margin, left_margin + main_width, 70, content_top)
        sidebar_rect = Rect(chart_rect.right + gap, self.width - left_margin, 70, content_top)

        self._draw_market_panel(chart_rect)
        self._draw_sidebar(sidebar_rect)

    def _draw_market_panel(self, rect: Rect) -> None:
        title_y = rect.top - 22
        icon_rect = Rect(rect.left, rect.left + 58, rect.top - 60, rect.top - 2)
        self._draw_rounded_panel(icon_rect, self.colors["panel_alt"])
        arcade.draw_circle_filled(icon_rect.center_x, icon_rect.center_y + 3, 15, arcade.color.WHITE)
        arcade.draw_triangle_filled(
            icon_rect.center_x,
            icon_rect.center_y + 21,
            icon_rect.center_x - 13,
            icon_rect.center_y,
            icon_rect.center_x + 13,
            icon_rect.center_y,
            arcade.color.WHITE,
        )

        arcade.draw_text(
            self.market_title,
            icon_rect.right + 18,
            title_y - 12,
            self.colors["text"],
            24,
            font_name=self.font_primary,
            bold=True,
        )

        stat_y = rect.top - 122
        arcade.draw_text("Price To Beat", rect.left, stat_y, self.colors["muted"], 13, font_name=self.font_primary, bold=True)
        arcade.draw_text(
            self._format_dollars(self.price_to_beat),
            rect.left,
            stat_y - 36,
            self.colors["text"],
            28,
            font_name=self.font_primary,
            bold=True,
        )

        arcade.draw_line(rect.left + 148, stat_y - 42, rect.left + 148, stat_y + 16, self.colors["panel_border"], 1)

        arcade.draw_text("Current Price", rect.left + 176, stat_y, self.colors["muted"], 13, font_name=self.font_primary, bold=True)
        arcade.draw_text(
            self._format_dollars(self.current_price),
            rect.left + 176,
            stat_y - 36,
            self.colors["text"],
            28,
            font_name=self.font_primary,
            bold=True,
        )

        delta_color = self.colors["accent_green"] if self.price_delta >= 0 else self.colors["accent_red"]
        delta_prefix = "▲" if self.price_delta >= 0 else "▼"
        arcade.draw_text(
            f"{delta_prefix} {self._format_signed_dollars(self.price_delta)}",
            rect.left + 288,
            stat_y - 4,
            delta_color,
            14,
            font_name=self.font_primary,
            bold=True,
        )

        countdown_x = rect.right - 166
        for index, value in enumerate(self._countdown_triplet()):
            unit_x = countdown_x + index * 56
            arcade.draw_text(
                f"{value:02d}",
                unit_x,
                stat_y - 14,
                self.colors["accent_red"],
                28,
                font_name=self.font_primary,
                bold=True,
            )
            label = ("HRS", "MINS", "SECS")[index]
            arcade.draw_text(
                label,
                unit_x + 6,
                stat_y - 36,
                self.colors["muted"],
                10,
                font_name=self.font_primary,
                bold=True,
            )

        chart_area = Rect(rect.left, rect.right, rect.bottom + 142, rect.top - 150)
        self._draw_chart(chart_area)
        self._draw_footer_controls(rect)

    def _draw_chart(self, rect: Rect) -> None:
        grid_top = rect.top - 6
        grid_bottom = rect.bottom + 16

        for index, value in enumerate(self.y_axis_labels):
            y = grid_bottom + index * (grid_top - grid_bottom) / 4
            arcade.draw_line(rect.left, y, rect.right - 22, y, self.colors["grid"], 1)
            arcade.draw_text(
                self._format_dollars(value),
                rect.right - 14,
                y - 8,
                self.colors["muted"],
                14,
                font_name=self.font_primary,
                anchor_x="left",
            )

        target_y = self._price_to_y(self.current_price, grid_bottom, grid_top)
        arcade.draw_line(rect.left, target_y, rect.right - 22, target_y, self.colors["muted_soft"], 1)

        points: list[tuple[float, float]] = []
        for index, price in enumerate(self.chart_points):
            x = rect.left + 6 + index * (rect.width - 62) / max(1, len(self.chart_points) - 1)
            y = self._price_to_y(price, grid_bottom, grid_top)
            points.append((x, y))

        if len(points) > 1:
            arcade.draw_line_strip(points, self.colors["line"], 3)
            last_x, last_y = points[-1]
            arcade.draw_circle_filled(last_x, last_y, 4, self.colors["line"])

        timestamps = self._chart_timestamps()
        for index, label in enumerate(timestamps):
            x = rect.left + 112 + index * (rect.width - 220) / max(1, len(timestamps) - 1)
            arcade.draw_text(
                label,
                x,
                rect.bottom - 10,
                self.colors["muted_soft"],
                12,
                font_name=self.font_primary,
                anchor_x="center",
            )

        target_pill = Rect(rect.right - 112, rect.right - 20, rect.bottom + 18, rect.bottom + 44)
        self._draw_rounded_panel(target_pill, self.colors["chip_active"])
        arcade.draw_text(
            "Target",
            target_pill.left + 20,
            target_pill.center_y - 7,
            self.colors["text"],
            13,
            font_name=self.font_primary,
            bold=True,
        )

    def _draw_footer_controls(self, rect: Rect) -> None:
        footer_y = rect.bottom + 82

        past_rect = Rect(rect.left, rect.left + 92, footer_y - 16, footer_y + 12)
        self._draw_rounded_panel(past_rect, self.colors["panel_alt"])
        arcade.draw_text(
            "Past",
            past_rect.left + 16,
            past_rect.center_y - 7,
            self.colors["text"],
            14,
            font_name=self.font_primary,
            bold=True,
        )

        chip_x = past_rect.right + 28
        chip_colors = [
            self.colors["accent_green"],
            self.colors["accent_green"],
            self.colors["accent_green"],
            self.colors["accent_red"],
        ]
        chip_labels = ["▲", "▲", "▲", "▼"]
        for color, label in zip(chip_colors, chip_labels):
            arcade.draw_circle_filled(chip_x, footer_y - 1, 12, color)
            arcade.draw_text(
                label,
                chip_x,
                footer_y - 7,
                arcade.color.WHITE,
                12,
                font_name=self.font_primary,
                anchor_x="center",
                bold=True,
            )
            chip_x += 34

        time_rect = Rect(chip_x + 10, chip_x + 126, footer_y - 16, footer_y + 14)
        self._draw_rounded_panel(time_rect, arcade.color.WHITE)
        arcade.draw_circle_filled(time_rect.left + 24, time_rect.center_y, 5, self.colors["accent_red"])
        arcade.draw_text(
            "5:00 PM",
            time_rect.left + 40,
            time_rect.center_y - 7,
            self.colors["panel"],
            14,
            font_name=self.font_primary,
            bold=True,
        )

        order_rect = Rect(rect.left, rect.right - 16, rect.bottom - 22, rect.bottom + 54)
        self._draw_rounded_panel(order_rect, self.colors["panel"], border_color=self.colors["panel_border"])
        arcade.draw_text(
            "Order Book",
            order_rect.left + 20,
            order_rect.center_y - 9,
            self.colors["text"],
            16,
            font_name=self.font_primary,
            bold=True,
        )
        arcade.draw_text(
            "$150K Vol.",
            order_rect.right - 18,
            order_rect.center_y - 9,
            self.colors["muted"],
            14,
            font_name=self.font_primary,
            anchor_x="right",
        )

    def _draw_sidebar(self, rect: Rect) -> None:
        ticket_rect = Rect(rect.left, rect.right, rect.bottom, rect.top - 6)
        self._draw_rounded_panel(ticket_rect, self.colors["panel"], border_color=self.colors["panel_border"])
        self._draw_trade_ticket(ticket_rect)

    def _draw_trade_ticket(self, rect: Rect) -> None:
        mode_y = rect.top - 34
        for index, mode in enumerate(("Buy", "Sell")):
            x = rect.left + 20 + index * 62
            selected = self.trade_mode == mode
            arcade.draw_text(
                mode,
                x,
                mode_y,
                self.colors["text"] if selected else self.colors["muted"],
                18,
                font_name=self.font_primary,
                bold=True,
            )
            button_rect = Rect(x - 4, x + 52, mode_y - 8, mode_y + 26)
            self.trade_mode_buttons[mode] = button_rect
            if selected:
                arcade.draw_line(button_rect.left, mode_y - 14, button_rect.right - 16, mode_y - 14, self.colors["text"], 3)

        arcade.draw_text(
            "Market",
            rect.right - 98,
            mode_y,
            self.colors["text"],
            16,
            font_name=self.font_primary,
            bold=True,
        )
        arcade.draw_line(rect.left, rect.top - 58, rect.right, rect.top - 58, self.colors["panel_border"], 1)

        up_rect = Rect(rect.left + 18, rect.left + rect.width / 2 - 8, rect.top - 134, rect.top - 82)
        down_rect = Rect(rect.left + rect.width / 2 + 8, rect.right - 18, rect.top - 134, rect.top - 82)
        self.trade_side_buttons["Up"] = up_rect
        self.trade_side_buttons["Down"] = down_rect
        self._draw_contract_button(up_rect, "Up", self.contract_prices["Up"], self.trade_side == "Up")
        self._draw_contract_button(down_rect, "Down", self.contract_prices["Down"], self.trade_side == "Down")

        stats_top = rect.top - 168
        self._draw_trade_stat(f"{self._player_call_name()}'s Cash", self._format_whole_dollars(self.cash_balance), rect.left + 18, stats_top)
        self._draw_trade_stat("Purchased", self._format_whole_dollars(self.purchased_total), rect.left + 188, stats_top)

        arcade.draw_text("Amount", rect.left + 18, rect.top - 248, self.colors["text"], 16, font_name=self.font_primary)
        self.amount_input_rect = Rect(rect.left + 114, rect.right - 16, rect.top - 296, rect.top - 234)
        input_border = self.colors["accent_blue"] if self.amount_input_active else self.colors["panel_border"]
        self._draw_rounded_panel(self.amount_input_rect, self.colors["panel_soft"], border_color=input_border)
        amount_display = f"${self.amount_input_text}" if self.amount_input_text else "$0"
        arcade.draw_text(
            amount_display,
            self.amount_input_rect.right - 14,
            self.amount_input_rect.center_y - 18,
            self.colors["text"] if self.amount_input_active or self.amount > 0 else self.colors["muted"],
            36,
            font_name=self.font_primary,
            anchor_x="right",
        )
        if self.amount_input_active:
            caret_x = self.amount_input_rect.right - 10
            arcade.draw_line(
                caret_x,
                self.amount_input_rect.bottom + 10,
                caret_x,
                self.amount_input_rect.top - 10,
                self.colors["text"],
                2,
            )

        chip_y = rect.top - 324
        chip_width = 50
        for index, step in enumerate(self.amount_steps):
            chip = Rect(rect.left + 130 + index * 56, rect.left + 130 + index * 56 + chip_width, chip_y - 16, chip_y + 14)
            self.amount_buttons[step] = chip
            active = self.amount >= step and self.amount % step == 0 and self.amount > 0
            self._draw_rounded_panel(chip, self.colors["chip_active"] if active else self.colors["chip"])
            arcade.draw_text(
                f"+${step}",
                chip.center_x,
                chip.center_y - 7,
                self.colors["text"] if active else self.colors["muted"],
                12,
                font_name=self.font_primary,
                anchor_x="center",
                bold=True,
            )

        self.trade_button_rect = Rect(rect.left + 18, rect.right - 18, rect.bottom + 20, rect.bottom + 72)
        trade_button_color = self.colors["accent_green"] if self.trade_mode == "Buy" else self.colors["accent_red"]
        self._draw_rounded_panel(self.trade_button_rect, trade_button_color)
        arcade.draw_text(
            self.trade_mode,
            self.trade_button_rect.center_x,
            self.trade_button_rect.center_y - 8,
            self.colors["text"],
            18,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )

        arcade.draw_text(
            self.status_message,
            rect.left + 18,
            rect.bottom - 6,
            self.colors["muted"],
            12,
            font_name=self.font_primary,
            width=int(rect.width - 36),
            multiline=True,
        )

    def _draw_contract_button(self, rect: Rect, label: str, price: int, selected: bool) -> None:
        if selected:
            fill = self.colors["accent_green"] if label == "Up" else self.colors["chip_active"]
            text = self.colors["text"]
        else:
            fill = self.colors["panel_soft"]
            text = self.colors["muted"]

        self._draw_rounded_panel(rect, fill)
        arcade.draw_text(
            f"{label} {price}¢",
            rect.center_x,
            rect.center_y - 9,
            text,
            16,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )

    def _draw_trade_stat(self, label: str, value: str, x: float, y: float) -> None:
        arcade.draw_text(label, x, y, self.colors["muted"], 12, font_name=self.font_primary, bold=True)
        arcade.draw_text(value, x, y - 28, self.colors["text"], 24, font_name=self.font_primary, bold=True)

    def _draw_rounded_panel(
        self,
        rect: Rect,
        fill_color: arcade.Color,
        *,
        border_color: arcade.Color | None = None,
    ) -> None:
        arcade.draw_rect_filled(
            arcade.XYWH(rect.center_x, rect.center_y, rect.width, rect.height),
            fill_color,
        )
        if border_color is not None:
            arcade.draw_rect_outline(
                arcade.XYWH(rect.center_x, rect.center_y, rect.width, rect.height),
                border_color,
                1,
            )

    def _price_to_y(self, price: float, bottom: float, top: float) -> float:
        span = max(0.01, self.chart_ceiling - self.chart_floor)
        return bottom + ((price - self.chart_floor) / span) * (top - bottom)

    def _format_dollars(self, value: float) -> str:
        return f"${value:,.2f}"

    def _format_signed_dollars(self, value: float) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"

    def _format_whole_dollars(self, value: int) -> str:
        return f"${value:,}"

    def _play_trade_sound(self) -> None:
        if self.buy_sound is not None:
            arcade.play_sound(self.buy_sound, volume=0.55)

    def _sync_amount_from_input(self) -> int:
        self.amount = int(self.amount_input_text) if self.amount_input_text else 0
        return self.amount

    def _player_call_name(self) -> str:
        if not self.player_full_name:
            return "Trader"
        return self.player_full_name.split()[0]

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

    def _estimate_trade_profit_loss(self, action: str, side: str, amount: int, price_cents: int) -> float:
        side_matches_market = (side == "Up" and self.price_delta >= 0) or (side == "Down" and self.price_delta < 0)
        price_edge = abs(price_cents - 50) / 90
        move_edge = abs(self.price_delta) / max(1, self.price_to_beat) * 5
        strength = max(0.03, min(0.28, price_edge + move_edge))
        profit_loss = amount * strength if side_matches_market else -amount * strength
        if action == "Sell":
            profit_loss *= -1
        return round(profit_loss, 2)

    def _record_trade(self, action: str, side: str, amount: int, price_cents: int, profit_loss: float) -> None:
        self.trade_history.insert(
            0,
            TradeRecord(
                action=action,
                side=side,
                amount=amount,
                price_cents=price_cents,
                profit_loss=profit_loss,
                balance_after=self.cash_balance,
            ),
        )

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del button, modifiers

        if self.onboarding_active:
            if self.onboarding_name_rect.contains(x, y):
                self.onboarding_name_active = True
                self.onboarding_message = "Type your full name, like Benjamin Silverman."
            elif self.onboarding_start_rect.contains(x, y):
                self._finish_onboarding()
            return

        if self.tutorial_active:
            if self.tutorial_continue_rect.contains(x, y):
                self.tutorial_active = False
                self.status_message = (
                    f"Welcome, {self._player_call_name()}. Pick Up or Down, choose an amount, "
                    "and place a mock order in the tutorial market."
                )
            return

        if self.dashboard_active:
            if self.dashboard_button_rect.contains(x, y):
                self.dashboard_active = False
            return

        if self.dashboard_button_rect.contains(x, y):
            self.dashboard_active = True
            self.amount_input_active = False
            return

        for mode, rect in self.trade_mode_buttons.items():
            if rect.contains(x, y):
                self.amount_input_active = False
                self.trade_mode = mode
                self.status_message = f"{mode} mode selected. {self._player_call_name()}'s mock ticket is ready."
                return

        for side, rect in self.trade_side_buttons.items():
            if rect.contains(x, y):
                self.amount_input_active = False
                self.trade_side = side
                price = self.contract_prices[side]
                self.status_message = f"{side} selected at {price}¢, {self._player_call_name()}. The live market will keep moving."
                return

        if self.amount_input_rect.contains(x, y):
            self.amount_input_active = True
            self.status_message = f"{self._player_call_name()}, type an amount, then click Buy or Sell."
            return

        self.amount_input_active = False
        self._sync_amount_from_input()

        for step, rect in self.amount_buttons.items():
            if rect.contains(x, y):
                self.amount += step
                self.amount_input_text = str(self.amount)
                self.status_message = f"Added ${step}. {self._player_call_name()}'s mock order total is now ${self.amount}."
                return

        if self.trade_button_rect.contains(x, y):
            trade_amount = self._sync_amount_from_input()

            if trade_amount <= 0:
                self.status_message = f"{self._player_call_name()}, choose an amount before placing the mock trade."
            elif self.trade_mode == "Buy" and trade_amount > self.cash_balance:
                self.status_message = f"{self._player_call_name()}, not enough cash. You have {self._format_whole_dollars(self.cash_balance)} left."
            elif self.trade_mode == "Sell" and trade_amount > self.purchased_total:
                self.status_message = f"{self._player_call_name()}, you only have {self._format_whole_dollars(self.purchased_total)} purchased to sell."
            else:
                selected_price = self.contract_prices[self.trade_side]
                if self.trade_mode == "Buy":
                    self.cash_balance -= trade_amount
                    self.purchased_total += trade_amount
                else:
                    self.cash_balance += trade_amount
                    self.purchased_total -= trade_amount
                profit_loss = self._estimate_trade_profit_loss(
                    self.trade_mode,
                    self.trade_side,
                    trade_amount,
                    selected_price,
                )
                self._record_trade(self.trade_mode, self.trade_side, trade_amount, selected_price, profit_loss)
                self._play_trade_sound()
                self.status_message = (
                    f"{self._player_call_name()}, {self.trade_mode} order filled for {self._format_whole_dollars(trade_amount)} on "
                    f"{self.trade_side} at {selected_price}¢. "
                    f"P/L: {self._format_signed_dollars(profit_loss)}. "
                    f"Cash: {self._format_whole_dollars(self.cash_balance)}. "
                    f"Purchased: {self._format_whole_dollars(self.purchased_total)}."
                )
                self.amount = 0
                self.amount_input_text = ""

    def on_text(self, text: str) -> None:
        if self.onboarding_active:
            if not self.onboarding_name_active:
                return

            allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -'."
            for character in text:
                if character in allowed and len(self.onboarding_name) < MAX_FULL_NAME_CHARS:
                    self.onboarding_name += character
            self.onboarding_message = "Click Start Practice Tutorial when your name is ready."
            return

        if not self.amount_input_active or not text.isdigit():
            return

        if self.amount_input_text == "0":
            self.amount_input_text = text
        elif len(self.amount_input_text) < 7:
            self.amount_input_text += text

        self._sync_amount_from_input()
        self.status_message = f"Amount set to ${self.amount}."

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers

        if self.onboarding_active:
            if symbol == arcade.key.BACKSPACE:
                self.onboarding_name = self.onboarding_name[:-1]
                self.onboarding_message = "Type your full name to create a practice identity."
            elif symbol in (arcade.key.ENTER, arcade.key.RETURN):
                self.onboarding_message = "Use the Start Practice Tutorial button to continue."
            elif symbol == arcade.key.TAB:
                self.onboarding_name_active = True
            return

        if self.tutorial_active:
            return

        if self.dashboard_active:
            return

        if not self.amount_input_active:
            return

        if symbol == arcade.key.BACKSPACE:
            self.amount_input_text = self.amount_input_text[:-1]
            self._sync_amount_from_input()
            self.status_message = f"Amount set to ${self.amount}."
        elif symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.ESCAPE):
            self.amount_input_active = False


def main() -> None:
    PredictionMarketWindow()
    arcade.run()


if __name__ == "__main__":
    main()
