# SPDX-License-Identifier: GPL-3.0-or-later
"""Deck: je Profil einer Rolle eine Spalte mit der Home-Timeline.

Phase 1 des Lese-Modus (siehe docs/deck-columns.md): nur lesen, Mastodon,
Abfrage alle 60 Sekunden, solange das Deck sichtbar ist.
"""

from __future__ import annotations

import logging
from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk, Pango

from .core.models import Profile, Role
from .platforms.base import PlatformError
from .reader.base import FeedPost, ReadScopeMissing
from .reader.content import relative_time, to_markup, to_text
from .util import spawn
from .widgets.avatars import AvatarCache

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

log = logging.getLogger(__name__)

COLUMN_WIDTH = 360
POLL_SECONDS = 60
FIRST_ROWS = 60
MORE_ROWS = 40


def _dim(text: str, *classes: str, ellipsize: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    for c in ("dim-label", *classes):
        label.add_css_class(c)
    if ellipsize:
        label.set_ellipsize(Pango.EllipsizeMode.END)
    return label


def _icon_count(icon: str, count: int, tooltip: str) -> Gtk.Box:
    box = Gtk.Box(spacing=4, tooltip_text=tooltip)
    image = Gtk.Image.new_from_icon_name(icon)
    image.add_css_class("dim-label")
    box.append(image)
    box.append(_dim(str(count), "caption", "numeric"))
    return box


def make_row(post: FeedPost, avatars: AvatarCache) -> Gtk.Box:
    """Ein Beitrag. Medien, Umfragen und Linkkarten erscheinen vorerst als Hinweiszeile."""
    root = Gtk.Box(spacing=10)
    root.add_css_class("feed-row")

    avatar = Adw.Avatar(size=36, text=post.account.name, show_initials=True,
                        valign=Gtk.Align.START)
    avatars.apply(avatar, post.account.avatar_url)
    root.append(avatar)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    root.append(body)

    if post.boosted_by:
        body.append(_dim(_("{name} boosted").format(name=post.boosted_by.name), "caption",
                         ellipsize=True))

    head = Gtk.Box(spacing=6)
    name = Gtk.Label(label=post.account.name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
    name.add_css_class("heading")
    head.append(name)
    age = _dim(relative_time(post.created_at) if post.created_at else "", "caption", "numeric")
    age.set_hexpand(True)
    age.set_xalign(1)
    head.append(age)
    body.append(head)
    body.append(_dim(f"@{post.account.acct}", "caption", ellipsize=True))

    content = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                        use_markup=True, selectable=False, halign=Gtk.Align.FILL)
    # to_markup liefert immer wohlgeformtes Markup (siehe tests/test_reader.py)
    content.set_markup(to_markup(post.html))
    content.set_margin_top(4)

    details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    details.append(content)
    if post.media:
        n = len(post.media)
        no_alt = sum(1 for m in post.media if not m.alt)
        text = ngettext("{n} attachment", "{n} attachments", n).format(n=n)
        if no_alt:
            text += " · " + _("{n} without description").format(n=no_alt)
        details.append(_info_line("image-x-generic-symbolic", text))
    if post.has_poll:
        details.append(_info_line("view-list-bullet-symbolic", _("Poll")))
    if post.card:
        details.append(_info_line("insert-link-symbolic", post.card.title))

    if post.spoiler or (post.sensitive and post.media):
        warning = post.spoiler or _("Sensitive content")
        revealer = Gtk.Revealer(child=details)
        toggle = Gtk.ToggleButton(label=_("Show"), valign=Gtk.Align.CENTER)
        toggle.add_css_class("flat")
        toggle.connect("toggled", lambda b: (revealer.set_reveal_child(b.get_active()),
                                             b.set_label(_("Hide") if b.get_active() else _("Show"))))
        row = Gtk.Box(spacing=8, margin_top=4)
        label = Gtk.Label(label=warning, xalign=0, wrap=True, hexpand=True)
        label.add_css_class("heading")
        row.append(label)
        row.append(toggle)
        body.append(row)
        body.append(revealer)
    else:
        body.append(details)

    counts = Gtk.Box(spacing=16, margin_top=4)
    for icon, n, tip in (("mail-reply-sender-symbolic", post.replies, _("Replies")),
                         ("media-playlist-repeat-symbolic", post.boosts, _("Boosts")),
                         ("starred-symbolic", post.likes, _("Favourites"))):
        if n:
            counts.append(_icon_count(icon, n, tip))
    if counts.get_first_child():
        body.append(counts)

    root.update_property([Gtk.AccessibleProperty.LABEL],
                         [f"{post.account.name}: {to_text(post.spoiler or post.html)[:200]}"])
    return root


def _info_line(icon: str, text: str) -> Gtk.Box:
    box = Gtk.Box(spacing=6)
    image = Gtk.Image.new_from_icon_name(icon)
    image.add_css_class("dim-label")
    box.append(image)
    label = _dim(text, "caption", ellipsize=True)
    label.set_hexpand(True)
    box.append(label)
    return box


class DeckColumn(Gtk.Box):
    """Eine Spalte für ein Profil."""

    def __init__(self, deck: DandelionDeck, profile: Profile) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, width_request=COLUMN_WIDTH)
        self.add_css_class("deck-column")
        self.deck = deck
        self.profile = profile
        self.posts: list[FeedPost] = []
        self.shown = FIRST_ROWS
        self.pending: list[FeedPost] = []
        self._busy = False
        self._exhausted = False

        # -- Kopf ---------------------------------------------------------
        head = Gtk.Box(spacing=10, margin_top=10, margin_bottom=10, margin_start=12, margin_end=6)
        avatar = Adw.Avatar(size=32, text=profile.title, show_initials=True)
        deck.avatars.apply(avatar, profile.avatar_url)
        head.append(avatar)
        who = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label=profile.title, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        title.add_css_class("heading")
        who.append(title)
        who.append(_dim(f"{profile.full_handle} · {_('Home')}", "caption", ellipsize=True))
        head.append(who)
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                                         tooltip_text=_("Refresh"))
        self.refresh_button.add_css_class("flat")
        self.refresh_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Refresh")])
        self.refresh_button.connect("clicked", lambda *_: self.refresh(manual=True))
        head.append(self.refresh_button)
        self.append(head)

        # -- „N neue Beiträge“ -------------------------------------------
        self.new_button = Gtk.Button()
        self.new_button.add_css_class("suggested-action")
        self.new_button.add_css_class("pill")
        self.new_button.set_halign(Gtk.Align.CENTER)
        self.new_button.set_margin_bottom(6)
        self.new_button.connect("clicked", self._show_pending)
        self.new_bar = Gtk.Revealer(child=self.new_button)
        self.append(self.new_bar)
        self.append(Gtk.Separator())

        # -- Inhalt -------------------------------------------------------
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER,
                                         valign=Gtk.Align.CENTER, width_request=32,
                                         height_request=32), "loading")
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("feed-list")
        self.older_button = Gtk.Button(label=_("Show Older Posts"), halign=Gtk.Align.CENTER,
                                       margin_top=12, margin_bottom=12)
        self.older_button.add_css_class("pill")
        self.older_button.connect("clicked", self._older)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.list_box.append(self.listbox)
        self.list_box.append(self.older_button)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, child=self.list_box)
        self.stack.add_named(self.scroller, "list")
        self.status = Adw.StatusPage()
        self.status.add_css_class("compact")
        self.status_button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.status_button.add_css_class("pill")
        self.status.set_child(self.status_button)
        self._status_handler = 0
        self.stack.add_named(self.status, "status")
        self.empty = Adw.StatusPage(icon_name="mail-unread-symbolic", title=_("No Posts Yet"),
                                    description=_("Follow some accounts to fill this column."))
        self.empty.add_css_class("compact")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

        cached = deck.service.cached_home(profile)
        if cached:
            self._set_posts(cached)
        else:
            self.stack.set_visible_child_name("loading")
        self.refresh(manual=True)

    # -- Anzeige ------------------------------------------------------------
    def _render(self) -> None:
        while (row := self.listbox.get_first_child()) is not None:
            self.listbox.remove(row)
        for post in self.posts[: self.shown]:
            self.listbox.append(make_row(post, self.deck.avatars))
        self.older_button.set_visible(not (self._exhausted and self.shown >= len(self.posts)))
        self.stack.set_visible_child_name("list" if self.posts else "empty")

    def _set_posts(self, posts: list[FeedPost]) -> None:
        self.posts = posts
        self.pending = []
        self.new_bar.set_reveal_child(False)
        self._render()

    def _show_pending(self, *_args: object) -> None:
        self._set_posts(self.deck.service.cached_home(self.profile))
        self.scroller.get_vadjustment().set_value(0)

    def _merge_new(self, posts: list[FeedPost]) -> None:
        known = {p.id for p in self.posts}
        fresh = [p for p in posts if p.id not in known]
        at_top = self.scroller.get_vadjustment().get_value() < 8
        if not self.posts or at_top:
            self._set_posts(posts)
            return
        self.pending = fresh
        if fresh:
            self.new_button.set_label(
                ngettext("{n} new post", "{n} new posts", len(fresh)).format(n=len(fresh)))
            self.new_bar.set_reveal_child(True)

    def _older(self, *_args: object) -> None:
        if self.shown + MORE_ROWS <= len(self.posts) or self._exhausted:
            self.shown += MORE_ROWS
            self._render()
            return

        async def run() -> None:
            before = len(self.posts)
            try:
                posts = await self.deck.service.load_older(self.profile)
            except PlatformError as e:
                self.deck.win.toast(e.message)
                return
            self._exhausted = len(posts) == before
            self.posts = posts
            self.shown += MORE_ROWS
            self._render()

        spawn(run())

    def _show_status(self, icon: str, title: str, text: str, button: str | None,
                     callback) -> None:  # type: ignore[no-untyped-def]
        self.status.set_icon_name(icon)
        self.status.set_title(title)
        self.status.set_description(text)
        if self._status_handler:
            self.status_button.disconnect(self._status_handler)
            self._status_handler = 0
        self.status_button.set_visible(bool(button))
        if button:
            self.status_button.set_label(button)
            self._status_handler = self.status_button.connect("clicked", lambda *_: callback())
        self.stack.set_visible_child_name("status")

    # -- Laden --------------------------------------------------------------
    def refresh(self, manual: bool = False) -> None:
        if self._busy:
            return
        self._busy = True
        self.refresh_button.set_sensitive(False)

        async def run() -> None:
            try:
                posts = await self.deck.service.refresh_home(self.profile)
            except ReadScopeMissing:
                if not self.posts:
                    self._show_status(
                        "dialog-password-symbolic", _("Allow Reading"),
                        _("{handle} was signed in before Dandelion could read timelines. "
                          "Sign in again to allow reading.").format(handle=self.profile.full_handle),
                        _("Sign In Again"), lambda: self.deck.win.relogin(self.profile))
            except PlatformError as e:
                if not self.posts:
                    if e.auth:
                        self._show_status("dialog-password-symbolic", _("Sign In Again"),
                                          e.message, _("Sign In Again"),
                                          lambda: self.deck.win.relogin(self.profile))
                    else:
                        self._show_status("network-error-symbolic", _("Could Not Load Posts"),
                                          e.message, _("Try Again"),
                                          lambda: self.refresh(manual=True))
                elif manual:
                    self.deck.win.toast(e.message)
            else:
                if manual:
                    self._set_posts(posts)
                else:
                    self._merge_new(posts)
            finally:
                self._busy = False
                self.refresh_button.set_sensitive(True)

        spawn(run())


