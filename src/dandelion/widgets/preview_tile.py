# SPDX-License-Identifier: GPL-3.0-or-later
"""Stilisierte Vorschau eines Beitrags auf einer Plattform (keine Markenlogos)."""

from __future__ import annotations

from gettext import gettext as _
from gettext import ngettext

from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ..core import imaging
from ..core.counting import find_hashtags, find_mentions, find_urls
from ..core.graphemes import iter_graphemes
from ..net.linkcard import LinkCard
from ..platforms.base import Composition, Count, Issue, Platform, PlatformLimits
from ..core.models import Profile
from .avatars import AvatarCache
from .profile_chip import platform_badge


def _markup(text: str) -> str:
    """Hebt URLs, Mentions und Hashtags hervor (Pango-Markup)."""
    spans = sorted(
        [(s.start, s.end) for s in find_urls(text)]
        + [(s.start, s.end) for s in find_mentions(text)]
        + [(s.start, s.end) for s in find_hashtags(text)])
    out, last = [], 0
    for start, end in spans:
        if start < last:
            continue
        out.append(GLib.markup_escape_text(text[last:start]))
        out.append(f'<span foreground="#{{accent}}">{GLib.markup_escape_text(text[start:end])}</span>')
        last = end
    out.append(GLib.markup_escape_text(text[last:]))
    return "".join(out)


def _truncate(text: str, limit: int | None) -> tuple[str, bool]:
    if not limit:
        return text, False
    out, n = [], 0
    for g in iter_graphemes(text):
        if n >= limit:
            return "".join(out).rstrip() + "…", True
        out.append(g)
        n += 1
    return text, False


COMPACT_GRAPHEMES = 160
COMPACT_LINES = 3


def _compact_text(text: str) -> str:
    """Kürzt auf etwa vier Zeilen: höchstens drei Absatzzeilen bzw. 160 Grapheme."""
    lines = text.strip().split("\n")
    cut = "\n".join(lines[:COMPACT_LINES]).rstrip()
    shortened, truncated = _truncate(cut, COMPACT_GRAPHEMES)
    if truncated:
        return shortened
    return cut + "…" if len(lines) > COMPACT_LINES else cut


