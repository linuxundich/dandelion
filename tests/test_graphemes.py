# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from dandelion.core.graphemes import count_graphemes, iter_graphemes


@pytest.mark.parametrize("text, expected", [
    ("", 0),
    ("abc", 3),
    ("Grüße", 5),
    ("é", 1),                       # e + kombinierender Akut
    ("\r\n", 1),
    ("👍🏽", 1),                            # Hautfarbe
    ("👨‍👩‍👧‍👦", 1),                          # ZWJ-Familie
    ("🏳️‍🌈", 1),                            # Regenbogenflagge
    ("🇩🇪🇫🇷", 2),                           # zwei Flaggen
    ("🇩🇪🇫", 2),                             # Flagge + einzelner RI
    ("🏴󠁧󠁢󠁳󠁣󠁴󠁿", 1),                           # Schottland (Tag-Sequenz)
    ("1️⃣", 1),                              # Keycap
    ("한국어", 3),                            # Hangul-Silben
    ("각", 1),              # Hangul-Jamo L V T
    ("नमस्ते", 4),                          # Devanagari (vereinfachte Zählung, ohne GB9c)
    ("a‍b", 2),                        # ZWJ ohne Emoji trennt nicht weiter
])
def test_count(text, expected):
    assert count_graphemes(text) == expected


def test_roundtrip():
    text = "Hallo 👨‍👩‍👧 Welt 🇩🇪!"
    assert "".join(iter_graphemes(text)) == text
