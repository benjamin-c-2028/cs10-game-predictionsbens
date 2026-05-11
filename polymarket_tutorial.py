"""Shared tutorial copy for the Polymarket practice games."""

from __future__ import annotations

from dataclasses import dataclass


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


SIMPLE_TUTORIAL_ARTICLES = [
    TutorialArticle(
        "Market Brief",
        "More people are buying Bitcoin today",
        "When buyers show up, price can move up fast.",
    ),
    TutorialArticle(
        "Risk Desk",
        "Some traders are selling after the last jump",
        "When selling grows, price can move down.",
    ),
    TutorialArticle(
        "Ticker Watch",
        "Price is moving slowly right now",
        "A weak clue means you have to think a bit more.",
    ),
]

TUTORIAL_CLICK_TARGETS = [
    TutorialClickTarget(
        "Up / Down",
        "Choose a side",
        "Pick the side you think will win.",
    ),
    TutorialClickTarget(
        "$ Amount",
        "Choose a stake",
        "Pick how much demo cash to use.",
    ),
    TutorialClickTarget(
        "Buy",
        "Start the market",
        "Start the demo round.",
    ),
]
