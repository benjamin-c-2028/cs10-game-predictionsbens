# Collaboration

## Team roles

- One student is the `game.py` owner for the day.
- Everyone else edits only their own `game-yourname.py` file.
- The owner integrates teammate changes into `game.py`.

## Student routine

- Before coding: `git pull`
- After coding: `git push`
- If a merge conflict appears: use AI help to resolve it, then run `python game.py`

## File ownership rules

- Only the owner edits `game.py` directly.
- Every other student edits only their own `game-yourname.py`.
- Every student creates their own file first (example: `game-sally.py`).

## PolyArcade ownership split

For the Bitcoin market game, use these ownership lines:

- `polyarcade/window.py`: UI layout, clicks, onboarding, dashboard
- `polyarcade/market_logic.py`: BTC movement, contract prices, resolve behavior
- `polyarcade/content.py`: article headlines, tutorial words, demo copy
- `polyarcade/constants.py`: colors, spacing, timing, balance defaults
- `polyarcade/models.py`: shared data shapes used across files

If two people need the same file, agree on one owner for that file before editing.

## Team check

After integration, run:

```bash
python game.py
```

If it runs, continue building.
