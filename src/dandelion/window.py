# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gettext import gettext as _
from gettext import ngettext

from gi.repository import Adw, Gio, GLib, Gtk

from .archive import ALL, CALENDAR, DRAFT, NEW, PUBLISHED, SCHEDULED, Archive, Key
from .composer import DandelionComposer  # noqa: F401  (Typ für das Template)
from .core.models import PostState, Profile, Role
from .deck import DandelionDeck  # noqa: F401  (Typ für das Template)
from .history import DandelionHistoryView  # noqa: F401
from .post_view import DandelionPostView  # noqa: F401
from .scheduled import DandelionScheduledView  # noqa: F401


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/window.ui")
class DandelionWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DandelionWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    split_view: Adw.NavigationSplitView = Gtk.Template.Child()
    sidebar: Adw.Sidebar = Gtk.Template.Child()
    search_bar: Gtk.SearchBar = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    search_button: Gtk.ToggleButton = Gtk.Template.Child()
    content_page: Adw.NavigationPage = Gtk.Template.Child()
    content_title: Adw.WindowTitle = Gtk.Template.Child()
    stack: Gtk.Stack = Gtk.Template.Child()
    sidebar_stack: Gtk.Stack = Gtk.Template.Child()
    mode_group: Adw.ToggleGroup = Gtk.Template.Child()
    read_roles: Gtk.ListBox = Gtk.Template.Child()
    deck: DandelionDeck = Gtk.Template.Child()
    refresh_button: Gtk.Button = Gtk.Template.Child()
    columns_button: Gtk.Button = Gtk.Template.Child()
    composer: DandelionComposer = Gtk.Template.Child()
    post_view: DandelionPostView = Gtk.Template.Child()
    history: DandelionHistoryView = Gtk.Template.Child()
    scheduled: DandelionScheduledView = Gtk.Template.Child()
    publish_button: Adw.SplitButton = Gtk.Template.Child()
    preview_button: Gtk.ToggleButton = Gtk.Template.Child()
    history_search_button: Gtk.ToggleButton = Gtk.Template.Child()
    filter_button: Gtk.MenuButton = Gtk.Template.Child()
    draft_menu: Gio.MenuModel = Gtk.Template.Child()
    scheduled_menu: Gio.MenuModel = Gtk.Template.Child()
    published_menu: Gio.MenuModel = Gtk.Template.Child()

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        app = self.get_application()
        self.settings: Gio.Settings = app.settings
        self.set_default_size(self.settings.get_int("window-width"),
                              self.settings.get_int("window-height"))
        if self.settings.get_boolean("window-maximized"):
            self.maximize()
        if app.get_application_id().endswith("Devel"):
            self.add_css_class("devel")

        self._action("new-post", lambda *_: self.composer.new_post())
        self._action("publish", lambda *_: self.composer.publish())
        self._action("schedule", lambda *_: self.composer.schedule())
        self._action("schedule-slot", lambda *_: self.composer.schedule_next_slot())
        self._action("save-draft", lambda *_: self.composer.save_now(toast=True))
        self._action("add-media", lambda *_: self.composer.open_file_dialog())
        self._action("choose-role", lambda *_: self.composer.popup_roles())
        self._action("manage-roles", lambda *_: self.show_preferences("roles"))
        self._action("search", lambda *_: self.toggle_search())
        self._action("search-history", lambda *_: self.history.toggle_search())
        self._action("refresh-deck", lambda *_: self.deck.refresh_all(manual=True))
        self._action("edit-columns", lambda *_: self.deck.edit_columns())

        preview = Gio.SimpleAction.new_stateful(
            "toggle-preview", None, GLib.Variant.new_boolean(self.settings.get_boolean("show-preview")))
        preview.connect("change-state", self._on_toggle_preview)
        self.add_action(preview)
        view = Gio.SimpleAction.new("view", GLib.VariantType.new("s"))
        view.connect("activate", lambda _a, v: self.show_view(v.get_string()))
        self.add_action(view)

        self.archive = Archive(app, self, self.sidebar, {
            DRAFT: self.draft_menu, SCHEDULED: self.scheduled_menu,
            PUBLISHED: self.published_menu})
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_key_capture_widget(self.sidebar)
        self.search_bar.connect("notify::search-mode-enabled", self._on_search_mode)

        self.composer.setup(app, self)
        self.post_view.setup(app, self)
        self.history.setup(app, self)
        self.scheduled.setup(app, self)
        self.deck.setup(app, self)
        self._mode_sync = False
        self._last_write_view = "composer"
        self._read_roles: dict[Gtk.ListBoxRow, Role] = {}
        self._read_badges: dict[Gtk.ListBoxRow, Gtk.Label] = {}
        self._read_role_id: int | None = None
        self.filter_button.set_popover(self.scheduled.filter_popover)
        app.scheduling.connect("changed", lambda *_: self.posts_changed())
        app.scheduling.connect("missed", lambda *_: self.show_missed_dialog())
        GLib.idle_add(lambda: (self.show_missed_dialog(), False)[1])
        self.composer.connect("notify::can-publish", self._sync_publish)
        self.stack.connect("notify::visible-child-name", self._on_view_changed)
        self._on_view_changed()
        self._sync_publish()
        self.archive.reload()
        self.connect("close-request", self._on_close)

    def _action(self, name: str, cb) -> None:  # type: ignore[no-untyped-def]
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", cb)
        self.add_action(a)

    def _on_toggle_preview(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        # Im eingeklappten Zustand nur vorübergehend zeigen, nicht als Vorgabe merken
        if self.composer.preview_docked():
            self.settings.set_boolean("show-preview", value.get_boolean())
        self.composer.set_preview_visible(value.get_boolean())

    # -- Navigation ------------------------------------------------------
    def show_view(self, name: str) -> None:
        """Zeigt eine Inhaltsseite; im schmalen Fenster auch über der Seitenleiste."""
        if name == "deck":
            self.show_read(show_content=True)
            return
        self._set_mode("write")
        if name in ("composer", "scheduled", "history"):
            self._last_write_view = name
        self.stack.set_visible_child_name(name)
        self.split_view.set_show_content(True)
        self.archive.sync_selection()

    # -- Lesen (Deck) ----------------------------------------------------
    def _set_mode(self, mode: str) -> None:
        self._mode_sync = True
        try:
            self.mode_group.set_active_name(mode)
            self.sidebar_stack.set_visible_child_name(mode)
            self.search_button.set_visible(mode == "write")
        finally:
            self._mode_sync = False

    @Gtk.Template.Callback()
    def on_mode_changed(self, group: Adw.ToggleGroup, *_args: object) -> None:
        if self._mode_sync:
            return
        if group.get_active_name() == "read":
            self.show_read()
        else:
            self.show_view(self._last_write_view)
            # im schmalen Fenster in der Seitenleiste bleiben
            self.split_view.set_show_content(False)

    def show_read(self, show_content: bool = False) -> None:
        """Schaltet auf das Deck um; ohne `show_content` bleibt die Seitenleiste vorn."""
        self._set_mode("read")
        self._fill_read_roles()
        self.stack.set_visible_child_name("deck")
        self.split_view.set_show_content(show_content)
        self.sync_title()
        if show_content:
            GLib.idle_add(self.deck.focus_first)

    def _fill_read_roles(self, force: bool = False) -> None:
        roles = self.get_application().store.roles()
        ids = [r.id for r in roles]
        if not force and ids == [r.id for r in self._read_roles.values()]:
            self._select_read_role()
            return
        while (row := self.read_roles.get_first_child()) is not None:
            self.read_roles.remove(row)
        self._read_roles = {}
        self._read_badges = {}
        for role in roles:
            box = Gtk.Box(spacing=10)
            emoji = Gtk.Label(label=role.emoji or "💬")
            emoji.add_css_class("role-emoji")
            box.append(emoji)
            name = Gtk.Label(label=role.name, xalign=0, hexpand=True)
            box.append(name)
            badge = Gtk.Label(visible=False, valign=Gtk.Align.CENTER)
            badge.add_css_class("unread-badge")
            box.append(badge)
            row = Gtk.ListBoxRow(child=box)
            self._read_badges[row] = badge
            row.update_property([Gtk.AccessibleProperty.LABEL], [role.name])
            self.read_roles.append(row)
            self._read_roles[row] = role
        if self._read_role_id not in ids:
            self._read_role_id = ids[0] if ids else None
            self.deck.set_role(roles[0] if roles else None)
        self._select_read_role()
        self.update_read_badges()

    def update_read_badges(self) -> None:
        """Zeigt je Rolle die Zahl ungelesener Einträge aller lesbaren Profile."""
        app = self.get_application()
        for row, role in self._read_roles.items():
            total = 0
            for rp in app.store.role_profiles(role.id):  # type: ignore[arg-type]
                p = app.store.profile(rp.profile_id)
                if p is not None and app.reader.can_read(p):
                    total += app.reader.unread_total(p)
            badge = self._read_badges[row]
            badge.set_visible(total > 0)
            badge.set_label("99+" if total > 99 else str(total))
            row.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{role.name}, " + ngettext("{n} unread", "{n} unread", total).format(n=total)
                 if total else role.name])

    def _select_read_role(self) -> None:
        for row, role in self._read_roles.items():
            if role.id == self._read_role_id:
                self.read_roles.select_row(row)
                if self.deck.role is None or self.deck.role.id != role.id:
                    self.deck.set_role(role)
                return

    @Gtk.Template.Callback()
    def on_read_role_activated(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        role = self._read_roles.get(row)
        if role is None:
            return
        self._read_role_id = role.id
        if self.deck.role is None or self.deck.role.id != role.id:
            self.deck.set_role(role)
        self.stack.set_visible_child_name("deck")
        self.split_view.set_show_content(True)
        self.sync_title()
        GLib.idle_add(self.deck.focus_first)           # damit j, k, r, f, b sofort gehen

    def reload_read(self) -> None:
        """Nach Änderungen an Rollen und Profilen."""
        if self.mode_group.get_active_name() == "read":
            self._fill_read_roles(force=True)
            self.deck.reload()
            self.sync_title()

    def relogin(self, profile: Profile) -> None:
        """Erneute Anmeldung, zum Beispiel um das Lesen zu erlauben."""
        from .add_profile import DandelionAddProfileDialog
        hint = profile.server if profile.platform == "mastodon" else profile.handle
        DandelionAddProfileDialog(self.get_application(), on_added=lambda _p: self.deck.reload(),
                                  platform=profile.platform, hint=hint).present(self)

    def show_post(self, post_id: int) -> None:
        if self.post_view.show_post(post_id):
            self.show_view("post")
            self.sync_title()

    def current_key(self) -> Key:
        name = self.stack.get_visible_child_name()
        if name == "scheduled":
            return (CALENDAR, None)
        if name == "history":
            return (ALL, None)
        if name == "deck":
            return (NEW, None)
        if name == "post":
            post = self.post_view.post
            return (PUBLISHED, post.id if post else None)
        post = self.composer.post
        if post.id is None:
            return (NEW, None)
        return (DRAFT if post.state == PostState.DRAFT else SCHEDULED, post.id)

    def posts_changed(self) -> None:
        """Nach Änderungen an Beiträgen: Leiste und sichtbare Liste auffrischen."""
        self.archive.reload()
        name = self.stack.get_visible_child_name()
        if name == "scheduled":
            self.scheduled.reload()
        elif name == "history":
            self.history.reload()
        elif name == "post":
            self.post_view.reload()
            self.sync_title()

    def sync_title(self) -> None:
        name = self.stack.get_visible_child_name()
        if name == "scheduled":
            title, subtitle = self.scheduled.title()
        elif name == "history":
            title, subtitle = _("Published"), ""
        elif name == "deck":
            role = self.deck.role
            title = f"{role.emoji} {role.name}" if role else _("Read")
            n = self.deck.column_count()
            subtitle = ngettext("{n} column", "{n} columns", n).format(n=n) if role else ""
        elif name == "post":
            title, subtitle = self.post_view.title()
        else:
            post = self.composer.post
            role = self.composer.role
            title = {
                PostState.SCHEDULED: _("Scheduled Post"),
                PostState.PAUSED: _("Paused Post"),
                PostState.MISSED: _("Missed Post"),
            }.get(post.state, _("New Post") if post.id is None else _("Draft"))
            subtitle = f"{role.emoji} {role.name}" if role else ""
        self.content_title.set_title(title)
        self.content_title.set_subtitle(subtitle)
        self.content_page.set_title(title)

    def toggle_search(self) -> None:
        self.split_view.set_show_content(False)
        self.search_bar.set_search_mode(not self.search_bar.get_search_mode())

    def _on_search_mode(self, *_args: object) -> None:
        active = self.search_bar.get_search_mode()
        self.search_button.set_active(active)
        if not active and self.archive.query:
            self.archive.set_query("")

    @Gtk.Template.Callback()
    def on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.archive.set_query(entry.get_text())

    @Gtk.Template.Callback()
    def on_stop_search(self, *_args: object) -> None:
        self.search_bar.set_search_mode(False)

    @Gtk.Template.Callback()
    def on_sidebar_activated(self, _sidebar: Adw.Sidebar, index: int) -> None:
        self.archive.activate(index)

    @Gtk.Template.Callback()
    def on_sidebar_setup_menu(self, _sidebar: Adw.Sidebar, item: Adw.SidebarItem | None) -> None:
        self.archive.setup_menu(item)

    def _on_view_changed(self, *_args: object) -> None:
        name = self.stack.get_visible_child_name()
        composing = name == "composer"
        self.publish_button.set_visible(composing)
        self.preview_button.set_visible(composing)
        self.history_search_button.set_visible(name == "history")
        self.filter_button.set_visible(name == "scheduled")
        self.refresh_button.set_visible(name == "deck")
        self.columns_button.set_visible(name == "deck")
        if name == "history":
            self.history.reload()
        elif name == "scheduled":
            self.scheduled.reload()
        self.sync_title()

    def _sync_publish(self, *_args: object) -> None:
        self.lookup_action("publish").set_enabled(self.composer.props.can_publish)
        self.lookup_action("schedule").set_enabled(self.composer.props.can_publish)
        role = self.composer.role
        self.lookup_action("schedule-slot").set_enabled(
            self.composer.props.can_publish and bool(role and role.slots))
        self.publish_button.set_tooltip_text(self.composer.publish_tooltip())

    def _on_close(self, *_args: object) -> bool:
        self.flush()
        width, height = self.get_default_size()
        self.settings.set_int("window-width", width)
        self.settings.set_int("window-height", height)
        self.settings.set_boolean("window-maximized", self.is_maximized())
        return False

    # ------------------------------------------------------------------
    def flush(self) -> None:
        self.composer.save_now()

    def toast(self, title: str, button: str | None = None, callback=None,  # type: ignore[no-untyped-def]
              timeout: int = 5) -> Adw.Toast:
        toast = Adw.Toast(title=title, timeout=timeout)
        if button and callback:
            toast.set_button_label(button)
            toast.connect("button-clicked", lambda *_: callback())
        self.toast_overlay.add_toast(toast)
        return toast

    def show_preferences(self, page: str | None = None) -> None:
        from .preferences import DandelionPreferences
        prefs = DandelionPreferences(self.get_application(), self)
        if page:
            prefs.set_visible_page_name(page)
        prefs.connect("closed", lambda *_: (self.composer.reload_profiles(), self.reload_read()))
        prefs.present(self)

    def show_missed_dialog(self) -> None:
        """Fragt nach, was mit verpassten Beiträgen passieren soll."""
        from gettext import gettext as _
        from gettext import ngettext

        from .core.models import PostState
        from .util import first_line
        app = self.get_application()
        if getattr(self, "_missed_dialog_open", False):
            return
        ids = app.store.post_ids([PostState.MISSED], order="scheduled_at")
        if not ids:
            return
        posts = [p for i in ids if (p := app.store.load_post(i))]
        lines = [f"• {first_line(p.body, 60)}" for p in posts[:5]]
        if len(posts) > 5:
            lines.append("…")
        dialog = Adw.AlertDialog(
            heading=ngettext("A Scheduled Post Was Not Sent", "{n} Scheduled Posts Were Not Sent",
                             len(posts)).format(n=len(posts)),
            body=_("The computer was off or asleep at the planned time.") + "\n\n" +
            "\n".join(lines))
        dialog.add_response("later", _("_Decide Later"))
        dialog.add_response("drafts", _("Move to _Drafts"))
        dialog.add_response("send", _("_Send Now"))
        dialog.set_response_appearance("send", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("send")
        dialog.set_close_response("later")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            self._missed_dialog_open = False
            if response == "send":
                for p in posts:
                    self.composer.retry(p.id, None)  # type: ignore[arg-type]
            elif response == "drafts":
                for p in posts:
                    app.store.set_post_schedule(p.id, PostState.DRAFT, None)  # type: ignore[arg-type]
                self.composer.reload_drafts()
            if response != "later":
                for p in posts:
                    app.withdraw_notification(f"post-{p.id}")
            app.scheduling.schedule_changed()

        dialog.connect("response", on_response)
        self._missed_dialog_open = True
        dialog.present(self)

    def show_history(self) -> None:
        self.show_view("history")
