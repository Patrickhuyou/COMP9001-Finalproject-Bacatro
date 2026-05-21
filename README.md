# Bacatro

**Bacatro** is a Pygame roguelike card game inspired by Balatro, but built around Baccarat. The player must beat 6 levels by reaching each chip target before running out of allowed bets.

## How To Run

Install the dependency:

```bash
python3 -m pip install -r requirements.txt
```

Run the game:

```bash
python3 main.py
```

## Gameplay

- Start with 100 chips.
- Choose a bet type and bet amount.
- Reach the target chip amount to clear the current level.
- There are 6 total levels.
- Higher levels give fewer allowed bets.
- If chips reach 0, the run is lost.
- If the level bet limit reaches 0 before the target is reached, the run is lost.
- After clearing a level, choose 1 of 3 evolution cards to upgrade the run.

## Controls

### Home Page

- `Enter`: start a new run
- `L`: open load page
- `Esc`: quit

### In Game

- `1`: bet on Player
- `2`: bet on Banker
- `3`: bet on Tie
- `4`: bet on Player Pair
- `5`: bet on Banker Pair
- `+` / `-`: increase or decrease bet
- `Space`: deal a round
- `S`: open save-slot page
- `L`: open load-slot page
- `H`: return to home page
- `R`: restart run

### Game Over / Victory

- `R`: start a new run
- `H`: return to home page

## Main Features

- Standard Baccarat dealing and third-card rules
- Player, Banker, Tie, Player Pair, and Banker Pair bets
- Live payout panel for Player, Banker, Tie, and Pair odds
- Six-level roguelike structure
- Shrinking bet limits at higher levels
- Common, Rare, and Epic evolution cards
- Pair-bet upgrades and extra-bet upgrades
- Home page, save/load pages, game-over page, and victory page
- 3-slot JSON save system
- JSON leaderboard output
- Pixel-style generated logo asset

## Evolution Examples

- `Tie Booster`: Tie bets pay 10:1 instead of 8:1.
- `No Commission`: Banker wins pay 1:1 instead of 0.95:1.
- `Pair Primer`: Pair bets pay 12:1.
- `Crowned Twins`: Pair bets pay 18:1.
- `Extra Hand`: gain 1 extra bet each level.
- `Final Reserve`: gain 3 extra bets each level.


## Project Structure

- `main.py`: starts the game
- `ui.py`: Pygame interface, buttons, menus, card drawing, and layout
- `game_state.py`: core run state, betting, payouts, level progression, and win/loss logic
- `cards.py`: `Card`, `Hand`, `Shoe`, and recursive hand-total logic
- `rules.py`: Baccarat third-card rules
- `items.py`: evolution card classes and rarity system
- `storage.py`: save slots and leaderboard file I/O
- `assets/`: generated game logo images
- `requirements.txt`: Python dependency list