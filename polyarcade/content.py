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
        "Bitcoin miners are sending less bitcoin to sell",
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
        "More cash is moving into crypto exchanges",
        "Market Pulse",
        "Cash clue",
        83,
        0.52,
    ),
    NewsCard(
        "Big investors keep adding money for a third day",
        "ETF Monitor",
        "Flow clue",
        89,
        0.68,
    ),
    NewsCard(
        "Traders betting against bitcoin are backing off",
        "Derivatives Desk",
        "Risk clue",
        86,
        0.55,
    ),
    NewsCard(
        "Big bitcoin holders buy more after a dip",
        "Chain Scope",
        "Whale clue",
        88,
        0.63,
    ),
    NewsCard(
        "Interest-rate news sounds easier for crypto",
        "Policy Note",
        "Macro clue",
        84,
        0.47,
    ),
    NewsCard(
        "There is less bitcoin sitting on exchanges",
        "Reserve Watch",
        "Supply clue",
        90,
        0.71,
    ),
    NewsCard(
        "Stronger stock markets are helping crypto",
        "Cross Asset Wire",
        "Market clue",
        85,
        0.44,
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
        "A stronger U.S. dollar is hurting crypto",
        "Macro Desk",
        "Market clue",
        86,
        -0.62,
    ),
    NewsCard(
        "Too many traders are betting bitcoin will go up",
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
    NewsCard(
        "Bitcoin miners are moving more coins to sell",
        "Miner Flow",
        "Supply clue",
        88,
        -0.68,
    ),
    NewsCard(
        "Big investors are pulling money out of bitcoin funds",
        "ETF Monitor",
        "Flow clue",
        87,
        -0.61,
    ),
    NewsCard(
        "Risky 'price will go up' bets are getting too crowded",
        "Perp Signal",
        "Risk clue",
        90,
        -0.73,
    ),
    NewsCard(
        "Higher interest rates are putting pressure on crypto",
        "Macro Desk",
        "Macro clue",
        85,
        -0.49,
    ),
    NewsCard(
        "A big exchange shows many more sellers than buyers",
        "Order Book Live",
        "Market clue",
        86,
        -0.57,
    ),
    NewsCard(
        "People are cashing out stablecoins, leaving less buying money",
        "Liquidity Wire",
        "Cash clue",
        84,
        -0.46,
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
        "Traders are split on whether bitcoin goes up or down",
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
    NewsCard(
        "Bitcoin keeps bouncing with no clear direction",
        "Chop Watch",
        "Mixed clue",
        80,
        0.09,
    ),
    NewsCard(
        "Big wallets look steady with no major surprise moves",
        "Chain Pulse",
        "Small clue",
        79,
        -0.08,
    ),
    NewsCard(
        "Market signals look balanced right now",
        "Vol Report",
        "Mixed clue",
        82,
        0.06,
    ),
    NewsCard(
        "Buying and selling look even across regions",
        "Flow Desk",
        "Small clue",
        78,
        -0.05,
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
        "Strong buying pressure is building",
        "A strong buy clue leans Up, but it is never guaranteed.",
    ),
    TutorialArticle(
        "Risk Desk",
        "Sellers are still active after the last jump",
        "Mixed clues mean you should size your stake carefully.",
    ),
    TutorialArticle(
        "Ticker Watch",
        "Short rounds move fast once Buy starts",
        "Pick side first, then amount, then click Buy & Start.",
    ),
]

TUTORIAL_CLICK_TARGETS = [
    TutorialClickTarget(
        "Up / Down",
        "Pick direction first",
        "You must click Up or Down before an order can place.",
    ),
    TutorialClickTarget(
        "$ Amount",
        "Choose a stake",
        "Type how much demo cash to risk on this round.",
    ),
    TutorialClickTarget(
        "Buy",
        "Launch the round",
        "Buy & Start opens the 15-second market timer. If you wait too long before buying, the trade clock can expire.",
    ),
]