class DandelionDeck(Gtk.Box):
    __gtype_name__ = "DandelionDeck"

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.role: Role | None = None
        self.columns: list[DeckColumn] = []
        self._timer = 0

        self.columns_box = Gtk.Box()
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                           vscrollbar_policy=Gtk.PolicyType.NEVER,
                                           child=self.columns_box, vexpand=True, hexpand=True)
        self.empty = Adw.StatusPage(icon_name="mail-unread-symbolic",
                                    title=_("Nothing to Read Here"),
                                    description=_("Add a Mastodon profile to this role to see "
                                                  "its timeline."))
        self.empty_button = Gtk.Button(label=_("Roles and Profiles"), halign=Gtk.Align.CENTER)
        self.empty_button.add_css_class("pill")
        self.empty_button.add_css_class("suggested-action")
        self.empty_button.set_action_name("win.manage-roles")
        self.empty.set_child(self.empty_button)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.scroller, "columns")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.service = app.reader
        self.avatars = AvatarCache(app.http)

    # -- Rolle --------------------------------------------------------------
    def set_role(self, role: Role | None) -> None:
        self.role = role
        self.reload()

    def reload(self) -> None:
        """Baut die Spalten der gewählten Rolle neu auf."""
        while (child := self.columns_box.get_first_child()) is not None:
            self.columns_box.remove(child)
        self.columns = []
        profiles: list[Profile] = []
        if self.role is not None:
            for rp in self.app.store.role_profiles(self.role.id):  # type: ignore[arg-type]
                p = self.app.store.profile(rp.profile_id)
                if p is not None and self.service.can_read(p):
                    profiles.append(p)
        for p in profiles:
            column = DeckColumn(self, p)
            if len(profiles) == 1:
                column.set_hexpand(True)
            self.columns.append(column)
            self.columns_box.append(column)
            if p is not profiles[-1]:
                self.columns_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.stack.set_visible_child_name("columns" if profiles else "empty")

    def column_count(self) -> int:
        return len(self.columns)

    def refresh_all(self, manual: bool = True) -> None:
        for column in self.columns:
            column.refresh(manual=manual)

    # -- Abfrage ------------------------------------------------------------
    def _on_map(self, *_args: object) -> None:
        if not self._timer:
            self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.refresh_all(manual=False)

    def _on_unmap(self, *_args: object) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _poll(self) -> bool:
        self.refresh_all(manual=False)
        return GLib.SOURCE_CONTINUE
