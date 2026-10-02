# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gi.repository import Adw, Gio, GLib, Gtk

from .composer import DandelionComposer  # noqa: F401  (Typ für das Template)
from .history import DandelionHistoryView  # noqa: F401
from .scheduled import DandelionScheduledView  # noqa: F401


@Gtk.Template(resource_path="/de/linuxundich/Dandelion/ui/window.ui")
class DandelionWindow(Adw.ApplicationWindow):
    __gtype_name__ = "DandelionWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    stack: Adw.ViewStack = Gtk.Template.Child()
    composer: DandelionComposer = Gtk.Template.Child()
    history: DandelionHistoryView = Gtk.Template.Child()
    scheduled: DandelionScheduledView = Gtk.Template.Child()
    scheduled_page: Adw.ViewStackPage = Gtk.Template.Child()
    publish_button: Adw.SplitButton = Gtk.Template.Child()
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
        self._action("schedule", lambda *_: self.composer.schedule())
        self._action("schedule-slot", lambda *_: self.composer.schedule_next_slot())
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
        self.scheduled.setup(app, self)
        app.scheduling.connect("changed", lambda *_: self._sync_scheduled_badge())
        app.scheduling.connect("missed", lambda *_: self.show_missed_dialog())
        self._sync_scheduled_badge()
        GLib.idle_add(lambda: (self.show_missed_dialog(), False)[1])
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
        elif name == "scheduled":
            self.scheduled.reload()

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

    def _sync_scheduled_badge(self) -> None:
        from .core.models import PostState
        store = self.get_application().store
        missed = len(store.post_ids([PostState.MISSED]))
        self.scheduled_page.set_needs_attention(missed > 0)
        self.scheduled_page.set_badge_number(missed)
        if self.stack.get_visible_child_name() == "scheduled":
            self.scheduled.reload()

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
        self.stack.set_visible_child_name("history")
