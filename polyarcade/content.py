"""Shared article and tutorial content for PolyArcade."""

from .models import NewsCard, TutorialArticle, TutorialClickTarget


UPWARD_BIAS_NEWS = [
    NewsCard(
        "Big funds keep buying Bitcoin",
        "Crypto Wire",
        "Big clue",
        91,
        0.82,
    ),
    NewsCard(
        "Miners send less Bitcoin to exchanges",
        "Block Ledger",
        "Flow clue",
        87,
        0.64,
    ),
    NewsCard(
        "Stocks and crypto rise on soft rate talk",
        "Macro Desk",
        "Market clue",
        88,
        0.58,
    ),
    NewsCard(
        "More stablecoin cash hits exchanges",
        "Market Pulse",
        "Cash clue",
        83,
        0.52,
    ),
]

DOWNWARD_BIAS_NEWS = [
    NewsCard(
        "A lot of Bitcoin moves to exchanges",
        "Chain Watch",
        "Big clue",
        92,
        -0.82,
    ),
    NewsCard(
        "A strong dollar hurts crypto",
        "Macro Desk",
        "Market clue",
        86,
        -0.62,
    ),
    NewsCard(
        "Too many traders are crowded on the long side",
        "Derivatives Daily",
        "Risk clue",
        89,
        -0.72,
    ),
    NewsCard(
        "A new rule headline slows crypto buying",
        "Policy Wire",
        "News clue",
        84,
        -0.54,
    ),
]

LOW_BIAS_NEWS = [
    NewsCard(
        "Bitcoin stays in a small range",
        "Ticker Desk",
        "Small clue",
        81,
        0.18,
    ),
    NewsCard(
        "Options traders expect a mixed move",
        "Vol Report",
        "Mixed clue",
        82,
        -0.16,
    ),
    NewsCard(
        "Trading volume looks normal today",
        "Exchange Beat",
        "Small clue",
        81,
        0.14,
    ),
]

ALL_NEWS = UPWARD_BIAS_NEWS + DOWNWARD_BIAS_NEWS + LOW_BIAS_NEWS

DEMO_NEWS_CARDS = [
    NewsCard(
        "Big funds are buying more Bitcoin today",
        "Demo Wire",
        "Demo clue",
        90,
        0.78,
    ),
    NewsCard(
        "Less Bitcoin is going to exchanges",
        "Flow Desk",
        "Demo clue",
        88,
        0.62,
    ),
    NewsCard(
        "Risk markets are moving up today",
        "Market Note",
        "Demo clue",
        85,
        0.42,
    ),
]

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
