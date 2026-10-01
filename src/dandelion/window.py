# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gi.repository import Adw, Gio, GLib, Gtk

from .composer import DandelionComposer  # noqa: F401  (Typ für das Template)
from .history import DandelionHistoryView  # noqa: F401


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/window.ui")
class DandelionWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DandelionWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    composer: DandelionComposer = Gtk.Template.Child()
    history: DandelionHistoryView = Gtk.Template.Child()
    publish_button: Gtk.Button = Gtk.Template.Child()
    drafts_button: Gtk.ToggleButton = Gtk.Template.Child()
    search_button: Gtk.ToggleButton = Gtk.Template.Child()

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
        self._action("save-draft", lambda *_: self.composer.save_now(toast=True))
        self._action("add-media", lambda *_: self.composer.open_file_dialog())
        self._action("choose-role", lambda *_: self.composer.popup_roles())
        self._action("manage-roles", lambda *_: self.show_preferences("roles"))
        self._action("search", lambda *_: self.history.toggle_search())

        drafts = Gio.SimpleAction.new_stateful(
            "toggle-drafts", None,
            GLib.Variant.new_boolean(self.settings.get_boolean("drafts-sidebar-visible")))
        drafts.connect("change-state", self._on_toggle_drafts)
        self.add_action(drafts)
        preview = Gio.SimpleAction.new_stateful(
            "toggle-preview", None, GLib.Variant.new_boolean(self.settings.get_boolean("show-preview")))
        preview.connect("change-state", self._on_toggle_preview)
        self.add_action(preview)
        view = Gio.SimpleAction.new("view", GLib.VariantType.new("s"))
        view.connect("activate", lambda _a, v: self.stack.set_visible_child_name(v.get_string()))
        self.add_action(view)

        self.composer.setup(app, self)
        self.history.setup(app, self)
        self.composer.connect("notify::can-publish", self._sync_publish)
        self.stack.connect("notify::visible-child-name", self._on_view_changed)
        self._on_view_changed()
        self._sync_publish()
        self.connect("close-request", self._on_close)

    def _action(self, name: str, cb) -> None:  # type: ignore[no-untyped-def]
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", cb)
        self.add_action(a)

    def _on_toggle_drafts(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.settings.set_boolean("drafts-sidebar-visible", value.get_boolean())
        self.composer.set_drafts_visible(value.get_boolean())

    def _on_toggle_preview(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.settings.set_boolean("show-preview", value.get_boolean())
        self.composer.set_preview_visible(value.get_boolean())

    def _on_view_changed(self, *_args: object) -> None:
        name = self.stack.get_visible_child_name()
        composing = name == "composer"
        self.publish_button.set_visible(composing)
        self.drafts_button.set_visible(composing)
        self.search_button.set_visible(name == "history")
        if name == "history":
            self.history.reload()

    def _sync_publish(self, *_args: object) -> None:
        self.lookup_action("publish").set_enabled(self.composer.props.can_publish)
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

    def show_history(self) -> None:
        self.stack.set_visible_child_name("history")
