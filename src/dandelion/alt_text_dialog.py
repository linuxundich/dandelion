# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Adw, Gdk, Gtk

from .core.graphemes import count_graphemes
from .core.models import Media


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/alt-text-dialog.ui")
class DandelionAltTextDialog(Adw.Dialog):
    __gtype_name__ = "DandelionAltTextDialog"

    picture: Gtk.Picture = Gtk.Template.Child()
    text_view: Gtk.TextView = Gtk.Template.Child()
    counter_label: Gtk.Label = Gtk.Template.Child()
    hint_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, media: Media, limit: int | None, limit_platform: str | None,
                 hints: list[str], on_done: Callable[[str], None]) -> None:
        super().__init__()
        self.media = media
        self.limit = limit
        self.limit_platform = limit_platform
        self._on_done = on_done
        if media.is_image:
            self.picture.set_filename(media.path)
        buf = self.text_view.get_buffer()
        buf.set_text(media.alt_text)
        buf.connect("changed", lambda *_: self._update())
        if hints:
            self.hint_label.set_label("\n".join(hints))
            self.hint_label.set_visible(True)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.text_view.add_controller(key)
        self._update()
        self.set_focus(self.text_view)

    def _text(self) -> str:
        buf = self.text_view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _update(self) -> None:
        n = count_graphemes(self._text().strip())
        label = self.counter_label
        for cls in ("error", "warning"):
            label.remove_css_class(cls)
        if self.limit:
            text = _("{n} / {max}").format(n=n, max=self.limit)
            if self.limit_platform:
                text += " · " + _("{platform} has the strictest limit").format(
                    platform=self.limit_platform)
            if n > self.limit:
                label.add_css_class("error")
            elif n > self.limit * 0.9:
                label.add_css_class("warning")
        else:
            text = _("{n} characters").format(n=n)
        label.set_label(text)

    def _on_key(self, _c, keyval: int, _code: int, state: Gdk.ModifierType) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and \
                state & Gdk.ModifierType.CONTROL_MASK:
            self.on_done()
            return True
        return False

    @Gtk.Template.Callback()
    def on_cancel(self, *_args: object) -> None:
        self.close()

    @Gtk.Template.Callback()
    def on_done(self, *_args: object) -> None:
        self._on_done(self._text().strip())
        self.close()