class PreviewTile(Gtk.Box):
    """Vorschau für ein Profil oder eine Gruppe gleich aussehender Profile."""

    def __init__(self, platform: Platform, profiles: list[Profile], comp: Composition,
                 limits: PlatformLimits, count: Count, avatars: AvatarCache,
                 card: LinkCard | None, accent_hex: str, issues: list[Issue] | None = None,
                 compact: bool = False, parts: list[str] | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8 if compact else 10)
        self.compact = compact
        self.profile_ids = {p.id for p in profiles}
        self.add_css_class("card")
        self.add_css_class("preview-tile")
        self.add_css_class(platform.style_class)
        handles = ", ".join(p.full_handle for p in profiles)
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [_("Preview for {handle} on {platform}").format(
                                 handle=handles, platform=platform.name)])

        # Kopf: Avatar(e), Name, Handle(s)
        head = Gtk.Box(spacing=10)
        head.append(self._avatars(profiles, platform.id, avatars))
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER,
                        hexpand=True)
        first = profiles[0]
        if len(profiles) == 1:
            title = first.display_name or first.handle
            subtitle = first.full_handle
        else:
            title = ngettext("{platform} · {n} profile", "{platform} · {n} profiles",
                             len(profiles)).format(platform=platform.name, n=len(profiles))
            subtitle = handles
        name = Gtk.Label(label=title, xalign=0, ellipsize=3)
        name.add_css_class("heading")
        handle = Gtk.Label(label=subtitle, xalign=0, ellipsize=3, tooltip_text=handles)
        handle.add_css_class("dim-label")
        handle.add_css_class("caption")
        names.append(name)
        names.append(handle)
        head.append(names)
        self.append(head)

        parts = parts if parts and len(parts) > 1 else None
        text = platform.display_text(parts[0] if parts else comp.text)
        shown, truncated = _truncate(text, limits.preview_truncate)
        body = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0, selectable=False)
        body.set_markup(_markup(shown).replace("{accent}", accent_hex))
        body.add_css_class("preview-text")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        if text.strip():
            content.append(body)
        if truncated:
            more = Gtk.Label(label=_("Show more"), xalign=0)
            more.add_css_class("accent")
            content.append(more)
        elif compact:
            short = _compact_text(shown)
            if short != shown:
                # Kompakt: gekürzter Text, auf Wunsch aufklappen
                full_markup = _markup(shown).replace("{accent}", accent_hex)
                short_markup = _markup(short).replace("{accent}", accent_hex)
                body.set_markup(short_markup)
                toggle = Gtk.Button(label=_("Show more"), halign=Gtk.Align.START)
                toggle.add_css_class("flat")
                toggle.add_css_class("small-button")
                toggle.connect("clicked", self._toggle_body, body, short_markup, full_markup)
                content.append(toggle)

        images = [m for m in comp.media if m.is_image]
        if images:
            content.append(self._grid(images, limits.max_images))
        elif card and (card.title or card.description):
            content.append(self._card(card))

        if parts:
            content.append(self._thread(parts[1:], platform, accent_hex, compact))

        if comp.content_warning and limits.supports_content_warning:
            cw = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            cw.add_css_class("preview-cw")
            row = Gtk.Box(spacing=6)
            row.append(Gtk.Image(icon_name="dialog-warning-symbolic"))
            row.append(Gtk.Label(label=comp.content_warning, xalign=0, wrap=True, hexpand=True))
            toggle = Gtk.ToggleButton(label=_("Show"))
            toggle.add_css_class("flat")
            row.append(toggle)
            cw.append(row)
            revealer = Gtk.Revealer(child=content)
            toggle.bind_property("active", revealer, "reveal-child", 0)
            toggle.connect("toggled", lambda t: t.set_label(_("Hide") if t.get_active()
                                                            else _("Show")))
            cw.append(revealer)
            self.append(cw)
        else:
            self.append(content)

        # Fuß: Plattform und Zähler
        foot = Gtk.Box(spacing=6)
        plat = Gtk.Label(label=platform.name, xalign=0, hexpand=True)
        plat.add_css_class("caption")
        plat.add_css_class("dim-label")
        foot.append(plat)
        counter = Gtk.Label(label=f"{count.used} / {count.limit}")
        counter.add_css_class("caption")
        counter.add_css_class("numeric")
        if count.over:
            counter.add_css_class("error")
        elif count.ratio >= 0.9:
            counter.add_css_class("warning")
        foot.append(counter)
        self.append(foot)

        # Probleme dieser Kachel direkt anzeigen
        for issue in (issues or [])[:4]:
            row = Gtk.Box(spacing=6)
            icon = Gtk.Image(icon_name="dialog-error-symbolic" if issue.severity == "error"
                             else "dialog-warning-symbolic", valign=Gtk.Align.START)
            icon.add_css_class("error" if issue.severity == "error" else "warning")
            row.append(icon)
            label = Gtk.Label(label=issue.message, xalign=0, wrap=True, hexpand=True)
            label.add_css_class("caption")
            row.append(label)
            self.append(row)
        if issues:
            worst = "error" if any(i.severity == "error" for i in issues) else "warning"
            self.add_css_class(f"has-{worst}")

    def _thread(self, rest: list[str], platform: Platform, accent_hex: str,
                compact: bool) -> Gtk.Widget:
        """Weitere Teile eines Threads, kompakt nur als Hinweis."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("preview-thread")
        if compact:
            hint = Gtk.Label(label=ngettext("Thread: {n} more part", "Thread: {n} more parts",
                                            len(rest)).format(n=len(rest)), xalign=0)
            hint.add_css_class("caption-heading")
            hint.add_css_class("accent")
            box.append(hint)
            return box
        for i, part in enumerate(rest, 2):
            label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0)
            label.set_markup(_markup(platform.display_text(part)).replace("{accent}", accent_hex))
            label.add_css_class("preview-text")
            label.update_property([Gtk.AccessibleProperty.LABEL],
                                  [_("Part {i}: {text}").format(i=i, text=part)])
            box.append(label)
        return box

    @staticmethod
    def _avatars(profiles: list[Profile], platform_id: str, avatars: AvatarCache) -> Gtk.Widget:
        """Ein Avatar oder bis zu drei überlappende, dazu der Plattform-Punkt."""
        shown = profiles[:3]
        size = 40 if len(shown) == 1 else 32
        step = size - 12
        fixed = Gtk.Fixed(width_request=size + step * (len(shown) - 1), height_request=size,
                          valign=Gtk.Align.CENTER)
        for i, p in enumerate(reversed(shown)):
            avatar = Adw.Avatar(size=size, text=p.title, show_initials=True)
            avatar.add_css_class("stacked-avatar")
            avatars.apply(avatar, p.avatar_url)
            fixed.put(avatar, step * (len(shown) - 1 - i), 0)
        overlay = Gtk.Overlay(child=fixed, valign=Gtk.Align.CENTER)
        overlay.add_overlay(platform_badge(platform_id, 12))
        return overlay

    def _grid(self, images, max_images: int) -> Gtk.Widget:  # type: ignore[no-untyped-def]
        grid = Gtk.Grid(column_spacing=4, row_spacing=4, column_homogeneous=True,
                        row_homogeneous=True)
        grid.add_css_class("preview-grid")
        shown = images[:max_images]
        n = len(shown)
        if self.compact:
            height = 110 if n == 1 else 72
        else:
            height = 180 if n == 1 else 120
        for i, m in enumerate(shown):
            png = imaging.preview_png(m.path, 800)
            pic = Gtk.Picture.new_for_paintable(
                Gdk.Texture.new_from_bytes(GLib.Bytes.new(png)) if png else None)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_can_shrink(True)
            pic.set_size_request(-1, height if n != 3 or i == 0 else height // 2 - 2)
            pic.set_alternative_text(m.alt_text or None)
            frame = Gtk.Overlay(child=pic, overflow=Gtk.Overflow.HIDDEN)
            frame.add_css_class("preview-image")
            if m.alt_text.strip():
                alt = Gtk.Label(label="ALT", halign=Gtk.Align.START, valign=Gtk.Align.END,
                                margin_start=4, margin_bottom=4)
                alt.add_css_class("alt-chip")
                frame.add_overlay(alt)
            if n == 1:
                grid.attach(frame, 0, 0, 2, 1)
            elif n == 2:
                grid.attach(frame, i, 0, 1, 1)
            elif n == 3:
                if i == 0:
                    grid.attach(frame, 0, 0, 1, 2)
                else:
                    grid.attach(frame, 1, i - 1, 1, 1)
            else:
                grid.attach(frame, i % 2, i // 2, 1, 1)
        return grid

    @staticmethod
    def _toggle_body(button: Gtk.Button, body: Gtk.Label, short: str, full: str) -> None:
        expanded = button.get_label() == _("Show less")
        body.set_markup(short if expanded else full)
        button.set_label(_("Show more") if expanded else _("Show less"))

    def _texture(self, card: LinkCard) -> Gdk.Texture | None:
        if not card.image_data:
            return None
        try:
            return Gdk.Texture.new_from_bytes(GLib.Bytes.new(card.image_data))
        except GLib.Error:
            return None

    def _card(self, card: LinkCard) -> Gtk.Widget:
        if self.compact:
            return self._card_compact(card)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, overflow=Gtk.Overflow.HIDDEN)
        box.add_css_class("preview-card")
        if card.image_data:
            try:
                tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(card.image_data))
                pic = Gtk.Picture.new_for_paintable(tex)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                pic.set_size_request(-1, 140)
                pic.set_can_shrink(True)
                box.append(pic)
            except GLib.Error:
                pass
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_start=10,
                       margin_end=10, margin_top=8, margin_bottom=8)
        site = Gtk.Label(label=card.site, xalign=0, ellipsize=3)
        site.add_css_class("caption")
        site.add_css_class("dim-label")
        title = Gtk.Label(label=card.title, xalign=0, wrap=True, lines=2, ellipsize=3)
        title.add_css_class("heading")
        text.append(site)
        text.append(title)
        if card.description:
            desc = Gtk.Label(label=card.description, xalign=0, wrap=True, lines=2, ellipsize=3)
            desc.add_css_class("caption")
            text.append(desc)
        box.append(text)
        return box

    def _card_compact(self, card: LinkCard) -> Gtk.Widget:
        """Link-Karte als eine Zeile: kleines Vorschaubild, Website und Titel."""
        box = Gtk.Box(spacing=10, overflow=Gtk.Overflow.HIDDEN)
        box.add_css_class("preview-card")
        tex = self._texture(card)
        if tex is not None:
            pic = Gtk.Picture.new_for_paintable(tex)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_can_shrink(True)
            pic.set_size_request(64, 64)
            box.append(pic)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER,
                       margin_top=6, margin_bottom=6, margin_end=10,
                       margin_start=0 if tex is not None else 10, hexpand=True)
        site = Gtk.Label(label=card.site, xalign=0, ellipsize=3)
        site.add_css_class("caption")
        site.add_css_class("dim-label")
        title = Gtk.Label(label=card.title or card.description, xalign=0, wrap=True, lines=2,
                          ellipsize=3)
        title.add_css_class("caption-heading")
        text.append(site)
        text.append(title)
        box.append(text)
        return box
