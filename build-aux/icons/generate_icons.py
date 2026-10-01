#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Erzeugt das App-Icon und das symbolische Icon von Dandelion.

Die Geometrie der Pusteblume (radiale Strahlen, Schirmchen) wird berechnet,
damit sie gleichmäßig bleibt. Ausgabe nach data/icons/hicolor/.

    python3 build-aux/icons/generate_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_ID = "de.linuxundich.Dandelion"

# GNOME-Palette (https://developer.gnome.org/hig/reference/palette.html)
BLUE1, BLUE2, BLUE3, BLUE4, BLUE5 = "#99c1f1", "#62a0ea", "#3584e4", "#1c71d8", "#1a5fb4"
GREEN3, GREEN4, GREEN5 = "#33d17a", "#2ec27e", "#26a269"
BROWN2, BROWN3, BROWN4 = "#cdab8f", "#b5835a", "#865e3c"
LIGHT1, LIGHT2, LIGHT3 = "#ffffff", "#f6f5f4", "#deddda"
DARK = "#2e3436"  # Standardfarbe für symbolische Icons


def f(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def pol(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def parachute(x: float, y: float, deg: float, stalk: float, fan: float,
              spread: float = 70, rays: int = 5) -> list[tuple[float, float, float, float]]:
    """Linien eines Schirmchens: Stiel von (x, y) in Richtung deg, oben ein Fächer."""
    tx, ty = pol(x, y, stalk, deg)
    lines = [(x, y, tx, ty)]
    for i in range(rays):
        d = deg - spread / 2 + spread * i / (rays - 1)
        ex, ey = pol(tx, ty, fan, d)
        lines.append((tx, ty, ex, ey))
    return lines


# --------------------------------------------------------------------------
# Vollfarbiges Icon, 128 × 128
# --------------------------------------------------------------------------

def app_icon() -> str:
    cx, cy, r = 64.0, 60.0, 54.0       # Himmelsscheibe
    hx, hy = 52.0, 56.0                # Mitte des Samenkopfs
    head_r = 26.0
    gap = (-62.0, -8.0)                # Lücke oben rechts: hier sind Samen weggeflogen

    out: list[str] = []
    out.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="sky" x1="0" y1="{f(cy - r)}" x2="0" y2="{f(cy + r)}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{BLUE2}"/>
      <stop offset="1" stop-color="{BLUE4}"/>
    </linearGradient>
    <radialGradient id="glow" cx="{f(hx)}" cy="{f(hy)}" r="{f(head_r + 4)}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{LIGHT1}" stop-opacity="0.5"/>
      <stop offset="0.75" stop-color="{LIGHT1}" stop-opacity="0.3"/>
      <stop offset="1" stop-color="{LIGHT1}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="disc"><circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"/></clipPath>
  </defs>''')

    # Dezenter Schlagschatten, Dicke der Scheibe, Scheibe
    out.append(f'  <ellipse cx="{f(cx)}" cy="{f(cy + r + 5)}" rx="{f(r * 0.75)}" ry="3.5" fill="#000" opacity="0.1"/>')
    out.append(f'  <circle cx="{f(cx)}" cy="{f(cy + 5)}" r="{f(r)}" fill="{BLUE5}"/>')
    out.append(f'  <circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="url(#sky)"/>')

    out.append('  <g clip-path="url(#disc)">')
    # Hügel am unteren Rand
    out.append(f'    <path d="M 0 {f(cy + 30)} C 40 {f(cy + 22)} 90 {f(cy + 30)} 128 {f(cy + 20)} L 128 128 L 0 128 Z" fill="{GREEN4}"/>')
    out.append(f'    <path d="M 0 {f(cy + 40)} C 50 {f(cy + 32)} 80 {f(cy + 40)} 128 {f(cy + 34)} L 128 128 L 0 128 Z" fill="{GREEN5}"/>')
    # Stiel
    out.append(f'    <path d="M {f(hx)} {f(hy + 6)} C {f(hx + 3)} {f(hy + 24)} {f(hx - 3)} {f(hy + 38)} {f(hx + 1)} {f(cy + r)}" '
               f'fill="none" stroke="{GREEN3}" stroke-width="4" stroke-linecap="round"/>')
    out.append('  </g>')

    # Samenkopf: weicher Schein, Strahlen mit Schirmchen
    out.append(f'  <circle cx="{f(hx)}" cy="{f(hy)}" r="{f(head_r + 4)}" fill="url(#glow)"/>')
    rays: list[tuple[float, float, float, float]] = []
    fans: list[tuple[float, float, float, float]] = []
    tufts: list[tuple[float, float]] = []
    n = 32
    for i in range(n):
        deg = -90 + 360 * i / n
        if gap[0] < deg < gap[1] or gap[0] < deg - 360 < gap[1]:
            continue
        x0, y0 = pol(hx, hy, 7, deg)
        x1, y1 = pol(hx, hy, head_r - 5, deg)
        rays.append((x0, y0, x1, y1))
        for _, _, ex, ey in parachute(x1, y1, deg, 0, 5, spread=100, rays=4)[1:]:
            fans.append((x1, y1, ex, ey))
            tufts.append((ex, ey))
    def lines_d(ls):
        return " ".join(f"M {f(a)} {f(b)} L {f(c)} {f(e)}" for a, b, c, e in ls)
    out.append(f'  <path d="{lines_d(rays)}" fill="none" stroke="{LIGHT1}" stroke-width="1.1" stroke-linecap="round" opacity="0.9"/>')
    out.append(f'  <path d="{lines_d(fans)}" fill="none" stroke="{LIGHT1}" stroke-width="0.9" stroke-linecap="round"/>')
    out.append("  " + "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="1.15" fill="{LIGHT1}"/>' for x, y in tufts))
    # Fruchtboden
    out.append(f'  <circle cx="{f(hx)}" cy="{f(hy + 1)}" r="7.5" fill="{BROWN4}"/>')
    out.append(f'  <circle cx="{f(hx)}" cy="{f(hy)}" r="7" fill="{BROWN3}"/>')
    out.append(f'  <circle cx="{f(hx - 2.2)}" cy="{f(hy - 2.2)}" r="2.4" fill="{BROWN2}"/>')

    # Fliegende Samen: ein Beitrag verteilt sich auf mehrere Ziele
    seeds = [  # (x, y, Flugrichtung in Grad, Größe)
        (81.0, 34.0, -60.0, 0.9),
        (90.0, 49.0, -35.0, 0.9),
        (87.0, 66.0, -12.0, 0.85),
    ]
    trail_d = []
    for (sx, sy, deg, s) in seeds:
        a = math.degrees(math.atan2(sy - hy, sx - hx))
        bx, by = pol(hx, hy, head_r + 1, a)
        ex, ey = pol(sx, sy, 3.5, a + 180)
        mx, my = (bx + ex) / 2, (by + ey) / 2 - 5
        trail_d.append(f"M {f(bx)} {f(by)} Q {f(mx)} {f(my)} {f(ex)} {f(ey)}")
    out.append(f'  <path d="{" ".join(trail_d)}" fill="none" stroke="{LIGHT1}" stroke-width="1.4" '
               f'stroke-linecap="round" stroke-dasharray="0.1 3.6" opacity="0.65"/>')
    for (sx, sy, deg, s) in seeds:
        lines = parachute(sx, sy, deg, 9 * s, 6.5 * s, spread=120, rays=5)
        out.append(f'  <path d="{lines_d(lines[:1])}" fill="none" stroke="{LIGHT1}" stroke-width="{f(1.6 * s)}" stroke-linecap="round"/>')
        out.append(f'  <path d="{lines_d(lines[1:])}" fill="none" stroke="{LIGHT1}" stroke-width="{f(1.2 * s)}" stroke-linecap="round"/>')
        for _, _, ex, ey in lines[1:]:
            out.append(f'  <circle cx="{f(ex)}" cy="{f(ey)}" r="{f(1.3 * s)}" fill="{LIGHT1}"/>')
        out.append(f'  <ellipse cx="{f(sx)}" cy="{f(sy)}" rx="{f(2.8 * s)}" ry="{f(1.6 * s)}" '
                   f'transform="rotate({f(deg)} {f(sx)} {f(sy)})" fill="{BROWN3}"/>')

    out.append("</svg>\n")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Symbolisches Icon, 16 × 16, nur gefüllte Flächen (GTK färbt fill um)
# --------------------------------------------------------------------------

def bar(x0: float, y0: float, x1: float, y1: float, w: float) -> str:
    """Strecke als gefülltes Polygon mit runden Enden (als Pfad)."""
    ang = math.atan2(y1 - y0, x1 - x0)
    nx, ny = -math.sin(ang) * w / 2, math.cos(ang) * w / 2
    r = w / 2
    return (f"M {f(x0 + nx)} {f(y0 + ny)} L {f(x1 + nx)} {f(y1 + ny)} "
            f"A {f(r)} {f(r)} 0 0 0 {f(x1 - nx)} {f(y1 - ny)} "
            f"L {f(x0 - nx)} {f(y0 - ny)} A {f(r)} {f(r)} 0 0 0 {f(x0 + nx)} {f(y0 + ny)} Z")


def dot(x: float, y: float, r: float) -> str:
    return (f"M {f(x - r)} {f(y)} A {f(r)} {f(r)} 0 1 0 {f(x + r)} {f(y)} "
            f"A {f(r)} {f(r)} 0 1 0 {f(x - r)} {f(y)} Z")


def symbolic_icon() -> str:
    hx, hy = 6.0, 7.5
    parts = [dot(hx, hy, 1.75)]
    # Strahlen im 45°-Raster (pixelgenau), oben rechts fehlen Samen
    for deg in (-90, 180, 135, 90, 45, -135):
        x0, y0 = pol(hx, hy, 2.6, deg)
        x1, y1 = pol(hx, hy, 4.4, deg)
        parts.append(bar(x0, y0, x1, y1, 1.1))
        parts.append(dot(*pol(hx, hy, 5.0, deg), 1.0))
    # Stiel
    parts.append(bar(hx, hy + 2.4, hx, 15.3, 1.3))
    # Zwei fliegende Samen
    for sx, sy in ((10.6, 5.4), (12.4, 10.0)):
        deg = -45
        tx, ty = pol(sx, sy, 2.4, deg)
        parts.append(bar(sx, sy, tx, ty, 1.0))
        parts.append(dot(sx, sy, 0.9))
        parts.append(dot(tx, ty, 1.3))
    # Einzelne Pfade, damit sich Überlappungen nicht gegenseitig auslöschen
    body = "".join(f'  <path d="{d}"/>\n' for d in parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">\n'
            f'<g fill="{DARK}">\n{body}</g>\n</svg>\n')


def main() -> None:
    base = ROOT / "data" / "icons" / "hicolor"
    sc = base / "scalable" / "apps" / f"{APP_ID}.svg"
    sy = base / "symbolic" / "apps" / f"{APP_ID}-symbolic.svg"
    for p, content in ((sc, app_icon()), (sy, symbolic_icon())):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
