# SPDX-License-Identifier: GPL-3.0-or-later
"""Bildinformationen und Verkleinern über GdkPixbuf (ohne GTK)."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402


@dataclass
class MediaInfo:
    mime: str
    width: int | None
    height: int | None
    bytes: int
    sha256: str


def probe(path: str | Path) -> MediaInfo:
    path = Path(path)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    width = height = None
    fmt, w, h = GdkPixbuf.Pixbuf.get_file_info(str(path))
    if fmt is not None:
        mime = fmt.get_mime_types()[0] if fmt.get_mime_types() else mime
        width, height = w, h
    return MediaInfo(mime, width, height, len(data), sha)


def import_file(src: str | Path, dest_dir: Path) -> tuple[Path, MediaInfo]:
    """Kopiert eine Datei inhaltsadressiert ins Datenverzeichnis."""
    info = probe(src)
    ext = Path(src).suffix.lower() or mimetypes.guess_extension(info.mime) or ""
    dest = dest_dir / f"{info.sha256}{ext}"
    if not dest.exists():
        shutil.copyfile(src, dest)
    return dest, info


def import_bytes(data: bytes, mime: str, dest_dir: Path) -> tuple[Path, MediaInfo]:
    sha = hashlib.sha256(data).hexdigest()
    ext = mimetypes.guess_extension(mime) or ".bin"
    dest = dest_dir / f"{sha}{ext}"
    if not dest.exists():
        dest.write_bytes(data)
    return dest, probe(dest)


def _pixbuf_from_bytes(data: bytes) -> GdkPixbuf.Pixbuf:
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        raise ValueError("Bild konnte nicht gelesen werden")
    return pixbuf.apply_embedded_orientation() or pixbuf


def shrink_to(data: bytes, max_bytes: int, max_dim: int = 2000) -> tuple[bytes, str, int, int]:
    """Verkleinert ein Bild als JPEG unter `max_bytes`.

    Liefert (Daten, MIME, Breite, Höhe). Ist das Bild schon klein genug,
    kommt es unverändert zurück (MIME dann unbekannt → image/jpeg-Annahme
    vermeiden: Aufrufer prüft vorher die Größe).
    """
    pixbuf = _pixbuf_from_bytes(data)
    w, h = pixbuf.get_width(), pixbuf.get_height()
    scale = min(1.0, max_dim / max(w, h))
    quality = 88
    for _attempt in range(12):
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        pb = pixbuf if (nw, nh) == (w, h) else pixbuf.scale_simple(nw, nh,
                                                                   GdkPixbuf.InterpType.BILINEAR)
        if pb.get_has_alpha():
            # JPEG kennt keine Transparenz: auf Weiß legen
            bg = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, nw, nh)
            bg.fill(0xFFFFFFFF)
            pb.composite(bg, 0, 0, nw, nh, 0, 0, 1, 1, GdkPixbuf.InterpType.BILINEAR, 255)
            pb = bg
        ok, out = pb.save_to_bufferv("jpeg", ["quality"], [str(quality)])
        if ok and len(out) <= max_bytes:
            return bytes(out), "image/jpeg", nw, nh
        if quality > 70:
            quality -= 8
        else:
            scale *= 0.8
    raise ValueError("Bild lässt sich nicht ausreichend verkleinern")


def thumbnail_png(path: str | Path, size: int) -> bytes | None:
    """Quadratisches, mittig beschnittenes Vorschaubild als PNG."""
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error:
        return None
    pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
    w, h = pixbuf.get_width(), pixbuf.get_height()
    side = min(w, h)
    square = pixbuf.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
    small = square.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    ok, data = small.save_to_bufferv("png", [], [])
    return bytes(data) if ok else None


def preview_png(path: str | Path, max_dim: int) -> bytes | None:
    """Bild auf höchstens ``max_dim`` Pixel verkleinert, Ausrichtung angewendet, als PNG.

    Geht über GdkPixbuf wie die Miniaturen; ``Gtk.Picture.set_filename`` zeigte
    manche Dateien (z. B. WebP) nicht an.
    """
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error:
        return None
    pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
    w, h = pixbuf.get_width(), pixbuf.get_height()
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        pixbuf = pixbuf.scale_simple(max(1, round(w * scale)), max(1, round(h * scale)),
                                     GdkPixbuf.InterpType.BILINEAR)
    ok, data = pixbuf.save_to_bufferv("png", [], [])
    return bytes(data) if ok else None


def load_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


__all__ = ["MediaInfo", "probe", "import_file", "import_bytes", "shrink_to", "preview_png", "load_bytes",
           "GLib"]
