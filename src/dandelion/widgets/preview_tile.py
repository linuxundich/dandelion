# SPDX-License-Identifier: GPL-3.0-or-later
"""Stilisierte Vorschau eines Beitrags auf einer Plattform (keine Markenlogos)."""

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ..core.counting import find_hashtags, find_mentions, find_urls
from ..core.graphemes import iter_graphemes
from ..net.linkcard import LinkCard
from ..platforms.base import Composition, Count, Platform, PlatformLimits
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


class PreviewTile(Gtk.Box):
    def __init__(self, platform: Platform, profile: Profile, comp: Composition,
                 limits: PlatformLimits, count: Count, avatars: AvatarCache,
                 card: LinkCard | None, accent_hex: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("card")
        self.add_css_class("preview-tile")
        self.add_css_class(platform.style_class)
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [_("Preview for {handle} on {platform}").format(
                                 handle=profile.full_handle, platform=platform.name)])

        # Kopf: Avatar, Name, Handle
        head = Gtk.Box(spacing=10)
        overlay = Gtk.Overlay()
        avatar = Adw.Avatar(size=40, text=profile.title, show_initials=True)
        avatars.apply(avatar, profile.avatar_url)
        overlay.set_child(avatar)
        overlay.add_overlay(platform_badge(profile.platform, 12))
        head.append(overlay)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        name = Gtk.Label(label=profile.display_name or profile.handle, xalign=0, ellipsize=3)
        name.add_css_class("heading")
        handle = Gtk.Label(label=profile.full_handle, xalign=0, ellipsize=3)
        handle.add_css_class("dim-label")
        handle.add_css_class("caption")
        names.append(name)
        names.append(handle)
        head.append(names)
        self.append(head)

        text = platform.display_text(comp.text)
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

        images = [m for m in comp.media if m.is_image]
        if images:
            content.append(self._grid(images, limits.max_images))
        elif card and (card.title or card.description) and \
                (limits.client_link_card or platform.id == "mastodon"):
            content.append(self._card(card))

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

    def _grid(self, images, max_images: int) -> Gtk.Widget:  # type: ignore[no-untyped-def]
        grid = Gtk.Grid(column_spacing=4, row_spacing=4, column_homogeneous=True,
                        row_homogeneous=True)
        grid.add_css_class("preview-grid")
        shown = images[:max_images]
        n = len(shown)
        height = 180 if n == 1 else 120
        for i, m in enumerate(shown):
            pic = Gtk.Picture.new_for_filename(m.path)
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

    def _card(self, card: LinkCard) -> Gtk.Widget:
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
