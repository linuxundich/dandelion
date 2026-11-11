# SPDX-License-Identifier: GPL-3.0-or-later
"""Kleines Schreibfenster im Deck: Antwort, Zitat oder neuer Beitrag eines Profils.

Der volle Composer (Varianten, Threads, KI, Planen) bleibt im Modus *Write*.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk, Pango

from .core.models import Profile
from .platforms.base import Composition, PlatformError
from .reader.base import FeedPost
from .util import spawn
from .widgets.feed_rows import excerpt, post_text

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

log = logging.getLogger(__name__)

VISIBILITIES = [("public", _("Public")), ("unlisted", _("Quiet public")),
                ("private", _("Followers only")), ("direct", _("Mentioned people only"))]
TITLES = {"new": _("New Post"), "reply": _("Reply"), "quote": _("Quote")}
DONE = {"new": _("Posted"), "reply": _("Reply sent"), "quote": _("Quote sent")}


class ComposeSheet(Adw.Dialog):
    __gtype_name__ = "DandelionComposeSheet"

    def __init__(self, app: DandelionApplication, win: DandelionWindow, profile: Profile,
                 mode: str = "new", target: FeedPost | None = None,
                 on_sent: Callable[[], None] | None = None) -> None:
        super().__init__(title=TITLES[mode], content_width=480, content_height=440)
        self.app, self.win, self.profile = app, win, profile
        self.mode, self.target, self.on_sent = mode, target, on_sent
        self.platform = app.registry.get(profile.platform)
        self.limits = self.platform.limits_for(profile)
        self.is_mastodon = profile.platform == "mastodon"

        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda *_a: self.close())
        header.pack_start(cancel)
        self.send_button = Gtk.Button(label={"new": _("Post"), "reply": _("Reply"),
                                             "quote": _("Quote")}[mode])
        self.send_button.add_css_class("suggested-action")
        self.send_button.connect("clicked", lambda *_a: self._send())
        header.pack_end(self.send_button)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                       margin_bottom=12, margin_start=12, margin_end=12)

        if target is not None:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.add_css_class("feed-card")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8,
                            margin_bottom=8, margin_start=10, margin_end=10)
            who = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
            who.set_markup(f"<b>{GLib.markup_escape_text(target.account.name)}</b>  "
                           f"<span alpha='60%'>@{GLib.markup_escape_text(target.account.acct)}</span>")
            inner.append(who)
            inner.append(Gtk.Label(label=excerpt(post_text(target), 220), xalign=0, wrap=True,
                                   lines=3, ellipsize=Pango.EllipsizeMode.END))
            card.append(inner)
            body.append(card)

        sender = Gtk.Box(spacing=8)
        sender.append(Gtk.Label(label=_("From"), css_classes=["dim-label"]))
        sender.append(Gtk.Label(label=profile.full_handle, xalign=0, hexpand=True,
                                ellipsize=Pango.EllipsizeMode.END))
        body.append(sender)

        self.cw_entry = Gtk.Entry(placeholder_text=_("Content warning"), visible=False)
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8, bottom_margin=8,
                                 left_margin=10, right_margin=10)
        self.text.add_css_class("feed-compose")
        self.text.update_property([Gtk.AccessibleProperty.LABEL], [TITLES[mode]])
        scroller = Gtk.ScrolledWindow(child=self.text, vexpand=True, min_content_height=120,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add_css_class("card")
        body.append(self.cw_entry)
        body.append(scroller)

        tools = Gtk.Box(spacing=8)
        if self.is_mastodon:
            self.cw_toggle = Gtk.ToggleButton(label=_("CW"), tooltip_text=_("Content warning"))
            self.cw_toggle.connect("toggled", self._on_cw)
            tools.append(self.cw_toggle)
            self.visibility = Gtk.DropDown(model=Gtk.StringList.new([v[1] for v in VISIBILITIES]))
            default = target.visibility if target and target.visibility in dict(VISIBILITIES) \
                else "public"
            self.visibility.set_selected([v[0] for v in VISIBILITIES].index(default))
            tools.append(self.visibility)
        tools.append(Gtk.Box(hexpand=True))
        self.counter = Gtk.Label()
        self.counter.add_css_class("numeric")
        tools.append(self.counter)
        body.append(tools)

        self.error = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.error.add_css_class("error")
        body.append(self.error)

        view = Adw.ToolbarView(content=body)
        view.add_top_bar(header)
        self.set_child(view)
        self.set_default_widget(self.send_button)

        buffer = self.text.get_buffer()
        if mode == "reply" and self.is_mastodon and target and \
                target.account.acct.lower() != profile.handle.lower():
            buffer.set_text(f"@{target.account.acct} ")
        buffer.connect("changed", lambda *_a: self._update())
        self.cw_entry.connect("changed", lambda *_a: self._update())
        self._update()
        GLib.idle_add(self._focus)

    def _focus(self) -> bool:
        self.text.grab_focus()
        buffer = self.text.get_buffer()
        buffer.place_cursor(buffer.get_end_iter())
        return GLib.SOURCE_REMOVE

    def _on_cw(self, toggle: Gtk.ToggleButton) -> None:
        self.cw_entry.set_visible(toggle.get_active())
        self._update()

    # -- Inhalt -------------------------------------------------------------
    def _composition(self) -> Composition:
        buffer = self.text.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()
        cw = self.cw_entry.get_text().strip() if self.is_mastodon and self.cw_entry.get_visible() \
            else ""
        visibility = VISIBILITIES[self.visibility.get_selected()][0] if self.is_mastodon else None
        return Composition(text=text, content_warning=cw, visibility=visibility)

    def _update(self) -> None:
        comp = self._composition()
        count = self.platform.count(comp, self.limits)
        self.counter.set_label(f"{count.used} / {count.limit}")
        (self.counter.add_css_class if count.over else self.counter.remove_css_class)("error")
        self.send_button.set_sensitive(bool(comp.text) and not count.over)

    # -- Senden -------------------------------------------------------------
    def _send(self) -> None:
        comp = self._composition()
        self.send_button.set_sensitive(False)
        self.error.set_visible(False)

        async def run() -> None:
            try:
                await self.app.reader.send(
                    self.profile, comp,
                    reply_to=self.target if self.mode == "reply" else None,
                    quote=self.target if self.mode == "quote" else None)
            except PlatformError as e:
                self._fail(e.message)
                return
            except Exception:
                log.exception("Beitrag konnte nicht gesendet werden")
                self._fail(_("The post could not be sent."))
                return
            self.close()
            self.win.toast(DONE[self.mode])
            if self.on_sent:
                self.on_sent()

        spawn(run())

    def _fail(self, message: str) -> None:
        self.error.set_label(message)
        self.error.set_visible(True)
        self._update()
