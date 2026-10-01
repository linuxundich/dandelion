# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Awaitable, Callable
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
    ai_button: Gtk.Button = Gtk.Template.Child()
    ai_revealer: Gtk.Revealer = Gtk.Template.Child()
    ai_status: Gtk.Label = Gtk.Template.Child()
    ai_spinner: Adw.Spinner = Gtk.Template.Child()
    ai_result: Gtk.Label = Gtk.Template.Child()
    ai_accept: Gtk.Button = Gtk.Template.Child()

    def __init__(self, media: Media, limit: int | None, limit_platform: str | None,
                 hints: list[str], on_done: Callable[[str], None],
                 ai_suggest: Callable[[Callable[[], None]], None] | None = None,
                 ai_generate: Callable[[Media, int | None], Awaitable[str]] | None = None,
                 ai_provider: str = "") -> None:
        super().__init__()
        self.media = media
        self.limit = limit
        self.limit_platform = limit_platform
        self._on_done = on_done
        self._ai_confirm = ai_suggest
        self._ai_generate = ai_generate
        self._ai_provider = ai_provider
        self._ai_task = None
        self.ai_button.set_visible(ai_generate is not None and media.is_image)
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
    def on_ai_generate(self, *_args: object) -> None:
        if self._ai_generate is None:
            return
        if self._ai_confirm:
            self._ai_confirm(self._ai_start)
        else:
            self._ai_start()

    def _ai_start(self) -> None:
        from .util import spawn
        self.ai_status.set_label(_("Suggestion from {provider}").format(
            provider=self._ai_provider))
        self.ai_result.set_label(_("Analyzing the image"))
        self.ai_result.add_css_class("dim-label")
        self.ai_spinner.set_visible(True)
        self.ai_accept.set_sensitive(False)
        self.ai_revealer.set_reveal_child(True)

        async def run() -> None:
            text = await self._ai_generate(self.media, self.limit)  # type: ignore[misc]
            self.ai_spinner.set_visible(False)
            self.ai_result.remove_css_class("dim-label")
            self.ai_result.set_label(text)
            self.ai_accept.set_sensitive(bool(text.strip()))

        def failed(e: BaseException) -> None:
            self.ai_spinner.set_visible(False)
            self.ai_result.set_label(getattr(e, "message", None) or str(e))

        self._ai_task = spawn(run(), on_error=failed)

    @Gtk.Template.Callback()
    def on_ai_discard(self, *_args: object) -> None:
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
        self.ai_revealer.set_reveal_child(False)

    @Gtk.Template.Callback()
    def on_ai_accept(self, *_args: object) -> None:
        buf = self.text_view.get_buffer()
        buf.begin_user_action()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        buf.insert(buf.get_start_iter(), self.ai_result.get_label())
        buf.end_user_action()
        self.ai_revealer.set_reveal_child(False)
        self.text_view.grab_focus()

    @Gtk.Template.Callback()
    def on_cancel(self, *_args: object) -> None:
        self.close()

    @Gtk.Template.Callback()
    def on_done(self, *_args: object) -> None:
        self._on_done(self._text().strip())
        self.close()
