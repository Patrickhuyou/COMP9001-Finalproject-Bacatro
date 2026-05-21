import json
from pathlib import Path
from typing import Dict, List, Optional


SAVES_FILE = Path("saves.json")
LEADERBOARD_FILE = Path("leaderboard.json")
SAVE_SLOT_COUNT = 3


def score_key(entry: Dict) -> tuple:
    return (int(entry.get("level", 0)), int(entry.get("chips", 0)))


def recursive_insert_score(scores: List[Dict], entry: Dict, index: int = 0) -> List[Dict]:
    """Insert a score from highest to lowest using recursion."""
    if index >= len(scores):
        return scores + [entry]
    if score_key(entry) > score_key(scores[index]):
        return scores[:index] + [entry] + scores[index:]
    return recursive_insert_score(scores, entry, index + 1)


class GameStorage:
    """Handles save files and leaderboard file I/O."""

    def __init__(
        self,
        saves_file: Path = SAVES_FILE,
        leaderboard_file: Path = LEADERBOARD_FILE,
    ):
        self.saves_file = saves_file
        self.leaderboard_file = leaderboard_file

    def empty_slots(self) -> List[Optional[Dict]]:
        return [None for _ in range(SAVE_SLOT_COUNT)]

    def read_save_slots(self) -> List[Optional[Dict]]:
        try:
            raw_slots = json.loads(self.saves_file.read_text(encoding="utf-8"))
            if isinstance(raw_slots, list):
                slots = [slot if isinstance(slot, dict) else None for slot in raw_slots[:SAVE_SLOT_COUNT]]
                return slots + [None for _ in range(SAVE_SLOT_COUNT - len(slots))]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return self.empty_slots()

    def save_game(self, data: Dict, slot: int = 0) -> None:
        if not 0 <= slot < SAVE_SLOT_COUNT:
            raise ValueError("Invalid save slot.")
        slots = self.read_save_slots()
        slots[slot] = data
        self.saves_file.write_text(json.dumps(slots, indent=2), encoding="utf-8")

    def load_game(self, slot: int = 0) -> Dict:
        if not 0 <= slot < SAVE_SLOT_COUNT:
            raise ValueError("Invalid save slot.")
        slot_data = self.read_save_slots()[slot]
        if slot_data is None:
            raise FileNotFoundError("No save file found.")
        return slot_data

    def read_leaderboard(self) -> List[Dict]:
        try:
            scores = json.loads(self.leaderboard_file.read_text(encoding="utf-8"))
            return scores if isinstance(scores, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def add_leaderboard_score(self, chips: int, level: int, rounds: int) -> None:
        entry = {"chips": chips, "level": level, "rounds": rounds}
        scores = recursive_insert_score(self.read_leaderboard(), entry)
        try:
            self.leaderboard_file.write_text(json.dumps(scores[:10], indent=2), encoding="utf-8")
        except OSError:
            pass


DEFAULT_STORAGE = GameStorage()
