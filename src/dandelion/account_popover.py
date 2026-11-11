# SPDX-License-Identifier: GPL-3.0-or-later
"""Popover zu einem Konto: Folgen, Stummschalten, Blockieren."""

from __future__ import annotations

import logging
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk, Pango

from .platforms.base import PlatformError
from .reader.base import FeedAccount, Relationship
from .util import spawn
from .widgets.feed_rows import avatar_for, open_url

if TYPE_CHECKING:
    from .feedview import FeedView

log = logging.getLogger(__name__)


class AccountPopover(Gtk.Popover):
    def __init__(self, view: FeedView, account: FeedAccount) -> None:
        super().__init__()
        self.view, self.account = view, account
        self.profile = view.profile
        self.service = view.service
        self.rel: Relationship | None = None
        self.is_self = account.id == view.profile.remote_id

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12,
                      margin_bottom=12, margin_start=12, margin_end=12, width_request=260)
        head = Gtk.Box(spacing=10)
        head.append(avatar_for(account, view.column.deck.avatars, 48))
        who = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        name = Gtk.Label(label=account.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        name.add_css_class("heading")
        who.append(name)
        handle = Gtk.Label(label=f"@{account.acct}", xalign=0, ellipsize=Pango.EllipsizeMode.END)
        handle.add_css_class("dim-label")
        handle.add_css_class("caption")
        who.append(handle)
        head.append(who)
        box.append(head)

        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("dim-label")
        self.status.add_css_class("caption")
        box.append(self.status)

        self.follow = self._button("", "suggested-action")
        self.mute = self._button("", "flat")
        self.block = self._button("", "flat")
        for b in (self.follow, self.mute, self.block):
            b.set_visible(False)
            box.append(b)
        self.follow.connect("clicked", lambda *_a: self._toggle("follow", "unfollow",
                                                                  lambda r: r.following or r.requested))
        self.mute.connect("clicked", lambda *_a: self._toggle("mute", "unmute", lambda r: r.muted))
        self.block.connect("clicked", self._on_block)

        if account.url:
            open_btn = Gtk.Button(label=_("Open Profile in Browser"))
            open_btn.add_css_class("flat")
            open_btn.connect("clicked", lambda *_a: (self.popdown(), open_url(self, account.url)))
            box.append(open_btn)
        self.set_child(box)
        self.connect("closed", lambda *_a: GLib.idle_add(self._cleanup))

        if self.is_self:
            self.status.set_label(_("This is your own profile."))
        else:
            self.status.set_label(_("Loading…"))
            spawn(self._load())

    def _button(self, label: str, css: str) -> Gtk.Button:
        b = Gtk.Button(label=label)
        b.add_css_class(css)
        return b

    def _cleanup(self) -> bool:
        if self.get_parent() is not None:
            self.unparent()
        return GLib.SOURCE_REMOVE

    # -- Beziehung ----------------------------------------------------------
    async def _load(self) -> None:
        try:
            self.rel = await self.service.relationship(self.profile, self.account)
        except PlatformError as e:
            self.status.set_label(e.message)
            return
        except Exception:
            log.exception("Beziehung nicht lesbar")
            self.status.set_label(_("Could not load the relationship."))
            return
        self._show()

    def _show(self) -> None:
        rel = self.rel
        assert rel is not None
        parts = []
        if rel.followed_by:
            parts.append(_("Follows you"))
        if rel.muted:
            parts.append(_("Muted"))
        if rel.blocking:
            parts.append(_("Blocked"))
        self.status.set_label(" · ".join(parts))
        self.status.set_visible(bool(parts))
        self.follow.set_visible(not rel.blocking)
        self.follow.set_label(_("Unfollow") if rel.following else
                              _("Cancel Follow Request") if rel.requested else _("Follow"))
        (self.follow.remove_css_class if rel.following or rel.requested else
         self.follow.add_css_class)("suggested-action")
        self.mute.set_visible(not rel.blocking)
        self.mute.set_label(_("Unmute") if rel.muted else _("Mute"))
        self.block.set_visible(True)
        self.block.set_label(_("Unblock") if rel.blocking else _("Block"))
        (self.block.remove_css_class if rel.blocking else self.block.add_css_class)("destructive-action")

    def _toggle(self, on: str, off: str, is_on) -> None:  # type: ignore[no-untyped-def]
        if self.rel is None:
            return
        self._run(off if is_on(self.rel) else on)

    def _run(self, action: str) -> None:
        if self.rel is None:
            return
        for b in (self.follow, self.mute, self.block):
            b.set_sensitive(False)

        async def run() -> None:
            try:
                self.rel = await self.service.set_relationship(
                    self.profile, self.account, action, self.rel)  # type: ignore[arg-type]
            except PlatformError as e:
                self.view.column.deck.win.toast(e.message)
            except Exception:
                log.exception("Aktion %s fehlgeschlagen", action)
                self.view.column.deck.win.toast(_("The action failed."))
            finally:
                for b in (self.follow, self.mute, self.block):
                    b.set_sensitive(True)
                self._show()
        spawn(run())

    def _on_block(self, *_args: object) -> None:
        if self.rel is None:
            return
        if self.rel.blocking:
            self._run("unblock")
            return
        dialog = Adw.AlertDialog(
            heading=_("Block {name}?").format(name=self.account.name),
            body=_("{name} will no longer see your posts and you will not see theirs.")
            .format(name=self.account.name))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("block", _("_Block"))
        dialog.set_response_appearance("block", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, r: self._run("block") if r == "block" else None)
        dialog.present(self.view.column.deck.win)
