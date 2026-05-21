from typing import Optional


class BaccaratRules:
    """Encapsulates Baccarat third-card flow control rules."""

    def player_should_draw(self, total: int) -> bool:
        # Player draws a third card on 0-5 and stands on 6-7.
        return total <= 5

    def banker_should_draw(self, banker_total: int, player_third: Optional[int]) -> bool:
        # Standard Baccarat banker third-card tableau: whether the banker draws
        # depends on its own total and the value of the player's third card.
        if player_third is None:
            # Player stood, so the banker follows the same 0-5 draw rule.
            return banker_total <= 5
        if banker_total <= 2:
            return True
        if banker_total == 3:
            return player_third != 8
        if banker_total == 4:
            return 2 <= player_third <= 7
        if banker_total == 5:
            return 4 <= player_third <= 7
        if banker_total == 6:
            return 6 <= player_third <= 7
        return False
