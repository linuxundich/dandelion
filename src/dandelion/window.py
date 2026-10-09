# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk

from .archive import ALL, CALENDAR, DRAFT, NEW, PUBLISHED, SCHEDULED, Archive, Key
from .composer import DandelionComposer  # noqa: F401  (Typ für das Template)
from .core.models import PostState
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
    composer: DandelionComposer = Gtk.Template.Child()
    post_view: DandelionPostView = Gtk.Template.Child()
    history: DandelionHistoryView = Gtk.Template.Child()
    scheduled: DandelionScheduledView = Gtk.Template.Child()
    publish_button: Adw.SplitButton = Gtk.Template.Child()
    preview_button: Gtk.ToggleButton = Gtk.Template.Child()
    history_search_button: Gtk.ToggleButton = Gtk.Template.Child()
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
        self.stack.set_visible_child_name(name)
        self.split_view.set_show_content(True)
        self.archive.sync_selection()

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
            title, subtitle = _("Calendar"), ""
        elif name == "history":
            title, subtitle = _("Published"), ""
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
        prefs.connect("closed", lambda *_: self.composer.reload_profiles())
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
