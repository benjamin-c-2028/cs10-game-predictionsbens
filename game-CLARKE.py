"""
Fake 5-minute buy/sell demo built with Python Arcade.

Run this file with the project virtual environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

import arcade


WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 760
WINDOW_TITLE = "5-Minute Buy/Sell Demo"
BUY_SOUND_PATH = Path(__file__).with_name("buy_sound.ogg")

BACKGROUND = (17, 22, 28)
PANEL = (23, 29, 36)
PANEL_DARK = (18, 23, 29)
BORDER = (42, 50, 60)
TEXT = (238, 242, 247)
MUTED = (136, 147, 161)
SOFT = (92, 103, 118)
GREEN = (86, 164, 109)
GREEN_DARK = (54, 120, 76)
RED = (208, 74, 68)
RED_DARK = (132, 48, 48)
ORANGE = (248, 158, 43)
BLUE = (79, 140, 245)
BUTTON = (31, 38, 47)
BUTTON_HOVER = (44, 53, 64)


@dataclass
class Button:
    """Simple rectangular control with mouse hit detection."""

    left: float
    bottom: float
    width: float
    height: float
    label: str
    kind: str
    value: str | int | None = None

    def hit_test(self, x: float, y: float) -> bool:
        return (
            self.left <= x <= self.left + self.width
            and self.bottom <= y <= self.bottom + self.height
        )

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.bottom + self.height / 2


class FiveMinuteMarketDemo(arcade.Window):
    """A fake trading ticket with hover and click interactions."""

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

        self.mode = "Buy"
        self.outcome = "Up"
        self.amount = 25
        self.balance = 500.00
        self.position = 0
        self.status_message = "Choose a side, amount, and place a fake order."

        self.target_price = 75646.92
        self.current_price = 75637.90
        self.up_price_cents = 50
        self.down_price_cents = 50
        self.price_history = self.make_initial_prices()
        self.countdown = 58.0
        self.elapsed = 0.0
        self.hovered_button: Button | None = None
        self.buy_sound = self.load_buy_sound()

        self.buttons: list[Button] = []
        self.create_buttons()
        self.update_outcome_prices()

    def load_buy_sound(self):
        if not BUY_SOUND_PATH.exists():
            return None
        return arcade.load_sound(BUY_SOUND_PATH)

    def make_initial_prices(self) -> list[float]:
        prices = []
        price = self.current_price - 18
        for index in range(90):
            drift = 0.12 if index > 50 else 0.04
            price += random.uniform(-0.18, 0.28) + drift
            if index == 55:
                price += 7
            prices.append(price)
        return prices

    def create_buttons(self) -> None:
        self.buttons = [
            Button(925, 621, 82, 36, "Buy", "mode", "Buy"),
            Button(1018, 621, 82, 36, "Sell", "mode", "Sell"),
            Button(925, 535, 140, 52, "Up 50c", "outcome", "Up"),
            Button(1076, 535, 140, 52, "Down 50c", "outcome", "Down"),
            Button(925, 410, 48, 44, "-", "amount_step", -5),
            Button(1168, 410, 48, 44, "+", "amount_step", 5),
            Button(925, 242, 291, 54, "Place Buy", "submit", None),
            Button(68, 132, 76, 36, "Past", "time", "Past"),
            Button(158, 132, 92, 36, "5:05 PM", "time", "5:05"),
            Button(264, 132, 92, 36, "5:10 PM", "time", "5:10"),
            Button(370, 132, 92, 36, "5:15 PM", "time", "5:15"),
        ]

    def on_draw(self) -> None:
        self.clear()
        self.draw_header()
        self.draw_market_panel()
        self.draw_graph()
        self.draw_time_buttons()
        self.draw_order_book()
        self.draw_trade_ticket()

    def on_update(self, delta_time: float) -> None:
        self.elapsed += delta_time
        self.countdown = max(0, self.countdown - delta_time)

        if self.elapsed >= 0.18:
            self.elapsed = 0
            move = random.uniform(-0.85, 0.95)
            if self.outcome == "Up":
                move += 0.10
            else:
                move -= 0.10
            self.current_price += move
            self.price_history.append(self.current_price)
            self.update_outcome_prices()

            if len(self.price_history) > 110:
                self.price_history.pop(0)

            if self.countdown <= 0:
                self.countdown = 60
                self.status_message = "New fake five-minute market started."

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self.hovered_button = self.find_button_at(x, y)

    def on_mouse_press(
        self, x: float, y: float, button: int, modifiers: int
    ) -> None:
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        clicked = self.find_button_at(x, y)
        if clicked is None:
            return

        if clicked.kind == "mode":
            self.mode = str(clicked.value)
            self.status_message = f"{self.mode} mode selected."
        elif clicked.kind == "outcome":
            self.outcome = str(clicked.value)
            self.status_message = f"{self.outcome} selected."
        elif clicked.kind == "amount_step":
            self.amount = self.clamp_amount(self.amount + int(clicked.value))
            self.status_message = f"Fake order amount set to ${self.amount}."
        elif clicked.kind == "submit":
            self.place_fake_order()
        elif clicked.kind == "time":
            self.status_message = f"Viewing fake {clicked.label} market."

    def find_button_at(self, x: float, y: float) -> Button | None:
        for button in self.buttons:
            if button.hit_test(x, y):
                return button
        return None

    def update_outcome_prices(self) -> None:
        price_gap = self.current_price - self.target_price
        up_price = round(50 + price_gap * 1.2)
        self.up_price_cents = max(5, min(95, up_price))
        self.down_price_cents = 100 - self.up_price_cents

        for button in self.buttons:
            if button.kind == "outcome" and button.value == "Up":
                button.label = f"Up {self.up_price_cents}c"
            elif button.kind == "outcome" and button.value == "Down":
                button.label = f"Down {self.down_price_cents}c"

    def selected_price_cents(self) -> int:
        if self.outcome == "Up":
            return self.up_price_cents
        return self.down_price_cents

    def place_fake_order(self) -> None:
        fee = random.uniform(0.01, 0.19)
        selected_price = self.selected_price_cents()
        fake_shares = max(1, round(self.amount / (selected_price / 100)))

        if self.mode == "Buy":
            self.play_buy_sound()
            self.balance = max(0, self.balance - self.amount - fee)
            self.position += fake_shares
        else:
            self.balance += self.amount - fee
            self.position = max(0, self.position - fake_shares)

        price_text = self.format_money(self.current_price)
        self.status_message = (
            f"{self.mode} {self.outcome} at {selected_price}c: "
            f"${self.amount} fake order "
            f"near {price_text}."
        )

    def play_buy_sound(self) -> None:
        if self.buy_sound is not None:
            arcade.play_sound(self.buy_sound, volume=0.65)

    def clamp_amount(self, amount: int) -> int:
        return max(5, min(500, amount))

    def draw_header(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 704, WINDOW_WIDTH, 56, PANEL_DARK)
        arcade.draw_line(0, 704, WINDOW_WIDTH, 704, BORDER, 1)

        arcade.draw_text(
            "5-Minute Market Demo",
            50,
            724,
            TEXT,
            22,
            bold=True,
            anchor_y="center",
        )
        arcade.draw_text(
            "Fake practice screen - no real trading",
            338,
            724,
            MUTED,
            13,
            anchor_y="center",
        )
        arcade.draw_text(
            "5 minute info: choose Up or Down before the timer ends",
            50,
            674,
            MUTED,
            13,
            bold=True,
        )

    def draw_market_panel(self) -> None:
        arcade.draw_lbwh_rectangle_filled(38, 610, 56, 56, ORANGE)
        arcade.draw_text("B", 66, 638, TEXT, 31, bold=True, anchor_x="center", anchor_y="center")
        arcade.draw_text("BTC Up or Down 5m", 112, 646, TEXT, 23, bold=True)
        arcade.draw_text("April 29, 5:05-5:10PM ET", 112, 620, MUTED, 15, bold=True)

        arcade.draw_text("Price To Beat", 38, 577, MUTED, 11, bold=True)
        arcade.draw_text(self.format_money(self.target_price), 38, 545, MUTED, 25, bold=True)
        arcade.draw_line(216, 544, 216, 580, BORDER, 1)
        arcade.draw_text("Current Price", 240, 577, ORANGE, 11, bold=True)
        arcade.draw_text(self.format_money(self.current_price), 240, 545, ORANGE, 25, bold=True)

        minutes = int(self.countdown // 60)
        seconds = int(self.countdown % 60)
        arcade.draw_text(
            f"{minutes:02d}",
            770,
            560,
            (241, 94, 88),
            25,
            bold=True,
            anchor_x="center",
        )
        arcade.draw_text(
            f"{seconds:02d}",
            812,
            560,
            (241, 94, 88),
            25,
            bold=True,
            anchor_x="center",
        )
        arcade.draw_text("MINS", 770, 538, MUTED, 9, bold=True, anchor_x="center")
        arcade.draw_text("SECS", 812, 538, MUTED, 9, bold=True, anchor_x="center")

    def draw_graph(self) -> None:
        left = 38
        bottom = 178
        width = 820
        height = 330

        for row in range(4):
            y = bottom + row * (height / 3)
            arcade.draw_line(left, y, left + width, y, (33, 41, 49), 1)

        target_y = bottom + height * 0.76
        arcade.draw_line(left, target_y, left + width, target_y, (146, 100, 40), 1)
        arcade.draw_text("$75,640", left + width + 10, target_y + 4, MUTED, 10)
        arcade.draw_text("+ $2", left + 12, bottom + 165, RED, 13, bold=True)
        arcade.draw_text("+ $4", left + 12, bottom + 112, GREEN, 13, bold=True)
        arcade.draw_text("+ $5", left + 12, bottom + 82, GREEN, 13, bold=True)

        low = min(self.price_history) - 2
        high = max(self.price_history) + 2
        price_range = max(1, high - low)
        step = width / max(1, len(self.price_history) - 1)
        points = []

        for index, price in enumerate(self.price_history):
            x = left + index * step
            y = bottom + ((price - low) / price_range) * height
            points.append((x, y))

        if len(points) > 1:
            arcade.draw_line_strip(points, ORANGE, 3)
            last_x, last_y = points[-1]
            arcade.draw_circle_filled(last_x, last_y, 4, ORANGE)

        arcade.draw_text("2:08:32 PM", left + 40, bottom - 20, MUTED, 10)
        arcade.draw_text("2:08:44 PM", left + 378, bottom - 20, MUTED, 10)
        arcade.draw_text("2:09:00 PM", left + 700, bottom - 20, MUTED, 10)

    def draw_time_buttons(self) -> None:
        for button in self.buttons:
            if button.kind != "time":
                continue

            selected = button.value == "5:10"
            color = (234, 238, 244) if selected else BUTTON
            text_color = BACKGROUND if selected else TEXT
            if button is self.hovered_button and not selected:
                color = BUTTON_HOVER

            self.draw_button_box(button, color, text_color, BORDER)

    def draw_order_book(self) -> None:
        arcade.draw_lbwh_rectangle_outline(38, 40, 820, 78, BORDER, 1)
        arcade.draw_text("Order Book", 54, 86, TEXT, 15, bold=True, anchor_y="center")
        arcade.draw_text("i", 142, 86, MUTED, 11, bold=True, anchor_y="center")
        arcade.draw_text("$510 Vol.", 764, 86, MUTED, 13, anchor_x="right", anchor_y="center")
        arcade.draw_text("Rules", 38, 12, TEXT, 13, bold=True)
        arcade.draw_text("Market Context", 104, 12, MUTED, 13, bold=True)

    def draw_trade_ticket(self) -> None:
        arcade.draw_lbwh_rectangle_outline(895, 56, 340, 611, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(896, 57, 338, 609, PANEL)
        arcade.draw_line(895, 613, 1235, 613, BORDER, 1)

        for button in self.buttons:
            if button.kind == "mode":
                selected = button.value == self.mode
                color = PANEL if selected else PANEL
                text_color = TEXT if selected else MUTED
                if button is self.hovered_button and not selected:
                    color = BUTTON_HOVER
                self.draw_button_box(button, color, text_color, color, selected)

        arcade.draw_text("Order Ticket", 925, 594, MUTED, 10, bold=True)

        for button in self.buttons:
            if button.kind == "outcome":
                selected = button.value == self.outcome
                if button.value == "Up":
                    color = GREEN if selected else BUTTON
                    selected_border = GREEN
                else:
                    color = RED_DARK if selected else BUTTON
                    selected_border = RED
                if button is self.hovered_button and not selected:
                    color = BUTTON_HOVER
                text_color = TEXT if selected or button is self.hovered_button else MUTED
                border = selected_border if selected else color
                self.draw_button_box(button, color, text_color, border)

        arcade.draw_text(f"{self.mode} {self.outcome}", 925, 502, TEXT, 16, bold=True)
        arcade.draw_text(
            f"Your Balance: ${self.balance:,.2f}",
            925,
            480,
            MUTED,
            12,
            bold=True,
        )

        for button in self.buttons:
            if button.kind == "amount_step":
                color = BUTTON_HOVER if button is self.hovered_button else BUTTON
                text_color = TEXT if button is self.hovered_button else MUTED
                self.draw_button_box(button, color, text_color, BORDER)

        arcade.draw_text("Amount", 925, 462, MUTED, 11, bold=True)
        arcade.draw_lbwh_rectangle_filled(985, 410, 171, 44, PANEL_DARK)
        arcade.draw_lbwh_rectangle_outline(985, 410, 171, 44, BORDER, 1)
        arcade.draw_text(
            f"${self.amount}",
            1070,
            434,
            TEXT,
            18,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )
        arcade.draw_text(
            "Use - / + to change fake order size",
            925,
            388,
            MUTED,
            10,
        )

        cost = self.amount
        selected_price = self.selected_price_cents()
        shares = max(1, round(self.amount / (selected_price / 100)))
        payout = round(shares)
        arcade.draw_text("Fake order summary", 925, 360, MUTED, 11, bold=True)
        arcade.draw_text(f"Cost: ${cost}", 925, 337, TEXT, 12)
        arcade.draw_text(f"Possible payout: ${payout}", 1060, 337, TEXT, 12)
        arcade.draw_text(
            f"Holdings: {self.position} {self.outcome} shares",
            925,
            314,
            MUTED,
            12,
        )
        arcade.draw_text(
            f"Live {self.outcome} price: {selected_price}c",
            1060,
            314,
            MUTED,
            12,
        )

        submit = next(button for button in self.buttons if button.kind == "submit")
        submit.label = f"Place {self.mode}"
        submit_color = GREEN_DARK if self.mode == "Buy" else RED_DARK
        if submit is self.hovered_button:
            submit_color = GREEN if self.mode == "Buy" else RED
        self.draw_button_box(submit, submit_color, TEXT, submit_color)

        arcade.draw_text(
            self.status_message,
            925,
            214,
            MUTED,
            11,
            width=291,
            multiline=True,
        )
        arcade.draw_line(925, 172, 1216, 172, BORDER, 1)
        self.draw_account_info(925, 82)

    def draw_account_info(self, left: float, bottom: float) -> None:
        arcade.draw_text("Your Balance", left, bottom + 72, MUTED, 12, bold=True)
        arcade.draw_text(
            f"${self.balance:,.2f}",
            left,
            bottom + 45,
            TEXT,
            18,
            bold=True,
        )
        arcade.draw_text("Your Current Holdings", left + 160, bottom + 72, MUTED, 12, bold=True)
        arcade.draw_text(
            f"{self.position} shares",
            left + 160,
            bottom + 45,
            TEXT,
            18,
            bold=True,
        )
        arcade.draw_text(
            f"Selected side: {self.outcome}",
            left,
            bottom + 15,
            MUTED,
            11,
        )

    def draw_button_box(
        self,
        button: Button,
        fill_color: tuple[int, int, int],
        text_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
        underline: bool = False,
    ) -> None:
        arcade.draw_lbwh_rectangle_filled(
            button.left,
            button.bottom,
            button.width,
            button.height,
            fill_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            button.left,
            button.bottom,
            button.width,
            button.height,
            border_color,
            1,
        )
        arcade.draw_text(
            button.label,
            button.center_x,
            button.center_y + 3,
            text_color,
            13,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        if underline:
            arcade.draw_line(
                button.left + 12,
                button.bottom + 3,
                button.left + button.width - 12,
                button.bottom + 3,
                TEXT,
                2,
            )

    def format_money(self, value: float) -> str:
        return f"${value:,.2f}"


def main() -> None:
    FiveMinuteMarketDemo()
    arcade.run()


if __name__ == "__main__":
    main()
