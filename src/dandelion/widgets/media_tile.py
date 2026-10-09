# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Gdk, Gio, GLib, Gtk

from ..core import imaging

from ..core.models import Media


class MediaTile(Gtk.Overlay):
    """Vorschaubild mit ALT-Abzeichen und Entfernen-Knopf."""

    def __init__(self, media: Media, index: int, total: int, alt_required: bool, *,
                 on_edit_alt: Callable[[Media], None], on_remove: Callable[[Media], None],
                 on_move: Callable[[Media, int], None]) -> None:
        super().__init__()
        self.media = media
        self.add_css_class("media-tile")
        self.set_size_request(112, 112)

        pic = Gtk.Image(icon_name="video-x-generic-symbolic", pixel_size=48)
        if media.is_image:
            data = imaging.thumbnail_png(media.path, 224)
            if data:
                pic = Gtk.Image.new_from_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(data)))
                pic.set_pixel_size(112)
        pic.set_size_request(112, 112)
        frame = Gtk.Button(child=pic, tooltip_text=_("Edit alt text"))
        frame.add_css_class("media-button")
        frame.connect("clicked", lambda *_: on_edit_alt(media))
        frame.update_property([Gtk.AccessibleProperty.LABEL],
                              [_("Media {n}, edit alt text").format(n=index + 1)])
        self.set_child(frame)

        has_alt = bool(media.alt_text.strip())
        badge = Gtk.Button(halign=Gtk.Align.START, valign=Gtk.Align.END, margin_start=4,
                           margin_bottom=4)
        content = Gtk.Box(spacing=3)
        content.append(Gtk.Label(label="ALT"))
        content.append(Gtk.Image(icon_name="object-select-symbolic" if has_alt
                                 else "window-close-symbolic", pixel_size=12))
        badge.set_child(content)
        badge.add_css_class("alt-badge")
        if not has_alt:
            badge.add_css_class("missing" if alt_required else "optional")
        badge.connect("clicked", lambda *_: on_edit_alt(media))
        label = (_("Alt text present for media {n}") if has_alt
                 else _("Alt text missing for media {n}")).format(n=index + 1)
        badge.set_tooltip_text(label)
        badge.update_property([Gtk.AccessibleProperty.LABEL], [label])
        self.add_overlay(badge)

        remove = Gtk.Button(icon_name="window-close-symbolic", halign=Gtk.Align.END,
                            valign=Gtk.Align.START, margin_end=4, margin_top=4,
                            tooltip_text=_("Remove"))
        remove.add_css_class("osd")
        remove.add_css_class("circular")
        remove.update_property([Gtk.AccessibleProperty.LABEL],
                               [_("Remove media {n}").format(n=index + 1)])
        remove.connect("clicked", lambda *_: on_remove(media))
        self.add_overlay(remove)

        # Kontextmenü zum Umsortieren
        group = Gio.SimpleActionGroup()
        for name, delta, enabled in (("left", -1, index > 0), ("right", 1, index < total - 1)):
            act = Gio.SimpleAction.new(name, None)
            act.set_enabled(enabled)
            act.connect("activate", lambda _a, _p, d=delta: on_move(media, d))
            group.add_action(act)
        alt = Gio.SimpleAction.new("alt", None)
        alt.connect("activate", lambda *_: on_edit_alt(media))
        group.add_action(alt)
        rm = Gio.SimpleAction.new("remove", None)
        rm.connect("activate", lambda *_: on_remove(media))
        group.add_action(rm)
        self.insert_action_group("tile", group)
        menu = Gio.Menu()
        menu.append(_("Edit Alt Text"), "tile.alt")
        move = Gio.Menu()
        move.append(_("Move Left"), "tile.left")
        move.append(_("Move Right"), "tile.right")
        menu.append_section(None, move)
        danger = Gio.Menu()
        danger.append(_("Remove"), "tile.remove")
        menu.append_section(None, danger)
        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self)
        popover.set_has_arrow(False)
        click = Gtk.GestureClick(button=3)
        click.connect("pressed", lambda *_: popover.popup())
        self.add_controller(click)
        self.connect("destroy", lambda *_: popover.unparent())
