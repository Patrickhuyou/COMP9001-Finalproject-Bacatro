import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Register clicks even when the window isn't focused (needed on some macOS setups).
os.environ.setdefault("SDL_MOUSE_FOCUS_CLICKTHROUGH", "1")

try:
    import pygame
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Pygame is not installed. Run: python3 -m pip install -r requirements.txt"
    ) from exc

from cards import Card, Hand, SUIT_SYMBOLS
from game_state import MAX_LEVEL, GameState, clamp
from items import ITEM_POOL, Item
from storage import DEFAULT_STORAGE, SAVE_SLOT_COUNT


WIDTH, HEIGHT = 1100, 720
FPS = 60

BG = (22, 52, 43)
FELT = (28, 96, 74)
INK = (237, 239, 229)
MUTED = (178, 194, 177)
GOLD = (229, 190, 96)
RED = (208, 82, 78)
BLUE = (78, 139, 206)
PANEL = (30, 42, 48)
BLACK = (18, 21, 24)
WHITE = (248, 248, 242)
CARD_EDGE = (226, 222, 210)
CARD_SHADOW = (8, 12, 12)
EVOLUTION_BG = (244, 239, 216)
EVOLUTION_INNER = (255, 252, 236)
EVOLUTION_DARK = (38, 36, 32)
CHIP_BG = (45, 62, 60)
HOME_PANEL = (24, 38, 38)
GAME_OVER_RED = (180, 61, 61)
RARITY_COLORS = {
    "Common": (170, 188, 177),
    "Rare": BLUE,
    "Epic": (198, 122, 226),
}
LOGO_FILE = Path("assets/bacatro-logo.png")


