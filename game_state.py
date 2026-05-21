import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cards import Card, Hand, Shoe
from items import ITEM_POOL, RARITY_WEIGHTS, Item
from rules import BaccaratRules
from storage import DEFAULT_STORAGE


MAX_LEVEL = 6
BASE_BETS_BY_LEVEL = {
    1: 10,
    2: 9,
    3: 8,
    4: 7,
    5: 6,
    6: 5,
}


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass
class RoundResult:
    player: Hand
    banker: Hand
    winner: str
    payout: int
    player_pair: bool
    banker_pair: bool
    narration: List[str]


@dataclass
class GameState:
    chips: int = 100
    level: int = 1
    target: int = 180
    bet: int = 10
    selected_bet: str = "Player"
    inventory: List[str] = field(default_factory=list)
    rules: BaccaratRules = field(default_factory=BaccaratRules)
    shoe: Shoe = field(default_factory=Shoe)
    no_commission: bool = False
    tie_multiplier: int = 8
    pair_multiplier: int = 11
    pair_loss_refund: float = 0.0
    bonus_bets_per_level: int = 0
    bets_remaining: Optional[int] = None
    has_scout_lens: bool = False
    rounds_won: int = 0
    rounds_played: int = 0
    run_cleared: bool = False
    is_game_over: bool = False
    loss_reason: str = ""
    message: str = "Choose a side, set your bet, then press Deal."
    history: List[str] = field(default_factory=list)
    last_result: Optional[RoundResult] = None
    shop_choices: List[Item] = field(default_factory=list)

    def __post_init__(self) -> None:
        # A fresh game starts with the full bet allowance for its current level.
        if self.bets_remaining is None:
            self.bets_remaining = self.level_bet_limit()

    def level_bet_limit(self, level: Optional[int] = None) -> int:
        # Bet limit shrinks with each level; min() guards levels past the table cap.
        current_level = self.level if level is None else level
        return BASE_BETS_BY_LEVEL[min(current_level, MAX_LEVEL)] + self.bonus_bets_per_level

    def add_bet_allowance(self, amount: int) -> None:
        self.bonus_bets_per_level += amount
        self.bets_remaining = int(self.bets_remaining or 0) + amount

    def reset_rule_effects(self) -> None:
        names = list(self.inventory)
        current_bets_remaining = self.bets_remaining
        self.rules = BaccaratRules()
        self.no_commission = False
        self.tie_multiplier = 8
        self.pair_multiplier = 11
        self.pair_loss_refund = 0.0
        self.bonus_bets_per_level = 0
        self.has_scout_lens = False
        self.inventory = []
        for name in names:
            self.add_item_by_name(name)
        self.bets_remaining = current_bets_remaining

    def add_item_by_name(self, name: str) -> None:
        for item_cls in ITEM_POOL:
            if item_cls.name == name:
                item = item_cls()
                self.inventory.append(item.name)
                item.apply(self)
                return

    def offer_items(self) -> None:
        owned = set(self.inventory)
        available = [item_cls for item_cls in ITEM_POOL if item_cls.name not in owned]
        chosen = []
        while available and len(chosen) < 3:
            selected = self.weighted_item_choice(available)
            chosen.append(selected)
            available.remove(selected)
        self.shop_choices = [item_cls() for item_cls in chosen]

    def weighted_item_choice(self, available: List[type]) -> type:
        # Weighted random pick: roll a point along the cumulative rarity weights,
        # so commons (larger weight) come up far more often than epics.
        total_weight = sum(RARITY_WEIGHTS[item_cls.rarity] for item_cls in available)
        roll = random.randint(1, total_weight)
        running_total = 0
        for item_cls in available:
            running_total += RARITY_WEIGHTS[item_cls.rarity]
            if roll <= running_total:
                return item_cls
        return available[-1]

    def choose_item(self, index: int) -> None:
        if 0 <= index < len(self.shop_choices):
            item = self.shop_choices[index]
            self.inventory.append(item.name)
            item.apply(self)
            self.message = f"Added item: {item.name}."
            self.shop_choices = []

    def next_level(self) -> None:
        self.level += 1
        # Target grows steeply each level to keep the run challenging.
        self.target = int(self.target * 1.45 + 50)
        self.bet = clamp(self.bet, 10, self.chips)
        self.bets_remaining = self.level_bet_limit()
        self.offer_items()

    def calculate_payout(
        self,
        bet_choice: str,
        winner: str,
        bet: int,
        player_pair: bool = False,
        banker_pair: bool = False,
    ) -> int:
        # Pair side bets resolve on their own, independent of who wins the hand.
        if bet_choice == "Player Pair":
            return bet * self.pair_multiplier if player_pair else -int(bet * (1 - self.pair_loss_refund))
        if bet_choice == "Banker Pair":
            return bet * self.pair_multiplier if banker_pair else -int(bet * (1 - self.pair_loss_refund))
        if winner == "Tie":
            # On a tie, Player/Banker wagers push (0); only a Tie bet pays out.
            return bet * self.tie_multiplier if bet_choice == "Tie" else 0
        if bet_choice != winner:
            return -bet
        if winner == "Banker" and not self.no_commission:
            # House takes the standard 5% commission on winning Banker bets.
            return int(bet * 0.95)
        return bet

    def scout_hint(self) -> str:
        if not self.has_scout_lens:
            return ""
        banker_edge = random.randint(46, 52)
        player_edge = random.randint(44, 51)
        if banker_edge >= player_edge:
            return f"Scout Lens: Banker looks slightly safer ({banker_edge}%)."
        return f"Scout Lens: Player looks lively ({player_edge}%)."

    def play_round(self) -> RoundResult:
        if self.chips <= 0:
            raise ValueError("You are out of chips.")
        if self.is_game_over:
            raise ValueError("This run is already over.")
        if self.run_cleared:
            raise ValueError("This run is already cleared.")
        if not self.bets_remaining:
            raise ValueError("No bets remaining this level.")
        self.bet = clamp(self.bet, 1, self.chips)
        player = Hand([self.shoe.draw(), self.shoe.draw()])
        banker = Hand([self.shoe.draw(), self.shoe.draw()])
        player_pair = player.has_opening_pair
        banker_pair = banker.has_opening_pair
        narration = [f"Initial totals - Player {player.total}, Banker {banker.total}."]
        if player_pair or banker_pair:
            pair_notes = []
            if player_pair:
                pair_notes.append("Player pair")
            if banker_pair:
                pair_notes.append("Banker pair")
            narration.append(f"Opening pairs - {', '.join(pair_notes)}.")

        player_third = None
        # A "natural" 8 or 9 on either opening hand ends the round with no draws.
        if player.total not in {8, 9} and banker.total not in {8, 9}:
            if self.rules.player_should_draw(player.total):
                card = self.shoe.draw()
                player.add(card)
                player_third = card.value
                narration.append(f"Player draws {card.label()}.")
            else:
                narration.append("Player stands.")

            if self.rules.banker_should_draw(banker.total, player_third):
                card = self.shoe.draw()
                banker.add(card)
                narration.append(f"Banker draws {card.label()}.")
            else:
                narration.append("Banker stands.")
        else:
            narration.append("Natural 8 or 9. No third cards.")

        if player.total > banker.total:
            winner = "Player"
        elif banker.total > player.total:
            winner = "Banker"
        else:
            winner = "Tie"

        payout = self.calculate_payout(self.selected_bet, winner, self.bet, player_pair, banker_pair)
        self.chips += payout
        self.bets_remaining = int(self.bets_remaining) - 1
        self.rounds_played += 1
        if payout > 0:
            self.rounds_won += 1

        result = RoundResult(player, banker, winner, payout, player_pair, banker_pair, narration)
        self.last_result = result
        self.history.insert(0, f"L{self.level} {self.selected_bet} ${self.bet}: {winner} ({payout:+})")
        self.history = self.history[:8]

        if self.chips >= self.target:
            if self.level >= MAX_LEVEL:
                self.run_cleared = True
                self.message = "Run cleared! You beat all 6 levels."
                DEFAULT_STORAGE.add_leaderboard_score(self.chips, self.level, self.rounds_played)
            else:
                self.message = f"Level {self.level} cleared! Choose a new item."
                self.next_level()
        elif self.chips <= 0:
            self.is_game_over = True
            self.loss_reason = "You ran out of chips."
            self.message = "Game over. You ran out of chips."
            DEFAULT_STORAGE.add_leaderboard_score(self.chips, self.level, self.rounds_played)
        elif self.bets_remaining <= 0:
            self.is_game_over = True
            self.loss_reason = "You ran out of bets before reaching the target."
            self.message = "Game over. No bets remaining this level."
            DEFAULT_STORAGE.add_leaderboard_score(self.chips, self.level, self.rounds_played)
        else:
            if self.selected_bet == "Player Pair":
                outcome = "Player pair hits" if player_pair else "Player pair misses"
            elif self.selected_bet == "Banker Pair":
                outcome = "Banker pair hits" if banker_pair else "Banker pair misses"
            else:
                outcome = f"{winner} wins"
            self.message = f"{outcome}. You {'gain' if payout >= 0 else 'lose'} {abs(payout)} chips."
        return result

    def to_dict(self) -> Dict:
        return {
            "chips": self.chips,
            "level": self.level,
            "target": self.target,
            "bet": self.bet,
            "selected_bet": self.selected_bet,
            "inventory": self.inventory,
            "bets_remaining": self.bets_remaining,
            "rounds_won": self.rounds_won,
            "rounds_played": self.rounds_played,
            "run_cleared": self.run_cleared,
            "is_game_over": self.is_game_over,
            "loss_reason": self.loss_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GameState":
        game = cls(
            chips=int(data.get("chips", 100)),
            level=int(data.get("level", 1)),
            target=int(data.get("target", 180)),
            bet=int(data.get("bet", 10)),
            selected_bet=str(data.get("selected_bet", "Player")),
            bets_remaining=data.get("bets_remaining"),
            rounds_won=int(data.get("rounds_won", 0)),
            rounds_played=int(data.get("rounds_played", 0)),
            run_cleared=bool(data.get("run_cleared", False)),
            is_game_over=bool(data.get("is_game_over", False)),
            loss_reason=str(data.get("loss_reason", "")),
        )
        for item_name in data.get("inventory", []):
            game.add_item_by_name(str(item_name))
        if "bets_remaining" in data:
            game.bets_remaining = int(data["bets_remaining"])
        game.message = "Loaded saved run."
        return game
