# SPDX-License-Identifier: GPL-3.0-or-later
"""Verlauf: veröffentlichte und (teilweise) fehlgeschlagene Beiträge."""

from __future__ import annotations

from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, GLib, Gtk

from .core.models import PostState, TargetState
from .util import label_widget, day_label, first_line, format_time, spawn

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

STATES = (PostState.PUBLISHED, PostState.PARTIAL, PostState.FAILED, PostState.SENDING)


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/history.ui")
class DandelionHistoryView(Adw.Bin):
    __gtype_name__ = "DandelionHistoryView"

    search_bar: Gtk.SearchBar = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    stack: Gtk.Stack = Gtk.Template.Child()
    list_box: Gtk.Box = Gtk.Template.Child()
    empty_page: Adw.StatusPage = Gtk.Template.Child()

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.connect("notify::search-mode-enabled", self._sync_search_button)

    def toggle_search(self) -> None:
        self.search_bar.set_search_mode(not self.search_bar.get_search_mode())

    def _sync_search_button(self, *_args: object) -> None:
        self.win.search_button.set_active(self.search_bar.get_search_mode())

    @Gtk.Template.Callback()
    def on_search_changed(self, *_args: object) -> None:
        self.reload()

    def reload(self) -> None:
        if not getattr(self, "app", None):
            return
        while (child := self.list_box.get_first_child()) is not None:
            self.list_box.remove(child)
        query = self.search_entry.get_text().strip()
        fts = " ".join(f'"{w}"*' for w in query.replace('"', " ").split()) if query else None
        ids = self.app.store.post_ids(STATES, order="COALESCE(published_at, updated_at) DESC",
                                      search=fts)
        profiles = {p.id: p for p in self.app.store.profiles()}
        roles = {r.id: r for r in self.app.store.roles()}
        group: Adw.PreferencesGroup | None = None
        current_day = None
        for pid in ids:
            post = self.app.store.load_post(pid)
            if post is None:
                continue
            when = post.published_at or post.updated_at
            day = day_label(when)
            if day != current_day:
                current_day = day
                group = Adw.PreferencesGroup(title=GLib.markup_escape_text(day))
                self.list_box.append(group)
            group.add(self._post_row(post, profiles, roles))  # type: ignore[union-attr]
        if ids:
            self.stack.set_visible_child_name("list")
        else:
            self.stack.set_visible_child_name("empty")
            if query:
                self.empty_page.set_icon_name("system-search-symbolic")
                self.empty_page.set_title(_("No Results"))
                self.empty_page.set_description(_("Try a different search."))
            else:
                self.empty_page.set_icon_name("mail-send-symbolic")
                self.empty_page.set_title(_("Nothing Published Yet"))
                self.empty_page.set_description(
                    _("Published posts appear here with links to every platform."))

    def _post_row(self, post, profiles, roles) -> Adw.ExpanderRow:  # type: ignore[no-untyped-def]
        row = Adw.ExpanderRow(title=GLib.markup_escape_text(first_line(post.body) or _("Post")))
        row.set_title_lines(2)
        ok = sum(1 for t in post.targets if t.state == TargetState.PUBLISHED)
        failed = sum(1 for t in post.targets if t.state == TargetState.FAILED)
        role = roles.get(post.role_id)
        parts = [format_time(post.published_at or post.updated_at)]
        if role:
            parts.append(f"{role.emoji} {role.name}")
        parts.append(_("{n} published").format(n=ok))
        if failed:
            parts.append(_("{n} failed").format(n=failed))
        row.set_subtitle(GLib.markup_escape_text(" · ".join(parts)))
        if failed:
            icon = Gtk.Image(icon_name="dialog-error-symbolic")
            icon.add_css_class("error")
            row.add_suffix(icon)
            row.set_expanded(True)

        for t in post.targets:
            p = profiles.get(t.profile_id)
            if p is None:
                continue
            platform = self.app.registry.get(p.platform).name \
                if p.platform in self.app.registry else p.platform
            sub = Adw.ActionRow(title=GLib.markup_escape_text(p.full_handle))
            sub.set_subtitle_selectable(True)
            if t.state == TargetState.PUBLISHED:
                sub.set_subtitle(platform)
                img = Gtk.Image(icon_name="object-select-symbolic")
                img.add_css_class("success")
                sub.add_prefix(img)
                if t.remote_url:
                    open_btn = Gtk.Button(icon_name="adw-external-link-symbolic",
                                          valign=Gtk.Align.CENTER, tooltip_text=_("Open Post"))
                    open_btn.add_css_class("flat")
                    label_widget(open_btn, open_btn.get_tooltip_text() or "")
                    open_btn.connect("clicked", lambda _b, u=t.remote_url: Gtk.UriLauncher.new(
                        u).launch(self.get_root(), None, None))
                    sub.add_suffix(open_btn)
                    copy_btn = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER,
                                          tooltip_text=_("Copy Link"))
                    copy_btn.add_css_class("flat")
                    label_widget(copy_btn, copy_btn.get_tooltip_text() or "")
                    copy_btn.connect("clicked", lambda _b, u=t.remote_url: self._copy(u))
                    sub.add_suffix(copy_btn)
                delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                    tooltip_text=_("Delete on {platform}").format(platform=platform))
                delete.add_css_class("flat")
                label_widget(delete, delete.get_tooltip_text() or "")
                delete.connect("clicked", lambda _b, pp=post, prof=p, name=platform:
                               self._confirm_delete(pp.id, prof, name))
                sub.add_suffix(delete)
            elif t.state == TargetState.DELETED:
                sub.set_subtitle(_("{platform} · deleted").format(platform=platform))
                sub.add_prefix(Gtk.Image(icon_name="user-trash-symbolic"))
            elif t.state == TargetState.SENDING:
                sub.set_subtitle(_("Publishing"))
                sub.add_prefix(Adw.Spinner())
            else:
                sub.set_subtitle(GLib.markup_escape_text(
                    f"{platform} · {t.last_error or _('Not published')}"))
                img = Gtk.Image(icon_name="dialog-error-symbolic")
                img.add_css_class("error")
                sub.add_prefix(img)
                retry = Gtk.Button(label=_("_Retry"), use_underline=True, valign=Gtk.Align.CENTER)
                retry.connect("clicked", lambda _b, pp=post, prof=p:
                              self.win.composer.retry(pp.id, {prof.id}))
                sub.add_suffix(retry)
            row.add_row(sub)

        reuse = Adw.ButtonRow(title=_("Use as New Draft"), start_icon_name="edit-copy-symbolic")
        reuse.connect("activated", lambda *_: self._reuse(post))
        row.add_row(reuse)
        return row

    def _copy(self, url: str) -> None:
        Gdk.Display.get_default().get_clipboard().set(url)
        self.win.toast(_("Link copied"))

    def _reuse(self, post) -> None:  # type: ignore[no-untyped-def]
        from .core.models import Media, Post, Target, Variant
        new = Post(role_id=post.role_id, body=post.body, content_warning=post.content_warning,
                   language=post.language, visibility=post.visibility,
                   bluesky_label=post.bluesky_label, use_signature=post.use_signature,
                   variants=[Variant(v.platform, v.body, v.profile_id, v.content_warning,
                                     v.base_hash) for v in post.variants],
                   media=[Media(m.path, m.sha256, m.mime, m.bytes, width=m.width,
                                height=m.height, alt_text=m.alt_text) for m in post.media],
                   targets=[Target(t.profile_id) for t in post.targets])
        self.win.composer.save_now()
        self.win.composer.load_post(new)
        self.win.stack.set_visible_child_name("composer")

    def _confirm_delete(self, post_id: int, profile, platform: str) -> None:  # type: ignore[no-untyped-def]
        dialog = Adw.AlertDialog(
            heading=_("Delete Post on {platform}?").format(platform=platform),
            body=_("The post will be removed from {handle}. This cannot be undone.").format(
                handle=profile.full_handle))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("delete", _("_Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")

        def on_response(_d, response: str) -> None:  # type: ignore[no-untyped-def]
            if response != "delete":
                return

            async def run() -> None:
                await self.app.publisher.delete_remote(post_id, profile.id)
                self.win.toast(_("Post deleted on {platform}").format(platform=platform))
                self.reload()

            spawn(run(), on_error=lambda e: self.win.toast(
                getattr(e, "message", None) or _("The post could not be deleted")))

        dialog.connect("response", on_response)
        dialog.present(self.win)