class Button:
    """Reusable clickable UI element built from a pygame.Rect and callback."""

    def __init__(self, rect: pygame.Rect, label: str, action: Callable):
        self.rect = rect
        self.label = label
        self.action = action

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, active: bool = True) -> None:
        mouse = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse)
        color = GOLD if hovered and active else (72, 92, 86)
        if not active:
            color = (48, 58, 58)
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, self.rect, width=2, border_radius=8)
        text = font.render(self.label, True, BLACK if active else MUTED)
        screen.blit(text, text.get_rect(center=self.rect.center))

    def click(self, pos: Tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.action()
            return True
        return False


class BacatroApp:
    """Main Pygame application controller for screens, input, and drawing."""

    def __init__(self):
        # Pygame setup: create the window, clock, fonts, and starting game state.
        pygame.init()
        pygame.display.set_caption("Bacatro")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("arial", 46, bold=True)
        self.big_font = pygame.font.SysFont("arial", 30, bold=True)
        self.card_title_font = pygame.font.SysFont("arial", 24, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.small_font = pygame.font.SysFont("arial", 17)
        self.item_font = pygame.font.SysFont("arial", 15)
        self.tiny_font = pygame.font.SysFont("arial", 13, bold=True)
        self.logo = self.load_logo()
        self.game = GameState()
        self.running = True
        self.buttons: List[Button] = []
        self.menu_return_state = "home"
        self.rules_scroll = 0
        self.rules_scroll_max = 0
        self.screen_state = ""
        self.set_screen_state("home")

    def set_screen_state(self, state: str) -> None:
        # Every screen owns a different set of buttons, so refresh them together.
        self.screen_state = state
        self.refresh_buttons()

    def refresh_buttons(self) -> None:
        # Screen-state dispatch keeps button layout out of the event loop.
        if self.screen_state == "home":
            self.build_home_buttons()
        elif self.screen_state == "playing":
            self.build_play_buttons()
        elif self.screen_state == "game_over":
            self.build_game_over_buttons()
        elif self.screen_state == "victory":
            self.build_victory_buttons()
        elif self.screen_state == "load_game":
            self.build_load_buttons()
        elif self.screen_state == "save_game":
            self.build_save_buttons()
        elif self.screen_state == "rules":
            self.build_rules_buttons()
        else:
            self.buttons = []

    def save_to_slot(self, slot: int) -> None:
        # UI calls storage through GameState.to_dict(), so files stay JSON-safe.
        try:
            DEFAULT_STORAGE.save_game(self.game.to_dict(), slot=slot)
            self.game.message = f"Game saved to slot {slot + 1}."
            self.set_screen_state("playing")
        except OSError as exc:
            self.game.message = f"Save failed: {exc}"
            self.set_screen_state("playing")

    def load_from_slot(self, slot: int) -> None:
        # After loading, choose the correct screen based on the saved run state.
        try:
            data = DEFAULT_STORAGE.load_game(slot=slot)
            self.game = GameState.from_dict(data)
            if self.game.run_cleared:
                self.set_screen_state("victory")
            elif self.game.is_game_over or self.game.chips <= 0:
                self.set_screen_state("game_over")
            else:
                self.set_screen_state("playing")
        except FileNotFoundError:
            self.game.message = f"Slot {slot + 1} is empty."
        except (OSError, ValueError) as exc:
            self.game.message = f"Load failed: {exc}"

    def open_load_screen(self, return_state: str) -> None:
        self.menu_return_state = return_state
        self.set_screen_state("load_game")

    def open_save_screen(self) -> None:
        self.menu_return_state = "playing"
        self.set_screen_state("save_game")

    def open_rules_screen(self) -> None:
        # Start the rules page at the top each time it opens.
        self.rules_scroll = 0
        self.set_screen_state("rules")

    def scroll_rules(self, amount: int) -> None:
        # Clamp prevents the scroll position from moving beyond the content.
        self.rules_scroll = clamp(self.rules_scroll + amount, 0, self.rules_scroll_max)

    def return_from_slot_screen(self) -> None:
        self.set_screen_state(self.menu_return_state)

    def restart(self) -> None:
        self.start_new_run()

    def start_new_run(self) -> None:
        self.game = GameState()
        self.set_screen_state("playing")

    def go_home(self) -> None:
        self.game = GameState()
        self.set_screen_state("home")

    def quit_game(self) -> None:
        self.running = False

    def load_logo(self) -> Optional[pygame.Surface]:
        if not LOGO_FILE.exists():
            return None
        image = pygame.image.load(str(LOGO_FILE)).convert_alpha()
        # Chroma-key the green screen out: make strongly-green pixels transparent.
        for x in range(image.get_width()):
            for y in range(image.get_height()):
                red, green, blue, alpha = image.get_at((x, y))
                if green > 170 and green > red + 70 and green > blue + 70:
                    image.set_at((x, y), (red, green, blue, 0))
        target_width = 360
        target_height = int(image.get_height() * target_width / image.get_width())
        return pygame.transform.scale(image, (target_width, target_height))

    def draw_text(self, text: str, x: int, y: int, font: pygame.font.Font, color=INK) -> None:
        self.screen.blit(font.render(text, True, color), (x, y))

    def fit_text(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        if font.size(text)[0] <= max_width:
            return text
        shortened = text
        while shortened and font.size(f"{shortened}...")[0] > max_width:
            shortened = shortened[:-1]
        return f"{shortened}..." if shortened else "..."

    def suit_color(self, card: Card) -> Tuple[int, int, int]:
        return RED if card.suit in {"H", "D"} else BLACK

    def draw_centered_text(
        self,
        text: str,
        center: Tuple[int, int],
        font: pygame.font.Font,
        color: Tuple[int, int, int],
    ) -> None:
        rendered = font.render(text, True, color)
        self.screen.blit(rendered, rendered.get_rect(center=center))

    def draw_rotated_text(
        self,
        text: str,
        bottomright: Tuple[int, int],
        font: pygame.font.Font,
        color: Tuple[int, int, int],
    ) -> None:
        rendered = pygame.transform.rotate(font.render(text, True, color), 180)
        self.screen.blit(rendered, rendered.get_rect(bottomright=bottomright))

    def draw_face_card(
        self,
        card: Card,
        rect: pygame.Rect,
        suit: str,
        color: Tuple[int, int, int],
    ) -> None:
        portrait = pygame.Rect(rect.x + 18, rect.y + 21, 38, 62)
        pygame.draw.rect(self.screen, (244, 241, 230), portrait, border_radius=5)
        pygame.draw.rect(self.screen, CARD_EDGE, portrait, width=1, border_radius=5)

        crown_y = rect.y + 31
        pygame.draw.polygon(
            self.screen,
            GOLD if card.rank == "K" else color,
            [
                (rect.centerx - 12, crown_y + 5),
                (rect.centerx - 7, crown_y - 5),
                (rect.centerx, crown_y + 4),
                (rect.centerx + 7, crown_y - 5),
                (rect.centerx + 12, crown_y + 5),
            ],
        )
        pygame.draw.circle(self.screen, (238, 205, 162), (rect.centerx, rect.y + 45), 9)
        pygame.draw.polygon(
            self.screen,
            color,
            [
                (rect.centerx, rect.y + 55),
                (rect.centerx - 15, rect.y + 76),
                (rect.centerx + 15, rect.y + 76),
            ],
        )
        self.draw_centered_text(card.rank, (rect.centerx, rect.y + 66), self.font, WHITE)
        self.draw_centered_text(suit, (rect.centerx, rect.y + 90), self.small_font, color)

    def draw_card(self, card: Card, x: int, y: int) -> None:
        # This custom renderer draws ranks, suits, pips, and face cards manually.
        rect = pygame.Rect(x, y, 74, 104)
        shadow = rect.move(3, 4)
        pygame.draw.rect(self.screen, CARD_SHADOW, shadow, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, rect, border_radius=8)
        pygame.draw.rect(self.screen, CARD_EDGE, rect, width=2, border_radius=8)

        color = self.suit_color(card)
        suit = SUIT_SYMBOLS.get(card.suit, card.suit)

        self.draw_text(card.rank, x + 8, y + 7, self.small_font, color)
        self.draw_rotated_text(card.rank, (x + 66, y + 96), self.small_font, color)

        if card.rank in {"J", "Q", "K"}:
            self.draw_text(suit, x + 10, y + 25, self.small_font, color)
            self.draw_rotated_text(suit, (x + 64, y + 78), self.small_font, color)
            self.draw_face_card(card, rect, suit, color)
            return

        if card.rank == "A":
            self.draw_centered_text(suit, rect.center, self.title_font, color)
            return

        pip_positions = {
            "2": [(37, 30), (37, 74)],
            "3": [(37, 28), (37, 52), (37, 76)],
            "4": [(24, 32), (50, 32), (24, 72), (50, 72)],
            "5": [(24, 30), (50, 30), (37, 52), (24, 74), (50, 74)],
            "6": [(24, 28), (50, 28), (24, 52), (50, 52), (24, 76), (50, 76)],
            "7": [(24, 26), (50, 26), (37, 40), (24, 54), (50, 54), (24, 78), (50, 78)],
            "8": [(24, 24), (50, 24), (37, 38), (24, 52), (50, 52), (37, 66), (24, 80), (50, 80)],
            "9": [(24, 24), (50, 24), (24, 38), (50, 38), (37, 52), (24, 66), (50, 66), (24, 80), (50, 80)],
            "10": [(24, 22), (50, 22), (24, 36), (50, 36), (24, 50), (50, 50), (24, 64), (50, 64), (24, 78), (50, 78)],
        }
        for px, py in pip_positions.get(card.rank, []):
            self.draw_centered_text(suit, (x + px, y + py), self.small_font, color)

    def draw_hand(self, title: str, hand: Optional[Hand], x: int, y: int, accent) -> None:
        self.draw_text(title, x, y, self.big_font, accent)
        if not hand:
            for index in range(2):
                rect = pygame.Rect(x + index * 88, y + 48, 74, 104)
                pygame.draw.rect(self.screen, (50, 66, 65), rect, border_radius=8)
                pygame.draw.rect(self.screen, BLACK, rect, width=2, border_radius=8)
            return
        self.draw_text(f"Total: {hand.total}", x + 180, y + 5, self.font, INK)
        for index, card in enumerate(hand.cards):
            self.draw_card(card, x + index * 88, y + 48)

    def build_play_buttons(self) -> None:
        # Buttons store callbacks, so the click handler can stay generic.
        self.buttons = [
            Button(pygame.Rect(56, 606, 82, 44), "Player", lambda: self.set_side("Player")),
            Button(pygame.Rect(146, 606, 82, 44), "Banker", lambda: self.set_side("Banker")),
            Button(pygame.Rect(236, 606, 62, 44), "Tie", lambda: self.set_side("Tie")),
            Button(pygame.Rect(306, 606, 82, 44), "P Pair", lambda: self.set_side("Player Pair")),
            Button(pygame.Rect(396, 606, 82, 44), "B Pair", lambda: self.set_side("Banker Pair")),
            Button(pygame.Rect(494, 606, 56, 44), "-10", lambda: self.change_bet(-10)),
            Button(pygame.Rect(558, 606, 56, 44), "+10", lambda: self.change_bet(10)),
            Button(pygame.Rect(630, 606, 82, 44), "Deal", self.deal),
            Button(pygame.Rect(728, 606, 70, 44), "Save", self.open_save_screen),
            Button(pygame.Rect(806, 606, 70, 44), "Load", lambda: self.open_load_screen("playing")),
            Button(pygame.Rect(884, 606, 70, 44), "Home", self.go_home),
            Button(pygame.Rect(962, 606, 82, 44), "New", self.restart),
        ]

    def build_home_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(430, 378, 240, 44), "Start Game", self.start_new_run),
            Button(pygame.Rect(430, 432, 240, 44), "Load Game", lambda: self.open_load_screen("home")),
            Button(pygame.Rect(430, 486, 240, 44), "Rules", self.open_rules_screen),
            Button(pygame.Rect(430, 540, 240, 44), "Quit", self.quit_game),
        ]

    def build_rules_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(382, 628, 160, 44), "Back", self.go_home),
            Button(pygame.Rect(558, 628, 160, 44), "Start Game", self.start_new_run),
        ]

    def build_game_over_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(356, 478, 180, 48), "Reset", self.restart),
            Button(pygame.Rect(564, 478, 180, 48), "Home Page", self.go_home),
        ]

    def build_victory_buttons(self) -> None:
        self.buttons = [
            Button(pygame.Rect(356, 478, 180, 48), "New Run", self.restart),
            Button(pygame.Rect(564, 478, 180, 48), "Home Page", self.go_home),
        ]

    def build_load_buttons(self) -> None:
        slots = DEFAULT_STORAGE.read_save_slots()
        self.buttons = [
            Button(pygame.Rect(430, 566, 240, 46), "Back", self.return_from_slot_screen),
        ]
        for index, slot in enumerate(slots):
            if slot is not None:
                self.buttons.append(
                    Button(
                        pygame.Rect(682, 210 + index * 100, 150, 42),
                        f"Load Slot {index + 1}",
                        lambda slot_index=index: self.load_from_slot(slot_index),
                    )
                )

    def build_save_buttons(self) -> None:
        self.buttons = [
            Button(
                pygame.Rect(682, 210 + index * 100, 150, 42),
                f"Save Slot {index + 1}",
                lambda slot_index=index: self.save_to_slot(slot_index),
            )
            for index in range(SAVE_SLOT_COUNT)
        ]
        self.buttons.append(Button(pygame.Rect(430, 566, 240, 46), "Back", self.return_from_slot_screen))

    def set_side(self, side: str) -> None:
        self.game.selected_bet = side

    def change_bet(self, delta: int) -> None:
        max_bet = max(1, self.game.chips)
        self.game.bet = clamp(self.game.bet + delta, 1, max_bet)

    def deal(self) -> None:
        # The UI starts a round, while GameState performs the actual game logic.
        if self.game.shop_choices:
            self.game.message = "Choose an item first."
            return
        try:
            self.game.play_round()
            if self.game.run_cleared:
                self.set_screen_state("victory")
            elif self.game.is_game_over:
                self.set_screen_state("game_over")
        except ValueError as exc:
            self.game.message = str(exc)

    def choose_shop_item(self, pos: Tuple[int, int]) -> bool:
        # Evolution cards are not normal buttons because they are large cards.
        if not self.game.shop_choices:
            return False
        for index, item in enumerate(self.game.shop_choices):
            rect = pygame.Rect(149 + index * 278, 238, 246, 220)
            if rect.collidepoint(pos):
                self.game.choose_item(index)
                return True
        return False

    def handle_key(self, key: int) -> None:
        # Keyboard behavior depends on the current screen state.
        if self.screen_state == "home":
            if key in {pygame.K_RETURN, pygame.K_SPACE}:
                self.start_new_run()
            elif key == pygame.K_l:
                self.open_load_screen("home")
            elif key == pygame.K_r:
                self.open_rules_screen()
            elif key == pygame.K_ESCAPE:
                self.quit_game()
            return

        if self.screen_state == "rules":
            if key in {pygame.K_ESCAPE, pygame.K_h, pygame.K_BACKSPACE}:
                self.go_home()
            elif key in {pygame.K_RETURN, pygame.K_SPACE}:
                self.start_new_run()
            elif key == pygame.K_DOWN:
                self.scroll_rules(36)
            elif key == pygame.K_UP:
                self.scroll_rules(-36)
            elif key == pygame.K_PAGEDOWN:
                self.scroll_rules(180)
            elif key == pygame.K_PAGEUP:
                self.scroll_rules(-180)
            return

        if self.screen_state == "load_game":
            if key == pygame.K_ESCAPE:
                self.return_from_slot_screen()
            elif pygame.K_1 <= key <= pygame.K_3:
                self.load_from_slot(key - pygame.K_1)
            return

        if self.screen_state == "save_game":
            if key == pygame.K_ESCAPE:
                self.return_from_slot_screen()
            elif pygame.K_1 <= key <= pygame.K_3:
                self.save_to_slot(key - pygame.K_1)
            return

        if self.screen_state == "game_over":
            if key == pygame.K_r:
                self.restart()
            elif key in {pygame.K_h, pygame.K_ESCAPE}:
                self.go_home()
            return

        if self.screen_state == "victory":
            if key == pygame.K_r:
                self.restart()
            elif key in {pygame.K_h, pygame.K_ESCAPE}:
                self.go_home()
            return

        # Number keys pick the bet side, and double as the item picker when the
        # evolution shop is open between levels.
        if key == pygame.K_SPACE:
            self.deal()
        elif key == pygame.K_1:
            self.set_side("Player")
            if self.game.shop_choices:
                self.game.choose_item(0)
        elif key == pygame.K_2:
            self.set_side("Banker")
            if self.game.shop_choices:
                self.game.choose_item(1)
        elif key == pygame.K_3:
            self.set_side("Tie")
            if self.game.shop_choices:
                self.game.choose_item(2)
        elif key == pygame.K_4:
            self.set_side("Player Pair")
        elif key == pygame.K_5:
            self.set_side("Banker Pair")
        elif key in {pygame.K_EQUALS, pygame.K_PLUS}:
            self.change_bet(10)
        elif key == pygame.K_MINUS:
            self.change_bet(-10)
        elif key == pygame.K_s:
            self.open_save_screen()
        elif key == pygame.K_l:
            self.open_load_screen("playing")
        elif key == pygame.K_h:
            self.go_home()
        elif key == pygame.K_r:
            self.restart()

    def draw_panel(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), rect, width=2, border_radius=8)

    def draw_wrapped_text(
        self,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        max_width: int,
        line_height: int,
    ) -> int:
        for line in wrap_text(text, font, max_width):
            self.draw_text(line, x, y, font, color)
            y += line_height
        return y

    def draw_odds_panel(self) -> None:
        rect = pygame.Rect(370, 318, 360, 64)
        self.draw_panel(rect)
        self.draw_text("Payouts", rect.x + 16, rect.y + 10, self.small_font, GOLD)
        odds = [
            ("Player", "1:1"),
            ("Banker", "1:1" if self.game.no_commission else "0.95:1"),
            ("Tie", f"{self.game.tie_multiplier}:1"),
            ("Pair", f"{self.game.pair_multiplier}:1"),
        ]
        column_width = 82
        for index, (label, value) in enumerate(odds):
            x = rect.x + 16 + index * column_width
            self.draw_text(label, x, rect.y + 33, self.tiny_font, MUTED)
            self.draw_text(value, x, rect.y + 47, self.small_font, INK)

    def draw_header_stat(self, rect: pygame.Rect, label: str, value: str, accent) -> None:
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), rect, width=2, border_radius=8)
        self.draw_text(label, rect.x + 12, rect.y + 8, self.tiny_font, MUTED)
        self.draw_text(value, rect.x + 12, rect.y + 23, self.font, accent)

    def draw_progress_panel(self) -> None:
        rect = pygame.Rect(74, 102, 952, 24)
        self.draw_text("Target progress", rect.x, rect.y + 2, self.small_font, MUTED)
        bar = pygame.Rect(rect.x + 118, rect.y + 3, rect.width - 118, 18)
        progress_width = clamp(int(bar.width * self.game.chips / max(1, self.game.target)), 0, bar.width)
        pygame.draw.rect(self.screen, (55, 64, 60), bar, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, pygame.Rect(bar.x, bar.y, progress_width, bar.height), border_radius=8)

    def draw_evolution_card(self, item: Item, index: int, rect: pygame.Rect) -> None:
        mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse)
        card_rect = rect.move(0, -6 if hovered else 0)
        accent = RARITY_COLORS[item.rarity]

        pygame.draw.rect(self.screen, (0, 0, 0, 90), card_rect.move(5, 7), border_radius=8)
        pygame.draw.rect(self.screen, EVOLUTION_BG, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, accent, card_rect, width=3 if hovered else 2, border_radius=8)

        header = pygame.Rect(card_rect.x, card_rect.y, card_rect.width, 42)
        pygame.draw.rect(self.screen, EVOLUTION_DARK, header, border_top_left_radius=8, border_top_right_radius=8)
        self.draw_text(f"{item.rarity.upper()} EVOLUTION", card_rect.x + 18, card_rect.y + 12, self.tiny_font, accent)
        number = pygame.Rect(card_rect.right - 42, card_rect.y + 8, 25, 25)
        pygame.draw.circle(self.screen, accent, number.center, 13)
        self.draw_centered_text(str(index + 1), number.center, self.tiny_font, EVOLUTION_DARK)

        inner = pygame.Rect(card_rect.x + 16, card_rect.y + 58, card_rect.width - 32, 134)
        pygame.draw.rect(self.screen, EVOLUTION_INNER, inner, border_radius=6)
        pygame.draw.rect(self.screen, CARD_EDGE, inner, width=1, border_radius=6)

        name = self.fit_text(item.name, self.card_title_font, inner.width - 24)
        self.draw_text(name, inner.x + 12, inner.y + 14, self.card_title_font, EVOLUTION_DARK)
        pygame.draw.line(self.screen, accent, (inner.x + 12, inner.y + 52), (inner.right - 12, inner.y + 52), width=2)

        wrapped = wrap_text(item.description, self.item_font, inner.width - 24)[:4]
        for line_index, line in enumerate(wrapped):
            self.draw_text(line, inner.x + 12, inner.y + 66 + line_index * 20, self.item_font, EVOLUTION_DARK)

        footer = self.fit_text("Click or press number key", self.tiny_font, card_rect.width - 32)
        self.draw_centered_text(footer, (card_rect.centerx, card_rect.bottom - 16), self.tiny_font, (88, 81, 61))

    def draw_inventory_chips(self, rect: pygame.Rect) -> None:
        self.draw_text("Items", rect.x, rect.y, self.small_font, MUTED)
        if not self.game.inventory:
            self.draw_text("No evolutions yet", rect.x, rect.y + 24, self.small_font, MUTED)
            return

        x = rect.x
        y = rect.y + 26
        row_height = 24
        hidden = 0
        for name in self.game.inventory:
            label = self.fit_text(name, self.item_font, min(148, rect.width - 18))
            chip_width = self.item_font.size(label)[0] + 18
            if x + chip_width > rect.right:
                x = rect.x
                y += row_height
            if y + row_height > rect.bottom:
                hidden += 1
                continue
            chip_rect = pygame.Rect(x, y, chip_width, 19)
            pygame.draw.rect(self.screen, CHIP_BG, chip_rect, border_radius=6)
            pygame.draw.rect(self.screen, (73, 95, 88), chip_rect, width=1, border_radius=6)
            self.draw_text(label, chip_rect.x + 9, chip_rect.y + 2, self.item_font, INK)
            x += chip_width + 7

        if hidden:
            more = f"+{hidden} more"
            more_width = self.item_font.size(more)[0] + 18
            if x + more_width > rect.right:
                x = rect.x
                y += row_height
            if y + row_height > rect.bottom:
                x = rect.right - more_width
                y = rect.bottom - 19
            more_rect = pygame.Rect(x, y, more_width, 19)
            pygame.draw.rect(self.screen, GOLD, more_rect, border_radius=6)
            self.draw_text(more, more_rect.x + 9, more_rect.y + 2, self.item_font, BLACK)

    def draw_shop(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 176))
        self.screen.blit(overlay, (0, 0))
        self.draw_centered_text("Choose an Evolution", (WIDTH // 2, 154), self.title_font, GOLD)
        self.draw_centered_text("Pick one upgrade for the next level", (WIDTH // 2, 197), self.small_font, INK)
        for index, item in enumerate(self.game.shop_choices):
            rect = pygame.Rect(149 + index * 278, 238, 246, 220)
            self.draw_evolution_card(item, index, rect)

    def draw_home(self) -> None:
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 28, 1044, 664), border_radius=18)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 28, 1044, 664), width=4, border_radius=18)

        panel = pygame.Rect(330, 72, 440, 548)
        pygame.draw.rect(self.screen, HOME_PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), panel, width=2, border_radius=8)

        self.draw_centered_text("BACATRO", (WIDTH // 2, 140), self.title_font, GOLD)
        self.draw_centered_text("Baccarat roguelike", (WIDTH // 2, 188), self.font, INK)

        if self.logo:
            logo_rect = self.logo.get_rect(center=(WIDTH // 2, 264))
            self.screen.blit(self.logo, logo_rect)
        else:
            self.draw_centered_text("BACATRO", (WIDTH // 2, 264), self.big_font, GOLD)

        self.draw_centered_text("Reach each chip target and evolve your run.", (WIDTH // 2, 342), self.small_font, MUTED)
        for button in self.buttons:
            button.draw(self.screen, self.font)

        if self.game.message != "Choose a side, set your bet, then press Deal.":
            message = self.fit_text(self.game.message, self.small_font, panel.width - 36)
            self.draw_centered_text(message, (WIDTH // 2, 605), self.small_font, INK)
        self.draw_centered_text("Enter Start   L Load   R Rules   Esc Quit", (WIDTH // 2, 648), self.small_font, MUTED)

    def draw_rules(self) -> None:
        # Rules uses a scrollable clipped viewport so the text can stay readable.
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 28, 1044, 664), border_radius=18)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 28, 1044, 664), width=4, border_radius=18)

        panel = pygame.Rect(62, 46, 976, 642)
        pygame.draw.rect(self.screen, HOME_PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), panel, width=2, border_radius=8)
        self.draw_centered_text("RULES", (WIDTH // 2, 88), self.title_font, GOLD)
        self.draw_centered_text("Learn the table, then build a run with evolution cards.", (WIDTH // 2, 124), self.small_font, MUTED)

        viewport = pygame.Rect(92, 150, 900, 438)
        content_frame = viewport.inflate(0, 0)
        self.draw_panel(content_frame)

        old_clip = self.screen.get_clip()
        self.screen.set_clip(viewport)

        left_x = viewport.x + 26
        right_x = viewport.x + 494
        column_width = 390
        left_y = viewport.y + 22 - self.rules_scroll
        right_y = left_y

        self.draw_text("Baccarat Basics", left_x, left_y, self.font, GOLD)
        left_y += 36
        basics = [
            "Player and Banker each receive two cards. The hand closest to 9 wins.",
            "Only the last digit counts: 15 becomes 5, 20 becomes 0.",
            "Natural 8 or 9 stops the round immediately.",
            "A counts as 1. 10, J, Q, and K count as 0.",
        ]
        for line in basics:
            left_y = self.draw_wrapped_text(f"- {line}", left_x + 4, left_y, self.small_font, INK, column_width, 22)
            left_y += 6

        left_y += 14
        self.draw_text("Drawing Rules", left_x, left_y, self.font, GOLD)
        left_y += 36
        drawing = [
            "Player draws on 0-5 and stands on 6-7.",
            "If Player stands, Banker draws on 0-5 and stands on 6-7.",
            "If Player draws, Banker uses its own total plus Player's third-card value.",
            "Pair bets only check the first two cards, not any third card.",
        ]
        for line in drawing:
            left_y = self.draw_wrapped_text(f"- {line}", left_x + 4, left_y, self.small_font, INK, column_width, 22)
            left_y += 6

        left_y += 14
        self.draw_text("Banker Third-Card Table", left_x, left_y, self.font, GOLD)
        left_y += 36
        banker_table = [
            "Banker 0-2: always draws.",
            "Banker 3: draws unless Player third card is 8.",
            "Banker 4: draws if Player third card is 2-7.",
            "Banker 5: draws if Player third card is 4-7.",
            "Banker 6: draws if Player third card is 6-7.",
            "Banker 7: stands.",
        ]
        for line in banker_table:
            left_y = self.draw_wrapped_text(f"- {line}", left_x + 4, left_y, self.small_font, INK, column_width, 22)
            left_y += 5

        left_y += 14
        self.draw_text("Bets And Levels", left_x, left_y, self.font, GOLD)
        left_y += 36
        bets = [
            "Player pays 1:1. Banker pays 0.95:1 unless upgraded.",
            "Tie pays 8:1. Player Pair and Banker Pair pay 11:1.",
            f"Clear {MAX_LEVEL} levels by reaching each chip target before bets run out.",
            "Higher levels allow fewer bets, so each decision matters more.",
        ]
        for line in bets:
            left_y = self.draw_wrapped_text(f"- {line}", left_x + 4, left_y, self.small_font, INK, column_width, 22)
            left_y += 6

        self.draw_text("Evolution Cards", right_x, right_y, self.font, GOLD)
        right_y += 34
        right_y = self.draw_wrapped_text(
            "After clearing a level, choose one of three cards. Common appears most often, Rare is stronger, and Epic is hardest to find.",
            right_x,
            right_y,
            self.small_font,
            MUTED,
            column_width,
            22,
        )
        right_y += 18

        rarity_rank = {"Common": 0, "Rare": 1, "Epic": 2}
        item_classes = sorted(ITEM_POOL, key=lambda item: (rarity_rank[item.rarity], item.name))
        for item_class in item_classes:
            color = RARITY_COLORS[item_class.rarity]
            pygame.draw.circle(self.screen, color, (right_x + 7, right_y + 10), 5)
            self.draw_text(item_class.name, right_x + 20, right_y, self.small_font, color)
            self.draw_text(item_class.rarity, right_x + 278, right_y + 2, self.tiny_font, MUTED)
            right_y += 24
            right_y = self.draw_wrapped_text(
                item_class.description,
                right_x + 20,
                right_y,
                self.small_font,
                INK,
                column_width - 20,
                22,
            )
            right_y += 16

        self.screen.set_clip(old_clip)

        # Calculate scrollbar size from the content height drawn above.
        content_bottom = max(left_y, right_y) + self.rules_scroll + 24
        self.rules_scroll_max = max(0, content_bottom - viewport.bottom)
        if self.rules_scroll > self.rules_scroll_max:
            self.rules_scroll = self.rules_scroll_max

        track = pygame.Rect(viewport.right + 10, viewport.y, 10, viewport.height)
        pygame.draw.rect(self.screen, (42, 56, 54), track, border_radius=5)
        if self.rules_scroll_max > 0:
            thumb_height = max(48, int(track.height * track.height / (track.height + self.rules_scroll_max)))
            thumb_range = track.height - thumb_height
            thumb_y = track.y + int(thumb_range * self.rules_scroll / self.rules_scroll_max)
            pygame.draw.rect(self.screen, GOLD, pygame.Rect(track.x, thumb_y, track.width, thumb_height), border_radius=5)
        else:
            pygame.draw.rect(self.screen, GOLD, track, border_radius=5)

        for button in self.buttons:
            button.draw(self.screen, self.font)
        self.draw_centered_text("Mouse Wheel / Up / Down Scroll   Esc Home   Enter Start", (WIDTH // 2, 606), self.small_font, MUTED)

    def draw_game_over(self) -> None:
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 28, 1044, 664), border_radius=18)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 28, 1044, 664), width=4, border_radius=18)

        panel = pygame.Rect(260, 130, 580, 430)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), panel, width=2, border_radius=8)

        self.draw_centered_text("GAME OVER", (WIDTH // 2, 206), self.title_font, GAME_OVER_RED)
        reason = self.game.loss_reason or "You ran out of chips."
        self.draw_centered_text(reason, (WIDTH // 2, 252), self.font, INK)

        stats = [
            f"Level reached: {self.game.level}",
            f"Rounds played: {self.game.rounds_played}",
            f"Rounds won: {self.game.rounds_won}",
            f"Final chips: ${self.game.chips}",
            f"Bets left: {self.game.bets_remaining}",
        ]
        for index, line in enumerate(stats):
            self.draw_centered_text(line, (WIDTH // 2, 300 + index * 32), self.font, INK)

        for button in self.buttons:
            button.draw(self.screen, self.font)
        self.draw_centered_text("R Reset   H Home Page", (WIDTH // 2, 544), self.small_font, MUTED)

    def draw_victory(self) -> None:
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 28, 1044, 664), border_radius=18)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 28, 1044, 664), width=4, border_radius=18)

        panel = pygame.Rect(260, 130, 580, 430)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), panel, width=2, border_radius=8)

        self.draw_centered_text("RUN CLEARED", (WIDTH // 2, 206), self.title_font, GOLD)
        self.draw_centered_text("You beat all 6 levels.", (WIDTH // 2, 252), self.font, INK)

        stats = [
            f"Final chips: ${self.game.chips}",
            f"Rounds played: {self.game.rounds_played}",
            f"Rounds won: {self.game.rounds_won}",
            f"Bets left: {self.game.bets_remaining}",
        ]
        for index, line in enumerate(stats):
            self.draw_centered_text(line, (WIDTH // 2, 314 + index * 34), self.font, INK)

        for button in self.buttons:
            button.draw(self.screen, self.font)
        self.draw_centered_text("R New Run   H Home Page", (WIDTH // 2, 544), self.small_font, MUTED)

    def draw_slot_screen(self, title: str, subtitle: str, saving: bool) -> None:
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 28, 1044, 664), border_radius=18)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 28, 1044, 664), width=4, border_radius=18)

        panel = pygame.Rect(220, 92, 660, 540)
        pygame.draw.rect(self.screen, HOME_PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, (12, 20, 20), panel, width=2, border_radius=8)
        self.draw_centered_text(title, (WIDTH // 2, 142), self.title_font, GOLD)
        self.draw_centered_text(subtitle, (WIDTH // 2, 184), self.small_font, MUTED)

        slots = DEFAULT_STORAGE.read_save_slots()
        for index, slot in enumerate(slots):
            row = pygame.Rect(268, 196 + index * 100, 564, 76)
            pygame.draw.rect(self.screen, PANEL, row, border_radius=8)
            pygame.draw.rect(self.screen, (12, 20, 20), row, width=2, border_radius=8)
            self.draw_text(f"Slot {index + 1}", row.x + 18, row.y + 13, self.font, GOLD)
            if slot is None:
                self.draw_text("Empty slot", row.x + 18, row.y + 43, self.small_font, MUTED)
            else:
                summary = (
                    f"Level {slot.get('level', 1)}   Chips ${slot.get('chips', 100)}   "
                    f"Rounds {slot.get('rounds_played', 0)}"
                )
                self.draw_text(summary, row.x + 18, row.y + 43, self.small_font, INK)
                if saving:
                    self.draw_text("Overwrite", row.right - 232, row.y + 43, self.tiny_font, MUTED)
        for button in self.buttons:
            button.draw(self.screen, self.font)

        if self.game.message != "Choose a side, set your bet, then press Deal.":
            message = self.fit_text(self.game.message, self.small_font, panel.width - 36)
            self.draw_centered_text(message, (WIDTH // 2, 632), self.small_font, INK)

    def draw_load_game(self) -> None:
        self.draw_slot_screen("Load Game", "Choose a saved run", saving=False)

    def draw_save_game(self) -> None:
        self.draw_slot_screen("Save Game", "Choose a slot to save this run", saving=True)

    def draw(self) -> None:
        # Top-level render dispatcher: draw the current screen and return early.
        if self.screen_state == "home":
            self.draw_home()
            pygame.display.flip()
            return

        if self.screen_state == "load_game":
            self.draw_load_game()
            pygame.display.flip()
            return

        if self.screen_state == "save_game":
            self.draw_save_game()
            pygame.display.flip()
            return

        if self.screen_state == "rules":
            self.draw_rules()
            pygame.display.flip()
            return

        if self.screen_state == "game_over":
            self.draw_game_over()
            pygame.display.flip()
            return

        if self.screen_state == "victory":
            self.draw_victory()
            pygame.display.flip()
            return

        self.screen.fill(BG)
        pygame.draw.rect(self.screen, FELT, pygame.Rect(28, 84, 1044, 504), border_radius=16)
        pygame.draw.rect(self.screen, (17, 35, 31), pygame.Rect(28, 84, 1044, 504), width=4, border_radius=16)

        self.draw_text("Bacatro", 52, 20, self.title_font, GOLD)
        self.draw_header_stat(pygame.Rect(392, 20, 170, 54), "CHIPS", f"${self.game.chips}", GOLD)
        self.draw_header_stat(pygame.Rect(576, 20, 170, 54), "LEVEL", f"{self.game.level}/{MAX_LEVEL}", BLUE)
        self.draw_header_stat(pygame.Rect(760, 20, 170, 54), "TARGET", f"${self.game.target}", INK)
        self.draw_header_stat(pygame.Rect(944, 20, 104, 54), "BETS", str(self.game.bets_remaining), RED)
        self.draw_progress_panel()

        result = self.game.last_result
        self.draw_hand("PLAYER", result.player if result else None, 100, 150, BLUE)
        self.draw_hand("BANKER", result.banker if result else None, 620, 150, RED)
        self.draw_odds_panel()

        self.draw_panel(pygame.Rect(74, 392, 460, 190))
        self.draw_text("Round log", 96, 410, self.font, GOLD)
        lines = result.narration if result else [self.game.scout_hint() or "No cards dealt yet."]
        for line_index, line in enumerate(lines[:5]):
            self.draw_text(line, 96, 446 + line_index * 24, self.small_font, INK)

        self.draw_panel(pygame.Rect(566, 392, 460, 190))
        self.draw_text("Run status", 588, 410, self.font, GOLD)
        message = self.fit_text(self.game.message, self.small_font, 416)
        self.draw_text(message, 588, 446, self.small_font, INK)
        self.draw_text(f"Bet: ${self.game.bet} on {self.game.selected_bet}", 588, 476, self.font, INK)
        self.draw_text(f"Bets left this level: {self.game.bets_remaining}", 588, 502, self.small_font, MUTED)
        self.draw_inventory_chips(pygame.Rect(588, 523, 416, 52))

        for button in self.buttons:
            button.draw(self.screen, self.font)
        selected_side_rects = {
            "Player": pygame.Rect(56, 606, 82, 44),
            "Banker": pygame.Rect(146, 606, 82, 44),
            "Tie": pygame.Rect(236, 606, 62, 44),
            "Player Pair": pygame.Rect(306, 606, 82, 44),
            "Banker Pair": pygame.Rect(396, 606, 82, 44),
        }
        pygame.draw.rect(
            self.screen,
            GOLD,
            selected_side_rects[self.game.selected_bet],
            width=3,
            border_radius=8,
        )

        self.draw_text(
            "Keys: 1 Player, 2 Banker, 3 Tie, 4 P Pair, 5 B Pair, Space Deal, +/- Bet, S Save, L Load, H Home",
            58,
            672,
            self.small_font,
            MUTED,
        )

        if self.game.shop_choices:
            self.draw_shop()

        pygame.display.flip()

    def run(self) -> None:
        # Main game loop: read events, update state through handlers, then draw.
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
                elif event.type == pygame.MOUSEWHEEL and self.screen_state == "rules":
                    self.scroll_rules(-event.y * 46)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.screen_state == "playing" and self.choose_shop_item(event.pos):
                        continue
                    for button in self.buttons:
                        if button.click(event.pos):
                            break
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
