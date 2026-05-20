"""Simulated Bitcoin Up/Down prediction market built with Python Arcade."""

from __future__ import annotations

import math
from pathlib import Path
import random

import arcade

from .constants import (
    BACKGROUND,
    BLUE,
    BORDER,
    GREEN,
    GREEN_DARK,
    GAME_OVER_BALANCE_THRESHOLD,
    HEADER,
    INSIDER_EAR_UNLOCK_PRICE,
    INSIDER_EAR_WHISPER_PRICE,
    MARKET_DURATION_SECONDS,
    MARKET_TRANSITION_SPEED,
    MAX_NEWS_ARTICLE_PURCHASES,
    MAX_PLAYER_NEWS_ARTICLES,
    MAX_CHART_RENDER_POINTS,
    MAX_AMOUNT_INPUT_CHARS,
    MAX_FRAME_SECONDS,
    MAX_FULL_NAME_CHARS,
    MIN_STAKE_RATIO,
    MUTED,
    MUTED_DARK,
    NEWS_ARTICLE_SHOP_PRICES,
    ORANGE,
    PANEL,
    PANEL_ALT,
    PANEL_SOFT,
    PRICE_TICK_SECONDS,
    RED,
    RED_DARK,
    SAVING_GRACE_SHOP_PRICE,
    SIMULATION_DAYS_LIMIT,
    SKIP_LIMIT,
    STARTING_BALANCE,
    TEXT,
    WHITE,
    WIN_BALANCE_TARGET,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    YELLOW,
)
from .content import (
    ALL_NEWS,
    DEMO_NEWS_CARDS,
    DOWNWARD_BIAS_NEWS,
    SIMPLE_TUTORIAL_ARTICLES,
    TUTORIAL_CLICK_TARGETS,
    UPWARD_BIAS_NEWS,
)
from .market_logic import advance_market_price, build_market, choose_news_cards, contract_price
from .models import ClickZone, MarketState, NewsCard, Position, TradeRecord

