# SPDX-License-Identifier: GPL-3.0-or-later
"""Einzelansicht eines veröffentlichten Beitrags."""

from __future__ import annotations

from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gtk

from .core.models import Post, PostState
from .util import format_time

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/post-view.ui")
class DandelionPostView(Adw.Bin):
    __gtype_name__ = "DandelionPostView"

    cw_label: Gtk.Label = Gtk.Template.Child()
    body_label: Gtk.Label = Gtk.Template.Child()
    media_box: Gtk.FlowBox = Gtk.Template.Child()
    targets_group: Adw.PreferencesGroup = Gtk.Template.Child()

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.post: Post | None = None
        self._rows: list[Gtk.Widget] = []

    def show_post(self, post_id: int) -> bool:
        post = self.app.store.load_post(post_id)
        if post is None:
            return False
        self.post = post
        self.cw_label.set_visible(bool(post.content_warning))
        self.cw_label.set_label(post.content_warning)
        self.body_label.set_label(post.body)

        self.media_box.remove_all()
        for m in post.media:
            if not m.mime.startswith("image/"):
                continue
            pic = Gtk.Picture.new_for_filename(m.path)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(96, 96)
            pic.set_alternative_text(m.alt_text or None)
            pic.add_css_class("preview-image")
            self.media_box.append(pic)
        self.media_box.set_visible(self.media_box.get_first_child() is not None)

        for row in self._rows:
            self.targets_group.remove(row)
        self._rows = []
        profiles = {p.id: p for p in self.app.store.profiles()}
        for t in post.targets:
            row = self.win.history.target_row(post, t, profiles)
            if row is not None:
                self.targets_group.add(row)
                self._rows.append(row)
        return True

    def reload(self) -> None:
        if self.post is not None and self.post.id is not None:
            self.show_post(self.post.id)

    def title(self) -> tuple[str, str]:
        if self.post is None:
            return _("Published"), ""
        role = self.app.store.role(self.post.role_id) if self.post.role_id else None
        subtitle = " · ".join(x for x in (format_time(self.post.published_at or
                                                      self.post.updated_at),
                                          role.name if role else "") if x)
        titles = {
            PostState.SENDING: _("Publishing"),
            PostState.PARTIAL: _("Partly Published"),
            PostState.FAILED: _("Not Published"),
        }
        return titles.get(self.post.state, _("Published")), subtitle

    @Gtk.Template.Callback()
    def on_reuse(self, *_args: object) -> None:
        if self.post is not None:
            self.win.history.reuse(self.post)
