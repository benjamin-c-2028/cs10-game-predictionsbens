from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path
import random
from dataclasses import dataclass

import arcade

WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 780
WINDOW_TITLE = "Arcade Prediction Market"
BUY_SOUND_PATH = Path(__file__).resolve().parent / "asset-game" / "sounds" / "buy_cash_register.ogg"
STARTING_CASH = 1000


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


class PredictionMarketWindow(arcade.Window):
    def __init__(self) -> None:
        super().__init__(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            WINDOW_TITLE,
            resizable=True,
            update_rate=1 / 60,
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
        self.status_message = "Live demo is updating. Select a side and build a mock position."

        self.amount_steps = [1, 5, 10, 100]
        self.trade_mode_buttons: dict[str, Rect] = {}
        self.trade_side_buttons: dict[str, Rect] = {}
        self.amount_buttons: dict[int, Rect] = {}
        self.amount_input_rect = Rect(0, 0, 0, 0)
        self.trade_button_rect = Rect(0, 0, 0, 0)
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
        self.market_tick_accumulator += delta_time
        while self.market_tick_accumulator >= self.market_tick_seconds:
            self.market_tick_accumulator -= self.market_tick_seconds
            self._advance_market()

    def on_draw(self) -> None:
        self.clear()
        self.trade_mode_buttons.clear()
        self.trade_side_buttons.clear()
        self.amount_buttons.clear()

        self._draw_header()
        self._draw_main_layout()

    def _draw_header(self) -> None:
        width = self.width
        header_height = 84
        category_height = 44

        arcade.draw_rect_filled(
            arcade.XYWH(width / 2, self.height - header_height / 2, width, header_height),
            self.colors["panel"],
        )
        arcade.draw_rect_filled(
            arcade.XYWH(width / 2, self.height - header_height - category_height / 2, width, category_height),
            self.colors["bg"],
        )
        arcade.draw_line(
            0,
            self.height - header_height - category_height,
            width,
            self.height - header_height - category_height,
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

        categories = ["Trending", "Breaking", "Energy", "Politics", "Sports", "Crypto", "Economy", "Weather", "More"]
        x = 34
        for label in categories:
            arcade.draw_text(
                label,
                x,
                self.height - 119,
                self.colors["muted"],
                13,
                font_name=self.font_primary,
                bold=label == "Trending",
            )
            x += 104 if label not in {"Economy", "Trending"} else 110

        arcade.draw_text(
            "Log In",
            width - 220,
            self.height - 56,
            self.colors["accent_blue"],
            16,
            font_name=self.font_primary,
            bold=True,
        )

        signup = Rect(width - 138, width - 40, self.height - 72, self.height - 26)
        self._draw_rounded_panel(signup, self.colors["accent_blue"])
        arcade.draw_text(
            "Sign Up",
            signup.center_x,
            signup.center_y - 9,
            self.colors["text"],
            16,
            font_name=self.font_primary,
            anchor_x="center",
            bold=True,
        )

    def _draw_main_layout(self) -> None:
        content_top = self.height - 148
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
        self._draw_trade_stat("Cash", self._format_whole_dollars(self.cash_balance), rect.left + 18, stats_top)
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

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del button, modifiers

        for mode, rect in self.trade_mode_buttons.items():
            if rect.contains(x, y):
                self.amount_input_active = False
                self.trade_mode = mode
                self.status_message = f"{mode} mode selected. Live mock ticket ready."
                return

        for side, rect in self.trade_side_buttons.items():
            if rect.contains(x, y):
                self.amount_input_active = False
                self.trade_side = side
                price = self.contract_prices[side]
                self.status_message = f"{side} selected at {price}¢. The live market will keep moving."
                return

        if self.amount_input_rect.contains(x, y):
            self.amount_input_active = True
            self.status_message = "Type an amount, then click Buy or Sell."
            return

        self.amount_input_active = False
        self._sync_amount_from_input()

        for step, rect in self.amount_buttons.items():
            if rect.contains(x, y):
                self.amount += step
                self.amount_input_text = str(self.amount)
                self.status_message = f"Added ${step}. Mock order total is now ${self.amount}."
                return

        if self.trade_button_rect.contains(x, y):
            trade_amount = self._sync_amount_from_input()

            if trade_amount <= 0:
                self.status_message = "Choose an amount before placing the mock trade."
            elif self.trade_mode == "Buy" and trade_amount > self.cash_balance:
                self.status_message = f"Not enough cash. You have {self._format_whole_dollars(self.cash_balance)} left."
            elif self.trade_mode == "Sell" and trade_amount > self.purchased_total:
                self.status_message = f"You only have {self._format_whole_dollars(self.purchased_total)} purchased to sell."
            else:
                if self.trade_mode == "Buy":
                    self.cash_balance -= trade_amount
                    self.purchased_total += trade_amount
                else:
                    self.cash_balance += trade_amount
                    self.purchased_total -= trade_amount
                self._play_trade_sound()
                self.status_message = (
                    f"{self.trade_mode} order filled for {self._format_whole_dollars(trade_amount)} on "
                    f"{self.trade_side} at {self.contract_prices[self.trade_side]}¢. "
                    f"Cash: {self._format_whole_dollars(self.cash_balance)}. "
                    f"Purchased: {self._format_whole_dollars(self.purchased_total)}."
                )
                self.amount = 0
                self.amount_input_text = ""

    def on_text(self, text: str) -> None:
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
