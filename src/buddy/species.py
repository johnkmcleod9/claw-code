"""
Buddy species — ASCII art sprites and species definitions.

18 species across 8 categories, each with 3 animation frames.
Sprites are 5 lines tall, ~12 chars wide.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Species:
    name: str
    category: str
    frames: tuple[str, ...]  # 3 animation frames


# ─── Species catalog ───

SPECIES: tuple[Species, ...] = (
    Species("Duck", "Classic", (
        "   __     \n  /  \\  . \n ( o> )   \n  \\_/|    \n   ||     ",
        "   __     \n  /  \\ .  \n ( o> )   \n  \\_/|    \n   |/     ",
        "   __     \n  /  \\  . \n ( o> )   \n  \\_/|    \n   \\|     ",
    )),
    Species("Goose", "Classic", (
        "    __    \n   /  \\   \n  ( O> )  \n   |  |   \n  _|  |_  ",
        "    __    \n   /  \\   \n  ( O> )! \n   |  |   \n  _/ \\|_  ",
        "    __    \n   /  \\   \n  ( O> )  \n   | \\|   \n  _|  |_  ",
    )),
    Species("Cat", "Classic", (
        "  /\\_/\\   \n ( o.o )  \n  > ^ <   \n   |_|    \n  /   \\   ",
        "  /\\_/\\   \n ( -.o )  \n  > ^ <   \n   |_|    \n  /   \\   ",
        "  /\\_/\\   \n ( o.- )  \n  > ^ <   \n   |_|    \n  /   \\   ",
    )),
    Species("Rabbit", "Classic", (
        "  (\\(\\    \n  ( -.-)  \n  o_(\")(\")\n          \n          ",
        "  (\\(\\    \n  ( o.o)  \n  o_(\")(\")\n          \n          ",
        "  (\\(\\    \n  ( ^.^)  \n  o_(\")(\")\n          \n          ",
    )),
    Species("Owl", "Wise", (
        "   {o,o}  \n   |)__)  \n   -\"-\"-  \n    | |   \n   _| |_  ",
        "   {o,o}  \n   |)__)  \n   -\"-\"-  \n    | |   \n   _| |_  ",
        "   {-,-}  \n   |)__)  \n   -\"-\"-  \n    | |   \n   _| |_  ",
    )),
    Species("Penguin", "Cool", (
        "   (o_o)  \n  /|   |\\ \n   |   |  \n   d   b  \n          ",
        "   (o_o)  \n  /|   |\\ \n   |   |  \n    d b   \n          ",
        "   (-_o)  \n  /|   |\\ \n   |   |  \n   d   b  \n          ",
    )),
    Species("Turtle", "Chill", (
        "    _____\n   /o   o\\\n  |  ___  |\n   \\_____/ \n   _|  |_  ",
        "    _____\n   /o   o\\\n  |  ___  |\n   \\_____/ \n  _|   |_  ",
        "    _____\n   /-   o\\\n  |  ___  |\n   \\_____/ \n   _|  |_  ",
    )),
    Species("Snail", "Chill", (
        "    @     \n   / \\    \n  /___\\   \n |------|  \n          ",
        "     @    \n    / \\   \n   /___\\  \n  |------| \n          ",
        "    @     \n   / \\    \n  /___\\   \n |------|  \n          ",
    )),
    Species("Dragon", "Mythical", (
        "   /\\_    \n  / o \\~  \n /  __/   \n/_/\\ \\    \n    \\_\\   ",
        "   /\\_    \n  / o \\*  \n /  __/   \n/_/\\ \\    \n    \\_\\   ",
        "   /\\_    \n  / - \\~  \n /  __/   \n/_/\\ \\    \n    \\_\\   ",
    )),
    Species("Octopus", "Aquatic", (
        "   ___    \n  (o o)   \n  /| |\\   \n / | | \\  \n/  | |  \\ ",
        "   ___    \n  (o.o)   \n  /| |\\   \n / | | \\  \n \\  |  /  ",
        "   ___    \n  (o o)   \n  \\| |/   \n / | | \\  \n/  | |  \\ ",
    )),
    Species("Axolotl", "Exotic", (
        " \\(o_o)/  \n  (   )   \n  /| |\\   \n   | |    \n   ~ ~    ",
        " \\(^_^)/  \n  (   )   \n  /| |\\   \n   | |    \n   ~ ~    ",
        " \\(o_o)/  \n  (   )   \n  \\| |/   \n   | |    \n   ~ ~    ",
    )),
    Species("Ghost", "Spooky", (
        "   ___    \n  / o \\   \n |  O  |  \n |     |  \n  \\/\\/\\/  ",
        "   ___    \n  / o \\   \n |  o  |  \n |     |  \n  \\/\\/\\/  ",
        "   ___    \n  / O \\   \n |  O  |  \n |     |  \n  \\/\\/\\/  ",
    )),
    Species("Robot", "Tech", (
        "  [===]   \n  |o o|   \n  |___|   \n  /| |\\   \n _| |_    ",
        "  [===]   \n  |* *|   \n  |___|   \n  /| |\\   \n _| |_    ",
        "  [===]   \n  |o o|   \n  |_=_|   \n  /| |\\   \n _| |_    ",
    )),
    Species("Blob", "Abstract", (
        "   .--.   \n  /    \\  \n | o  o | \n  \\    /  \n   '--'   ",
        "   .---.  \n  /     \\ \n | o  o | \n  \\    /  \n   '---'  ",
        "  .---.   \n /     \\  \n| o  o  | \n \\     /  \n  '---'   ",
    )),
    Species("Cactus", "Plant", (
        "    |     \n   /|\\    \n  / | \\   \n    |     \n   ~~~    ",
        "    |     \n   /|\\  * \n  / | \\   \n    |     \n   ~~~    ",
        "    | *   \n   /|\\    \n  / | \\   \n    |     \n   ~~~    ",
    )),
    Species("Mushroom", "Fungi", (
        "   .--.   \n  / ~~ \\  \n /______\\ \n    ||    \n    ||    ",
        "   .--.   \n  / ** \\  \n /______\\ \n    ||    \n    ||    ",
        "   .--.   \n  / ~~ \\  \n /______\\ \n    ||    \n   _||_   ",
    )),
    Species("Chonk", "Meme", (
        "  /\\_/\\   \n ( O_O )  \n (>   <)  \n  |   |   \n  \\___/   ",
        "  /\\_/\\   \n ( O.O )  \n (>   <)  \n  |   |   \n  \\___/   ",
        "  /\\_/\\   \n ( -_- )  \n (>   <)  \n  |   |   \n  \\___/   ",
    )),
    Species("Capybara", "Special", (
        "  .----.  \n (  o o ) \n  | -- |  \n  /    \\  \n _|    |_ ",
        "  .----.  \n (  o o ) \n  | \\/ |  \n  /    \\  \n _|    |_ ",
        "  .----.  \n (  - o ) \n  | -- |  \n  /    \\  \n _|    |_ ",
    )),
)

SPECIES_BY_NAME = {s.name: s for s in SPECIES}
