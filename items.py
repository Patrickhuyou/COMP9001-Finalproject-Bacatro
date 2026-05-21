from typing import TYPE_CHECKING, Callable, Dict, List, Type

if TYPE_CHECKING:
    from game_state import GameState


def payout_modifier(multiplier: float) -> Callable:
    """Decorator factory used by item effects to modify payout rules."""

    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args, **kwargs) -> int:
            payout = func(self, *args, **kwargs)
            # Only scale winnings; losses and pushes pass through unchanged.
            return int(payout * multiplier) if payout > 0 else payout

        return wrapper

    return decorator


class Item:
    name = "Item"
    description = "No effect."
    rarity = "Common"

    def apply(self, game: "GameState") -> None:
        pass


class NoCommission(Item):
    name = "No Commission"
    description = "Banker wins pay 1:1 instead of 0.95:1."
    rarity = "Rare"

    def apply(self, game: "GameState") -> None:
        game.no_commission = True


class TieBooster(Item):
    name = "Tie Booster"
    description = "Tie bets pay 10:1 instead of 8:1."
    rarity = "Common"

    def apply(self, game: "GameState") -> None:
        game.tie_multiplier = 10


class GoldenShoe(Item):
    name = "Golden Shoe"
    description = "Winning payouts are increased by 10%."
    rarity = "Rare"

    def apply(self, game: "GameState") -> None:
        # Wrap this instance's calculate_payout with the multiplier decorator and
        # rebind it as a bound method so later calls flow through the wrapper.
        original = game.calculate_payout.__func__
        game.calculate_payout = payout_modifier(1.1)(original).__get__(game, type(game))


class ScoutLens(Item):
    name = "Scout Lens"
    description = "Before each round, predicts the statistically safer side."
    rarity = "Common"

    def apply(self, game: "GameState") -> None:
        game.has_scout_lens = True


class CautiousCharm(Item):
    name = "Cautious Charm"
    description = "Player hand draws only on 0-4, changing the normal third-card rule."
    rarity = "Rare"

    def apply(self, game: "GameState") -> None:
        game.rules.player_should_draw = lambda total: total <= 4


class PairPrimer(Item):
    name = "Pair Primer"
    description = "Pair bets pay 12:1 instead of 11:1."
    rarity = "Common"

    def apply(self, game: "GameState") -> None:
        game.pair_multiplier = max(game.pair_multiplier, 12)


class TwinMagnet(Item):
    name = "Twin Magnet"
    description = "Pair bets pay 14:1 instead of 11:1."
    rarity = "Rare"

    def apply(self, game: "GameState") -> None:
        game.pair_multiplier = max(game.pair_multiplier, 14)


class CrownedTwins(Item):
    name = "Crowned Twins"
    description = "Pair bets pay 18:1 instead of 11:1."
    rarity = "Epic"

    def apply(self, game: "GameState") -> None:
        game.pair_multiplier = max(game.pair_multiplier, 18)


class PairInsurance(Item):
    name = "Pair Insurance"
    description = "Losing pair bets refund 40% of the stake."
    rarity = "Epic"

    def apply(self, game: "GameState") -> None:
        game.pair_loss_refund = max(game.pair_loss_refund, 0.4)


class ExtraHand(Item):
    name = "Extra Hand"
    description = "Gain 1 extra bet every level."
    rarity = "Common"

    def apply(self, game: "GameState") -> None:
        game.add_bet_allowance(1)


class LongTable(Item):
    name = "Long Table"
    description = "Gain 2 extra bets every level."
    rarity = "Rare"

    def apply(self, game: "GameState") -> None:
        game.add_bet_allowance(2)


class FinalReserve(Item):
    name = "Final Reserve"
    description = "Gain 3 extra bets every level."
    rarity = "Epic"

    def apply(self, game: "GameState") -> None:
        game.add_bet_allowance(3)


ITEM_POOL: List[Type[Item]] = [
    NoCommission,
    TieBooster,
    GoldenShoe,
    ScoutLens,
    CautiousCharm,
    PairPrimer,
    TwinMagnet,
    CrownedTwins,
    PairInsurance,
    ExtraHand,
    LongTable,
    FinalReserve,
]

RARITY_WEIGHTS: Dict[str, int] = {
    "Common": 60,
    "Rare": 28,
    "Epic": 12,
}
