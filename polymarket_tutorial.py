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
        "Bitcoin moves higher after buyers return",
        "A positive article can be a clue that Up may become more expensive.",
    ),
    TutorialArticle(
        "Risk Desk",
        "Crypto slips after traders sell the rally",
        "A negative article can be a clue that Down may become more expensive.",
    ),
    TutorialArticle(
        "Ticker Watch",
        "Price stays flat while volume slows",
        "A neutral article means the choice is less obvious, so compare the prices.",
    ),
]

TUTORIAL_CLICK_TARGETS = [
    TutorialClickTarget(
        "Up / Down",
        "Choose a side",
        "Pick the outcome you think will win.",
    ),
    TutorialClickTarget(
        "$ Amount",
        "Choose a stake",
        "Set how much practice cash to risk.",
    ),
    TutorialClickTarget(
        "Buy",
        "Start the market",
        "Place the mock order to make the timer run.",
    ),
]
