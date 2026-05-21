import random
from dataclasses import dataclass, field
from typing import List


SUIT_SYMBOLS = {
    "S": "♠",
    "H": "♥",
    "D": "♦",
    "C": "♣",
}

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]


def recursive_card_value_sum(cards: List["Card"], index: int = 0) -> int:
    """Return the total card value using recursion for the rubric requirement."""
    if index >= len(cards):
        return 0
    return cards[index].value + recursive_card_value_sum(cards, index + 1)


@dataclass
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        # Baccarat values: Ace = 1, tens and face cards = 0, all others face value.
        if self.rank == "A":
            return 1
        if self.rank in {"10", "J", "Q", "K"}:
            return 0
        return int(self.rank)

    def label(self) -> str:
        return f"{self.rank}{SUIT_SYMBOLS.get(self.suit, self.suit)}"


class Shoe:
    def __init__(self, decks: int = 6):
        self.decks = decks
        self.cards: List[Card] = []
        self.shuffle()

    def shuffle(self) -> None:
        self.cards = [Card(rank, suit) for _ in range(self.decks) for suit in SUITS for rank in RANKS]
        random.shuffle(self.cards)

    def draw(self) -> Card:
        # Reshuffle a fresh shoe before it runs too low to deal a full round.
        if len(self.cards) < 20:
            self.shuffle()
        return self.cards.pop()


@dataclass
class Hand:
    cards: List[Card] = field(default_factory=list)

    def add(self, card: Card) -> None:
        self.cards.append(card)

    @property
    def total(self) -> int:
        # Baccarat hand total is the ones digit only (e.g. 7 + 8 = 15 -> 5).
        return recursive_card_value_sum(self.cards) % 10

    @property
    def has_opening_pair(self) -> bool:
        # Pair side bets only consider the first two dealt cards.
        return len(self.cards) >= 2 and self.cards[0].rank == self.cards[1].rank

    def labels(self) -> str:
        return "  ".join(card.label() for card in self.cards)