CLICK_SNAP_DISTANCE = 12.0
CURSOR_TEXT_KEYS = frozenset({"onboard_name", "amount_input"})
TEXTBOX_PULSE_SPEED = 11.0
TEXT_CARET_BLINK_SECONDS = 0.9
TEXT_CARET_VISIBLE_RATIO = 0.64
PAGE_SWITCH_SPEED = 7.2
RESULT_POPUP_DURATION = 2.4
ISSUE_POPUP_DURATION = 3.2
CHART_SMOOTHING_WINDOW = 5
ALL_IN_GOLD = (214, 167, 49)
ALL_IN_GOLD_HOVER = (236, 190, 74)
ALL_IN_GOLD_DISABLED = (98, 83, 44)
SKIP_RED = (188, 59, 59)
SKIP_RED_HOVER = (226, 78, 78)
SKIP_RED_DISABLED = (96, 47, 47)
SOUNDS_DIR = Path(__file__).resolve().parent.parent / "asset-game" / "sounds"
WIN_SOUND_FILES = ("win_1.wav", "win_2.wav", "win_3.wav")
LOSE_SOUND_FILES = ("lose_1.wav", "lose_2.wav", "lose_3.wav")


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
        self.unlocked_news_cards = 1
        self.news_articles_purchased = 0
        self.skips_remaining = SKIP_LIMIT
        self.saving_grace_owned = False
        self.insider_ear_owned = False
        self.insider_tip_text = "Insider Ear not unlocked yet."
        self.insider_tip_side = ""
        self.insider_tip_confidence = 0
        self.insider_suspicion = 0.0
        self.game_over_active = False
        self.game_won_active = False
        self.game_over_title = "GAME OVER"
        self.game_over_message = (
            f"Your balance dropped below {self._format_money(float(GAME_OVER_BALANCE_THRESHOLD))}."
        )
        self.game_over_hint = "Restart to continue with a fresh $1,000 run."
        self.simulation_days_completed = 0
        self.selected_side = ""
        self.selected_amount = 0
        self.amount_input_text = ""
        self.amount_input_active = False
        self.position_entry_seconds_total = 0
        self.position_entry_seconds_remaining = 0.0
        self.position: Position | None = None
        self.trade_history: list[TradeRecord] = []
        self.dashboard_active = False
        self.shop_active = False
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
        self.result_popup_kind: str | None = None
        self.result_popup_timer = 0.0
        self.result_popup_amount = 0.0
        self.result_popup_side = ""
        self.issue_popup_title = ""
        self.issue_popup_message = ""
        self.issue_popup_timer = 0.0
        self.insider_activation_prompt_active = False
        self._hover_refresh_needed = True
        self._chart_prices_cache: list[float] = []
        self._text_width_cache: dict[tuple[str, int, bool], float] = {}
        self._chart_geometry_cache: dict[str, object] | None = None
        self._chart_geometry_dims: tuple[float, float, float, float] | None = None
        self._chart_geometry_dirty = True
        self._chart_prices_dirty = True
        self.real_market_up_total = 0
        self.real_market_down_total = 0
        self.news_cards = choose_news_cards(ALL_NEWS, count=MAX_PLAYER_NEWS_ARTICLES)
        self.win_sounds = self._load_sound_set(WIN_SOUND_FILES)
        self.lose_sounds = self._load_sound_set(LOSE_SOUND_FILES)
        self.market = self._new_market(track_real_direction=False)
        self.set_mouse_visible(False)

    def _current_page_key(self) -> str:
        if self.onboarding_active:
            return "onboarding"
        if self.tutorial_active:
            return "tutorial"
        if self.shop_active:
            return "shop"
        if self.dashboard_active:
            return "dashboard"
        return "market"

    def _starter_first_news_cards(self, cards: list[NewsCard]) -> list[NewsCard]:
        if not cards:
            return []

        starter_index = max(range(len(cards)), key=lambda index: cards[index].reliability)
        starter = cards[starter_index]
        remaining = [card for index, card in enumerate(cards) if index != starter_index]
        return [starter, *remaining]

    def _max_news_articles_this_round(self) -> int:
        return min(
            MAX_PLAYER_NEWS_ARTICLES,
            1 + MAX_NEWS_ARTICLE_PURCHASES,
            len(self.news_cards),
        )

    def _max_news_purchases_this_round(self) -> int:
        return max(0, self._max_news_articles_this_round() - 1)

    def _position_entry_window_seconds(self) -> int:
        if self.balance >= 7500:
            return 15
        if self.balance >= 5000:
            return 20
        if self.balance >= 3000:
            return 25
        return 30

    def _minimum_order_amount(self, available_balance: float | None = None) -> int:
        if available_balance is None:
            available_balance = self._available_balance()
        return max(1, int(math.ceil(max(0.0, float(available_balance)) * MIN_STAKE_RATIO)))

    def _first_article_locked_by_day(self) -> bool:
        return (
            not self.demo_round_active
            and self.news_articles_purchased == 0
            and self.simulation_days_completed < 1
        )

    def _advance_simulation_day(self) -> None:
        if self.demo_round_active or self.game_over_active or self.game_won_active:
            return
        self.simulation_days_completed = min(
            SIMULATION_DAYS_LIMIT,
            self.simulation_days_completed + 1,
        )

    def _simulation_day_label(self) -> str:
        current_day = min(SIMULATION_DAYS_LIMIT, self.simulation_days_completed + 1)
        return f"Day {current_day}/{SIMULATION_DAYS_LIMIT}"

    def _choose_next_real_market_direction_up(self) -> bool:
        if self.real_market_up_total == self.real_market_down_total:
            return random.random() < 0.5
        return self.real_market_up_total < self.real_market_down_total

    def _handle_position_entry_timeout(self) -> None:
        if self.demo_round_active or self.market.active or self.market.settled or self.position is not None:
            return
        if self.game_over_active or self.game_won_active:
            return

        window_used = self.position_entry_seconds_total
        self.market.active = False
        self.market.settled = True
        self.market.current_price = self.market.resolve_price
        self.market.history.append(self.market.current_price)
        self._mark_chart_dirty()
        self.position_entry_seconds_remaining = 0.0
        self.selected_side = ""
        self.selected_amount = 0
        self.amount_input_text = ""
        self.amount_input_active = False
        penalty = round(float(self.balance) * 0.20, 2)
        self.balance = round(max(0.0, float(self.balance) - penalty), 2)
        self._advance_simulation_day()
        self.status_message = (
            f"{self._player_call_name()}, order window expired after {window_used} seconds. "
            f"No position was placed for this day. "
            f"You lost {self._format_money(penalty)} (20% inactivity penalty)."
        )
        self._trigger_issue_popup(
            "Order Window Expired",
            (
                f"You had {window_used} seconds to place a position. "
                f"Day advanced with no trade, and you lost {self._format_money(penalty)} "
                "(20% of your net worth). Click New Market."
            ),
        )
        self._hover_refresh_needed = True
        self._check_game_loss_state()

    def _next_article_price(self) -> int | None:
        if self.news_articles_purchased >= self._max_news_purchases_this_round():
            return None
        if self.news_articles_purchased >= len(NEWS_ARTICLE_SHOP_PRICES):
            return None
        return NEWS_ARTICLE_SHOP_PRICES[self.news_articles_purchased]

    def _locked_slot_price(self, article_number: int) -> int | None:
        purchase_index = article_number - 2
        if purchase_index < 0 or purchase_index >= len(NEWS_ARTICLE_SHOP_PRICES):
            return None
        return NEWS_ARTICLE_SHOP_PRICES[purchase_index]

    def _new_market(self, demo_mode: bool = False, track_real_direction: bool = True) -> MarketState:
        self.tick_accumulator = 0.0
        self.price_velocity = 0.0
        # Keep click response immediate: do not fade in a post-click transition overlay.
        self.market_transition = 1.0
        self.result_popup_kind = None
        self.result_popup_timer = 0.0
        self.result_popup_amount = 0.0
        self.result_popup_side = ""
        self.insider_activation_prompt_active = False
        self.position_entry_seconds_total = 0
        self.position_entry_seconds_remaining = 0.0
        self._clear_issue_popup()
        self._chart_prices_cache = []
        self._chart_geometry_cache = None
        self._chart_geometry_dims = None
        self._mark_chart_dirty()
        self._hover_refresh_needed = True
        self.position = None
        if demo_mode:
            self.insider_tip_text = "Insider Ear is locked during demo."
            self.insider_tip_side = ""
            self.insider_tip_confidence = 0
        else:
            self.insider_tip_text = "Insider Ear inactive for this market."
            self.insider_tip_side = ""
            self.insider_tip_confidence = 0
            self.insider_suspicion = max(0.0, self.insider_suspicion - 0.08)
        if demo_mode:
            self.selected_side = ""
            self.selected_amount = 0
            self.amount_input_text = ""
            self.amount_input_active = False
            self.news_cards = self._starter_first_news_cards(
                choose_news_cards(DEMO_NEWS_CARDS, count=MAX_PLAYER_NEWS_ARTICLES)
            )
            self.demo_round_complete = False
            self.demo_side_picked = False
            self.demo_amount_picked = False
        else:
            self.selected_side = ""
            self.selected_amount = 0
            self.amount_input_text = ""
            self.amount_input_active = False
            target_up = self._choose_next_real_market_direction_up()
            directional_pool = UPWARD_BIAS_NEWS if target_up else DOWNWARD_BIAS_NEWS
            self.news_cards = self._starter_first_news_cards(
                choose_news_cards(directional_pool, count=MAX_PLAYER_NEWS_ARTICLES)
            )
            if track_real_direction:
                if target_up:
                    self.real_market_up_total += 1
                else:
                    self.real_market_down_total += 1

        if demo_mode:
            self.unlocked_news_cards = min(3, self._max_news_articles_this_round())
            self.news_articles_purchased = max(0, self.unlocked_news_cards - 1)
            self.position_entry_seconds_total = 0
            self.position_entry_seconds_remaining = 0.0
        else:
            self.unlocked_news_cards = 1
            self.news_articles_purchased = 0
            self.position_entry_seconds_total = self._position_entry_window_seconds()
            self.position_entry_seconds_remaining = float(self.position_entry_seconds_total)

        call_name = self._player_call_name()
        if demo_mode:
            self.status_message = (
                f"{call_name}, demo step 1: pick Up or Down. "
                "This round uses demo cash only."
            )
        else:
            self.status_message = (
                f"{call_name}, choose a side, enter an amount, then buy to start the market. "
                f"Minimum stake is {self._format_money(float(self._minimum_order_amount(self.balance)))} (10%). "
                f"You have {self.position_entry_seconds_total} seconds to place this day's position."
            )

        return build_market(self.news_cards)

    def _load_sound_set(self, file_names: tuple[str, ...]) -> list[arcade.Sound]:
        sounds: list[arcade.Sound] = []
        for file_name in file_names:
            sound_path = SOUNDS_DIR / file_name
            try:
                sounds.append(arcade.load_sound(str(sound_path)))
            except Exception:
                continue
        return sounds

    def _play_outcome_sound(self, kind: str) -> None:
        if kind == "win":
            pool = self.win_sounds
        elif kind == "loss":
            pool = self.lose_sounds
        else:
            return
        if not pool:
            return
        try:
            arcade.play_sound(random.choice(pool), volume=0.9)
        except Exception:
            return

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
            f"Now complete {SIMULATION_DAYS_LIMIT} real simulation days and reach "
            f"{self._format_money(float(WIN_BALANCE_TARGET))}. "
            f"You have {self.position_entry_seconds_total} seconds to place this day's position."
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
            minimum_order = self._minimum_order_amount(self.demo_balance)
            self.status_message = (
                f"{call_name}, demo step 2: type a demo amount "
                f"(minimum {self._format_money(float(minimum_order))}, 10%)."
            )
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
        if self.shop_active:
            self._draw_shop()
            self._draw_issue_popup()
            self._draw_insider_activation_confirm_popup()
            self._draw_game_over_overlay()
            self._draw_game_win_overlay()
            self._refresh_hovered_key_if_needed()
            self._draw_game_cursor()
            self._draw_page_transition()
            return
        if self.dashboard_active:
            self._draw_dashboard()
            self._draw_insider_activation_confirm_popup()
            self._draw_game_over_overlay()
            self._draw_game_win_overlay()
            self._refresh_hovered_key_if_needed()
            self._draw_game_cursor()
            self._draw_page_transition()
            return

        self._draw_header()
        self._draw_market()
        self._draw_ticket()
        self._draw_news_cards()
        self._draw_transition_overlay()
        self._draw_result_popup()
        self._draw_issue_popup()
        self._draw_insider_activation_confirm_popup()
        self._draw_game_over_overlay()
        self._draw_game_win_overlay()
        self._refresh_hovered_key_if_needed()
        self._draw_game_cursor()
        self._draw_page_transition()

    def on_update(self, delta_time: float) -> None:
        delta_time = max(0.0, delta_time)
        self.ui_animation_seconds += delta_time
        animation_delta = min(delta_time, MAX_FRAME_SECONDS)
        self.cursor_anim_time += animation_delta
        self.cursor_click_flash = max(0.0, self.cursor_click_flash - animation_delta * 6.0)
        if self.result_popup_kind is not None:
            self.result_popup_timer = max(0.0, self.result_popup_timer - delta_time)
            if self.result_popup_timer <= 0:
                self.result_popup_kind = None
        if self.issue_popup_timer > 0.0:
            self.issue_popup_timer = max(0.0, self.issue_popup_timer - delta_time)
            if self.issue_popup_timer <= 0.0:
                self._clear_issue_popup()
        if self.page_transition_progress < 1.0:
            self.page_transition_progress = min(
                1.0,
                self.page_transition_progress + delta_time * PAGE_SWITCH_SPEED,
            )

        if self.onboarding_active or self.tutorial_active:
            return

        if not self.dashboard_active and not self.shop_active:
            self.market_transition = min(
                1.0,
                self.market_transition + animation_delta * MARKET_TRANSITION_SPEED,
            )

        if (
            not self.demo_round_active
            and not self.market.active
            and not self.market.settled
            and self.position is None
            and self.position_entry_seconds_remaining > 0.0
        ):
            self.position_entry_seconds_remaining = max(0.0, self.position_entry_seconds_remaining - delta_time)
            if self.position_entry_seconds_remaining <= 0.0:
                self._handle_position_entry_timeout()
                return

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
                self._advance_simulation_day()
                self.status_message = f"{call_name}, market settled {winning_side}. No position was opened."
            self._check_game_loss_state()
            return

        payout = round(self.position.shares, 2)
        if self.position.side == winning_side:
            profit_value = round(payout - self.position.amount, 2)
            if self.demo_round_active:
                self.demo_balance += payout
            else:
                self.balance += payout
            self.position.resolved_result = "Won"
            self._trigger_result_popup("win", profit_value, winning_side)
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
            loss_value = -float(self.position.amount)
            self.position.resolved_result = "Lost"
            self._trigger_result_popup("loss", loss_value, winning_side)
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
        self._check_game_loss_state()

    def _trigger_result_popup(self, kind: str, amount: float, winning_side: str) -> None:
        self.result_popup_kind = kind
        self.result_popup_timer = RESULT_POPUP_DURATION
        self.result_popup_amount = amount
        self.result_popup_side = winning_side
        self._play_outcome_sound(kind)

    def _record_trade(self, winning_side: str, profit_loss: float) -> None:
        if self.position is None:
            return

        self._advance_simulation_day()
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

    def _available_balance(self) -> float:
        return self.demo_balance if self.demo_round_active else self.balance

    def _effective_balance_for_loss_check(self) -> float:
        effective_balance = self.balance
        if self.position is not None and self.market.active and not self.market.settled:
            # Count committed stake while a position is still open.
            effective_balance += float(self.position.amount)
        return effective_balance

    def _all_in(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, all-in is disabled in demo. Type a demo amount instead."
            self._trigger_issue_popup(
                "Demo Mode",
                "All In is turned off during the guided demo. Type an amount manually.",
            )
            return
        if self.position is not None:
            self.status_message = f"{call_name}, trade is locked. Watch the market settle."
            self._trigger_issue_popup("Trade Locked", "Trade is locked while this market is active.")
            return
        if self.market.active:
            self.status_message = f"{call_name}, market is already running."
            self._trigger_issue_popup("Market Active", "The round is already live. Wait for settlement first.")
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market."
            self._trigger_issue_popup("Market Settled", "Start a new market before going all-in.")
            return
        if not self.selected_side:
            self.status_message = f"{call_name}, choose a side first. Click Up or Down."
            self._trigger_issue_popup("Pick a Side", "Click Up or Down first, then click All In.")
            return

        stake = int(self._available_balance())
        if stake <= 0:
            self.status_message = f"{call_name}, no cash left to go all-in."
            self._trigger_issue_popup("No Cash Available", "Your available cash is under $1, so all-in is unavailable.")
            return

        self.selected_amount = stake
        self.amount_input_text = str(stake)
        self.amount_input_active = False
        if self.demo_round_active:
            self.demo_amount_picked = True
        self._buy_position()

    def _skip_day(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, skip is disabled in demo. Complete the guided round first."
            self._trigger_issue_popup(
                "Demo Mode",
                "Skip is turned off during the guided demo. Complete this demo round first.",
            )
            return
        if self.position is not None or self.market.active:
            self.status_message = f"{call_name}, you cannot skip while a trade is active."
            self._trigger_issue_popup("Trade Locked", "Wait for this market to settle before skipping the day.")
            return
        if self.skips_remaining <= 0:
            self.status_message = f"{call_name}, no skips left. You only get {SKIP_LIMIT} total."
            self._trigger_issue_popup("No Skips Left", f"You used all {SKIP_LIMIT} skips. Play this market instead.")
            return

        self.skips_remaining -= 1
        self._advance_simulation_day()
        self._check_game_loss_state()
        if self.game_over_active or self.game_won_active:
            self._hover_refresh_needed = True
            return

        self.market = self._new_market(demo_mode=self.demo_round_active)
        if self.demo_round_active:
            self.status_message = (
                f"{call_name}, demo day skipped. New demo market loaded. "
                f"Skips left: {self.skips_remaining}."
            )
        else:
            self.status_message = (
                f"{call_name}, day skipped. New market loaded. "
                f"Skips left: {self.skips_remaining}. {self._simulation_day_label()} is next."
            )
        self._hover_refresh_needed = True

    def _buy_news_article(self) -> None:
        call_name = self._player_call_name()
        max_articles = self._max_news_articles_this_round()
        max_purchases = self._max_news_purchases_this_round()
        next_price = self._next_article_price()
        if self.news_articles_purchased >= max_purchases:
            self.status_message = (
                f"{call_name}, max article purchases reached ({max_purchases})."
            )
            self._trigger_issue_popup(
                "Purchase Limit Reached",
                f"You can buy at most {max_purchases} extra articles this round.",
            )
            return
        if self.unlocked_news_cards >= max_articles:
            self.status_message = (
                f"{call_name}, article cap reached. "
                f"You can only hold {max_articles} articles this round."
            )
            self._trigger_issue_popup(
                "Article Limit Reached",
                f"You already unlocked {self.unlocked_news_cards} of {max_articles} articles.",
            )
            return
        if next_price is None:
            self.status_message = f"{call_name}, no article tiers left to buy."
            self._trigger_issue_popup("Purchase Limit Reached", "No article price tiers remain this round.")
            return
        if self._first_article_locked_by_day():
            self.status_message = (
                f"{call_name}, first article unlock opens after Day 1. "
                "Complete one real simulation first."
            )
            self._trigger_issue_popup(
                "Unlocks After Day 1",
                "Finish one real simulation day before buying your first extra article.",
            )
            return

        available_balance = self._available_balance()
        if available_balance < next_price:
            self.status_message = (
                f"{call_name}, not enough cash for another article. "
                f"Need {self._format_money(float(next_price))}."
            )
            self._trigger_issue_popup(
                "Not Enough Cash",
                (
                    f"Article cost: {self._format_money(float(next_price))}. "
                    f"Available: {self._format_money(available_balance)}."
                ),
            )
            return

        self._clear_issue_popup()
        if self.demo_round_active:
            self.demo_balance -= next_price
        else:
            self.balance -= next_price
        self.unlocked_news_cards += 1
        self.news_articles_purchased += 1
        self.status_message = (
            f"{call_name}, article unlocked for {self._format_money(float(next_price))} "
            f"({self.unlocked_news_cards}/{max_articles}). "
            "More market context is now visible."
        )
        self._check_game_loss_state()

    def _buy_saving_grace(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, Saving Grace can only be bought with real practice cash."
            self._trigger_issue_popup(
                "Demo Mode",
                "Saving Grace is disabled in demo. Start the real market to buy it.",
            )
            return
        if self.saving_grace_owned:
            self.status_message = f"{call_name}, Saving Grace is already armed (1 use)."
            self._trigger_issue_popup(
                "Already Owned",
                "Saving Grace is already armed for one use.",
            )
            return
        if self.balance < SAVING_GRACE_SHOP_PRICE:
            self.status_message = (
                f"{call_name}, not enough cash for Saving Grace. "
                f"Need {self._format_money(float(SAVING_GRACE_SHOP_PRICE))}."
            )
            self._trigger_issue_popup(
                "Not Enough Cash",
                (
                    f"Saving Grace cost: {self._format_money(float(SAVING_GRACE_SHOP_PRICE))}. "
                    f"Available: {self._format_money(self.balance)}."
                ),
            )
            return

        self.balance -= SAVING_GRACE_SHOP_PRICE
        self.saving_grace_owned = True
        self.status_message = (
            f"{call_name}, Saving Grace armed (1 use). "
            "If your balance drops below $100 once, you revive at $1,000 and it is consumed."
        )
        self._trigger_issue_popup(
            "Saving Grace Unlocked",
            "Protection armed for one use. On first trigger below $100, it restores to $1,000 then expires.",
        )
        self._check_game_loss_state()

    def _current_suspicion_label(self) -> str:
        if self.insider_suspicion < 0.25:
            return "Not Suspicious"
        if self.insider_suspicion < 0.5:
            return "Questionable"
        if self.insider_suspicion < 0.75:
            return "Suspicious"
        return "Very Suspicious"

    def _buy_insider_ear(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, Insider Ear is locked in demo."
            self._trigger_issue_popup(
                "Demo Mode",
                "Insider Ear can only be used in the real practice market.",
            )
            return
        if self.insider_ear_owned:
            self.status_message = f"{call_name}, Insider Ear already unlocked."
            self._trigger_issue_popup(
                "Already Owned",
                "Insider Ear is already unlocked. Activate it from the Buy panel when you want to use it.",
            )
            return
        if self.balance < INSIDER_EAR_UNLOCK_PRICE:
            self.status_message = (
                f"{call_name}, not enough cash to unlock Insider Ear. "
                f"Need {self._format_money(float(INSIDER_EAR_UNLOCK_PRICE))}."
            )
            self._trigger_issue_popup(
                "Not Enough Cash",
                (
                    f"Unlock price: {self._format_money(float(INSIDER_EAR_UNLOCK_PRICE))}. "
                    f"Available: {self._format_money(self.balance)}."
                ),
            )
            return

        self.balance -= INSIDER_EAR_UNLOCK_PRICE
        self.insider_ear_owned = True
        self.insider_tip_text = "Insider Ear unlocked. Activate it from the Buy panel when ready."
        self.status_message = (
            f"{call_name}, Insider Ear unlocked. "
            "You can save it for later and activate it before any market."
        )
        self._trigger_issue_popup(
            "Insider Ear Unlocked",
            (
                "Unlocked. Use Activate Insider Ear from the Buy panel to reveal the correct side."
            ),
        )
        self._check_game_loss_state()

    def _request_activate_insider_ear(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, Insider Ear is locked in demo."
            self._trigger_issue_popup(
                "Demo Mode",
                "Insider Ear activation is only available in the real practice market.",
            )
            return
        if not self.insider_ear_owned:
            self.status_message = f"{call_name}, unlock Insider Ear first."
            self._trigger_issue_popup(
                "Locked",
                (
                    "Unlock Insider Ear first for "
                    f"{self._format_money(float(INSIDER_EAR_UNLOCK_PRICE))}."
                ),
            )
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market first."
            self._trigger_issue_popup(
                "Market Settled",
                "Start a new market before activating Insider Ear.",
            )
            return
        if self.market.active or self.position is not None:
            self.status_message = f"{call_name}, you can only activate Insider Ear before the market starts."
            self._trigger_issue_popup(
                "Trade Locked",
                "Activate Insider Ear before you place a trade.",
            )
            return
        if self.insider_tip_side:
            self.status_message = f"{call_name}, Insider Ear is already active for this market."
            self._trigger_issue_popup(
                "Already Active",
                f"The insider already highly smiles upon {self.insider_tip_side} this round.",
            )
            return

        self.insider_activation_prompt_active = True
        self._clear_issue_popup()
        self.status_message = f"{call_name}, confirm Insider Ear activation to reveal the insider call."
        self._hover_refresh_needed = True

    def _resolve_activate_insider_ear(self, confirmed: bool) -> None:
        self.insider_activation_prompt_active = False
        self._hover_refresh_needed = True
        if not confirmed:
            self.status_message = f"{self._player_call_name()}, Insider Ear activation canceled."
            return

        true_side = "Up" if self.market.resolve_price >= self.market.target_price else "Down"
        self.insider_tip_side = true_side
        self.insider_tip_confidence = 99
        self.insider_tip_text = f"Insider highly smiles upon {true_side}. This call is correct."
        self.status_message = (
            f"{self._player_call_name()}, insider highly smiles upon {true_side}. "
            "That call is guaranteed correct for this market."
        )
        self._trigger_issue_popup(
            "Insider Ear Activated",
            f"Insider highly smiles upon {true_side}.",
        )

    def _buy_insider_whisper(self) -> None:
        call_name = self._player_call_name()
        if self.demo_round_active:
            self.status_message = f"{call_name}, insider whispers are disabled in demo."
            self._trigger_issue_popup(
                "Demo Mode",
                "Insider whispers are only available in the real practice market.",
            )
            return
        if not self.insider_ear_owned:
            self.status_message = f"{call_name}, unlock Insider Ear first."
            self._trigger_issue_popup(
                "Locked",
                (
                    "Unlock Insider Ear first for "
                    f"{self._format_money(float(INSIDER_EAR_UNLOCK_PRICE))}."
                ),
            )
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market first."
            self._trigger_issue_popup(
                "Market Settled",
                "Start a new market before buying an insider whisper.",
            )
            return
        if self.balance < INSIDER_EAR_WHISPER_PRICE:
            self.status_message = (
                f"{call_name}, not enough cash for an insider whisper. "
                f"Need {self._format_money(float(INSIDER_EAR_WHISPER_PRICE))}."
            )
            self._trigger_issue_popup(
                "Not Enough Cash",
                (
                    f"Whisper price: {self._format_money(float(INSIDER_EAR_WHISPER_PRICE))}. "
                    f"Available: {self._format_money(self.balance)}."
                ),
            )
            return

        self.balance -= INSIDER_EAR_WHISPER_PRICE

        true_side = "Up" if self.market.resolve_price >= self.market.target_price else "Down"
        hinted_side = true_side
        confidence = 99
        self.insider_tip_side = hinted_side
        self.insider_tip_confidence = confidence

        self.insider_suspicion = min(1.0, self.insider_suspicion + 0.05)
        suspicion_label = self._current_suspicion_label()
        self.insider_tip_text = (
            f"Insider whisper: '{hinted_side}' is favored ({confidence}% confidence). "
            f"Demeanor: {suspicion_label}."
        )
        self.status_message = (
            f"{call_name}, insider whisper purchased: {hinted_side} favored "
            f"({confidence}% confidence). Demeanor is now {suspicion_label.lower()}."
        )
        self._trigger_issue_popup(
            "Insider Whisper Received",
            (
                f"Insider says '{hinted_side}' ({confidence}% confidence). "
                f"Demeanor: {suspicion_label}."
            ),
        )
        self._check_game_loss_state()

    def _check_game_loss_state(self) -> None:
        if self.demo_round_active or self.game_over_active or self.game_won_active:
            return
        # While a position is live, cash is intentionally "in play".
        # Only evaluate loss/win thresholds after the simulation settles.
        if self.market.active:
            return
        if self.balance >= WIN_BALANCE_TARGET:
            self._trigger_game_win()
            return
        if self.simulation_days_completed >= SIMULATION_DAYS_LIMIT:
            self._trigger_game_over(
                title="SIMULATION OVER",
                message=(
                    f"You reached Day {SIMULATION_DAYS_LIMIT} and ended at "
                    f"{self._format_money(self.balance)}."
                ),
                hint=(
                    f"Goal was {self._format_money(float(WIN_BALANCE_TARGET))} in "
                    f"{SIMULATION_DAYS_LIMIT} simulation days."
                ),
            )
            return
        if self._effective_balance_for_loss_check() >= GAME_OVER_BALANCE_THRESHOLD:
            return

        call_name = self._player_call_name()
        if self.saving_grace_owned:
            self.saving_grace_owned = False
            self.balance = STARTING_BALANCE
            self.market = self._new_market()
            self.status_message = (
                f"{call_name}, Saving Grace activated and was consumed. "
                f"Balance restored to {self._format_money(float(STARTING_BALANCE))}."
            )
            self._trigger_issue_popup(
                "Saving Grace Activated",
                (
                    "You dropped below $100, so Saving Grace revived you "
                    f"to {self._format_money(float(STARTING_BALANCE))}. The one-time shield is now used."
                ),
            )
            self._hover_refresh_needed = True
            return

        self._trigger_game_over()

    def _trigger_game_win(self) -> None:
        call_name = self._player_call_name()
        completed_day = max(1, min(SIMULATION_DAYS_LIMIT, self.simulation_days_completed))
        self.game_won_active = True
        self.market.active = False
        self.market.settled = True
        self.position = None
        self.amount_input_active = False
        self.dashboard_active = False
        self.shop_active = False
        self.status_message = (
            f"{call_name}, you reached {self._format_money(float(WIN_BALANCE_TARGET))} "
            f"on Day {completed_day} and won the run."
        )
        self._hover_refresh_needed = True

    def _trigger_game_over(
        self,
        title: str = "GAME OVER",
        message: str | None = None,
        hint: str | None = None,
    ) -> None:
        call_name = self._player_call_name()
        self.game_over_active = True
        self.game_won_active = False
        self.market.active = False
        self.market.settled = True
        self.position = None
        self.amount_input_active = False
        self.dashboard_active = False
        self.shop_active = False
        if message is None:
            message = f"Your balance dropped below {self._format_money(float(GAME_OVER_BALANCE_THRESHOLD))}."
        if hint is None:
            hint = "Restart to continue with a fresh $1,000 run."
        self.game_over_title = title
        self.game_over_message = message
        self.game_over_hint = hint
        self.status_message = (
            f"{call_name}, {title.lower()}. {message}"
        )
        self._hover_refresh_needed = True

    def _restart_after_game_over(self) -> None:
        self.game_over_active = False
        self.game_won_active = False
        self.game_over_title = "GAME OVER"
        self.game_over_message = (
            f"Your balance dropped below {self._format_money(float(GAME_OVER_BALANCE_THRESHOLD))}."
        )
        self.game_over_hint = "Restart to continue with a fresh $1,000 run."
        self.balance = STARTING_BALANCE
        self.demo_balance = STARTING_BALANCE
        self.simulation_days_completed = 0
        self.unlocked_news_cards = 1
        self.news_articles_purchased = 0
        self.skips_remaining = SKIP_LIMIT
        self.saving_grace_owned = False
        self.insider_ear_owned = False
        self.insider_tip_text = "Insider Ear not unlocked yet."
        self.insider_tip_side = ""
        self.insider_tip_confidence = 0
        self.insider_suspicion = 0.0
        self.real_market_up_total = 0
        self.real_market_down_total = 0
        self.trade_history.clear()
        self.market = self._new_market()
        self.status_message = (
            f"{self._player_call_name()}, new run started at "
            f"{self._format_money(float(STARTING_BALANCE))}. "
            f"Goal: {self._format_money(float(WIN_BALANCE_TARGET))} in {SIMULATION_DAYS_LIMIT} simulation days."
        )
        self._clear_issue_popup()
        self._hover_refresh_needed = True

    def _buy_position(self) -> None:
        call_name = self._player_call_name()
        available_balance = self.demo_balance if self.demo_round_active else self.balance
        if self.position is not None:
            self.status_message = f"{call_name}, you already bought this market. Wait for settlement."
            self._trigger_issue_popup("Trade Locked", "You already bought this market. Wait for settlement.")
            return
        if self.market.settled:
            self.status_message = f"{call_name}, this market is settled. Start a new market."
            self._trigger_issue_popup("Market Settled", "This market is settled. Start a new market first.")
            return
        if not self.selected_side:
            self.status_message = f"{call_name}, choose a side first. Click Up or Down."
            self._trigger_issue_popup("Pick a Side", "Click Up or Down first, then click Buy & Start.")
            return
        if self.selected_amount <= 0:
            self.status_message = f"{call_name}, pick a stake first."
            self._trigger_issue_popup("Enter an Amount", "Type a dollar amount before you click Buy & Start.")
            return
        minimum_order = self._minimum_order_amount(available_balance)
        if self.selected_amount < minimum_order:
            self.status_message = (
                f"{call_name}, minimum stake is {self._format_money(float(minimum_order))} "
                "(10% of your current net worth)."
            )
            self._trigger_issue_popup(
                "Minimum Stake Required",
                (
                    f"Your current net worth is {self._format_money(available_balance)}. "
                    f"Place at least {self._format_money(float(minimum_order))}."
                ),
            )
            return
        if self.selected_amount > available_balance:
            self.status_message = (
                f"{call_name}, not enough balance for that order amount. "
                f"Available: {self._format_money(available_balance)}."
            )
            self._trigger_issue_popup(
                "Not Enough Cash",
                (
                    f"Order amount: {self._format_money(float(self.selected_amount))}. "
                    f"Available: {self._format_money(available_balance)}."
                ),
            )
            return

        entry_price = self._contract_price(self.selected_side)
        shares = self.selected_amount / (entry_price / 100)
        self._clear_issue_popup()
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
        self.position_entry_seconds_remaining = 0.0
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
        self._check_game_loss_state()

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

        if self.issue_popup_timer > 0.0:
            self._clear_issue_popup()
            return

        self.cursor_click_flash = 1.0
        clicked_key = self._resolve_click_key(x, y)
        self._update_hovered_key(x, y)
        self._hover_refresh_needed = False

        if self.insider_activation_prompt_active:
            if clicked_key == "insider_confirm_activate":
                self._resolve_activate_insider_ear(True)
            else:
                self._resolve_activate_insider_ear(False)
            return

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
            elif clicked_key == "tutorial_skip_demo":
                self.tutorial_active = False
                self.market_transition = 1.0
                self.demo_round_active = False
                self.demo_round_complete = False
                self.demo_side_picked = False
                self.demo_amount_picked = False
                self.market = self._new_market()
                self.status_message = (
                    f"{self._player_call_name()}, guided demo skipped. "
                    f"You now have {self.position_entry_seconds_total} seconds to place this day's position."
                )
                self._hover_refresh_needed = True
            return

        if self.game_over_active or self.game_won_active:
            if clicked_key == "restart_game":
                self._restart_after_game_over()
            return

        if clicked_key == "dashboard_toggle":
            self.dashboard_active = not self.dashboard_active
            if self.dashboard_active:
                self.shop_active = False
            self._hover_refresh_needed = True
            return

        if clicked_key == "shop_toggle":
            self.shop_active = not self.shop_active
            if self.shop_active:
                self.dashboard_active = False
            self._hover_refresh_needed = True
            return

        if clicked_key == "amount_input" and not self.market.settled and self.position is None:
            self.amount_input_active = True
            if self.demo_round_active:
                self._update_demo_status()
            else:
                minimum_order = self._minimum_order_amount()
                self.status_message = (
                    f"Type the dollar amount, then buy. "
                    f"Minimum is {self._format_money(float(minimum_order))} (10%)."
                )
            return

        if clicked_key == "new_market":
            if self.demo_round_active and self.market.settled:
                self._finish_demo_round()
            else:
                self.market = self._new_market()
            self._hover_refresh_needed = True
            return

        if clicked_key == "all_in":
            self._all_in()
            return

        if clicked_key == "activate_insider_ear":
            self._request_activate_insider_ear()
            return

        if clicked_key == "skip_day":
            self._skip_day()
            return

        if clicked_key == "shop_buy_article":
            self._buy_news_article()
            return

        if clicked_key == "shop_buy_saving_grace":
            self._buy_saving_grace()
            return

        if clicked_key == "shop_buy_insider_ear":
            self._buy_insider_ear()
            return

        if self.position is not None:
            self.status_message = f"{self._player_call_name()}, trade is locked. Watch the market settle."
            self._trigger_issue_popup("Trade Locked", "Trade is locked while this market is active.")
            return

        if clicked_key in ("side_up", "side_down") and not self.market.settled:
            chosen_side = "Up" if clicked_key == "side_up" else "Down"
            if self.selected_side == chosen_side:
                self.selected_side = ""
                if self.demo_round_active:
                    self.demo_side_picked = False
                    self._update_demo_status()
                else:
                    self.status_message = "Side cleared. Click Up or Down to choose a direction."
            else:
                self.selected_side = chosen_side
                if self.demo_round_active:
                    self.demo_side_picked = True
                    self._update_demo_status()
                else:
                    minimum_order = self._minimum_order_amount()
                    self.status_message = (
                        f"{self.selected_side} selected, {self._player_call_name()}. "
                        f"Choose amount, then buy (minimum {self._format_money(float(minimum_order))}, 10%)."
                    )
        elif clicked_key == "buy":
            if self.demo_round_active:
                if not self.demo_side_picked:
                    self._trigger_issue_popup(
                        "Pick a Side",
                        "Click Up or Down before you click Buy & Start.",
                    )
                    self._update_demo_status()
                    return
                if not self.demo_amount_picked:
                    self._trigger_issue_popup(
                        "Enter an Amount",
                        "Type a dollar amount before you click Buy & Start.",
                    )
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
                if self.selected_side:
                    minimum_order = self._minimum_order_amount()
                    self.status_message = (
                        f"Order amount set to ${self.selected_amount}. "
                        f"Minimum right now is {self._format_money(float(minimum_order))} (10%)."
                    )
                else:
                    self.status_message = "Amount set. Now click Up or Down, then Buy & Start."

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
        self.status_message = (
            f"Tutorial opened. Goal: reach {self._format_money(float(WIN_BALANCE_TARGET))} "
            f"in {SIMULATION_DAYS_LIMIT} simulation days. Start with Step 1: click Up or Down."
        )

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

    def _measure_text_width(self, text: str, font_size: int, bold: bool) -> float:
        if not text:
            return 0.0
        key = (text, font_size, bold)
        cached_width = self._text_width_cache.get(key)
        if cached_width is not None:
            return cached_width

        measured_text = arcade.Text(
            text,
            0,
            0,
            TEXT,
            font_size=font_size,
            bold=bold,
        )
        measured_width = float(measured_text.content_width)
        if len(self._text_width_cache) > 320:
            self._text_width_cache.clear()
        self._text_width_cache[key] = measured_width
        return measured_width

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

        max_text_width = max(0.0, zone.width - (text_left - zone.left) - 18)
        raw_text_width = self._measure_text_width(typed_text, font_size, bold)
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
            "Set up a practice identity before your 14-day simulation challenge begins.",
            panel_left + 50,
            panel_bottom + 466,
            MUTED,
            15,
        )

        steps = [
            ("1", "Enter your first name", "Use your first name for the practice identity."),
            ("2", "Click Start Practice Tutorial", "This opens the guided demo before the real market starts."),
            (
                "3",
                "Play the demo round",
                "Then complete 14 real simulation days and try to reach $10,000 by Day 14.",
            ),
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
            f"Hello, {self._player_call_name()}",
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

        arcade.draw_text("Tutorial: click side, set amount, buy", panel_left + 42, panel_bottom + panel_height - 70, TEXT, 31, bold=True)
        arcade.draw_text(
            (
                "Goal: reach $10,000 within 14 days. Follow this order every round: "
                "1) click Up or Down, 2) type amount, 3) click Buy & Start. "
                "Use Skip Demo Round if you want to jump right into real markets."
            ),
            panel_left + 44,
            panel_bottom + panel_height - 106,
            MUTED,
            14,
            width=760,
            multiline=True,
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
        skip_zone = ClickZone("tutorial_skip_demo", panel_left + panel_width - 642, panel_bottom + 28, 290, 54)
        self.click_zones.append(continue_zone)
        self.click_zones.append(skip_zone)
        button_color = GREEN if self.hovered_key == "tutorial_continue" else GREEN_DARK
        skip_color = PANEL_SOFT if self.hovered_key != "tutorial_skip_demo" else BLUE
        arcade.draw_lbwh_rectangle_filled(skip_zone.left, skip_zone.bottom, skip_zone.width, skip_zone.height, skip_color)
        arcade.draw_lbwh_rectangle_outline(skip_zone.left, skip_zone.bottom, skip_zone.width, skip_zone.height, BORDER, 1)
        arcade.draw_text("Skip Demo Round", skip_zone.center_x, skip_zone.center_y + 1, TEXT, 17, bold=True, anchor_x="center", anchor_y="center")
        arcade.draw_lbwh_rectangle_filled(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(continue_zone.left, continue_zone.bottom, continue_zone.width, continue_zone.height, BORDER, 1)
        arcade.draw_text("Start Guided Demo Round", continue_zone.center_x, continue_zone.center_y + 1, TEXT, 17, bold=True, anchor_x="center", anchor_y="center")

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
        arcade.draw_text(
            f"Hello, {self._player_call_name()}",
            WINDOW_WIDTH - 392,
            WINDOW_HEIGHT - 45,
            MUTED,
            13,
            anchor_x="right",
            anchor_y="center",
        )

        self._draw_shop_button("Shop")
        self._draw_dashboard_button("Dashboard")

    def _draw_dashboard_button(self, label: str) -> None:
        zone = ClickZone("dashboard_toggle", WINDOW_WIDTH - 216, WINDOW_HEIGHT - 62, 146, 38)
        self.click_zones.append(zone)
        button_color = BLUE if self.hovered_key == "dashboard_toggle" else PANEL_SOFT
        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BORDER, 1)
        arcade.draw_text(label, zone.center_x, zone.center_y + 1, TEXT, 14, bold=True, anchor_x="center", anchor_y="center")

    def _draw_shop_button(self, label: str) -> None:
        zone = ClickZone("shop_toggle", WINDOW_WIDTH - 374, WINDOW_HEIGHT - 62, 146, 38)
        self.click_zones.append(zone)
        button_color = BLUE if self.hovered_key == "shop_toggle" else PANEL_SOFT
        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, button_color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, BORDER, 1)
        arcade.draw_text(label, zone.center_x, zone.center_y + 1, TEXT, 14, bold=True, anchor_x="center", anchor_y="center")

    def _draw_dashboard(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)
        arcade.draw_text("PolyArcade", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")
        arcade.draw_text(
            f"Hello, {self._player_call_name()}",
            WINDOW_WIDTH - 392,
            WINDOW_HEIGHT - 45,
            MUTED,
            13,
            anchor_x="right",
            anchor_y="center",
        )
        self._draw_shop_button("Shop")
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
            ("Simulation Day", self._simulation_day_label(), TEXT),
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

    def _draw_shop(self) -> None:
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND)
        arcade.draw_lbwh_rectangle_filled(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, 74, HEADER)
        arcade.draw_line(0, WINDOW_HEIGHT - 74, WINDOW_WIDTH, WINDOW_HEIGHT - 74, BORDER, 1)
        arcade.draw_text("PolyArcade", 70, WINDOW_HEIGHT - 45, TEXT, 24, bold=True, anchor_y="center")
        arcade.draw_text("<>", 40, WINDOW_HEIGHT - 45, TEXT, 18, bold=True, anchor_y="center")
        arcade.draw_text(
            f"Hello, {self._player_call_name()}",
            WINDOW_WIDTH - 392,
            WINDOW_HEIGHT - 45,
            MUTED,
            13,
            anchor_x="right",
            anchor_y="center",
        )
        self._draw_shop_button("Back")
        self._draw_dashboard_button("Dashboard")

        panel_left = 96
        panel_bottom = 102
        panel_width = WINDOW_WIDTH - 192
        panel_height = WINDOW_HEIGHT - 226
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom, panel_width, panel_height, PANEL)
        arcade.draw_lbwh_rectangle_outline(panel_left, panel_bottom, panel_width, panel_height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(panel_left, panel_bottom + panel_height - 8, panel_width, 8, BLUE)

        arcade.draw_text("Market Shop", panel_left + 32, panel_bottom + panel_height - 62, TEXT, 34, bold=True)
        mode_text = (
            "Demo shop bundle: 3 articles already unlocked. Saving Grace is locked in demo."
            if self.demo_round_active
            else "Buy extra news articles and one-use protection upgrades. First article opens after Day 1."
        )
        arcade.draw_text(mode_text, panel_left + 34, panel_bottom + panel_height - 96, MUTED, 14)

        max_articles = self._max_news_articles_this_round()
        max_purchases = self._max_news_purchases_this_round()
        unlocked = min(self.unlocked_news_cards, max_articles)
        current_balance = self._available_balance()
        next_price = self._next_article_price()
        first_article_locked = self._first_article_locked_by_day()
        shop_disabled = (
            self.news_articles_purchased >= max_purchases
            or unlocked >= max_articles
            or next_price is None
            or first_article_locked
            or current_balance < next_price
        )

        stat_cards = [
            ("Cash Available", self._format_money(current_balance), TEXT),
            ("Unlocked Articles", f"{unlocked}/{max_articles}", TEXT),
            ("Saving Grace", "Armed (1 use)" if self.saving_grace_owned else "Not Armed", GREEN if self.saving_grace_owned else TEXT),
        ]
        for index, (label, value, value_color) in enumerate(stat_cards):
            card_left = panel_left + 32 + index * 296
            arcade.draw_lbwh_rectangle_filled(card_left, panel_bottom + panel_height - 212, 268, 98, PANEL_ALT)
            arcade.draw_lbwh_rectangle_outline(card_left, panel_bottom + panel_height - 212, 268, 98, BORDER, 1)
            arcade.draw_text(label, card_left + 16, panel_bottom + panel_height - 154, MUTED, 12, bold=True)
            arcade.draw_text(value, card_left + 16, panel_bottom + panel_height - 190, value_color, 24, bold=True)

        buy_zone = ClickZone("shop_buy_article", panel_left + 32, panel_bottom + panel_height - 290, 420, 62)
        self.click_zones.append(buy_zone)
        buy_color = PANEL_SOFT if shop_disabled else GREEN_DARK
        if self.hovered_key == "shop_buy_article" and not shop_disabled:
            buy_color = GREEN
        arcade.draw_lbwh_rectangle_filled(buy_zone.left, buy_zone.bottom, buy_zone.width, buy_zone.height, buy_color)
        arcade.draw_lbwh_rectangle_outline(buy_zone.left, buy_zone.bottom, buy_zone.width, buy_zone.height, BORDER, 1)
        buy_label = (
            f"Buy Article ({self._format_money(float(next_price))})"
            if next_price is not None
            else "Article Limit Reached"
        )
        buy_label_color = TEXT if not shop_disabled else MUTED
        if self.news_articles_purchased >= max_purchases or unlocked >= max_articles or next_price is None:
            buy_label = "Article Limit Reached"
            buy_label_color = MUTED
        elif first_article_locked:
            buy_label = "Unlocks after Day 1"
            buy_label_color = ORANGE
        elif current_balance < next_price:
            shortfall = max(0.0, float(next_price) - current_balance)
            buy_label = f"Need ${int(math.ceil(shortfall)):,} more"
            buy_label_color = ORANGE
        arcade.draw_text(
            buy_label,
            buy_zone.center_x,
            buy_zone.center_y + 2,
            buy_label_color,
            20,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        active_price_tiers = NEWS_ARTICLE_SHOP_PRICES[:max_purchases]
        if not active_price_tiers:
            tier_line = "Price tiers: no article purchases available this round."
        elif len(active_price_tiers) == 1:
            tier_line = f"Price tier: {self._format_money(float(active_price_tiers[0]))}."
        else:
            tier_line = "Price tiers: " + ", then ".join(
                self._format_money(float(price)) for price in active_price_tiers
            ) + "."

        helper_lines = [
            f"Each buy unlocks one new article slot for this round only.",
            f"Starter slot is always the highest-reliability article (80%+).",
            f"Round cap: 1 starter + up to {max_purchases} purchased articles.",
            f"First purchase unlocks after 1 completed simulation day.",
            f"Saving Grace is one-use only per purchase.",
            f"Drop below {self._format_money(float(GAME_OVER_BALANCE_THRESHOLD))} and you lose the run.",
            f"Reach {self._format_money(float(WIN_BALANCE_TARGET))} by Day {SIMULATION_DAYS_LIMIT} to win the run.",
            tier_line,
        ]
        for index, line in enumerate(helper_lines):
            arcade.draw_text(line, panel_left + 34, panel_bottom + panel_height - 346 - index * 26, MUTED, 13)

        feature_gap = 20
        saving_card_left = panel_left + 32
        saving_card_bottom = panel_bottom + 54
        saving_card_width = (panel_width - 64 - feature_gap) / 2
        saving_card_height = 224
        arcade.draw_lbwh_rectangle_filled(saving_card_left, saving_card_bottom, saving_card_width, saving_card_height, PANEL_ALT)
        arcade.draw_lbwh_rectangle_outline(saving_card_left, saving_card_bottom, saving_card_width, saving_card_height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(saving_card_left, saving_card_bottom + saving_card_height - 8, saving_card_width, 8, ORANGE)

        icon_center_x = saving_card_left + 106
        icon_center_y = saving_card_bottom + 116
        self._draw_saving_grace_icon(icon_center_x, icon_center_y, scale=0.85)

        arcade.draw_text("In The Shop: Saving Grace", saving_card_left + 190, saving_card_bottom + 168, TEXT, 24, bold=True)
        arcade.draw_text(
            "One-use only: if real balance drops below $100, it revives you to $1,000 once.",
            saving_card_left + 190,
            saving_card_bottom + 136,
            MUTED,
            13,
        )
        arcade.draw_text(
            f"Price: {self._format_money(float(SAVING_GRACE_SHOP_PRICE))}",
            saving_card_left + 190,
            saving_card_bottom + 104,
            ORANGE,
            15,
            bold=True,
        )

        saving_disabled = self.demo_round_active or self.saving_grace_owned or current_balance < SAVING_GRACE_SHOP_PRICE
        saving_buy_zone = ClickZone(
            "shop_buy_saving_grace",
            saving_card_left + saving_card_width - 296,
            saving_card_bottom + 30,
            260,
            58,
        )
        self.click_zones.append(saving_buy_zone)
        saving_buy_color = PANEL_SOFT if saving_disabled else GREEN_DARK
        if self.hovered_key == "shop_buy_saving_grace" and not saving_disabled:
            saving_buy_color = GREEN
        arcade.draw_lbwh_rectangle_filled(
            saving_buy_zone.left,
            saving_buy_zone.bottom,
            saving_buy_zone.width,
            saving_buy_zone.height,
            saving_buy_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            saving_buy_zone.left,
            saving_buy_zone.bottom,
            saving_buy_zone.width,
            saving_buy_zone.height,
            BORDER,
            1,
        )

        saving_buy_label = "Buy 1-Use Saving Grace"
        saving_buy_label_color = TEXT if not saving_disabled else MUTED
        if self.demo_round_active:
            saving_buy_label = "Locked In Demo"
            saving_buy_label_color = MUTED
        elif self.saving_grace_owned:
            saving_buy_label = "Armed (1 Use)"
            saving_buy_label_color = GREEN
        elif current_balance < SAVING_GRACE_SHOP_PRICE:
            shortfall = max(0.0, float(SAVING_GRACE_SHOP_PRICE) - current_balance)
            saving_buy_label = f"Need ${int(math.ceil(shortfall)):,} more"
            saving_buy_label_color = ORANGE
        arcade.draw_text(
            saving_buy_label,
            saving_buy_zone.center_x,
            saving_buy_zone.center_y + 2,
            saving_buy_label_color,
            15,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        insider_card_left = saving_card_left + saving_card_width + feature_gap
        insider_card_bottom = saving_card_bottom
        insider_card_width = saving_card_width
        insider_card_height = saving_card_height
        insider_purple = (152, 98, 242)
        arcade.draw_lbwh_rectangle_filled(insider_card_left, insider_card_bottom, insider_card_width, insider_card_height, PANEL_ALT)
        arcade.draw_lbwh_rectangle_outline(insider_card_left, insider_card_bottom, insider_card_width, insider_card_height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(insider_card_left, insider_card_bottom + insider_card_height - 8, insider_card_width, 8, insider_purple)

        insider_icon_x = insider_card_left + 78
        insider_icon_y = insider_card_bottom + 118
        self._draw_insider_ear_icon(insider_icon_x, insider_icon_y, scale=0.82)

        arcade.draw_text("Insider Ear", insider_card_left + 158, insider_card_bottom + 170, TEXT, 24, bold=True)
        insider_price_label = (
            f"Unlock: {self._format_money(float(INSIDER_EAR_UNLOCK_PRICE))}"
            if not self.insider_ear_owned
            else "Owned: Activate from Buy panel"
        )
        arcade.draw_text(
            insider_price_label,
            insider_card_left + 158,
            insider_card_bottom + 142,
            insider_purple,
            14,
            bold=True,
        )

        insider_text_box_left = insider_card_left + 152
        insider_text_box_bottom = insider_card_bottom + 72
        insider_text_box_width = insider_card_width - 170
        insider_text_box_height = 62
        arcade.draw_lbwh_rectangle_filled(
            insider_text_box_left,
            insider_text_box_bottom,
            insider_text_box_width,
            insider_text_box_height,
            (20, 27, 36),
        )
        arcade.draw_lbwh_rectangle_outline(
            insider_text_box_left,
            insider_text_box_bottom,
            insider_text_box_width,
            insider_text_box_height,
            BORDER,
            1,
        )
        insider_text = self.insider_tip_text
        if self.demo_round_active:
            insider_text = "Demo mode: Insider Ear is locked."
        elif not self.insider_ear_owned:
            insider_text = "Unlock Insider Ear, then activate it from the Buy panel when needed."
        elif self.insider_tip_side:
            insider_text = f"Activated this market. Insider highly smiles upon {self.insider_tip_side}."
        else:
            insider_text = "Owned and saved. Activate Insider Ear from the Buy panel when ready."
        arcade.draw_text(
            insider_text,
            insider_text_box_left + 10,
            insider_text_box_bottom + insider_text_box_height - 20,
            MUTED,
            11,
            width=int(insider_text_box_width - 16),
            multiline=True,
        )

        suspicion_bar_left = insider_card_left + 152
        suspicion_bar_bottom = insider_card_bottom + 44
        suspicion_bar_width = insider_card_width - 170
        suspicion_bar_height = 12
        arcade.draw_text("Activation Readiness", suspicion_bar_left, suspicion_bar_bottom + 15, MUTED, 11, bold=True)
        arcade.draw_lbwh_rectangle_filled(
            suspicion_bar_left,
            suspicion_bar_bottom,
            suspicion_bar_width,
            suspicion_bar_height,
            (30, 37, 46),
        )
        readiness_progress = 1.0 if self.insider_ear_owned and not self.demo_round_active else 0.0
        suspicion_color = GREEN if readiness_progress > 0 else MUTED_DARK
        arcade.draw_lbwh_rectangle_filled(
            suspicion_bar_left,
            suspicion_bar_bottom,
            suspicion_bar_width * readiness_progress,
            suspicion_bar_height,
            suspicion_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            suspicion_bar_left,
            suspicion_bar_bottom,
            suspicion_bar_width,
            suspicion_bar_height,
            BORDER,
            1,
        )
        arcade.draw_text("Locked", suspicion_bar_left, suspicion_bar_bottom - 15, MUTED_DARK, 10)
        arcade.draw_text("Ready", suspicion_bar_left + suspicion_bar_width, suspicion_bar_bottom - 15, MUTED_DARK, 10, anchor_x="right")
        readiness_label = "Ready"
        if self.demo_round_active:
            readiness_label = "Demo Locked"
        elif not self.insider_ear_owned:
            readiness_label = "Locked"
        elif self.insider_tip_side:
            readiness_label = f"Active: {self.insider_tip_side}"
        arcade.draw_text(
            readiness_label,
            suspicion_bar_left + suspicion_bar_width,
            suspicion_bar_bottom + 15,
            MUTED,
            11,
            bold=True,
            anchor_x="right",
        )

        insider_disabled = self.demo_round_active or (
            self.insider_ear_owned or current_balance < INSIDER_EAR_UNLOCK_PRICE
        )
        insider_buy_zone = ClickZone(
            "shop_buy_insider_ear",
            insider_card_left + insider_card_width - 296,
            insider_card_bottom + 30,
            260,
            58,
        )
        self.click_zones.append(insider_buy_zone)
        insider_buy_color = PANEL_SOFT if insider_disabled else GREEN_DARK
        if self.hovered_key == "shop_buy_insider_ear" and not insider_disabled:
            insider_buy_color = GREEN
        arcade.draw_lbwh_rectangle_filled(
            insider_buy_zone.left,
            insider_buy_zone.bottom,
            insider_buy_zone.width,
            insider_buy_zone.height,
            insider_buy_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            insider_buy_zone.left,
            insider_buy_zone.bottom,
            insider_buy_zone.width,
            insider_buy_zone.height,
            BORDER,
            1,
        )
        insider_buy_label = "Unlock Ear"
        insider_buy_label_color = TEXT if not insider_disabled else MUTED
        if self.demo_round_active:
            insider_buy_label = "Locked In Demo"
            insider_buy_label_color = MUTED
        elif self.insider_ear_owned:
            insider_buy_label = "Owned"
            insider_buy_label_color = GREEN
        elif current_balance < INSIDER_EAR_UNLOCK_PRICE:
            shortfall = max(0.0, float(INSIDER_EAR_UNLOCK_PRICE) - current_balance)
            insider_buy_label = f"Need ${int(math.ceil(shortfall)):,} more"
            insider_buy_label_color = ORANGE
        arcade.draw_text(
            insider_buy_label,
            insider_buy_zone.center_x,
            insider_buy_zone.center_y + 1,
            insider_buy_label_color,
            14,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

    def _draw_saving_grace_icon(self, center_x: float, center_y: float, scale: float = 1.0) -> None:
        wing_color = (130, 122, 112)
        wing_shadow = (84, 78, 72)
        heart_color = (188, 66, 59)
        heart_shadow = (120, 44, 40)
        halo_color = (228, 178, 74)

        wing_width = 72 * scale
        wing_height = 46 * scale
        arcade.draw_triangle_filled(
            center_x - 26 * scale,
            center_y + 4 * scale,
            center_x - 26 * scale - wing_width,
            center_y + wing_height,
            center_x - 30 * scale - wing_width * 0.88,
            center_y - wing_height,
            wing_shadow,
        )
        arcade.draw_triangle_filled(
            center_x + 26 * scale,
            center_y + 4 * scale,
            center_x + 26 * scale + wing_width,
            center_y + wing_height,
            center_x + 30 * scale + wing_width * 0.88,
            center_y - wing_height,
            wing_shadow,
        )
        arcade.draw_triangle_filled(
            center_x - 22 * scale,
            center_y + 6 * scale,
            center_x - 22 * scale - wing_width * 0.86,
            center_y + wing_height * 0.8,
            center_x - 24 * scale - wing_width * 0.78,
            center_y - wing_height * 0.84,
            wing_color,
        )
        arcade.draw_triangle_filled(
            center_x + 22 * scale,
            center_y + 6 * scale,
            center_x + 22 * scale + wing_width * 0.86,
            center_y + wing_height * 0.8,
            center_x + 24 * scale + wing_width * 0.78,
            center_y - wing_height * 0.84,
            wing_color,
        )

        arcade.draw_circle_outline(center_x, center_y + 56 * scale, 28 * scale, halo_color, 4)

        arcade.draw_circle_filled(center_x - 16 * scale, center_y + 8 * scale, 17 * scale, heart_shadow)
        arcade.draw_circle_filled(center_x + 16 * scale, center_y + 8 * scale, 17 * scale, heart_shadow)
        arcade.draw_triangle_filled(
            center_x - 32 * scale,
            center_y + 4 * scale,
            center_x + 32 * scale,
            center_y + 4 * scale,
            center_x,
            center_y - 44 * scale,
            heart_shadow,
        )

        arcade.draw_circle_filled(center_x - 14 * scale, center_y + 10 * scale, 14 * scale, heart_color)
        arcade.draw_circle_filled(center_x + 14 * scale, center_y + 10 * scale, 14 * scale, heart_color)
        arcade.draw_triangle_filled(
            center_x - 28 * scale,
            center_y + 6 * scale,
            center_x + 28 * scale,
            center_y + 6 * scale,
            center_x,
            center_y - 38 * scale,
            heart_color,
        )

    def _draw_insider_ear_icon(self, center_x: float, center_y: float, scale: float = 1.0) -> None:
        aura = (142, 94, 238)
        ear_outer = (223, 198, 185)
        ear_inner = (172, 133, 129)
        blood = (136, 38, 42)

        aura_offsets = [
            (-34, 40, 22),
            (30, 36, 20),
            (-40, -12, 24),
            (36, -16, 20),
            (0, -48, 22),
        ]
        for ox, oy, radius in aura_offsets:
            arcade.draw_circle_outline(
                center_x + ox * scale,
                center_y + oy * scale,
                radius * scale,
                aura,
                3,
            )

        outer_shape = [
            (center_x - 42 * scale, center_y + 28 * scale),
            (center_x - 14 * scale, center_y + 58 * scale),
            (center_x + 26 * scale, center_y + 54 * scale),
            (center_x + 44 * scale, center_y + 22 * scale),
            (center_x + 46 * scale, center_y - 16 * scale),
            (center_x + 18 * scale, center_y - 62 * scale),
            (center_x - 18 * scale, center_y - 66 * scale),
            (center_x - 40 * scale, center_y - 34 * scale),
            (center_x - 44 * scale, center_y - 4 * scale),
        ]
        inner_shape = [
            (center_x - 18 * scale, center_y + 24 * scale),
            (center_x + 10 * scale, center_y + 30 * scale),
            (center_x + 22 * scale, center_y + 12 * scale),
            (center_x + 20 * scale, center_y - 14 * scale),
            (center_x + 6 * scale, center_y - 42 * scale),
            (center_x - 14 * scale, center_y - 44 * scale),
            (center_x - 24 * scale, center_y - 18 * scale),
            (center_x - 24 * scale, center_y + 2 * scale),
        ]
        arcade.draw_polygon_filled(outer_shape, ear_outer)
        arcade.draw_polygon_filled(inner_shape, ear_inner)
        arcade.draw_line_strip(outer_shape + [outer_shape[0]], (112, 82, 77), 2)
        arcade.draw_line_strip(inner_shape + [inner_shape[0]], (101, 73, 70), 2)

        arcade.draw_triangle_filled(
            center_x - 16 * scale,
            center_y - 66 * scale,
            center_x + 12 * scale,
            center_y - 66 * scale,
            center_x - 4 * scale,
            center_y - 94 * scale,
            blood,
        )

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
        if not self.demo_round_active:
            arcade.draw_text(
                f"{self._simulation_day_label()} | Goal: {self._format_money(float(WIN_BALANCE_TARGET))} by Day {SIMULATION_DAYS_LIMIT}",
                left + 88,
                bottom + height - 84,
                MUTED,
                11,
                bold=True,
            )
        if self.demo_round_active:
            demo_banner_left = left + 88
            demo_banner_bottom = bottom + height - 96
            demo_banner_width = 540
            demo_banner_height = 22
            arcade.draw_lbwh_rectangle_filled(
                demo_banner_left,
                demo_banner_bottom,
                demo_banner_width,
                demo_banner_height,
                (60, 40, 14),
            )
            arcade.draw_lbwh_rectangle_outline(
                demo_banner_left,
                demo_banner_bottom,
                demo_banner_width,
                demo_banner_height,
                ORANGE,
                1,
            )
            arcade.draw_text(
                "DEMO ROUND ONLY - uses demo cash, no real practice balance impact",
                demo_banner_left + 10,
                demo_banner_bottom + 5,
                TEXT,
                10,
                bold=True,
            )

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
            if not self.demo_round_active and self.position is None and self.position_entry_seconds_remaining > 0.0:
                place_seconds = int(math.ceil(self.position_entry_seconds_remaining))
                place_color = RED if place_seconds <= 5 else YELLOW
                arcade.draw_text(
                    f"{place_seconds:02d}S TO ENTER",
                    left + width - 84,
                    stats_y + 15,
                    place_color,
                    12,
                    bold=True,
                    anchor_x="center",
                )
            else:
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

    def _smooth_chart_prices(self, prices: list[float]) -> list[float]:
        if len(prices) < 4:
            return prices
        window = CHART_SMOOTHING_WINDOW
        if window <= 1:
            return prices

        radius = window // 2
        smoothed: list[float] = []
        for index in range(len(prices)):
            start = max(0, index - radius)
            end = min(len(prices), index + radius + 1)
            weighted_sum = 0.0
            weight_total = 0.0
            for inner_index in range(start, end):
                distance = abs(inner_index - index)
                weight = float(radius + 1 - distance)
                weighted_sum += prices[inner_index] * weight
                weight_total += weight
            smoothed.append(weighted_sum / weight_total if weight_total else prices[index])
        smoothed[-1] = prices[-1]
        return smoothed

    def _chart_geometry(self, left: float, bottom: float, width: float, height: float) -> dict[str, object]:
        dims = (left, bottom, width, height)
        if (
            not self._chart_geometry_dirty
            and self._chart_geometry_cache is not None
            and self._chart_geometry_dims == dims
        ):
            return self._chart_geometry_cache

        raw_prices = self._sample_chart_prices()
        prices = self._smooth_chart_prices(raw_prices)
        chart_min = min(min(raw_prices), self.market.target_price - 75)
        chart_max = max(max(raw_prices), self.market.target_price + 125)
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
            arcade.draw_line_strip(points, ORANGE, 2)
            arcade.draw_circle_filled(points[-1][0], points[-1][1], 4, ORANGE)
            arcade.draw_circle_outline(points[-1][0], points[-1][1], 8, ORANGE, 1)

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
        ticket_mode_label = "DEMO CASH ONLY" if self.demo_round_active else "One-tap prediction"
        ticket_mode_color = ORANGE if self.demo_round_active else MUTED
        arcade.draw_text(
            ticket_mode_label,
            left + width - 26,
            bottom + height - 33,
            ticket_mode_color,
            12,
            bold=self.demo_round_active,
            anchor_x="right",
            anchor_y="center",
        )
        if not self.demo_round_active and not self.market.active and not self.market.settled and self.position is None:
            place_seconds = int(math.ceil(self.position_entry_seconds_remaining))
            place_color = RED if place_seconds <= 5 else ORANGE
            arcade.draw_text(
                f"Place trade in {place_seconds}s",
                left + 26,
                bottom + height - 66,
                place_color,
                11,
                bold=True,
            )
        if self.demo_round_active:
            demo_ticket_left = left + 26
            demo_ticket_bottom = bottom + height - 82
            demo_ticket_width = width - 52
            demo_ticket_height = 20
            arcade.draw_lbwh_rectangle_filled(
                demo_ticket_left,
                demo_ticket_bottom,
                demo_ticket_width,
                demo_ticket_height,
                (60, 40, 14),
            )
            arcade.draw_lbwh_rectangle_outline(
                demo_ticket_left,
                demo_ticket_bottom,
                demo_ticket_width,
                demo_ticket_height,
                ORANGE,
                1,
            )
            arcade.draw_text(
                "DEMO TRADE - fake cash only",
                demo_ticket_left + demo_ticket_width / 2,
                demo_ticket_bottom + 5,
                TEXT,
                10,
                bold=True,
                anchor_x="center",
            )

        up_price = self._contract_price("Up")
        down_price = self._contract_price("Down")
        side_row_left = left + 26
        side_row_bottom = bottom + height - 140
        side_row_gap = 12
        side_button_width = (width - 52 - side_row_gap * 2) / 3
        side_button_height = 58
        self._draw_side_button(
            "side_up",
            "Up",
            up_price,
            side_row_left,
            side_row_bottom,
            side_button_width,
            side_button_height,
        )
        self._draw_side_button(
            "side_down",
            "Down",
            down_price,
            side_row_left + side_button_width + side_row_gap,
            side_row_bottom,
            side_button_width,
            side_button_height,
        )

        activate_zone = ClickZone(
            "activate_insider_ear",
            side_row_left + (side_button_width + side_row_gap) * 2,
            side_row_bottom,
            side_button_width,
            side_button_height,
        )
        self.click_zones.append(activate_zone)
        activate_disabled = (
            self.demo_round_active
            or not self.insider_ear_owned
            or self.market.active
            or self.market.settled
            or self.position is not None
            or bool(self.insider_tip_side)
        )
        activate_color = (78, 57, 126) if activate_disabled else (116, 76, 188)
        if self.hovered_key == "activate_insider_ear" and not activate_disabled:
            activate_color = (144, 98, 224)
        arcade.draw_lbwh_rectangle_filled(
            activate_zone.left,
            activate_zone.bottom,
            activate_zone.width,
            activate_zone.height,
            activate_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            activate_zone.left,
            activate_zone.bottom,
            activate_zone.width,
            activate_zone.height,
            BORDER,
            1,
        )
        activate_label = "Activate Ear"
        activate_label_color = TEXT if not activate_disabled else MUTED
        if self.demo_round_active:
            activate_label = "Demo Lock"
        elif not self.insider_ear_owned:
            activate_label = "Need Ear"
        elif self.insider_tip_side:
            activate_label = "Ear Active"
            activate_label_color = GREEN
        arcade.draw_text(
            activate_label,
            activate_zone.center_x,
            activate_zone.center_y + 1,
            activate_label_color,
            12,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        insider_hint_text = "Insider Ear locked. Buy it in Shop."
        insider_hint_color = MUTED_DARK
        if self.demo_round_active:
            insider_hint_text = "Insider Ear is disabled during demo."
        elif self.insider_tip_side:
            insider_hint_text = f"Insider highly smiles upon {self.insider_tip_side}."
            insider_hint_color = GREEN if self.insider_tip_side == "Up" else RED
        elif self.insider_ear_owned:
            insider_hint_text = "Insider Ear ready. Click Activate Ear when you want the call."
            insider_hint_color = MUTED
        arcade.draw_text(
            insider_hint_text,
            left + 26,
            side_row_bottom - 22,
            insider_hint_color,
            11,
            bold=True,
            width=int(width - 52),
            multiline=True,
        )

        arcade.draw_text("Order Amount", left + 26, bottom + height - 210, MUTED, 12, bold=True)
        self._draw_amount_field(left + 26, bottom + height - 282, width - 52, 66)

        arcade.draw_line(left + 26, bottom + height - 320, left + width - 26, bottom + height - 320, BORDER, 1)
        self._draw_position_summary(left + 26, bottom + height - 338, width - 52)

        quick_gap = 10
        quick_button_width = (width - 52 - quick_gap) / 2
        quick_button_bottom = bottom + 92
        all_in_zone = ClickZone("all_in", left + 26, quick_button_bottom, quick_button_width, 40)
        skip_zone = ClickZone("skip_day", left + 26 + quick_button_width + quick_gap, quick_button_bottom, quick_button_width, 40)
        self.click_zones.append(all_in_zone)
        self.click_zones.append(skip_zone)

        all_in_disabled = (
            self.demo_round_active
            or self.position is not None
            or self.market.active
            or self.market.settled
            or int(self._available_balance()) <= 0
        )
        skip_disabled = (
            self.demo_round_active
            or self.position is not None
            or self.market.active
            or self.skips_remaining <= 0
        )

        all_in_label = "All In Off" if self.demo_round_active else "All In"
        skip_label = "Skip Off" if self.demo_round_active else f"Skip ({self.skips_remaining})"

        all_in_color = ALL_IN_GOLD_DISABLED if all_in_disabled else ALL_IN_GOLD
        if self.hovered_key == "all_in" and not all_in_disabled:
            all_in_color = ALL_IN_GOLD_HOVER
        arcade.draw_lbwh_rectangle_filled(
            all_in_zone.left,
            all_in_zone.bottom,
            all_in_zone.width,
            all_in_zone.height,
            all_in_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            all_in_zone.left,
            all_in_zone.bottom,
            all_in_zone.width,
            all_in_zone.height,
            BORDER,
            1,
        )
        arcade.draw_text(
            all_in_label,
            all_in_zone.center_x,
            all_in_zone.center_y + 1,
            TEXT if not all_in_disabled else MUTED,
            14,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        skip_color = SKIP_RED_DISABLED if skip_disabled else SKIP_RED
        if self.hovered_key == "skip_day" and not skip_disabled:
            skip_color = SKIP_RED_HOVER
        arcade.draw_lbwh_rectangle_filled(skip_zone.left, skip_zone.bottom, skip_zone.width, skip_zone.height, skip_color)
        arcade.draw_lbwh_rectangle_outline(skip_zone.left, skip_zone.bottom, skip_zone.width, skip_zone.height, BORDER, 1)
        arcade.draw_text(
            skip_label,
            skip_zone.center_x,
            skip_zone.center_y + 1,
            TEXT if not skip_disabled else MUTED,
            14,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

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
        side_font_size = 13 if width < 110 else 15
        arcade.draw_text(
            f"{label} {price}c",
            left + width / 2,
            bottom + height / 2 + 2,
            text_color,
            side_font_size,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

    def _draw_amount_field(self, left: float, bottom: float, width: float, height: float) -> None:
        zone = ClickZone("amount_input", left, bottom, width, height)
        self.click_zones.append(zone)
        disabled = self.position is not None or self.market.settled
        active = self.amount_input_active and not disabled
        show_attention = self._should_flash_amount_field() and not disabled

        amount_pulse = self._pulse_fraction(speed=9.0)

        color = PANEL_SOFT if active else PANEL_ALT
        if self.hovered_key == "amount_input" and not disabled:
            color = (41, 52, 65)
        if active:
            color = self._boost_rgb(PANEL_SOFT, int(3 + 7 * amount_pulse))

        border_color = BLUE if active else BORDER
        border_width = 2 if active else 1
        if show_attention and not active:
            border_color = YELLOW
            border_width = 2

        arcade.draw_lbwh_rectangle_filled(zone.left, zone.bottom, zone.width, zone.height, color)
        arcade.draw_lbwh_rectangle_outline(zone.left, zone.bottom, zone.width, zone.height, border_color, border_width)

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
        minimum_order = self._minimum_order_amount()
        arcade.draw_text(
            f"minimum {self._format_money(float(minimum_order))} (10% net worth)",
            zone.left + 18,
            zone.center_y - 17,
            MUTED,
            10,
            anchor_y="center",
        )

    def _should_flash_amount_field(self) -> bool:
        if self.market.settled or self.position is not None or self.amount_input_active:
            return False
        return bool(self.selected_side) and self.selected_amount <= 0

    def _draw_position_summary(self, left: float, top: float, width: float) -> None:
        balance_label = "DEMO CASH (FAKE MONEY)" if self.demo_round_active else f"{self._player_call_name()}'s Balance"
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
            arcade.draw_text("Preview", left, top - 120, MUTED, 12, bold=True)
            arcade.draw_text(f"{self.selected_side}: {price}c per share", left, top - 146, TEXT, 15, bold=True)
            if self.market.settled or price <= 0:
                arcade.draw_text("Market settled. Click New Market to place another order.", left, top - 168, MUTED, 11)
                return
            shares = self.selected_amount / (price / 100)
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
        card_height = 152
        max_articles = self._max_news_articles_this_round()
        card_width = (total_width - gap * (max_articles - 1)) / max(1, max_articles)

        arcade.draw_text("Bitcoin articles", left, bottom + card_height + 22, TEXT, 17, bold=True)
        article_note = "Starter article is 80%+ reliability. First extra article unlocks after Day 1 in Shop."
        arcade.draw_text(article_note, left + 180, bottom + card_height + 23, MUTED, 12)

        unlocked = min(self.unlocked_news_cards, max_articles)
        max_purchases = self._max_news_purchases_this_round()
        arcade.draw_text(
            f"Unlocked: {unlocked}/{max_articles}",
            left + total_width - 10,
            bottom + card_height + 26,
            MUTED,
            11,
            bold=True,
            anchor_x="right",
        )
        arcade.draw_text(
            f"Bought: {self.news_articles_purchased}/{max_purchases}",
            left + total_width - 10,
            bottom + card_height + 10,
            MUTED_DARK,
            10,
            bold=True,
            anchor_x="right",
        )
        for index in range(max_articles):
            card_left = left + index * (card_width + gap)
            if index < unlocked:
                self._draw_news_card(self.news_cards[index], card_left, bottom, card_width, card_height)
            else:
                self._draw_locked_news_card(index + 1, card_left, bottom, card_width, card_height)

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
            f"Reliability score = {card.reliability}%",
            left + width - inset,
            bottom + height - 31,
            MUTED,
            9,
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

    def _draw_locked_news_card(
        self,
        article_number: int,
        left: float,
        bottom: float,
        width: float,
        height: float,
    ) -> None:
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL_ALT)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, BORDER, 1)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 8, width, 8, SKIP_RED_DISABLED)
        lock_price = self._locked_slot_price(article_number)
        arcade.draw_text(
            f"Article {article_number} Locked",
            left + width / 2,
            bottom + height / 2 + 20,
            MUTED,
            15,
            bold=True,
            anchor_x="center",
        )
        arcade.draw_text(
            (
                f"Buy from shop for {self._format_money(float(lock_price))}"
                if lock_price is not None
                else "Unlock from shop"
            ),
            left + width / 2,
            bottom + height / 2 - 8,
            MUTED_DARK,
            11,
            bold=True,
            anchor_x="center",
        )
        arcade.draw_text(
            "More clues about likely BTC direction",
            left + width / 2,
            bottom + height / 2 - 30,
            MUTED_DARK,
            10,
            anchor_x="center",
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

    def _draw_result_popup(self) -> None:
        if self.result_popup_kind is None:
            return

        progress = 1.0 - (self.result_popup_timer / RESULT_POPUP_DURATION)
        progress = max(0.0, min(1.0, progress))
        enter_phase = min(1.0, progress / 0.18)
        enter_ease = enter_phase * enter_phase * (3 - 2 * enter_phase)
        exit_phase = max(0.0, (progress - 0.8) / 0.2)
        fade = 1.0 - (exit_phase * exit_phase)
        alpha = int(232 * fade)
        if alpha <= 0:
            return

        is_win = self.result_popup_kind == "win"
        accent = GREEN if is_win else RED
        title = "WIN" if is_win else "LOSS"
        result_line = (
            f"Settled {self.result_popup_side} | {self._format_delta(self.result_popup_amount)}"
            if self.result_popup_side
            else self._format_delta(self.result_popup_amount)
        )

        scale = 0.9 + enter_ease * 0.1
        popup_width = 448 * scale
        popup_height = 158 * scale
        center_x = WINDOW_WIDTH / 2
        center_y = WINDOW_HEIGHT - 186 + math.sin(progress * math.tau * 1.2) * 5 * fade
        shake_x = 0.0
        if not is_win:
            shake_x = math.sin(progress * 90.0) * max(0.0, 1.0 - progress * 2.6) * 6.5
        center_x += shake_x
        left = center_x - popup_width / 2
        bottom = center_y - popup_height / 2

        if is_win:
            confetti_count = 14
            for confetti_index in range(confetti_count):
                lane = (confetti_index * 0.173) % 1.0
                cycle = (progress * 1.3 + confetti_index * 0.09) % 1.0
                confetti_x = left + 26 + (popup_width - 52) * lane
                confetti_x += math.sin(progress * 8.2 + confetti_index * 1.1) * 6.0
                confetti_y = bottom + popup_height + 8 + cycle * 56
                confetti_alpha = int(max(0, 180 - cycle * 145) * fade)
                if confetti_alpha <= 0:
                    continue
                size = 2.4 + (confetti_index % 3) * 0.8
                if confetti_index % 3 == 0:
                    confetti_color = GREEN
                elif confetti_index % 3 == 1:
                    confetti_color = YELLOW
                else:
                    confetti_color = BLUE
                arcade.draw_polygon_filled(
                    (
                        (confetti_x, confetti_y + size),
                        (confetti_x + size, confetti_y),
                        (confetti_x, confetti_y - size),
                        (confetti_x - size, confetti_y),
                    ),
                    (*confetti_color, confetti_alpha),
                )

            badge_radius = 24 * scale
            badge_x = left + popup_width - 42 * scale
            badge_y = bottom + popup_height - 40 * scale
            arcade.draw_circle_filled(badge_x, badge_y, badge_radius, (*GREEN, int(220 * fade)))
            arcade.draw_circle_outline(badge_x, badge_y, badge_radius, (*WHITE, int(220 * fade)), 2)
            check_alpha = int(230 * fade)
            arcade.draw_line(
                badge_x - badge_radius * 0.38,
                badge_y - badge_radius * 0.02,
                badge_x - badge_radius * 0.1,
                badge_y - badge_radius * 0.3,
                (*WHITE, check_alpha),
                3,
            )
            arcade.draw_line(
                badge_x - badge_radius * 0.1,
                badge_y - badge_radius * 0.3,
                badge_x + badge_radius * 0.4,
                badge_y + badge_radius * 0.24,
                (*WHITE, check_alpha),
                3,
            )
        else:
            for streak_index in range(8):
                phase = (streak_index * 0.12 + progress * 1.8) % 1.0
                streak_x = center_x - 160 + streak_index * 45
                streak_top = center_y + 86 - phase * 150
                streak_alpha = int((130 - phase * 100) * fade)
                if streak_alpha <= 0:
                    continue
                arcade.draw_line(
                    streak_x,
                    streak_top,
                    streak_x,
                    streak_top - 22,
                    (*RED, streak_alpha),
                    1,
                )

        arcade.draw_lbwh_rectangle_filled(left, bottom, popup_width, popup_height, (*PANEL, alpha))
        arcade.draw_lbwh_rectangle_outline(left, bottom, popup_width, popup_height, (*accent, alpha), 2)
        arcade.draw_text(
            title,
            left + 20,
            bottom + popup_height - 50,
            (*accent, alpha),
            int(32 * scale),
            bold=True,
        )
        arcade.draw_text(
            result_line,
            left + 22,
            bottom + popup_height - 92,
            (*TEXT, alpha),
            int(16 * scale),
            bold=True,
        )
        subtitle = "Nice call. Click New Market when ready." if is_win else "Tough round. Click New Market to run it back."
        arcade.draw_text(
            subtitle,
            left + 22,
            bottom + 24,
            (*MUTED, alpha),
            int(12 * scale),
        )

    def _draw_insider_activation_confirm_popup(self) -> None:
        if not self.insider_activation_prompt_active:
            return

        left = WINDOW_WIDTH / 2 - 320
        bottom = WINDOW_HEIGHT / 2 - 130
        width = 640
        height = 260
        insider_purple = (152, 98, 242)

        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (4, 8, 12, 165))
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, insider_purple, 2)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 14, width, 14, insider_purple)
        arcade.draw_text("Activate Insider Ear?", left + 24, bottom + height - 54, TEXT, 29, bold=True)
        arcade.draw_text(
            "Confirm to reveal what the insider highly smiles upon for this market.",
            left + 24,
            bottom + height - 96,
            MUTED,
            15,
            width=590,
            multiline=True,
        )

        confirm_zone = ClickZone("insider_confirm_activate", left + 32, bottom + 34, 276, 58)
        cancel_zone = ClickZone("insider_cancel_activate", left + width - 308, bottom + 34, 276, 58)
        self.click_zones.append(confirm_zone)
        self.click_zones.append(cancel_zone)

        confirm_color = GREEN_DARK if self.hovered_key != "insider_confirm_activate" else GREEN
        cancel_color = PANEL_SOFT if self.hovered_key != "insider_cancel_activate" else BLUE
        arcade.draw_lbwh_rectangle_filled(
            confirm_zone.left,
            confirm_zone.bottom,
            confirm_zone.width,
            confirm_zone.height,
            confirm_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            confirm_zone.left,
            confirm_zone.bottom,
            confirm_zone.width,
            confirm_zone.height,
            BORDER,
            1,
        )
        arcade.draw_text(
            "Confirm Activation",
            confirm_zone.center_x,
            confirm_zone.center_y + 2,
            TEXT,
            16,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

        arcade.draw_lbwh_rectangle_filled(
            cancel_zone.left,
            cancel_zone.bottom,
            cancel_zone.width,
            cancel_zone.height,
            cancel_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            cancel_zone.left,
            cancel_zone.bottom,
            cancel_zone.width,
            cancel_zone.height,
            BORDER,
            1,
        )
        arcade.draw_text(
            "Not Now",
            cancel_zone.center_x,
            cancel_zone.center_y + 2,
            TEXT,
            16,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

    def _trigger_issue_popup(self, title: str, message: str) -> None:
        self.issue_popup_title = title
        self.issue_popup_message = message
        self.issue_popup_timer = ISSUE_POPUP_DURATION

    def _clear_issue_popup(self) -> None:
        self.issue_popup_title = ""
        self.issue_popup_message = ""
        self.issue_popup_timer = 0.0

    def _draw_issue_popup(self) -> None:
        if self.issue_popup_timer <= 0.0 or not self.issue_popup_title:
            return

        fade = min(1.0, self.issue_popup_timer / ISSUE_POPUP_DURATION)
        overlay_alpha = int(145 * max(0.45, fade))
        card_alpha = int(242 * max(0.55, fade))
        text_alpha = int(242 * max(0.7, fade))
        left = WINDOW_WIDTH / 2 - 320
        bottom = WINDOW_HEIGHT / 2 - 118
        width = 640
        height = 236

        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (4, 8, 12, overlay_alpha))
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (*PANEL, card_alpha))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, (*ORANGE, card_alpha), 2)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 14, width, 14, (*ORANGE, card_alpha))
        arcade.draw_text(
            self.issue_popup_title,
            left + 24,
            bottom + height - 54,
            (*TEXT, text_alpha),
            27,
            bold=True,
        )
        arcade.draw_text(
            self.issue_popup_message,
            left + 24,
            bottom + height - 96,
            (*TEXT, text_alpha),
            16,
            width=590,
            multiline=True,
        )
        arcade.draw_text(
            "Fix the order details, then try again.",
            left + 24,
            bottom + 34,
            (*MUTED, text_alpha),
            12,
            bold=True,
        )

    def _draw_game_over_overlay(self) -> None:
        if not self.game_over_active:
            return

        pulse = 0.5 + 0.5 * math.sin(self.ui_animation_seconds * 6.0)
        overlay_alpha = 176 + int(28 * pulse)
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (4, 8, 12, overlay_alpha))

        sweep = (self.ui_animation_seconds * 170.0) % 160.0
        streak_alpha = 26 + int(30 * pulse)
        for offset in range(-220, WINDOW_WIDTH + 220, 160):
            streak_x = offset + sweep
            arcade.draw_line(streak_x, WINDOW_HEIGHT, streak_x - 220, 0, (122, 24, 32, streak_alpha), 3)

        left = WINDOW_WIDTH / 2 - 390
        bottom = WINDOW_HEIGHT / 2 - 210
        width = 780
        height = 420
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (15, 21, 29))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, RED, 2)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 16, width, 16, RED)

        skull_x = left + 86
        skull_y = bottom + height - 90
        skull_alpha = 170 + int(60 * pulse)
        bone_color = (232, 236, 240, skull_alpha)
        bone_shadow = (198, 206, 214, min(255, skull_alpha + 6))
        socket_color = (16, 19, 24)

        arcade.draw_circle_filled(skull_x, skull_y - 2, 35, (255, 76, 76, int(48 + 34 * pulse)))
        arcade.draw_circle_outline(skull_x, skull_y - 2, 35, (255, 122, 122, int(88 + 52 * pulse)), 2)

        arcade.draw_ellipse_filled(skull_x, skull_y + 8, 58, 54, bone_color)
        arcade.draw_ellipse_filled(skull_x, skull_y - 15, 40, 27, bone_shadow)
        arcade.draw_ellipse_outline(skull_x, skull_y + 8, 58, 54, (250, 250, 250, min(255, skull_alpha + 20)), 2)
        arcade.draw_ellipse_outline(skull_x, skull_y - 15, 40, 27, (250, 250, 250, min(255, skull_alpha + 20)), 2)

        arcade.draw_ellipse_filled(skull_x - 12, skull_y + 10, 12, 10, socket_color)
        arcade.draw_ellipse_filled(skull_x + 12, skull_y + 10, 12, 10, socket_color)
        arcade.draw_ellipse_outline(skull_x - 12, skull_y + 10, 12, 10, (96, 106, 120), 1)
        arcade.draw_ellipse_outline(skull_x + 12, skull_y + 10, 12, 10, (96, 106, 120), 1)

        arcade.draw_triangle_filled(
            skull_x,
            skull_y - 2,
            skull_x - 5,
            skull_y - 13,
            skull_x + 5,
            skull_y - 13,
            socket_color,
        )

        teeth_left = skull_x - 13
        teeth_bottom = skull_y - 23
        teeth_width = 26
        teeth_height = 10
        arcade.draw_lbwh_rectangle_filled(teeth_left, teeth_bottom, teeth_width, teeth_height, socket_color)
        arcade.draw_lbwh_rectangle_outline(teeth_left, teeth_bottom, teeth_width, teeth_height, (96, 106, 120), 1)
        for notch_x in (teeth_left + 6, teeth_left + 13, teeth_left + 20):
            arcade.draw_line(notch_x, teeth_bottom + 1, notch_x, teeth_bottom + teeth_height - 1, (96, 106, 120), 1)

        arcade.draw_line(skull_x - 22, skull_y + 26, skull_x - 14, skull_y + 16, (198, 206, 214, 180), 2)
        arcade.draw_line(skull_x - 14, skull_y + 16, skull_x - 17, skull_y + 8, (198, 206, 214, 180), 2)

        title_size = 42 if len(self.game_over_title) <= 14 else 34
        arcade.draw_text(self.game_over_title, left + 138, bottom + height - 66, RED, title_size, bold=True)
        arcade.draw_text(
            self.game_over_message,
            left + 140,
            bottom + height - 108,
            TEXT,
            18,
            bold=True,
            width=620,
            multiline=True,
        )
        arcade.draw_text(
            self.game_over_hint,
            left + 140,
            bottom + height - 138,
            MUTED,
            14,
            width=620,
            multiline=True,
        )

        total_trades = len(self.trade_history)
        total_profit = sum(trade.profit_loss for trade in self.trade_history)
        recent_trade = self.trade_history[0] if self.trade_history else None
        recent_trade_line = "Last trade: none recorded this run."
        if recent_trade is not None:
            recent_trade_line = (
                f"Last trade: {recent_trade.side} {self._format_money(float(recent_trade.amount))} "
                f"at {recent_trade.entry_price_cents}c -> {recent_trade.result}"
            )

        stats_left = left + 30
        stats_bottom = bottom + 120
        stats_width = width - 60
        stats_height = 124
        arcade.draw_lbwh_rectangle_filled(stats_left, stats_bottom, stats_width, stats_height, PANEL_ALT)
        arcade.draw_lbwh_rectangle_outline(stats_left, stats_bottom, stats_width, stats_height, BORDER, 1)
        arcade.draw_text(
            f"Final Balance: {self._format_money(self.balance)}",
            stats_left + 18,
            stats_bottom + 88,
            TEXT,
            16,
            bold=True,
        )
        arcade.draw_text(
            f"Run P/L: {self._format_delta(total_profit)}",
            stats_left + 18,
            stats_bottom + 62,
            GREEN if total_profit >= 0 else RED,
            14,
            bold=True,
        )
        arcade.draw_text(
            f"Trades Played: {total_trades}",
            stats_left + 280,
            stats_bottom + 62,
            MUTED,
            14,
            bold=True,
        )
        arcade.draw_text(
            recent_trade_line,
            stats_left + 18,
            stats_bottom + 30,
            MUTED,
            12,
            width=int(stats_width - 32),
            multiline=True,
        )

        restart_zone = ClickZone("restart_game", left + width / 2 - 190, bottom + 36, 380, 64)
        self.click_zones.append(restart_zone)
        restart_color = BLUE if self.hovered_key == "restart_game" else GREEN_DARK
        arcade.draw_lbwh_rectangle_filled(
            restart_zone.left,
            restart_zone.bottom,
            restart_zone.width,
            restart_zone.height,
            restart_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            restart_zone.left,
            restart_zone.bottom,
            restart_zone.width,
            restart_zone.height,
            BORDER,
            1,
        )
        arcade.draw_text(
            "Respawn Run ($1,000)",
            restart_zone.center_x,
            restart_zone.center_y + 2,
            TEXT,
            20,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

    def _draw_game_win_overlay(self) -> None:
        if not self.game_won_active:
            return

        completed_day = max(1, min(SIMULATION_DAYS_LIMIT, self.simulation_days_completed))
        overlay_alpha = 172
        left = WINDOW_WIDTH / 2 - 360
        bottom = WINDOW_HEIGHT / 2 - 180
        width = 720
        height = 360
        arcade.draw_lbwh_rectangle_filled(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, (4, 8, 12, overlay_alpha))
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, PANEL)
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, GREEN, 2)
        arcade.draw_lbwh_rectangle_filled(left, bottom + height - 14, width, 14, GREEN)
        arcade.draw_text("YOU WIN", left + 28, bottom + height - 62, GREEN, 38, bold=True)
        arcade.draw_text(
            f"You reached {self._format_money(float(WIN_BALANCE_TARGET))} by Day {completed_day}.",
            left + 30,
            bottom + height - 108,
            TEXT,
            18,
            bold=True,
        )
        arcade.draw_text(
            "Restart to run it again from $1,000.",
            left + 30,
            bottom + height - 142,
            MUTED,
            14,
        )

        restart_zone = ClickZone("restart_game", left + width / 2 - 170, bottom + 44, 340, 62)
        self.click_zones.append(restart_zone)
        restart_color = BLUE if self.hovered_key == "restart_game" else GREEN_DARK
        arcade.draw_lbwh_rectangle_filled(
            restart_zone.left,
            restart_zone.bottom,
            restart_zone.width,
            restart_zone.height,
            restart_color,
        )
        arcade.draw_lbwh_rectangle_outline(
            restart_zone.left,
            restart_zone.bottom,
            restart_zone.width,
            restart_zone.height,
            BORDER,
            1,
        )
        arcade.draw_text(
            "Play Again",
            restart_zone.center_x,
            restart_zone.center_y + 2,
            TEXT,
            20,
            bold=True,
            anchor_x="center",
            anchor_y="center",
        )

    def _draw_page_transition(self) -> None:
        if self.page_transition_progress >= 1.0:
            return

        eased = self.page_transition_progress ** 0.82
        reveal_x = WINDOW_WIDTH * eased
        cover_width = max(0.0, WINDOW_WIDTH - reveal_x)
        if cover_width <= 0:
            return

        arcade.draw_lbwh_rectangle_filled(reveal_x, 0, cover_width, WINDOW_HEIGHT, HEADER)
        arcade.draw_line(reveal_x, 0, reveal_x, WINDOW_HEIGHT, BLUE, 2)
        trail_x = max(0.0, reveal_x - 16.0)
        arcade.draw_line(trail_x, 0, trail_x, WINDOW_HEIGHT, BORDER, 1)

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
