# SPDX-License-Identifier: GPL-3.0-or-later
"""Erweiterte Graphem-Cluster nach UAX #29, ohne externe Abhängigkeiten.

Abgedeckt sind die Regeln GB3–GB13: CR LF, Steuerzeichen, Hangul-Silben,
Extend/ZWJ, SpacingMark, Prepend, Emoji-ZWJ-Sequenzen und Paare von
Regional Indicators (Flaggen). Die Eigenschaften werden aus `unicodedata`
und Codepunkt-Bereichen abgeleitet. Für Zeichenzähler reicht das; seltene
Sonderfälle (z. B. indische Konjunkte nach GB9c) werden als einzelne
Grapheme gezählt.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from enum import Enum, auto


class _P(Enum):
    OTHER = auto()
    CR = auto()
    LF = auto()
    CONTROL = auto()
    EXTEND = auto()
    ZWJ = auto()
    RI = auto()
    PREPEND = auto()
    SPACING_MARK = auto()
    L = auto()
    V = auto()
    T = auto()
    LV = auto()
    LVT = auto()


# Extended_Pictographic, angenähert über die Emoji-Blöcke
_PICTO_RANGES = (
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C), (0x2049, 0x2049),
    (0x2122, 0x2122), (0x2139, 0x2139), (0x2194, 0x2199), (0x21A9, 0x21AA),
    (0x231A, 0x231B), (0x2328, 0x2328), (0x2388, 0x2388), (0x23CF, 0x23CF),
    (0x23E9, 0x23F3), (0x23F8, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25AB),
    (0x25B6, 0x25B6), (0x25C0, 0x25C0), (0x25FB, 0x25FE), (0x2600, 0x27BF),
    (0x2934, 0x2935), (0x2B05, 0x2B07), (0x2B1B, 0x2B1C), (0x2B50, 0x2B50),
    (0x2B55, 0x2B55), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297),
    (0x3299, 0x3299), (0x1F000, 0x1F0FF), (0x1F10D, 0x1F10F), (0x1F12F, 0x1F12F),
    (0x1F16C, 0x1F171), (0x1F17E, 0x1F17F), (0x1F18E, 0x1F18E), (0x1F191, 0x1F19A),
    (0x1F1AD, 0x1F1E5), (0x1F201, 0x1F20F), (0x1F21A, 0x1F21A), (0x1F22F, 0x1F22F),
    (0x1F232, 0x1F23A), (0x1F23C, 0x1F23F), (0x1F249, 0x1F3FA), (0x1F400, 0x1F53D),
    (0x1F546, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F774, 0x1F77F), (0x1F7D5, 0x1F7FF),
    (0x1F80C, 0x1F80F), (0x1F848, 0x1F84F), (0x1F85A, 0x1F85F), (0x1F888, 0x1F88F),
    (0x1F8AE, 0x1F8FF), (0x1F90C, 0x1F93A), (0x1F93C, 0x1F945), (0x1F947, 0x1FAFF),
    (0x1FC00, 0x1FFFD),
)

_PREPEND = {0x0600, 0x0601, 0x0602, 0x0603, 0x0604, 0x0605, 0x06DD, 0x070F,
            0x0890, 0x0891, 0x08E2, 0x110BD, 0x110CD}

_SBASE, _LBASE, _VBASE, _TBASE = 0xAC00, 0x1100, 0x1161, 0x11A7
_SCOUNT = 11172


def _is_picto(cp: int) -> bool:
    if cp < 0xA9:
        return False
    for lo, hi in _PICTO_RANGES:
        if cp < lo:
            return False
        if cp <= hi:
            return True
    return False


def _prop(ch: str) -> _P:
    cp = ord(ch)
    if cp == 0x0D:
        return _P.CR
    if cp == 0x0A:
        return _P.LF
    if cp == 0x200D:
        return _P.ZWJ
    if 0x1F1E6 <= cp <= 0x1F1FF:
        return _P.RI
    if 0x1F3FB <= cp <= 0x1F3FF:          # Hautfarben-Modifikatoren
        return _P.EXTEND
    if 0xE0020 <= cp <= 0xE007F:          # Tag-Zeichen (Subdivision-Flaggen)
        return _P.EXTEND
    if cp in (0x200C,):                   # ZWNJ
        return _P.EXTEND
    if cp in _PREPEND:
        return _P.PREPEND
    # Hangul
    if 0x1100 <= cp <= 0x115F or 0xA960 <= cp <= 0xA97C:
        return _P.L
    if 0x1160 <= cp <= 0x11A7 or 0xD7B0 <= cp <= 0xD7C6:
        return _P.V
    if 0x11A8 <= cp <= 0x11FF or 0xD7CB <= cp <= 0xD7FB:
        return _P.T
    if _SBASE <= cp < _SBASE + _SCOUNT:
        return _P.LV if (cp - _SBASE) % 28 == 0 else _P.LVT
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Me"):
        return _P.EXTEND
    if cat == "Mc":
        return _P.SPACING_MARK
    if cat in ("Cc", "Zl", "Zp") or (cat == "Cf" and cp not in (0x200D,)):
        return _P.CONTROL
    return _P.OTHER


def iter_graphemes(text: str) -> Iterator[str]:
    """Liefert die Graphem-Cluster von `text` nacheinander."""
    if not text:
        return
    start = 0
    props = [_prop(c) for c in text]
    picto = [_is_picto(ord(c)) for c in text]
    ri_run = 0                      # Anzahl RI im aktuellen Lauf
    in_emoji_seq = picto[0]         # für GB11: ExtPict Extend* ZWJ × ExtPict
    if props[0] is _P.RI:
        ri_run = 1
    for i in range(1, len(text)):
        prev, cur = props[i - 1], props[i]
        brk = True
        if prev is _P.CR and cur is _P.LF:                                 # GB3
            brk = False
        elif prev in (_P.CONTROL, _P.CR, _P.LF) or cur in (_P.CONTROL, _P.CR, _P.LF):
            brk = True                                                     # GB4, GB5
        elif prev is _P.L and cur in (_P.L, _P.V, _P.LV, _P.LVT):          # GB6
            brk = False
        elif prev in (_P.LV, _P.V) and cur in (_P.V, _P.T):                # GB7
            brk = False
        elif prev in (_P.LVT, _P.T) and cur is _P.T:                       # GB8
            brk = False
        elif cur in (_P.EXTEND, _P.ZWJ):                                   # GB9
            brk = False
        elif cur is _P.SPACING_MARK:                                       # GB9a
            brk = False
        elif prev is _P.PREPEND:                                           # GB9b
            brk = False
        elif prev is _P.ZWJ and picto[i] and in_emoji_seq:                 # GB11
            brk = False
        elif prev is _P.RI and cur is _P.RI and ri_run % 2 == 1:           # GB12, GB13
            brk = False

        if brk:
            yield text[start:i]
            start = i
            in_emoji_seq = picto[i]
            ri_run = 1 if cur is _P.RI else 0
        else:
            if cur is _P.RI:
                ri_run += 1
            if picto[i]:
                in_emoji_seq = True
            elif cur not in (_P.EXTEND, _P.ZWJ):
                in_emoji_seq = False
    yield text[start:]


def count_graphemes(text: str) -> int:
    return sum(1 for _ in iter_graphemes(text))


def grapheme_boundaries(text: str) -> list[int]:
    """Codepunkt-Indizes, an denen ein neues Graphem beginnt, plus len(text)."""
    out = [0]
    pos = 0
    for g in iter_graphemes(text):
        pos += len(g)
        out.append(pos)
    return out if text else [0]
