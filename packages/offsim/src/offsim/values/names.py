"""Invented club and player names."""

from __future__ import annotations

import random

_TOWN_START = ("Ash", "Bram", "Carr", "Dun", "Elm", "Fen", "Gar", "Holt", "Kel", "Lyn")
_TOWN_END = ("ford", "wick", "ley", "mouth", "bury", "dale", "stow", "ham")
_CLUB_SUFFIX = ("Athletic", "Rovers", "United", "Wanderers", "Town", "Albion")

_GIVEN = ("Aro", "Bel", "Cai", "Dari", "Edo", "Fen", "Galo", "Iko", "Jaro", "Kesi",
          "Lio", "Maro", "Nilo", "Oren", "Pavo", "Remi", "Sami", "Tavi", "Ulo", "Vito")
_FAMILY_START = ("Am", "Bor", "Cal", "Dav", "Est", "Gor", "Har", "Ival", "Kor", "Mar",
                 "Nor", "Ost", "Pel", "Rov", "Sel", "Tor", "Val", "Wen")
_FAMILY_END = ("ani", "ek", "enko", "ez", "ini", "ov", "sen", "son", "ura", "ovic")


def club_name(r: random.Random, taken: set[str]) -> tuple[str, str]:
    """(name, three-letter short name), unique within ``taken``."""
    while True:
        town = r.choice(_TOWN_START) + r.choice(_TOWN_END)
        name = f"{town} {r.choice(_CLUB_SUFFIX)}"
        if name not in taken:
            taken.add(name)
            return name, town[:3].upper()


def player_name(r: random.Random) -> str:
    return f"{r.choice(_GIVEN)} {r.choice(_FAMILY_START)}{r.choice(_FAMILY_END)}"
