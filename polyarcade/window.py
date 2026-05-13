"""Simulated Bitcoin Up/Down prediction market built with Python Arcade."""

from __future__ import annotations

import math

import arcade

from .constants import (
    BACKGROUND,
    BLUE,
    BORDER,
    GREEN,
    GREEN_DARK,
    HEADER,
    MARKET_DURATION_SECONDS,
    MARKET_TRANSITION_SPEED,
    MAX_CHART_RENDER_POINTS,
    MAX_AMOUNT_INPUT_CHARS,
    MAX_FRAME_SECONDS,
    MAX_FULL_NAME_CHARS,
    MUTED,
    MUTED_DARK,
    ORANGE,
    PANEL,
    PANEL_ALT,
    PANEL_SOFT,
    PRICE_TICK_SECONDS,
    RED,
    RED_DARK,
    STARTING_BALANCE,
    TEXT,
    WHITE,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    YELLOW,
)
from .content import ALL_NEWS, DEMO_NEWS_CARDS, SIMPLE_TUTORIAL_ARTICLES, TUTORIAL_CLICK_TARGETS
from .market_logic import advance_market_price, build_market, choose_news_cards, contract_price
from .models import ClickZone, MarketState, NewsCard, Position, TradeRecord

CLICK_SNAP_DISTANCE = 12.0
CURSOR_TEXT_KEYS = frozenset({"onboard_name", "amount_input"})
TEXTBOX_PULSE_SPEED = 11.0
TEXT_CARET_BLINK_SECONDS = 0.9
TEXT_CARET_VISIBLE_RATIO = 0.64
PAGE_SWITCH_SPEED = 7.2


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
            antialiasing=False,
            samples=0,
            vsync=True,
        )
        arcade.set_background_color(BACKGROUND)

        self.onboarding_active = True
        self.tutorial_active = False
        self.onboarding_name = ""
        self.onboarding_name_active = True
        self.onboarding_message = "Type your first name to create a practice identity."
        self.player_full_name = ""
        self.balance = STARTING_BALANCE
        self.demo_balance = STARTING_BALANCE
        self.selected_side = "Up"
        self.selected_amount = 0
        self.amount_input_text = ""
        self.amount_input_active = False
        self.position: Position | None = None
        self.trade_history: list[TradeRecord] = []
        self.dashboard_active = False
        self.demo_round_active = False
        self.demo_round_complete = False
        self.demo_side_picked = False
        self.demo_amount_picked = False
        self.status_message = "Choose Up or Down, enter an amount, then buy to start the market."
        self.ui_animation_seconds = 0.0
        self.tick_accumulator = 0.0
        self.price_velocity = 0.0
        self.market_transition = 1.0
        self.hovered_key: str | None = None
        self.click_zones: list[ClickZone] = []
        self.cursor_x = WINDOW_WIDTH / 2
        self.cursor_y = WINDOW_HEIGHT / 2
        self.cursor_click_flash = 0.0
        self.cursor_anim_time = 0.0
        self.page_transition_progress = 1.0
        self.page_key = "onboarding"
        self._hover_refresh_needed = True
        self._chart_prices_cache: list[float] = []
        self._chart_geometry_cache: dict[str, object] | None = None
        self._chart_geometry_dims: tuple[float, float, float, float] | None = None
        self._chart_geometry_dirty = True
        self._chart_prices_dirty = True
        self.news_cards = choose_news_cards(ALL_NEWS)
        self.market = self._new_market()
        self.set_mouse_visible(False)

    def _current_page_key(self) -> str:
        if self.onboarding_active:
            return "onboarding"
        if self.tutorial_active:
            return "tutorial"
        if self.dashboard_active:
            return "dashboard"
        return "market"

    def _new_market(self, demo_mode: bool = False) -> MarketState:
        self.tick_accumulator = 0.0
        self.price_velocity = 0.0
        # Keep click response immediate: do not fade in a post-click transition overlay.
        self.market_transition = 1.0
        self._chart_prices_cache = []
        self._chart_geometry_cache = None
        self._chart_geometry_dims = None
        self._mark_chart_dirty()
        self._hover_refresh_needed = True
        self.position = None
        if demo_mode:
            self.selected_side = ""
            self.selected_amount = 0
            self.amount_input_text = ""
            self.amount_input_active = False
            self.news_cards = choose_news_cards(DEMO_NEWS_CARDS)
            self.demo_round_complete = False
            self.demo_side_picked = False
            self.demo_amount_picked = False
        else:
            self.selected_side = "Up"
            self.selected_amount = 0
            self.amount_input_text = ""
            self.amount_input_active = False
            self.news_cards = choose_news_cards(ALL_NEWS)

        call_name = self._player_call_name()
        if demo_mode:
            self.status_message = (
                f"{call_name}, demo step 1: pick Up or Down. "
                "This round uses demo cash only."
            )
        else:
            self.status_message = f"{call_name}, choose a side, enter an amount, then buy to start the market."

        return build_market(self.news_cards)

    def _start_demo_round(self) -> None:
        self.demo_round_active = True
        self.demo_balance = STARTING_BALANCE
        self.dashboard_active = False
        self.market = self._new_market(demo_mode=True)

    def _finish_demo_round(self) -> None:
        self.demo_round_active = False
        self.demo_round_complete = False
        self.demo_side_picked = False
        self.demo_amount_picked = False
        self.demo_balance = STARTING_BALANCE
        self.market = self._new_market()
        self.status_message = (
            f"{self._player_call_name()}, demo done. "
            "Now this is your real practice market."
        )

    def _sync_selected_amount_from_text(self) -> None:
        self.selected_amount = int(self.amount_input_text) if self.amount_input_text else 0
        if self.demo_round_active:
            self.demo_amount_picked = self.selected_amount > 0

    def _update_demo_status(self) -> None:
        if not self.demo_round_active or self.market.active or self.market.settled:
            return

        call_name = self._player_call_name()
        if not self.demo_side_picked:
            self.status_message = f"{call_name}, demo step 1: pick Up or Down."
        elif not self.demo_amount_picked:
            self.status_message = f"{call_name}, demo step 2: type a demo amount."
        else:
            self.status_message = (
                f"{call_name}, demo step 3: click Buy & Start. "
                "This still uses demo cash only."
            )

    def on_draw(self) -> None:
        self.clear()
        self.click_zones.clear()
        current_page = self._current_page_key()
        if current_page != self.page_key:
            self.page_key = current_page
            self.page_transition_progress = 0.0
        if self.onboarding_active:
            self._draw_onboarding()
            self._refresh_hovered_key_if_needed()
            self._draw_game_cursor()
            self._draw_page_transition()
            return
        if self.tutorial_active:
            self._draw_tutorial_page()
            self._refresh_hovered_key_if_needed()
            self._draw_game_cursor()
            self._draw_page_transition()
            return
        if self.dashboard_active:
            self._draw_dashboard()
            self._refresh_hovered_key_if_needed()
            self._draw_game_cursor()
            self._draw_page_transition()
            return

        self._draw_header()
        self._draw_market()
        self._draw_ticket()
        self._draw_news_cards()
        self._draw_transition_overlay()
        self._refresh_hovered_key_if_needed()
        self._draw_game_cursor()
        self._draw_page_transition()

    def on_update(self, delta_time: float) -> None:
        delta_time = max(0.0, delta_time)
        self.ui_animation_seconds += delta_time
        animation_delta = min(delta_time, MAX_FRAME_SECONDS)
        self.cursor_anim_time += animation_delta
        self.cursor_click_flash = max(0.0, self.cursor_click_flash - animation_delta * 6.0)
        if self.page_transition_progress < 1.0:
            self.page_transition_progress = min(
                1.0,
                self.page_transition_progress + delta_time * PAGE_SWITCH_SPEED,
            )

        if self.onboarding_active or self.tutorial_active:
            return

        if not self.dashboard_active:
            self.market_transition = min(
                1.0,
                self.market_transition + animation_delta * MARKET_TRANSITION_SPEED,
            )

        if not self.market.active or self.market.settled:
            return

        max_market_delta = max(0.0, MARKET_DURATION_SECONDS - self.market.elapsed_seconds)
        remaining_delta = min(delta_time, max_market_delta)
        while remaining_delta > 0 and not self.market.settled:
            step_delta = min(remaining_delta, MAX_FRAME_SECONDS)
            previous_elapsed = self.market.elapsed_seconds
            self.market.elapsed_seconds = min(
                MARKET_DURATION_SECONDS,
                self.market.elapsed_seconds + step_delta,
            )
            effective_delta = self.market.elapsed_seconds - previous_elapsed
            if effective_delta <= 0:
                break

            self.price_velocity, self.market.current_price = advance_market_price(
                self.market,
                self.price_velocity,
                effective_delta,
            )
            self.tick_accumulator += effective_delta

            while self.tick_accumulator >= PRICE_TICK_SECONDS and not self.market.settled:
                self.tick_accumulator -= PRICE_TICK_SECONDS
                self.market.history.append(self.market.current_price)
                self._mark_chart_dirty()

            if self.market.elapsed_seconds >= MARKET_DURATION_SECONDS and not self.market.settled:
                self._settle_market()
                break
            remaining_delta -= effective_delta

    def _settle_market(self) -> None:
        self.market.active = False
        self.market.current_price = self.market.resolve_price
        self.market.history.append(self.market.current_price)
        self._mark_chart_dirty()
        self.market.settled = True
        self._hover_refresh_needed = True

        winning_side = "Up" if self.market.current_price >= self.market.target_price else "Down"
        call_name = self._player_call_name()
        if self.position is None:
            if self.demo_round_active:
                self.demo_round_complete = True
                self.status_message = (
                    f"{call_name}, demo over. {winning_side} won. "
                    "Click Start Real Market."
                )
            else:
                self.status_message = f"{call_name}, market settled {winning_side}. No position was opened."
            return

        payout = round(self.position.shares, 2)
        if self.position.side == winning_side:
            if self.demo_round_active:
                self.demo_balance += payout
            else:
                self.balance += payout
            self.position.resolved_result = "Won"
            if self.demo_round_active:
                self.demo_round_complete = True
                self.status_message = (
                    f"{call_name}, demo over. {winning_side} won. "
                    f"Your demo cash would be ${self.demo_balance:,.2f}. "
                    "Click Start Real Market."
                )
            else:
                self._record_trade(winning_side, round(payout - self.position.amount, 2))
                self.status_message = (
                    f"{call_name}, {winning_side} wins. Your ${self.position.amount} position paid ${payout:,.2f}."
                )
        else:
            self.position.resolved_result = "Lost"
            if self.demo_round_active:
                self.demo_round_complete = True
                self.status_message = (
                    f"{call_name}, demo over. {winning_side} won. "
                    f"Your demo cash would be ${self.demo_balance:,.2f}. "
                    "Click Start Real Market."
                )
            else:
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
        available_balance = self.demo_balance if self.demo_round_active else self.balance
        if self.position is not None:
            self.status_message = f"{call_name}, you already bought this market. Wait for settlement."
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market."
            return
        if not self.selected_side:
            self.status_message = f"{call_name}, pick Up or Down first."
            return
        if self.selected_amount <= 0:
            self.status_message = f"{call_name}, pick a stake first."
            return
        if self.selected_amount > available_balance:
            self.status_message = f"{call_name}, not enough balance for that order amount."
            return

        entry_price = self._contract_price(self.selected_side)
        shares = self.selected_amount / (entry_price / 100)
        if self.demo_round_active:
            self.demo_balance -= self.selected_amount
        else:
            self.balance -= self.selected_amount
        self.position = Position(
            side=self.selected_side,
            amount=self.selected_amount,
            entry_price_cents=entry_price,
            shares=shares,
        )
        self.market.active = True
        if self.demo_round_active:
            self.status_message = (
                f"{call_name}, demo order placed: {self.selected_side} at {entry_price}c. "
                "Watch the demo round settle."
            )
        else:
            self.status_message = (
                f"Nice, {call_name}. Bought {self.selected_side} for ${self.selected_amount} at {entry_price}c. "
                "The 15-second market is now live."
            )

    def _contract_price(self, side: str) -> int:
        return contract_price(self.market, side)

    def _topmost_zone_at(self, x: float, y: float, padding: float = 0.0) -> ClickZone | None:
        for zone in reversed(self.click_zones):
            if zone.contains(x, y, padding=padding):
                return zone
        return None

    def _resolve_click_key(self, x: float, y: float) -> str | None:
        direct_zone = self._topmost_zone_at(x, y)
        if direct_zone is not None:
            return direct_zone.key

        snapped_zone: ClickZone | None = None
        best_distance = CLICK_SNAP_DISTANCE
        for zone in reversed(self.click_zones):
            distance = zone.edge_distance(x, y)
            if distance <= best_distance:
                best_distance = distance
                snapped_zone = zone
        return snapped_zone.key if snapped_zone is not None else None

    def _update_hovered_key(self, x: float, y: float) -> None:
        hovered_zone = self._topmost_zone_at(x, y)
        self.hovered_key = hovered_zone.key if hovered_zone is not None else None

    def _refresh_hovered_key_if_needed(self) -> None:
        if not self._hover_refresh_needed:
            return
        self._update_hovered_key(self.cursor_x, self.cursor_y)
        self._hover_refresh_needed = False

    def _mark_chart_dirty(self) -> None:
        self._chart_prices_dirty = True
        self._chart_geometry_dirty = True

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        del dx, dy
        self.cursor_x = x
        self.cursor_y = y
        self._update_hovered_key(x, y)
        self._hover_refresh_needed = False

    def on_mouse_drag(
        self,
        x: float,
        y: float,
        dx: float,
        dy: float,
        buttons: int,
        modifiers: int,
    ) -> None:
        del dx, dy, buttons, modifiers
        self.cursor_x = x
        self.cursor_y = y
        self._update_hovered_key(x, y)
        self._hover_refresh_needed = False

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        del modifiers
        self.cursor_x = x
        self.cursor_y = y
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        self.cursor_click_flash = 1.0
        clicked_key = self._resolve_click_key(x, y)
        self._update_hovered_key(x, y)
        self._hover_refresh_needed = False

        if clicked_key is None:
            self.amount_input_active = False
            return

        if clicked_key != "amount_input":
            self.amount_input_active = False

        if self.onboarding_active:
            self._handle_onboarding_click(clicked_key)
            return
        if self.tutorial_active:
            if clicked_key == "tutorial_continue":
                self.tutorial_active = False
                self.market_transition = 1.0
                self._start_demo_round()
                self._hover_refresh_needed = True
            return

        if clicked_key == "dashboard_toggle":
            self.dashboard_active = not self.dashboard_active
            self._hover_refresh_needed = True
            return

        if clicked_key == "amount_input" and not self.market.settled and self.position is None:
            self.amount_input_active = True
            if self.demo_round_active:
                self._update_demo_status()
            else:
                self.status_message = "Type the dollar amount, then buy."
            return

        if clicked_key == "new_market":
            if self.demo_round_active and self.market.settled:
                self._finish_demo_round()
            else:
                self.market = self._new_market()
            self._hover_refresh_needed = True
            return

        if self.position is not None:
            self.status_message = f"{self._player_call_name()}, trade is locked. Watch the market settle."
            return

        if clicked_key in ("side_up", "side_down") and not self.market.settled:
            self.selected_side = "Up" if clicked_key == "side_up" else "Down"
            if self.demo_round_active:
                self.demo_side_picked = True
                self._update_demo_status()
            else:
                self.status_message = f"{self.selected_side} selected, {self._player_call_name()}. Choose amount, then buy."
        elif clicked_key == "buy":
            if self.demo_round_active:
                if not self.demo_side_picked or not self.demo_amount_picked:
                    self._update_demo_status()
                    return
            self._buy_position()

    def on_text(self, text: str) -> None:
        if self.onboarding_active and self.onboarding_name_active:
            allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-'."
            for character in text:
                if character.isspace():
                    break
                if character in allowed and len(self.onboarding_name) < MAX_FULL_NAME_CHARS:
                    self.onboarding_name += character
            self.onboarding_message = "Click Start Practice Tutorial when your name is ready."
            return

        if self.amount_input_active and not self.market.settled and self.position is None:
            for character in text:
                if character.isdigit() and len(self.amount_input_text) < MAX_AMOUNT_INPUT_CHARS:
                    self.amount_input_text += character
            self._sync_selected_amount_from_text()
            if self.demo_round_active:
                self._update_demo_status()
            elif self.selected_amount > 0:
                self.status_message = f"Order amount set to ${self.selected_amount}."

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers
        if self.onboarding_active:
            if symbol == arcade.key.BACKSPACE:
                self.onboarding_name = self.onboarding_name[:-1]
                self.onboarding_message = "Type your first name to create a practice identity."
            elif symbol in (arcade.key.ENTER, arcade.key.RETURN):
                self.onboarding_message = "Use the Start Practice Tutorial button to continue."
            elif symbol == arcade.key.TAB:
                self.onboarding_name_active = True
            return

        if self.amount_input_active and not self.market.settled and self.position is None:
            if symbol == arcade.key.BACKSPACE:
                self.amount_input_text = self.amount_input_text[:-1]
                self._sync_selected_amount_from_text()
                if self.demo_round_active:
                    self._update_demo_status()
            elif symbol in (arcade.key.ENTER, arcade.key.RETURN):
                self.amount_input_active = False

    def _handle_onboarding_click(self, clicked_key: str) -> None:
        if clicked_key == "onboard_name":
            self.onboarding_name_active = True
            self.onboarding_message = "Type your first name, like John."
        elif clicked_key == "onboard_start":
            self._finish_onboarding()

    def _finish_onboarding(self) -> None:
        first_name = self.onboarding_name.strip().split()[0] if self.onboarding_name.strip() else ""
        if not first_name:
            self.onboarding_name_active = True
            self.onboarding_message = "Enter your first name first, like John."
            return

        self.player_full_name = first_name
        self.onboarding_name = first_name
        self.onboarding_name_active = False
        self.onboarding_active = False
        self.tutorial_active = True
        self._hover_refresh_needed = True
        self.status_message = "Tutorial opened. The first round will be a guided demo."

    def _player_call_name(self) -> str:
        if not self.player_full_name:
            return "Trader"
        return self.player_full_name

    def _pulse_fraction(self, speed: float = TEXTBOX_PULSE_SPEED) -> float:
        return 0.5 + 0.5 * math.sin(self.cursor_anim_time * speed)

    def _boost_rgb(self, color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
        return tuple(min(255, channel + amount) for channel in color)

    def _is_caret_visible(self) -> bool:
        cycle_pos = self.cursor_anim_time % TEXT_CARET_BLINK_SECONDS
        return cycle_pos < TEXT_CARET_BLINK_SECONDS * TEXT_CARET_VISIBLE_RATIO

    def _draw_textbox_caret(
        self,
        zone: ClickZone,
        text_left: float,
        typed_text: str,
        font_size: int = 16,
        bold: bool = True,
    ) -> None:
        if not self._is_caret_visible():
            return

        del bold
        approx_char_width = max(7.0, font_size * 0.56)
        max_text_width = max(0.0, zone.width - (text_left - zone.left) - 18)
        raw_text_width = len(typed_text) * approx_char_width
        text_width = min(raw_text_width, max_text_width)
        caret_x = min(text_left + text_width + 2.0, zone.right - 14.0)
        caret_bottom = zone.bottom + 11.0
        caret_top = zone.top - 11.0
        arcade.draw_line(caret_x, caret_bottom, caret_x, caret_top, WHITE, 3)
        arcade.draw_line(caret_x + 2.0, caret_bottom, caret_x + 2.0, caret_top, (*WHITE, 140), 1)

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
            ("1", "Enter your first name", "Use your first name for the practice identity."),
            ("2", "Click Start Practice Tutorial", "This opens the guided demo before the real market starts."),
            ("3", "Play the demo round", "The first round uses demo cash and walks you through the clicks."),
        ]
        for index, (number, title, detail) in enumerate(steps):
            y = panel_bottom + 370 - index * 92
            circle_x = panel_left + 70
            circle_y = y + 8
            arcade.draw_circle_filled(circle_x, circle_y, 22, PANEL_SOFT)
            arcade.draw_circle_outline(circle_x, circle_y, 22, BLUE, 2)
            arcade.draw_text(number, circle_x, circle_y, TEXT, 15, bold=True, anchor_x="center", anchor_y="center")
            arcade.draw_text(title, panel_left + 110, y + 18, TEXT, 18, bold=True)
            arcade.draw_text(detail, panel_left + 110, y - 10, MUTED, 13, width=390, multiline=True)

        form_left = panel_left + 570
        form_top = panel_bottom + 372
        arcade.draw_text("Create Practice Identity", form_left, form_top + 74, TEXT, 21, bold=True)
        arcade.draw_text("First Name", form_left, form_top + 38, MUTED, 12, bold=True)

        name_zone = ClickZone("onboard_name", form_left, form_top - 32, 352, 58)
        self.click_zones.append(name_zone)
        name_is_active = self.onboarding_name_active
        name_pulse = self._pulse_fraction()
        name_fill = PANEL_SOFT
        if name_is_active:
            name_fill = self._boost_rgb(PANEL_SOFT, int(4 + 8 * name_pulse))
        elif self.hovered_key == "onboard_name":
            name_fill = (41, 52, 65)

        name_border = BLUE if name_is_active else BORDER
        arcade.draw_lbwh_rectangle_filled(name_zone.left, name_zone.bottom, name_zone.width, name_zone.height, name_fill)
        arcade.draw_lbwh_rectangle_outline(
            name_zone.left,
            name_zone.bottom,
            name_zone.width,
            name_zone.height,
            name_border,
            2 if name_is_active else 1,
        )

        text_left = name_zone.left + 18
        text_y = name_zone.center_y - 8
        if self.onboarding_name:
            name_display = self.onboarding_name
            name_color = TEXT
        else:
            name_display = "Example: John"
            name_color = MUTED_DARK
        arcade.draw_text(name_display, text_left, text_y, name_color, 16, bold=True)
        if name_is_active:
            self._draw_textbox_caret(name_zone, text_left, self.onboarding_name, font_size=16)
            typing_hint_color = ORANGE if self._is_caret_visible() else MUTED
            arcade.draw_text(
                "typing...",
                name_zone.right - 12,
                name_zone.bottom + 7,
                typing_hint_color,
                10,
                bold=True,
                anchor_x="right",
            )

        arcade.draw_text(
            "No password is needed. This tutorial only stores your first name in memory for this run.",
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

        arcade.draw_text("Tutorial: choose, enter, buy", panel_left + 42, panel_bottom + panel_height - 70, TEXT, 31, bold=True)
        arcade.draw_text(
            "This page explains the buttons. After this, the first round is a guided demo with demo cash.",
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
            (amount_button, "$ Amount", PANEL_SOFT),
            (buy_button, "Buy & Start", GREEN_DARK),
        ):
            arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, color)
            arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BORDER, 1)
            arcade.draw_text(label, zone.center_x, zone.center_y + 1, TEXT, 15, bold=True, anchor_x="center", anchor_y="center")

        for index, target in enumerate(TUTORIAL_CLICK_TARGETS):
            text_x = guide_left + 32
            text_y = guide_bottom + 302 - index * 100
            arcade.draw_text(target.button_label, text_x, text_y + 30, BLUE, 12, bold=True)
            arcade.draw_text(target.title, text_x, text_y + 7, TEXT, 16, bold=True)
            arcade.draw_text(target.detail, text_x, text_y - 18, MUTED, 12, width=200, multiline=True)

        continue_zone = ClickZone("tutorial_continue", panel_left + panel_width - 332, panel_bottom + 28, 290, 54)
        self.click_zones.append(continue_zone)
        button_color = GREEN if self.hovered_key == "tutorial_continue" else GREEN_DARK
        arcade.draw_lbwh_rectangle_filled(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, BORDER, 1)
        arcade.draw_text("Start Guided Demo", continue_zone.center_x, continue_zone.center_y + 1, TEXT, 17, bold=True, anchor_x="center", anchor_y="center")

    def _draw_game_cursor(self) -> None:
        is_text_target = self.hovered_key in CURSOR_TEXT_KEYS
        is_click_target = self.hovered_key is not None
        cursor_color = WHITE

        pulse = 1 + 0.035 * math.sin(self.cursor_anim_time * 9)
        outer_radius = (9 if is_click_target else 7) * pulse + self.cursor_click_flash * 1.8
        inner_radius = 2.9 + self.cursor_click_flash * 0.45
        outer_color = cursor_color
        ring_color = cursor_color
        center_color = TEXT

        arcade.draw_circle_outline(self.cursor_x, self.cursor_y, outer_radius, outer_color, border_width=2)
        arcade.draw_circle_outline(
            self.cursor_x,
            self.cursor_y,
            max(outer_radius - 4.0, 4.0),
            ring_color,
            border_width=1,
        )
        arcade.draw_circle_filled(self.cursor_x, self.cursor_y, inner_radius, center_color)

        if is_text_target:
            bar_x = self.cursor_x + 13
            bar_half = 12 + self.cursor_click_flash * 1.6
            arcade.draw_line(bar_x, self.cursor_y - bar_half, bar_x, self.cursor_y + bar_half, ring_color, 2)
        elif is_click_target:
            arcade.draw_text(
                "CLICK",
                self.cursor_x + 16,
                self.cursor_y + 12,
                ring_color,
                10,
                bold=True,
            )

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
        subtitle = "Pick a side, enter an amount, then watch $5 Bitcoin ticks for 15 seconds"
        if self.demo_round_active and self.market.settled:
            subtitle = "Guided demo finished. Your real practice balance did not change."
        elif self.demo_round_active:
            subtitle = "Guided demo round. This uses demo cash, not your real practice balance."
        elif self.market.active:
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

        remaining = int(math.ceil(max(0.0, MARKET_DURATION_SECONDS - self.market.elapsed_seconds)))
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

    def _sample_chart_prices(self) -> list[float]:
        if not self._chart_prices_dirty and self._chart_prices_cache:
            return self._chart_prices_cache

        price_series = list(self.market.history)
        if not price_series:
            self._chart_prices_cache = [self.market.current_price]
            self._chart_prices_dirty = False
            return self._chart_prices_cache

        if len(price_series) <= MAX_CHART_RENDER_POINTS:
            self._chart_prices_cache = price_series
            self._chart_prices_dirty = False
            return self._chart_prices_cache

        last_index = len(price_series) - 1
        stride = last_index / (MAX_CHART_RENDER_POINTS - 1)
        sampled = [price_series[round(index * stride)] for index in range(MAX_CHART_RENDER_POINTS - 1)]
        sampled.append(price_series[-1])
        self._chart_prices_cache = sampled
        self._chart_prices_dirty = False
        return self._chart_prices_cache

    def _chart_geometry(self, left: float, bottom: float, width: float, height: float) -> dict[str, object]:
        dims = (left, bottom, width, height)
        if (
            not self._chart_geometry_dirty
            and self._chart_geometry_cache is not None
            and self._chart_geometry_dims == dims
        ):
            return self._chart_geometry_cache

        prices = self._sample_chart_prices()
        chart_min = min(min(prices), self.market.target_price - 75)
        chart_max = max(max(prices), self.market.target_price + 125)
        padding = max(10, (chart_max - chart_min) * 0.08)
        low = chart_min - padding
        high = chart_max + padding
        span = max(1, high - low)
        chart_right = left + width - 24

        target_y = bottom + ((self.market.target_price - low) / span) * height
        points: list[tuple[float, float]] = []
        step = (width - 46) / max(1, len(prices) - 1)
        for index, price in enumerate(prices):
            x = left + index * step
            y = bottom + ((price - low) / span) * height
            points.append((x, y))

        area_points: list[tuple[float, float]] = []
        if len(points) > 1:
            area_points = [(points[0][0], bottom), *points, (points[-1][0], bottom)]

        geometry: dict[str, object] = {
            "chart_right": chart_right,
            "target_y": target_y,
            "points": points,
            "area_points": area_points,
            "scale_labels": (low, (low + high) / 2, high),
        }
        self._chart_geometry_cache = geometry
        self._chart_geometry_dims = dims
        self._chart_geometry_dirty = False
        return geometry

    def _draw_chart(self, left: float, bottom: float, width: float, height: float) -> None:
        chart_right = left + width - 24
        arcade.draw_lbwh_rectangle_filled(left, bottom, width - 24, height, (12, 16, 20))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width - 24, height, (24, 31, 39), 1)

        for row in range(5):
            y = bottom + row * height / 4
            grid_color = (41, 51, 63) if row in (0, 4) else (27, 35, 44)
            arcade.draw_line(left, y, chart_right, y, grid_color, 1)

        geometry = self._chart_geometry(left, bottom, width, height)
        target_y = float(geometry["target_y"])
        points = geometry["points"]
        area_points = geometry["area_points"]
        scale_labels = geometry["scale_labels"]
        arcade.draw_line(left, target_y, chart_right, target_y, (143, 97, 45), 2)
        arcade.draw_text("Target", left + width - 76, target_y + 8, YELLOW, 11, bold=True)

        if area_points:
            arcade.draw_polygon_filled(area_points, (247, 151, 38, 28))
            arcade.draw_line_strip(points, (247, 151, 38, 80), 7)
            arcade.draw_line_strip(points, ORANGE, 3)
            arcade.draw_circle_filled(points[-1][0], points[-1][1], 5, ORANGE)
            arcade.draw_circle_outline(points[-1][0], points[-1][1], 10, (247, 151, 38, 90), 2)

        for index, value in enumerate(scale_labels):
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
        self._draw_amount_field(left + 26, bottom + height - 282, width - 52, 66)

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
        if self.demo_round_active and self.market.settled:
            button_text = "Start Real Market"
        elif self.demo_round_active:
            button_text = "Buy Demo & Start"
        else:
            button_text = "New Market" if self.market.settled else "Buy & Start"
        arcade.draw_text(button_text, buy_zone.center_x, buy_zone.center_y + 2, TEXT if not buy_disabled else MUTED, 18, bold=True, anchor_x="center", anchor_y="center")

    def _draw_side_button(self, key: str, label: str, price: int, left: float, bottom: float, width: float, height: float) -> None:
        selected = self.selected_side == label
        disabled = self.position is not None or self.market.settled
        zone = ClickZone(key, left, bottom, width, height)
        self.click_zones.append(zone)

        if selected and label == "Up":
            color = GREEN_DARK
        elif selected:
            color = RED_DARK
        elif self.hovered_key == key and not disabled:
            color = PANEL_SOFT
        else:
            color = PANEL_ALT

        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, color)
        selected_outline = GREEN if label == "Up" else RED
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, selected_outline if selected else BORDER, 1)
        text_color = MUTED if disabled and not selected else TEXT
        arcade.draw_text(f"{label} {price}c", left + width / 2, bottom + height / 2 + 2, text_color, 15, bold=True, anchor_x="center", anchor_y="center")

    def _draw_amount_field(self, left: float, bottom: float, width: float, height: float) -> None:
        zone = ClickZone("amount_input", left, bottom, width, height)
        self.click_zones.append(zone)
        disabled = self.position is not None or self.market.settled
        active = self.amount_input_active and not disabled
        show_attention = self._should_flash_amount_field() and not disabled
        pulse = 0.5 + 0.5 * math.sin(self.ui_animation_seconds * 8.8)

        amount_pulse = self._pulse_fraction(speed=9.0)
        if active:
            glow_alpha = int(24 + 32 * amount_pulse)
            arcade.draw_lbwh_rectangle_filled(
                zone.left - 3,
                zone.bottom - 3,
                zone.width + 6,
                zone.height + 6,
                (*BLUE, glow_alpha),
            )

        color = PANEL_SOFT if active else PANEL_ALT
        if self.hovered_key == "amount_input" and not disabled:
            color = (41, 52, 65)
        if active:
            color = self._boost_rgb(PANEL_SOFT, int(5 + 9 * amount_pulse))
        elif show_attention:
            color = self._blend_color(color, PANEL_SOFT, 0.24 + pulse * 0.24)

        border_color = self._boost_rgb(BLUE, int(14 + 20 * amount_pulse)) if active else BORDER
        border_width = 2 if active else 1
        if show_attention and not active:
            border_color = self._blend_color(BLUE, YELLOW, 0.32 + pulse * 0.55)
            border_width = 2 if pulse > 0.28 else 1

        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, border_color, border_width)
        if show_attention and not active:
            outer_color = self._blend_color(BLUE, YELLOW, 0.45 + pulse * 0.35)
            arcade.draw_lbwh_rectangle_outline(
                zone.left - 3,
                zone.bottom - 3,
                zone.width + 6,
                zone.height + 6,
                outer_color,
                1,
            )

        if self.amount_input_text:
            amount_text = f"${self.amount_input_text}"
            amount_color = TEXT if not disabled else MUTED
        elif active:
            amount_text = "$"
            amount_color = MUTED
        else:
            amount_text = "Type dollars"
            amount_color = MUTED

        text_left = zone.left + 18
        arcade.draw_text(amount_text, text_left, zone.center_y + 9, amount_color, 20, bold=True, anchor_y="center")
        if active:
            self._draw_textbox_caret(zone, text_left, amount_text, font_size=20)
            typing_hint_color = ORANGE if self._is_caret_visible() else MUTED
            arcade.draw_text(
                "typing...",
                zone.right - 12,
                zone.bottom + 9,
                typing_hint_color,
                10,
                bold=True,
                anchor_x="right",
            )
        arcade.draw_text("custom stake", zone.left + 18, zone.center_y - 17, MUTED, 10, anchor_y="center")

    def _should_flash_amount_field(self) -> bool:
        if self.market.settled or self.position is not None or self.amount_input_active:
            return False
        return bool(self.selected_side) and self.selected_amount <= 0

    def _blend_color(
        self,
        source: tuple[int, int, int],
        target: tuple[int, int, int],
        amount: float,
    ) -> tuple[int, int, int]:
        mix = max(0.0, min(1.0, amount))
        return tuple(
            int(source[channel] + (target[channel] - source[channel]) * mix)
            for channel in range(3)
        )

    def _draw_position_summary(self, left: float, top: float, width: float) -> None:
        balance_label = "Demo Cash" if self.demo_round_active else f"{self._player_call_name()}'s Balance"
        shown_balance = self.demo_balance if self.demo_round_active else self.balance
        arcade.draw_text(balance_label, left, top, MUTED, 12, bold=True)
        arcade.draw_text(f"${shown_balance:,.2f}", left, top - 28, TEXT, 22, bold=True)
        arcade.draw_text(self.status_message, left, top - 74, MUTED, 11, width=int(width), multiline=True)

        if self.position is None:
            if not self.selected_side:
                arcade.draw_text("Preview", left, top - 120, MUTED, 12, bold=True)
                arcade.draw_text("Pick Up or Down first", left, top - 146, TEXT, 15, bold=True)
                arcade.draw_text("The demo will guide you step by step.", left, top - 168, MUTED, 11)
                return
            if self.selected_amount <= 0:
                arcade.draw_text("Preview", left, top - 120, MUTED, 12, bold=True)
                arcade.draw_text(f"{self.selected_side} selected", left, top - 146, TEXT, 15, bold=True)
                arcade.draw_text("Now type an amount to keep going.", left, top - 168, MUTED, 11)
                return
            price = self._contract_price(self.selected_side)
            shares = self.selected_amount / (price / 100)
            arcade.draw_text("Preview", left, top - 120, MUTED, 12, bold=True)
            arcade.draw_text(f"{self.selected_side}: {price}c per share", left, top - 146, TEXT, 15, bold=True)
            if self.demo_round_active:
                arcade.draw_text(f"Demo only | Max payout ${shares:,.2f}", left, top - 168, MUTED, 11)
            else:
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
        total_width = 900
        gap = 16
        card_width = (total_width - gap * 2) / 3
        card_height = 152

        arcade.draw_text("Bitcoin articles", left, bottom + card_height + 22, TEXT, 17, bold=True)
        article_note = "Optional clues only. You can trade without clicking or reading these cards."
        arcade.draw_text(article_note, left + 180, bottom + card_height + 23, MUTED, 12)
        for index, card in enumerate(self.news_cards):
            card_left = left + index * (card_width + gap)
            self._draw_news_card(card, card_left, bottom, card_width, card_height)

    def _draw_news_card(
        self,
        card: NewsCard,
        left: float,
        bottom: float,
        width: float,
        height: float,
    ) -> None:
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 8, width, 8, BLUE)

        inset = 16
        content_width = int(width - inset * 2)

        arcade.draw_text(card.source, left + inset, bottom + height - 31, MUTED, 9, bold=True)
        arcade.draw_text(
            f"{card.reliability}%",
            left + width - inset,
            bottom + height - 31,
            MUTED,
            10,
            bold=True,
            anchor_x="right",
        )
        arcade.draw_text(
            card.headline,
            left + inset,
            bottom + height / 2 - 4,
            TEXT,
            16,
            bold=True,
            width=content_width,
            align="center",
            multiline=True,
        )

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
            "Choose a side, set your amount, then start the round",
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
